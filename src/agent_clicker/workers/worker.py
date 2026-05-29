"""Worker: pulls a TaskDTO from queue and runs end-to-end."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Callable

from agent_clicker.browser.runner import AgentRunner
from agent_clicker.config import BrowserProfileDefaults
from agent_clicker.db.repository import TaskRepository
from agent_clicker.domain.task import TaskDTO, TaskResult
from agent_clicker.observability.logging import current_task_id, current_worker_id
from agent_clicker.profiles.factory import ProfileFactory
from agent_clicker.proxy.pool import ProxyPool
from agent_clicker.settings_store import SettingsStore

logger = logging.getLogger(__name__)


ProfileFactoryBuilder = Callable[[BrowserProfileDefaults], ProfileFactory]


class Worker:
    def __init__(
        self,
        *,
        worker_id: str,
        in_queue: asyncio.Queue[TaskDTO],
        repo: TaskRepository,
        settings_store: SettingsStore,
        proxy_pool: ProxyPool,
        profile_factory_builder: ProfileFactoryBuilder,
        runner: AgentRunner,
    ) -> None:
        self.worker_id = worker_id
        self._queue = in_queue
        self._repo = repo
        self._store = settings_store
        self._proxy_pool = proxy_pool
        self._build_factory = profile_factory_builder
        self._runner = runner

    async def run(self) -> None:
        while True:
            task = await self._queue.get()
            tok_t = current_task_id.set(task.id)
            tok_w = current_worker_id.set(self.worker_id)
            try:
                await self._handle(task)
            finally:
                current_task_id.reset(tok_t)
                current_worker_id.reset(tok_w)
                self._queue.task_done()

    async def _handle(self, task: TaskDTO) -> None:
        scheduled_at = task.exec_time
        try:
            browser_defaults = await self._store.get_browser()
            factory = self._build_factory(browser_defaults)
            proxy = await self._proxy_pool.acquire(preferred_geo=None)
            spec = factory.build_spec(proxy=proxy)
            profile_audit = spec.to_audit_dict()
            browser_profile = factory.build_browser_profile(spec)

            run_result = await self._runner.run(
                task=task,
                worker_id=self.worker_id,
                browser_profile=browser_profile,
            )

            result = TaskResult(
                is_successful=run_result.is_successful,
                steps=run_result.steps,
                duration_seconds=run_result.duration_seconds,
                final_result=run_result.final_result,
                artifacts_dir=run_result.artifacts_dir,
                error=None if run_result.is_successful else "agent reported failure",
                scheduled_at=scheduled_at,
                started_at=run_result.started_at,
                finished_at=run_result.finished_at,
                extra={"history": run_result.history_summary},
            )

            if run_result.is_successful:
                await self._repo.mark_done(
                    task.id,
                    result=result.to_jsonable(),
                    profile=profile_audit,
                )
                await self._proxy_pool.release(proxy, healthy=True)
                logger.info("task.done", extra={"steps": run_result.steps})
            else:
                await self._retry_or_fail(task, profile_audit, "agent.is_successful=false", result)
                await self._proxy_pool.release(proxy, healthy=True)

        except asyncio.CancelledError:
            logger.warning("task.cancelled")
            await self._repo.mark_failed(
                task.id,
                error="worker cancelled (graceful shutdown)",
                profile=None,
                retry_at=datetime.utcnow(),
            )
            raise
        except Exception as exc:
            logger.exception("task.exception")
            try:
                await self._retry_or_fail(task, None, repr(exc), None)
            except Exception:  # pragma: no cover
                logger.exception("task.failed_to_record")
            try:
                await self._proxy_pool.release(None, healthy=False)
            except Exception:
                pass

    async def _retry_or_fail(
        self,
        task: TaskDTO,
        profile_audit: dict[str, Any] | None,
        error: str,
        result: TaskResult | None,
    ) -> None:
        worker_cfg = await self._store.get_worker()
        # attempts is incremented at lease time → check against max_attempts.
        attempts = task.attempts or 0  # already includes this attempt
        max_attempts = task.max_attempts or worker_cfg.max_attempts
        if attempts < max_attempts:
            delay = worker_cfg.backoff_base_seconds * (2 ** max(attempts - 1, 0))
            retry_at = datetime.utcnow() + timedelta(seconds=delay)
            await self._repo.mark_failed(
                task.id,
                error=error,
                profile=profile_audit,
                retry_at=retry_at,
            )
            logger.info("task.retry_scheduled", extra={"retry_at": retry_at.isoformat(), "attempts": attempts})
        else:
            await self._repo.mark_failed(
                task.id,
                error=error,
                profile=profile_audit,
                retry_at=None,
            )
            logger.error("task.failed_terminal", extra={"attempts": attempts})
