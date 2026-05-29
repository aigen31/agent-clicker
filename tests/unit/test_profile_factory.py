from agent_clicker.profiles.catalog import GEO_LOCALE_TZ
from agent_clicker.config import BrowserProfileDefaults, Settings
from agent_clicker.domain.profile import ProxyLease
from agent_clicker.profiles.factory import ProfileFactory


def test_build_spec_uses_geo_locale() -> None:
    f = ProfileFactory(BrowserProfileDefaults(), Settings())
    proxy = ProxyLease(server="http://x", username=None, password=None, geo="US")
    spec = f.build_spec(proxy=proxy)
    assert spec.locale, spec.timezone_id == GEO_LOCALE_TZ["US"]
    assert spec.viewport_width > 0 and spec.viewport_height > 0


def test_build_spec_no_proxy_picks_fallback() -> None:
    f = ProfileFactory(BrowserProfileDefaults(), Settings())
    spec = f.build_spec(proxy=None)
    assert spec.locale and spec.timezone_id
