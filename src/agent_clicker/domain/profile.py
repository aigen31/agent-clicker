"""Domain DTOs for browser profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ProxyLease:
    server: str
    username: str | None
    password: str | None
    geo: str | None = None


@dataclass(frozen=True, slots=True)
class ProfileSpec:
    user_agent: str
    viewport_width: int
    viewport_height: int
    device_scale_factor: float
    locale: str
    timezone_id: str
    proxy: ProxyLease | None

    def to_audit_dict(self) -> dict[str, Any]:
        """Safe dict for tasks.profile (no proxy creds)."""
        proxy_audit = None
        if self.proxy:
            proxy_audit = {"server": self.proxy.server, "geo": self.proxy.geo}
        return {
            "user_agent": self.user_agent,
            "viewport": {"w": self.viewport_width, "h": self.viewport_height},
            "device_scale_factor": self.device_scale_factor,
            "locale": self.locale,
            "timezone_id": self.timezone_id,
            "proxy": proxy_audit,
        }
