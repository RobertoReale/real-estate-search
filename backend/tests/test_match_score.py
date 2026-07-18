"""Smart Match Score (services/match_score.py).

Pure, offline weighted scoring: each test builds a transient Property (no DB
needed) and checks one criterion in isolation, then a couple of combinations.
The "why" comments pin the deliberate design choices — missing data scores 0,
floor is dropped when unparseable, numeric wishes degrade linearly — so a later
change that "simplifies" them trips a test instead of silently changing scores.
"""

from app.models import Listing, Property
from app.services.match_score import annotate_match_scores, compute_match


def _prop(descriptions: list[str] | None = None, **kwargs) -> Property:
    base = dict(
        title="",
        city="",
        zone="",
        address="",
        floor="",
        rooms=None,
        sqm=None,
        current_min_price=None,
    )
    base.update(kwargs)
    p = Property(**base)
    p.listings = [
        Listing(portal="immobiliare", portal_id=str(i), url="u", description=d)
        for i, d in enumerate(descriptions or [])
    ]
    return p


def _prefs(**kwargs) -> dict:
    base = dict(
        enabled=True,
        max_price=None,
        min_rooms=None,
        min_sqm=None,
        min_floor=None,
        keywords=[],
        zones=[],
    )
    base.update(kwargs)
    return base


def test_disabled_scores_none():
    assert compute_match(_prop(current_min_price=100), _prefs(enabled=False, max_price=200)) is None


def test_no_configured_criteria_scores_none():
    """Enabled but nothing to score against: the badge must not appear rather
    than show a meaningless 100%."""
    assert compute_match(_prop(current_min_price=100), _prefs()) is None


def test_within_budget_is_full_score():
    assert compute_match(_prop(current_min_price=300_000), _prefs(max_price=350_000)) == 100


def test_over_budget_decays_linearly():
    """A €385k flat against a €350k budget is 'almost', not 'no': 10% over
    budget scores 90, and twice the budget reaches 0."""
    assert compute_match(_prop(current_min_price=385_000), _prefs(max_price=350_000)) == 90
    assert compute_match(_prop(current_min_price=700_000), _prefs(max_price=350_000)) == 0


def test_missing_price_scores_zero_against_budget():
    """A listing with no price cannot be shown to fit a budget, so it scores 0
    — not skipped, which would have let it inherit a perfect score."""
    assert compute_match(_prop(current_min_price=None), _prefs(max_price=350_000)) == 0


def test_rooms_below_wish_is_partial():
    assert compute_match(_prop(rooms=2), _prefs(min_rooms=3)) == 67
    assert compute_match(_prop(rooms=3), _prefs(min_rooms=3)) == 100
    assert compute_match(_prop(rooms=5), _prefs(min_rooms=3)) == 100


def test_sqm_below_wish_is_partial():
    assert compute_match(_prop(sqm=60), _prefs(min_sqm=80)) == 75


def test_floor_meets_or_misses_wish():
    assert compute_match(_prop(floor="3"), _prefs(min_floor=2)) == 100
    assert compute_match(_prop(floor="1"), _prefs(min_floor=2)) == 0
    # ground floor / mezzanine read as 0
    assert compute_match(_prop(floor="piano terra"), _prefs(min_floor=2)) == 0


def test_unparseable_floor_is_dropped_not_zeroed():
    """Floor is free text and unreadable more often than not. If the only
    configured wish is floor and it can't be parsed, there is nothing to score,
    so the result is None — not a misleading 0 that would rank the flat last."""
    assert compute_match(_prop(floor=""), _prefs(min_floor=2)) is None
    # and when combined with another wish it simply does not drag the average
    assert compute_match(_prop(floor="", rooms=3), _prefs(min_floor=2, min_rooms=3)) == 100


def test_keyword_fraction_over_title_and_descriptions():
    """Desired features are matched on word boundaries (reusing the filter
    engine) across title + address + zone + every listing description."""
    prop = _prop(title="Trilocale con balcone", descriptions=["Luminoso, con ascensore e cantina"])
    # 2 of 3 desired features present -> 67
    assert compute_match(prop, _prefs(keywords=["balcone", "ascensore", "terrazzo"])) == 67


def test_keyword_matching_respects_word_boundaries():
    """ "asta" must not match inside "vasta": the whole point of the filter
    engine's boundary matching, reused here."""
    prop = _prop(title="Vasta metratura")
    assert compute_match(prop, _prefs(keywords=["asta"])) == 0


def test_zone_preference_matches_city_or_zone():
    assert compute_match(_prop(city="Milano", zone="Isola"), _prefs(zones=["isola"])) == 100
    assert compute_match(_prop(city="Milano", zone="Navigli"), _prefs(zones=["isola"])) == 0


def test_combined_criteria_are_averaged():
    """Budget met (1.0) + rooms 2-of-3 (0.667) -> average 0.833 -> 83."""
    prop = _prop(current_min_price=300_000, rooms=2)
    assert compute_match(prop, _prefs(max_price=350_000, min_rooms=3)) == 83


def test_annotate_sets_match_score_from_settings():
    props = [_prop(current_min_price=300_000)]
    annotate_match_scores(props, {"match_score_enabled": True, "dream_max_price": 350_000})
    assert props[0].match_score == 100


def test_annotate_none_when_settings_disabled():
    props = [_prop(current_min_price=300_000)]
    annotate_match_scores(props, {"match_score_enabled": False, "dream_max_price": 350_000})
    assert props[0].match_score is None


def test_zone_matches_on_word_boundaries_not_substrings():
    """Regression: `_zone_match` was the one containment test left in the
    codebase — a preferred zone "Isola" silently matched "Isolabella" and
    "Isolotto" addresses, inflating the score."""
    prefs = _prefs(zones=["Isola"])
    assert compute_match(_prop(zone="Isola"), prefs) == 100
    assert compute_match(_prop(address="Via Isolabella 3"), prefs) == 0
    assert compute_match(_prop(zone="Isolotto"), prefs) == 0
