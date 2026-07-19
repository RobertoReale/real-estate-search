"""Maintenance module to repair empty or incomplete properties and imported listings.

When properties were imported via email prior to extraction enhancements, they
often lacked `city`, `zone`, `image_url`, and descriptive `title`. This service
analyzes existing database text (email subjects, URLs, titles, search profiles)
to instantly populate missing fields without requiring external web visits.

It also merges duplicate dashboard cards: `upsert_listing` (deduplicator.py)
already prevents a second Listing row for the same portal+portal_id, but that
key is not infallible — a scraper regression that mints a new portal_id for an
ad already tracked (URL renumbering, a re-crawled redirect) slips past it and
produces two Property cards pointing at the same real ad. Comparing the
listing URLs directly catches that case regardless of which portal_id each
side landed on.
"""

import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ImportedListing, Listing, ListingProfile, Property, SearchProfile
from . import geo_reference
from .deduplicator import _refresh_min_price

logger = logging.getLogger(__name__)

_STATUS_RANK = {"hidden": 3, "active": 2, "filtered": 1, "gone": 0}


def _normalize_listing_url(url: str) -> str:
    """Collapses cosmetic URL differences (scheme, www, trailing slash,
    tracking query string/fragment) so the same ad is recognized even when
    re-scraped with a different portal_id."""
    if not url:
        return ""
    u = url.strip().lower()
    u = re.sub(r"^https?://(www\.)?", "", u)
    u = u.split("?", 1)[0].split("#", 1)[0]
    return u.rstrip("/")


def _merge_property_into(db: Session, survivor: Property, dupe: Property) -> None:
    """Folds `dupe` into `survivor`: reassigns its listings, price history and
    any imported-listing back-reference, then deletes it. `survivor` is always
    the earlier-seen of the two (see merge_duplicate_listings), so it keeps
    its identity and only gains data the other side had and it didn't."""
    for listing in list(dupe.listings):
        listing.property = survivor
    for ph in list(dupe.price_history):
        ph.property = survivor
    db.query(ImportedListing).filter(ImportedListing.property_id == dupe.id).update(
        {"property_id": survivor.id}
    )

    survivor.first_seen_at = min(survivor.first_seen_at, dupe.first_seen_at)
    survivor.last_seen_at = max(survivor.last_seen_at, dupe.last_seen_at)
    # user-curated fields (invariant 10): union rather than overwrite, so
    # merging never silently discards a favorite or a note
    survivor.is_favorite = survivor.is_favorite or dupe.is_favorite
    if dupe.notes and dupe.notes.strip() and dupe.notes.strip() not in (survivor.notes or ""):
        survivor.notes = f"{survivor.notes}\n{dupe.notes}".strip() if survivor.notes else dupe.notes
    if not survivor.city and dupe.city:
        survivor.city = dupe.city
    if not survivor.zone and dupe.zone:
        survivor.zone = dupe.zone
    if not survivor.address and dupe.address:
        survivor.address = dupe.address
    if survivor.latitude is None and dupe.latitude is not None:
        survivor.latitude, survivor.longitude = dupe.latitude, dupe.longitude
    if survivor.rooms is None and dupe.rooms is not None:
        survivor.rooms = dupe.rooms
    if not survivor.floor and dupe.floor:
        survivor.floor = dupe.floor
    if survivor.sqm is None and dupe.sqm is not None:
        survivor.sqm = dupe.sqm
    if not survivor.image_url and dupe.image_url:
        survivor.image_url = dupe.image_url
    if is_bad_title(survivor.title) and not is_bad_title(dupe.title):
        survivor.title = dupe.title
    if survivor.source == "email" and dupe.source == "scan":
        survivor.source = "scan"  # invariant 19: never demote a scan-origin merge

    # hidden is sacred (invariant 5) and wins regardless of which side the
    # user hid; otherwise keep whichever status is more "alive"
    if _STATUS_RANK.get(dupe.status, 0) > _STATUS_RANK.get(survivor.status, 0):
        survivor.status = dupe.status
        survivor.filtered_reason = dupe.filtered_reason
        if survivor.status != "gone":
            # back among the living: a stale gone_at would keep truncating
            # days-on-market (same clearing scanner.py does on reactivation)
            survivor.gone_at = None

    db.delete(dupe)


def merge_duplicate_listings(db: Session) -> dict:
    """Finds Properties whose listings share an identical (normalized) portal
    URL and merges them into one. Returns counts of properties merged away and
    redundant Listing rows collapsed. Does not commit — the caller decides
    the transaction boundary."""
    summary = {"properties_merged": 0, "duplicate_listings_removed": 0}

    listings = list(db.scalars(select(Listing)))
    by_url: dict[str, list[Listing]] = {}
    for listing in listings:
        key = _normalize_listing_url(listing.url)
        if key:
            by_url.setdefault(key, []).append(listing)

    # union-find over property ids connected by a shared listing URL
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for group in by_url.values():
        prop_ids = {l.property_id for l in group}
        if len(prop_ids) > 1:
            ids = list(prop_ids)
            for other in ids[1:]:
                union(ids[0], other)

    components: dict[int, list[int]] = {}
    for pid in parent:
        components.setdefault(find(pid), []).append(pid)

    for group_ids in components.values():
        if len(group_ids) < 2:
            continue
        props = [p for p in (db.get(Property, pid) for pid in group_ids) if p is not None]
        if len(props) < 2:
            continue
        # earliest-seen property keeps its identity; the rest are folded in
        props.sort(key=lambda p: (p.first_seen_at, p.id))
        survivor, *dupes = props
        for dupe in dupes:
            logger.info(
                "Repair: merging duplicate property #%s into #%s (shared listing URL)",
                dupe.id,
                survivor.id,
            )
            _merge_property_into(db, survivor, dupe)
            summary["properties_merged"] += 1
        db.flush()
        db.refresh(survivor)
        # same path the scanner uses: if the merge lowered the minimum, a
        # PriceHistory row is recorded, keeping the "price_history[-1] is the
        # latest change" contract intact for the notifier and trend charts
        _refresh_min_price(db, survivor)

    # second pass: collapse redundant Listing rows left on the SAME property
    # (e.g. two portal_ids for the one ad that were already sharing a
    # property through other dedup criteria before this repair ran)
    db.flush()
    by_prop_url: dict[tuple[int, str], list[Listing]] = {}
    for listing in db.scalars(select(Listing)):
        key = _normalize_listing_url(listing.url)
        if key:
            by_prop_url.setdefault((listing.property_id, key), []).append(listing)

    for group in by_prop_url.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda l: (l.description == "", l.first_seen_at))
        keeper, *extra = group
        for listing in extra:
            if listing.image_url and not keeper.image_url:
                keeper.image_url = listing.image_url
            if listing.description and not keeper.description:
                keeper.description = listing.description
            keeper.first_seen_at = min(keeper.first_seen_at, listing.first_seen_at)
            keeper.last_seen_at = max(keeper.last_seen_at, listing.last_seen_at)
            # the doomed row carries the provenance of the searches that found
            # it: hand it to the keeper, or deleting one of those searches
            # "with its results" would spare a listing it did produce
            keeper_profiles = {link.profile_id for link in keeper.profile_links}
            for link in list(listing.profile_links):
                if link.profile_id not in keeper_profiles:
                    db.add(
                        ListingProfile(
                            listing_id=keeper.id,
                            profile_id=link.profile_id,
                            first_seen_at=link.first_seen_at,
                        )
                    )
                    keeper_profiles.add(link.profile_id)
            db.delete(listing)
            summary["duplicate_listings_removed"] += 1

    return summary


def _detect_city(text: str, profile_cities: tuple[str, ...] | list[str] = ()) -> str:
    """City mentioned in `text`, or "" — the layered detector of geo_reference:
    the user's own monitored cities first, then the full ISTAT comuni index.
    Never a default (a wrong city blocks cross-portal merges, invariant 1)."""
    return geo_reference.detect_city(text, profile_cities)


def _agency_prefixes() -> list[str]:
    """Agency names whose branding pollutes imported titles. Data-driven
    (settings `repair_agency_prefixes`, seeded with the agencies met so far)
    so a user in another market extends the list without a code change."""
    from ..config import load_settings

    values = load_settings().get("repair_agency_prefixes") or []
    return [str(v).strip().casefold() for v in values if str(v).strip()]


# The structural shape of a portal auto-title: optional generic property words,
# "in vendita/affitto", optionally anchored to place names. "Appartamento in
# vendita", "Residenziale in affitto a Milano, Milano" and their equivalents
# for ANY comune all match; a title carrying real information does not.
_PLACEHOLDER_RE = re.compile(
    r"^(?:(?:immobile|residenziale|appartamento|casa|attico|villa|loft"
    r"|monolocale|bilocale|trilocale|quadrilocale)\s+)*"
    r"(?:in\s+)?(?:vendita|affitto)"
    r"(?:\s+a\s+(?P<place>.+))?$"
)


def _is_placeholder_phrase(text: str) -> bool:
    """Does `text` match the auto-generated "<generic> in vendita a <comune>"
    shape? The place tail, when present, must be real comuni (comma-separated,
    the portal loves "a Milano, Milano") — an unknown tail means the title
    carries information and must be kept (fail towards keeping)."""
    normalized = " ".join((text or "").casefold().strip(" .-").split())
    if not normalized:
        return False
    m = _PLACEHOLDER_RE.match(normalized)
    if not m:
        return False
    place = m.group("place")
    if not place:
        return True
    index = geo_reference.load_comuni()
    segments = [s.strip() for s in place.split(",") if s.strip()]
    return bool(segments) and all(seg in index for seg in segments)


def is_placeholder_zone(zone: str) -> bool:
    """'In vendita a Milano' (or any comune) stored as a zone is portal
    boilerplate, not a place name."""
    z = " ".join((zone or "").casefold().split())
    m = _PLACEHOLDER_RE.match(z)
    if not m or not m.group("place"):
        return False
    index = geo_reference.load_comuni()
    segments = [s.strip() for s in m.group("place").split(",") if s.strip()]
    return bool(segments) and all(seg in index for seg in segments)


def is_bad_title(title: str) -> bool:
    if not title:
        return True
    tl = " ".join(title.casefold().strip(" .-").split())
    if tl in ("", "n/a"):
        return True
    if _is_placeholder_phrase(tl):
        return True
    if "ti propone" in tl:
        return True
    for prefix in _agency_prefixes():
        if re.search(rf"(?<!\w){re.escape(prefix)}(?!\w)", tl):
            return True
    return False


def _strip_agency_prefix(raw: str) -> str:
    """Strip a leading "AGENCY NAME: " from an email subject/title.

    Generic shape, not a fixed alternation of named agencies: a configured
    agency name (settings seed) always strips; otherwise a short title-case or
    ALL-CAPS prefix does — that is how agencies brand their alert subjects,
    while a real title's leading segment ("Attico: vista duomo") stays lower
    after the first word and is kept.
    """
    m = re.match(r"^([^:\r\n]{1,60}):\s*", raw)
    if not m:
        return raw
    prefix = m.group(1).strip()
    prefix_cf = prefix.casefold()
    if any(re.search(rf"(?<!\w){re.escape(a)}(?!\w)", prefix_cf) for a in _agency_prefixes()):
        return raw[m.end() :]
    words = prefix.split()
    alpha_words = [w for w in words if w[:1].isalpha()]
    if 2 <= len(words) <= 4 and alpha_words and all(w[:1].isupper() for w in alpha_words):
        return raw[m.end() :]
    if len(words) == 1 and prefix.isupper() and len(prefix) >= 4:
        return raw[m.end() :]
    return raw


def _extract_zone_and_title(subject: str, city: str, orig_title: str) -> tuple[str, str]:
    raw = subject if subject and len(subject) > len(orig_title) else (orig_title or subject or "")
    cleaned = _strip_agency_prefix(raw)
    cleaned = re.sub(
        r"\b(?:ti propone un immobile per la tua ricerca\s*:?|ti propone\s*:?|\s+:\s+Residenziale in vendita)\s*",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"\s*\|\s*(?:Immobiliare\.it|Idealista|Casa\.it).*$", "", cleaned, flags=re.I)

    lines = [l.strip() for l in re.split(r"[\r\n]+", cleaned) if l.strip()]
    detail = lines[-1] if lines else cleaned
    detail = " ".join(detail.split()).strip(" :-")

    zone = ""
    title = orig_title
    if detail and not _is_placeholder_phrase(detail):
        parts = [p.strip() for p in re.split(r"[-–—]", detail) if p.strip()]
        if len(parts) >= 2:
            if any(
                w in parts[-1].casefold()
                for w in ("locale", "attico", "villa", "loft", "casa", "appartamento")
            ):
                zone = parts[0]
                title = f"{parts[-1]} - {parts[0]}, {city or 'Italia'}"
            elif any(
                w in parts[0].casefold()
                for w in ("locale", "attico", "villa", "loft", "casa", "appartamento")
            ):
                zone = parts[-1]
                title = f"{parts[0]} - {parts[-1]}, {city or 'Italia'}"
            else:
                title = f"{detail}, {city or 'Italia'}"
        else:
            title = f"{detail}, {city or 'Italia'}"

    if is_bad_title(title):
        # no literal city default: an unknown location stays generic rather
        # than being stamped with somebody else's city
        where = zone or city
        title = f"Immobile residenziale - {where}" if where else "Immobile residenziale"

    return zone[:100], title[:150]


def repair_empty_listings_locally(db: Session) -> dict:
    """Repairs all properties and listings currently lacking city, zone, title, or
    image_url, and merges dashboard cards that turn out to be the same ad
    (see merge_duplicate_listings)."""
    summary = {"properties_fixed": 0, "listings_fixed": 0, "images_recovered": 0}
    summary.update(merge_duplicate_listings(db))

    # The user's own monitored searches are the first city-detection layer
    # (geo_reference's design): each profile's URL already encodes its city,
    # and those names are always right for this user's market.
    from .email_import import profile_criteria

    profiles = list(db.scalars(select(SearchProfile).where(SearchProfile.is_active.is_(True))))
    profile_cities: list[str] = []
    for p in profiles:
        try:
            c = profile_criteria(p, []).get("city") or ""
        except Exception:
            c = ""
        c = c or _detect_city(p.search_url or p.name)
        if c and c not in profile_cities:
            profile_cities.append(c)
    default_city = profile_cities[0] if profile_cities else ""

    properties = list(db.scalars(select(Property)))
    for prop in properties:
        changed = False

        imp = db.scalar(select(ImportedListing).where(ImportedListing.property_id == prop.id))

        # 1. Recover city
        if not prop.city or prop.city == "N/A" or prop.city == "":
            c = ""
            for listing in prop.listings:
                c = _detect_city(listing.description or "", profile_cities) or _detect_city(
                    listing.url or "", profile_cities
                )
                if c:
                    break
            if not c and imp:
                c = _detect_city(imp.email_subject or "", profile_cities) or _detect_city(
                    imp.title or "", profile_cities
                )
            if not c:
                c = default_city
            if c:
                prop.city = c
                changed = True

        # 2. Recover zone & title
        if (
            is_bad_title(prop.title)
            or not prop.zone
            or prop.zone == ""
            or is_placeholder_zone(prop.zone)
        ):
            subj = imp.email_subject if imp else ""
            zone, new_title = _extract_zone_and_title(subj, prop.city, prop.title)
            if zone and (not prop.zone or is_placeholder_zone(prop.zone)):
                prop.zone = zone
                changed = True
            elif prop.zone and is_placeholder_zone(prop.zone):
                prop.zone = ""
                changed = True
            # rewrite the title only when the current one is bad: "different
            # from before" is not an improvement — the len(parts) < 2 branch of
            # _extract_zone_and_title returns the existing title with the city
            # appended, so writing on mere difference made every repair run
            # append the city once more ("…, Milano, Milano, Milano")
            if is_bad_title(prop.title):
                if new_title and not is_bad_title(new_title):
                    prop.title = new_title
                    changed = True
                else:
                    where = prop.zone or prop.city
                    prop.title = (
                        f"Immobile residenziale - {where}" if where else "Immobile residenziale"
                    )
                    changed = True

        # 3. Recover image_url across property, listings, and imported_listings
        for listing in prop.listings:
            l_changed = False
            if not prop.image_url and listing.image_url:
                prop.image_url = listing.image_url
                changed = True
                summary["images_recovered"] += 1
            elif not listing.image_url and prop.image_url:
                listing.image_url = prop.image_url
                l_changed = True
            elif not prop.image_url and imp and imp.image_url:
                prop.image_url = imp.image_url
                listing.image_url = imp.image_url
                changed = True
                l_changed = True
                summary["images_recovered"] += 1

            if l_changed:
                summary["listings_fixed"] += 1

        if changed:
            summary["properties_fixed"] += 1

    db.commit()
    logger.info("repair_empty_listings_locally completed: %s", summary)
    return summary
