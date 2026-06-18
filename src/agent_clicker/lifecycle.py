"""Lifespan helper: orderly start/stop with timeout."""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class Lifecycled(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...


class Lifespan:
    def __init__(self, components: list[Lifecycled], stop_timeout: float = 60.0) -> None:
        self._components = components
        self._stop_timeout = stop_timeout

    async def __aenter__(self) -> Lifespan:
        for c in self._components:
            await c.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: D401
        for c in reversed(self._components):
            try:
                await asyncio.wait_for(c.stop(), timeout=self._stop_timeout)
            except TimeoutError:
                logger.warning("lifecycle.stop.timeout", extra={"component": type(c).__name__})
            except Exception:
                logger.exception("lifecycle.stop.error")
