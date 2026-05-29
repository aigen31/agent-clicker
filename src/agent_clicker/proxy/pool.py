"""Proxy pool — supports CSV PROXY_LIST and (stubbed) provider URL."""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Iterable

from agent_clicker.config import Settings
from agent_clicker.domain.profile import ProxyLease

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _ProxyEntry:
    lease: ProxyLease
    unhealthy_until: float = 0.0


def _parse_csv(raw: str) -> list[ProxyLease]:
    out: list[ProxyLease] = []
    for chunk in (c.strip() for c in raw.split(",") if c.strip()):
        parts = chunk.split("|")
        server = parts[0]
        user = parts[1] if len(parts) > 1 and parts[1] else None
        pwd = parts[2] if len(parts) > 2 and parts[2] else None
        geo = parts[3] if len(parts) > 3 and parts[3] else None
        out.append(ProxyLease(server=server, username=user, password=pwd, geo=geo))
    return out


class ProxyPool:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._entries: list[_ProxyEntry] = []
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        leases = _parse_csv(self._settings.proxy_list)
        # provider URL not implemented — only CSV in MVP
        self._entries = [_ProxyEntry(lease=lease) for lease in leases]
        logger.info("proxy_pool.start", extra={"size": len(self._entries)})

    async def stop(self) -> None:
        return None

    async def acquire(self, *, preferred_geo: str | None = None) -> ProxyLease | None:
        async with self._lock:
            now = asyncio.get_running_loop().time()
            healthy = [e for e in self._entries if e.unhealthy_until <= now]
            if not healthy:
                return None
            if preferred_geo:
                geo_match = [e for e in healthy if (e.lease.geo or "").lower() == preferred_geo.lower()]
                pool = geo_match or healthy
            else:
                pool = healthy
            return random.choice(pool).lease

    async def release(self, lease: ProxyLease | None, *, healthy: bool) -> None:
        if lease is None:
            return
        if healthy:
            return
        async with self._lock:
            now = asyncio.get_running_loop().time()
            for e in self._entries:
                if e.lease == lease:
                    e.unhealthy_until = now + 120.0
                    return
