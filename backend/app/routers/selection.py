"""The one property-selection path, shared by every router that returns
properties.

Not a router itself: it holds the query builder and the transient annotations
that `properties` (grid, export, single card) and `analytics` (the comparables
behind a median) both need. It lives here rather than in `services/` because it
speaks HTTP — a bad `profile_id` or a malformed polygon is a 4xx, decided here
so the callers cannot each invent their own answer.

The reason it is one function and not three: the grid, the map and the export
must show the same set under the same filters (the "dossier mirrors the screen"
convention). The moment a second selection query exists, one of the two gets a
filter the other does not.
"""

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ..config import load_settings
from ..models import Listing, ListingProfile, Property, SearchProfile, Tag
from ..services.commute import annotate_commutes
from ..services.deal_score import annotate_deal_scores
from ..services.geo_filter import haversine_m, parse_polygon, point_in_polygon
from ..services.match_score import _parse_floor, annotate_match_scores
from ..services.omi_benchmark import annotate_omi_benchmark
from ..services.pricing_stats import annotate_market_position
from ..services.timeutils import as_utc


def annotate_provenance(db: Session, props: list[Property]) -> None:
    """Set each property's transient `found_by` to the monitored searches that
    have found it, read from the ListingProfile links the scanner writes. One
    query for the whole set (never per property): joins listings→links→profiles
    for all the ids at once, then buckets the rows in Python.

    Provenance, not origin — a property may be found by several overlapping
    searches (see invariant 20), and an email import never re-found by a scan
    simply has no links, so its `found_by` stays empty."""
    if not props:
        return
    ids = [p.id for p in props]
    rows = db.execute(
        select(Listing.property_id, SearchProfile.id, SearchProfile.name)
        .join(ListingProfile, ListingProfile.listing_id == Listing.id)
        .join(SearchProfile, SearchProfile.id == ListingProfile.profile_id)
        .where(Listing.property_id.in_(ids))
    ).all()
    # property_id -> ordered {profile_id: name}, so a search found by two of a
    # property's listings appears once, in first-seen order.
    by_prop: dict[int, dict[int, str]] = {}
    for prop_id, profile_id, name in rows:
        by_prop.setdefault(prop_id, {})[profile_id] = name
    for p in props:
        p.found_by = [{"id": pid, "name": name} for pid, name in by_prop.get(p.id, {}).items()]


def annotate(db: Session, props: list[Property]) -> None:
    """The full transient annotation set for one or few properties (market
    position and OMI band first: the deal score reads both). One helper instead
    of the same calls repeated per endpoint."""
    settings = load_settings()
    annotate_market_position(db, props)
    annotate_omi_benchmark(db, props)
    annotate_match_scores(props, settings)
    annotate_deal_scores(db, props)
    annotate_provenance(db, props)
    annotate_commutes(db, props, settings)


# Floor bands offered by the dashboard filter. The free-text floor label is
# messy ("piano terra", "T", "3", "attico"), so bands are matched in Python on
# the parsed number (reusing match_score._parse_floor, the one floor reader) —
# except "top", which a number can't express and is read straight off the label
# ("attico"/"ultimo piano"). A property whose floor can't be read matches no
# band: it cannot be shown to satisfy the filter, so it is left out.
def _floor_in_band(floor: str, band: str) -> bool:
    if band == "top":
        norm = (floor or "").strip().lower()
        return "attico" in norm or "ultimo" in norm
    n = _parse_floor(floor)
    if n is None:
        return False
    if band == "ground":
        return n == 0
    if band == "low":
        return 1 <= n <= 2
    if band == "mid":
        return 3 <= n <= 5
    if band == "high":
        return n >= 6
    return True


def select_properties(
    db: Session,
    *,
    status: str,
    contract: str | None,
    city: str | None,
    min_price: float | None,
    max_price: float | None,
    min_sqm: float | None,
    max_sqm: float | None = None,
    floor_band: str | None = None,
    rooms: int | None,
    only_price_drops: bool,
    only_favorites: bool,
    sort: str,
    q: str | None = None,
    zone: str | None = None,
    source: str | None = None,
    profile_id: int | None = None,
    tag: str | None = None,
    portal: str | None = None,
    agency: str | None = None,
    deal: str | None = None,
    min_sqm_price: float | None = None,
    max_sqm_price: float | None = None,
    merged_only: bool = False,
    center_lat: float | None = None,
    center_lng: float | None = None,
    radius_m: float | None = None,
    poly_vertices: list[tuple[float, float]] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[Property], int]:
    """Shared property selection + annotation for the grid, the map and the
    exports, so a dossier holds exactly what the dashboard is showing under the
    same filters. Match scores are annotated before the sort (compatibility
    ranking needs them); market position and deal score are order-independent.

    Returns `(page, total)`. `total` counts the whole filtered set, `page` is the
    `limit`/`offset` window of it — `limit=None` means "everything", which is
    what the export and the map ask for (a dossier of one page, or a map missing
    every pin past the fiftieth, would both be wrong).

    **The window is applied last, not as SQL LIMIT.** Half of these filters
    cannot be expressed in the query — floor band, price drops, merged-only, the
    €/sqm band, the drawn zone, the deal label are all Python post-filters, and
    `sort=match` orders on a score computed in Python too. A `LIMIT` in the
    statement would therefore page over the *pre-filter* set: pages with holes in
    them, a `total` that counts rows the user cannot see, and an ordering that
    changes as later pages arrive.

    `profile_id` limits the grid to the properties a monitored search actually
    found — its ListingProfile provenance links (the card's "🔍 Found by"),
    not a re-derivation of the search's contract/city (those overlap heavily
    between searches and filtered almost nothing). Email imports, which carry
    no links, drop out: that search never found them."""
    profile = db.get(SearchProfile, profile_id) if profile_id else None
    if profile_id and profile is None:
        # a silent no-op here showed the unfiltered grid as if the overlay
        # applied, which reads as "the filter is broken" rather than "that
        # search is gone"
        raise HTTPException(404, "Profile not found")

    query = select(Property).options(
        selectinload(Property.listings),
        selectinload(Property.price_history),
        selectinload(Property.tags),
    )
    if status != "all":
        query = query.where(Property.status == status)
    else:
        # "all" shows active, filtered, and gone — but never the two states
        # the user removed from their market on purpose: manually "hidden" and
        # confirmed "sold". Each has its own filter to review it deliberately.
        query = query.where(Property.status.notin_(("hidden", "sold")))
    if contract:
        query = query.where(Property.contract == contract)
    if city:
        query = query.where(Property.city.ilike(f"%{city}%"))
    if zone:
        query = query.where(Property.zone.ilike(f"%{zone}%"))
    if source in ("scan", "email"):
        query = query.where(Property.source == source)
    if profile is not None:
        # "Limit to a search" = only the properties this monitored search
        # actually found, read from the ListingProfile provenance links the
        # scanner writes (the card's "🔍 Found by"), not re-derived from the
        # search's contract/city — those overlap heavily between searches and
        # filtered nothing. A property qualifies when any of its listings is
        # linked to this profile. Email imports, which carry no links, are
        # correctly excluded: this search never found them.
        query = query.where(
            Property.listings.any(
                Listing.profile_links.any(ListingProfile.profile_id == profile_id)
            )
        )
    if portal in ("immobiliare", "idealista"):
        # a Property groups listings from several portals: "on Idealista" means
        # at least one of its ads lives there, not that all do
        query = query.where(Property.listings.any(Listing.portal == portal))
    if agency and agency.strip():
        query = query.where(Property.listings.any(Listing.agency.ilike(f"%{agency.strip()}%")))
    if tag and tag.strip():
        query = query.where(Property.tags.any(Tag.name_normalized == tag.strip().lower()))
    if q and q.strip():
        # Free-text search across the fields a user would actually type
        # (zone "San Siro", a street, "nuova costruzione" in the title or the
        # listing's own description/agency, "piano terra" in the floor).
        # Split on whitespace and AND the terms: "attico navigli" then matches
        # a property whose title says "attico" and whose zone says "Navigli",
        # which a single substring never would. Each term may still match any
        # one field.
        def _floor_match(term: str):
            # floor holds short values ("1", "17", "T") and occasionally a
            # two-word phrase ("piano terra"): a plain substring match makes
            # "1" match "17", "21"... it needs a word-boundary match instead,
            # anchored at the start/end of the field or a surrounding space
            # (mirrors filter_engine's word-boundary keyword matching).
            return or_(
                Property.floor.ilike(term),
                Property.floor.ilike(f"{term} %"),
                Property.floor.ilike(f"% {term}"),
                Property.floor.ilike(f"% {term} %"),
            )

        tokens = q.split()
        # "1 piano" / "piano 1" is a floor query in Italian, not two
        # independent words: "piano" here names the field rather than text to
        # find elsewhere, and requiring it as a literal word in the title or
        # description would return nothing (or the wrong listings, since a
        # bare digit alone still needs restricting below). Pair a digit with
        # an adjacent floor word up front and search only the floor field for
        # it. The whole UI is in English, so "floor" is accepted alongside the
        # Italian "piano" ("floor 4" behaves exactly like "4 piano").
        floor_words = {"piano", "floor"}
        floor_terms: list[str] = []
        rest: list[str] = []
        skip_next = False
        for i, t in enumerate(tokens):
            if skip_next:
                skip_next = False
                continue
            nxt = tokens[i + 1] if i + 1 < len(tokens) else None
            if t.isdigit() and nxt and nxt.lower() in floor_words:
                floor_terms.append(t)
                skip_next = True
            elif t.lower() in floor_words and nxt and nxt.isdigit():
                floor_terms.append(nxt)
                skip_next = True
            else:
                rest.append(t)

        for term in floor_terms:
            query = query.where(_floor_match(term))
        for term in rest:
            if term.isdigit():
                # a bare number with no "piano" nearby is still almost always
                # about the floor: matching it against address/description too
                # would catch street numbers and prices instead ("via Fulvio
                # Testi 110" for "1").
                query = query.where(_floor_match(term))
                continue
            like = f"%{term}%"
            query = query.where(
                or_(
                    Property.title.ilike(like),
                    Property.zone.ilike(like),
                    Property.address.ilike(like),
                    Property.city.ilike(like),
                    _floor_match(term),
                    Property.listings.any(
                        or_(
                            Listing.agency.ilike(like),
                            Listing.description.ilike(like),
                        )
                    ),
                )
            )
    # "is not None" and not truthiness: 0 is a legitimate threshold
    if min_price is not None:
        query = query.where(Property.current_min_price >= min_price)
    if max_price is not None:
        query = query.where(Property.current_min_price <= max_price)
    if min_sqm is not None:
        query = query.where(Property.sqm >= min_sqm)
    if max_sqm is not None:
        query = query.where(Property.sqm <= max_sqm)
    if rooms is not None:
        query = query.where(Property.rooms == rooms)
    if only_favorites:
        query = query.where(Property.is_favorite.is_(True))

    props = list(db.scalars(query))
    if floor_band:
        # post-filter: the floor label is free text, not a number in the DB
        props = [p for p in props if _floor_in_band(p.floor, floor_band)]
    if only_price_drops:
        props = [
            p
            for p in props
            if p.first_price and p.current_min_price and p.current_min_price < p.first_price
        ]
    if merged_only:
        # a property backed by more than one ad: the cross-portal/agency
        # duplicates the deduplicator folded into a single card
        props = [p for p in props if len(p.listings) > 1]
    if min_sqm_price is not None or max_sqm_price is not None:
        # €/sqm is derived (price ÷ surface), not stored: a property missing
        # either can't be placed on that axis, so it drops out of the band
        def _sqm_price(p: Property) -> float | None:
            return p.current_min_price / p.sqm if p.current_min_price and p.sqm else None

        props = [
            p
            for p in props
            if (sp := _sqm_price(p)) is not None
            and (min_sqm_price is None or sp >= min_sqm_price)
            and (max_sqm_price is None or sp <= max_sqm_price)
        ]
    # Geographic zone drawn on the map: radius (point + distance) or polygon.
    # A property with NULL coordinates cannot be placed in a zone, so it always
    # drops out — the caveat MapView surfaces as a persistent banner + the
    # "N without coordinates" chip (many listings arrive un-geocoded).
    if radius_m and center_lat is not None and center_lng is not None:
        props = [
            p
            for p in props
            if p.latitude is not None
            and p.longitude is not None
            and haversine_m(center_lat, center_lng, p.latitude, p.longitude) <= radius_m
        ]
    elif poly_vertices:
        props = [
            p
            for p in props
            if p.latitude is not None
            and p.longitude is not None
            and point_in_polygon(p.latitude, p.longitude, poly_vertices)
        ]
    settings = load_settings()
    annotate_match_scores(props, settings)
    if sort == "newest":
        # as_utc, not the raw column: SQLite returns naive datetimes while a row
        # created earlier in this same session still carries the aware value it
        # was built with (SessionLocal keeps `expire_on_commit=False`). Sorting
        # the two kinds together raises TypeError and takes the whole grid down.
        props.sort(key=lambda p: as_utc(p.first_seen_at), reverse=True)
    elif sort == "price_asc":
        props.sort(key=lambda p: p.current_min_price or 1e12)
    elif sort == "price_desc":
        props.sort(key=lambda p: p.current_min_price or 0, reverse=True)
    elif sort == "sqm_price":
        props.sort(
            key=lambda p: (p.current_min_price / p.sqm) if p.current_min_price and p.sqm else 1e12
        )
    elif sort == "match":
        # best matches first; unscored (None) sink to the bottom
        props.sort(key=lambda p: p.match_score if p.match_score is not None else -1, reverse=True)
    if deal:
        # The deal label is itself a filter here, so it has to exist for every
        # candidate before the window is cut — annotating the page only would
        # filter one page and report a total for a different population.
        annotate_market_position(db, props)
        annotate_omi_benchmark(db, props)
        annotate_deal_scores(db, props)
        if deal == "undervalued":
            props = [p for p in props if p.deal_label == "undervalued"]
        elif deal == "fair_plus":
            # "fair or better": drop the overpriced ones (and those with no
            # score, since without a local median a deal cannot be confirmed)
            props = [p for p in props if p.deal_label in ("undervalued", "fair")]

    total = len(props)
    page = props[offset:] if limit is None else props[offset : offset + limit]
    if not deal:
        # Purely presentational here, and both are per-property lookups against
        # medians read from the DB — the values do not depend on which other
        # properties are in the list, so computing them for the window alone is
        # identical to computing them for all and throwing most away.
        annotate_market_position(db, page)
        annotate_omi_benchmark(db, page)
        annotate_deal_scores(db, page)
    annotate_provenance(db, page)
    # Cache-only, so the window is the right scope: reading the routed legs of
    # the fifty cards on screen costs nothing the whole set would not.
    annotate_commutes(db, page, settings)
    return page, total


def parse_poly_param(poly: str | None) -> list[tuple[float, float]] | None:
    """Turn the `poly` query param into vertices, or None when absent.

    A malformed polygon is an explicit 400, never a silently-ignored filter that
    would show the unfiltered grid as if the zone applied."""
    if not poly or not poly.strip():
        return None
    try:
        return parse_polygon(poly)
    except ValueError as exc:
        raise HTTPException(400, f"Invalid polygon: {exc}") from exc
