"""Opt-in geocoding to backfill the map coordinates most listings lack.

~70% of Immobiliare listings arrive with no lat/lng, so the map view is mostly
empty. This turns a listing's "address/zone + city" into a real pin via
Nominatim (OpenStreetMap) — free, and self-hostable for unlimited offline use.

Two rules keep it safe and inside the free tier:

* **Fail-open, never a wrong pin.** A lookup that fails or is ambiguous leaves
  the property's coordinates untouched. A missing pin is fine; a pin in the
  wrong place is a lie the user would act on.
* **Cache everything, including misses.** Every query is remembered in
  `GeocodeCache` (a NULL result is a *negative* cache), so the same
  "via Dante, Milano" is never asked twice — that is what lets an opt-in batch
  stay under Nominatim's 1-request-per-second policy.

Like `repair_listings`, it only ever runs when the user triggers it (a batched,
paced maintenance endpoint), never inside the hot scan path. The outbound HTTP
call lives in `_nominatim_lookup` alone, so tests drive the whole cache/batch
logic with it mocked — no network, fully reproducible (invariant 17's spirit).
"""

import json
import logging
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import GeocodeCache, Property

logger = logging.getLogger(__name__)

# Nominatim's usage policy: at most one request per second, and a real
# User-Agent identifying the app. Both are non-negotiable for the public
# instance; a self-hosted one does not care but the pause is harmless.
PACE_SECONDS = 1.0


def _get_user_agent() -> str:
    try:
        from ..config import load_settings

        email = (load_settings().get("email_from") or "").strip()
        if email:
            return f"RealEstateSearch/1.0 (local personal use; contact: {email})"
    except Exception:
        pass
    return "RealEstateSearch/1.0 (local personal use)"


# One call must not stall the request forever. The public Nominatim instance is
# capped at 1 req/s, so this is roughly the wall-clock seconds a single click
# costs (cache hits are free): kept modest so the request returns in under a
# minute and the UI's "run it again to continue" (via `remaining`) carries the
# rest, rather than one click blocking for minutes with no progress.
MAX_PER_CALL = 40


class GeocoderError(Exception):
    """Raised when a geocoding check cannot start (e.g. lock already held)."""


_geocode_progress: dict = {
    "active": False,
    "done": 0,
    "total": 0,
    "geocoded": 0,
    "cached": 0,
    "not_found": 0,
    "remaining": 0,
    "last_error": None,
}
_geocode_run_lock = threading.Lock()
_geocode_cancel_event = threading.Event()


def get_geocode_progress() -> dict:
    """Snapshot of the running geocoding check, for UI polling."""
    return dict(_geocode_progress)


def request_cancel() -> None:
    """Signals a running geocoding batch to stop after its current property."""
    _geocode_cancel_event.set()


def clear_geocode_cache(db: Session, misses_only: bool = True) -> int:
    """Forget cached geocoding lookups so the next batch re-queries them.

    Defaults to `misses_only`: it drops only the *negative* rows (NULL lat/lng),
    which are the stuck ones — a transient empty answer from Nominatim gets
    frozen as a permanent miss and never retried by the paced batch (the on-
    demand single-property path already retries them, see `geocode`'s
    `retry_negative`). Positive rows are the requests we already paid for under
    the rate limit, so they are kept. `misses_only=False` wipes the whole cache.
    Returns how many rows were removed. This never touches a property's own
    coordinates — only the lookup memory — so it is safe and idempotent.
    """
    stmt = select(GeocodeCache)
    if misses_only:
        stmt = stmt.where(GeocodeCache.latitude.is_(None))
    rows = db.scalars(stmt).all()
    for row in rows:
        db.delete(row)
    db.commit()
    return len(rows)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


KNOWN_CITY_BOXES: dict[str, tuple[float, float, float, float]] = {
    # lat_min, lat_max, lon_min, lon_max
    "milano": (45.34, 45.56, 9.01, 9.31),
    "roma": (41.65, 42.05, 12.20, 12.75),
    "torino": (44.95, 45.16, 7.55, 7.78),
    "bologna": (44.40, 44.57, 11.23, 11.45),
    "firenze": (43.70, 43.83, 11.16, 11.33),
    "napoli": (40.80, 40.90, 14.15, 14.35),
    "genova": (44.38, 44.47, 8.75, 9.08),
    "palermo": (38.05, 38.21, 13.25, 13.45),
    "bari": (41.05, 41.17, 16.78, 16.95),
    "catania": (37.45, 37.56, 15.01, 15.13),
    "verona": (45.38, 45.49, 10.92, 11.06),
    "padova": (45.35, 45.46, 11.81, 11.95),
    "trieste": (45.60, 45.73, 13.71, 13.86),
    "brescia": (45.49, 45.59, 10.15, 10.28),
    "parma": (44.75, 44.86, 10.26, 10.39),
    "monza": (45.56, 45.61, 9.24, 9.31),
    "bergamo": (45.67, 45.73, 9.63, 9.72),
    "udine": (46.02, 46.10, 13.19, 13.28),
    "modena": (44.60, 44.70, 10.86, 10.98),
    "reggio emilia": (44.65, 44.75, 10.57, 10.69),
    "perugia": (43.05, 43.16, 12.33, 12.45),
    "cagliari": (39.18, 39.26, 9.08, 9.18),
    "foggia": (41.42, 41.50, 15.50, 15.60),
    "rimini": (44.02, 44.10, 12.52, 12.62),
    "salerno": (40.65, 40.71, 14.74, 14.84),
    "ferrara": (44.80, 44.88, 11.56, 11.66),
}


def is_valid_coordinate_for_city(lat: float | None, lon: float | None, city: str) -> bool:
    """Checks if (lat, lon) falls roughly inside Italy and within the target city's bounds."""
    if lat is None or lon is None:
        return False
    if not (35.0 <= lat <= 47.5 and 6.5 <= lon <= 18.6):
        return False
    key = _normalize(city)
    if key in KNOWN_CITY_BOXES:
        lat_min, lat_max, lon_min, lon_max = KNOWN_CITY_BOXES[key]
        return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max
    return True


def _is_in_city(item_address: dict, expected_city: str) -> bool:
    """Verifies from OSM address details that the result actually belongs to expected_city."""
    if not expected_city or not isinstance(item_address, dict):
        return True
    exp = _normalize(expected_city)
    for key in ("city", "town", "village", "municipality", "hamlet"):
        val = item_address.get(key)
        if val and _normalize(val) == exp:
            return True
    local_places = [
        item_address.get(k)
        for k in ("city", "town", "village", "municipality", "hamlet")
        if item_address.get(k)
    ]
    if local_places:
        return False
    for key in ("suburb", "city_district", "county"):
        val = item_address.get(key)
        if val and _normalize(val) == exp:
            return True
    return False


def _clean_street_name(place: str) -> str:
    """Removes house numbers, floors, and stair designations for fallback querying."""
    if not place:
        return ""
    s = place.strip()
    if " - " in s:
        s = s.split(" - ")[0].strip()
    if "," in s:
        s = s.split(",")[0].strip()
    # "s.n.c" / "snc" = "senza numero civico": agencies write it where a house
    # number would go, and Nominatim returns 0 results for "Via Camaldoli s.n.c"
    # while "Via Camaldoli" resolves cleanly — so it must be stripped like the
    # other civic-address tokens, or the fallback query fails too.
    s = re.sub(
        r"\s+\b(?:s\.?n\.?c\.?|n\.?|civico|piano|p\.?T|scala|sc\.?|int\.?|interno)\b.*$",
        "",
        s,
        flags=re.I,
    ).strip()
    s = re.sub(r"\s+\b\d+([a-zA-Z/0-9-]*)$", "", s).strip()
    return s


def build_queries(prop: Property) -> list[str]:
    """Returns a prioritized list of address queries for a property, anchored to city.

    Prefers full address with house number, falling back to street name without
    number, and finally zone, so if 'Via Tolmezzo, 2, Milano, Italia' fails or is
    in another municipality, 'Via Tolmezzo, Milano, Italia' or 'Udine, Milano, Italia'
    can still succeed.
    """
    city = (prop.city or "").strip()
    if not city:
        return []

    queries = []
    seen = set()

    def _add(q: str) -> None:
        key = _normalize(q)
        if key and key not in seen:
            seen.add(key)
            queries.append(q)

    address = (prop.address or "").strip()
    if address:
        _add(f"{address}, {city}, Italia")
        clean_addr = _clean_street_name(address)
        if clean_addr and len(clean_addr) >= 3 and _normalize(clean_addr) != _normalize(address):
            _add(f"{clean_addr}, {city}, Italia")

    zone = (prop.zone or "").strip()
    if zone and _normalize(zone) not in ("in vendita a milano", "vendita a milano"):
        clean_zone = _clean_street_name(zone)
        _add(f"{zone}, {city}, Italia")
        if clean_zone and len(clean_zone) >= 3 and _normalize(clean_zone) != _normalize(zone):
            _add(f"{clean_zone}, {city}, Italia")

    return queries


def build_query(prop: Property) -> str:
    """The most specific address string we can form for a property.

    Prefers a street address (best precision), else the zone, always anchored
    to the city and country so "Isola, Milano, Italia" cannot resolve to an
    Isola somewhere else. Returns "" when there is nothing better than a city —
    a bare city would drop every such listing on one downtown pin.
    """
    queries = build_queries(prop)
    return queries[0] if queries else ""


def _nominatim_lookup(
    query: str, base_url: str, expected_city: str = ""
) -> tuple[float, float] | None:
    """Single geocoding request. Isolated so tests can mock it."""
    url = (
        base_url.rstrip("/")
        + "/search?"
        + urllib.parse.urlencode(
            {
                "q": query,
                "format": "json",
                "limit": 5,
                "addressdetails": 1,
                "countrycodes": "it",
            }
        )
    )
    req = urllib.request.Request(url, headers={"User-Agent": _get_user_agent()})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data or not isinstance(data, list):
        return None
    for item in data:
        try:
            lat = float(item["lat"])
            lon = float(item["lon"])
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        item_address = item.get("address", {}) if isinstance(item, dict) else {}
        if _is_in_city(item_address, expected_city) and is_valid_coordinate_for_city(
            lat, lon, expected_city
        ):
            return lat, lon
    return None


def geocode(
    db: Session, query: str, base_url: str, expected_city: str = "", retry_negative: bool = False
) -> tuple[float, float] | None:
    """Resolve `query` to (lat, lng), consulting and populating the cache.

    A cached row — hit or miss — short-circuits the network entirely; only a
    genuinely new query spends a request (and returns True in the 2-tuple's
    place via the `hit_network` flag on the batch, not here). Failures are
    cached as NULL so they are not retried on the next batch.

    `retry_negative=True` discards a cached *miss* (NULL) and looks it up again.
    A negative result is often just a transient empty answer from Nominatim (a
    rate-limit hiccup, or OSM data that has since improved) frozen forever by
    the cache — harmless for the paced batch, but for the on-demand single-
    property path it strands a perfectly resolvable address behind a stale
    "not found". That path spends at most a couple of requests, so it can
    afford to re-ask; the batch stays on the default so it keeps its rate
    budget.
    """
    key = _normalize(query)
    if not key:
        return None
    cached = db.scalar(select(GeocodeCache).where(GeocodeCache.query == key))
    if cached is not None:
        if cached.latitude is not None and cached.longitude is not None:
            if is_valid_coordinate_for_city(cached.latitude, cached.longitude, expected_city):
                return cached.latitude, cached.longitude
            db.delete(cached)
            db.commit()
        elif retry_negative:
            db.delete(cached)
            db.commit()
        else:
            return None
    try:
        try:
            result = _nominatim_lookup(query, base_url, expected_city=expected_city)
        except TypeError:
            result = _nominatim_lookup(query, base_url)
    except Exception as e:
        logger.warning("geocoder: lookup failed for %r (%s)", query, e)
        _geocode_progress["last_error"] = str(e)
        if isinstance(e, urllib.error.HTTPError) and e.code in (403, 429):
            raise e
        return None  # transient: do NOT cache, so a later batch can retry
    lat, lng = result if result else (None, None)
    db.add(GeocodeCache(query=key, latitude=lat, longitude=lng))
    db.commit()
    return result if result else None


def geocode_property(db: Session, prop: Property) -> tuple[float, float] | None:
    """Resolve one property's coordinates on demand, for the card's "View on
    map" button when it has no pin yet. Sets `prop.latitude/longitude` and
    returns the coords when found, else None.

    Reuses the cached, city-verified `geocode()`, so a query already seen (hit
    or negative) costs no network. It is deliberately *not* gated by
    `_geocode_run_lock` — that serialises the maintenance sweep over hundreds of
    rows; this fills the single property the user is looking at right now, at
    most a handful of queries. Fail-open like the batch (invariant's spirit): a
    block or an ambiguous lookup leaves the property un-pinned rather than
    writing a wrong pin.
    """
    from ..config import load_settings

    base_url = (
        load_settings().get("nominatim_url") or "https://nominatim.openstreetmap.org"
    ).strip()
    for query in build_queries(prop):
        key = _normalize(query)
        cached_row = db.scalar(select(GeocodeCache).where(GeocodeCache.query == key))
        # A positive cache hit costs no network; a negative one is retried here
        # (see geocode's retry_negative), so it must not count as "cached" for
        # pacing — we may still spend a real request on it.
        cached = cached_row is not None and cached_row.latitude is not None
        try:
            coords = geocode(db, query, base_url, expected_city=prop.city, retry_negative=True)
        except Exception as e:
            # geocode() re-raises 403/429: Nominatim is blocking, so stop and
            # fail open (no pin) rather than hammering it for the next query.
            logger.warning("geocoder: single lookup blocked for #%s (%s)", prop.id, e)
            return None
        if coords:
            prop.latitude, prop.longitude = coords
            db.commit()
            return coords
        # Pace only between genuine network lookups; a cached miss is free.
        if not cached:
            time.sleep(PACE_SECONDS)
    return None


def geocode_missing_properties(db: Session, max_calls: int | None = -1) -> dict:
    """Fill in coordinates for properties that have an address/zone but no pin.

    When `max_calls` is -1 (default), it caps at `MAX_PER_CALL` for synchronous
    batches. When `max_calls` is None, it runs all remaining candidates without
    capping (`budget = float("inf")`), ideal for background progress execution.
    """
    if not _geocode_run_lock.acquire(blocking=False):
        raise GeocoderError("A geocoding batch is already running: wait for it to finish")
    _geocode_cancel_event.clear()
    try:
        return _geocode_missing_properties_inner(db, max_calls)
    finally:
        _geocode_run_lock.release()


def _geocode_missing_properties_inner(db: Session, max_calls: int | None = -1) -> dict:
    from ..config import load_settings

    base_url = (
        load_settings().get("nominatim_url") or "https://nominatim.openstreetmap.org"
    ).strip()

    # Clear out any existing coordinates that fall clearly outside the property's city
    # (repairing old mis-geocodings like 'Via Tolmezzo, 2' -> Cernusco or 'Dergano' -> Torino).
    existing_geocoded = db.scalars(
        select(Property).where(Property.latitude.is_not(None)).where(Property.city != "")
    ).all()
    for p in existing_geocoded:
        if not is_valid_coordinate_for_city(p.latitude, p.longitude, p.city):
            logger.info(
                "geocoder: clearing out-of-bounds coords for property #%s (%s: %s, %s)",
                p.id,
                p.city,
                p.latitude,
                p.longitude,
            )
            p.latitude, p.longitude = None, None
    db.commit()

    candidates = db.scalars(
        select(Property)
        .where(Property.latitude.is_(None))
        .where(Property.city != "")
        .where(or_(Property.address != "", Property.zone != ""))
        .order_by(Property.id)
    ).all()

    summary = {
        "scanned": 0,
        "geocoded": 0,
        "cached": 0,
        "not_found": 0,
        "remaining": 0,
        "cancelled": False,
    }
    if max_calls is None:
        budget = float("inf")
    elif max_calls == -1:
        budget = MAX_PER_CALL
    else:
        budget = max_calls

    _geocode_progress.update(
        active=True,
        done=0,
        total=len(candidates),
        geocoded=0,
        cached=0,
        not_found=0,
        remaining=0,
        last_error=None,
    )
    try:
        for index, prop in enumerate(candidates):
            if _geocode_cancel_event.is_set():
                summary["cancelled"] = True
                summary["remaining"] += len(candidates) - index
                logger.info("geocoder: cancelled by user after %d candidates", index)
                break

            queries = build_queries(prop)
            if not queries:
                _geocode_progress.update(done=index + 1)
                continue
            summary["scanned"] += 1

            coords = None
            was_cached = False
            try:
                for query in queries:
                    key = _normalize(query)
                    cached_row = db.scalar(select(GeocodeCache).where(GeocodeCache.query == key))
                    cached_exists = cached_row is not None
                    if not cached_exists:
                        if budget <= 0:
                            break
                        budget -= 1

                    coords = geocode(db, query, base_url, expected_city=prop.city)
                    if cached_exists and coords:
                        was_cached = True
                    if coords:
                        break
                    if not cached_exists and budget > 0:
                        if _geocode_cancel_event.is_set():
                            break
                        time.sleep(PACE_SECONDS)
            except Exception as e:
                logger.warning("geocoder: aborting batch due to block/rate-limit: %s", e)
                summary["cancelled"] = True
                summary["remaining"] += len(candidates) - index
                _geocode_progress["last_error"] = str(e)
                break

            if not coords and budget <= 0 and not was_cached:
                summary["remaining"] += 1
                continue

            if was_cached and coords:
                summary["cached"] += 1
            if coords:
                prop.latitude, prop.longitude = coords
                summary["geocoded"] += 1
            else:
                summary["not_found"] += 1

            # Commit progressively so user doesn't lose pins if stopped or interrupted
            db.commit()
            _geocode_progress.update(
                done=index + 1,
                geocoded=summary["geocoded"],
                cached=summary["cached"],
                not_found=summary["not_found"],
                remaining=summary["remaining"],
            )
    finally:
        _geocode_progress.update(active=False)
    return summary
