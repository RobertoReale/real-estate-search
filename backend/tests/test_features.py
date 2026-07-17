"""Tests for Horizon 1/2 features: rental support (contract detection and
rent-range price parsing), contract-aware deduplication, local pricing
statistics, search URL builder, notification channel routing, additive DB
migrations, and the property PATCH endpoint (favorites/notes)."""
from typing import Any

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Property
from app.scrapers.base import RawListing, detect_contract, parse_price
from app.services import notifier
from app.services.deduplicator import upsert_listing
from app.services.pricing_stats import annotate_market_position
from app.services.search_builder import (
    build_idealista_url, build_immobiliare_url, parse_search_url,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


# --- Rental support ---------------------------------------------------------

def test_contract_detected_from_url():
    assert detect_contract(
        "https://www.immobiliare.it/affitto-case/milano/") == "rent"
    assert detect_contract(
        "https://www.idealista.it/affitto-case/milano-milano/") == "rent"
    assert detect_contract(
        "https://www.immobiliare.it/vendita-case/milano/") == "sale"


def test_rent_price_within_monthly_range_is_parsed():
    """Regression: the sale bounds (min 10,000 €) rejected every monthly
    rent, so rental profiles produced listings without any price."""
    assert parse_price("Bilocale € 750 al mese", contract="rent") == 750.0
    # sale parsing must keep rejecting small accessory amounts
    assert parse_price("Bilocale € 750 al mese", contract="sale") is None
    assert parse_price("Trilocale € 250.000", contract="sale") == 250_000.0


def _raw(**kwargs) -> RawListing:
    base: dict[str, Any] = dict(
        portal="immobiliare", portal_id="111",
        url="https://www.immobiliare.it/annunci/111/",
        title="Trilocale via Roma", city="Milano", rooms=3, sqm=90.0,
        price=300_000.0, latitude=45.4642, longitude=9.19,
        address="Via Roma, 12",
    )
    base.update(kwargs)
    return RawListing(**base)


def test_sale_and_rent_of_same_house_are_not_merged(db):
    """The same physical house listed for sale AND for rent must stay two
    records: different price scale, different meaning for the user."""
    prop_sale, _, _ = upsert_listing(db, _raw(contract="sale"))
    prop_rent, is_new, _ = upsert_listing(db, _raw(
        portal="idealista", portal_id="999",
        url="https://www.idealista.it/immobile/999/",
        contract="rent", price=1_200.0,
    ))
    assert is_new is True
    assert prop_sale.id != prop_rent.id
    assert prop_rent.contract == "rent"


def test_existing_listing_heals_migrated_contract(db):
    """DBs migrated before rental support default every Property to "sale";
    the next scan of a rental profile must correct the label."""
    prop, _, _ = upsert_listing(db, _raw(contract="sale"))  # simulates old data
    prop2, is_new, _ = upsert_listing(db, _raw(contract="rent", price=900.0))
    assert is_new is False and prop2.id == prop.id
    assert prop2.contract == "rent"


# --- Pricing statistics -----------------------------------------------------

def _prop(**kwargs) -> Property:
    base: dict[str, Any] = dict(
        fingerprint="fp", title="Casa", city="Milano", zone="Navigli",
        contract="sale", sqm=100.0, current_min_price=300_000.0,
        status="active")
    base.update(kwargs)
    return Property(**base)


def test_market_position_below_zone_median(db):
    # zone median from 4 comparables at 3,000 €/sqm
    db.add_all([_prop() for _ in range(4)])
    cheap = _prop(current_min_price=240_000.0)  # 2,400 €/sqm = -20%
    db.add(cheap)
    db.commit()

    annotate_market_position(db, [cheap])
    assert cheap.area_median_scope == "zone"
    assert cheap.sqm_price_delta_pct == -20.0


def test_no_median_without_enough_samples(db):
    """A "median" of one or two listings is noise, not insight."""
    lone = _prop(city="Pavia", zone="Centro")
    db.add(lone)
    db.commit()
    annotate_market_position(db, [lone])
    assert lone.area_median_sqm_price is None
    assert lone.sqm_price_delta_pct is None


def test_median_falls_back_to_city_when_zone_is_sparse(db):
    db.add_all([_prop(zone=f"Z{i}") for i in range(4)])  # 4 distinct zones
    target = _prop(zone="Z0", current_min_price=150_000.0)
    db.add(target)
    db.commit()
    annotate_market_position(db, [target])
    assert target.area_median_scope == "city"
    assert target.sqm_price_delta_pct == -50.0


def test_rent_and_sale_medians_are_separate(db):
    """Mixing 300k sale prices with 1k rents would produce a meaningless
    median: statistics are always segmented by contract."""
    db.add_all([_prop() for _ in range(3)])
    rental = _prop(contract="rent", current_min_price=1_000.0)
    db.add(rental)
    db.commit()
    annotate_market_position(db, [rental])
    assert rental.area_median_sqm_price is None  # only 1 rent comparable


# --- Search builder ---------------------------------------------------------

def test_immobiliare_url_generation():
    url = build_immobiliare_url(
        city="Sesto San Giovanni", contract="sale",
        min_price=100_000, max_price=300_000, min_rooms=3, min_sqm=80,
    )
    assert url.startswith(
        "https://www.immobiliare.it/vendita-case/sesto-san-giovanni/?")
    assert "prezzoMinimo=100000" in url
    assert "prezzoMassimo=300000" in url
    assert "localiMinimo=3" in url
    assert "superficieMinima=80" in url


def test_immobiliare_rent_url():
    url = build_immobiliare_url(city="Milano", contract="rent", max_price=1200)
    assert url.startswith("https://www.immobiliare.it/affitto-case/milano/")
    assert "prezzoMassimo=1200" in url
    # generated URLs must round-trip through the scraper's contract detection
    assert detect_contract(url) == "rent"


def test_idealista_url_city_province_and_filters():
    """Grammar verified live on 2026-07-09: room segments need the numeric
    suffix ("con-trilocali/" is a 404, "con-trilocali-3/" works) and
    "min N rooms" is the union of the discrete room categories from N up to
    quadrilocali-4 (the portal's own "4 or more" bucket)."""
    url = build_idealista_url(
        city="Sesto San Giovanni", province="Milano", contract="sale",
        max_price=300_000, min_rooms=3,
    )
    assert "/vendita-case/sesto-san-giovanni-milano/" in url
    assert "con-" in url and "prezzo_300000" in url
    assert "trilocali-3,quadrilocali-4" in url


def test_idealista_room_union_is_capped_by_max_rooms():
    """Regression: an exact room count ("3 locali", as the search assistant
    produces) generated "trilocali-3,quadrilocali-4" on Idealista while
    Immobiliare honoured localiMassimo=3 — the same profile returned
    different flats on the two portals."""
    url = build_idealista_url(city="Milano", min_rooms=3, max_rooms=3)
    assert "trilocali-3" in url and "quadrilocali" not in url

    url = build_idealista_url(city="Milano", min_rooms=2, max_rooms=3)
    assert "bilocali-2,trilocali-3" in url and "quadrilocali" not in url

    # 4 is the portal's own "4 or more" bucket: capping there keeps it
    url = build_idealista_url(city="Milano", min_rooms=3, max_rooms=5)
    assert "trilocali-3,quadrilocali-4" in url


def test_idealista_url_defaults_province_to_city():
    url = build_idealista_url(city="Milano")
    assert url == "https://www.idealista.it/vendita-case/milano-milano/"


def test_accents_are_stripped_from_slugs():
    url = build_immobiliare_url(city="Cinisello Balsamo è")
    assert "cinisello-balsamo-e" in url


def test_parse_search_url_roundtrip_immobiliare():
    url = build_immobiliare_url(
        city="Sesto San Giovanni", contract="sale", zone="Centro",
        min_price=100_000, max_price=300_000, min_rooms=3, min_sqm=80,
    )
    parsed = parse_search_url(url)
    assert parsed["city"] == "Sesto San Giovanni"
    assert parsed["zone"] == "Centro"
    assert parsed["contract"] == "sale"
    assert parsed["min_price"] == 100000
    assert parsed["max_price"] == 300000
    assert parsed["min_rooms"] == 3
    assert parsed["min_sqm"] == 80


def test_parse_search_url_roundtrip_idealista():
    url = build_idealista_url(
        city="Sesto San Giovanni", province="Milano", contract="sale",
        max_price=300_000, min_rooms=3,
    )
    parsed = parse_search_url(url)
    assert parsed["city"] == "Sesto San Giovanni"
    assert parsed["province"] == "Milano"
    assert parsed["contract"] == "sale"
    assert parsed["max_price"] == 300000
    assert parsed["min_rooms"] == 3


# --- Notification channel routing -------------------------------------------

def test_broadcast_respects_channel_selection(monkeypatch):
    calls = []
    monkeypatch.setattr(notifier, "send_telegram_message",
                        lambda text: calls.append("telegram") or True)
    monkeypatch.setattr(notifier, "send_email_message",
                        lambda text, subject=None: calls.append("email") or True)

    notifier.broadcast("hi", ["email"])
    assert calls == ["email"]

    calls.clear()
    # empty selection = all channels (each still gated by its own setting)
    notifier.broadcast("hi", None)
    assert calls == ["telegram", "email"]


def test_parse_channels_csv_ignores_unknown_channels():
    assert notifier.parse_channels_csv("email, whatsapp, telegram") == [
        "email", "telegram"]
    assert notifier.parse_channels_csv("") == []


def test_profile_channels_tells_muted_apart_from_unspecified():
    """The empty string means "all enabled channels", so a muted search needs a
    value of its own: None (all) and [] (none) are different answers, and
    `channels or CHANNELS` — what broadcast used to do — collapses them."""
    assert notifier.profile_channels("") is None
    assert notifier.profile_channels("email") == ["email"]
    assert notifier.profile_channels(notifier.MUTED) == []


def test_a_muted_selection_broadcasts_nowhere(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(notifier, "send_telegram_message",
                        lambda text: calls.append("telegram") or True)
    monkeypatch.setattr(notifier, "send_email_message",
                        lambda text, subject=None: calls.append("email") or True)

    assert notifier.broadcast("hi", []) is False
    assert calls == []


def test_disabled_channels_send_nothing():
    """With default settings (everything disabled) broadcast returns False
    instead of raising: a scan must never crash because notifications are
    unconfigured."""
    assert notifier.broadcast("hi") is False


# --- Additive DB migration ---------------------------------------------------

def test_missing_columns_are_added_to_existing_db(tmp_path, monkeypatch):
    """Regression path for the "no Alembic" constraint: opening an old DB
    (created before new columns existed) must not break queries nor require
    deleting case.db (price history would be lost)."""
    from app import database

    db_file = tmp_path / "old.db"
    engine = create_engine(f"sqlite:///{db_file}")
    # simulate a pre-upgrade properties table without the new columns
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE properties (id INTEGER PRIMARY KEY, "
            "fingerprint VARCHAR, title VARCHAR)"
        ))
    monkeypatch.setattr(database, "engine", engine)
    database.init_db()

    cols = {c["name"] for c in inspect(engine).get_columns("properties")}
    assert {"contract", "is_favorite", "notes"} <= cols
    # existing rows readable with defaults applied
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO properties (fingerprint, title) "
                          "VALUES ('f', 't')"))
        row = conn.execute(text(
            "SELECT contract, is_favorite, notes FROM properties")).one()
    assert row[0] == "sale"


def test_search_builder_parse_endpoint():
    from app import schemas
    from app.main import search_builder_parse

    url = build_immobiliare_url(city="Milano", max_price=400_000, min_rooms=2)
    out = search_builder_parse(schemas.UrlIn(url=url))
    assert isinstance(out, schemas.SearchBuilderParamsOut)
    assert out.city == "Milano"
    assert out.max_price == 400000
    assert out.min_rooms == 2


def test_profile_out_includes_computed_params(db):
    from app import schemas
    from app.main import create_profile

    url = build_idealista_url(city="Milano", province="Milano", min_rooms=3, max_price=350_000)
    in_data = schemas.SearchProfileIn(name="Milan 3 rooms", search_url=url)
    profile_db = create_profile(in_data, db)
    profile_out = schemas.SearchProfileOut.model_validate(profile_db)
    assert isinstance(profile_out, schemas.SearchProfileOut)
    assert profile_out.params.city == "Milano"
    assert profile_out.params.min_rooms == 3
    assert profile_out.params.max_price == 350000


# --- PATCH endpoint (favorites & notes) --------------------------------------

def test_patch_property_updates_favorite_and_notes(db):
    # the endpoint function is called directly: spinning up TestClient would
    # also start the real scheduler via the app lifespan
    from app import schemas
    from app.main import patch_property

    prop = _prop()
    db.add(prop)
    db.commit()

    out = patch_property(prop.id,
                         schemas.PropertyPatch(is_favorite=True,
                                               notes="call agent"), db)
    assert out.is_favorite is True
    assert out.notes == "call agent"

    # partial patch must not clear the other field
    out = patch_property(prop.id,
                         schemas.PropertyPatch(notes="viewing Friday"), db)
    assert out.is_favorite is True
    assert out.notes == "viewing Friday"


def test_zone_urls_use_the_zone_page_grammar():
    """Immobiliare: zone as an extra path segment.

    Idealista: the free-text /cerca/ endpoint, because it has NO addressable
    zone page. This test used to assert /vendita-case/milano/navigli/ on the
    strength of a code comment; measured live on 2026-07-17 that grammar is a
    404, and so is /milano-milano/navigli/ — the province suffix was never the
    issue, Idealista simply keys its zone pages by internal slugs that a zone's
    name does not yield. Every zone search the app generated was therefore a
    guaranteed 404, which no offline test could have seen. /cerca/ resolves the
    location server-side and takes the same con- filters (verified: the result
    total moves 179 -> 112 when trilocali-3 is added).
    """
    assert build_immobiliare_url(city="Milano", zone="Navigli") == (
        "https://www.immobiliare.it/vendita-case/milano/navigli/"
    )
    assert build_idealista_url(city="Milano", zone="Navigli") == (
        "https://www.idealista.it/cerca/vendita-case/Navigli_Milano/"
    )
    # filters keep their con- segment, which on /cerca/ PRECEDES the location
    assert build_idealista_url(
        city="Milano", zone="Porta Romana", max_price=300_000
    ) == ("https://www.idealista.it/cerca/vendita-case/con-prezzo_300000/"
          "Porta_Romana_Milano/")
    # a plain city keeps the canonical municipality-province page: it works,
    # and it is the URL the user recognises from their own browser
    assert build_idealista_url(city="Milano") == (
        "https://www.idealista.it/vendita-case/milano-milano/"
    )


def test_zone_page_is_used_only_on_positive_proof():
    """Idealista's zone pages are real (/vendita-case/milano/forlanini/ lists
    124 flats) but keyed by its own slugs, and a zone's name is only sometimes
    one: 7 of the 8 searches in the live database 404'd. Nothing offline tells
    the two apart, so the portal is asked once — and only a clear yes buys the
    precise page. A 404, a DataDome block and a timeout all land on /cerca/,
    which always answers: an outage may cost precision, never a working search.
    """
    from app.services.search_builder import resolve_idealista_url

    params = dict(city="Milano", zone="Forlanini", max_price=380_000, min_sqm=65)

    url, zone_page = resolve_idealista_url(params, probe=lambda _u: True)
    assert zone_page is True
    assert url == ("https://www.idealista.it/vendita-case/milano/forlanini/"
                   "con-prezzo_380000,dimensione_65/")

    for answer in (False, None):  # 404, and "blocked/timed out: unknown"
        url, zone_page = resolve_idealista_url(params, probe=lambda _u: answer)
        assert zone_page is False
        assert url.startswith("https://www.idealista.it/cerca/")

    # the probe asks about the BARE zone page: a filtered one can hold zero
    # listings for honest reasons, and reading that as "dead slug" would throw
    # away a working zone page
    asked: list[str] = []
    resolve_idealista_url(params, probe=lambda u: asked.append(u) or True)
    assert asked == ["https://www.idealista.it/vendita-case/milano/forlanini/"]


def test_build_search_urls_does_not_touch_the_network_unless_asked():
    """The UI re-derives URLs to prefill its edit form; only pressing Generate
    means "go ask the portal". A probe on every call would put a live request
    behind opening a dialog."""
    def explode(_url):
        raise AssertionError("probed without verify=True")

    from app.services import search_builder as sb
    original, sb.probe_zone_page = sb.probe_zone_page, explode
    try:
        urls = sb.build_search_urls(dict(city="Milano", zone="Bovisa"))
        assert urls["idealista"].startswith("https://www.idealista.it/cerca/")
        assert urls["idealista_zone_page"] is False
    finally:
        sb.probe_zone_page = original


def test_immobiliare_filter_segment_is_not_mistaken_for_a_zone():
    """Immobiliare puts filter segments where a zone would sit
    (/vendita-case/milano/con-ascensore/). Taken as a zone it became a search
    for a district called "Con Ascensore", and the Idealista twin built from it
    was /vendita-case/milano/con-ascensore/con-prezzo_260000/ — two con-
    segments, a certain 404. Found in the live DB, twice."""
    parsed = parse_search_url(
        "https://www.immobiliare.it/vendita-case/milano/con-ascensore/?prezzoMassimo=260000")
    assert parsed["city"] == "Milano"
    assert parsed["zone"] == ""
    # a real zone still reads through, filters after it or not
    parsed = parse_search_url(
        "https://www.immobiliare.it/vendita-case/milano/bovisa/con-ascensore/?prezzoMassimo=380000")
    assert parsed["city"] == "Milano"
    assert parsed["zone"] == "Bovisa"


def test_idealista_url_with_two_con_segments_keeps_its_filters():
    """A URL can carry more than one con- segment. Reading only the first one
    dropped price and size silently, and the URL rebuilt from that parse was a
    search for the entire city (~7.800 listings against ~50) — the failure
    direction that floods the dashboard rather than emptying it. Two such URLs
    are saved in the live database."""
    parsed = parse_search_url(
        "https://www.idealista.it/vendita-case/milano/con-ascensore/con-prezzo_260000,dimensione_50/")
    assert parsed["city"] == "Milano"
    assert parsed["max_price"] == 260000
    assert parsed["min_sqm"] == 50


def test_idealista_cerca_url_parses_back_to_city_zone_and_contract():
    """The /cerca/ location is free text ("Udine_Lambrate_Milano"): nothing in
    it marks where the zone ends, so known city spellings decide the split.

    The contract is the trap: on /cerca/ the "affitto-case" segment no longer
    leads the path, and reading segments[0] (= "cerca") reported every zone
    rental as a sale — silently, since the URL still scraped fine."""
    parsed = parse_search_url(
        "https://www.idealista.it/cerca/affitto-case/con-prezzo_1500/Udine_Lambrate_Milano/")
    assert parsed["city"] == "Milano"
    assert parsed["zone"] == "Udine Lambrate"
    assert parsed["contract"] == "rent"
    assert parsed["max_price"] == 1500

    # round-trip through the builder, zone included
    url = build_idealista_url(city="Milano", zone="Bovisa", max_price=380_000,
                              min_sqm=65, contract="sale")
    parsed = parse_search_url(url)
    assert parsed["city"] == "Milano"
    assert parsed["zone"] == "Bovisa"
    assert parsed["contract"] == "sale"
    assert parsed["max_price"] == 380000
    assert parsed["min_sqm"] == 65


# --- Settings persistence -----------------------------------------------------

def test_saved_secrets_lose_their_display_spaces():
    """Gmail renders an app password as "abcd efgh ijkl mnop" and users paste it
    as shown. imaplib/smtplib forward the spaces and Gmail answers with a bare
    AUTHENTICATIONFAILED, which reads as "wrong password" and sends the user
    back to regenerate a perfectly good credential.

    Writes to the throwaway settings.json of the `isolated_settings` fixture."""
    from app import config

    saved = config.save_settings({
        "smtp_password": "jetd xuwl wvpy embm",
        "imap_password": " jetd\txuwl\nwvpy embm ",
        "telegram_bot_token": "123456:AAH ExampleToken",
        "smtp_user": "someone@gmail.com",
    })

    assert saved["smtp_password"] == "jetdxuwlwvpyembm"
    assert saved["imap_password"] == "jetdxuwlwvpyembm"
    assert saved["telegram_bot_token"] == "123456:AAHExampleToken"
    # only secrets are squeezed: a display name or keyword keeps its spaces
    assert saved["smtp_user"] == "someone@gmail.com"
    assert config.load_settings()["smtp_password"] == "jetdxuwlwvpyembm"


def test_manual_cookie_paste_stamps_its_own_timestamp():
    """A datadome cookie pasted by hand must refresh datadome_cookie_updated_at:
    otherwise the UI shows a stale "Last refreshed" and the pre-scan
    auto-refresh judges the fresh paste stale, launching a browser for nothing.
    The harvester's own explicit timestamp must still win over the stamp.

    Writes to the throwaway settings.json of the `isolated_settings` fixture."""
    from app import config

    saved = config.save_settings({"datadome_cookie": "aFreshlyPastedToken"})
    assert saved["datadome_cookie_updated_at"], "manual paste must be stamped"

    # an unrelated save must not touch the timestamp
    stamp = saved["datadome_cookie_updated_at"]
    assert config.save_settings({"proxy_url": "x"})["datadome_cookie_updated_at"] == stamp

    # the harvester passes its timestamp explicitly: it must not be overridden
    saved = config.save_settings({
        "datadome_cookie": "harvestedToken",
        "datadome_cookie_updated_at": "2026-01-01T00:00:00+00:00",
    })
    assert saved["datadome_cookie_updated_at"] == "2026-01-01T00:00:00+00:00"


def test_properties_status_param_rejects_typos():
    """GET /api/properties?status=<typo> must fail loudly, not answer [].

    An unknown status used to filter `WHERE status == '<typo>'` and return an
    empty list — indistinguishable from "no matches", the same silent-failure
    shape as invariant 7. The route is inspected instead of spun up: TestClient
    would need httpx and would start the real scheduler via the app lifespan.
    """
    from fastapi.routing import APIRoute

    from app.main import app

    route = next(
        r for r in app.router.routes
        if isinstance(r, APIRoute) and r.path == "/api/properties"
        and "GET" in (r.methods or set())
    )
    status_param = next(
        p for p in route.dependant.query_params if p.name == "status"
    )

    for good in ("active", "filtered", "gone", "hidden", "all"):
        _, errors = status_param.validate(good, {}, loc=("query", "status"))
        assert not errors, f"'{good}' is a real status and must stay accepted"

    _, errors = status_param.validate("actve", {}, loc=("query", "status"))
    assert errors, "a typo'd status must be a 422, not an empty result set"


def test_callable_default_columns_are_backfilled(tmp_path, monkeypatch):
    """Regression: the additive migration only knew literal defaults, so a
    new non-nullable datetime column (default=utcnow, a callable) left every
    existing row NULL — and the first Pydantic read of an old row 500'd."""
    from app import database

    db_file = tmp_path / "old.db"
    engine = create_engine(f"sqlite:///{db_file}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE properties (id INTEGER PRIMARY KEY, "
            "fingerprint VARCHAR, title VARCHAR)"
        ))
        conn.execute(text(
            "INSERT INTO properties (fingerprint, title) VALUES ('f', 't')"
        ))
    monkeypatch.setattr(database, "engine", engine)
    database.init_db()

    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT first_seen_at, last_seen_at FROM properties"
        )).one()
    assert row[0] is not None, "utcnow-defaulted column must be backfilled"
    assert row[1] is not None


def test_updating_a_profile_url_rearms_the_baseline(db):
    """Regression (invariant 3): editing search_url left baseline_done=True
    from the old search, so the next scan — effectively the first on the new
    search — notified every single listing as "new"."""
    from app import schemas
    from app.main import update_profile
    from app.models import SearchProfile
    from datetime import datetime, timezone

    profile = SearchProfile(
        name="Test", portal="immobiliare",
        search_url="https://www.immobiliare.it/vendita-case/milano/",
        baseline_done=True, last_run_at=datetime.now(timezone.utc),
        last_run_status="ok", consecutive_failures=2, health_alert_sent=True,
    )
    db.add(profile)
    db.commit()

    # same URL: baseline untouched
    update_profile(profile.id, schemas.SearchProfileIn(
        name="Renamed", search_url=profile.search_url), db)
    assert profile.baseline_done is True

    # new URL: a new search — the next scan must be a silent baseline
    update_profile(profile.id, schemas.SearchProfileIn(
        name="Renamed", search_url="https://www.immobiliare.it/vendita-case/torino/"), db)
    assert profile.baseline_done is False
    assert profile.last_run_at is None
    assert profile.consecutive_failures == 0
    assert profile.health_alert_sent is False
