"""Optional scraping-API transport (Scrapfly / ScraperAPI / Zyte).

These providers solve DataDome server-side and return the target's HTML, so the
one thing that changes is the fetch choke point (`_fetch_once`); every parser
downstream still receives ordinary HTML. All offline: the provider HTTP call is
faked, so CI never touches a network or spends a credit.
"""

import base64

import pytest

from app import config
from app.scrapers.base import (
    BlockedError,
    build_scrape_api_request,
    unwrap_scrape_api_response,
)
from app.scrapers.immobiliare import ImmobiliareScraper


class _ApiResponse:
    def __init__(self, status_code=200, text="", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json = json_data

    def json(self):
        if self._json is None:
            raise ValueError("not JSON")
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def _with_key(monkeypatch, provider="scrapfly", key="SECRET"):
    monkeypatch.setattr(
        config,
        "load_settings",
        lambda: {
            **config.DEFAULT_SETTINGS,
            "scrape_api_provider": provider,
            "scrape_api_key": key,
        },
    )


# --- request building / response unwrapping -----------------------------------


def test_scrapfly_request_encodes_the_target_url():
    req = build_scrape_api_request(
        "scrapfly", "KEY", "https://www.immobiliare.it/vendita-case/milano/"
    )
    assert req.method == "GET"
    assert req.url.startswith("https://api.scrapfly.io/scrape")
    assert "key=KEY" in req.url and "asp=true" in req.url
    # the target must be percent-encoded into the query, not left as a bare URL
    assert "url=https%3A%2F%2Fwww.immobiliare.it" in req.url


def test_scrapfly_unwraps_result_content():
    resp = _ApiResponse(json_data={"result": {"content": "<html>SOLVED</html>"}})
    assert unwrap_scrape_api_response("scrapfly", resp) == "<html>SOLVED</html>"


def test_scraperapi_returns_raw_html_verbatim():
    req = build_scrape_api_request("scraperapi", "KEY", "https://x.it/")
    assert req.url == "https://api.scraperapi.com/"
    assert req.params == {"api_key": "KEY", "url": "https://x.it/", "country_code": "it"}
    resp = _ApiResponse(text="<html>RAW</html>")
    assert unwrap_scrape_api_response("scraperapi", resp) == "<html>RAW</html>"


def test_zyte_uses_basic_auth_and_decodes_base64_body():
    req = build_scrape_api_request("zyte", "KEY", "https://x.it/")
    assert req.method == "POST"
    assert req.headers is not None
    assert req.headers["Authorization"].startswith("Basic ")
    assert req.json_body == {"url": "https://x.it/", "httpResponseBody": True}
    encoded = base64.b64encode(b"<html>Z</html>").decode()
    resp = _ApiResponse(json_data={"httpResponseBody": encoded})
    assert unwrap_scrape_api_response("zyte", resp) == "<html>Z</html>"


def test_malformed_provider_response_is_a_block_not_a_crash():
    # A 200 with the wrong shape is a quota/plan error dressed up; surfacing it as
    # BlockedError routes it into the same rotate/abandon path as any refusal.
    with pytest.raises(BlockedError):
        unwrap_scrape_api_response("scrapfly", _ApiResponse(json_data={"oops": 1}))


# --- the choke point: _fetch_once ---------------------------------------------


def test_fetch_once_routes_through_the_api_when_a_key_is_set(monkeypatch):
    _with_key(monkeypatch)
    scraper = ImmobiliareScraper()
    calls: dict = {}

    class FakeSession:
        def request(self, method, url, **kw):
            calls["url"] = url
            return _ApiResponse(json_data={"result": {"content": "<html>OK</html>"}})

        def get(self, url, **kw):  # the local curl path must not run
            calls["used_local_get"] = True
            return _ApiResponse(text="local")

    setattr(scraper, "session", FakeSession())
    html = scraper._fetch_once("https://www.immobiliare.it/vendita-case/milano/")
    assert html == "<html>OK</html>"
    assert "api.scrapfly.io" in calls["url"]
    assert "used_local_get" not in calls


def test_fetch_once_uses_the_local_path_when_no_key(monkeypatch):
    monkeypatch.setattr(config, "load_settings", lambda: dict(config.DEFAULT_SETTINGS))
    scraper = ImmobiliareScraper()
    calls: dict = {}

    class FakeSession:
        def get(self, url, **kw):
            calls["local"] = url
            return _ApiResponse(text="<html>local</html>")

    setattr(scraper, "session", FakeSession())
    assert scraper._fetch_once("https://www.immobiliare.it/x/") == "<html>local</html>"
    assert calls["local"].endswith("/x/")


def test_provider_refusal_becomes_a_block_error(monkeypatch):
    _with_key(monkeypatch)
    scraper = ImmobiliareScraper()

    class FakeSession:
        def request(self, method, url, **kw):
            return _ApiResponse(status_code=403)

    setattr(scraper, "session", FakeSession())
    with pytest.raises(BlockedError):
        scraper._fetch_once("https://www.immobiliare.it/x/")
