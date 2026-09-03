"""Idealista's official Search API as a second engine behind `get_scraper`.

Offline like everything else: `_post_form` is the module's only network call and
every test replaces it, so nothing here mints a token or spends a request. What
is worth pinning is not the HTTP — it is the two rules that keep this engine from
quietly returning the wrong set:

* it serves a search **only** when every filter in the URL maps to an API
  parameter whose meaning is known (rooms famously do not: this codebase counts
  Italian *locali*, the API filters `bedrooms`), and
* whatever goes wrong, the HTML scraper takes the search — the fallback is the
  real scraper, inherited, not a second copy of it.
"""

import pytest

from app import config
from app.scrapers import get_scraper, idealista_api, transport_policy
from app.scrapers.idealista import IdealistaScraper
from app.scrapers.idealista_api import IdealistaApiError, IdealistaApiScraper

MILANO_SALE = "https://www.idealista.it/vendita-case/milano-milano/"
MILANO_RENT = "https://www.idealista.it/affitto-case/milano-milano/"


@pytest.fixture(autouse=True)
def cold_token_cache(monkeypatch):
    """No token survives from one test into the next."""
    monkeypatch.setattr(idealista_api, "_token_cache", None)


def _configured(monkeypatch, **overrides):
    monkeypatch.setattr(
        config,
        "load_settings",
        lambda: {
            **config.DEFAULT_SETTINGS,
            "idealista_api_key": "KEY",
            "idealista_api_secret": "SECRET",
            **overrides,
        },
    )


def _unconfigured(monkeypatch):
    monkeypatch.setattr(config, "load_settings", lambda: dict(config.DEFAULT_SETTINGS))


def _element(**overrides) -> dict:
    """One elementList entry, in the shape the public documentation describes."""
    return {
        "propertyCode": "12345",
        "url": "https://www.idealista.it/immobile/12345/",
        "price": 320000.0,
        "size": 85.0,
        "rooms": 3,
        "bathrooms": 1,
        "floor": "2",
        "latitude": 45.4642,
        "longitude": 9.19,
        "address": "Via Volvinio, 26",
        "municipality": "Milano",
        "district": "Stadera",
        "neighborhood": "Chiesa Rossa",
        "description": "Trilocale ristrutturato con balcone",
        "thumbnail": "https://img.idealista.it/12345.jpg",
        "suggestedTexts": {"title": "Trilocale in Via Volvinio"},
        **overrides,
    }


def _payload(elements=None, **overrides) -> dict:
    return {
        "elementList": elements if elements is not None else [_element()],
        "total": 1,
        "totalPages": 1,
        "actualPage": 1,
        **overrides,
    }


def _fake_post(monkeypatch, calls: list, search_payload=None, token="TKN"):
    """Answer both endpoints from memory, recording every call."""

    def post(url, form, headers):
        calls.append({"url": url, "form": form, "headers": headers})
        if url == idealista_api.TOKEN_URL:
            return {"access_token": token, "expires_in": 43200}
        return search_payload if search_payload is not None else _payload()

    monkeypatch.setattr(idealista_api, "_post_form", post)
    return calls


# --- the opt-in ---------------------------------------------------------------


def test_no_credentials_means_the_plain_scraper(monkeypatch):
    _unconfigured(monkeypatch)
    assert not idealista_api.is_configured()
    scraper = get_scraper("idealista")
    assert type(scraper) is IdealistaScraper


def test_half_a_credential_is_not_configured(monkeypatch):
    # A key pasted without its secret cannot authenticate; treating it as
    # configured would swap the engine and then fall back on every scan.
    monkeypatch.setattr(
        config,
        "load_settings",
        lambda: {**config.DEFAULT_SETTINGS, "idealista_api_key": "KEY"},
    )
    assert not idealista_api.is_configured()
    assert type(get_scraper("idealista")) is IdealistaScraper


def test_credentials_select_the_api_engine(monkeypatch):
    _configured(monkeypatch)
    scraper = get_scraper("idealista")
    assert isinstance(scraper, IdealistaApiScraper)
    # ...and it is still a scraper: the fallback is inherited, not reimplemented
    assert isinstance(scraper, IdealistaScraper)


def test_immobiliare_is_untouched_by_idealista_credentials(monkeypatch):
    _configured(monkeypatch)
    assert get_scraper("immobiliare").portal == "immobiliare"


# --- the faithfulness rule ----------------------------------------------------


def test_a_plain_city_search_maps_to_center_and_distance(monkeypatch):
    _configured(monkeypatch)
    plan = idealista_api.search_plan(MILANO_SALE)
    assert plan is not None
    params, city = plan
    assert city == "Milano"
    assert params["operation"] == "sale"
    assert params["propertyType"] == "homes"
    assert params["country"] == "it"
    # the comuni gazetteer's own centroid and size-scaled radius
    lat, lng = (float(x) for x in params["center"].split(","))
    assert 45.0 < lat < 45.8 and 8.8 < lng < 9.5
    assert int(params["distance"]) > 0
    assert params["maxItems"] == str(idealista_api.MAX_ITEMS_PER_PAGE)


def test_contract_comes_from_the_url(monkeypatch):
    _configured(monkeypatch)
    plan = idealista_api.search_plan(MILANO_RENT)
    assert plan is not None
    assert plan[0]["operation"] == "rent"


def test_price_and_size_filters_are_carried_over(monkeypatch):
    _configured(monkeypatch)
    url = (
        "https://www.idealista.it/vendita-case/milano-milano/"
        "con-prezzo_380000,prezzo-min_200000,dimensione_70/"
    )
    plan = idealista_api.search_plan(url)
    assert plan is not None
    params, _ = plan
    assert params["maxPrice"] == "380000"
    assert params["minPrice"] == "200000"
    assert params["minSize"] == "70"


@pytest.mark.parametrize(
    "url",
    [
        # rooms: "trilocali-3" is 3 *locali*; the API filters bedrooms, and
        # "locali - 1" is a guess this project does not make (search_builder's
        # "measure the token, never infer it" rule).
        "https://www.idealista.it/vendita-case/milano-milano/con-trilocali-3/",
        # feature tokens, floor bands and condition: measured for the portal's
        # URL grammar, unknown for the API's parameters
        "https://www.idealista.it/vendita-case/milano-milano/con-ascensori/",
        "https://www.idealista.it/vendita-case/milano-milano/con-piano-terra/",
        "https://www.idealista.it/vendita-case/milano-milano/con-ristrutturare/",
        # a zone needs Idealista's internal locationId, not derivable offline
        "https://www.idealista.it/cerca/vendita-case/Bovisa_Milano/",
    ],
)
def test_a_filter_without_a_measured_parameter_declines_the_search(monkeypatch, url):
    _configured(monkeypatch)
    assert idealista_api.search_plan(url) is None


def test_an_unknown_or_ambiguous_comune_declines(monkeypatch):
    _configured(monkeypatch)
    # Castro is two comuni 800 km apart (BG and LE): geo_reference refuses a
    # centroid for exactly this reason, and a 30 km circle around the wrong one
    # is a search for the wrong province.
    assert idealista_api.search_plan("https://www.idealista.it/vendita-case/castro-castro/") is None
    assert idealista_api.search_plan("https://www.idealista.it/multi/vendita-case/aOA,aOw/") is None


# --- reading a response -------------------------------------------------------


def test_an_element_becomes_the_same_RawListing_shape(monkeypatch):
    _configured(monkeypatch)
    (listing,) = idealista_api.to_listings(_payload(), "sale", "Milano")
    assert listing.portal == "idealista"
    assert listing.portal_id == "12345"
    assert listing.url == "https://www.idealista.it/immobile/12345/"
    assert listing.title == "Trilocale in Via Volvinio"
    assert listing.price == 320000.0
    assert listing.sqm == 85.0
    assert listing.rooms == 3
    assert listing.city == "Milano"
    assert listing.latitude == 45.4642
    assert listing.strategy == "official-api"
    assert listing.contract == "sale"


def test_missing_fields_cost_that_value_and_nothing_else(monkeypatch):
    # The response schema is documented by third parties, not by a response this
    # project has seen: a renamed field must degrade, never raise.
    _configured(monkeypatch)
    bare = {"propertyCode": "999"}
    (listing,) = idealista_api.to_listings(_payload([bare]), "sale", "Milano")
    assert listing.portal_id == "999"
    assert listing.url.endswith("/immobile/999/")
    assert listing.price is None and listing.sqm is None
    # the search's own comune fills in for a listing that names none
    assert listing.city == "Milano"


def test_an_element_without_an_ad_id_is_dropped(monkeypatch):
    _configured(monkeypatch)
    assert idealista_api.to_listings(_payload([{"price": 1}]), "sale", "Milano") == []


def test_a_rent_placeholder_price_is_rejected_like_everywhere_else(monkeypatch):
    _configured(monkeypatch)
    # 320000 is a plausible sale price and an impossible monthly rent: the same
    # per-contract bounds the JSON-LD strategy applies (invariant 10).
    (listing,) = idealista_api.to_listings(_payload(), "rent", "Milano")
    assert listing.price is None


def test_neighbouring_comuni_inside_the_circle_are_dropped(monkeypatch):
    # center+distance is a circle and reaches past the city limits, while the
    # equivalent portal page never does. Without this the dashboard would gain
    # listings the monitored search did not ask for.
    _configured(monkeypatch)
    elements = [
        _element(propertyCode="1", municipality="Milano"),
        _element(propertyCode="2", municipality="Sesto San Giovanni"),
        _element(propertyCode="3", municipality="MILANO"),  # spelling is not identity
    ]
    kept = idealista_api.to_listings(_payload(elements), "sale", "Milano")
    assert sorted(l.portal_id for l in kept) == ["1", "3"]


def test_a_malformed_payload_yields_nothing_rather_than_raising(monkeypatch):
    _configured(monkeypatch)
    assert idealista_api.to_listings({"oops": 1}, "sale", "Milano") == []
    assert idealista_api.to_listings({"elementList": ["not a dict"]}, "sale", "Milano") == []


# --- the request ---------------------------------------------------------------


def test_a_scrape_authenticates_then_searches(monkeypatch):
    _configured(monkeypatch)
    calls = _fake_post(monkeypatch, [])
    result = IdealistaApiScraper().scrape(MILANO_SALE)

    assert [c["url"] for c in calls] == [idealista_api.TOKEN_URL, idealista_api.SEARCH_URL]
    token_call, search_call = calls
    assert token_call["form"] == {"grant_type": "client_credentials", "scope": "read"}
    assert token_call["headers"]["Authorization"].startswith("Basic ")
    assert search_call["headers"]["Authorization"] == "Bearer TKN"
    assert result.strategy_used == "official-api"
    assert len(result.listings) == 1


def test_the_token_is_reused_across_scrapes(monkeypatch):
    # Minting a token spends a request against a ceiling that is agreed per key
    # and published nowhere, so it is cached process-wide like the proxy pool's
    # cool-downs — scraper instances are rebuilt every scan, the token is not.
    _configured(monkeypatch)
    calls = _fake_post(monkeypatch, [])
    IdealistaApiScraper().scrape(MILANO_SALE)
    IdealistaApiScraper().scrape(MILANO_SALE)
    assert [c["url"] for c in calls].count(idealista_api.TOKEN_URL) == 1


def test_editing_the_credentials_invalidates_the_cached_token(monkeypatch):
    _configured(monkeypatch)
    calls = _fake_post(monkeypatch, [])
    IdealistaApiScraper().scrape(MILANO_SALE)
    _configured(monkeypatch, idealista_api_key="OTHER")
    IdealistaApiScraper().scrape(MILANO_SALE)
    assert [c["url"] for c in calls].count(idealista_api.TOKEN_URL) == 2


def test_one_request_per_scan_by_default(monkeypatch):
    # The default is 1, not max_pages_per_search's 10: ten requests per profile
    # per hour would exhaust any plausible ceiling within a day.
    _configured(monkeypatch)
    calls = _fake_post(monkeypatch, [], search_payload=_payload(totalPages=9))
    IdealistaApiScraper().scrape(MILANO_SALE)
    assert [c["url"] for c in calls].count(idealista_api.SEARCH_URL) == 1


def test_raising_the_page_budget_paginates(monkeypatch):
    _configured(monkeypatch, idealista_api_max_pages=3)
    monkeypatch.setattr(idealista_api, "PAGE_DELAY_SECONDS", 0)
    pages = []

    def post(url, form, headers):
        if url == idealista_api.TOKEN_URL:
            return {"access_token": "T", "expires_in": 100}
        pages.append(form["numPage"])
        code = f"id-{form['numPage']}"
        return _payload([_element(propertyCode=code, url=f"https://x/{code}")], totalPages=5)

    monkeypatch.setattr(idealista_api, "_post_form", post)
    result = IdealistaApiScraper().scrape(MILANO_SALE)
    assert pages == ["1", "2", "3"]
    assert len(result.listings) == 3


def test_pagination_stops_at_the_last_page(monkeypatch):
    _configured(monkeypatch, idealista_api_max_pages=5)
    monkeypatch.setattr(idealista_api, "PAGE_DELAY_SECONDS", 0)
    calls = _fake_post(monkeypatch, [], search_payload=_payload(totalPages=1))
    IdealistaApiScraper().scrape(MILANO_SALE)
    assert [c["url"] for c in calls].count(idealista_api.SEARCH_URL) == 1


# --- the fallback -------------------------------------------------------------


def _scraper_with_html_fallback(monkeypatch, marker="fallback-ran"):
    """An API scraper whose inherited HTML scrape is observable."""
    scraper = IdealistaApiScraper()
    seen: dict = {}

    def fake_super_scrape(url, known=None):
        seen["url"] = url
        seen["known"] = known
        from app.scrapers.base import ScrapeResult

        return ScrapeResult(strategy_used=marker)

    monkeypatch.setattr(IdealistaScraper, "scrape", staticmethod(fake_super_scrape))
    return scraper, seen


def test_a_search_the_api_cannot_express_goes_to_the_scraper(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr(idealista_api, "_post_form", lambda *a, **k: pytest.fail("no request"))
    scraper, seen = _scraper_with_html_fallback(monkeypatch)
    url = "https://www.idealista.it/vendita-case/milano-milano/con-trilocali-3/"
    assert scraper.scrape(url).strategy_used == "fallback-ran"
    assert seen["url"] == url
    assert scraper.used_official_api is False


def test_a_refused_key_falls_back_instead_of_failing_the_scan(monkeypatch):
    _configured(monkeypatch)

    def refuse(url, form, headers):
        raise IdealistaApiError("HTTP 401")

    monkeypatch.setattr(idealista_api, "_post_form", refuse)
    scraper, _ = _scraper_with_html_fallback(monkeypatch)
    assert scraper.scrape(MILANO_SALE).strategy_used == "fallback-ran"


def test_a_token_response_without_a_token_falls_back(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr(idealista_api, "_post_form", lambda *a, **k: {"error": "invalid_client"})
    scraper, _ = _scraper_with_html_fallback(monkeypatch)
    assert scraper.scrape(MILANO_SALE).strategy_used == "fallback-ran"


def test_an_empty_result_falls_back_rather_than_reporting_zero(monkeypatch):
    # Zero listings from the API is indistinguishable from a location that
    # mapped badly. The scraper can read the portal's own "nothing matched"
    # page and tell an empty search from a broken one (invariant 11's streak
    # depends on that distinction), so it gets the last word.
    _configured(monkeypatch)
    _fake_post(monkeypatch, [], search_payload=_payload([], total=0, totalPages=0))
    scraper, _ = _scraper_with_html_fallback(monkeypatch)
    assert scraper.scrape(MILANO_SALE).strategy_used == "fallback-ran"


def test_a_network_error_is_wrapped_not_propagated(monkeypatch):
    _configured(monkeypatch)

    def boom(url, form, headers):
        raise OSError("connection reset")

    monkeypatch.setattr(idealista_api, "_post_form", boom)
    with pytest.raises(IdealistaApiError):
        idealista_api.access_token()


# --- observability ------------------------------------------------------------


def test_the_health_snapshot_names_the_engine_that_served_the_scan(monkeypatch):
    _configured(monkeypatch)
    settings = config.DEFAULT_SETTINGS
    scraper = IdealistaApiScraper()

    assert transport_policy.transport_used(scraper, settings) == "local (curl_cffi)"
    _fake_post(monkeypatch, [])
    scraper.scrape(MILANO_SALE)
    assert transport_policy.transport_used(scraper, settings) == "idealista official API"


def test_a_scan_that_fell_back_is_not_credited_to_the_api(monkeypatch):
    _configured(monkeypatch)
    scraper, _ = _scraper_with_html_fallback(monkeypatch)
    scraper.used_official_api = True  # as a previous, API-served scan left it
    scraper.scrape("https://www.idealista.it/vendita-case/milano-milano/con-trilocali-3/")
    assert transport_policy.transport_used(scraper, config.DEFAULT_SETTINGS) != (
        "idealista official API"
    )
