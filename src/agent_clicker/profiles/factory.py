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

    def build_spec(self, *, proxy: ProxyLease | None, pin_desktop: bool = False) -> ProfileSpec:
        if pin_desktop:
            # When the task carries authenticated cookies, randomizing UA breaks
            # session validation on sites that bind sessions to a UA fingerprint
            # (observed: VK redirect loops). Pin to a stable, common desktop
            # Chrome/Windows UA so that the cookies, locale and viewport stay
            # internally consistent.
            ua_entry = next(
                (e for e in UA_CATALOG if "Windows NT" in e.user_agent and "Chrome" in e.user_agent),
                UA_CATALOG[0],
            )
        else:
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

    def build_browser_profile(
        self,
        spec: ProfileSpec,
        *,
        storage_state: Any = None,
        disable_extensions: bool = False,
    ) -> Any:
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
            server = spec.proxy.server
            if "://" not in server:
                server = "http://" + server
            proxy_settings = ProxySettings(
                server=server,
                username=spec.proxy.username or "",
                password=spec.proxy.password or "",
            )

        # Default browser-use extensions (uBlock Origin Lite, "I still don't
        # care about cookies", Force Background Tab) inject extra HTTP headers
        # and rewrite responses. On tightly-fingerprinted sites (VK in
        # particular) this caused ERR_TOO_MANY_REDIRECTS even when the same
        # cookies worked fine with plain curl. Disable them when the task
        # carries its own authentication.
        enable_extensions = (
            False if disable_extensions else self._defaults.enable_default_extensions
        )

        # Anti-detection Chrome args. Sites like VK run JS that detects
        # navigator.webdriver and headless markers, then triggers anti-bot
        # challenges (the "challenge.js" PerformanceObserver path) which loop
        # the browser into ERR_TOO_MANY_REDIRECTS even with valid cookies.
        stealth_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--no-default-browser-check",
            "--no-first-run",
            "--disable-infobars",
            "--disable-dev-shm-usage",
        ]

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
            enable_default_extensions=enable_extensions,
            cross_origin_iframes=self._defaults.cross_origin_iframes,
            max_iframes=self._defaults.max_iframes,
            proxy=proxy_settings,
            storage_state=storage_state,
            args=stealth_args,
        )
