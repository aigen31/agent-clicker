from agent_clicker.domain.profile import ProfileSpec, ProxyLease
from agent_clicker.profiles.catalog import GEO_LOCALE_TZ, UA_CATALOG


def test_ua_catalog_non_empty() -> None:
    assert len(UA_CATALOG) >= 8
    for entry in UA_CATALOG:
        assert entry.user_agent
        assert entry.viewports


def test_geo_locale_tz_has_keys() -> None:
    assert "US" in GEO_LOCALE_TZ
    assert "RU" in GEO_LOCALE_TZ


def test_profile_spec_audit_omits_proxy_password() -> None:
    spec = ProfileSpec(
        user_agent="ua",
        viewport_width=1920,
        viewport_height=1080,
        device_scale_factor=1.0,
        locale="en-US",
        timezone_id="America/New_York",
        proxy=ProxyLease(server="http://p", username="u", password="secret", geo="US"),
    )
    audit = spec.to_audit_dict()
    assert audit["proxy"] == {"server": "http://p", "geo": "US"}
    assert "secret" not in str(audit)
