"""Tests for market velocity signals (services/market_velocity.py):
days-on-market, sell-through per neighborhood, and agency pricing behavior.

Every date here is built relative to "now" so the suite stays deterministic
regardless of when it runs.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Listing, Property
from app.services.market_velocity import (
    MIN_SAMPLE, _days_on_market, compute_market_velocity,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


NOW = datetime.now(timezone.utc)


def _days_ago(n: float) -> datetime:
    return NOW - timedelta(days=n)


def _prop(db, *, city="Milano", zone="Navigli", contract="sale",
          status="active", first_seen_days_ago=30.0, gone_days_ago=None,
          first_price=300_000.0, price=300_000.0, sqm=100.0, agency="",
          **kwargs) -> Property:
    prop = Property(
        fingerprint=f"fp-{city}-{zone}-{db.query(Property).count()}",
        city=city, zone=zone, contract=contract, status=status,
        first_price=first_price, current_min_price=price, sqm=sqm,
        first_seen_at=_days_ago(first_seen_days_ago),
        last_seen_at=_days_ago(gone_days_ago) if gone_days_ago else NOW,
        gone_at=_days_ago(gone_days_ago) if gone_days_ago else None,
        **kwargs,
    )
    db.add(prop)
    db.flush()
    if agency:
        db.add(Listing(property_id=prop.id, portal="immobiliare",
                       portal_id=str(prop.id), url="http://x", price=price,
                       agency=agency))
    db.flush()
    return prop


# --- Days on market ----------------------------------------------------------

def test_days_on_market_of_a_gone_property_ends_at_gone_at():
    prop = Property(first_seen_at=_days_ago(50), last_seen_at=_days_ago(20),
                    gone_at=_days_ago(20), status="gone")
    assert _days_on_market(prop, NOW) == pytest.approx(30, abs=0.01)


def test_days_on_market_of_a_live_property_runs_until_now():
    prop = Property(first_seen_at=_days_ago(40), last_seen_at=NOW,
                    status="active")
    assert _days_on_market(prop, NOW) == pytest.approx(40, abs=0.01)


def test_legacy_gone_rows_without_gone_at_fall_back_to_last_seen():
    """`gone_at` was added after the first releases: properties marked gone
    before the migration have it NULL, and dating them "now" would inflate
    every median. last_seen_at is the honest proxy."""
    prop = Property(first_seen_at=_days_ago(60), last_seen_at=_days_ago(25),
                    gone_at=None, status="gone")
    assert _days_on_market(prop, NOW) == pytest.approx(35, abs=0.01)


def test_days_on_market_of_a_sold_property_ends_at_sold_at():
    """A user-confirmed sale is a precise, real close date — stronger than the
    inferred "gone" heuristic — so the window ends at sold_at, and sold_at wins
    even if gone_at is also present."""
    prop = Property(first_seen_at=_days_ago(45), last_seen_at=_days_ago(3),
                    sold_at=_days_ago(15), gone_at=_days_ago(3), status="sold")
    assert _days_on_market(prop, NOW) == pytest.approx(30, abs=0.01)


def test_days_on_market_is_never_negative():
    prop = Property(first_seen_at=_days_ago(5), last_seen_at=_days_ago(10),
                    gone_at=_days_ago(10), status="gone")
    assert _days_on_market(prop, NOW) == 0.0


# --- Area velocity -----------------------------------------------------------

def test_zone_median_days_and_sell_through(db):
    # three sold in 10/20/30 days, three still listed for 40 days
    for days in (10, 20, 30):
        _prop(db, status="gone", first_seen_days_ago=days + 5,
              gone_days_ago=5)
    for _ in range(3):
        _prop(db, status="active", first_seen_days_ago=40)

    result = compute_market_velocity(db, contract="sale")
    zone = next(r for r in result["areas"] if r["scope"] == "zone")
    assert zone["sample"] == 6 and zone["closed"] == 3
    assert zone["median_days_to_gone"] == pytest.approx(20, abs=0.1)
    assert zone["median_days_listed"] == pytest.approx(40, abs=0.1)
    assert zone["sell_through_pct"] == 50.0


def test_area_below_minimum_sample_is_not_reported(db):
    """Same rule as pricing_stats: a median of two listings is noise wearing
    the costume of a statistic."""
    for _ in range(MIN_SAMPLE - 1):
        _prop(db, zone="Isola")
    assert compute_market_velocity(db, contract="sale")["areas"] == []


def test_median_days_needs_enough_closed_listings(db):
    """A zone with plenty of listings but only one sale must still report its
    sell-through rate — just not a median days-on-market."""
    _prop(db, status="gone", first_seen_days_ago=20, gone_days_ago=1)
    for _ in range(4):
        _prop(db, status="active")

    zone = next(r for r in compute_market_velocity(db, contract="sale")["areas"]
                if r["scope"] == "zone")
    assert zone["median_days_to_gone"] is None
    assert zone["sell_through_pct"] == 20.0


def test_city_row_aggregates_its_zones(db):
    for _ in range(MIN_SAMPLE):
        _prop(db, zone="Navigli")
    for _ in range(MIN_SAMPLE):
        _prop(db, zone="Isola")

    areas = compute_market_velocity(db, contract="sale")["areas"]
    city_row = next(r for r in areas if r["scope"] == "city")
    assert city_row["sample"] == 6
    assert {r["zone"] for r in areas if r["scope"] == "zone"} == {"Navigli", "Isola"}


def test_areas_are_sorted_fastest_moving_first(db):
    for days in (5, 6, 7):        # fast zone
        _prop(db, zone="Fast", status="gone",
              first_seen_days_ago=days + 1, gone_days_ago=1)
    for days in (90, 100, 110):   # slow zone
        _prop(db, zone="Slow", status="gone",
              first_seen_days_ago=days + 1, gone_days_ago=1)

    zones = [r for r in compute_market_velocity(db, contract="sale")["areas"]
             if r["scope"] == "zone"]
    assert [z["zone"] for z in zones] == ["Fast", "Slow"]


def test_rent_and_sale_velocity_are_separate(db):
    """Rentals turn over in days, sales in months: mixing them would make
    both numbers meaningless (same reasoning as invariant #9)."""
    for _ in range(MIN_SAMPLE):
        _prop(db, contract="rent", price=1200.0, first_price=1200.0)
    for _ in range(MIN_SAMPLE):
        _prop(db, contract="sale")

    assert compute_market_velocity(db, contract="rent")["total_properties"] == 3
    assert compute_market_velocity(db, contract="sale")["total_properties"] == 3


def test_hidden_properties_are_excluded_but_filtered_ones_count(db):
    """A property the user hid left *their* market, not the market. A
    keyword-filtered ground floor flat is still a real data point."""
    for _ in range(MIN_SAMPLE):
        _prop(db, status="filtered")
    _prop(db, status="hidden")

    result = compute_market_velocity(db, contract="sale")
    assert result["total_properties"] == MIN_SAMPLE


def test_sold_counts_as_a_confirmed_close(db):
    """"sold" is the confirmed-sale datapoint "gone" only infers: it joins the
    closed set (feeding sell-through and days-to-gone) and is also broken out
    on its own so the UI can distinguish a real sale from a mere market exit."""
    # three confirmed sold (10/20/30 days on market), one inferred-gone, two live
    for days in (10, 20, 30):
        _prop(db, status="sold", first_seen_days_ago=days + 5,
              sold_at=_days_ago(5))
    _prop(db, status="gone", first_seen_days_ago=35, gone_days_ago=5)
    for _ in range(2):
        _prop(db, status="active", first_seen_days_ago=40)

    result = compute_market_velocity(db, contract="sale")
    assert result["sold_properties"] == 3
    assert result["closed_properties"] == 4          # 3 sold + 1 gone
    zone = next(r for r in result["areas"] if r["scope"] == "zone")
    assert zone["closed"] == 4 and zone["sold"] == 3
    # 4 of 6 left the market; the confirmed-sold subset alone medians at 20 days
    assert zone["sell_through_pct"] == pytest.approx(66.7, abs=0.1)
    assert zone["median_days_to_sold"] == pytest.approx(20, abs=0.1)


def test_city_filter_narrows_the_sample(db):
    for _ in range(MIN_SAMPLE):
        _prop(db, city="Milano")
    for _ in range(MIN_SAMPLE):
        _prop(db, city="Roma")

    result = compute_market_velocity(db, contract="sale", city="mila")
    assert result["total_properties"] == MIN_SAMPLE
    assert all(r["city"] == "Milano" for r in result["areas"])


# --- Agency behavior ---------------------------------------------------------

def test_agency_price_drop_share_and_median_discount(db):
    # three listings, two of which dropped 10% and 20%
    _prop(db, agency="Acme", first_price=300_000.0, price=270_000.0)
    _prop(db, agency="Acme", first_price=300_000.0, price=240_000.0)
    _prop(db, agency="Acme", first_price=300_000.0, price=300_000.0)

    agency = compute_market_velocity(db, contract="sale")["agencies"][0]
    assert agency["agency"] == "Acme"
    assert agency["sample"] == 3
    assert agency["price_drop_pct"] == pytest.approx(66.7, abs=0.1)
    # median of the *dropped* ones only: averaging in the unchanged listing
    # would report a discount nobody ever offered. Only 2 samples < MIN_SAMPLE
    assert agency["median_drop_pct"] is None


def test_agency_median_discount_needs_min_sample_of_drops(db):
    for price in (270_000.0, 240_000.0, 285_000.0):
        _prop(db, agency="Acme", first_price=300_000.0, price=price)

    agency = compute_market_velocity(db, contract="sale")["agencies"][0]
    assert agency["price_drop_pct"] == 100.0
    assert agency["median_drop_pct"] == pytest.approx(10.0, abs=0.1)


def test_agency_overpricing_measured_against_the_local_median(db):
    """"Which agencies list overpriced" = median €/sqm delta vs the zone
    median. Cheap sets the baseline; Pricey must come out above it."""
    for _ in range(3):
        _prop(db, agency="Cheap", price=200_000.0, first_price=200_000.0,
              sqm=100.0)                       # 2,000 €/sqm
    for _ in range(3):
        _prop(db, agency="Pricey", price=300_000.0, first_price=300_000.0,
              sqm=100.0)                       # 3,000 €/sqm

    agencies = {a["agency"]: a for a in
                compute_market_velocity(db, contract="sale")["agencies"]}
    # zone median is 2,500 €/sqm: -20% vs +20%
    assert agencies["Cheap"]["median_sqm_price_delta_pct"] == pytest.approx(-20, abs=0.1)
    assert agencies["Pricey"]["median_sqm_price_delta_pct"] == pytest.approx(20, abs=0.1)


def test_agency_below_minimum_sample_is_not_judged(db):
    for _ in range(MIN_SAMPLE - 1):
        _prop(db, agency="Tiny")
    assert compute_market_velocity(db, contract="sale")["agencies"] == []


def test_a_property_merged_across_portals_counts_once_per_agency(db):
    """Dedup can attach several listings to one Property. Each agency answers
    for the price it published, but only once — otherwise an agency that
    cross-posts inflates its own sample."""
    prop = _prop(db, agency="Acme")
    db.add(Listing(property_id=prop.id, portal="idealista", portal_id="dup",
                   url="http://y", price=300_000.0, agency="Acme"))
    for _ in range(MIN_SAMPLE - 1):
        _prop(db, agency="Acme")
    db.flush()

    agency = compute_market_velocity(db, contract="sale")["agencies"][0]
    assert agency["sample"] == MIN_SAMPLE


def test_tracking_since_reports_the_observation_window(db):
    """days-on-market cannot predate the first scan: the UI says so rather
    than presenting truncated ages as market truth."""
    _prop(db, first_seen_days_ago=100)
    _prop(db, first_seen_days_ago=10)

    result = compute_market_velocity(db, contract="sale")
    assert (NOW - result["tracking_since"]).days == 100


def test_empty_database_returns_an_empty_payload(db):
    result = compute_market_velocity(db, contract="sale")
    assert result["total_properties"] == 0
    assert result["areas"] == [] and result["agencies"] == []
    assert result["tracking_since"] is None


def test_agency_samples_merge_across_casing(db):
    """Regression: agency names were raw dict keys, so "Acme Srl" on one
    portal and "ACME SRL" on the other split the sample below MIN_SAMPLE and
    the agency vanished from the behaviour table."""
    _prop(db, agency="Acme Srl", first_price=300_000.0, price=270_000.0)
    _prop(db, agency="ACME SRL", first_price=300_000.0, price=240_000.0)
    _prop(db, agency="acme srl", first_price=300_000.0, price=300_000.0)
    db.commit()

    out = compute_market_velocity(db, contract="sale")
    agencies = {r["agency"]: r for r in out["agencies"]}
    assert len(agencies) == 1
    row = next(iter(agencies.values()))
    assert row["sample"] == 3
