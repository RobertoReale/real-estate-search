"""Search Profile Validation & Deduplication.

Enforces uniqueness of monitored searches (`SearchProfile`) across the application.
Two searches are considered exactly equal (`ricerche esattamente uguali`) when
their normalized portal URL and normalized excluded keywords match.

It also answers the question that has to be asked *before* a search is saved:
will the URL about to be written actually search everything the user selected?
A zone that cannot survive the trip into a portal's URL grammar is not a scan
that fails — it is a scan that succeeds against a wider area and reports a
number, which is the failure nobody can see from the result.
"""

import logging
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ListingProfile, SearchProfile
from .filter_engine import parse_keywords_csv
from .search_builder import zone_id_list, zone_names

logger = logging.getLogger(__name__)


def normalize_profile_url(url: str) -> str:
    """Normalizes a portal search URL for exact duplicate comparison.

    Strips whitespace and trailing slashes, lowercases scheme/netloc/path,
    removes non-filtering/bookmark parameters (`id`, `imm_source`, `pag`, and
    the sort order), and sorts remaining query parameters alphabetically.

    The sort order belongs on that list for the same reason as `pag`: it decides
    how the answer is arranged, never what is in it, so the same search ranked
    two ways is one search. Left in, the day the builder started pinning
    newest-first every rebuilt URL would have stopped matching the profile it
    was rebuilt from — a duplicate the check could no longer see.
    """
    url_str = (url or "").strip()
    if not url_str:
        return ""
    try:
        parsed = urlparse(url_str)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/").lower()

        # Parse query params, filtering out tracking/pagination/ordering params
        ignore_params = {"id", "imm_source", "pag", "criterio", "ordine"}
        query_items = [
            (k, v)
            for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k.lower() not in ignore_params
        ]
        query_items.sort()
        query = urlencode(query_items) if query_items else ""

        return urlunparse((scheme, netloc, path, parsed.params, query, ""))
    except Exception:
        return url_str.rstrip("/").lower()


def zone_coverage_warnings(params: dict[str, Any]) -> list[str]:
    """Which of the selected zones the Immobiliare URL cannot carry, said now.

    Both cases below end the same way if nothing is said: a scan runs against a
    wider area than the one that was picked, answers 200, and reports a listing
    count that looks like a result. The user then meets the difference as
    "properties from somewhere else" weeks later — the report G.3 counts after
    the fact and this refuses to let happen silently in the first place.

    - **Several zone names and no ids.** Immobiliare's path holds exactly one
      zone, and turning a name into one of the portal's ids needs the live
      geography autocomplete, which the builder does not call. So the first
      name is searched and the rest are not. The way out is in the message,
      because it is the same click the user already knows: pick the zones on
      Immobiliare's own map and paste that link, which carries them as ids.
    - **More ids than one request can carry.** Named rather than assumed —
      `scrapers.immobiliare.MAX_ZONE_IDS` derives it from the request-line
      budget, and no real selection reaches it (see the comment there).

    Ids are never a loss on their own: they travel as repeated query params,
    all of them, beside the municipality the geography resolves.
    """
    from ..scrapers.immobiliare import MAX_ZONE_IDS

    names = zone_names(params.get("zone") or "", params.get("zones") or None)
    ids = zone_id_list(params.get("zone_ids") or [])
    out: list[str] = []
    if len(names) > 1 and not ids:
        out.append(
            f"Immobiliare's URL carries one zone name: only '{names[0]}' will be searched, "
            f"and the other {len(names) - 1} will not. Select the zones on Immobiliare's map "
            "and paste that link to keep every one of them."
        )
    if len(ids) > MAX_ZONE_IDS:
        out.append(
            f"{len(ids)} zones selected, more than the {MAX_ZONE_IDS} an Immobiliare search "
            "URL can carry. Split them across several monitored searches."
        )
    return out


def normalize_profile_keywords(csv_str: str) -> str:
    """Normalizes excluded keywords: lowercased, sorted, deduplicated CSV."""
    keywords = sorted({k.lower() for k in parse_keywords_csv(csv_str)})
    return ",".join(keywords)


def check_duplicate_profile(
    db: Session, search_url: str, excluded_keywords: str, exclude_profile_id: int | None = None
) -> SearchProfile | None:
    """Returns an existing SearchProfile with identical normalized URL and keywords, or None."""
    norm_url = normalize_profile_url(search_url)
    norm_kw = normalize_profile_keywords(excluded_keywords)

    query = select(SearchProfile)
    if exclude_profile_id is not None:
        query = query.where(SearchProfile.id != exclude_profile_id)

    for p in db.scalars(query):
        if (
            normalize_profile_url(p.search_url) == norm_url
            and normalize_profile_keywords(p.excluded_keywords) == norm_kw
        ):
            return p
    return None


def deduplicate_search_profiles(db: Session) -> int:
    """Finds existing exact duplicate SearchProfiles in the database, reassigns
    their listing links to the oldest canonical profile, and removes the duplicates.
    """
    profiles = list(db.scalars(select(SearchProfile).order_by(SearchProfile.id)))
    groups: dict[tuple[str, str], list[SearchProfile]] = {}
    for p in profiles:
        key = (
            normalize_profile_url(p.search_url),
            normalize_profile_keywords(p.excluded_keywords),
        )
        groups.setdefault(key, []).append(p)

    removed_count = 0
    for _key, group in groups.items():
        if len(group) <= 1:
            continue
        canonical = group[0]
        duplicates = group[1:]
        logger.info(
            "Found %d duplicates for search profile '%s' (id=%d). Merging into id=%d...",
            len(duplicates),
            canonical.name,
            canonical.id,
            canonical.id,
        )
        for dup in duplicates:
            for link in list(dup.listing_links):
                existing = db.get(ListingProfile, (link.listing_id, canonical.id))
                if existing:
                    db.delete(link)
                else:
                    link.profile_id = canonical.id
            db.delete(dup)
            removed_count += 1

    if removed_count > 0:
        db.commit()
        logger.info("Successfully deduplicated %d search profiles.", removed_count)
    return removed_count
