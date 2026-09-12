"""Optional scraping-API transport (Scrapfly / ScraperAPI / Zyte).

These providers solve DataDome server-side and return the target's HTML, so the
one thing that changes is the fetch choke point (`_fetch_once`); every parser
downstream still receives ordinary HTML. All offline: the provider HTTP call is
faked, so CI never touches a network or spends a credit.
"""

import base64
import json
import logging

import pytest

from app import config
from app.scrapers.base import ScrapeResult
from app.scrapers.immobiliare import ImmobiliareScraper
from app.scrapers.transport import (
    ESTIMATED_CREDITS_PER_PAGE,
    SCRAPE_API_TIMEOUT_SECONDS,
    BlockedError,
    build_scrape_api_request,
    new_scrape_api_session,
    scrape_api_error,
    unwrap_scrape_api_response,
)

from . import mock_portal


class _ApiResponse:
    def __init__(self, status_code=200, text="", json_data=None, headers=None):
        self.status_code = status_code
        self.text = text
        self._json = json_data
        self.headers = headers or {}

    def json(self):
        if self._json is None:
            raise ValueError("not JSON")
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class _FakeApiSession:
    """Stands in for the provider session, recording what reached it."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def request(self, method, url, **kw):
        self.calls.append({"method": method, "url": url, **kw})
        return self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]


def _provider_session(scraper, *responses) -> _FakeApiSession:
    session = _FakeApiSession(*responses)
    setattr(scraper, "_api_session", session)
    return session


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
    local: dict = {}

    class PortalSession:
        def get(self, url, **kw):  # the local curl path must not run
            local["used_local_get"] = True
            return _ApiResponse(text="local")

    setattr(scraper, "session", PortalSession())
    provider = _provider_session(
        scraper, _ApiResponse(json_data={"result": {"content": "<html>OK</html>"}})
    )
    html = scraper._fetch_once("https://www.immobiliare.it/vendita-case/milano/")
    assert html == "<html>OK</html>"
    assert "api.scrapfly.io" in provider.calls[0]["url"]
    assert "used_local_get" not in local


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
    _provider_session(scraper, _ApiResponse(status_code=403))
    with pytest.raises(BlockedError):
        scraper._fetch_once("https://www.immobiliare.it/x/")


# --- the provider is not the portal -------------------------------------------


def test_the_provider_session_carries_nothing_of_the_portals(monkeypatch):
    # The defect this whole path was rewritten for: the provider call used to go
    # out on the portal's impersonated session, which pinned a DataDome cookie
    # to .immobiliare.it, set Sec-Fetch-*/Referer for a navigation inside the
    # portal, and — fatally — capped the wait at the portal's 30 s.
    monkeypatch.setattr(
        config,
        "load_settings",
        lambda: {**config.DEFAULT_SETTINGS, "datadome_cookie": "COOKIEVALUE"},
    )
    session = new_scrape_api_session()
    assert dict(session.cookies) == {}
    assert not [h for h in dict(session.headers) if h.lower().startswith(("sec-fetch", "referer"))]
    assert session.proxies in ({}, None)
    # Scrapfly documents a 155 s read timeout and asks clients to match it:
    # https://scrapfly.io/docs/scrape-api/getting-started
    assert SCRAPE_API_TIMEOUT_SECONDS == 155
    assert session.timeout == SCRAPE_API_TIMEOUT_SECONDS


def test_the_portal_session_is_never_the_one_that_calls_the_provider(monkeypatch):
    _with_key(monkeypatch)
    scraper = ImmobiliareScraper()
    portal_session = scraper.session
    provider = _provider_session(
        scraper, _ApiResponse(json_data={"result": {"content": "<html>OK</html>"}})
    )
    scraper._fetch_once("https://www.immobiliare.it/x/")
    assert scraper.scrape_api_session() is provider
    assert scraper.scrape_api_session() is not portal_session


# --- provider error codes reach the user --------------------------------------


@pytest.mark.parametrize(
    "status,headers,body,code",
    [
        # quota: Scrapfly publishes the code in the reject headers
        (
            429,
            {"x-scrapfly-reject-code": "ERR::SCRAPE::QUOTA_LIMIT_REACHED"},
            None,
            "ERR::SCRAPE::QUOTA_LIMIT_REACHED",
        ),
        # the unblocker gave up: same code, read out of the body this time
        (
            422,
            {},
            {"result": {"error": {"code": "ERR::ASP::SHIELD_PROTECTION_FAILED"}}},
            "ERR::ASP::SHIELD_PROTECTION_FAILED",
        ),
        # a rejected key never reaches `result` at all
        (
            401,
            {},
            {"code": "ERR::AUTH::UNABLE_TO_AUTHENTICATE"},
            "ERR::AUTH::UNABLE_TO_AUTHENTICATE",
        ),
    ],
)
def test_each_provider_error_code_names_itself_in_the_block(
    monkeypatch, status, headers, body, code
):
    # "HTTP 422" alone does not tell the user whether to top up the account, fix
    # the key or try another transport; the provider's own code does.
    _with_key(monkeypatch)
    scraper = ImmobiliareScraper()
    _provider_session(scraper, _ApiResponse(status_code=status, headers=headers, json_data=body))
    with pytest.raises(BlockedError) as blocked:
        scraper._fetch_once("https://www.immobiliare.it/x/")
    assert code in str(blocked.value)


def test_zyte_names_its_error_type():
    resp = _ApiResponse(status_code=429, json_data={"type": "/limits/over-user-limit"})
    assert scrape_api_error("zyte", resp) == "/limits/over-user-limit"


def test_a_provider_that_names_no_code_still_blocks(monkeypatch):
    _with_key(monkeypatch)
    scraper = ImmobiliareScraper()
    _provider_session(scraper, _ApiResponse(status_code=500, text="upstream boom"))
    with pytest.raises(BlockedError) as blocked:
        scraper._fetch_once("https://www.immobiliare.it/x/")
    assert "HTTP 500" in str(blocked.value)


def test_a_portal_refusal_through_the_provider_is_a_block_not_a_page(monkeypatch):
    # The provider answered (its own 200); the portal, through it, did not. The
    # number that matters is the upstream one.
    _with_key(monkeypatch)
    scraper = ImmobiliareScraper()
    _provider_session(
        scraper,
        _ApiResponse(json_data={"result": {"status_code": 403, "content": "<html>blocked</html>"}}),
    )
    with pytest.raises(BlockedError) as blocked:
        scraper._fetch_once("https://www.immobiliare.it/x/")
    assert "403" in str(blocked.value)


def test_the_credit_cost_of_every_call_is_logged(monkeypatch, caplog):
    # The provider bills the attempt, so a call whose price is never written
    # down is money the user cannot account for.
    _with_key(monkeypatch)
    scraper = ImmobiliareScraper()
    _provider_session(
        scraper,
        _ApiResponse(
            json_data={"result": {"content": "<html>OK</html>"}},
            headers={"X-Scrapfly-Api-Cost": "30"},
        ),
    )
    with caplog.at_level(logging.INFO, logger="app.scrapers.base"):
        scraper._fetch_once("https://www.immobiliare.it/x/")
    assert "30 credits" in caplog.text


def test_a_refused_call_is_logged_with_its_price_too(monkeypatch, caplog):
    _with_key(monkeypatch)
    scraper = ImmobiliareScraper()
    _provider_session(
        scraper,
        _ApiResponse(
            status_code=422,
            headers={"X-Scrapfly-Api-Cost": "25", "x-scrapfly-reject-code": "ERR::ASP::TIMEOUT"},
        ),
    )
    with caplog.at_level(logging.INFO, logger="app.scrapers.base"):
        with pytest.raises(BlockedError):
            scraper._fetch_once("https://www.immobiliare.it/x/")
    assert "25 credits" in caplog.text


# --- what the provider hands back must still parse -----------------------------


def _page_shaped_like_the_capture(flats) -> str:
    """A results page carrying `__NEXT_DATA__` where the portal puts it today.

    The nesting is the one measured in the page the provider returned on
    2026-09-12 — `props.pageProps.dehydratedState.queries[].state.data.results`,
    each entry `{idGeoHash, realEstate, seo}`. `_find_results` reaches it by
    recursion rather than by that path (invariant 2), so this fixture exists to
    prove the recursion still lands on it, and to fail loudly if the day comes
    when the payload moves out from under it.
    """
    data = {
        "props": {
            "pageProps": {
                "dehydratedState": {
                    "queries": [
                        {
                            "state": {
                                "data": {
                                    "results": [
                                        {
                                            "idGeoHash": "u0nd",
                                            **mock_portal.immobiliare_api_entry(f),
                                        }
                                        for f in flats
                                    ]
                                }
                            }
                        }
                    ]
                }
            }
        }
    }
    return (
        "<!DOCTYPE html><html><body><div></div>"
        f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
        "</body></html>"
    )


def test_a_page_shaped_like_the_capture_parses():
    flats = [
        mock_portal.Flat(
            ad_id="120100001",
            title="Trilocale via Bicocca 4",
            price=249000,
            rooms=3,
            sqm=85,
            city="Milano",
            zone="Bicocca",
            street="Via Bicocca degli Arcimboldi",
            civic="4",
        ),
        mock_portal.Flat(
            ad_id="120100002",
            title="Bilocale viale Sarca 210",
            price=189000,
            rooms=2,
            sqm=60,
            city="Milano",
            zone="Bicocca",
            street="Viale Sarca",
            civic="210",
        ),
    ]
    scraper = ImmobiliareScraper()
    listings, strategies = scraper.parse_page(
        _page_shaped_like_the_capture(flats), "https://www.immobiliare.it/vendita-case/milano/"
    )
    assert strategies == "embedded"
    assert sorted(listing.portal_id for listing in listings) == ["120100001", "120100002"]
    assert {listing.price for listing in listings} == {249000.0, 189000.0}


# --- one escalation, then the rest of the walk goes the same way ---------------


def test_the_api_walk_escalates_once_and_carries_on_through_the_provider(monkeypatch):
    """Invariant 8's last sentence, on the JSON path.

    A portal that refuses the api-next page refuses every page of that walk, so
    the escalation is remembered: page 2 onwards goes straight to the provider
    instead of spending a guaranteed-403 request per page on the residential IP.
    """
    _with_key(monkeypatch)
    scraper = ImmobiliareScraper(delay_seconds=0, max_pages=2)
    # what the scanner sets in the default `scrape_api_mode="fallback"`
    scraper.use_scrape_api = False
    monkeypatch.setattr(scraper, "_rotate_session", lambda: False)
    monkeypatch.setattr(scraper, "_recover_cookie", lambda: False)
    monkeypatch.setattr(
        scraper,
        "_api_params",
        lambda url: {"idComune": "8042", "idContratto": "1", "path": "/vendita-case/"},
    )
    flats = [
        mock_portal.Flat(
            ad_id=f"9900{n}", title=f"Casa {n}", price=200000 + n, rooms=3, sqm=80, city="Milano"
        )
        for n in range(4)
    ]
    pages = [
        mock_portal.immobiliare_api_page(flats[:2], max_pages=2, count=4),
        mock_portal.immobiliare_api_page(flats[2:], max_pages=2, count=4),
    ]
    local: list[int] = []

    def refuse(params, referer, page):
        local.append(page)
        return _ApiResponse(status_code=403)

    monkeypatch.setattr(scraper, "_api_get", refuse)
    provider = _provider_session(
        scraper,
        *(_ApiResponse(json_data={"result": {"content": json.dumps(page)}}) for page in pages),
    )

    result = ScrapeResult()
    scraper._api_search("https://www.immobiliare.it/vendita-case/milano/", result)

    # the local session was tried once and never again
    assert local == [1]
    assert len(provider.calls) == 2
    assert all("api-next%2Fsearch-list" in call["url"] for call in provider.calls)
    # and the declared size of the result set survived the trip through it,
    # which is what lets the scan state a proportion at all (invariant 26)
    assert result.total_pages == 2
    assert result.total_listings == 4
    assert len(result.listings) == 4
    assert not result.blocked


def test_always_mode_sends_the_json_walk_through_the_provider_from_the_start(monkeypatch):
    """`scrape_api_mode="always"` means every fetch, this one included.

    It used to reach the HTML path alone, which on this portal is the fallback:
    the primary walk went on leaving from the residential connection the setting
    had just been used to stop using.
    """
    _with_key(monkeypatch)
    scraper = ImmobiliareScraper(delay_seconds=0, max_pages=1)
    scraper.use_scrape_api = True  # what the scanner sets in "always" mode
    monkeypatch.setattr(
        scraper,
        "_api_params",
        lambda url: {"idComune": "8042", "idContratto": "1", "path": "/vendita-case/"},
    )

    def never(*args, **kwargs):
        raise AssertionError("the residential connection was used in 'always' mode")

    monkeypatch.setattr(scraper, "_api_get", never)
    flat = mock_portal.Flat(
        ad_id="99010", title="Casa", price=200000, rooms=3, sqm=80, city="Milano"
    )
    provider = _provider_session(
        scraper,
        _ApiResponse(
            json_data={
                "result": {
                    "content": json.dumps(mock_portal.immobiliare_api_page([flat], max_pages=1))
                }
            }
        ),
    )

    result = ScrapeResult()
    scraper._api_search("https://www.immobiliare.it/vendita-case/milano/", result)

    assert len(provider.calls) == 1
    assert len(result.listings) == 1
    assert not result.blocked


# --- what it cost, and the point at which it stops being spent -----------------


class _FreeLocalSession:
    """The residential path, always answering. Records what it was asked for,
    so "it carried on without the provider" is a claim with evidence."""

    def __init__(self):
        self.calls: list[str] = []

    def get(self, url, **kw):
        self.calls.append(url)
        return _ApiResponse(status_code=200, text="<html>free</html>")


def test_the_receipt_of_every_call_is_added_to_this_scrape_s_bill(monkeypatch):
    _with_key(monkeypatch)
    scraper = ImmobiliareScraper()
    _provider_session(
        scraper,
        _ApiResponse(
            json_data={"result": {"content": "<html>OK</html>"}},
            headers={"X-Scrapfly-Api-Cost": "30"},
        ),
        _ApiResponse(
            json_data={"result": {"content": "<html>OK</html>"}},
            headers={"X-Scrapfly-Api-Cost": "25"},
        ),
    )
    scraper._fetch_once("https://www.immobiliare.it/1/")
    scraper._fetch_once("https://www.immobiliare.it/2/")

    assert scraper.api_calls == 2
    assert scraper.api_credits_spent == 55
    # Both prices were quoted, so none of the total is a guess.
    assert scraper.api_credits_estimated == 0


def test_a_call_the_provider_priced_at_nothing_is_charged_the_measured_page_price(monkeypatch):
    """A receipt with no price on it must not cost zero.

    Zero is what a provider whose headers changed would look like, and it would
    let a whole month's ceiling be spent without the number ever moving. The
    measured page price stands in, and the share it stands in for is carried
    separately so nothing downstream states an estimate as a fact (invariant 26).
    """
    _with_key(monkeypatch)
    scraper = ImmobiliareScraper()
    _provider_session(scraper, _ApiResponse(json_data={"result": {"content": "<html>OK</html>"}}))
    scraper._fetch_once("https://www.immobiliare.it/x/")

    assert scraper.api_credits_spent == ESTIMATED_CREDITS_PER_PAGE
    assert scraper.api_credits_estimated == ESTIMATED_CREDITS_PER_PAGE


def test_the_allowance_is_checked_before_the_call_that_would_overshoot_it(monkeypatch):
    _with_key(monkeypatch)
    scraper = ImmobiliareScraper()
    scraper.api_credits_left = 2 * ESTIMATED_CREDITS_PER_PAGE
    assert scraper.scrape_api_affordable() is True
    # The real price only exists on the receipt, so the check is made against
    # the measured one: the last page of an allowance may overshoot it.
    scraper.api_credits_spent = ESTIMATED_CREDITS_PER_PAGE + 1
    assert scraper.scrape_api_affordable() is False


def test_a_scrape_that_runs_out_mid_walk_finishes_on_the_free_path(monkeypatch):
    """Page 4 of a ten-page search can be the one that reaches the ceiling.

    The walk carries on locally rather than ending there — a partial read is
    worth more than none — and the paid rung stays off for the rest of it,
    including as the escalation a block would otherwise reach for.
    """
    _with_key(monkeypatch)
    scraper = ImmobiliareScraper()
    scraper.use_scrape_api = True
    scraper.api_credits_left = ESTIMATED_CREDITS_PER_PAGE
    provider = _provider_session(
        scraper,
        _ApiResponse(
            json_data={"result": {"content": "<html>paid</html>"}},
            headers={"X-Scrapfly-Api-Cost": "25"},
        ),
    )
    local = _FreeLocalSession()
    monkeypatch.setattr(scraper, "session", local)

    assert scraper._fetch_once("https://www.immobiliare.it/1/") == "<html>paid</html>"
    assert scraper._fetch_once("https://www.immobiliare.it/2/") == "<html>free</html>"

    assert len(provider.calls) == 1
    assert local.calls == ["https://www.immobiliare.it/2/"]
    assert scraper.use_scrape_api is False
    assert scraper.allow_scrape_api_fallback is False


def test_an_exhausted_local_ladder_does_not_escalate_past_the_ceiling(monkeypatch):
    """The half that would otherwise keep paying.

    `fetch` reaches for the provider precisely when everything else has been
    refused, so a ceiling that only governed the starting rung would hold right
    up until the moment it mattered.
    """
    _with_key(monkeypatch)
    scraper = ImmobiliareScraper(delay_seconds=0)
    scraper.use_scrape_api = False
    scraper.api_credits_left = 0
    monkeypatch.setattr(scraper, "_rotate_session", lambda: False)

    def refused(url, **kw):
        return _ApiResponse(status_code=403, text="")

    monkeypatch.setattr(scraper, "session", type("S", (), {"get": staticmethod(refused)})())
    provider = _provider_session(
        scraper, _ApiResponse(json_data={"result": {"content": "<html/>"}})
    )

    with pytest.raises(BlockedError):
        scraper.fetch("https://www.immobiliare.it/x/")
    assert provider.calls == []
