"""Verification of multi-strategy pipeline on simulated HTML pages:
the parser must dynamically choose JSON-LD -> embedded -> heuristic."""

import json
import logging
from collections.abc import Callable
from urllib.parse import parse_qs, urlparse

import pytest

from app.scrapers import immobiliare
from app.scrapers.base import BaseScraper, ScrapeResult
from app.scrapers.idealista import IdealistaScraper
from app.scrapers.immobiliare import ImmobiliareScraper
from app.scrapers.parsing import parse_price, parse_rooms, parse_sqm
from app.scrapers.probe import AdProbe
from app.scrapers.transport import resolve_impersonations, supported_impersonations

from . import mock_portal
from .mock_portal import MockPortalServer


@pytest.fixture
def portal():
    """The portals on loopback HTTP. Same sandbox `test_offline_sandbox` drives
    end to end, used here for the one question a fake session cannot answer:
    what the request the scraper issues actually looks like on the wire."""
    with MockPortalServer() as server:
        yield server


# --- Simulated Pages ---

PAGE_JSON_LD = """
<html><head>
<script type="application/ld+json">
{
  "@type": "ItemList",
  "itemListElement": [
    {"item": {
      "@type": "RealEstateListing",
      "url": "https://www.immobiliare.it/annunci/12345/",
      "name": "Trilocale via Verdi",
      "offers": {"price": "250000"},
      "numberOfRooms": 3,
      "floorSize": {"value": "95"},
      "address": {"addressLocality": "Torino", "streetAddress": "Via Verdi 10"},
      "geo": {"latitude": 45.07, "longitude": 7.68}
    }}
  ]
}
</script></head><body></body></html>
"""

PAGE_NEXT_DATA = """
<html><body>
<script id="__NEXT_DATA__" type="application/json">
{"props": {"pageProps": {"dehydratedState": {"queries": [{"state": {"data": {
  "results": [
    {"realEstate": {
       "id": 777, "title": "Bilocale zona Navigli",
       "price": {"value": 199000},
       "properties": [{"surface": "60 m²", "rooms": "2",
         "location": {"city": "Milano", "macrozone": "Navigli",
                      "latitude": 45.45, "longitude": 9.17},
         "description": "Luminoso bilocale ristrutturato"}],
       "advertiser": {"agency": {"displayName": "Agenzia Rossi"}}
     },
     "seo": {"url": "https://www.immobiliare.it/annunci/777/"}}
  ]
}}}]}}}}
</script></body></html>
"""

PAGE_HTML_ONLY = """
<html><body>
<div class="qualcosa-random-xyz">
  <a href="https://www.immobiliare.it/annunci/55555/">Quadrilocale centro storico</a>
  <span class="zzz">€ 420.000</span>
  <span>4 locali</span> <span>120 mq</span>
  <img src="https://img.example.com/foto.jpg"/>
</div>
</body></html>
"""

IDEALISTA_HTML = """
<html><body>
<article class="cls-cambiata-2026">
  <a href="/immobile/88888/">Appartamento in vendita in via Dante</a>
  <span>€ 315.000</span> <span>3 locali</span> <span>100 m²</span>
</article>
</body></html>
"""


def test_strategy_1_json_ld():
    listings, strategy = ImmobiliareScraper().parse_page(PAGE_JSON_LD, "url")
    assert strategy == "json-ld"
    assert len(listings) == 1
    l = listings[0]
    assert l.portal_id == "12345"
    assert l.price == 250000
    assert l.rooms == 3
    assert l.sqm == 95
    assert l.city == "Torino"


def test_strategy_2_next_data():
    listings, strategy = ImmobiliareScraper().parse_page(PAGE_NEXT_DATA, "url")
    assert strategy == "embedded"
    assert len(listings) == 1
    l = listings[0]
    assert l.portal_id == "777"
    assert l.price == 199000
    assert l.rooms == 2
    assert l.sqm == 60
    assert l.city == "Milano"
    assert l.agency == "Agenzia Rossi"


def test_strategy_3_heuristic_without_css_classes():
    listings, strategy = ImmobiliareScraper().parse_page(PAGE_HTML_ONLY, "url")
    assert strategy == "heuristic"
    assert len(listings) == 1
    l = listings[0]
    assert l.portal_id == "55555"
    assert l.price == 420000
    assert l.rooms == 4
    assert l.sqm == 120


def test_idealista_heuristic():
    listings, strategy = IdealistaScraper().parse_page(IDEALISTA_HTML, "url")
    assert "heuristic" in strategy
    assert len(listings) == 1
    l = listings[0]
    assert l.portal_id == "88888"
    assert l.price == 315000
    assert l.sqm == 100


def test_empty_page_does_not_crash():
    listings, strategy = ImmobiliareScraper().parse_page("<html></html>", "url")
    assert listings == []


# --- Every coordinate the portal hands over is taken ------------------------
#
# A pin the ad already carried is free and exact, and the alternative is a paced
# Nominatim request for something the app was given. Idealista's JSON-LD read
# past `geo` for years, so a listing found by that strategy arrived with no
# coordinates and waited for a maintenance sweep to approximate one — which is
# the expensive half of this suite's point. These four cases are one per parsing
# path that can be handed a coordinate, so a field dropped from any of them
# turns a test red instead of quietly emptying the map.

IDEALISTA_JSON_LD = """
<html><head>
<script type="application/ld+json">
{
  "@type": "ItemList",
  "itemListElement": [
    {"item": {
      "@type": "RealEstateListing",
      "url": "https://www.idealista.it/immobile/88888/",
      "name": "Trilocale in vendita in Via Dante, 5, Milano",
      "offers": {"price": "315000"},
      "geo": {"@type": "GeoCoordinates", "latitude": 45.4661, "longitude": 9.1878}
    }}
  ]
}
</script></head><body></body></html>
"""

IDEALISTA_EMBEDDED = """
<html><body><script>
window.__INITIAL_PROPS__ = [
  {"adId": 99001, "title": "Bilocale Isola", "price": 285000, "size": 62,
   "rooms": 2, "latitude": 45.4881, "longitude": 9.1889,
   "municipality": "Milano", "address": "Via Borsieri 4"}
];
</script></body></html>
"""


@pytest.mark.parametrize(
    "scraper,page,expected",
    [
        (ImmobiliareScraper, PAGE_JSON_LD, (45.07, 7.68)),
        (ImmobiliareScraper, PAGE_NEXT_DATA, (45.45, 9.17)),
        (IdealistaScraper, IDEALISTA_JSON_LD, (45.4661, 9.1878)),
        (IdealistaScraper, IDEALISTA_EMBEDDED, (45.4881, 9.1889)),
    ],
)
def test_a_page_that_carries_coordinates_never_loses_them(scraper, page, expected):
    listings, _ = scraper().parse_page(page, "https://example.invalid/vendita-case/milano-milano/")
    assert len(listings) == 1
    assert (listings[0].latitude, listings[0].longitude) == expected


def test_the_heuristic_strategy_places_nothing_it_cannot_read():
    """The two card parsers get plain text and no coordinates, and must not
    invent any: an unplaced listing is the geocoder's problem, and a guessed pin
    would be a wrong one nobody could detect."""
    for scraper, page in ((ImmobiliareScraper, PAGE_HTML_ONLY), (IdealistaScraper, IDEALISTA_HTML)):
        listings, strategy = scraper().parse_page(page, "url")
        assert "heuristic" in strategy
        assert listings[0].latitude is None and listings[0].longitude is None


# The portals' real "nothing matched" pages, reduced to what decides the case.
# Idealista serves this with HTTP 404 — the same status as a dead slug — while
# Immobiliare serves its own with 200.
IDEALISTA_NO_RESULTS = """
<html><body><h1>Abbiamo guardato dappertutto, ma non abbiamo trovato quello
che stavi cercando.</h1><p>Con i tuoi criteri di ricerca non ci sono annunci
che corrispondano ai tuoi criteri a City Life, Milano</p></body></html>
"""
IMMOBILIARE_NO_RESULTS = """
<html><body><h1>Nessun risultato per case in vendita Milano</h1>
<p>Oops ... non ci sono annunci per la tua ricerca. Rimuovi dei filtri o
aumenta l'area di ricerca.</p></body></html>
"""


def test_empty_search_is_an_answer_not_a_failure():
    """A zone can be alive and simply hold nothing today: City Life answers
    "non ci sono annunci ... a City Life, Milano" and names the zone back, so
    the slug plainly resolved.

    Both portals were reporting this as a broken profile — Idealista because it
    serves the page with HTTP 404, Immobiliare because an empty parse tripped
    the "no listings extracted" alarm. The dashboard then showed a permanent
    "Error", and the health streak (invariant 11) counted it towards alerting
    about a scraper that was working perfectly.
    """
    from app.scrapers.page_text import text_says_no_results

    assert text_says_no_results(IDEALISTA_NO_RESULTS) is True
    assert text_says_no_results(IMMOBILIARE_NO_RESULTS) is True


def test_a_real_markup_change_still_raises_the_alarm():
    """The dangerous direction: if an empty page were assumed harmless, a portal
    rewriting its markup would go unnoticed and the searches would quietly
    return nothing forever. Only the portal's own words may excuse an empty
    parse — a page that says nothing must still be an error."""
    from app.scrapers.page_text import text_says_no_results

    assert text_says_no_results("<html><body>Case in vendita</body></html>") is False
    assert text_says_no_results("") is False


def test_no_results_message_hidden_in_scripts_does_not_count():
    """Matched against VISIBLE text only, like the gone markers (invariant 16):
    the portals ship their i18n dictionaries inside the page's JSON, so a raw
    substring scan would call a page full of listings "empty" and silence the
    markup-change alarm on every scan."""
    from app.scrapers.page_text import text_says_no_results

    html = (
        '<html><body><script>var i18n = {"empty": "non ci sono annunci '
        'per la tua ricerca"};</script><div>30 case</div></body></html>'
    )
    assert text_says_no_results(html) is False


def test_parse_helpers():
    assert parse_price("da € 1.250.000 trattabili") == 1_250_000
    assert parse_price("€ 5.000") is None  # below plausible range
    assert parse_sqm("120 mq") == 120
    assert parse_sqm("85,5 m²") == 85.5
    assert parse_rooms("3 locali") == 3
    assert parse_rooms("1 locale") == 1


def test_parse_price_symbol_after_number():
    """Idealista writes "399.000 €", Immobiliare "€ 399.000"."""
    assert parse_price("Trilocale 399.000 € 3 locali") == 399_000


def test_parse_price_ignores_price_per_square_meter():
    """Regression: "3.990 €/m²" is not the property price."""
    assert parse_price("399.000 € 3.990 €/m² 3 locali 100 m²") == 399_000
    assert parse_price("5.933 €/m² 445.000 €") == 445_000


def test_parse_price_prefers_main_price_over_accessories():
    """The card shows the price first, then any extras ("Box opz.")."""
    assert parse_price("399.000 € 3.990 €/m² Box opz. 39.000 €") == 399_000


IDEALISTA_CARD_REALE = """
<html><body>
<div class="items-container">
  <article>
    <a href="/immobile/36124807/"><img src="https://img.example/a.jpg"/></a>
    <a href="/immobile/36124807/">Trilocale in Via Volvinio, 26, Stadera, Milano</a>
    <span>399.000 €</span> <span>3.990 €/m²</span>
    <span>Box opz. 39.000 €</span>
    <span>3 locali</span> <span>100 m²</span>
  </article>
  <article>
    <a href="/immobile/35972645/">Bilocale in Via Tito Livio, 25, Calvairate, Milano</a>
    <span>445.000 €</span> <span>5.933 €/m²</span>
    <span>2 locali</span> <span>75 m²</span>
  </article>
</div>
<footer>idealista provincia di Milano 26.351 Milano 10.438 Abitanti 40 mq</footer>
</body></html>
"""


def test_idealista_real_card_extracts_price_and_does_not_touch_footer():
    """Regression: without a card boundary, the parser read numbers from the
    footer (all ads appeared as 40 sqm and without price)."""
    listings, _ = IdealistaScraper().parse_page(
        IDEALISTA_CARD_REALE, "https://www.idealista.it/vendita-case/milano-milano/"
    )
    by_id = {l.portal_id: l for l in listings}
    assert len(by_id) == 2

    a = by_id["36124807"]
    assert a.price == 399_000  # not 39,000 (garage) nor 3,990 (€/m²)
    assert a.sqm == 100  # not 40 (footer)
    assert a.rooms == 3
    assert a.city == "Milano"
    assert a.address == "Via Volvinio, 26"
    assert "26.351" not in a.description  # no footer text

    b = by_id["35972645"]
    assert b.price == 445_000
    assert b.sqm == 75


def test_immobiliare_heuristic_ignores_footer():
    html = """
    <html><body>
      <div><a href="/annunci/55555/">Quadrilocale centro</a>
        <span>€ 420.000</span><span>4 locali</span><span>120 mq</span></div>
      <div><a href="/annunci/66666/">Bilocale</a>
        <span>€ 200.000</span><span>2 locali</span><span>50 mq</span></div>
      <footer>Immobiliare.it 1.000.000 annunci 40 mq</footer>
    </body></html>
    """
    listings, strategy = ImmobiliareScraper().parse_page(html, "url")
    assert strategy == "heuristic"
    by_id = {l.portal_id: l for l in listings}
    assert by_id["55555"].price == 420_000 and by_id["55555"].sqm == 120
    assert by_id["66666"].price == 200_000 and by_id["66666"].sqm == 50


def test_pagination():
    s = ImmobiliareScraper()
    url2 = s.next_page_url("https://www.immobiliare.it/vendita-case/milano/?prezzoMax=300000", 2)
    assert "pag=2" in url2 and "prezzoMax=300000" in url2
    i = IdealistaScraper()
    url3 = i.next_page_url("https://www.idealista.it/vendita-case/milano-milano/", 3)
    assert url3.endswith("/lista-3.htm")
    # a page that is already paginated must not accumulate /lista-N segments
    url4 = i.next_page_url("https://www.idealista.it/vendita-case/milano-milano/lista-3.htm", 4)
    assert url4.endswith("/lista-4.htm") and url4.count("lista-") == 1


def test_idealista_extracts_city_and_address_from_url_and_title():
    i = IdealistaScraper()
    assert i._city_from_url("https://www.idealista.it/vendita-case/milano-milano/") == "Milano"
    assert (
        i._address_from_title("Trilocale in Via Volvinio, 26, Stadera, Milano")
        == "Via Volvinio, 26"
    )


def test_idealista_multi_word_city_zones_and_polygons():
    """Idealista city segment is "municipality-province": the last token must
    be discarded. Regression: "sesto-san-giovanni-milano" became "Sesto",
    breaking cross-portal deduplication (the city never matched)."""
    i = IdealistaScraper()
    assert (
        i._city_from_url("https://www.idealista.it/vendita-case/sesto-san-giovanni-milano/")
        == "Sesto San Giovanni"
    )
    # already paginated: city must not change
    assert (
        i._city_from_url("https://www.idealista.it/vendita-case/milano-milano/lista-2.htm")
        == "Milano"
    )
    # search drawn on map: better no city than an incorrect one
    assert i._city_from_url("https://www.idealista.it/aree/vendita-case/?shape=abc") == ""
    # zone search: the free-text /cerca/ endpoint (see search_builder — the
    # /municipality/zone/ page this once asserted is a 404 on the real site).
    # The segment after "vendita-case" here is the FILTER list, so the
    # positional rule read a city of "Con Prezzo 380000,dimensione" — straight
    # into the dedup fingerprint, where a bogus city silently blocks every
    # cross-portal merge for the whole search.
    assert (
        i._city_from_url(
            "https://www.idealista.it/cerca/vendita-case/con-prezzo_380000,dimensione_65/Bovisa_Milano/"
        )
        == "Milano"
    )
    # multi-word zone, and pagination on top of it
    assert (
        i._city_from_url(
            "https://www.idealista.it/cerca/vendita-case/Udine_Lambrate_Milano/lista-2.htm"
        )
        == "Milano"
    )


def test_immobiliare_builds_api_params_from_url(monkeypatch):
    s = ImmobiliareScraper()
    monkeypatch.setattr(
        s,
        "_resolve_geography",
        lambda q: (
            {
                "idNazione": "IT",
                "fkRegione": "lom",
                "idProvincia": "MI",
                "idComune": "8042",
                "idMZona[]": "10070",
            }
            if q == "citta studi"
            else {}
        ),
    )
    params = s._api_params(
        "https://www.immobiliare.it/vendita-case/milano/citta-studi/?prezzoMassimo=400000"
    )
    assert params is not None
    assert params["idContratto"] == "1"  # sale
    assert params["idComune"] == "8042"
    # a zone selection is always a list, whatever its arity and whichever
    # spelling it arrived in: one canonical repeated param, encoded on the wire
    # exactly as the single string used to be
    assert params["idMZona[]"] == ["10070"]  # zone respected
    assert params["prezzoMassimo"] == "400000"  # user filter passed to API
    assert params["path"] == "/vendita-case/milano/citta-studi/"


def test_immobiliare_api_params_rental(monkeypatch):
    s = ImmobiliareScraper()
    monkeypatch.setattr(s, "_resolve_geography", lambda q: {"idComune": "8042"})
    params = s._api_params("https://www.immobiliare.it/affitto-case/milano/")
    assert params is not None
    assert params["idContratto"] == "2"


def test_immobiliare_api_params_search_list():
    s = ImmobiliareScraper()
    params = s._api_params(
        "https://www.immobiliare.it/search-list/?idCategoria=1&idContratto=1&idNazione=IT&prezzoMassimo=380000&superficieMinima=60"
    )
    assert params is not None
    assert params["idContratto"] == "1"
    assert params["idCategoria"] == "1"
    assert params["prezzoMassimo"] == "380000"
    assert params["superficieMinima"] == "60"
    assert params["path"] == "/search-list/"


# --- A search with many zones ----------------------------------------------
#
# The URL Immobiliare's own map produces when districts are clicked: the path
# stays at the bare municipality and every district rides along as its own
# `idMZona[]`. Twenty of them, because the question this section answers is
# whether a *large* selection survives the trip to the portal intact.
_MANY_ZONE_IDS = [str(10040 + n) for n in range(20)]
_MANY_ZONE_URL = "https://www.immobiliare.it/vendita-case/milano/?" + "&".join(
    f"idMZona[]={z}" for z in _MANY_ZONE_IDS
)


def _milano_geography(monkeypatch, scraper):
    """Autocomplete resolving the municipality and nothing narrower — which is
    what the portal answers for the bare "milano" a multi-zone URL carries."""
    monkeypatch.setattr(
        scraper,
        "_resolve_geography",
        lambda q: {"idNazione": "IT", "idProvincia": "MI", "idComune": "8042"},
    )


def test_immobiliare_api_params_keeps_every_zone_of_a_many_zone_url(monkeypatch):
    """Twenty zones in, twenty zones out — beside the municipality, not instead
    of it. The geography is the area api-next needs to answer at all
    (invariant 7); the ids are the filter inside it, so losing either one scans
    for something the user did not ask for."""
    s = ImmobiliareScraper()
    _milano_geography(monkeypatch, s)
    params = s._api_params(_MANY_ZONE_URL)
    assert params is not None
    assert params["idComune"] == "8042"
    assert params["idMZona[]"] == _MANY_ZONE_IDS


def test_immobiliare_api_params_reads_every_zone_id_spelling(monkeypatch):
    """`idMZona[]` and `idMZona[0]` are one selection written two ways (the
    portal emits both, as it does for `fasciaPiano`). Passed through as they
    arrive they were two different parameters, and nothing said which one the
    portal was meant to read."""
    s = ImmobiliareScraper()
    _milano_geography(monkeypatch, s)
    params = s._api_params(
        "https://www.immobiliare.it/vendita-case/milano/?idMZona[0]=10046&idMZona[1]=10047"
    )
    assert params is not None
    assert params["idMZona[]"] == ["10046", "10047"]
    assert "idMZona[0]" not in params and "idMZona[1]" not in params


def test_immobiliare_url_zone_ids_beat_the_zone_in_the_path(monkeypatch):
    """A path zone and a query id list describe the same thing at different
    precisions. The ids are the portal's own keys and the slug is a best-effort
    name, so the ids are the selection — while the municipality the geography
    resolved stays, because it is the area they are read inside."""
    s = ImmobiliareScraper()
    monkeypatch.setattr(
        s,
        "_resolve_geography",
        lambda q: {"idComune": "8042", "idMZona[]": "10070"},
    )
    params = s._api_params(
        "https://www.immobiliare.it/vendita-case/milano/citta-studi/?idMZona[]=10046&idMZona[]=10047"
    )
    assert params is not None
    assert params["idComune"] == "8042"
    assert params["idMZona[]"] == ["10046", "10047"]


def test_immobiliare_sends_every_zone_to_the_portal(portal, monkeypatch):
    """The acceptance, measured on the wire rather than on the params dict: the
    api-next request the scraper really issues carries all twenty ids and the
    municipality together. `requested` is also the proof it never left
    loopback."""
    portal.install(monkeypatch)
    portal.serve_json("/api-next/geography/autocomplete/", mock_portal.immobiliare_geography())
    portal.serve_json("/api-next/search-list/listings/", mock_portal.immobiliare_api_page([]))

    s = ImmobiliareScraper(delay_seconds=0, max_pages=1)
    result = ScrapeResult()
    s._api_search(_MANY_ZONE_URL, result)

    listings = [p for p in portal.requested if p.startswith("/api-next/search-list/listings/")]
    assert listings, "the api-next page was never requested"
    sent = parse_qs(urlparse(listings[0]).query)
    assert sent["idMZona[]"] == _MANY_ZONE_IDS
    assert sent["idComune"] == ["8042"]


def test_immobiliare_refuses_a_selection_larger_than_one_request(portal, monkeypatch):
    """Over the request-line budget the portal truncates the query and answers
    200 for a wider search — a wrong answer wearing a right one's clothes. So
    the scrape refuses before spending the request, and names the limit."""
    portal.install(monkeypatch)
    portal.serve_json("/api-next/geography/autocomplete/", mock_portal.immobiliare_geography())
    portal.serve_json("/api-next/search-list/listings/", mock_portal.immobiliare_api_page([]))

    too_many = [str(20000 + n) for n in range(immobiliare.MAX_ZONE_IDS + 1)]
    url = "https://www.immobiliare.it/vendita-case/milano/?" + "&".join(
        f"idMZona[]={z}" for z in too_many
    )
    s = ImmobiliareScraper(delay_seconds=0, max_pages=1)
    result = ScrapeResult()
    s._api_search(url, result)

    assert str(immobiliare.MAX_ZONE_IDS) in result.error
    assert str(len(too_many)) in result.error
    assert not result.listings
    assert not [p for p in portal.requested if p.startswith("/api-next/search-list/listings/")]


class _FakeApiResp:
    """Minimal stand-in for a curl_cffi response used by the api-next path."""

    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload
        self.url = ""
        self.text = ""

    def json(self):
        if self._payload is None:
            raise json.JSONDecodeError("no body", "", 0)
        return self._payload


class _FakeApiSession:
    """A fake session whose `get` yields canned api-next responses. Assigned as
    the whole `session` object (not by patching `.get` on the real typed
    Session), matching how `_probe` wires the AdProbe below."""

    def __init__(self, responder):
        self._responder = responder
        self.headers = {}

    def get(self, url, params=None, headers=None):
        return self._responder(url, params, headers)


_API_ENTRY = {
    "realEstate": {
        "id": 999,
        "title": "Trilocale",
        "price": {"value": 250000},
        "properties": [{"surface": "80 m²", "rooms": "3", "location": {"city": "Milano"}}],
    }
}


def _api_first_scraper(monkeypatch):
    s = ImmobiliareScraper()
    monkeypatch.setattr(s, "warm_session", lambda: None)
    monkeypatch.setattr(
        s, "_api_params", lambda url: {"idComune": "8042", "idContratto": "1", "path": "/x"}
    )
    return s


def test_immobiliare_scrape_tries_api_before_html(monkeypatch):
    """api-next is the primary path: when it answers, the HTML strategies (which
    would spend a guaranteed-blocked request on the residential IP) must never
    run. Regression for the old HTML-first ordering."""
    s = _api_first_scraper(monkeypatch)

    def responder(url, params, headers):
        if (params or {}).get("pag") == "1":
            return _FakeApiResp(200, {"results": [_API_ENTRY], "maxPages": 1})
        return _FakeApiResp(200, {"results": []})

    setattr(s, "session", _FakeApiSession(responder))
    html_fetches = []
    monkeypatch.setattr(s, "fetch", lambda url: html_fetches.append(url) or "")

    result = s.scrape("https://www.immobiliare.it/vendita-case/milano/")
    assert result.strategy_used == "api-next"
    assert [l.portal_id for l in result.listings] == ["999"]
    assert html_fetches == [], "HTML must not be fetched when api-next succeeds"


def test_immobiliare_falls_back_to_html_when_api_is_unusable(monkeypatch):
    """If api-next yields nothing (endpoint changed/removed), the HTML safety
    net (strategies 1-3) still runs — it is a deliberate fallback, not dead
    code."""
    s = ImmobiliareScraper()
    monkeypatch.setattr(s, "warm_session", lambda: None)
    monkeypatch.setattr(s, "_api_params", lambda url: None)  # api-next gives up
    html = '<div><a href="/annunci/55555/">Bilocale</a><span>60 m² 3 locali € 200.000</span></div>'
    monkeypatch.setattr(s, "fetch", lambda url: html)

    result = s.scrape("https://www.immobiliare.it/vendita-case/milano/")
    assert [l.portal_id for l in result.listings] == ["55555"]
    assert result.listings[0].price == 200000


def test_api_block_recovers_the_cookie_once_when_opted_in(monkeypatch):
    """On a 403 under every impersonation, an opt-in reactive harvest mints a
    fresh cookie and retries the page — exactly once, never in a loop."""
    s = _api_first_scraper(monkeypatch)
    monkeypatch.setattr(s, "_rotate_session", lambda: False)
    recoveries = []
    monkeypatch.setattr(s, "_recover_cookie", lambda: (recoveries.append(1), True)[1])
    responses = iter(
        [
            _FakeApiResp(403),
            _FakeApiResp(200, {"results": [_API_ENTRY], "maxPages": 1}),
            _FakeApiResp(200, {"results": []}),
        ]
    )
    setattr(s, "session", _FakeApiSession(lambda u, p, h: next(responses)))

    result = s.scrape("https://www.immobiliare.it/vendita-case/milano/")
    assert recoveries == [1]
    assert [l.portal_id for l in result.listings] == ["999"]


def test_api_block_without_optin_stays_blocked(monkeypatch):
    """Reactive recovery is opt-in: with `datadome_auto_refresh` off, a 403 is
    reported as blocked and no browser is launched."""
    s = _api_first_scraper(monkeypatch)
    monkeypatch.setattr(s, "_rotate_session", lambda: False)
    monkeypatch.setattr("app.config.load_settings", lambda: {"datadome_auto_refresh": False})
    setattr(s, "session", _FakeApiSession(lambda u, p, h: _FakeApiResp(403)))
    # HTML fallback also finds nothing here; the api-next block must survive.
    monkeypatch.setattr(s, "fetch", lambda url: "")

    result = s.scrape("https://www.immobiliare.it/vendita-case/milano/")
    assert result.blocked is True


def test_immobiliare_entry_to_listing_handles_range_rooms():
    s = ImmobiliareScraper()
    entry = {
        "realEstate": {
            "id": 999,
            "title": "Nuova costruzione",
            "price": {"value": 250000},
            "properties": [{"surface": "55 m²", "rooms": "2 - 4", "location": {"city": "Milano"}}],
        }
    }
    l = s._entry_to_listing(entry)
    assert l is not None
    assert l.sqm == 55
    assert l.rooms is None  # a range is not a room count
    assert l.price == 250000


def test_impersonation_profiles_exist_in_curl_cffi():
    """`curl_cffi` is pinned open-ended (>=0.13) and drops profile names as the
    browsers they mimic age out. An unknown name raises only when a real fetch
    runs, which no test does, so a routine `pip install -U curl_cffi` could
    silently leave every scrape broken until the next live scan. Fail here
    instead, with the list to refresh."""
    import typing

    from curl_cffi.requests.impersonate import BrowserTypeLiteral

    supported = set(typing.get_args(BrowserTypeLiteral))
    for scraper in (BaseScraper, ImmobiliareScraper, IdealistaScraper):
        unknown = [p for p in scraper.impersonations if p not in supported]
        assert not unknown, f"{scraper.__name__}: unsupported profiles {unknown}"


def test_resolve_impersonations_drops_unsupported_names_but_keeps_order():
    """A curl_cffi upgrade can retire a profile name; at runtime that raises
    only on a real fetch, breaking every scrape silently. Resolving the list
    against the installed set filters the stale name while preserving the
    empirical Safari-first ordering of the survivors."""
    resolved = resolve_impersonations(["safari184", "totally_made_up_profile", "safari180"])
    assert resolved == ["safari184", "safari180"]


def test_resolve_impersonations_dedupes():
    assert resolve_impersonations(["safari184", "safari184", "safari180"]) == [
        "safari184",
        "safari180",
    ]


def test_resolve_impersonations_never_returns_empty():
    """An all-unsupported list must not leave a scraper with no handshake to
    use: it falls back to the provided default, then to the generic alias
    curl_cffi always ships. A blocked default still beats a crash."""
    fallback = resolve_impersonations(["nope1", "nope2"], ["safari180"])
    assert fallback == ["safari180"]

    last_ditch = resolve_impersonations(["nope1"], ["also_nope"])
    assert last_ditch == ["safari"]
    assert "safari" in supported_impersonations()


def test_settings_override_replaces_the_scraper_profile_list(monkeypatch):
    """A non-empty `tls_impersonations` setting is the zero-code escape hatch to
    rotate handshakes when a new block wave lands; unsupported entries in it are
    filtered out the same way the code defaults are."""
    from app import config

    monkeypatch.setattr(
        config,
        "load_settings",
        lambda: {
            **config.DEFAULT_SETTINGS,
            "tls_impersonations": ["safari180", "bogus", "firefox147"],
        },
    )
    scraper = IdealistaScraper()
    assert scraper.impersonations == ["safari180", "firefox147"]


def test_default_settings_rotate_exactly_the_measured_profiles(monkeypatch):
    """Moving the list out of the code and into settings must be invisible: on
    default settings the rotation is the same sequence, in the same order, that
    was hardcoded in `base.py` before it became data. These six names are each a
    measurement against a live portal (invariant 8) — changing one is a decision,
    never a side effect of an edit elsewhere."""
    from app import config

    monkeypatch.setattr(config, "load_settings", lambda: dict(config.DEFAULT_SETTINGS))
    for scraper in (ImmobiliareScraper(), IdealistaScraper()):
        assert scraper.impersonations == [
            "safari184",
            "chrome131_android",
            "safari180",
            "safari18_4_ios",
            "firefox147",
            "safari260",
        ]
        assert scraper.impersonations == list(BaseScraper.impersonations)


def test_a_bogus_profile_is_filtered_and_says_why(caplog):
    """The list is a setting now, so a typo in it is a user error rather than a
    code one — and a silent filter turns it into a rotation quietly shorter than
    the one configured, with nothing anywhere to explain it."""
    with caplog.at_level(logging.WARNING, logger="app.scrapers.transport"):
        assert resolve_impersonations(["safari184", "safari_from_2011"]) == ["safari184"]
    assert "safari_from_2011" in caplog.text


def test_an_empty_configured_list_still_scans(monkeypatch):
    """Fail open: emptying the setting (or upgrading from a settings.json
    written before it had a default) must degrade to the built-in rotation, never
    to a scraper with no handshake to present."""
    from app import config

    monkeypatch.setattr(
        config,
        "load_settings",
        lambda: {**config.DEFAULT_SETTINGS, "tls_impersonations": []},
    )
    assert IdealistaScraper().impersonations == list(BaseScraper.impersonations)


# --- AdProbe: "is this ad still online?" ---------------------------------------


class _Response:
    def __init__(self, status_code=200, text="Trilocale in vendita", url=None):
        self.status_code = status_code
        self.text = text
        self.url = url or "https://www.immobiliare.it/annunci/129244060/"


def _probe(response=None, raises=None) -> AdProbe:
    """A probe wired to a canned response instead of the network. A single
    impersonation profile keeps `_rotate_session` from building a real one."""
    probe = AdProbe()
    probe.impersonations = ["safari184"]

    class _Session:
        def __init__(self):
            self.urls = []
            self.headers = {}

        def get(self, url, **kwargs):
            self.urls.append(url)
            if raises is not None:
                raise raises
            return response

    setattr(probe, "session", _Session())
    return probe


def test_probe_warms_the_homepage_once_per_host():
    """A session that lands on a deep ad URL having never seen the homepage
    carries no DataDome cookie, and is the easiest thing to flag. The scrapers
    warm up before their first search page; an ad page is no different."""
    probe = _probe(_Response())
    probe.check("https://www.immobiliare.it/annunci/111/")
    probe.check("https://www.immobiliare.it/annunci/222/")
    probe.check("https://www.idealista.it/immobile/333/")

    homepages = [u for u in getattr(probe.session, "urls") if u.endswith(".it/")]
    assert homepages == ["https://www.immobiliare.it/", "https://www.idealista.it/"]


def test_a_failed_warm_up_is_not_retried_before_every_ad():
    probe = _probe(raises=OSError("no route to host"))
    probe.check("https://www.immobiliare.it/annunci/111/")
    probe.check("https://www.immobiliare.it/annunci/222/")
    assert getattr(probe.session, "urls").count("https://www.immobiliare.it/") == 1


def test_probe_reports_a_removed_ad():
    assert (
        _probe(_Response(status_code=404)).check("https://www.immobiliare.it/annunci/129244060/")
        is False
    )


def test_probe_reads_the_portals_own_404_page_served_as_200():
    """Immobiliare answers 200 with "La pagina che stai cercando non è presente
    sul nostro sito o non è più disponibile" — the status code alone lies."""
    page = "La pagina che stai cercando non è presente sul nostro sito."
    assert (
        _probe(_Response(text=page)).check("https://www.immobiliare.it/annunci/129244060/") is False
    )


def test_probe_treats_a_bounce_to_the_search_list_as_gone():
    resp = _Response(url="https://www.idealista.it/vendita-case/milano-milano/")
    assert _probe(resp).check("https://www.idealista.it/immobile/555/") is False


def test_probe_gone_page_wins_over_a_stray_captcha_mention():
    """Regression: a removed-ad page still carries DataDome's anti-bot script,
    whose URL mentions "captcha". Read the portal's own "no longer available"
    copy BEFORE the block heuristic, or a plainly-gone ad gets diverted down the
    blocked/None branch and reported "not verifiable" instead of "removed"."""
    page = (
        "<script src='https://ct.captcha-delivery.com/c.js'></script>"
        "La pagina che stai cercando non è più disponibile."
    )
    assert (
        _probe(_Response(text=page)).check("https://www.immobiliare.it/annunci/129424494/") is False
    )


def test_browser_check_reads_the_gone_page_over_a_captcha_script():
    """Regression: the availability check opened a browser that rendered
    Immobiliare's own "non più disponibile" page — a definitive gone signal —
    yet reported "not verifiable" (0 removed). The rendered DOM also held
    DataDome's anti-bot script, whose "captcha" substring tripped the block
    heuristic before the gone copy was ever read. The gone signal must win."""
    probe = AdProbe()
    probe._browser_headful = False
    probe._browser_warmed_hosts = {"www.immobiliare.it"}

    class FakeResp:
        status = 200

    class FakePage:
        url = "https://www.immobiliare.it/annunci/129424494/"

        def goto(self, url, **kwargs):
            return FakeResp()

        def wait_for_timeout(self, _ms):
            pass

        def content(self):
            # The real removed-ad page: the portal's "gone" copy AND DataDome's
            # anti-bot script (which mentions "captcha") in the same document.
            return (
                "<html><head><script src='https://ct.captcha-delivery.com/c.js'>"
                "</script></head><body>La pagina che stai cercando non è "
                "presente sul nostro sito o non è più disponibile.</body></html>"
            )

    setattr(probe, "_browser_page", FakePage())
    assert probe._browser_check_inner("https://www.immobiliare.it/annunci/129424494/") is False
    assert probe.was_blocked is False


def test_probe_confirms_a_live_ad():
    assert _probe(_Response()).check("https://www.immobiliare.it/annunci/129244060/") is True


# The portal's i18n error dictionary shipped inside every ad page's Next.js
# JSON, verbatim from a live listing captured on the real site.
_LIVE_AD_WITH_BURIED_MARKERS = (
    "<html><head><title>Vendita Appartamento Milano. Bilocale in via "
    "Lombardini</title>"
    '<script id="__NEXT_DATA__" type="application/json">'
    '{"props":{"page_service_404_generic_text1":['
    '"La pagina che stai cercando non è presente sul nostro sito o '
    'non è più disponibile."]}}</script></head>'
    "<body><h1>Bilocale in via Lombardini</h1>"
    "<p>Ottimo stato, quarto piano, € 250.000</p></body></html>"
)


def test_probe_ignores_gone_markers_buried_in_page_scripts():
    """Regression (real bug, IP 91.80.4.244): every Immobiliare ad page — live
    OR removed — embeds the portal's i18n error dictionary, "non è più
    disponibile" included, inside its Next.js JSON. Matching the gone markers
    against the raw HTML+JS reported *live* ads as removed (and a discard is
    remembered forever, invariant 16). Only the VISIBLE text may say "gone"."""
    url = "https://www.immobiliare.it/annunci/130663822/"
    assert _probe(_Response(text=_LIVE_AD_WITH_BURIED_MARKERS, url=url)).check(url) is True


def test_browser_check_ignores_gone_markers_buried_in_page_scripts():
    """Same regression on the browser transport: the rendered DOM still holds
    the buried i18n dictionary, so `_browser_check_inner` must judge "gone" from
    the visible text, not the raw content."""
    probe = AdProbe()
    probe._browser_headful = False
    probe._browser_warmed_hosts = {"www.immobiliare.it"}

    class FakeResp:
        status = 200

    class FakePage:
        url = "https://www.immobiliare.it/annunci/130663822/"

        def goto(self, url, **kwargs):
            return FakeResp()

        def wait_for_timeout(self, _ms):
            pass

        def content(self):
            return _LIVE_AD_WITH_BURIED_MARKERS

    setattr(probe, "_browser_page", FakePage())
    assert probe._browser_check_inner("https://www.immobiliare.it/annunci/130663822/") is True


def test_probe_treats_the_datadome_wall_served_200_as_blocked():
    """DataDome's "Access is temporarily restricted" wall can arrive as HTTP 200
    with no "captcha" anywhere in its text. It is still a block (unknown), never
    a removal — the false negative is the one that costs the user data."""
    wall = (
        "<html><body><h1>Access is temporarily restricted</h1>"
        "<p>We detected unusual activity from your device or network.</p>"
        "</body></html>"
    )
    probe = _probe(_Response(text=wall))
    assert probe.check("https://www.immobiliare.it/annunci/1/") is None
    assert probe.was_blocked is True


def test_a_block_never_means_the_ad_is_gone():
    """The dangerous mistake is the false negative: a listing wrongly reported
    as gone gets discarded, and a discard is remembered forever. DataDome
    blocks, timeouts and 5xx must all answer "unknown"."""
    assert _probe(_Response(status_code=403)).check("https://x.it/annunci/1/") is None
    assert (
        _probe(_Response(text="Please solve the captcha")).check("https://x.it/annunci/1/") is None
    )
    assert _probe(_Response(status_code=503)).check("https://x.it/annunci/1/") is None
    assert _probe(raises=OSError("timed out")).check("https://x.it/annunci/1/") is None


def test_only_a_refusal_sets_was_blocked():
    """The caller aborts a batch on a streak of refusals. A timeout is not a
    refusal — the portal never said no, so it must not count towards giving up."""
    refused = _probe(_Response(status_code=403))
    refused.check("https://x.it/annunci/1/")
    assert refused.was_blocked is True

    unreachable = _probe(raises=OSError("timed out"))
    unreachable.check("https://x.it/annunci/1/")
    assert unreachable.was_blocked is False

    live = _probe(_Response())
    live.check("https://www.immobiliare.it/annunci/129244060/")
    assert live.was_blocked is False


def test_browser_fallback_stays_opt_in(monkeypatch):
    """A blocked probe may fall back to a real (headless) browser, but only
    when `datadome_auto_refresh` is on: no batch may launch a browser the user
    did not ask for (invariant 18). With the flag off, a block stays a plain
    "unknown" and still counts towards the abort streak."""
    from app import config
    from app.services import cookie_harvester

    launched = []
    monkeypatch.setattr(cookie_harvester, "is_available", lambda: True)
    monkeypatch.setattr(cookie_harvester, "_launch", lambda *a, **k: launched.append(True))
    monkeypatch.setattr(config, "load_settings", lambda: {"datadome_auto_refresh": False})

    probe = _probe(_Response(status_code=403))
    assert probe.check("https://www.immobiliare.it/annunci/1/") is None
    assert probe.was_blocked is True
    assert launched == []


def test_browser_session_starts_when_opted_in(monkeypatch):
    """The same flag flipped on authorises the persistent fallback session
    (the launch itself is headless — that lives in the inner helper, faked
    here to keep the test browser-free)."""
    from app import config
    from app.services import cookie_harvester

    monkeypatch.setattr(cookie_harvester, "is_available", lambda: True)
    monkeypatch.setattr(config, "load_settings", lambda: {"datadome_auto_refresh": True})

    seen = {}

    def fake_inner(self):
        seen["started"] = True
        return True

    monkeypatch.setattr(AdProbe, "_start_browser_session_inner", fake_inner)
    probe = _probe(_Response(status_code=403))
    assert probe.start_browser_session() is True
    assert seen == {"started": True}
    probe.close_browser_session()


def test_headful_availability_check_is_opt_in_and_desktop_only(monkeypatch):
    """The availability check may open a VISIBLE browser so the watching user
    can solve a CAPTCHA by hand (`availability_browser_headful`). It is opt-in
    like every other launch (invariant 18) — and only where a human can see it:
    a Windows service runs in session 0 with no interactive desktop, so a
    visible window would hang invisibly and must fall back to headless."""
    from app import config
    from app.services import cookie_harvester

    monkeypatch.setattr(cookie_harvester, "is_available", lambda: True)
    monkeypatch.setattr(config, "load_settings", lambda: {"availability_browser_headful": True})

    seen = {}

    def fake_inner(self):
        # the launch mode is decided before the (faked) browser opens
        seen["headful"] = self._browser_headful
        return True

    monkeypatch.setattr(AdProbe, "_start_browser_session_inner", fake_inner)

    # Opted in on an interactive desktop -> visible window
    monkeypatch.setattr(cookie_harvester, "_is_session_zero_nt", lambda: False)
    probe = _probe(_Response(status_code=403))
    assert probe.start_browser_session() is True
    assert seen["headful"] is True
    probe.close_browser_session()

    # Same opt-in, but running as a background service -> headless
    monkeypatch.setattr(cookie_harvester, "_is_session_zero_nt", lambda: True)
    probe2 = _probe(_Response(status_code=403))
    assert probe2.start_browser_session() is True
    assert seen["headful"] is False
    probe2.close_browser_session()


def test_wait_for_human_solve_returns_once_the_captcha_clears():
    """The headful CAPTCHA wait polls the page until the challenge markup is
    gone (the user solved it), then lets the caller re-read the ad."""
    probe = AdProbe()

    # Speaks the BrowserEngine surface (wait/content), like everything the
    # probe drives past the launch (scrapers/browser_engine.py).
    class ClearingEngine:
        def __init__(self):
            self.polls = 0

        def humanize(self, rng=None):
            pass

        def wait(self, _ms):
            self.polls += 1

        def content(self):
            # challenged for the first two polls, then solved
            return "please solve the captcha" if self.polls < 2 else "<html>the ad</html>"

    assert probe._wait_for_human_solve(ClearingEngine()) is True


def test_browser_status_names_the_service_when_headful_is_forced_off(monkeypatch):
    """When the user turned on `availability_browser_headful` but the process
    is running as the NSSM service (session 0, no desktop), `start_browser_session`
    silently downgrades to headless — correct, but the old browser_status just
    said "(headless)", which reads identically to "headful was never asked
    for". That made a real block (portal challenge, headless run) look
    indistinguishable from a misconfiguration, and the UI told the user to
    'enable' settings that were already on. The status must name the actual
    cause so the fix (run interactively instead of as a service) is reachable."""
    from app import config
    from app.services import cookie_harvester

    monkeypatch.setattr(cookie_harvester, "is_available", lambda: True)
    monkeypatch.setattr(config, "load_settings", lambda: {"availability_browser_headful": True})
    monkeypatch.setattr(cookie_harvester, "_is_session_zero_nt", lambda: True)

    class FakeCtx:
        _engine_label = "camoufox"
        pages: list = []

        def new_page(self):
            return object()

    monkeypatch.setattr(cookie_harvester, "_launch", lambda p_factory, headless: FakeCtx())

    probe = _probe(_Response(status_code=403))
    assert probe.start_browser_session() is True
    assert "forced" in probe.browser_status
    assert "Windows service" in probe.browser_status
    probe.close_browser_session()


def test_browser_status_explains_why_no_window_opened(monkeypatch):
    """Diagnostic surfaced to the UI: when the browser does not take over, the
    probe records WHY (engine missing, no option enabled) so "why didn't the
    window open?" is answerable instead of a silent fall back to curl."""
    from app import config
    from app.services import cookie_harvester

    # Engine present, but no browser option is on
    monkeypatch.setattr(cookie_harvester, "is_available", lambda: True)
    monkeypatch.setattr(config, "load_settings", lambda: {})
    probe = _probe(_Response(status_code=403))
    assert probe.start_browser_session() is False
    assert "no browser option" in probe.browser_status

    # Engine not installed at all
    monkeypatch.setattr(cookie_harvester, "is_available", lambda: False)
    probe2 = _probe(_Response(status_code=403))
    assert probe2.start_browser_session() is False
    assert "not installed" in probe2.browser_status


def test_wait_for_human_solve_gives_up_when_ignored():
    """An unattended/ignored window must not hang the batch forever: past the
    (here shrunk) deadline the wait reports failure and the caller blocks."""
    probe = AdProbe()
    probe._HEADFUL_SOLVE_TIMEOUT_MS = 30  # ms: don't wait 3 real minutes

    class StuckEngine:
        def wait(self, _ms):
            pass

        def content(self):
            return "captcha challenge still here"

    assert probe._wait_for_human_solve(StuckEngine()) is False


def test_wait_for_human_solve_stops_promptly_when_cancelled():
    """Regression: a hard "temporarily restricted" block page has no solvable
    widget and never stops mentioning "captcha" in its own resource URLs, so
    this used to poll for the full (here shrunk) timeout with no way to stop
    it -- clicking "Stop" on the batch had no effect until it expired, and the
    visible browser window stayed open the whole time. A cancel event must be
    picked up within one poll instead."""
    import threading

    cancel_event = threading.Event()
    probe = AdProbe(cancel_event=cancel_event)
    probe._HEADFUL_SOLVE_TIMEOUT_MS = 60_000  # would hang the test if not cancelled

    class StuckEngine:
        def wait(self, _ms):
            pass

        def content(self):
            return "captcha challenge still here"

    cancel_event.set()
    assert probe._wait_for_human_solve(StuckEngine()) is False


def test_rotation_stops_when_profiles_are_exhausted():
    """Rotation must report exhaustion rather than wrap around: the caller
    turns a False into a 'blocked' scan status, and a wrapping list would
    retry the same rejected handshakes forever."""
    s = IdealistaScraper()
    setattr(s, "warm_session", lambda: None)  # no network
    setattr(s, "_new_session", lambda: None)
    for _ in range(len(s.impersonations) - 1):
        assert s._rotate_session() is True
    assert s._rotate_session() is False


# --- Regressions from the July 2026 code review ------------------------------


def test_detect_contract_reads_idcontratto_on_polygon_urls():
    """Regression: polygon/area searches (/search-list/) have no
    "affitto"/"vendita" path segment, so a rental polygon search was tagged
    "sale" — wrong Property.contract (invariant 9) and sale price bounds
    applied to monthly rents."""
    from app.scrapers.parsing import detect_contract

    assert (
        detect_contract("https://www.immobiliare.it/search-list/?idContratto=2&idCategoria=1")
        == "rent"
    )
    assert (
        detect_contract("https://www.immobiliare.it/search-list/?idContratto=1&idCategoria=1")
        == "sale"
    )
    # path segment still wins where present
    assert detect_contract("https://www.immobiliare.it/affitto-case/milano/") == "rent"
    assert detect_contract("https://www.immobiliare.it/vendita-case/milano/") == "sale"


def test_parse_sqm_handles_thousands_separator():
    """Regression: "5.000 m²" (large plots) parsed as 5.0 sqm."""
    assert parse_sqm("terreno di 5.000 m²") == 5000.0
    assert parse_sqm("90 m²") == 90.0
    assert parse_sqm("45,5 mq") == 45.5


def test_scrapers_inherit_the_full_tls_rotation():
    """Regression: both scrapers overrode `impersonations` with the original
    three-profile list, shadowing the newer anti-block profiles added to
    BaseScraper — the fix was inactive exactly where it mattered (the real
    scans; only AdProbe got it)."""
    assert ImmobiliareScraper.impersonations is BaseScraper.impersonations
    assert IdealistaScraper.impersonations is BaseScraper.impersonations
    assert "firefox147" in BaseScraper.impersonations


def test_structured_price_placeholders_are_rejected():
    """Regression: JSON-LD / embedded-state prices skipped the plausibility
    bounds parse_price applies to scraped text, so a "price on request"
    placeholder (1 €) sailed into the dashboard."""
    scraper = ImmobiliareScraper()
    entry = {
        "realEstate": {
            "id": 42,
            "title": "Trilocale",
            "price": {"value": 1},
            "properties": [{"surface": "90 m²"}],
        }
    }
    listing = scraper._entry_to_listing(entry)
    assert listing is not None
    assert listing.price is None

    ld = json.dumps(
        {
            "@type": "ItemList",
            "itemListElement": [
                {
                    "item": {
                        "@type": "RealEstateListing",
                        "url": "https://www.immobiliare.it/annunci/777/",
                        "name": "Bilocale",
                        "offers": {"price": "0"},
                    }
                }
            ],
        }
    )
    html = f'<html><head><script type="application/ld+json">{ld}</script></head></html>'
    found = scraper.parse_json_ld(html, "https://www.immobiliare.it/vendita-case/milano/")
    assert found and found[0].price is None


def test_idealista_address_survives_in_vendita_in_phrasing():
    """Regression: the most common Italian title, "Trilocale in vendita in
    Via Roma, 12, Milano", matched the first "in" and produced the corrupted
    address "vendita in Via Roma"."""
    fn = IdealistaScraper._address_from_title
    assert fn("Trilocale in vendita in Via Roma, 12, Milano") == "Via Roma, 12"
    assert fn("Trilocale in Via Volvinio, 26, Stadera, Milano") == "Via Volvinio, 26"
    assert fn("Appartamento in affitto in Corso Lodi, 3, Milano") == "Corso Lodi, 3"
    assert fn("Villa unifamiliare") == ""


# --- Was that all of them? (the page limit, said out loud) ------------------
#
# `max_pages_per_search` defaults to 10, and the stop condition it drives was
# silent: a search with forty pages of results returned the first ten and
# reported "N listings across 10 pages", a sentence that sounds complete. These
# pin both halves — a capped scrape says so and carries the portal's own
# totals, and a scrape that fit says nothing, because a truncation notice on a
# complete answer is how the real one stops being read.

TRUNCATION_SEARCH = "/vendita-case/torino/"


def _flat(n: int) -> mock_portal.Flat:
    return mock_portal.Flat(
        ad_id=f"9{n:04d}",
        title=f"Trilocale {n}",
        price=250_000 + n,
        rooms=3,
        sqm=90,
        city="Torino",
    )


def _paged_portal(portal, monkeypatch, *, total_pages: int, per_page: int = 2):
    """The sandbox serving a search that really does span several pages."""
    portal.install(monkeypatch)
    portal.serve_json("/api-next/geography/autocomplete/", mock_portal.immobiliare_geography())
    portal.serve_json_pages(
        "/api-next/search-list/listings/",
        lambda page: mock_portal.immobiliare_api_page(
            [_flat(page * 100 + i) for i in range(per_page)],
            max_pages=total_pages,
            count=total_pages * per_page,
        ),
    )


def test_a_scrape_the_page_limit_cut_short_says_so(portal, monkeypatch):
    """The acceptance: more pages on the portal than the cap allows. The scrape
    stops at the cap, and carries the two numbers the message needs — what came
    back, and what the portal said it had."""
    _paged_portal(portal, monkeypatch, total_pages=4, per_page=2)

    s = ImmobiliareScraper(delay_seconds=0, max_pages=2)
    result = ScrapeResult()
    s._api_search(portal.url(TRUNCATION_SEARCH), result)

    assert result.truncated
    assert result.truncated_by == "page_limit"
    assert result.page_limit == 2
    assert result.pages_fetched == 2
    assert result.total_pages == 4
    assert result.total_listings == 8
    assert len(result.listings) == 4


def test_a_scrape_that_fit_inside_the_cap_is_not_truncated(portal, monkeypatch):
    """The other half, and as important: the portal had two pages and the cap
    allowed ten, so everything it has is here. A false alarm at this point
    trains the user to ignore the true one."""
    _paged_portal(portal, monkeypatch, total_pages=2, per_page=2)

    s = ImmobiliareScraper(delay_seconds=0, max_pages=10)
    result = ScrapeResult()
    s._api_search(portal.url(TRUNCATION_SEARCH), result)

    assert not result.truncated
    assert result.truncated_by == ""
    assert result.pages_fetched == 2
    assert result.total_pages == 2
    assert result.total_listings == 4
    assert len(result.listings) == 4


def test_a_portal_that_declares_no_page_count_makes_no_truncation_claim(monkeypatch):
    """No `maxPages` in the payload means the app does not know whether there
    was more. It must not guess: an unstated total is reported as unstated, not
    as complete and not as truncated."""
    s = _api_first_scraper(monkeypatch)
    setattr(
        s,
        "session",
        _FakeApiSession(lambda u, p, h: _FakeApiResp(200, {"results": [_API_ENTRY], "count": 1})),
    )
    s.max_pages = 1
    result = ScrapeResult()
    s._api_search("https://www.immobiliare.it/vendita-case/milano/", result)

    assert result.total_pages is None
    assert not result.truncated


def test_the_html_path_reports_the_cap_when_a_full_page_had_a_successor(portal, monkeypatch):
    """Idealista publishes no page count anywhere a parser can reach, so the
    evidence stops at "the last page this scan was allowed to fetch was full,
    and another one follows". That is reported as the page limit with no total
    attached — never as a number nobody stated."""
    portal.install(monkeypatch)
    flats = [_flat(1), _flat(2)]
    portal.serve(TRUNCATION_SEARCH, mock_portal.idealista_results_page(flats, total=1234))
    portal.serve(
        f"{TRUNCATION_SEARCH}lista-2.htm",
        mock_portal.idealista_results_page([_flat(3), _flat(4)], total=1234),
    )

    s = IdealistaScraper(delay_seconds=0, max_pages=2)
    s.delay_seconds = 0  # the constructor floors it at 8s for the real portal
    result = s.scrape(portal.url(TRUNCATION_SEARCH))

    assert result.truncated_by == "page_limit"
    assert result.page_limit == 2
    assert result.total_listings == 1234
    assert result.total_pages is None
    assert len(result.listings) == 4


def test_the_html_path_says_nothing_when_the_results_ran_out_first(portal, monkeypatch):
    """The search ended before the cap did — the second page is empty, so this
    scan holds everything there was and claims no truncation."""
    portal.install(monkeypatch)
    portal.serve(TRUNCATION_SEARCH, mock_portal.idealista_results_page([_flat(1), _flat(2)]))
    portal.serve(f"{TRUNCATION_SEARCH}lista-2.htm", mock_portal.idealista_results_page([]))

    s = IdealistaScraper(delay_seconds=0, max_pages=5)
    s.delay_seconds = 0
    result = s.scrape(portal.url(TRUNCATION_SEARCH))

    assert not result.truncated
    assert len(result.listings) == 2


def test_a_search_page_total_is_read_only_where_the_portal_states_one():
    """The regex behind the HTML path's total. It reads the portal's own
    heading, and answers None for a page that carries no such sentence — which
    is what keeps "of about N" off a scan that was never told an N."""
    from app.scrapers.page_text import declared_result_total

    assert (
        declared_result_total("<html><body><h1>1.234 case in vendita a Milano</h1></body>") == 1234
    )
    assert declared_result_total("<html><body><p>87 annunci in affitto a Torino</p></body>") == 87
    assert (
        declared_result_total("<html><body><main>Trilocale, 3 locali, 90 m²</main></body>") is None
    )
    assert declared_result_total("<html><body><a>Case in vendita a Roma</a></body>") is None
    assert declared_result_total("") is None


# --- what a scrape reports about itself while it runs -----------------------
#
# A scrape used to be silent for its whole duration, which for a ten-page search
# at six seconds a page is minutes with nothing to show. These pin the facts it
# now emits and, as importantly, that emitting them can never cost a listing.


def _recorder() -> tuple[list[dict], Callable[..., None]]:
    seen: list[dict] = []
    return seen, lambda **facts: seen.append(facts)


def test_a_scrape_announces_every_page_before_it_asks_for_it(portal, monkeypatch):
    """The page in flight, reported before the request rather than after it:
    reported afterwards, the number on screen would always be the page that has
    already finished — silence for exactly as long as the fetch takes."""
    _paged_portal(portal, monkeypatch, total_pages=2, per_page=2)
    seen, record = _recorder()

    s = ImmobiliareScraper(delay_seconds=0, max_pages=2)
    s.on_progress = record
    s._api_search(portal.url(TRUNCATION_SEARCH), ScrapeResult())

    assert {"phase": "fetching", "page": 1} in seen
    assert {"page": 1, "listings": 2} in seen
    assert {"phase": "fetching", "page": 2} in seen
    assert {"page": 2, "listings": 4} in seen
    # the portal's own totals, once, from the page that states them
    assert {"total_pages": 2, "total_listings": 4} in seen


def test_the_html_path_reports_pages_without_inventing_a_total(portal, monkeypatch):
    """No portal publishes a page count in its HTML, so this path reports a
    rising count and no total to divide it by. That absence is the point: only
    a real total may ever be drawn as a proportion."""
    portal.install(monkeypatch)
    portal.serve(TRUNCATION_SEARCH, mock_portal.idealista_results_page([_flat(1), _flat(2)]))
    seen, record = _recorder()

    s = IdealistaScraper(delay_seconds=0, max_pages=1)
    s.delay_seconds = 0
    s.on_progress = record
    s.scrape(portal.url(TRUNCATION_SEARCH))

    assert {"phase": "fetching", "page": 1} in seen
    assert {"page": 1, "listings": 2} in seen
    assert not any("total_pages" in facts for facts in seen)
    assert {"total_listings": None} in seen


def test_the_pause_between_pages_is_announced_before_it_is_spent(monkeypatch):
    """Most of a scan's wall clock is `polite_sleep`, so announcing it after the
    fact would report the wait once it no longer matters. The seconds reported
    are the ones actually about to be slept."""
    slept: list[float] = []
    monkeypatch.setattr("app.scrapers.base.time.sleep", slept.append)
    seen, record = _recorder()

    s = BaseScraper(delay_seconds=6.0)
    s.on_progress = record
    s.polite_sleep()

    assert len(seen) == 1 and len(slept) == 1
    assert seen[0]["phase"] == "waiting"
    assert seen[0]["waiting_seconds"] == round(slept[0], 1)
    assert 4.2 <= seen[0]["waiting_seconds"] <= 8.4  # the 0.7-1.4 jitter around 6s


def test_a_watcher_that_raises_never_costs_the_scrape_a_listing(portal, monkeypatch, caplog):
    """Observability must never take a scan down. The callback belongs to the
    caller, so a broken one is contained where it is invoked rather than ending
    the scrape it was only supposed to describe."""
    _paged_portal(portal, monkeypatch, total_pages=2, per_page=2)

    def explode(**facts):
        raise RuntimeError("the watcher is broken")

    s = ImmobiliareScraper(delay_seconds=0, max_pages=2)
    s.on_progress = explode
    result = ScrapeResult()
    with caplog.at_level(logging.ERROR):
        s._api_search(portal.url(TRUNCATION_SEARCH), result)

    assert len(result.listings) == 4
    assert result.pages_fetched == 2
    assert "progress callback failed" in caplog.text


def test_a_scrape_nobody_is_watching_reports_nothing(portal, monkeypatch):
    """The default, and the one every non-scan caller uses: `AdProbe`, the
    availability check and the search validator all leave `on_progress` unset,
    and pay a single `is None` for it."""
    _paged_portal(portal, monkeypatch, total_pages=1, per_page=2)

    s = ImmobiliareScraper(delay_seconds=0, max_pages=1)
    result = ScrapeResult()
    s._api_search(portal.url(TRUNCATION_SEARCH), result)

    assert s.on_progress is None
    assert len(result.listings) == 2
