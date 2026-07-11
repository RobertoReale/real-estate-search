"""Deal Score (services/deal_score.py).

The score folds three signals into one number; each test isolates one so a
later tweak to the weights trips a specific expectation. Scoring is pure over
transient attributes, so most tests need no DB — the last one exercises the
agency-signature lookup, which does.
"""
from datetime import timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Listing, Property
from app.services import deal_score
from app.services.deal_score import (
    _score_property, _target_range, annotate_deal_scores,
)
from app.services.notifier import _deal_line


def _prop(delta=None, scope="zone", descriptions=None, agency="",
          contract="sale", price=300_000, sqm=100.0,
          area_median=None) -> Property:
    p = Property(fingerprint="f", title="", city="milano", zone="isola",
                 contract=contract, current_min_price=price, sqm=sqm,
                 status="active")
    p.sqm_price_delta_pct = delta
    p.area_median_scope = scope
    p.area_median_sqm_price = area_median
    p.listings = [Listing(portal="immobiliare", portal_id=str(i), url="u",
                          agency=agency, description=d)
                  for i, d in enumerate(descriptions or [""])]
    return p


def _score(**kw) -> Property:
    p = _prop(**kw)
    _score_property(p, {})
    return p


def test_below_market_is_undervalued():
    p = _score(delta=-16)
    assert p.deal_score == 16
    assert p.deal_label == "undervalued"
    assert any("below zone median" in r for r in p.deal_reasons or [])


def test_above_market_is_overpriced():
    p = _score(delta=20)
    assert p.deal_score == -20
    assert p.deal_label == "overpriced"


def test_needs_renovation_cancels_a_discount():
    """A 16%-below-median flat that reads "da ristrutturare" is not really a
    deal: the discount is the cost of the works. −15 pulls +16 down to +1."""
    p = _score(delta=-16, descriptions=["Ampio trilocale da ristrutturare"])
    assert p.deal_score == 1
    assert p.deal_label == "fair"
    assert any("needs renovation" in r for r in p.deal_reasons or [])


def test_renovated_lifts_a_fairly_priced_listing():
    """At the area median (delta 0) a renovated flat is actually a good buy:
    +10 makes it undervalued."""
    p = _score(delta=0, descriptions=["Appartamento completamente ristrutturato"])
    assert p.deal_score == 10
    assert p.deal_label == "undervalued"


def test_condition_cues_respect_word_boundaries():
    """"da ristrutturare" must not fire on "ristrutturato": they are opposite
    signals. The filter engine's boundary matching keeps them apart."""
    p = _score(delta=0, descriptions=["Casa ristrutturata di recente"])
    # only the positive cue counts
    assert p.deal_score == 10


def test_no_median_means_no_score():
    """Without a local median there is no fair-value anchor: the badge must not
    appear rather than invent a number."""
    p = _score(delta=None)
    assert p.deal_score is None
    assert p.deal_label is None
    assert p.target_price_low is None


def test_score_is_clamped():
    assert _score(delta=-80).deal_score == 50
    assert _score(delta=80).deal_score == -50


def test_target_range_from_area_median():
    """A sale priced above the fair value implied by the area median yields a
    proposal band below asking, rounded to €1,000."""
    p = _prop(price=300_000, sqm=100.0, area_median=2800.0)  # fair = 280k
    low, high = _target_range(p, expected_discount=None)
    assert (low, high) == (272_000, 280_000)


def test_target_range_prefers_the_lower_of_fair_value_and_agency_discount():
    p = _prop(price=300_000, sqm=100.0, area_median=2900.0)  # fair = 290k
    # agency historically cuts 10% -> 270k, lower than fair value
    low, high = _target_range(p, expected_discount=10.0)
    assert low is not None and high is not None
    assert high == 270_000
    assert low < high < 300_000


def test_no_target_when_priced_at_or_below_value():
    p = _prop(price=280_000, sqm=100.0, area_median=3000.0)  # fair 300k > asking
    assert _target_range(p, expected_discount=None) == (None, None)


def test_rent_has_no_proposal_target():
    p = _prop(contract="rent", price=1500, sqm=60.0, area_median=30.0)
    assert _target_range(p, expected_discount=5.0) == (None, None)


# --- notifier integration ----------------------------------------------------

def test_deal_line_only_fires_for_undervalued():
    under = _score(delta=-16)
    assert "Below market" in _deal_line(under)

    fair = _score(delta=2)
    assert _deal_line(fair) == ""

    # a property the scan never annotated (no attribute set) is silent
    bare = Property(fingerprint="f", contract="sale")
    bare.listings = []
    assert _deal_line(bare) == ""


# --- agency signature lookup (needs a DB) ------------------------------------

@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def test_annotate_pulls_the_agency_expected_discount(db):
    """Three of the agency's listings dropped their price, so its median
    discount is known and feeds both a reason line and the proposal target —
    while the score itself stays driven by the €/sqm position."""
    for i in range(3):
        p = Property(fingerprint=f"f{i}", city="milano", zone="isola",
                     contract="sale", first_price=340_000,
                     current_min_price=300_000, sqm=100.0, status="active")
        p.listings = [Listing(portal="immobiliare", portal_id=str(i), url="u",
                              agency="Studio Rossi")]
        db.add(p)
    db.commit()

    target = db.query(Property).first()
    # pretend market position already ran
    target.sqm_price_delta_pct = -16.0
    target.area_median_scope = "zone"
    target.area_median_sqm_price = 2900.0

    annotate_deal_scores(db, [target])

    assert target.deal_score == 16  # agency behaviour does not move the score
    assert target.expected_discount_pct is not None
    assert any("agency typically cuts" in r for r in target.deal_reasons or [])
    # a proposal band exists and sits below the asking price
    low, high = target.target_price_low, target.target_price_high
    assert low is not None and high is not None
    assert low < high <= 300_000
