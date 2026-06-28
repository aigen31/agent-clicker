"""Composition root."""

from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path

import uvicorn

from agent_clicker.admin.app import create_app
from agent_clicker.browser.runner import AgentRunner
from agent_clicker.config import (
    AgentSettings,
    BrowserProfileDefaults,
    Settings,
    WorkerRuntimeSettings,
)
from agent_clicker.db.engine import build_engines, dispose_engines
from agent_clicker.db.repository import AdProxyRepository, SettingsRepository, TaskProxyRepository, TaskRepository
from agent_clicker.lifecycle import Lifespan
from agent_clicker.observability.artifacts import ArtifactStore
from agent_clicker.observability.broadcaster import LogBroadcaster
from agent_clicker.observability.logging import configure_logging
from agent_clicker.profiles.factory import ProfileFactory
from agent_clicker.proxy.pool import ProxyPool
from agent_clicker.queue.dispatcher import Dispatcher
from agent_clicker.queue.watchdog import Watchdog
from agent_clicker.settings_store import SettingsStore
from agent_clicker.workers.pool import WorkerPool
from agent_clicker.workers.worker import Worker

logger = logging.getLogger(__name__)


def _agent_defaults(s: Settings) -> AgentSettings:
    return AgentSettings(
        llm_model=s.boot_llm_model,
        max_steps=s.boot_agent_max_steps,
        use_vision=s.boot_agent_use_vision,
        use_thinking=s.boot_agent_use_thinking,
        max_failures=s.boot_agent_max_failures,
        step_timeout=s.boot_agent_step_timeout,
        max_actions_per_step=s.boot_agent_max_actions_per_step,
        enable_planning=s.boot_agent_enable_planning,
        extend_system_message=s.boot_agent_extend_system_message,
    )


def _browser_defaults(s: Settings) -> BrowserProfileDefaults:
    return BrowserProfileDefaults(
        headless=s.boot_browser_headless,
        disable_security=s.boot_browser_disable_security,
        wait_between_actions=s.boot_browser_wait_between_actions,
        minimum_wait_page_load_time=s.boot_browser_minimum_wait_page_load_time,
        wait_for_network_idle_page_load_time=s.boot_browser_wait_for_network_idle_page_load_time,
        highlight_elements=s.boot_browser_highlight_elements,
        enable_default_extensions=s.boot_browser_enable_default_extensions,
        cross_origin_iframes=s.boot_browser_cross_origin_iframes,
        max_iframes=s.boot_browser_max_iframes,
    )


def _worker_defaults(s: Settings) -> WorkerRuntimeSettings:
    return WorkerRuntimeSettings(
        worker_concurrency=s.boot_worker_concurrency,
        lease_timeout_seconds=s.boot_lease_timeout_seconds,
        max_attempts=s.boot_max_attempts,
        backoff_base_seconds=s.boot_backoff_base_seconds,
        min_time_on_site_seconds=s.boot_min_time_on_site_seconds,
        max_time_on_site_seconds=s.boot_max_time_on_site_seconds,
    )


def _validate_admin_binding(s: Settings) -> None:
    if s.admin_host not in ("127.0.0.1", "localhost") and not s.admin_allow_public:
        raise SystemExit(
            f"admin_host={s.admin_host!r} requires admin_allow_public=true (refusing to expose admin panel)"
        )


async def run() -> None:
    settings = Settings()
    broadcaster = LogBroadcaster(buffer_size=settings.log_buffer_size)
    configure_logging(settings.log_level, broadcaster)
    logger.info("boot.start")

    engines = build_engines(
        external_dsn=settings.external_tasks_dsn,
        internal_dsn=settings.internal_state_dsn,
        external_migrations_dsn=settings.external_migrations_dsn,
    )
    settings_repo = SettingsRepository(engines.internal_session)
    settings_store = SettingsStore(settings_repo)
    await settings_store.bootstrap(
        agent_defaults=_agent_defaults(settings),
        browser_defaults=_browser_defaults(settings),
        worker_defaults=_worker_defaults(settings),
    )

    worker_cfg = await settings_store.get_worker()

    task_repo = TaskRepository(
        external_session=engines.external_session,
        internal_session=engines.internal_session,
        default_max_attempts=worker_cfg.max_attempts,
    )
    # Use external migrations database for proxy repos if available, otherwise fallback to internal
    proxy_repo_session = engines.external_migrations_session or engines.internal_session
    ad_proxy_repo = AdProxyRepository(proxy_repo_session)
    task_proxy_repo = TaskProxyRepository(proxy_repo_session)
    artifact_store = ArtifactStore(Path(settings.artifacts_dir))
    proxy_pool = ProxyPool(settings)
    runner = AgentRunner(settings_store, artifact_store, settings)

    queue: asyncio.Queue = asyncio.Queue(maxsize=worker_cfg.worker_concurrency)

    def build_factory(defaults: BrowserProfileDefaults) -> ProfileFactory:
        return ProfileFactory(defaults, settings)

    def build_worker(wid: str) -> Worker:
        return Worker(
            worker_id=wid,
            in_queue=queue,
            repo=task_repo,
            settings_store=settings_store,
            proxy_pool=proxy_pool,
            profile_factory_builder=build_factory,
            runner=runner,
            artifact_store=artifact_store,
            ad_proxy_repo=ad_proxy_repo,
            task_proxy_repo=task_proxy_repo,
        )

    dispatcher = Dispatcher(task_repo, settings_store, queue)
    watchdog = Watchdog(task_repo, settings_store)
    worker_pool = WorkerPool(settings_store, build_worker, queue)

    _validate_admin_binding(settings)
    app = create_app(
        repo=task_repo,
        ad_proxy_repo=ad_proxy_repo,
        task_proxy_repo=task_proxy_repo,
        settings_store=settings_store,
        broadcaster=broadcaster,
        artifact_store=artifact_store,
        static_settings=settings,
    )
    uv_cfg = uvicorn.Config(
        app,
        host=settings.admin_host,
        port=settings.admin_port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )
    server = uvicorn.Server(uv_cfg)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: setattr(server, "should_exit", True))
        except NotImplementedError:  # windows / restricted env
            pass

    try:
        async with Lifespan(
            [proxy_pool, dispatcher, watchdog, worker_pool],
            stop_timeout=worker_cfg.lease_timeout_seconds + 30,
        ):
            logger.info("boot.ready")
            await server.serve()
    finally:
        await dispose_engines(engines)
        logger.info("boot.shutdown")
