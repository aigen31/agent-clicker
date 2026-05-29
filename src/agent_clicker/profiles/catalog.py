"""Static catalog: realistic User-Agent / viewport / geo→locale entries."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UAEntry:
    user_agent: str
    viewports: tuple[tuple[int, int, float], ...]  # (w, h, dpr)


UA_CATALOG: tuple[UAEntry, ...] = (
    # Desktop Chrome / Windows
    UAEntry(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36",
        ((1920, 1080, 1.0), (1536, 864, 1.25), (1366, 768, 1.0)),
    ),
    UAEntry(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36",
        ((1920, 1080, 1.0), (1366, 768, 1.0)),
    ),
    # Desktop Chrome / Mac
    UAEntry(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36",
        ((2560, 1440, 2.0), (1440, 900, 2.0), (1680, 1050, 2.0)),
    ),
    # Desktop Firefox
    UAEntry(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
        ((1920, 1080, 1.0), (1366, 768, 1.0)),
    ),
    UAEntry(
        "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
        ((1920, 1080, 1.0),),
    ),
    # Safari
    UAEntry(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4 Safari/605.1.15",
        ((1440, 900, 2.0), (1680, 1050, 2.0)),
    ),
    # iPhone Safari
    UAEntry(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, "
        "like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        ((390, 844, 3.0), (414, 896, 3.0)),
    ),
    # Android Chrome
    UAEntry(
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Mobile Safari/537.36",
        ((412, 915, 2.625),),
    ),
    UAEntry(
        "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Mobile Safari/537.36",
        ((360, 780, 3.0),),
    ),
    # Edge
    UAEntry(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
        ((1920, 1080, 1.0),),
    ),
)


# Default locale/timezone for known geo codes.
GEO_LOCALE_TZ: dict[str, tuple[str, str]] = {
    "US": ("en-US", "America/New_York"),
    "GB": ("en-GB", "Europe/London"),
    "DE": ("de-DE", "Europe/Berlin"),
    "FR": ("fr-FR", "Europe/Paris"),
    "RU": ("ru-RU", "Europe/Moscow"),
    "UA": ("uk-UA", "Europe/Kyiv"),
    "TR": ("tr-TR", "Europe/Istanbul"),
    "KZ": ("ru-KZ", "Asia/Almaty"),
    "BR": ("pt-BR", "America/Sao_Paulo"),
    "JP": ("ja-JP", "Asia/Tokyo"),
}

FALLBACK_LOCALES: tuple[tuple[str, str], ...] = (
    ("ru-RU", "Europe/Moscow"),
    ("en-US", "America/New_York"),
    ("en-GB", "Europe/London"),
)
