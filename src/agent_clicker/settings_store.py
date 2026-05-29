"""Cache + bootstrap layer for dynamic settings."""

from __future__ import annotations

import asyncio
import time

from agent_clicker.config import AgentSettings, BrowserProfileDefaults, WorkerRuntimeSettings
from agent_clicker.db.repository import SettingsRepository


class SettingsStore:
    _AGENT = "agent"
    _BROWSER = "browser"
    _WORKER = "worker"

    def __init__(self, repo: SettingsRepository, ttl_seconds: float = 5.0) -> None:
        self._repo = repo
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[float, object]] = {}
        self._lock = asyncio.Lock()

    async def bootstrap(
        self,
        *,
        agent_defaults: AgentSettings,
        browser_defaults: BrowserProfileDefaults,
        worker_defaults: WorkerRuntimeSettings,
    ) -> None:
        """Idempotent: insert missing keys, merge missing fields into existing."""

        async def _ensure(key: str, defaults: dict[str, object]) -> None:
            current = await self._repo.get(key) or {}
            merged = {**defaults, **current}
            if merged != current:
                await self._repo.upsert(key, merged)

        await _ensure(self._AGENT, agent_defaults.model_dump())
        await _ensure(self._BROWSER, browser_defaults.model_dump())
        await _ensure(self._WORKER, worker_defaults.model_dump())

    def invalidate(self) -> None:
        self._cache.clear()

    async def _get(self, key: str, model_cls: type) -> object:
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached and (now - cached[0]) < self._ttl:
            return cached[1]
        async with self._lock:
            cached = self._cache.get(key)
            if cached and (time.monotonic() - cached[0]) < self._ttl:
                return cached[1]
            raw = await self._repo.get(key) or {}
            obj = model_cls(**raw)
            self._cache[key] = (time.monotonic(), obj)
            return obj

    async def get_agent(self) -> AgentSettings:
        return await self._get(self._AGENT, AgentSettings)  # type: ignore[return-value]

    async def get_browser(self) -> BrowserProfileDefaults:
        return await self._get(self._BROWSER, BrowserProfileDefaults)  # type: ignore[return-value]

    async def get_worker(self) -> WorkerRuntimeSettings:
        return await self._get(self._WORKER, WorkerRuntimeSettings)  # type: ignore[return-value]

    async def update_agent(self, new: AgentSettings) -> None:
        await self._repo.upsert(self._AGENT, new.model_dump())
        self.invalidate()

    async def update_browser(self, new: BrowserProfileDefaults) -> None:
        await self._repo.upsert(self._BROWSER, new.model_dump())
        self.invalidate()

    async def update_worker(self, new: WorkerRuntimeSettings) -> None:
        await self._repo.upsert(self._WORKER, new.model_dump())
        self.invalidate()
