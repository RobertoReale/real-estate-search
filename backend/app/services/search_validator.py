"""Search Profile Validation & Deduplication.

Enforces uniqueness of monitored searches (`SearchProfile`) across the application.
Two searches are considered exactly equal (`ricerche esattamente uguali`) when
their normalized portal URL and normalized excluded keywords match.
"""
import logging
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ListingProfile, SearchProfile
from .filter_engine import parse_keywords_csv

logger = logging.getLogger(__name__)


def normalize_profile_url(url: str) -> str:
    """Normalizes a portal search URL for exact duplicate comparison.

    Strips whitespace and trailing slashes, lowercases scheme/netloc/path,
    removes non-filtering/bookmark parameters (`id`, `imm_source`, `pag`),
    and sorts remaining query parameters alphabetically.
    """
    url_str = (url or "").strip()
    if not url_str:
        return ""
    try:
        parsed = urlparse(url_str)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/").lower()

        # Parse query params, filtering out tracking/pagination params
        ignore_params = {"id", "imm_source", "pag"}
        query_items = [
            (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k.lower() not in ignore_params
        ]
        query_items.sort()
        query = urlencode(query_items) if query_items else ""

        return urlunparse((scheme, netloc, path, parsed.params, query, ""))
    except Exception:
        return url_str.rstrip("/").lower()


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
    for key, group in groups.items():
        if len(group) <= 1:
            continue
        canonical = group[0]
        duplicates = group[1:]
        logger.info(
            "Found %d duplicates for search profile '%s' (id=%d). Merging into id=%d...",
            len(duplicates), canonical.name, canonical.id, canonical.id,
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
