"""WorkerPool: spawn N workers, manage graceful shutdown."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from agent_clicker.settings_store import SettingsStore
from agent_clicker.workers.worker import Worker

logger = logging.getLogger(__name__)


class WorkerPool:
    def __init__(
        self,
        settings_store: SettingsStore,
        build_worker: Callable[[str], Worker],
        in_queue: asyncio.Queue,
        *,
        worker_id_prefix: str = "worker",
    ) -> None:
        self._store = settings_store
        self._build = build_worker
        self._prefix = worker_id_prefix
        self._queue = in_queue
        self._tasks: list[asyncio.Task[None]] = []
        self._concurrency = 0

    async def start(self) -> None:
        cfg = await self._store.get_worker()
        self._concurrency = max(1, cfg.worker_concurrency)
        for i in range(self._concurrency):
            wid = f"{self._prefix}-{i}"
            w = self._build(wid)
            self._tasks.append(asyncio.create_task(w.run(), name=wid))
        logger.info("worker_pool.start", extra={"concurrency": self._concurrency})

    async def stop(self) -> None:
        cfg = await self._store.get_worker()
        # wait for queue to drain (bounded by lease_timeout)
        try:
            await asyncio.wait_for(self._queue.join(), timeout=cfg.lease_timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning("worker_pool.drain_timeout")
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._tasks.clear()
