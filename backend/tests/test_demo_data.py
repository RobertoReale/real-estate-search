"""Tests for the deterministic demo corpus (services/demo_data.py).

Two things about this generator have to stay true, and neither is visible from
reading its output once. It must produce the *same* corpus every run, or a
browser suite built on it compares today's screen against yesterday's data; and
it must keep covering every case the dashboard can render, or a generator that
quietly stopped producing, say, a property with no coordinates would leave the
map's "without coordinates" banner untested with nothing failing.

Offline and in-memory like the rest of the suite. The one test that spawns a
subprocess is there because the script's contract — seed a directory, refuse a
directory already seeded, exit non-zero when it refuses — is what the browser
harness will depend on, and it cannot be checked from inside the process.
"""

import hashlib
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import Listing, ListingProfile, PriceHistory, Property, SearchProfile, Tag
from app.services import demo_data
from app.services.pricing_stats import annotate_market_position

ROOT = Path(__file__).resolve().parents[2]
SEED_SCRIPT = ROOT / "scripts" / "seed_demo.py"


def _fresh_db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


@pytest.fixture
def db():
    session = _fresh_db()
    yield session
    session.close()


@pytest.fixture
def seeded(db):
    demo_data.seed_demo(db)
    return db


def _count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def _row_counts(db) -> dict[str, int]:
    models = (Property, Listing, PriceHistory, Tag, SearchProfile, ListingProfile)
    return {m.__name__: _count(db, m) for m in models}


def _fingerprint_hash(db) -> str:
    """The acceptance test's own comparison: the property fingerprints, in id
    order, hashed. Cheap, and sensitive to anything that reorders or reshapes
    the corpus."""
    ordered = db.scalars(select(Property.fingerprint).order_by(Property.id)).all()
    return hashlib.sha256("\n".join(ordered).encode()).hexdigest()


def _full_digest(db) -> str:
    """Everything a property carries, timestamps included — only equal across
    two runs when `now` was pinned as well as the seed."""
    rows = db.scalars(select(Property).order_by(Property.id)).all()
    parts = []
    for p in rows:
        parts.append(
            f"{p.fingerprint}|{p.title}|{p.address}|{p.zone}|{p.contract}|{p.status}|"
            f"{p.rooms}|{p.sqm}|{p.floor}|{p.current_min_price}|{p.first_price}|"
            f"{p.latitude}|{p.longitude}|{p.is_favorite}|{p.image_url}|"
            f"{p.first_seen_at}|{p.last_seen_at}|{p.gone_at}|"
            f"{[(l.portal, l.portal_id, l.price, l.agency) for l in p.listings]}|"
            f"{[(h.old_price, h.new_price, h.changed_at) for h in p.price_history]}|"
            f"{sorted(t.name for t in p.tags)}"
        )
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def test_two_runs_produce_the_same_corpus():
    first, second = _fresh_db(), _fresh_db()
    demo_data.seed_demo(first)
    demo_data.seed_demo(second)

    assert _row_counts(first) == _row_counts(second)
    assert _fingerprint_hash(first) == _fingerprint_hash(second)


def test_a_pinned_now_makes_the_two_runs_identical():
    """The seed fixes the content; `now` fixes the timestamps hanging off it."""
    pinned = datetime(2026, 3, 14, 9, 30, tzinfo=UTC)
    first, second = _fresh_db(), _fresh_db()
    demo_data.seed_demo(first, now=pinned)
    demo_data.seed_demo(second, now=pinned)

    assert _full_digest(first) == _full_digest(second)


def test_a_different_seed_produces_a_different_corpus():
    first, second = _fresh_db(), _fresh_db()
    demo_data.seed_demo(first)
    demo_data.seed_demo(second, seed=demo_data.DEFAULT_SEED + 1)

    assert _fingerprint_hash(first) != _fingerprint_hash(second)


@pytest.mark.parametrize(
    "existing",
    [
        Property(fingerprint="milano|3|80", city="Milano"),
        SearchProfile(name="mine", portal="immobiliare", search_url="https://example.test/s"),
        Tag(name="da vedere", name_normalized="da vedere"),
    ],
    ids=["a property", "a search", "a tag"],
)
def test_refuses_a_database_that_holds_anything(db, existing):
    db.add(existing)
    db.commit()

    with pytest.raises(demo_data.DatabaseNotEmpty):
        demo_data.seed_demo(db)


def test_refuses_to_run_twice_over_its_own_output(seeded):
    with pytest.raises(demo_data.DatabaseNotEmpty):
        demo_data.seed_demo(seeded)


def test_the_corpus_covers_every_case_the_dashboard_renders(seeded):
    props = seeded.scalars(select(Property)).all()

    assert len(props) == demo_data.DEFAULT_COUNT
    assert {p.contract for p in props} == {"sale", "rent"}
    assert {p.status for p in props} == {"active", "gone", "hidden"}
    assert len({p.zone for p in props}) == len(demo_data.ZONES)
    assert sum(1 for p in props if len({l.portal for l in p.listings}) == 2) > 0
    assert sum(1 for p in props if p.price_history) > 0
    assert sum(1 for p in props if p.is_favorite) > 0
    assert sum(1 for p in props if p.tags) > 0
    assert sum(1 for p in props if not p.image_url) > 0
    assert sum(1 for p in props if p.latitude is None) > 0
    # ...and the complement of each optional case, or "some" would be "all"
    assert sum(1 for p in props if p.image_url) > 0
    assert sum(1 for p in props if p.latitude is not None) > 0


def test_a_small_corpus_still_covers_every_case(db):
    """The shares are rounded up to at least one, so a caller asking for a
    handful of properties gets a sample of each case rather than whichever ones
    survived the rounding."""
    demo_data.seed_demo(db, count=12)
    props = db.scalars(select(Property)).all()

    assert len(props) == 12
    assert {p.contract for p in props} == {"sale", "rent"}
    assert {p.status for p in props} == {"active", "gone", "hidden"}
    assert sum(1 for p in props if p.price_history) > 0
    assert sum(1 for p in props if not p.image_url) > 0


def test_the_three_searches_are_in_three_health_states(seeded):
    profiles = {p.name: p for p in seeded.scalars(select(SearchProfile)).all()}
    assert len(profiles) == 3

    healthy = [p for p in profiles.values() if p.is_active and p.consecutive_failures == 0]
    blocked = [p for p in profiles.values() if p.is_active and p.consecutive_failures > 0]
    inactive = [p for p in profiles.values() if not p.is_active]

    assert len(healthy) == 1 and healthy[0].last_run_status == "ok"
    assert len(blocked) == 1 and blocked[0].last_run_status == "blocked"
    # a streak the user has already been told about, or the alert would fire
    # again on the demo corpus' first scan (invariant 11)
    assert blocked[0].health_alert_sent
    assert len(inactive) == 1
    # every search has already had its silent first scan: a demo corpus that
    # arrived with baseline_done unset would notify on all eighty properties
    # the first time anyone pressed Scan now (invariant 3)
    assert all(p.baseline_done for p in profiles.values())


def test_every_listing_says_which_search_found_it(seeded):
    listings = seeded.scalars(select(Listing)).all()

    assert listings
    assert all(l.profile_links for l in listings)


def test_price_history_lands_on_the_current_price(seeded):
    """A chain whose last new_price disagreed with current_min_price would be a
    state no scan can produce — and the card would show two prices for one
    property."""
    for prop in seeded.scalars(select(Property)).all():
        if not prop.price_history:
            assert prop.first_price == prop.current_min_price
            continue
        chain = prop.price_history
        assert chain[-1].new_price == prop.current_min_price
        assert prop.first_price == chain[0].old_price
        for earlier, later in zip(chain, chain[1:], strict=False):
            assert earlier.new_price == later.old_price
            assert later.new_price < later.old_price
        assert all(h.changed_at >= prop.first_seen_at for h in chain)


def test_the_cheapest_listing_is_the_property_price(seeded):
    """What `deduplicator._refresh_min_price` guarantees, which is what makes a
    merged pair meaningful: the dashboard shows the lower of the two asks."""
    for prop in seeded.scalars(select(Property)).all():
        assert prop.current_min_price == min(l.price for l in prop.listings)


def test_gone_properties_are_dated_at_their_last_sighting(seeded):
    """`scanner._mark_vanished_properties` dates a disappearance at the last
    sighting, not at the day it noticed; market velocity reads the difference."""
    for prop in seeded.scalars(select(Property)).all():
        if prop.status == "gone":
            assert prop.gone_at == prop.last_seen_at
            assert prop.gone_at > prop.first_seen_at
        else:
            assert prop.gone_at is None


def test_tags_carry_a_normalized_name(seeded):
    """The trap the ad-hoc scripts kept falling into: `name_normalized` is what
    the tag filter matches on, so a tag written without one is invisible."""
    tags = seeded.scalars(select(Tag)).all()

    assert tags
    for tag in tags:
        assert tag.name_normalized == tag.name.strip().lower()
    assert len({t.name_normalized for t in tags}) == len(tags)


def test_nothing_in_the_corpus_points_at_the_network(seeded):
    """The corpus has to render with the network unplugged: `.invalid` is
    reserved never to resolve, and the photos travel inside the row."""
    for listing in seeded.scalars(select(Listing)).all():
        assert listing.url.startswith(f"https://{demo_data.DEMO_HOST}/")
    for profile in seeded.scalars(select(SearchProfile)).all():
        assert profile.search_url.startswith(f"https://{demo_data.DEMO_HOST}/")
    for prop in seeded.scalars(select(Property)).all():
        assert prop.image_url == "" or prop.image_url.startswith("data:image/svg+xml;base64,")


def test_the_corpus_is_dense_enough_to_produce_market_positions(seeded):
    """Realism, measured rather than asserted by eye: the €/m² medians need at
    least three comparables per area (`pricing_stats.MIN_SAMPLE`), so a corpus
    spread too thin would render every card without its market badge."""
    props = seeded.scalars(select(Property).where(Property.status == "active")).all()
    annotate_market_position(seeded, props)

    positioned = [p for p in props if p.sqm_price_delta_pct is not None]
    assert len(positioned) == len(props)
    # and the spread is wide enough for the badge to say something in both
    # directions, not eighty cards all reading "in line with the area"
    assert min(p.sqm_price_delta_pct for p in positioned) < -10
    assert max(p.sqm_price_delta_pct for p in positioned) > 10


def test_the_script_seeds_a_directory_and_then_refuses_it(tmp_path):
    """The acceptance test of `scripts/seed_demo.py`, run the way it ships."""

    def run(data_dir: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SEED_SCRIPT), "--data-dir", str(data_dir), "--count", "12"],
            capture_output=True,
            text=True,
        )

    first, second = tmp_path / "one", tmp_path / "two"
    assert run(first).returncode == 0
    assert run(second).returncode == 0

    engines = [create_engine(f"sqlite:///{d / 'case.db'}") for d in (first, second)]
    sessions = [sessionmaker(bind=e)() for e in engines]
    try:
        assert _row_counts(sessions[0]) == _row_counts(sessions[1])
        assert _fingerprint_hash(sessions[0]) == _fingerprint_hash(sessions[1])
    finally:
        for session, engine in zip(sessions, engines, strict=True):
            session.close()
            engine.dispose()

    refused = run(first)
    assert refused.returncode != 0
    assert "empty" in refused.stdout
