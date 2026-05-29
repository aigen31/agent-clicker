"""Watchdog: reclaim expired leases."""

from __future__ import annotations

import asyncio
import logging

from agent_clicker.db.repository import TaskRepository
from agent_clicker.settings_store import SettingsStore

logger = logging.getLogger(__name__)


class Watchdog:
    def __init__(
        self,
        repo: TaskRepository,
        settings_store: SettingsStore,
        interval_seconds: float = 30.0,
    ) -> None:
        self._repo = repo
        self._store = settings_store
        self._interval = interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        self._stopping.clear()
        self._task = asyncio.create_task(self._loop(), name="watchdog")

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
                reclaimed = await self._repo.reclaim_expired(
                    lease_timeout_seconds=worker_cfg.lease_timeout_seconds
                )
                if reclaimed:
                    logger.warning("watchdog.reclaimed", extra={"count": reclaimed})
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("watchdog.error")
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
            except asyncio.TimeoutError:
                pass
