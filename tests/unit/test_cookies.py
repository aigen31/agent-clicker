"""Tests for cookie header parser."""

from __future__ import annotations

import pytest

from agent_clicker.browser.cookies import (
    coerce_cookies,
    normalize_cookies,
    parse_cookie_header,
)


def test_parse_simple() -> None:
    out = parse_cookie_header("a=1; b=2", url="https://vk.com/im")
    assert len(out) == 2
    assert out[0]["name"] == "a"
    assert out[0]["value"] == "1"
    assert out[0]["domain"] == ".vk.com"
    assert out[0]["path"] == "/"
    assert out[0]["secure"] is True


def test_parse_strips_www() -> None:
    out = parse_cookie_header("x=y", url="https://www.example.com/page")
    assert out[0]["domain"] == ".example.com"


def test_parse_preserves_complex_values() -> None:
    raw = "remixsid=1_VtB3qaxSm%7CrzU; httoken=abc-def_123"
    out = parse_cookie_header(raw, url="https://vk.com")
    assert out[0]["value"] == "1_VtB3qaxSm%7CrzU"  # NOT url-decoded
    assert out[1]["name"] == "httoken"
    assert out[1]["value"] == "abc-def_123"


def test_parse_empty() -> None:
    assert parse_cookie_header("", url="https://vk.com") == []
    assert parse_cookie_header("  ; ; ", url="https://vk.com") == []


def test_parse_ignores_malformed_parts() -> None:
    out = parse_cookie_header("good=1; bare; =empty; also_good=2", url="https://vk.com")
    names = [c["name"] for c in out]
    assert names == ["good", "also_good"]


def test_parse_handles_newlines() -> None:
    out = parse_cookie_header("a=1\nb=2;\nc=3", url="https://vk.com")
    assert [c["name"] for c in out] == ["a", "b", "c"]


def test_parse_requires_valid_url() -> None:
    with pytest.raises(ValueError):
        parse_cookie_header("a=1", url="not-a-url")


def test_normalize_fills_defaults() -> None:
    out = normalize_cookies(
        [{"name": "x", "value": "y"}], url="https://vk.com"
    )
    assert out[0]["domain"] == ".vk.com"
    assert out[0]["path"] == "/"
    assert out[0]["sameSite"] == "Lax"


def test_normalize_preserves_explicit_fields() -> None:
    out = normalize_cookies(
        [{"name": "x", "value": "y", "domain": ".sub.vk.com", "secure": False, "sameSite": "None"}],
        url="https://vk.com",
    )
    assert out[0]["domain"] == ".sub.vk.com"
    assert out[0]["secure"] is False
    assert out[0]["sameSite"] == "None"


def test_coerce_accepts_string_and_list() -> None:
    assert coerce_cookies(None, url="https://vk.com") == []
    s = coerce_cookies("a=1", url="https://vk.com")
    lst = coerce_cookies([{"name": "a", "value": "1"}], url="https://vk.com")
    assert s[0]["name"] == lst[0]["name"] == "a"
