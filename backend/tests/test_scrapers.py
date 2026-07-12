"""Verification of multi-strategy pipeline on simulated HTML pages:
the parser must dynamically choose JSON-LD -> embedded -> heuristic."""
import json

from app.scrapers.immobiliare import ImmobiliareScraper
from app.scrapers.idealista import IdealistaScraper
from app.scrapers.base import (
    AdProbe,
    BaseScraper,
    parse_price,
    parse_rooms,
    parse_sqm,
    resolve_impersonations,
    supported_impersonations,
)

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
    assert a.price == 399_000          # not 39,000 (garage) nor 3,990 (€/m²)
    assert a.sqm == 100                # not 40 (footer)
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
    assert i._address_from_title(
        "Trilocale in Via Volvinio, 26, Stadera, Milano"
    ) == "Via Volvinio, 26"


def test_idealista_multi_word_city_zones_and_polygons():
    """Idealista city segment is "municipality-province": the last token must
    be discarded. Regression: "sesto-san-giovanni-milano" became "Sesto",
    breaking cross-portal deduplication (the city never matched)."""
    i = IdealistaScraper()
    assert i._city_from_url(
        "https://www.idealista.it/vendita-case/sesto-san-giovanni-milano/"
    ) == "Sesto San Giovanni"
    # already paginated: city must not change
    assert i._city_from_url(
        "https://www.idealista.it/vendita-case/milano-milano/lista-2.htm"
    ) == "Milano"
    # search drawn on map: better no city than an incorrect one
    assert i._city_from_url(
        "https://www.idealista.it/aree/vendita-case/?shape=abc"
    ) == ""
    # zone page: /municipality/zone/
    assert i._city_from_url(
        "https://www.idealista.it/vendita-case/milano/navigli/"
    ) == "Milano"


def test_immobiliare_builds_api_params_from_url(monkeypatch):
    s = ImmobiliareScraper()
    monkeypatch.setattr(s, "_resolve_geography", lambda q: {
        "idNazione": "IT", "fkRegione": "lom", "idProvincia": "MI",
        "idComune": "8042", "idMZona[]": "10070",
    } if q == "citta studi" else {})
    params = s._api_params(
        "https://www.immobiliare.it/vendita-case/milano/citta-studi/?prezzoMassimo=400000"
    )
    assert params is not None
    assert params["idContratto"] == "1"          # sale
    assert params["idComune"] == "8042"
    assert params["idMZona[]"] == "10070"        # zone respected
    assert params["prezzoMassimo"] == "400000"   # user filter passed to API
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



def test_immobiliare_entry_to_listing_handles_range_rooms():
    s = ImmobiliareScraper()
    entry = {"realEstate": {
        "id": 999, "title": "Nuova costruzione",
        "price": {"value": 250000},
        "properties": [{"surface": "55 m²", "rooms": "2 - 4",
                        "location": {"city": "Milano"}}],
    }}
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
    resolved = resolve_impersonations(
        ["safari184", "totally_made_up_profile", "safari180"]
    )
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
        lambda: {**config.DEFAULT_SETTINGS,
                 "tls_impersonations": ["safari180", "bogus", "firefox147"]},
    )
    scraper = IdealistaScraper()
    assert scraper.impersonations == ["safari180", "firefox147"]


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
    assert homepages == ["https://www.immobiliare.it/",
                         "https://www.idealista.it/"]


def test_a_failed_warm_up_is_not_retried_before_every_ad():
    probe = _probe(raises=OSError("no route to host"))
    probe.check("https://www.immobiliare.it/annunci/111/")
    probe.check("https://www.immobiliare.it/annunci/222/")
    assert getattr(probe.session, "urls").count("https://www.immobiliare.it/") == 1


def test_probe_reports_a_removed_ad():
    assert _probe(_Response(status_code=404)).check(
        "https://www.immobiliare.it/annunci/129244060/"
    ) is False


def test_probe_reads_the_portals_own_404_page_served_as_200():
    """Immobiliare answers 200 with "La pagina che stai cercando non è presente
    sul nostro sito o non è più disponibile" — the status code alone lies."""
    page = "La pagina che stai cercando non è presente sul nostro sito."
    assert _probe(_Response(text=page)).check(
        "https://www.immobiliare.it/annunci/129244060/"
    ) is False


def test_probe_treats_a_bounce_to_the_search_list_as_gone():
    resp = _Response(url="https://www.idealista.it/vendita-case/milano-milano/")
    assert _probe(resp).check("https://www.idealista.it/immobile/555/") is False


def test_probe_confirms_a_live_ad():
    assert _probe(_Response()).check(
        "https://www.immobiliare.it/annunci/129244060/"
    ) is True


def test_a_block_never_means_the_ad_is_gone():
    """The dangerous mistake is the false negative: a listing wrongly reported
    as gone gets discarded, and a discard is remembered forever. DataDome
    blocks, timeouts and 5xx must all answer "unknown"."""
    assert _probe(_Response(status_code=403)).check("https://x.it/annunci/1/") is None
    assert _probe(_Response(text="Please solve the captcha")).check(
        "https://x.it/annunci/1/"
    ) is None
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
    monkeypatch.setattr(cookie_harvester, "_launch",
                        lambda *a, **k: launched.append(True))
    monkeypatch.setattr(config, "load_settings",
                        lambda: {"datadome_auto_refresh": False})

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
    monkeypatch.setattr(config, "load_settings",
                        lambda: {"datadome_auto_refresh": True})

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
    monkeypatch.setattr(config, "load_settings",
                        lambda: {"availability_browser_headful": True})

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

    class ClearingPage:
        def __init__(self):
            self.polls = 0

        def wait_for_timeout(self, _ms):
            self.polls += 1

        def content(self):
            # challenged for the first two polls, then solved
            return "please solve the captcha" if self.polls < 2 else "<html>the ad</html>"

    assert probe._wait_for_human_solve(ClearingPage()) is True


def test_wait_for_human_solve_gives_up_when_ignored():
    """An unattended/ignored window must not hang the batch forever: past the
    (here shrunk) deadline the wait reports failure and the caller blocks."""
    probe = AdProbe()
    probe._HEADFUL_SOLVE_TIMEOUT_MS = 30  # ms: don't wait 3 real minutes

    class StuckPage:
        def wait_for_timeout(self, _ms):
            pass

        def content(self):
            return "captcha challenge still here"

    assert probe._wait_for_human_solve(StuckPage()) is False


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
