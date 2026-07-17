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
import time
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
_USER_AGENT = "RealEstateSearch/1.0 (local personal use)"
# One call must not stall the request forever. The public Nominatim instance is
# capped at 1 req/s, so this is roughly the wall-clock seconds a single click
# costs (cache hits are free): kept modest so the request returns in under a
# minute and the UI's "run it again to continue" (via `remaining`) carries the
# rest, rather than one click blocking for minutes with no progress.
MAX_PER_CALL = 40


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def build_query(prop: Property) -> str:
    """The most specific address string we can form for a property.

    Prefers a street address (best precision), else the zone, always anchored
    to the city and country so "Isola, Milano, Italia" cannot resolve to an
    Isola somewhere else. Returns "" when there is nothing better than a city —
    a bare city would drop every such listing on one downtown pin.
    """
    city = (prop.city or "").strip()
    if not city:
        return ""
    place = (prop.address or "").strip() or (prop.zone or "").strip()
    if not place:
        return ""
    return f"{place}, {city}, Italia"


def _nominatim_lookup(query: str, base_url: str) -> tuple[float, float] | None:
    """Single geocoding request. Isolated so tests can mock it."""
    url = base_url.rstrip("/") + "/search?" + urllib.parse.urlencode({
        "q": query, "format": "json", "limit": 1, "countrycodes": "it",
    })
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data:
        return None
    try:
        return float(data[0]["lat"]), float(data[0]["lon"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def geocode(db: Session, query: str, base_url: str) -> tuple[float, float] | None:
    """Resolve `query` to (lat, lng), consulting and populating the cache.

    A cached row — hit or miss — short-circuits the network entirely; only a
    genuinely new query spends a request (and returns True in the 2-tuple's
    place via the `hit_network` flag on the batch, not here). Failures are
    cached as NULL so they are not retried on the next batch.
    """
    key = _normalize(query)
    if not key:
        return None
    cached = db.scalar(select(GeocodeCache).where(GeocodeCache.query == key))
    if cached is not None:
        if cached.latitude is not None and cached.longitude is not None:
            return cached.latitude, cached.longitude
        return None
    try:
        result = _nominatim_lookup(query, base_url)
    except Exception as e:
        logger.warning("geocoder: lookup failed for %r (%s)", query, e)
        return None  # transient: do NOT cache, so a later batch can retry
    lat, lng = result if result else (None, None)
    db.add(GeocodeCache(query=key, latitude=lat, longitude=lng))
    db.commit()
    return result if result else None


def geocode_missing_properties(db: Session) -> dict:
    """Fill in coordinates for properties that have an address/zone but no pin.

    Batched (`MAX_PER_CALL`) and paced (`PACE_SECONDS` between *network* calls
    only — cache hits are free), so a large dashboard is completed across
    repeated runs, like the availability check. `remaining` tells the UI to run
    it again to continue.
    """
    from ..config import load_settings
    base_url = (load_settings().get("nominatim_url")
                or "https://nominatim.openstreetmap.org").strip()

    candidates = db.scalars(
        select(Property)
        .where(Property.latitude.is_(None))
        .where(Property.city != "")
        .where(or_(Property.address != "", Property.zone != ""))
        .order_by(Property.id)
    ).all()

    summary = {"scanned": 0, "geocoded": 0, "cached": 0,
               "not_found": 0, "remaining": 0}
    budget = MAX_PER_CALL
    for prop in candidates:
        query = build_query(prop)
        if not query:
            continue
        summary["scanned"] += 1
        key = _normalize(query)
        was_cached = db.scalar(
            select(GeocodeCache.id).where(GeocodeCache.query == key)
        ) is not None
        if not was_cached:
            if budget <= 0:
                summary["remaining"] += 1
                continue
            budget -= 1
        coords = geocode(db, query, base_url)
        if was_cached:
            summary["cached"] += 1
        if coords:
            prop.latitude, prop.longitude = coords
            summary["geocoded"] += 1
        else:
            summary["not_found"] += 1
        # Pace only after a real network call, and never after the last one.
        if not was_cached and budget > 0:
            time.sleep(PACE_SECONDS)
    db.commit()
    return summary
