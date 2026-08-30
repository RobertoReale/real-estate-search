"""Tests for the map's geographic filter: the pure geometry (`geo_filter`) and
its wiring into `select_properties` / the endpoint.

Offline like everything else: fake in-memory properties, no network. The one
thing that matters beyond "does the maths work" is the invariant the caveat is
about — a property with NULL coordinates can't be placed in a zone and must
*always* drop out of a geographic filter, never leak through as a silent match.
"""

from typing import Any

import pytest
from fastapi import HTTPException
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.routers.selection import parse_poly_param, select_properties
from app.scrapers.base import RawListing
from app.services.deduplicator import upsert_listing
from app.services.geo_filter import haversine_m, parse_polygon, point_in_any, point_in_polygon

# --- haversine_m -----------------------------------------------------------


def test_haversine_zero_distance():
    assert haversine_m(45.0, 9.0, 45.0, 9.0) == pytest.approx(0.0, abs=1e-6)


def test_haversine_known_distance():
    # Milan Duomo → Turin (Porta Nuova), ~126 km great-circle.
    d = haversine_m(45.4642, 9.1900, 45.0625, 7.6785)
    assert d == pytest.approx(126_000, rel=0.02)


def test_haversine_one_degree_latitude():
    # one degree of latitude is ~111 km anywhere on Earth
    assert haversine_m(0.0, 0.0, 1.0, 0.0) == pytest.approx(111_195, rel=0.01)


# --- point_in_polygon ------------------------------------------------------

# A simple square around (0,0): lat/lng in [-1, 1].
_SQUARE = [(-1.0, -1.0), (-1.0, 1.0), (1.0, 1.0), (1.0, -1.0)]

# A concave "arrow"/chevron: the notch means a naive convex test would fail.
_CONCAVE = [(0.0, 0.0), (0.0, 4.0), (4.0, 4.0), (2.0, 2.0), (4.0, 0.0)]


def test_point_inside_square():
    assert point_in_polygon(0.0, 0.0, _SQUARE) is True


def test_point_outside_square():
    assert point_in_polygon(5.0, 5.0, _SQUARE) is False


def test_point_on_edge_counts_as_inside():
    # exactly on the top edge (lat=1, lng between -1 and 1)
    assert point_in_polygon(1.0, 0.0, _SQUARE) is True


def test_point_on_vertex_counts_as_inside():
    assert point_in_polygon(-1.0, -1.0, _SQUARE) is True


def test_concave_point_inside_notch_is_outside():
    # (3, 2) sits inside the bounding box but within the chevron's notch,
    # so it must read outside — the concave case a convex test gets wrong.
    assert point_in_polygon(3.0, 2.0, _CONCAVE) is False


def test_concave_point_in_arm_is_inside():
    assert point_in_polygon(1.0, 2.0, _CONCAVE) is True


def test_too_few_vertices_never_inside():
    assert point_in_polygon(0.0, 0.0, [(0.0, 0.0), (1.0, 1.0)]) is False


@given(
    st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False),
    st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False),
)
def test_point_far_outside_bounding_box_is_outside(lat, lng):
    # anything beyond the square's [-1,1] box can never be inside it
    if abs(lat) > 1.0 or abs(lng) > 1.0:
        assert point_in_polygon(lat, lng, _SQUARE) is False


@given(
    st.floats(min_value=-0.99, max_value=0.99, allow_nan=False, allow_infinity=False),
    st.floats(min_value=-0.99, max_value=0.99, allow_nan=False, allow_infinity=False),
)
def test_point_strictly_within_square_is_inside(lat, lng):
    assert point_in_polygon(lat, lng, _SQUARE) is True


# --- point_in_any ----------------------------------------------------------

# A second square, well clear of the first: a *selection* of areas, which is
# what a multi-zone search is and what a single-polygon test cannot express.
_FAR_SQUARE = [(9.0, 9.0), (9.0, 11.0), (11.0, 11.0), (11.0, 9.0)]

# The square above with its middle punched out, the shape a published perimeter
# genuinely has (a block inside the boundary that belongs elsewhere).
_HOLED = {"outer": _SQUARE, "holes": [[(-0.5, -0.5), (-0.5, 0.5), (0.5, 0.5), (0.5, -0.5)]]}


def test_point_in_any_finds_the_second_perimeter():
    areas = [{"outer": _SQUARE}, {"outer": _FAR_SQUARE}]
    assert point_in_any(10.0, 10.0, areas) is True


def test_point_in_any_outside_every_perimeter():
    areas = [{"outer": _SQUARE}, {"outer": _FAR_SQUARE}]
    assert point_in_any(5.0, 5.0, areas) is False


def test_point_in_any_respects_holes():
    """The hole is not part of the area, so a point in it is outside — the
    perimeter half of this has to behave exactly like point_in_rings."""
    assert point_in_any(0.0, 0.0, [_HOLED]) is False
    assert point_in_any(0.9, 0.9, [_HOLED]) is True


def test_point_in_any_accepts_a_circle():
    """A comune is known offline as a centroid and a radius, never a boundary,
    so "inside the requested area" has to be answerable for a circle too."""
    milano = (45.4642, 9.1900, 12_000.0)
    assert point_in_any(45.47, 9.18, [milano]) is True
    # Turin is ~126 km away: outside by two orders of magnitude
    assert point_in_any(45.0625, 7.6785, [milano]) is False


def test_point_in_any_mixes_shapes():
    assert point_in_any(10.0, 10.0, [(45.4642, 9.19, 12_000.0), {"outer": _FAR_SQUARE}]) is True


def test_nothing_requested_contains_nothing():
    """An empty selection is False, not "everything": the caller keeps the
    difference between "outside the requested area" and "no area requested",
    and collapsing the two here would flag every listing of a search that named
    no location at all."""
    assert point_in_any(0.0, 0.0, []) is False


# --- parse_polygon ---------------------------------------------------------


def test_parse_polygon_valid():
    v = parse_polygon("45.1,9.1;45.2,9.2;45.3,9.1")
    assert v == [(45.1, 9.1), (45.2, 9.2), (45.3, 9.1)]


def test_parse_polygon_tolerates_trailing_separator():
    v = parse_polygon("45.1,9.1;45.2,9.2;45.3,9.1;")
    assert len(v) == 3


def test_parse_polygon_too_few_vertices():
    with pytest.raises(ValueError):
        parse_polygon("45.1,9.1;45.2,9.2")


def test_parse_polygon_out_of_range():
    with pytest.raises(ValueError):
        parse_polygon("91.0,9.1;45.2,9.2;45.3,9.1")
    with pytest.raises(ValueError):
        parse_polygon("45.1,181.0;45.2,9.2;45.3,9.1")


def test_parse_polygon_non_numeric():
    with pytest.raises(ValueError):
        parse_polygon("45.1,abc;45.2,9.2;45.3,9.1")


def test_parse_polygon_malformed_vertex():
    with pytest.raises(ValueError):
        parse_polygon("45.1;45.2,9.2;45.3,9.1")


def test_parse_polygon_empty():
    with pytest.raises(ValueError):
        parse_polygon("")


# --- parse_poly_param (endpoint helper) -----------------------------------


def test_parse_poly_param_none_when_absent():
    assert parse_poly_param(None) is None
    assert parse_poly_param("  ") is None


def test_parse_poly_param_malformed_raises_400():
    with pytest.raises(HTTPException) as exc:
        parse_poly_param("45.1,9.1;45.2,9.2")  # only 2 vertices
    assert exc.value.status_code == 400


# --- select_properties integration ----------------------------------------


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def _make(db, portal_id: str, lat: float | None, lng: float | None):
    # Distinct surface/price/address per id so the deduplicator never folds two
    # of these into one card (which would break the "N properties" counts below);
    # the geometry, not the merge logic, is what these tests are about.
    n = int(portal_id)
    base: dict[str, Any] = dict(
        portal="immobiliare",
        portal_id=portal_id,
        url=f"https://www.immobiliare.it/annunci/{portal_id}/",
        title=f"Apartment {portal_id}",
        city="Milano",
        zone="Centro",
        rooms=3,
        sqm=50.0 + 10 * n,
        price=200_000.0 + 50_000 * n,
        latitude=lat,
        longitude=lng,
        address=f"Via Roma, {n}",
    )
    prop, _, _ = upsert_listing(db, RawListing(**base))
    return prop


def _select(db, **kw):
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
    # (page, total): these tests are about which properties the zone keeps, so
    # they take the page — unbounded here, since no limit is passed
    props, _total = select_properties(db, **params)
    return props


def test_radius_keeps_only_inside(db):
    near = _make(db, "1", 45.4642, 9.1900)  # Milan Duomo
    _make(db, "2", 45.0625, 7.6785)  # Turin, ~126 km away
    db.commit()
    got = _select(db, center_lat=45.4642, center_lng=9.1900, radius_m=5000)
    assert {p.id for p in got} == {near.id}


def test_polygon_keeps_only_inside(db):
    inside = _make(db, "1", 45.46, 9.19)
    _make(db, "2", 48.0, 2.0)  # far outside
    db.commit()
    poly = [(45.40, 9.10), (45.40, 9.30), (45.55, 9.30), (45.55, 9.10)]
    got = _select(db, poly_vertices=poly)
    assert {p.id for p in got} == {inside.id}


def test_null_coordinates_always_excluded_by_radius(db):
    _make(db, "1", 45.4642, 9.1900)
    no_coords = _make(db, "2", None, None)
    db.commit()
    # a huge radius covering the whole planet still excludes the NULL-coord one
    got = _select(db, center_lat=45.4642, center_lng=9.1900, radius_m=100_000)
    assert no_coords.id not in {p.id for p in got}


def test_null_coordinates_always_excluded_by_polygon(db):
    _make(db, "1", 45.46, 9.19)
    no_coords = _make(db, "2", None, None)
    db.commit()
    poly = [(-90.0, -180.0), (-90.0, 180.0), (90.0, 180.0), (90.0, -180.0)]
    got = _select(db, poly_vertices=poly)
    assert no_coords.id not in {p.id for p in got}


def test_no_geo_params_leaves_set_untouched(db):
    _make(db, "1", 45.4642, 9.1900)
    _make(db, "2", None, None)
    db.commit()
    got = _select(db)
    assert len(got) == 2


def test_radius_takes_precedence_over_polygon(db):
    """Radius and polygon are mutually exclusive; if both arrive, radius wins
    (matches the `if radius … elif poly` order in `select_properties`)."""
    inside = _make(db, "1", 45.4642, 9.1900)
    db.commit()
    # a polygon that would exclude everything, but radius includes the point
    tiny_poly = [(0.0, 0.0), (0.0, 0.1), (0.1, 0.1)]
    got = _select(
        db,
        center_lat=45.4642,
        center_lng=9.1900,
        radius_m=1000,
        poly_vertices=tiny_poly,
    )
    assert {p.id for p in got} == {inside.id}
