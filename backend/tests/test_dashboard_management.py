"""Tests for dashboard bulk-management features: property origin tracking
(scan vs email import), the free-text / zone / source filters and the
"filter by a monitored search" overlay on the grid, and the bulk
hide/restore/favorite endpoint.

Each covers a concrete usability gap: an inbox flooded with imports the user
cannot tell apart from monitored finds, cannot search by zone, and cannot prune
in bulk. Endpoint functions are called directly (like test_features) so the app
lifespan — and the real scheduler — never starts."""
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import schemas
from app.database import Base
from app.main import _select_properties, bulk_properties
from app.models import SearchProfile
from app.scrapers.base import RawListing
from app.services.deduplicator import upsert_listing


def list_properties(*, db, **kw):
    """Call the grid selection with sensible defaults filled in.

    The real endpoint uses FastAPI `Query(...)` defaults which only resolve
    under a request; called directly they leak Query objects into the SQL, so
    tests target the shared `_select_properties` helper instead."""
    params: dict[str, Any] = dict(
        status="active", contract=None, city=None, min_price=None,
        max_price=None, min_sqm=None, rooms=None, only_price_drops=False,
        only_favorites=False, sort="newest",
    )
    params.update(kw)
    return _select_properties(db, **params)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def _raw(**kwargs) -> RawListing:
    base: dict[str, Any] = dict(
        portal="immobiliare", portal_id="111",
        url="https://www.immobiliare.it/annunci/111/",
        title="Trilocale via Roma", city="Milano", zone="Navigli",
        rooms=3, sqm=90.0, price=300_000.0,
        latitude=45.4642, longitude=9.19, address="Via Roma, 12",
    )
    base.update(kwargs)
    return RawListing(**base)


# --- Origin tracking (source) ----------------------------------------------

def test_scan_creates_scan_origin_property(db):
    prop, is_new, _ = upsert_listing(db, _raw())
    assert is_new is True
    assert prop.source == "scan"


def test_email_accept_creates_email_origin_property(db):
    prop, _, _ = upsert_listing(db, _raw(), source="email")
    assert prop.source == "email"


def test_email_origin_upgraded_to_scan_when_a_scan_refinds_it(db):
    """"email" must mean "only ever seen via the inbox": the moment a monitored
    search covers the same ad, it is a legitimate scan result and the bulk
    "prune all email imports" gesture must no longer catch it."""
    prop, _, _ = upsert_listing(db, _raw(), source="email")
    assert prop.source == "email"
    # same portal ad re-found by a scan (existing-listing branch)
    prop_again, is_new, _ = upsert_listing(db, _raw())
    assert is_new is False
    assert prop_again.id == prop.id
    assert prop_again.source == "scan"


def test_email_import_into_scan_property_never_downgrades(db):
    """An email import merging into a scan-origin property leaves it "scan":
    source is only ever upgraded, never lowered."""
    prop, _, _ = upsert_listing(db, _raw())
    assert prop.source == "scan"
    # a different portal ad of the same physical house, imported from email
    same, is_new, _ = upsert_listing(db, _raw(
        portal="idealista", portal_id="999",
        url="https://www.idealista.it/immobile/999/",
    ), source="email")
    assert is_new is False
    assert same.id == prop.id
    assert same.source == "scan"


# --- Filters: q / zone / source --------------------------------------------

def _seed_mixed(db):
    scan = upsert_listing(db, _raw(portal_id="1"))[0]
    email = upsert_listing(db, _raw(
        portal="idealista", portal_id="2",
        url="https://www.idealista.it/immobile/2/",
        title="Nuova costruzione San Siro", zone="San Siro",
        address="Via Novara, 5", latitude=45.48, longitude=9.12,
    ), source="email")[0]
    db.commit()
    return scan, email


def test_source_filter_isolates_email_imports(db):
    scan, email = _seed_mixed(db)
    out = list_properties(db=db, source="email")
    assert [p.id for p in out] == [email.id]
    out = list_properties(db=db, source="scan")
    assert [p.id for p in out] == [scan.id]


def test_zone_filter_matches_substring_case_insensitive(db):
    _scan, email = _seed_mixed(db)
    out = list_properties(db=db, zone="san siro")
    assert [p.id for p in out] == [email.id]


def test_free_text_q_matches_title_and_zone_and_description(db):
    scan, email = _seed_mixed(db)
    # title of the email one
    assert [p.id for p in list_properties(db=db, q="nuova costruzione")] == [email.id]
    # zone
    assert [p.id for p in list_properties(db=db, q="San Siro")] == [email.id]
    # nothing matches -> empty (not an error)
    assert list_properties(db=db, q="zzz-no-match") == []
    # a term present in both titles ("Trilocale" only in scan's) stays specific
    assert [p.id for p in list_properties(db=db, q="Trilocale")] == [scan.id]


def test_q_matches_listing_description(db):
    prop = upsert_listing(db, _raw(description="Attico con vista, in asta giudiziaria"))[0]
    db.commit()
    assert [p.id for p in list_properties(db=db, q="asta giudiziaria")] == [prop.id]


def test_q_terms_are_anded_across_fields(db):
    """Multi-word search ANDs the terms and each may match a different field:
    "attico navigli" must find a property whose *title* says attico and whose
    *zone* says Navigli — a single substring never would, since no one field
    holds the whole phrase."""
    hit = upsert_listing(db, _raw(portal_id="1", title="Attico ristrutturato", zone="Navigli"))[0]
    # same zone but a different type: the "attico" term must exclude it
    miss = upsert_listing(db, _raw(
        portal="idealista", portal_id="2",
        url="https://www.idealista.it/immobile/2/",
        title="Bilocale economico", zone="Navigli",
        latitude=45.99, longitude=9.99, address="Via Altra, 9",
    ))[0]
    db.commit()
    out = [p.id for p in list_properties(db=db, q="attico navigli")]
    assert out == [hit.id]
    assert miss.id not in out


def test_q_matches_floor(db):
    """The floor is a field a user types ("piano terra"): searching it must
    work, so a listing on the ground floor surfaces without scrolling."""
    ground = upsert_listing(db, _raw(portal_id="1", floor="piano terra"))[0]
    upsert_listing(db, _raw(
        portal="idealista", portal_id="2",
        url="https://www.idealista.it/immobile/2/",
        floor="3", latitude=45.99, longitude=9.99, address="Via Altra, 9",
    ))
    db.commit()
    assert [p.id for p in list_properties(db=db, q="piano terra")] == [ground.id]


def test_q_floor_term_does_not_match_as_substring(db):
    """A bare floor query like "1" must not match "17" or "21": floor search
    needs word-boundary matching, not substring (same class of bug invariant 4
    forbids for keywords: "asta" must not match inside "Castanese")."""
    first = upsert_listing(db, _raw(portal_id="1", floor="1"))[0]
    upsert_listing(db, _raw(
        portal="idealista", portal_id="2",
        url="https://www.idealista.it/immobile/2/",
        floor="17", latitude=45.99, longitude=9.99, address="Via Altra, 9",
    ))
    upsert_listing(db, _raw(
        portal="immobiliare", portal_id="3",
        url="https://www.immobiliare.it/annunci/3/",
        floor="21", latitude=45.50, longitude=9.50, address="Via Terza, 9",
    ))
    db.commit()
    assert [p.id for p in list_properties(db=db, q="1")] == [first.id]


def test_q_floor_phrase_does_not_leak_into_other_fields(db):
    """"1 piano"/"piano 1" is an Italian floor query: pairing a digit with
    "piano" must filter on the floor field alone. Treating "1" and "piano" as
    two independent AND terms (each matchable in any field) let a floor-17
    listing through: "1" matched a street number in the address and "piano"
    matched the listing description, even though the floor itself was 17."""
    ground = upsert_listing(db, _raw(portal_id="1", floor="1"))[0]
    upsert_listing(db, _raw(
        portal="idealista", portal_id="2",
        url="https://www.idealista.it/immobile/2/",
        floor="17", address="Viale Fulvio Testi 110",
        description="Ultimo piano, vista panoramica",
        latitude=45.99, longitude=9.99,
    ))
    db.commit()
    assert [p.id for p in list_properties(db=db, q="1 piano")] == [ground.id]
    assert [p.id for p in list_properties(db=db, q="piano 1")] == [ground.id]


# --- Filter by a monitored search (profile overlay) ------------------------

def test_profile_overlay_applies_contract_city_and_keywords(db):
    """Selecting a monitored search filters the whole grid — including email
    imports, which never passed through the scan's keyword filter — by that
    profile's contract, city and exclusion keywords."""
    clean = upsert_listing(db, _raw(portal_id="1", title="Trilocale luminoso"))[0]
    auction = upsert_listing(db, _raw(
        portal="idealista", portal_id="2",
        url="https://www.idealista.it/immobile/2/",
        title="Trilocale in asta", latitude=45.99, longitude=9.99,
        address="Via Altra, 9",
    ), source="email")[0]
    profile = SearchProfile(
        name="Milano vendita", portal="immobiliare",
        search_url="https://www.immobiliare.it/vendita-case/milano/",
        excluded_keywords="asta",
    )
    db.add(profile)
    db.commit()

    out = list_properties(db=db, profile_id=profile.id)
    ids = [p.id for p in out]
    assert clean.id in ids
    assert auction.id not in ids  # dropped by the profile's "asta" keyword


# --- Bulk endpoint ----------------------------------------------------------

def test_bulk_hide_and_restore(db):
    scan, email = _seed_mixed(db)
    res = bulk_properties(
        schemas.PropertyBulkIn(ids=[scan.id, email.id], action="hide"), db)
    assert res["processed"] == 2
    db.refresh(scan)
    db.refresh(email)
    assert scan.status == "hidden" and email.status == "hidden"
    assert list_properties(db=db, status="active") == []

    bulk_properties(schemas.PropertyBulkIn(ids=[scan.id], action="restore"), db)
    db.refresh(scan)
    assert scan.status == "active"


def test_bulk_favorite(db):
    scan, email = _seed_mixed(db)
    bulk_properties(
        schemas.PropertyBulkIn(ids=[scan.id, email.id], action="favorite"), db)
    db.refresh(scan)
    assert scan.is_favorite is True
    assert len(list_properties(db=db, only_favorites=True)) == 2


def test_bulk_skips_missing_ids(db):
    scan, _ = _seed_mixed(db)
    res = bulk_properties(
        schemas.PropertyBulkIn(ids=[scan.id, 999999], action="hide"), db)
    assert res["processed"] == 1
