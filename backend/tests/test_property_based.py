"""Property-based tests (hypothesis) for the pure, mathematical helpers.

The rest of the suite pins *specific* real-portal cases that once broke; this
file complements them by asserting the *laws* those helpers must obey for every
input hypothesis can invent — the class of edge case that is cheaper to generate
than to enumerate by hand. Kept deliberately to functions with no I/O and a
clear contract: the dedup tolerance gate, the haversine distance, the price/sqm
parsers and the floor reader.
"""

import math

from hypothesis import given
from hypothesis import strategies as st

from app.scrapers.base import (
    MAX_PRICE,
    MAX_RENT,
    MIN_PRICE,
    MIN_RENT,
    parse_price,
    parse_sqm,
)
from app.services.deduplicator import _haversine_m, _within
from app.services.match_score import _parse_floor

# Real-world-plausible finite coordinates; excludes NaN/inf so the geometry laws
# below are about the maths, not float pathologies the callers never pass.
_lat = st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False)
_lon = st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False)
_pos = st.floats(min_value=1.0, max_value=1e9, allow_nan=False, allow_infinity=False)
_tol = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


# --- _within: the ±tolerance gate at the heart of conservative dedup (inv. 1) ---


@given(_pos, _tol)
def test_within_is_reflexive(x, tol):
    # a value is always within any non-negative tolerance of itself
    assert _within(x, x, tol) is True


@given(_pos, _pos, _tol)
def test_within_is_symmetric(a, b, tol):
    assert _within(a, b, tol) == _within(b, a, tol)


@given(_pos, _pos, _tol)
def test_within_matches_the_relative_difference(a, b, tol):
    # the gate is exactly "relative difference <= tolerance", nothing looser
    expected = abs(a - b) / max(a, b) <= tol
    assert _within(a, b, tol) is expected


@given(_pos, _tol)
def test_within_rejects_missing_values(x, tol):
    # None/0 are "unknown": never proof of a match, either way round
    assert _within(None, x, tol) is False
    assert _within(x, None, tol) is False
    assert _within(0, x, tol) is False


# --- _haversine_m: great-circle distance in metres ---

_EARTH_HALF_CIRCUMFERENCE_M = math.pi * 6_371_000  # antipodal upper bound


@given(_lat, _lon, _lat, _lon)
def test_haversine_is_nonnegative_and_bounded(lat1, lon1, lat2, lon2):
    d = _haversine_m(lat1, lon1, lat2, lon2)
    assert d >= 0.0
    # no two points on Earth are farther apart than the antipode (+1 m slack)
    assert d <= _EARTH_HALF_CIRCUMFERENCE_M + 1.0


@given(_lat, _lon)
def test_haversine_identity_is_zero(lat, lon):
    assert _haversine_m(lat, lon, lat, lon) == 0.0


@given(_lat, _lon, _lat, _lon)
def test_haversine_is_symmetric(lat1, lon1, lat2, lon2):
    there = _haversine_m(lat1, lon1, lat2, lon2)
    back = _haversine_m(lat2, lon2, lat1, lon1)
    assert math.isclose(there, back, rel_tol=1e-9, abs_tol=1e-6)


# --- parse_price / parse_sqm: never crash, always in range, round-trip ---


@given(st.text())
def test_parse_price_never_crashes_and_stays_in_range(text):
    for contract, lo, hi in (("sale", MIN_PRICE, MAX_PRICE), ("rent", MIN_RENT, MAX_RENT)):
        value = parse_price(text, contract)
        assert value is None or lo <= value <= hi


@given(st.integers(min_value=MIN_PRICE, max_value=MAX_PRICE))
def test_parse_price_reads_back_a_plausible_sale_amount(amount):
    # Italian thousands use ".", and the € sign is what marks it as a price
    formatted = f"€ {amount:,}".replace(",", ".")
    assert parse_price(formatted, "sale") == float(amount)


@given(st.text())
def test_parse_sqm_never_crashes(text):
    result = parse_sqm(text)
    assert result is None or result >= 0.0


@given(st.integers(min_value=1, max_value=999))
def test_parse_sqm_reads_back_a_plain_surface(sqm):
    assert parse_sqm(f"{sqm} m²") == float(sqm)


# --- _parse_floor: free-text floor label -> int | None ---


@given(st.text())
def test_parse_floor_never_crashes(text):
    result = _parse_floor(text)
    assert result is None or isinstance(result, int)


@given(st.integers(min_value=0, max_value=99))
def test_parse_floor_reads_a_bare_number(n):
    assert _parse_floor(str(n)) == n


@given(st.sampled_from(["piano terra", "Piano Terra", "terra", "rialzato", "Rialzato"]))
def test_parse_floor_treats_ground_and_mezzanine_as_zero(label):
    assert _parse_floor(label) == 0


@given(st.sampled_from(["piano terra 5", "rialzato 3", "terra 12"]))
def test_parse_floor_ground_wins_over_a_trailing_number(label):
    # "terra"/"rialzat" short-circuit before the numeric search, on purpose
    assert _parse_floor(label) == 0
