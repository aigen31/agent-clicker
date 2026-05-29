"""Dispatcher: polls external `tasks` and feeds an asyncio.Queue of TaskDTO."""

from __future__ import annotations

import asyncio
import logging

from agent_clicker.db.repository import TaskRepository
from agent_clicker.domain.task import TaskDTO
from agent_clicker.settings_store import SettingsStore

logger = logging.getLogger(__name__)


class Dispatcher:
    def __init__(
        self,
        repo: TaskRepository,
        settings_store: SettingsStore,
        out_queue: asyncio.Queue[TaskDTO],
        *,
        worker_id_prefix: str = "dispatcher",
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self._repo = repo
        self._store = settings_store
        self._queue = out_queue
        self._prefix = worker_id_prefix
        self._interval = poll_interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        self._stopping.clear()
        self._task = asyncio.create_task(self._loop(), name="dispatcher")

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

    async def _loop(self) -> None:
        while not self._stopping.is_set():
            try:
                worker_cfg = await self._store.get_worker()
                free = self._queue.maxsize - self._queue.qsize() if self._queue.maxsize else 10
                if free <= 0:
                    await asyncio.sleep(self._interval)
                    continue
                batch = await self._repo.lease_batch(
                    worker_id=self._prefix,
                    batch_size=free,
                    lease_timeout_seconds=worker_cfg.lease_timeout_seconds,
                )
                if batch:
                    logger.info("dispatcher.leased", extra={"count": len(batch)})
                    for t in batch:
                        await self._queue.put(t)
                else:
                    await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("dispatcher.error")
                await asyncio.sleep(self._interval)
