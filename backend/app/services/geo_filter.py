"""Pure geometry for the map's geographic filter (radius + polygon).

The dashboard can keep only the properties inside a drawn area: a point + a
maximum radius, or a free polygon. That is all decided here, offline and
dependency-free — the module holds nothing but geometry so it stays trivially
unit-testable (invariant 17's spirit) and has no reason to touch the DB or the
network.

`geocoder.py` turns an address into coordinates; this turns coordinates into an
"inside/outside" answer. Two different responsibilities, two different homes.
"""

import math

# Great-circle radius of the Earth in metres (matches deduplicator._haversine_m,
# whose gate is measured in metres too).
_EARTH_RADIUS_M = 6_371_000


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points, in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def point_in_polygon(lat: float, lng: float, vertices: list[tuple[float, float]]) -> bool:
    """Ray casting: is (lat, lng) inside the polygon `vertices`?

    Treats lat/lng as planar (x=lng, y=lat). At a city's scale the distortion is
    negligible for a "keep what I drew" filter, and the polygon the user draws is
    in the very same projected space Leaflet shows them. Handles concave shapes
    (the algorithm makes no convexity assumption); a point exactly on an edge is
    reported inside, so a vertex-snapped listing is never silently dropped.
    """
    if len(vertices) < 3:
        return False
    # On-edge is "inside": check it up front, because the parity test below is
    # otherwise ambiguous for a point lying exactly on a boundary segment.
    n = len(vertices)
    for i in range(n):
        ay, ax = vertices[i]
        by, bx = vertices[(i + 1) % n]
        if _on_segment(lat, lng, ay, ax, by, bx):
            return True
    inside = False
    j = n - 1
    for i in range(n):
        yi, xi = vertices[i]
        yj, xj = vertices[j]
        # does the horizontal ray at y=lat cross edge i→j?
        if (yi > lat) != (yj > lat):
            x_cross = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lng < x_cross:
                inside = not inside
        j = i
    return inside


def _on_segment(py: float, px: float, ay: float, ax: float, by: float, bx: float) -> bool:
    """Is point (py, px) on the segment (ay,ax)-(by,bx)? (with a tiny epsilon)."""
    cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    if abs(cross) > 1e-9:
        return False
    # collinear: must fall within the bounding box of the segment
    return min(ax, bx) - 1e-9 <= px <= max(ax, bx) + 1e-9 and (
        min(ay, by) - 1e-9 <= py <= max(ay, by) + 1e-9
    )


def parse_polygon(raw: str) -> list[tuple[float, float]]:
    """Codec for the `poly` query param: "lat,lng;lat,lng;…" → vertices.

    Raises `ValueError` (never silently ignores) on a malformed string, fewer
    than 3 vertices, or a coordinate out of range — the endpoint turns that into
    a 400, consistent with how the other filters reject bad input.
    """
    if not raw or not raw.strip():
        raise ValueError("empty polygon")
    vertices: list[tuple[float, float]] = []
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split(",")
        if len(parts) != 2:
            raise ValueError(f"malformed vertex: {chunk!r}")
        try:
            lat = float(parts[0])
            lng = float(parts[1])
        except ValueError as exc:
            raise ValueError(f"non-numeric vertex: {chunk!r}") from exc
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
            raise ValueError(f"coordinate out of range: {chunk!r}")
        vertices.append((lat, lng))
    if len(vertices) < 3:
        raise ValueError("a polygon needs at least 3 vertices")
    return vertices
