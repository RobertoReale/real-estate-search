"""Deduplication & Matching Engine.

Recognizes when two listings (even across different portals or agencies) refer
to the same property and merges them under a single Property, preserving
price history.

Philosophy: **it is far better to show the same house twice than to merge two
different houses.** A false merge hides a property from the user and pollutes
the price history; a missed merge only costs one extra card.

Why location proof (coordinates or street+house number) is required: in a city like
Milan there are hundreds of three-room apartments around ~100 sqm priced at ~450,000 €,
so comparing city + rooms + sqm + price alone merges completely different
properties (and by transitivity chains them into ever-larger groups).

A listing is merged into an existing Property only if **all** these
conditions hold true:
  * compatible surface area (±5%) — mandatory;
  * same number of rooms (when known on both sides);
  * price within ±5% of every already-merged listing (when known);
  * location proof: coordinates within 60 m **OR** exact same street and
    house number in the same municipality.
"""
import logging
import math
import re
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Listing, PriceHistory, Property
from ..scrapers.base import RawListing

logger = logging.getLogger(__name__)

COORD_MAX_METERS = 60
SQM_TOLERANCE = 0.05
PRICE_TOLERANCE = 0.05


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _within(a: float | None, b: float | None, tolerance: float) -> bool:
    if not a or not b:
        return False
    return abs(a - b) / max(a, b) <= tolerance


def _normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(text.split())


def street_and_civic(address: str) -> tuple[str, str] | None:
    """"Via Val Gardena, 17" -> ("via val gardena", "17").

    Without a house number, the address is not sufficient location proof
    (a street in Milan can be kilometers long), so it returns None.
    """
    norm = _normalize_text(address)
    if not norm:
        return None
    tokens = norm.split()
    civics = [t for t in tokens if t.isdigit()]
    if not civics:
        return None
    civic = civics[-1]
    street = " ".join(t for t in tokens if not t.isdigit()).strip()
    if not street:
        return None
    return street, civic


def _same_address(raw: RawListing, prop: Property) -> bool:
    if not raw.city or not prop.city:
        return False
    if raw.city.strip().lower() != prop.city.strip().lower():
        return False
    a, b = street_and_civic(raw.address), street_and_civic(prop.address)
    return a is not None and a == b


def _same_coordinates(raw: RawListing, prop: Property) -> bool:
    if not (raw.latitude and raw.longitude and prop.latitude and prop.longitude):
        return False
    return _haversine_m(
        raw.latitude, raw.longitude, prop.latitude, prop.longitude
    ) <= COORD_MAX_METERS


def _price_compatible(raw: RawListing, prop: Property) -> bool:
    """Price must be close to EVERY already-merged listing.

    Price is mandatory on both sides: without it, in a building of
    40 sqm studio apartments, every unit would look like the exact same one.
    Comparing against a single listing of the group (any anchor: the minimum,
    the newest, "at least one") allows progressive drift — 100k merges 105k,
    105k merges 110.25k, and the group walks away from its original price
    band. Requiring compatibility with all members bounds the group's spread
    to the tolerance itself.
    """
    if not raw.price:
        return False
    prices = [l.price for l in prop.listings if l.price]
    if not prices:
        return False
    return all(_within(raw.price, p, PRICE_TOLERANCE) for p in prices)


def _floor_compatible(raw: RawListing, prop: Property) -> bool:
    """Two apartments on different floors cannot be the same property."""
    a, b = (raw.floor or "").strip().lower(), (prop.floor or "").strip().lower()
    if not a or not b:
        return True
    return a == b


def _matches_property(raw: RawListing, prop: Property) -> bool:
    # 1. surface: mandatory and strict
    if not _within(raw.sqm, prop.sqm, SQM_TOLERANCE):
        return False
    # 2. rooms: if known on both sides, must match
    if raw.rooms and prop.rooms and raw.rooms != prop.rooms:
        return False
    # 3. floor: if known on both sides, must match
    if not _floor_compatible(raw, prop):
        return False
    # 4. price: known on both sides and consistent with every already-merged listing
    if not _price_compatible(raw, prop):
        return False
    # 5. location proof: nearby coordinates or exact same street + house number
    return _same_coordinates(raw, prop) or _same_address(raw, prop)


def _fingerprint(raw: RawListing) -> str:
    parts = [
        (raw.city or "?").lower(),
        str(raw.rooms or "?"),
        str(int(raw.sqm)) if raw.sqm else "?",
    ]
    return "|".join(parts)


def _refresh_min_price(db: Session, prop: Property) -> bool:
    """Recalculates minimum price across all listings of the Property and, if
    changed, records the variation in price history.

    Returns True only if the *minimum* actually changed: this is the signal
    used for notifications. The individual listing price is not enough — if the
    most expensive (non-minimum) listing changes price, the "house price" for
    the user hasn't changed, and notifying by reading the last history row
    would show an old and misleading change.
    """
    prices = [l.price for l in prop.listings if l.price]
    new_min = min(prices) if prices else None
    changed = bool(
        new_min and prop.current_min_price and new_min != prop.current_min_price
    )
    if changed:
        db.add(PriceHistory(
            property_id=prop.id,
            old_price=prop.current_min_price,
            new_price=new_min,
        ))
    if prop.first_price is None:
        prop.first_price = new_min
    prop.current_min_price = new_min
    return changed


def _find_matching_property(db: Session, raw: RawListing) -> Property | None:
    """Searches among Properties in the same city (the only ones that can
    match, since both location proofs require or imply it)."""
    # never merge across contracts: the same physical house can be listed
    # both for sale and for rent, and those are two distinct records for
    # the user (different price scale, different notifications)
    query = select(Property).where(
        Property.status != "gone", Property.contract == raw.contract
    )
    if raw.city:
        query = query.where(Property.city.ilike(raw.city.strip()))
    for candidate in db.scalars(query):
        if _matches_property(raw, candidate):
            return candidate
    return None


def upsert_listing(
    db: Session, raw: RawListing, *, source: str = "scan"
) -> tuple[Property, bool, bool]:
    """Inserts or updates a listing.

    `source` records how a *newly created* property first entered the
    dashboard ("scan" for a monitored search, "email" for an inbox import).
    A property already stored as email-origin is upgraded to "scan" the moment
    a monitored scan re-finds it, so "email" keeps meaning "only ever seen via
    the inbox" — never downgraded, so an email import merging into a
    scan-origin property leaves it "scan".

    Returns (property, is_new_property, price_changed), where price_changed
    indicates that the *minimum* price of the Property changed (see
    _refresh_min_price): when True, the last row in price_history is
    always the newly recorded change.
    """
    now = datetime.now(timezone.utc)

    existing = db.scalar(
        select(Listing).where(
            Listing.portal == raw.portal, Listing.portal_id == raw.portal_id
        )
    )
    if existing:
        prop = existing.property
        # a portal ad is either sale or rent, never both, so raw.contract is
        # authoritative: this heals DBs migrated with the "sale" default
        # even though the profile that owns them is a rental search
        if prop.contract != raw.contract:
            prop.contract = raw.contract
        if source == "scan" and prop.source == "email":
            prop.source = "scan"  # a monitored search now covers it
        if raw.price:
            existing.price = raw.price
        if raw.description:
            existing.description = raw.description
        if raw.image_url and not existing.image_url:
            existing.image_url = raw.image_url
        existing.last_seen_at = now
        prop.last_seen_at = now
        price_changed = _refresh_min_price(db, prop)
        db.flush()
        return prop, False, price_changed

    prop = _find_matching_property(db, raw)
    if prop is not None:
        logger.info(
            "Dedup: listing %s/%s merged into property #%s",
            raw.portal, raw.portal_id, prop.id,
        )

    is_new = prop is None
    if is_new:
        prop = Property(
            fingerprint=_fingerprint(raw),
            title=raw.title,
            city=raw.city,
            zone=raw.zone,
            address=raw.address,
            latitude=raw.latitude,
            longitude=raw.longitude,
            rooms=raw.rooms,
            floor=raw.floor,
            sqm=raw.sqm,
            contract=raw.contract,
            image_url=raw.image_url,
            source=source,
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(prop)
        db.flush()
    else:
        if source == "scan" and prop.source == "email":
            prop.source = "scan"  # a monitored search now covers it
        # enriches the Property with any missing data
        if not prop.title and raw.title:
            prop.title = raw.title
        if prop.latitude is None and raw.latitude is not None:
            prop.latitude, prop.longitude = raw.latitude, raw.longitude
        if not prop.address and raw.address:
            prop.address = raw.address
        if prop.rooms is None and raw.rooms is not None:
            prop.rooms = raw.rooms
        if not prop.image_url and raw.image_url:
            prop.image_url = raw.image_url
        prop.last_seen_at = now

    listing = Listing(
        property_id=prop.id,
        portal=raw.portal,
        portal_id=raw.portal_id,
        url=raw.url,
        price=raw.price,
        agency=raw.agency,
        description=raw.description,
        image_url=raw.image_url,
        first_seen_at=now,
        last_seen_at=now,
    )
    db.add(listing)
    db.flush()
    db.refresh(prop)
    # if the newly merged listing is cheaper, the minimum drops:
    # the change goes into history and notification ("costs less elsewhere")
    price_changed = _refresh_min_price(db, prop)
    db.flush()
    return prop, is_new, price_changed
