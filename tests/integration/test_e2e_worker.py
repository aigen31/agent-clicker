"""End-to-end test: dispatcher → worker → mock agent → DB."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_clicker.browser.runner import AgentRunner
from agent_clicker.config import BrowserProfileDefaults, Settings
from agent_clicker.domain.task import TaskStatus
from agent_clicker.observability.artifacts import ArtifactStore
from agent_clicker.profiles.factory import ProfileFactory
from agent_clicker.proxy.pool import ProxyPool
from agent_clicker.queue.dispatcher import Dispatcher
from agent_clicker.workers.pool import WorkerPool
from agent_clicker.workers.worker import Worker


class _FakeBrowserProfile:
    pass


class _FakeProfileFactory(ProfileFactory):
    def build_browser_profile(self, spec):  # type: ignore[override]
        return _FakeBrowserProfile()


def _fake_history(success: bool = True) -> MagicMock:
    h = MagicMock()
    h.is_successful = MagicMock(return_value=success)
    h.number_of_steps = MagicMock(return_value=3)
    h.final_result = MagicMock(return_value="ok")
    return h


def _fake_agent_builder(success: bool = True):
    def builder(**kwargs: Any) -> Any:
        agent = MagicMock()
        agent.run = AsyncMock(return_value=_fake_history(success))
        agent.close = AsyncMock()
        return agent

    return builder


@pytest.mark.asyncio
async def test_e2e_success_flow(task_repo, settings_store, tmp_path) -> None:
    t = await task_repo.create_task(ad_id=1, link="https://example.com", description="d")

    settings = Settings()
    settings.llm_api_key = settings.llm_api_key  # noqa: PLW0127
    proxy_pool = ProxyPool(settings)
    await proxy_pool.start()
    artifacts = ArtifactStore(tmp_path)
    runner = AgentRunner(settings_store, artifacts, settings, agent_builder=_fake_agent_builder(True))

    queue: asyncio.Queue = asyncio.Queue(maxsize=4)

    def build_factory(defaults: BrowserProfileDefaults) -> ProfileFactory:
        return _FakeProfileFactory(defaults, settings)

    def build_worker(wid: str) -> Worker:
        return Worker(
            worker_id=wid,
            in_queue=queue,
            repo=task_repo,
            settings_store=settings_store,
            proxy_pool=proxy_pool,
            profile_factory_builder=build_factory,
            runner=runner,
            artifact_store=artifacts,
        )

    dispatcher = Dispatcher(task_repo, settings_store, queue, poll_interval_seconds=0.1)
    pool = WorkerPool(settings_store, build_worker, queue)
    await dispatcher.start()
    await pool.start()

    # Wait until task reaches terminal status (timeout safety)
    for _ in range(50):
        await asyncio.sleep(0.2)
        got = await task_repo.get_task(t.id)
        if got and got.status in TaskStatus.TERMINAL:
            break

    await dispatcher.stop()
    await pool.stop()
    await proxy_pool.stop()

    got = await task_repo.get_task(t.id)
    assert got is not None
    assert got.status == TaskStatus.COMPLETED
    assert got.result and got.result.get("is_successful") is True
    assert got.profile and got.profile.get("user_agent")


@pytest.mark.asyncio
async def test_e2e_failure_retries(task_repo, settings_store, tmp_path) -> None:
    t = await task_repo.create_task(ad_id=2, link="https://example.com", description="d", max_attempts=2)

    settings = Settings()
    proxy_pool = ProxyPool(settings)
    await proxy_pool.start()
    artifacts = ArtifactStore(tmp_path)
    runner = AgentRunner(settings_store, artifacts, settings, agent_builder=_fake_agent_builder(False))

    queue: asyncio.Queue = asyncio.Queue(maxsize=2)

    def build_factory(defaults: BrowserProfileDefaults) -> ProfileFactory:
        return _FakeProfileFactory(defaults, settings)

    def build_worker(wid: str) -> Worker:
        return Worker(
            worker_id=wid,
            in_queue=queue,
            repo=task_repo,
            settings_store=settings_store,
            proxy_pool=proxy_pool,
            profile_factory_builder=build_factory,
            runner=runner,
            artifact_store=artifacts,
        )

    dispatcher = Dispatcher(task_repo, settings_store, queue, poll_interval_seconds=0.05)
    pool = WorkerPool(settings_store, build_worker, queue)
    await dispatcher.start()
    await pool.start()

    # 1st attempt should fail and move back to pending with future exec_time.
    for _ in range(30):
        await asyncio.sleep(0.1)
        got = await task_repo.get_task(t.id)
        if got and got.attempts >= 1 and got.status == TaskStatus.PENDING:
            break

    await dispatcher.stop()
    await pool.stop()
    await proxy_pool.stop()

    got = await task_repo.get_task(t.id)
    assert got is not None
    # Either retry scheduled (pending) or terminal failure.
    assert got.attempts >= 1
    assert got.last_error
