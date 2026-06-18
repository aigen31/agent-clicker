"""In-memory log broadcaster (pub/sub with bounded buffers)."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import AsyncIterator
from typing import Any

from agent_clicker.observability.logging import record_to_dict


class LogBroadcaster:
    def __init__(self, buffer_size: int = 2000) -> None:
        self._buffer: deque[dict[str, Any]] = deque(maxlen=buffer_size)
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    def publish_nowait(self, record: dict[str, Any]) -> None:
        self._buffer.append(record)
        dead: list[asyncio.Queue[dict[str, Any]]] = []
        for q in self._subscribers:
            try:
                q.put_nowait(record)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.discard(q)

    def snapshot(self) -> list[dict[str, Any]]:
        return list(self._buffer)

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self._subscribers.add(q)
        try:
            while True:
                item = await q.get()
                yield item
        finally:
            self._subscribers.discard(q)


class LogBroadcastHandler(logging.Handler):
    def __init__(self, broadcaster: LogBroadcaster) -> None:
        super().__init__()
        self._broadcaster = broadcaster

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._broadcaster.publish_nowait(record_to_dict(record))
        except Exception:  # pragma: no cover
            self.handleError(record)
