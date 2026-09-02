"""Filling in the map coordinates a listing did not arrive with.

~70% of Immobiliare listings arrive with no lat/lng, so the map view starts
mostly empty. Three things fill it in, in the order that costs least first, and
the order is the whole design:

1. **What the ad already carried.** Free and exact. `deduplicator` writes it,
   this module never sees it, and every coordinate field a parser can read is
   held to that by `test_scrapers.py` — a portal that sends a pin the app then
   pays Nominatim to re-derive is the cheapest bug there is.
2. **What is already known offline** (`resolve_offline`). A street this
   database has geocoded once answers every other listing on it for nothing,
   and a district that already holds pins can place a listing inside itself.
   No request, so a scan can do it every time.
3. **Nominatim** (`geocode_missing_properties`), paced at one request a second
   and bounded per run. A scan triggers it over what it has just imported; the
   maintenance action still runs it over everything on demand.

Three rules keep it safe, cheap and honest:

* **Fail-open, never a wrong pin.** A lookup that fails or is ambiguous leaves
  the property's coordinates untouched. A missing pin is fine; a pin in the
  wrong place is a lie the user would act on.
* **Cache everything, including misses.** Every query is remembered in
  `GeocodeCache` (a NULL result is a *negative* cache), so the same
  "via Dante, Milano" is never asked twice — that is what lets a paced batch
  stay under Nominatim's 1-request-per-second policy, and what makes layer 2
  answer most of a city for free.
* **Say how precise the pin is.** A district centre is not an address, and
  drawing the two the same way is an approximation presented as a location —
  the one kind of error the user cannot catch. Every write records where the
  pin came from in `Property.coordinate_source`; `APPROXIMATE_SOURCES` below is
  the single list of which of those are not addresses.

The outbound HTTP call lives in `_nominatim_lookup` alone, so tests drive the
whole cache/batch logic with it mocked — no network, fully reproducible
(invariant 17's spirit).
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
from . import geo_reference

logger = logging.getLogger(__name__)

# Nominatim's usage policy: at most one request per second, and a real
# User-Agent identifying the app. Both are non-negotiable for the public
# instance; a self-hosted one does not care but the pause is harmless.
PACE_SECONDS = 1.0

# The vocabulary of `Property.coordinate_source`, written down once. The models
# module documents what each value means for a reader of the schema; the
# authority on which of them are *approximations* is here, next to the code that
# creates them, so a fourth source cannot be added without deciding.
SOURCE_PORTAL = "portal"  # the ad carried its own pin
SOURCE_ADDRESS = "address"  # this property's own street, resolved
SOURCE_ZONE = "zone"  # the middle of its district

# A pin here is somewhere in the right area and nowhere in particular. The map
# draws it differently, and a portal pin overwrites it. There is deliberately no
# comune-wide equivalent: a bare city would drop every unplaceable listing on
# one downtown pin, which is why `build_located_queries` has never built a query
# out of one either.
APPROXIMATE_SOURCES = frozenset({SOURCE_ZONE})

# How many exact pins a district needs before their mean counts as its centre.
# Two, for a reason that is not statistical: the mean of two points is neither
# of them, so an approximate pin can never land exactly on a real address and be
# read as one. With a single pin it would, which is the confusion the whole
# `coordinate_source` column exists to prevent.
ZONE_CENTRE_MIN_PINS = 2


def is_approximate(source: str | None) -> bool:
    """Is a pin from `source` an area rather than an address?

    An unknown source ("") answers False: it is a pin written before this column
    existed, and calling it approximate would put a warning on the map for every
    property in an upgraded database. Only what this code can prove is an
    approximation is labelled as one.
    """
    return (source or "") in APPROXIMATE_SOURCES


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


def is_valid_coordinate_for_city(lat: float | None, lon: float | None, city: str) -> bool:
    """Checks if (lat, lon) falls roughly inside Italy and near the target city.

    Name and signature kept from the hand-drawn-boxes era so callers and tests
    don't churn; the actual judgment now comes from the bundled comuni
    gazetteer (geo_reference), which covers every Italian municipality instead
    of 26 remembered ones.
    """
    return geo_reference.is_plausible_coordinate(lat, lon, city)


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


def build_located_queries(prop: Property) -> list[tuple[str, str]]:
    """The queries to try for a property, each with the precision it would buy.

    Same prioritized list `build_queries` has always returned — full address
    with house number, then the street without it, then the zone — paired with
    the `SOURCE_*` the resolved pin would deserve. The pairing is the point: the
    fallback to the zone was always there and always produced a district centre
    labelled exactly like a street address, so a property whose address could
    not be resolved ended up on the map claiming a precision nobody had.
    """
    city = (prop.city or "").strip()
    if not city:
        return []

    queries: list[tuple[str, str]] = []
    seen = set()

    def _add(q: str, source: str) -> None:
        key = _normalize(q)
        if key and key not in seen:
            seen.add(key)
            queries.append((q, source))

    address = (prop.address or "").strip()
    if address:
        _add(f"{address}, {city}, Italia", SOURCE_ADDRESS)
        clean_addr = _clean_street_name(address)
        if clean_addr and len(clean_addr) >= 3 and _normalize(clean_addr) != _normalize(address):
            _add(f"{clean_addr}, {city}, Italia", SOURCE_ADDRESS)

    zone = (prop.zone or "").strip()
    from .listing_text import is_placeholder_zone

    if zone and not is_placeholder_zone(zone):
        clean_zone = _clean_street_name(zone)
        _add(f"{zone}, {city}, Italia", SOURCE_ZONE)
        if clean_zone and len(clean_zone) >= 3 and _normalize(clean_zone) != _normalize(zone):
            _add(f"{clean_zone}, {city}, Italia", SOURCE_ZONE)

    return queries


def build_queries(prop: Property) -> list[str]:
    """The same list as `build_located_queries`, without the precisions.

    Kept for the callers that only need something to look up — the commute
    resolver and the negative-cache repair — so neither has to know that a
    query carries a precision at all.
    """
    return [query for query, _ in build_located_queries(prop)]


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
    for query, source in build_located_queries(prop):
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
            prop.coordinate_source = source
            db.commit()
            return coords
        # Pace only between genuine network lookups; a cached miss is free.
        if not cached:
            time.sleep(PACE_SECONDS)
    return None


# ---------------------------------------------------------------------------
# Layer 2: what is already known, without a single request
# ---------------------------------------------------------------------------


def _zone_centres(db: Session) -> dict[tuple[str, str], tuple[float, float]]:
    """The middle of every district this database can already draw.

    Built from the properties that carry an *exact* pin: a district holding
    `ZONE_CENTRE_MIN_PINS` of them knows roughly where it is, and that is enough
    to place a listing whose own address nobody has resolved. It is the same
    trick the cache plays with streets, one level coarser, and it is why a first
    scan can put most of its listings on the map for nothing.

    Approximate pins are excluded from the input on purpose: averaging centroids
    into new centroids would let one district's guess drift into the next one's
    and there would be no way back to a real coordinate.
    """
    rows = db.scalars(
        select(Property)
        .where(Property.latitude.is_not(None))
        .where(Property.city != "")
        .where(Property.zone != "")
    ).all()
    grouped: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for prop in rows:
        if is_approximate(prop.coordinate_source):
            continue
        if prop.latitude is None or prop.longitude is None:
            continue
        key = (_normalize(prop.city), _normalize(prop.zone))
        grouped.setdefault(key, []).append((prop.latitude, prop.longitude))
    return {
        key: (sum(p[0] for p in pins) / len(pins), sum(p[1] for p in pins) / len(pins))
        for key, pins in grouped.items()
        if len(pins) >= ZONE_CENTRE_MIN_PINS
    }


def _place_offline(
    db: Session, prop: Property, zone_centres: dict[tuple[str, str], tuple[float, float]]
) -> tuple[float, float, str] | None:
    """(lat, lng, source) for one property from local knowledge alone, or None.

    Best precision first, and each layer is a fact this database already holds:

    1. **a lookup already paid for.** `GeocodeCache` is keyed by the query
       string, so "via dei tigli 4, milano, italia" resolved for one listing
       answers every other listing at that address, and the street-level
       fallback answers the whole street. This is the layer that does the work.
    2. **the district's own pins.** Coarser, and honestly labelled as such.

    And then it stops. A listing this cannot place keeps no pin and goes to
    Nominatim, which is the whole reason the network layer runs *after* this one
    — a comune-wide fallback here would place everything, badly, and the paced
    lookup that could have found the real address would never get a candidate.

    Nothing here opens a socket, and nothing here writes a negative cache row:
    a query this pass cannot answer is left exactly as the network layer would
    find it.
    """
    city = (prop.city or "").strip()
    if not city:
        return None

    for query, source in build_located_queries(prop):
        row = db.scalar(select(GeocodeCache).where(GeocodeCache.query == _normalize(query)))
        if row is None or row.latitude is None or row.longitude is None:
            continue
        if is_valid_coordinate_for_city(row.latitude, row.longitude, city):
            return row.latitude, row.longitude, source

    zone = (prop.zone or "").strip()
    if not zone:
        return None
    from .listing_text import is_placeholder_zone

    if is_placeholder_zone(zone):
        return None
    centre = zone_centres.get((_normalize(city), _normalize(zone)))
    if centre and is_valid_coordinate_for_city(centre[0], centre[1], city):
        return centre[0], centre[1], SOURCE_ZONE
    return None


def resolve_offline(db: Session, property_ids: set[int] | None = None) -> dict:
    """Place every property this database can already place, with no network.

    Runs before the paced Nominatim batch and, unlike it, is free — so a scan
    calls it every time rather than leaving the map empty until somebody clicks
    a maintenance button. Fail-open like the rest of the module: a property it
    cannot place keeps no pin at all, and the network layer gets its turn.

    Returns what it did, split by precision, because "68 placed" and "68 placed,
    12 of them only to their district" are different sentences and the caller
    reports the second one.
    """
    stmt = (
        select(Property)
        .where(Property.latitude.is_(None))
        .where(Property.city != "")
        .order_by(Property.id)
    )
    if property_ids is not None:
        stmt = stmt.where(Property.id.in_(property_ids))
    candidates = db.scalars(stmt).all()

    summary = {"scanned": len(candidates), "placed": 0, "exact": 0, "approximate": 0}
    if not candidates:
        return summary

    zone_centres = _zone_centres(db)
    for prop in candidates:
        found = _place_offline(db, prop, zone_centres)
        if found is None:
            continue
        prop.latitude, prop.longitude, prop.coordinate_source = found
        summary["placed"] += 1
        summary["approximate" if is_approximate(found[2]) else "exact"] += 1
    db.commit()
    if summary["placed"]:
        logger.info(
            "geocoder: placed %d properties offline (%d exact, %d approximate)",
            summary["placed"],
            summary["exact"],
            summary["approximate"],
        )
    return summary


def geocode_missing_properties(
    db: Session, max_calls: int | None = -1, property_ids: set[int] | None = None
) -> dict:
    """Fill in coordinates for properties that have an address/zone but no pin.

    When `max_calls` is -1 (default), it caps at `MAX_PER_CALL` for synchronous
    batches. When `max_calls` is None, it runs all remaining candidates without
    capping (`budget = float("inf")`), ideal for background progress execution.

    `property_ids` narrows the candidates to a named set, which is how a scan
    sweeps what it has just imported instead of re-attempting, every hour, the
    addresses Nominatim has already declined. The maintenance action passes
    nothing and still sees the whole database.
    """
    if not _geocode_run_lock.acquire(blocking=False):
        raise GeocoderError("A geocoding batch is already running: wait for it to finish")
    _geocode_cancel_event.clear()
    try:
        return _geocode_missing_properties_inner(db, max_calls, property_ids)
    finally:
        _geocode_run_lock.release()


def _geocode_missing_properties_inner(
    db: Session, max_calls: int | None = -1, property_ids: set[int] | None = None
) -> dict:
    from ..config import load_settings

    base_url = (
        load_settings().get("nominatim_url") or "https://nominatim.openstreetmap.org"
    ).strip()

    # Clear out any existing coordinates that fall clearly outside the property's city
    # (repairing old mis-geocodings like 'Via Tolmezzo, 2' -> Cernusco or 'Dergano' -> Torino).
    # Scoped like the candidates below: a scan repairs what it has just touched,
    # while the maintenance action still sweeps the whole database.
    repair_stmt = select(Property).where(Property.latitude.is_not(None)).where(Property.city != "")
    if property_ids is not None:
        repair_stmt = repair_stmt.where(Property.id.in_(property_ids))
    for p in db.scalars(repair_stmt).all():
        if not is_valid_coordinate_for_city(p.latitude, p.longitude, p.city):
            logger.info(
                "geocoder: clearing out-of-bounds coords for property #%s (%s: %s, %s)",
                p.id,
                p.city,
                p.latitude,
                p.longitude,
            )
            p.latitude, p.longitude = None, None
            p.coordinate_source = ""
    db.commit()

    stmt = (
        select(Property)
        .where(Property.latitude.is_(None))
        .where(Property.city != "")
        .where(or_(Property.address != "", Property.zone != ""))
        .order_by(Property.id)
    )
    if property_ids is not None:
        stmt = stmt.where(Property.id.in_(property_ids))
    candidates = db.scalars(stmt).all()

    summary = {
        "scanned": 0,
        "geocoded": 0,
        # of those, how many landed on a district centre rather than a street.
        # Counted separately because "40 properties placed" and "40 properties
        # placed, 31 of them only to the district" are different answers.
        "approximate": 0,
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

            queries = build_located_queries(prop)
            if not queries:
                _geocode_progress.update(done=index + 1)
                continue
            summary["scanned"] += 1

            coords = None
            source = ""
            was_cached = False
            try:
                for query, query_source in queries:
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
                        source = query_source
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
                # `source` says which of this property's queries answered: the
                # street, or the district it stands in. The batch has always
                # fallen back to the district and never said so.
                prop.coordinate_source = source
                summary["geocoded"] += 1
                if is_approximate(source):
                    summary["approximate"] += 1
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
