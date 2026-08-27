"""Distance and travel time from each property to the places the user actually
goes: work, the university, the nearest metro stop.

A price is only half of a decision — "40 minutes from the office" is the other
half, and it is the one no portal filter answers. The coordinates are already
there (`geocoder.py` fills them in), so this only adds the routing leg, through
OSRM (OpenStreetMap's router): free, and self-hostable for unlimited offline
use exactly like Nominatim.

Three rules keep it safe, cheap and honest, and each mirrors the geocoder next
door rather than inventing a second way of doing the same thing:

* **The annotation never touches the network.** `annotate_commutes` reads the
  cache and nothing else, so rendering a grid page cannot fire fifty routing
  requests at a public server (or stall the request while it does). Filling the
  cache is a separate, user-triggered, paced batch — the same split the geocoder
  makes between `annotate`-time and its maintenance endpoint.
* **One request per property, not one per point.** OSRM's `/table` service
  answers a whole one-to-many matrix in a single call, so three saved places
  cost one request instead of three. Points are grouped by travel mode, since a
  matrix is computed on one routing profile.
* **Fail-open, never a wrong number.** A block, a timeout or a malformed answer
  leaves the property with no commute shown. A *routed* "there is no way to get
  there" is a real answer and is cached as such (a NULL row, like the geocoder's
  negative cache); a transport failure is not cached at all, so a later run
  retries it.

**The limitation worth stating**: the public demo server
(`router.project-osrm.org`) is built on the driving network alone. It accepts
the walking and cycling profiles and answers with car routing, so "on foot" is
only truly on foot against a self-hosted OSRM. `osrm_url` is the setting that
points there.
"""

import json
import logging
import threading
import time
import urllib.parse
import urllib.request

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CommuteCache, GeocodeCache, Property

logger = logging.getLogger(__name__)

# The public OSRM demo server asks for reasonable use rather than publishing a
# rate limit. One request per second is the same pace the Nominatim policy
# demands next door, so the batch keeps one rhythm the user can reason about;
# against a self-hosted instance the pause is merely harmless.
PACE_SECONDS = 1.0

# Wall-clock ceiling for a single synchronous batch, in network requests. Same
# reasoning as the geocoder's: the run returns while the user is still watching,
# and `remaining` carries the rest into the next click.
MAX_PER_CALL = 60

# Travel modes offered to the user, mapped to the OSRM routing profiles. The
# names on the left are what the settings and the UI speak; the names on the
# right are OSRM's own. See the module docstring for what the demo server
# actually routes.
MODE_PROFILES = {
    "car": "driving",
    "foot": "walking",
    "bike": "cycling",
}
DEFAULT_MODE = "car"

# Coordinates are keyed at 5 decimals (~1 m). Finer than that is noise from the
# geocoder anyway, and it lets two listings in the same building share a row.
_COORD_PRECISION = 5


class CommuteError(Exception):
    """Raised when a commute batch cannot start (e.g. lock already held)."""


_commute_progress: dict = {
    "active": False,
    "done": 0,
    "total": 0,
    "routed": 0,
    "cached": 0,
    "unreachable": 0,
    "remaining": 0,
    "last_error": None,
}
_commute_run_lock = threading.Lock()
_commute_cancel_event = threading.Event()


def get_commute_progress() -> dict:
    """Snapshot of the running commute batch, for UI polling."""
    return dict(_commute_progress)


def request_cancel() -> None:
    """Signals a running commute batch to stop after its current property."""
    _commute_cancel_event.set()


def _round(value: float) -> float:
    return round(float(value), _COORD_PRECISION)


def cache_key(mode: str, olat: float, olng: float, dlat: float, dlng: float) -> str:
    """The identity of one origin→destination leg on one travel mode."""
    return f"{mode}|{_round(olat)},{_round(olng)}|{_round(dlat)},{_round(dlng)}"


def points_from_settings(settings: dict) -> list[dict]:
    """The user's saved places, normalized and validated.

    Each entry is `{"name", "address", "lat", "lng", "mode"}`. An entry with no
    name, or with neither an address nor a coordinate pair, is dropped rather
    than half-used: it can never produce a labelled answer. An unknown mode
    falls back to the default instead of failing the whole list — one bad row
    must not cost the user the other three.
    """
    if not settings.get("commute_enabled"):
        return []
    points: list[dict] = []
    for raw in settings.get("commute_points") or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        address = str(raw.get("address") or "").strip()
        lat, lng = _coerce_coords(raw.get("lat"), raw.get("lng"))
        if not name or (not address and lat is None):
            continue
        mode = str(raw.get("mode") or DEFAULT_MODE).strip().lower()
        if mode not in MODE_PROFILES:
            mode = DEFAULT_MODE
        points.append({"name": name, "address": address, "lat": lat, "lng": lng, "mode": mode})
    return points


def _coerce_coords(lat: object, lng: object) -> tuple[float | None, float | None]:
    """An explicit coordinate pair from the settings, or (None, None).

    Both halves or neither: a latitude with no longitude is not half a pin, it
    is an unusable one, and letting it through would put the point at the
    prime meridian.
    """
    try:
        flat, flng = float(lat), float(lng)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None, None
    if not (-90.0 <= flat <= 90.0) or not (-180.0 <= flng <= 180.0):
        return None, None
    return flat, flng


def _cached_geocode(db: Session, query: str) -> tuple[float, float] | None:
    """A geocoding result already paid for, or None. Deliberately read-only: the
    annotation path must not spend a Nominatim request while rendering a grid."""
    from .geocoder import _normalize

    key = _normalize(query)
    if not key:
        return None
    row = db.scalar(select(GeocodeCache).where(GeocodeCache.query == key))
    if row is None or row.latitude is None or row.longitude is None:
        return None
    return row.latitude, row.longitude


def resolve_points(db: Session, points: list[dict], *, allow_network: bool) -> list[dict]:
    """Attach real coordinates to each saved place, dropping the ones that have
    none yet.

    A point given as an address is geocoded through the *existing* geocoder, so
    it lands in the same cache under the same rules — there is no second
    address-to-coordinates path in this project, and this is not the place to
    open one. With `allow_network=False` only an explicit pin or an already-
    cached lookup counts, which is what keeps the annotation offline.
    """
    resolved: list[dict] = []
    for point in points:
        lat, lng = point["lat"], point["lng"]
        if lat is None and point["address"]:
            coords = _cached_geocode(db, point["address"])
            if coords is None and allow_network:
                coords = _geocode_point(db, point["address"])
            if coords is not None:
                lat, lng = coords
        if lat is None or lng is None:
            continue
        resolved.append({**point, "lat": lat, "lng": lng})
    return resolved


def _geocode_point(db: Session, address: str) -> tuple[float, float] | None:
    """One Nominatim lookup for a saved place, fail-open like every other."""
    from ..config import load_settings
    from . import geocoder

    base_url = (
        load_settings().get("nominatim_url") or "https://nominatim.openstreetmap.org"
    ).strip()
    try:
        # No expected_city: the user's own "Politecnico di Milano, Milano" is
        # already as specific as they chose to make it, and the city guard is
        # there to stop a *listing* address resolving to another comune.
        coords = geocoder.geocode(db, address, base_url, retry_negative=True)
    except Exception as e:
        logger.warning("commute: could not geocode the saved place %r (%s)", address, e)
        return None
    time.sleep(PACE_SECONDS)
    return coords


def _osrm_table(
    origin: tuple[float, float],
    destinations: list[tuple[float, float]],
    profile: str,
    base_url: str,
) -> list[tuple[float, float] | None] | None:
    """One-to-many distances and durations in a single request. Isolated so the
    tests drive the whole cache/batch logic with it mocked — no network.

    Returns one `(distance_m, duration_s)` per destination, with `None` where
    OSRM found no route, or `None` for the whole call when the request itself
    failed (the caller must tell those apart: the first is an answer to cache,
    the second is a transport failure to retry later).
    """
    coords = ";".join(f"{lng},{lat}" for lat, lng in [origin, *destinations])
    url = f"{base_url.rstrip('/')}/table/v1/{profile}/{coords}?" + urllib.parse.urlencode(
        {"sources": "0", "annotations": "distance,duration"}
    )
    req = urllib.request.Request(url, headers={"User-Agent": _user_agent()})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, dict):
        return None
    code = data.get("code")
    if code == "NoRoute":
        # A real answer: the router looked and there is no way through.
        unreachable: list[tuple[float, float] | None] = [None] * len(destinations)
        return unreachable
    if code != "Ok":
        return None
    durations = _first_row(data.get("durations"))
    distances = _first_row(data.get("distances"))
    if durations is None or distances is None:
        return None
    results: list[tuple[float, float] | None] = []
    # Index 0 of each row is the source against itself; the destinations follow
    # in the order they were sent.
    for i in range(1, len(destinations) + 1):
        try:
            meters, seconds = distances[i], durations[i]
        except IndexError:
            results.append(None)
            continue
        if meters is None or seconds is None:
            results.append(None)
        else:
            results.append((float(meters), float(seconds)))
    return results


def _first_row(matrix: object) -> list | None:
    if not isinstance(matrix, list) or not matrix:
        return None
    row = matrix[0]
    return row if isinstance(row, list) else None


def _user_agent() -> str:
    from .geocoder import _get_user_agent

    return _get_user_agent()


def annotate_commutes(db: Session, props: list[Property], settings: dict) -> None:
    """Attach the transient `commutes` read by PropertyOut — from the cache only.

    Every leg the batch has already routed shows up here for free; anything not
    yet routed is simply absent, exactly as a property with no pin shows no map
    marker. That is what makes this safe to call on every grid page.
    """
    points = resolve_points(db, points_from_settings(settings), allow_network=False)
    if not points:
        for p in props:
            p.commutes = []
        return
    for p in props:
        p.commutes = _cached_commutes(db, p, points)


def _cached_commutes(db: Session, prop: Property, points: list[dict]) -> list[dict]:
    if prop.latitude is None or prop.longitude is None:
        return []
    out: list[dict] = []
    for point in points:
        row = db.scalar(
            select(CommuteCache).where(
                CommuteCache.leg
                == cache_key(
                    point["mode"], prop.latitude, prop.longitude, point["lat"], point["lng"]
                )
            )
        )
        if row is None or row.distance_m is None or row.duration_s is None:
            continue
        out.append(
            {
                "name": point["name"],
                "mode": point["mode"],
                "distance_m": row.distance_m,
                "duration_s": row.duration_s,
            }
        )
    return out


def compute_missing_commutes(db: Session, max_calls: int | None = -1) -> dict:
    """Route every property/place pair that is not in the cache yet.

    `max_calls` counts *network* requests, not properties: -1 (the default) caps
    at `MAX_PER_CALL` for a synchronous run, None removes the cap for a
    background one, mirroring the geocoder's batch.
    """
    if not _commute_run_lock.acquire(blocking=False):
        raise CommuteError("A commute batch is already running: wait for it to finish")
    _commute_cancel_event.clear()
    try:
        return _compute_missing_commutes_inner(db, max_calls)
    finally:
        _commute_run_lock.release()


def _compute_missing_commutes_inner(db: Session, max_calls: int | None = -1) -> dict:
    from ..config import load_settings

    settings = load_settings()
    base_url = (settings.get("osrm_url") or "https://router.project-osrm.org").strip()
    # allow_network here: this is the paced batch, and a saved place given as an
    # address has to become a coordinate once before anything can be routed to it.
    points = resolve_points(db, points_from_settings(settings), allow_network=True)

    summary = {
        "scanned": 0,
        "routed": 0,
        "cached": 0,
        "unreachable": 0,
        "remaining": 0,
        "points": len(points),
        "cancelled": False,
    }
    if not points:
        return summary

    candidates = db.scalars(
        select(Property)
        .where(Property.latitude.is_not(None))
        .where(Property.longitude.is_not(None))
        .order_by(Property.id)
    ).all()

    if max_calls is None:
        budget = float("inf")
    elif max_calls == -1:
        budget = MAX_PER_CALL
    else:
        budget = max_calls

    _commute_progress.update(
        active=True,
        done=0,
        total=len(candidates),
        routed=0,
        cached=0,
        unreachable=0,
        remaining=0,
        last_error=None,
    )
    try:
        for index, prop in enumerate(candidates):
            if _commute_cancel_event.is_set():
                summary["cancelled"] = True
                summary["remaining"] += len(candidates) - index
                logger.info("commute: cancelled by user after %d properties", index)
                break

            if prop.latitude is None or prop.longitude is None:
                continue  # the query excludes these; the check is for the type
            origin = (prop.latitude, prop.longitude)

            summary["scanned"] += 1
            missing = _missing_legs(db, origin, points)
            summary["cached"] += len(points) - len(missing)
            if not missing:
                _commute_progress.update(done=index + 1, cached=summary["cached"])
                continue
            if budget <= 0:
                summary["remaining"] += 1
                continue

            spent = _route_property(db, prop.id, origin, missing, base_url, summary)
            budget -= spent
            db.commit()
            _commute_progress.update(
                done=index + 1,
                routed=summary["routed"],
                cached=summary["cached"],
                unreachable=summary["unreachable"],
                remaining=summary["remaining"],
            )
            if spent and budget > 0 and not _commute_cancel_event.is_set():
                time.sleep(PACE_SECONDS)
    finally:
        _commute_progress.update(active=False)
    return summary


def _missing_legs(db: Session, origin: tuple[float, float], points: list[dict]) -> list[dict]:
    """The saved places this pin has no cached answer for — a routed
    "unreachable" counts as answered, so it is never re-asked."""
    missing = []
    for point in points:
        key = cache_key(point["mode"], origin[0], origin[1], point["lat"], point["lng"])
        if db.scalar(select(CommuteCache).where(CommuteCache.leg == key)) is None:
            missing.append(point)
    return missing


def _route_property(
    db: Session,
    prop_id: int,
    origin: tuple[float, float],
    points: list[dict],
    base_url: str,
    summary: dict,
) -> int:
    """Route one property to its missing places, grouped by travel mode. Returns
    how many network requests it spent, so the caller can bill the budget."""
    spent = 0
    by_mode: dict[str, list[dict]] = {}
    for point in points:
        by_mode.setdefault(point["mode"], []).append(point)

    for mode, group in by_mode.items():
        destinations = [(p["lat"], p["lng"]) for p in group]
        spent += 1
        try:
            results = _osrm_table(origin, destinations, MODE_PROFILES[mode], base_url)
        except Exception as e:
            # Transport failure: cache nothing, so the next run asks again.
            logger.warning("commute: routing failed for property #%s (%s)", prop_id, e)
            _commute_progress["last_error"] = str(e)
            summary["remaining"] += 1
            return spent
        if results is None:
            summary["remaining"] += 1
            return spent
        for point, result in zip(group, results, strict=False):
            key = cache_key(mode, origin[0], origin[1], point["lat"], point["lng"])
            meters, seconds = result if result else (None, None)
            db.add(CommuteCache(leg=key, distance_m=meters, duration_s=seconds))
            if result:
                summary["routed"] += 1
            else:
                summary["unreachable"] += 1
    return spent


def clear_commute_cache(db: Session) -> int:
    """Forget every routed leg, so the next batch recomputes them.

    Unlike the geocoder's cache this is wiped whole rather than misses-only: a
    commute answer goes stale for a reason the row cannot see (the user moved
    the office pin, or a self-hosted OSRM got a fresher map extract), and a
    positive row is exactly the one that then keeps lying.
    """
    rows = db.scalars(select(CommuteCache)).all()
    for row in rows:
        db.delete(row)
    db.commit()
    return len(rows)
