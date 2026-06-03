"""Cookie parsing: HTTP header / browser dev-tools format -> Playwright cookies.

Playwright cookie shape (used by `storage_state={"cookies": [...]}`):
    {"name": str, "value": str, "domain": str, "path": "/", "secure": bool, "httpOnly": bool, "sameSite": "Lax"|"Strict"|"None"}

Input formats supported:
* String "k=v; k2=v2" (browser document.cookie / Cookie header) — domain is derived from URL.
* List[dict] — assumed already in Playwright shape, missing fields are filled in.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote, urlparse


def _domain_from_url(url: str) -> str:
    """Return cookie `Domain` attribute for the URL — leading dot lets it match subdomains."""
    host = urlparse(url).hostname or ""
    if not host:
        raise ValueError(f"cannot derive cookie domain from url: {url!r}")
    # Strip leading "www." so cookies stick to apex + subdomains.
    if host.startswith("www."):
        host = host[4:]
    return "." + host


def parse_cookie_header(raw: str, *, url: str) -> list[dict[str, Any]]:
    """Parse `k=v; k2=v2` style cookie string into Playwright cookie dicts."""
    if not raw or not raw.strip():
        return []
    domain = _domain_from_url(url)
    out: list[dict[str, Any]] = []
    # Split on ';' OR newlines (operators sometimes paste line-broken cookies).
    parts: list[str] = []
    for chunk in raw.replace("\n", ";").split(";"):
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    for part in parts:
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            continue
        # The browser stores cookie values URL-decoded in dev-tools but the
        # `Cookie` header serializes them verbatim. We do NOT decode — Playwright
        # will re-encode if needed, and double-decoding corrupts opaque tokens.
        out.append(
            {
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/",
                "secure": True,
                "httpOnly": False,
                # Real servers (VK, Google, etc.) set auth cookies as
                # SameSite=None;Secure. Using "Lax" can break session-rotation
                # flows where the server expects the cookie back on cross-site
                # subresource redirects (observed: VK ERR_TOO_MANY_REDIRECTS).
                "sameSite": "None",
            }
        )
    return out


def normalize_cookies(
    cookies: list[dict[str, Any]] | None, *, url: str
) -> list[dict[str, Any]]:
    """Ensure each cookie has the keys Playwright requires."""
    if not cookies:
        return []
    domain = _domain_from_url(url)
    norm: list[dict[str, Any]] = []
    for c in cookies:
        if "name" not in c or "value" not in c:
            continue
        norm.append(
            {
                "name": str(c["name"]),
                "value": str(c["value"]),
                "domain": str(c.get("domain") or domain),
                "path": str(c.get("path") or "/"),
                "secure": bool(c.get("secure", True)),
                "httpOnly": bool(c.get("httpOnly", False)),
                "sameSite": str(c.get("sameSite") or "None"),
            }
        )
    return norm


def coerce_cookies(
    raw: str | list[dict[str, Any]] | None, *, url: str
) -> list[dict[str, Any]]:
    """Accept either a header string or a pre-parsed list, return Playwright list."""
    if raw is None:
        return []
    if isinstance(raw, str):
        return parse_cookie_header(raw, url=url)
    if isinstance(raw, list):
        return normalize_cookies(raw, url=url)
    raise TypeError(f"unsupported cookies type: {type(raw).__name__}")


__all__ = ["parse_cookie_header", "normalize_cookies", "coerce_cookies"]
