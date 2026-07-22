"""Tests for dashboard bulk-management features: property origin tracking
(scan vs email import), the free-text / zone / source filters and the
"filter by a monitored search" overlay on the grid, and the bulk
hide/restore/favorite endpoint.

Each covers a concrete usability gap: an inbox flooded with imports the user
cannot tell apart from monitored finds, cannot search by zone, and cannot prune
in bulk. Endpoint functions are called directly (like test_features) so the app
lifespan — and the real scheduler — never starts."""

from datetime import UTC
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import schemas
from app.database import Base
from app.main import _select_properties, bulk_properties, restore_property
from app.models import SearchProfile
from app.scrapers.base import RawListing
from app.services.deduplicator import upsert_listing


def list_properties(*, db, **kw):
    """Call the grid selection with sensible defaults filled in.

    The real endpoint uses FastAPI `Query(...)` defaults which only resolve
    under a request; called directly they leak Query objects into the SQL, so
    tests target the shared `_select_properties` helper instead."""
    params: dict[str, Any] = dict(
        status="active",
        contract=None,
        city=None,
        min_price=None,
        max_price=None,
        min_sqm=None,
        rooms=None,
        only_price_drops=False,
        only_favorites=False,
        sort="newest",
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
        portal="immobiliare",
        portal_id="111",
        url="https://www.immobiliare.it/annunci/111/",
        title="Trilocale via Roma",
        city="Milano",
        zone="Navigli",
        rooms=3,
        sqm=90.0,
        price=300_000.0,
        latitude=45.4642,
        longitude=9.19,
        address="Via Roma, 12",
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
    """ "email" must mean "only ever seen via the inbox": the moment a monitored
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
    same, is_new, _ = upsert_listing(
        db,
        _raw(
            portal="idealista",
            portal_id="999",
            url="https://www.idealista.it/immobile/999/",
        ),
        source="email",
    )
    assert is_new is False
    assert same.id == prop.id
    assert same.source == "scan"


# --- Filters: q / zone / source --------------------------------------------


def _seed_mixed(db):
    scan = upsert_listing(db, _raw(portal_id="1"))[0]
    email = upsert_listing(
        db,
        _raw(
            portal="idealista",
            portal_id="2",
            url="https://www.idealista.it/immobile/2/",
            title="Nuova costruzione San Siro",
            zone="San Siro",
            address="Via Novara, 5",
            latitude=45.48,
            longitude=9.12,
        ),
        source="email",
    )[0]
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
    miss = upsert_listing(
        db,
        _raw(
            portal="idealista",
            portal_id="2",
            url="https://www.idealista.it/immobile/2/",
            title="Bilocale economico",
            zone="Navigli",
            latitude=45.99,
            longitude=9.99,
            address="Via Altra, 9",
        ),
    )[0]
    db.commit()
    out = [p.id for p in list_properties(db=db, q="attico navigli")]
    assert out == [hit.id]
    assert miss.id not in out


def test_q_matches_floor(db):
    """The floor is a field a user types ("piano terra"): searching it must
    work, so a listing on the ground floor surfaces without scrolling."""
    ground = upsert_listing(db, _raw(portal_id="1", floor="piano terra"))[0]
    upsert_listing(
        db,
        _raw(
            portal="idealista",
            portal_id="2",
            url="https://www.idealista.it/immobile/2/",
            floor="3",
            latitude=45.99,
            longitude=9.99,
            address="Via Altra, 9",
        ),
    )
    db.commit()
    assert [p.id for p in list_properties(db=db, q="piano terra")] == [ground.id]


def test_q_floor_term_does_not_match_as_substring(db):
    """A bare floor query like "1" must not match "17" or "21": floor search
    needs word-boundary matching, not substring (same class of bug invariant 4
    forbids for keywords: "asta" must not match inside "Castanese")."""
    first = upsert_listing(db, _raw(portal_id="1", floor="1"))[0]
    upsert_listing(
        db,
        _raw(
            portal="idealista",
            portal_id="2",
            url="https://www.idealista.it/immobile/2/",
            floor="17",
            latitude=45.99,
            longitude=9.99,
            address="Via Altra, 9",
        ),
    )
    upsert_listing(
        db,
        _raw(
            portal="immobiliare",
            portal_id="3",
            url="https://www.immobiliare.it/annunci/3/",
            floor="21",
            latitude=45.50,
            longitude=9.50,
            address="Via Terza, 9",
        ),
    )
    db.commit()
    assert [p.id for p in list_properties(db=db, q="1")] == [first.id]


def test_q_floor_phrase_does_not_leak_into_other_fields(db):
    """ "1 piano"/"piano 1" is an Italian floor query: pairing a digit with
    "piano" must filter on the floor field alone. Treating "1" and "piano" as
    two independent AND terms (each matchable in any field) let a floor-17
    listing through: "1" matched a street number in the address and "piano"
    matched the listing description, even though the floor itself was 17."""
    ground = upsert_listing(db, _raw(portal_id="1", floor="1"))[0]
    upsert_listing(
        db,
        _raw(
            portal="idealista",
            portal_id="2",
            url="https://www.idealista.it/immobile/2/",
            floor="17",
            address="Viale Fulvio Testi 110",
            description="Ultimo piano, vista panoramica",
            latitude=45.99,
            longitude=9.99,
        ),
    )
    db.commit()
    assert [p.id for p in list_properties(db=db, q="1 piano")] == [ground.id]
    assert [p.id for p in list_properties(db=db, q="piano 1")] == [ground.id]


def test_q_floor_phrase_accepts_english_floor_word(db):
    """The whole UI is in English, so "floor 4"/"4 floor" must behave exactly
    like the Italian "4 piano" — a floor query on the floor field alone, not
    two loose AND terms that leak into address/description (the bug the Italian
    twin above documents). Reported by a user: "4 piano" worked, "floor 4"
    silently returned nothing."""
    fourth = upsert_listing(db, _raw(portal_id="1", floor="4"))[0]
    upsert_listing(
        db,
        _raw(
            portal="idealista",
            portal_id="2",
            url="https://www.idealista.it/immobile/2/",
            floor="17",
            address="Viale Fulvio Testi 4",
            description="Quarto piano ristrutturato",
            latitude=45.99,
            longitude=9.99,
        ),
    )
    db.commit()
    assert [p.id for p in list_properties(db=db, q="floor 4")] == [fourth.id]
    assert [p.id for p in list_properties(db=db, q="4 floor")] == [fourth.id]


def test_floor_band_filter_reads_the_free_text_label(db):
    """The dashboard's Floor dropdown filters on bands parsed from the messy
    free-text floor label, reusing the one floor reader (match_score). Ground
    ("piano terra") reads as 0; "attico"/"ultimo" is the top band even though no
    number is present; an unreadable/empty floor matches no band and drops out
    (it cannot be shown to satisfy the filter)."""
    ground = upsert_listing(db, _raw(portal_id="1", floor="piano terra"))[0]
    second = upsert_listing(
        db,
        _raw(
            portal="idealista",
            portal_id="2",
            url="https://www.idealista.it/immobile/2/",
            floor="2",
            latitude=45.99,
            longitude=9.99,
            address="Via Altra, 9",
        ),
    )[0]
    seventh = upsert_listing(
        db,
        _raw(
            portal="immobiliare",
            portal_id="3",
            url="https://www.immobiliare.it/annunci/3/",
            floor="7",
            latitude=45.50,
            longitude=9.50,
            address="Via Terza, 9",
        ),
    )[0]
    attic = upsert_listing(
        db,
        _raw(
            portal="immobiliare",
            portal_id="4",
            url="https://www.immobiliare.it/annunci/4/",
            floor="Attico",
            latitude=45.10,
            longitude=9.10,
            address="Via Quarta, 9",
        ),
    )[0]
    # unreadable floor: excluded from every band
    upsert_listing(
        db,
        _raw(
            portal="immobiliare",
            portal_id="5",
            url="https://www.immobiliare.it/annunci/5/",
            floor="",
            latitude=45.20,
            longitude=9.20,
            address="Via Quinta, 9",
        ),
    )
    db.commit()

    # "R" (piano rialzato) is stored as the bare abbreviation and must count as
    # ground, or the mezzanine falls through the parser and drops out of the band
    mezzanine = upsert_listing(
        db,
        _raw(
            portal="immobiliare",
            portal_id="6",
            url="https://www.immobiliare.it/annunci/6/",
            floor="R",
            latitude=45.30,
            longitude=9.30,
            address="Via Sesta, 9",
        ),
    )[0]
    db.commit()

    assert {p.id for p in list_properties(db=db, floor_band="ground")} == {ground.id, mezzanine.id}
    assert [p.id for p in list_properties(db=db, floor_band="low")] == [second.id]
    assert [p.id for p in list_properties(db=db, floor_band="high")] == [seventh.id]
    assert [p.id for p in list_properties(db=db, floor_band="top")] == [attic.id]


def test_max_sqm_filter_caps_the_surface(db):
    """Min sqm alone can't express "small flats only"; Max sqm is its symmetric
    twin (a bare number in the DB, so a plain SQL bound)."""
    small = upsert_listing(db, _raw(portal_id="1", sqm=55.0))[0]
    upsert_listing(
        db,
        _raw(
            portal="idealista",
            portal_id="2",
            url="https://www.idealista.it/immobile/2/",
            sqm=140.0,
            latitude=45.99,
            longitude=9.99,
            address="Via Altra, 9",
        ),
    )
    db.commit()
    assert [p.id for p in list_properties(db=db, max_sqm=80.0)] == [small.id]


def test_portal_filter_keeps_cards_present_on_that_portal(db):
    """A card can group ads from several portals; the Portal filter keeps the
    ones with at least one ad on the chosen portal (not "all of its ads there")."""
    imm = upsert_listing(db, _raw(portal_id="1"))[0]
    ideal = upsert_listing(
        db,
        _raw(
            portal="idealista",
            portal_id="2",
            url="https://www.idealista.it/immobile/2/",
            latitude=45.99,
            longitude=9.99,
            address="Via Altra, 9",
        ),
    )[0]
    db.commit()
    assert [p.id for p in list_properties(db=db, portal="idealista")] == [ideal.id]
    assert [p.id for p in list_properties(db=db, portal="immobiliare")] == [imm.id]


def test_agency_filter_matches_a_substring(db):
    """Agency is stored on the listing; the filter is a case-insensitive
    substring so "tecnocasa" finds "Tecnocasa Milano Sud"."""
    match = upsert_listing(db, _raw(portal_id="1", agency="Tecnocasa Milano Sud"))[0]
    upsert_listing(
        db,
        _raw(
            portal="idealista",
            portal_id="2",
            url="https://www.idealista.it/immobile/2/",
            agency="Gabetti",
            latitude=45.99,
            longitude=9.99,
            address="Via Altra, 9",
        ),
    )
    db.commit()
    assert [p.id for p in list_properties(db=db, agency="tecnocasa")] == [match.id]


def test_merged_only_keeps_multi_ad_cards(db):
    """ "Merged only" surfaces the cards the deduplicator folded from more than
    one ad (the same home across portals/agencies)."""
    # same location/price/rooms/surface → the two ads merge into one card
    first = upsert_listing(db, _raw(portal="immobiliare", portal_id="1"))[0]
    merged = upsert_listing(
        db, _raw(portal="idealista", portal_id="2", url="https://www.idealista.it/immobile/2/")
    )[0]
    assert first.id == merged.id  # precondition: they actually merged
    # a lone ad elsewhere: single-listing, must be excluded
    upsert_listing(
        db,
        _raw(
            portal="immobiliare",
            portal_id="3",
            url="https://www.immobiliare.it/annunci/3/",
            latitude=45.10,
            longitude=9.10,
            address="Via Lontana, 1",
        ),
    )
    db.commit()
    assert [p.id for p in list_properties(db=db, merged_only=True)] == [merged.id]


def test_sqm_price_band_filters_on_derived_price_per_sqm(db):
    """€/sqm is price ÷ surface, computed on the fly; a card missing either
    can't be placed on that axis and drops out of the band."""
    cheap = upsert_listing(db, _raw(portal_id="1", price=100_000.0, sqm=100.0))[0]  # 1000 €/sqm
    upsert_listing(
        db,
        _raw(
            portal="idealista",
            portal_id="2",
            url="https://www.idealista.it/immobile/2/",
            price=450_000.0,
            sqm=90.0,  # 5000 €/sqm
            latitude=45.99,
            longitude=9.99,
            address="Via Altra, 9",
        ),
    )
    db.commit()
    assert [p.id for p in list_properties(db=db, max_sqm_price=2000.0)] == [cheap.id]


def test_deal_filter_excludes_unscored_cards(db):
    """The Deal filter reads the Deal Score, which needs a local €/sqm median.
    With too few comparables no score exists, so "undervalued only" — which
    can't confirm a deal — returns nothing rather than a false positive."""
    upsert_listing(db, _raw(portal_id="1"))
    db.commit()
    assert list_properties(db=db, deal="undervalued") == []


# --- Filter by a monitored search (profile overlay) ------------------------


def test_profile_overlay_limits_to_properties_the_search_found(db):
    """Selecting a monitored search narrows the grid to the properties that
    search actually found (its ListingProfile provenance), not everything that
    merely matches its city/contract. An email import no search ever found —
    and a property found only by a *different* search — both drop out."""
    profile = SearchProfile(
        name="Milano vendita",
        portal="immobiliare",
        search_url="https://www.immobiliare.it/vendita-case/milano/",
    )
    other = SearchProfile(
        name="Milano affitto",
        portal="immobiliare",
        search_url="https://www.immobiliare.it/affitto-case/milano/",
    )
    db.add_all([profile, other])
    db.commit()

    # found by our profile
    mine = upsert_listing(db, _raw(portal_id="1"), profile_id=profile.id)[0]
    # found only by a different search (distinct sqm/price/location so the
    # deduplicator keeps it a separate Property)
    theirs = upsert_listing(
        db,
        _raw(
            portal="idealista",
            portal_id="2",
            url="https://www.idealista.it/immobile/2/",
            sqm=55.0,
            price=180_000.0,
            rooms=2,
            latitude=45.50,
            longitude=9.25,
            address="Via Altra, 9",
        ),
        profile_id=other.id,
    )[0]
    # an email import, linked to no search at all (again distinct so it stands
    # on its own)
    imported = upsert_listing(
        db,
        _raw(
            portal_id="3",
            url="https://www.immobiliare.it/annunci/3/",
            sqm=120.0,
            price=450_000.0,
            rooms=4,
            latitude=45.40,
            longitude=9.10,
            address="Via Terza, 3",
        ),
        source="email",
    )[0]
    db.commit()

    out = list_properties(db=db, profile_id=profile.id)
    ids = [p.id for p in out]
    assert mine.id in ids
    assert theirs.id not in ids  # a different search found it, not this one
    assert imported.id not in ids  # no search found it


# --- Bulk endpoint ----------------------------------------------------------


def test_bulk_hide_and_restore(db):
    scan, email = _seed_mixed(db)
    res = bulk_properties(schemas.PropertyBulkIn(ids=[scan.id, email.id], action="hide"), db)
    assert res["processed"] == 2
    db.refresh(scan)
    db.refresh(email)
    assert scan.status == "hidden" and email.status == "hidden"
    assert list_properties(db=db, status="active") == []

    bulk_properties(schemas.PropertyBulkIn(ids=[scan.id], action="restore"), db)
    db.refresh(scan)
    assert scan.status == "active"


def test_restore_clears_gone_at(db):
    """The availability check is fail-open by design (invariant 16), but a
    portal redirect or block it misreads as removal can still mark a live
    listing "gone" (seen for real: a wrongly-"gone" property with a stale
    `gone_at` after being restored). `restore` is the only way back for that
    case, so it must clear `gone_at` too instead of leaving a stale date that
    would corrupt days-on-market stats if the property goes "gone" again
    later (the availability check only sets `gone_at` `if ... is None`)."""
    from datetime import datetime

    scan, _ = _seed_mixed(db)
    scan.status = "gone"
    scan.gone_at = datetime(2020, 1, 1, tzinfo=UTC)
    db.commit()

    restore_property(scan.id, db)
    db.refresh(scan)
    assert scan.status == "active"
    assert scan.gone_at is None


def test_bulk_favorite(db):
    scan, email = _seed_mixed(db)
    bulk_properties(schemas.PropertyBulkIn(ids=[scan.id, email.id], action="favorite"), db)
    db.refresh(scan)
    assert scan.is_favorite is True
    assert len(list_properties(db=db, only_favorites=True)) == 2


def test_bulk_skips_missing_ids(db):
    scan, _ = _seed_mixed(db)
    res = bulk_properties(schemas.PropertyBulkIn(ids=[scan.id, 999999], action="hide"), db)
    assert res["processed"] == 1


def test_newest_sort_survives_mixed_naive_and_aware_timestamps(db):
    """`upsert_listing` stamps timezone-aware datetimes, but SQLite gives them
    back naive — and `SessionLocal` keeps `expire_on_commit=False`, so a session
    can genuinely hold both shapes at once. Sorting them together raised
    "can't compare offset-naive and offset-aware datetimes", taking down the
    whole grid (and the export, which shares this selection)."""
    upsert_listing(db, _raw(portal_id="111"))
    second, _, _ = upsert_listing(
        db,
        # a different building: same-coordinates + same-price would be merged
        # into one card by the deduplicator and the test would prove nothing
        _raw(
            portal_id="222",
            url="https://www.immobiliare.it/annunci/222/",
            address="Via Bergamo, 3",
            latitude=45.5,
            longitude=9.3,
            price=410_000.0,
        ),
    )
    db.commit()
    # force one of the two to be re-read from SQLite: it comes back naive,
    # while the other keeps the aware value it was created with
    db.expire(second)

    props = list_properties(db=db, sort="newest")
    assert len(props) == 2
