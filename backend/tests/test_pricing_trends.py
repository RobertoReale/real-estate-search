"""Historical price trends: the daily snapshot table and the series it feeds.

pricing_stats computes medians instantaneously; nothing remembered what the
median was last week until PricingSnapshot. These tests pin the once-per-day
capture, its idempotence, and the shape of the series the chart consumes.
"""
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import PricingSnapshot, Property
from app.services.pricing_stats import (
    capture_snapshots, get_trends, list_trend_areas, maybe_snapshot,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def _prop(price, sqm, city="milano", zone="isola", contract="sale",
          status="active") -> Property:
    return Property(fingerprint="f", city=city, zone=zone, contract=contract,
                    current_min_price=price, sqm=sqm, status=status)


def _three_comparables(db, **kw):
    # three listings so the median clears MIN_SAMPLE (3)
    for price in (300_000, 320_000, 340_000):
        db.add(_prop(price, 100, **kw))
    db.commit()


def test_capture_writes_city_and_zone_rows(db):
    _three_comparables(db)
    written = capture_snapshots(db, today=date(2026, 7, 1))
    # one whole-city aggregate (zone="") plus one zone row, same three samples
    assert written == 2
    rows = db.scalars(select(PricingSnapshot)).all()
    scopes = {(r.city, r.zone) for r in rows}
    assert scopes == {("milano", ""), ("milano", "isola")}
    assert all(r.median_sqm_price == 3200.0 and r.sample_count == 3
               for r in rows)


def test_capture_is_idempotent_per_day(db):
    """The instantaneous median drifts as scans add listings; one reading per
    day is all a trend needs, so a second capture the same day is a no-op."""
    _three_comparables(db)
    assert capture_snapshots(db, today=date(2026, 7, 1)) == 2
    assert capture_snapshots(db, today=date(2026, 7, 1)) == 0
    assert len(db.scalars(select(PricingSnapshot)).all()) == 2


def test_too_few_comparables_are_not_snapshotted(db):
    """Two listings are not a median: below MIN_SAMPLE nothing is captured,
    the same honesty rule pricing_stats applies to the live badge."""
    db.add(_prop(300_000, 100))
    db.add(_prop(320_000, 100))
    db.commit()
    assert capture_snapshots(db, today=date(2026, 7, 1)) == 0


def test_get_trends_returns_ordered_series(db):
    _three_comparables(db)
    capture_snapshots(db, today=date(2026, 7, 1))
    # prices rise the next day -> higher median
    for price in (360_000, 380_000, 400_000):
        db.add(_prop(price, 100))
    db.commit()
    capture_snapshots(db, today=date(2026, 7, 3))

    series = get_trends(db, city="Milano", zone="Isola", contract="sale")
    dates = [p["captured_on"] for p in series["points"]]
    assert dates == [date(2026, 7, 1), date(2026, 7, 3)]  # oldest first
    assert series["points"][1]["median_sqm_price"] > \
        series["points"][0]["median_sqm_price"]


def test_get_trends_city_aggregate_uses_empty_zone(db):
    _three_comparables(db)
    capture_snapshots(db, today=date(2026, 7, 1))
    # empty zone asks for the whole-city aggregate
    series = get_trends(db, city="milano", zone="", contract="sale")
    assert len(series["points"]) == 1
    assert series["zone"] == ""


def test_list_trend_areas_needs_at_least_two_points(db):
    _three_comparables(db)
    capture_snapshots(db, today=date(2026, 7, 1))
    # only one point so far -> nothing chartable yet
    assert list_trend_areas(db, "sale") == []

    capture_snapshots(db, today=date(2026, 7, 2))
    areas = list_trend_areas(db, "sale")
    keys = {(a["city"], a["zone"]) for a in areas}
    assert keys == {("milano", ""), ("milano", "isola")}
    # whole-city aggregate sorts before its zones
    assert areas[0]["zone"] == ""


def test_maybe_snapshot_is_fail_open(db, monkeypatch):
    """A snapshot is a nice-to-have; a failure must not bubble into the scan or
    the scheduler that call it."""
    import app.services.pricing_stats as ps

    def _boom(*a, **k):
        raise RuntimeError("median math exploded")

    monkeypatch.setattr(ps, "compute_sqm_price_medians", _boom)
    assert maybe_snapshot(db) == 0  # swallowed, not raised
