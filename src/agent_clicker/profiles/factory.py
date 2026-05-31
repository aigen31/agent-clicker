"""Generates randomized BrowserProfile per task."""

from __future__ import annotations

import random
from typing import Any

from agent_clicker.config import BrowserProfileDefaults, Settings
from agent_clicker.domain.profile import ProfileSpec, ProxyLease
from agent_clicker.profiles.catalog import (
    FALLBACK_LOCALES,
    GEO_LOCALE_TZ,
    UA_CATALOG,
)


class ProfileFactory:
    def __init__(self, defaults: BrowserProfileDefaults, settings: Settings) -> None:
        self._defaults = defaults
        self._settings = settings

    def build_spec(self, *, proxy: ProxyLease | None) -> ProfileSpec:
        ua_entry = random.choice(UA_CATALOG)
        w, h, dpr = random.choice(ua_entry.viewports)
        if proxy and proxy.geo and proxy.geo.upper() in GEO_LOCALE_TZ:
            locale, tz = GEO_LOCALE_TZ[proxy.geo.upper()]
        else:
            locale, tz = random.choice(FALLBACK_LOCALES)
        return ProfileSpec(
            user_agent=ua_entry.user_agent,
            viewport_width=w,
            viewport_height=h,
            device_scale_factor=dpr,
            locale=locale,
            timezone_id=tz,
            proxy=proxy,
        )

    def build_browser_profile(self, spec: ProfileSpec, *, storage_state: Any = None) -> Any:
        """Lazy import to keep tests/CLI independent from browser_use."""
        try:
            from browser_use import BrowserProfile  # type: ignore
            from browser_use.browser.profile import ProxySettings  # type: ignore
        except Exception:  # pragma: no cover — import-time guard
            BrowserProfile = None  # type: ignore[assignment]
            ProxySettings = None  # type: ignore[assignment]
        if BrowserProfile is None:
            raise RuntimeError("browser_use not installed")

        proxy_settings = None
        if spec.proxy:
            proxy_settings = ProxySettings(
                server=spec.proxy.server,
                username=spec.proxy.username or "",
                password=spec.proxy.password or "",
            )

        return BrowserProfile(
            user_data_dir=None,
            headless=self._defaults.headless,
            disable_security=self._defaults.disable_security,
            user_agent=spec.user_agent,
            viewport={"width": spec.viewport_width, "height": spec.viewport_height},
            device_scale_factor=spec.device_scale_factor,
            locale=spec.locale,
            timezone_id=spec.timezone_id,
            wait_between_actions=self._defaults.wait_between_actions,
            minimum_wait_page_load_time=self._defaults.minimum_wait_page_load_time,
            wait_for_network_idle_page_load_time=self._defaults.wait_for_network_idle_page_load_time,
            highlight_elements=self._defaults.highlight_elements,
            enable_default_extensions=self._defaults.enable_default_extensions,
            cross_origin_iframes=self._defaults.cross_origin_iframes,
            max_iframes=self._defaults.max_iframes,
            proxy=proxy_settings,
            storage_state=storage_state,
        )
