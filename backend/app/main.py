"""FastAPI entrypoint: REST routes for properties, search profiles,
scans, and settings."""
import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from . import schemas
from .config import BASE_DIR, FRONTEND_DIST, load_settings, save_settings
from .database import get_db, init_db
from .models import ImportedListing, Listing, Property, SearchProfile
from .scrapers import detect_portal
from .services import (availability_check, data_reset, email_import, exporter,
                       notifier, scheduler)
from .services.deal_score import annotate_deal_scores
from .services.filter_engine import find_excluded_keyword
from .services.market_velocity import compute_market_velocity
from .services.match_score import annotate_match_scores
from .services.pricing_stats import (
    annotate_market_position, get_trends, list_trend_areas,
)
from .services.query_parser import parse_query
from .services.scanner import run_scan, scan_state
from .services.search_builder import build_search_urls

# Log both to console and rotating file: the scheduler runs overnight without
# anyone at the terminal, and without a log file it would be impossible to diagnose
# why a scan failed afterwards.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            BASE_DIR / "app.log", maxBytes=1_000_000, backupCount=2,
            encoding="utf-8",
        ),
    ],
)
# Alembic's plugin-setup chatter at INFO floods app.log on every startup and
# buries the scan/probe lines the file exists to preserve.
logging.getLogger("alembic").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.start_scheduler()
    yield
    scheduler.shutdown()


app = FastAPI(title="Real Estate Search", lifespan=lifespan)

# Only the Vite dev server needs CORS. The phone loads the built app from this
# same origin (see the StaticFiles mount at the bottom), so serving remote
# clients never requires widening this list — keep it that way.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Properties ---

def _annotate(db: Session, props: list[Property]) -> None:
    """The full transient annotation set for one or few properties (market
    position first: the deal score reads it). One helper instead of the same
    three calls repeated per endpoint."""
    annotate_market_position(db, props)
    annotate_match_scores(props, load_settings())
    annotate_deal_scores(db, props)


def _select_properties(
    db: Session, *, status: str, contract: str | None, city: str | None,
    min_price: float | None, max_price: float | None, min_sqm: float | None,
    rooms: int | None, only_price_drops: bool, only_favorites: bool, sort: str,
    q: str | None = None, zone: str | None = None, source: str | None = None,
    profile_id: int | None = None,
) -> list[Property]:
    """Shared property selection + annotation for the grid and the exports, so
    a dossier holds exactly what the dashboard is showing under the same
    filters. Match scores are annotated before the sort (compatibility ranking
    needs them); market position and deal score are order-independent.

    `profile_id` overlays a monitored search on the whole dashboard (D): it
    forces the profile's contract/city and drops properties matching that
    profile's exclusion keywords (global + profile), so the same criteria that
    keep the scans clean can be applied retroactively to email imports too."""
    profile = db.get(SearchProfile, profile_id) if profile_id else None
    if profile_id and profile is None:
        # same answer list_imported gives for the same concept: a silent
        # no-op here showed the unfiltered grid as if the overlay applied
        raise HTTPException(404, "Profile not found")
    profile_keywords: list[str] = []
    if profile is not None:
        crit = email_import.profile_criteria(
            profile, list(load_settings().get("excluded_keywords", []))
        )
        # the profile's own contract/city take precedence over ad-hoc filters
        contract = crit["contract"] or contract
        city = crit["city"] or city
        profile_keywords = crit["keywords"]

    query = select(Property).options(
        selectinload(Property.listings), selectinload(Property.price_history)
    )
    if status != "all":
        query = query.where(Property.status == status)
    else:
        # "all" shows active, filtered, and gone — but never manually
        # hidden properties: the user excluded them intentionally
        query = query.where(Property.status != "hidden")
    if contract:
        query = query.where(Property.contract == contract)
    if city:
        query = query.where(Property.city.ilike(f"%{city}%"))
    if zone:
        query = query.where(Property.zone.ilike(f"%{zone}%"))
    if source in ("scan", "email"):
        query = query.where(Property.source == source)
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
        # an adjacent "piano" up front and search only the floor field for it.
        floor_terms: list[str] = []
        rest: list[str] = []
        skip_next = False
        for i, t in enumerate(tokens):
            if skip_next:
                skip_next = False
                continue
            nxt = tokens[i + 1] if i + 1 < len(tokens) else None
            if t.isdigit() and nxt and nxt.lower() == "piano":
                floor_terms.append(t)
                skip_next = True
            elif t.lower() == "piano" and nxt and nxt.isdigit():
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
            query = query.where(or_(
                Property.title.ilike(like),
                Property.zone.ilike(like),
                Property.address.ilike(like),
                Property.city.ilike(like),
                _floor_match(term),
                Property.listings.any(or_(
                    Listing.agency.ilike(like), Listing.description.ilike(like),
                )),
            ))
    # "is not None" and not truthiness: 0 is a legitimate threshold
    if min_price is not None:
        query = query.where(Property.current_min_price >= min_price)
    if max_price is not None:
        query = query.where(Property.current_min_price <= max_price)
    if min_sqm is not None:
        query = query.where(Property.sqm >= min_sqm)
    if rooms is not None:
        query = query.where(Property.rooms == rooms)
    if only_favorites:
        query = query.where(Property.is_favorite.is_(True))

    props = list(db.scalars(query))
    if profile_keywords:
        # apply the monitored search's exclusion keywords to the whole set:
        # email imports never passed through the scan's keyword filter, so this
        # is how "nuda proprietà"/"asta"/… get pruned from them too
        props = [
            p for p in props
            if not find_excluded_keyword(
                [p.title, p.zone, p.address,
                 *(l.description for l in p.listings),
                 *(l.agency for l in p.listings)],
                profile_keywords,
            )
        ]
    if only_price_drops:
        props = [
            p for p in props
            if p.first_price and p.current_min_price
            and p.current_min_price < p.first_price
        ]
    annotate_match_scores(props, load_settings())
    if sort == "newest":
        props.sort(key=lambda p: p.first_seen_at, reverse=True)
    elif sort == "price_asc":
        props.sort(key=lambda p: p.current_min_price or 1e12)
    elif sort == "price_desc":
        props.sort(key=lambda p: p.current_min_price or 0, reverse=True)
    elif sort == "sqm_price":
        props.sort(
            key=lambda p: (p.current_min_price / p.sqm)
            if p.current_min_price and p.sqm else 1e12
        )
    elif sort == "match":
        # best matches first; unscored (None) sink to the bottom
        props.sort(key=lambda p: p.match_score if p.match_score is not None else -1,
                   reverse=True)
    annotate_market_position(db, props)
    annotate_deal_scores(db, props)
    return props


@app.get("/api/properties", response_model=list[schemas.PropertyOut])
def list_properties(
    db: Session = Depends(get_db),
    # validated like `contract`/`sort`: a typo'd status would otherwise return
    # an empty list, indistinguishable from "no matches" — a silent failure
    status: str = Query("active", pattern="^(active|filtered|gone|hidden|all)$"),
    contract: str | None = Query(None, pattern="^(sale|rent)$"),
    city: str | None = None,
    zone: str | None = None,
    q: str | None = None,
    source: str | None = Query(None, pattern="^(scan|email)$"),
    profile_id: int | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_sqm: float | None = None,
    rooms: int | None = None,
    only_price_drops: bool = False,
    only_favorites: bool = False,
    sort: str = Query(
        "newest",
        pattern="^(newest|price_asc|price_desc|sqm_price|match)$",
    ),
):
    return _select_properties(
        db, status=status, contract=contract, city=city, min_price=min_price,
        max_price=max_price, min_sqm=min_sqm, rooms=rooms,
        only_price_drops=only_price_drops, only_favorites=only_favorites,
        sort=sort, q=q, zone=zone, source=source, profile_id=profile_id,
    )


@app.get("/api/properties/export")
def export_properties(
    db: Session = Depends(get_db),
    fmt: str = Query("html", pattern="^(html|markdown|csv)$"),
    title: str = "Property shortlist",
    status: str = Query("active", pattern="^(active|filtered|gone|hidden|all)$"),
    contract: str | None = Query(None, pattern="^(sale|rent)$"),
    city: str | None = None,
    zone: str | None = None,
    q: str | None = None,
    source: str | None = Query(None, pattern="^(scan|email)$"),
    profile_id: int | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_sqm: float | None = None,
    rooms: int | None = None,
    only_price_drops: bool = False,
    only_favorites: bool = False,
    sort: str = Query(
        "newest", pattern="^(newest|price_asc|price_desc|sqm_price|match)$"),
):
    """Download the currently-filtered shortlist as a self-contained dossier.

    Same selection as the grid, so the file mirrors what the user sees. Returned
    as an attachment (no server, no DB) that can be shared over chat or email —
    the reason the export exists rather than sharing the live dashboard."""
    props = _select_properties(
        db, status=status, contract=contract, city=city, min_price=min_price,
        max_price=max_price, min_sqm=min_sqm, rooms=rooms,
        only_price_drops=only_price_drops, only_favorites=only_favorites,
        sort=sort, q=q, zone=zone, source=source, profile_id=profile_id,
    )
    clean_title = (title or "Property shortlist").strip()[:120] or "Property shortlist"
    if fmt == "csv":
        body = exporter.properties_to_csv(props)
        media, ext = "text/csv; charset=utf-8", "csv"
    elif fmt == "markdown":
        body = exporter.properties_to_markdown(props, clean_title)
        media, ext = "text/markdown; charset=utf-8", "md"
    else:
        body = exporter.properties_to_html(props, clean_title)
        media, ext = "text/html; charset=utf-8", "html"
    filename = f"dossier-{datetime.now(timezone.utc):%Y%m%d}.{ext}"
    return Response(
        content=body, media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/properties/check-progress")
def properties_check_progress():
    """Live progress of the ongoing dashboard properties availability check.

    Must stay registered before GET /api/properties/{property_id}: Starlette
    matches routes in registration order, and an int-typed path parameter
    still matches the literal segment "check-progress" first, turning every
    poll into a 422 instead of ever reaching this handler — the progress bar
    then never advances past its initial state.
    """
    return availability_check.get_prop_check_progress()


@app.get("/api/properties/{property_id}", response_model=schemas.PropertyOut)
def get_property(property_id: int, db: Session = Depends(get_db)):
    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")
    _annotate(db, [prop])
    return prop


@app.patch("/api/properties/{property_id}", response_model=schemas.PropertyOut)
def patch_property(
    property_id: int, data: schemas.PropertyPatch, db: Session = Depends(get_db)
):
    """Updates user-curated fields (favorite flag, personal notes)."""
    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")
    if data.is_favorite is not None:
        prop.is_favorite = data.is_favorite
    if data.notes is not None:
        prop.notes = data.notes
    db.commit()
    db.refresh(prop)
    _annotate(db, [prop])
    return prop


@app.delete("/api/properties/{property_id}")
def hide_property(property_id: int, db: Session = Depends(get_db)):
    """Hides the property instead of physically deleting it: a real DELETE would
    be undone by the next scan, which would find the listing on the portal again
    and reinsert it (notifying it as new). The "hidden" status excludes it
    permanently from lists and notifications."""
    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")
    prop.status = "hidden"
    prop.filtered_reason = ""
    db.commit()
    return {"ok": True}


@app.post("/api/properties/{property_id}/restore")
def restore_property(property_id: int, db: Session = Depends(get_db)):
    """Restores a manually hidden property back to active status.

    Also used to correct a property wrongly marked "gone" by the
    availability check (invariant 16 is fail-open by design, but a portal
    redirect or block misread as removal can still slip through) — so this
    clears `gone_at` too, matching the availability check's own "reappeared
    online" handling, instead of leaving a stale date behind."""
    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")
    prop.status = "active"
    prop.gone_at = None
    db.commit()
    return {"ok": True}


@app.post("/api/properties/bulk")
def bulk_properties(data: schemas.PropertyBulkIn, db: Session = Depends(get_db)):
    """Apply hide/restore/favorite/unfavorite to many properties at once.

    Same per-property semantics as the single-item routes (hiding stays
    reversible only via restore, invariant 5), just batched: the point is to
    let the user clear a dashboard cluttered by inbox imports in one gesture
    instead of opening cards one by one. Missing ids are skipped silently."""
    props = [p for p in (db.get(Property, x) for x in data.ids) if p]
    for prop in props:
        if data.action == "hide":
            prop.status = "hidden"
            prop.filtered_reason = ""
        elif data.action == "restore":
            prop.status = "active"
            prop.gone_at = None
        elif data.action == "favorite":
            prop.is_favorite = True
        elif data.action == "unfavorite":
            prop.is_favorite = False
    db.commit()
    return {"ok": True, "processed": len(props)}


@app.post("/api/properties/check")
def properties_check(data: schemas.PropertyCheckIn, db: Session = Depends(get_db)):
    """Runs live availability check (`AdProbe`) across multiple dashboard properties.

    The whole selection is accepted: the service itself caps live portal
    fetches per run (invariant 16) and skips recently verified properties, so
    a "select all" batch progresses across repeated runs instead of re-probing
    the same first slice.
    """
    props = [p for p in (db.get(Property, x) for x in data.ids) if p]
    if not props:
        raise HTTPException(400, "No properties to check")
    try:
        return availability_check.check_properties_availability(db, props)
    except availability_check.AvailabilityCheckError as e:
        raise HTTPException(400, str(e))


@app.post("/api/properties/check/cancel")
def cancel_properties_check():
    """Stops the running batch after its current property (invariant 16's
    pacing means each one can take several seconds, so this is not instant).
    A no-op if nothing is running."""
    availability_check.request_cancel()
    return {"ok": True}


@app.post("/api/properties/{property_id}/check")
def check_single_property(property_id: int, db: Session = Depends(get_db)):
    """Runs AdProbe live availability check on a single property."""
    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")
    try:
        summary = availability_check.check_properties_availability(db, [prop])
    except availability_check.AvailabilityCheckError as e:
        raise HTTPException(400, str(e))
    _annotate(db, [prop])
    return {
        "property": schemas.PropertyOut.model_validate(prop).model_dump(mode="json"),
        "summary": summary,
    }



# --- Search profiles ---

@app.get("/api/search-profiles", response_model=list[schemas.SearchProfileOut])
def list_profiles(db: Session = Depends(get_db)):
    return list(db.scalars(select(SearchProfile).order_by(SearchProfile.id)))


@app.post("/api/search-profiles", response_model=schemas.SearchProfileOut)
def create_profile(data: schemas.SearchProfileIn, db: Session = Depends(get_db)):
    profile = SearchProfile(
        name=data.name,
        portal=detect_portal(data.search_url),
        search_url=data.search_url,
        excluded_keywords=data.excluded_keywords,
        notify_channels=data.notify_channels,
        is_active=data.is_active,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@app.put("/api/search-profiles/{profile_id}", response_model=schemas.SearchProfileOut)
def update_profile(
    profile_id: int, data: schemas.SearchProfileIn, db: Session = Depends(get_db)
):
    profile = db.get(SearchProfile, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    if data.search_url != profile.search_url:
        # a new URL is a new search: the old baseline says nothing about it.
        # Left armed, the next scan would notify every listing of the new
        # search as "new" — the flood invariant 3 exists to prevent.
        profile.baseline_done = False
        profile.last_run_at = None
        profile.last_run_status = ""
        profile.last_run_detail = ""
        profile.consecutive_failures = 0
        profile.health_alert_sent = False
    profile.name = data.name
    profile.search_url = data.search_url
    profile.portal = detect_portal(data.search_url)
    profile.excluded_keywords = data.excluded_keywords
    profile.notify_channels = data.notify_channels
    profile.is_active = data.is_active
    db.commit()
    db.refresh(profile)
    return profile


@app.get("/api/search-profiles/{profile_id}/results")
def profile_results(profile_id: int, db: Session = Depends(get_db)):
    """How many dashboard properties this search produced, and how many of them
    deleting it would actually remove — the numbers the delete dialog shows
    before the user chooses. See data_reset.profile_results for what is spared."""
    profile = db.get(SearchProfile, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    summary = data_reset.profile_results(db, profile_id)
    summary.pop("properties")
    return summary


@app.delete("/api/search-profiles/{profile_id}")
def delete_profile(
    profile_id: int, delete_results: bool = False, db: Session = Depends(get_db)
):
    """Deletes a monitored search. With `delete_results=true` the properties it
    alone produced go with it (irreversibly); by default they stay in the
    dashboard, now orphaned but intact."""
    profile = db.get(SearchProfile, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    if delete_results and scan_state["running"]:
        # a scan in flight is writing the very links this decision reads (and
        # would re-create the properties it deletes): same guard the resets use
        raise HTTPException(
            409, "A scan is running: wait for it to finish before deleting the results"
        )
    # results first, in the same transaction: the classification reads the
    # profile's links, and deleting the profile cascades them away
    results = (data_reset.delete_profile_results(db, profile_id)
               if delete_results else None)
    db.delete(profile)
    db.commit()
    return {"ok": True, "results": results}


# --- Search builder ---

@app.post("/api/search-builder")
def search_builder(data: schemas.SearchBuilderIn):
    """Generates ready-to-use search URLs for both portals from structured
    parameters, so the user does not have to copy/paste from the browser."""
    return build_search_urls(data.model_dump())


# --- Search assistant (natural language) ---

@app.post("/api/search-assistant", response_model=schemas.AssistantOut)
def search_assistant(data: schemas.AssistantQueryIn):
    """Turns a plain-language query into search-builder parameters.

    A query with disjunctions ("bilocale in zona X o trilocale in zona Y")
    yields one search per alternative. Never raises on an unparseable query:
    it answers with whatever it understood plus `warnings`, and the UI
    pre-fills the builder form so the user can correct it. URLs are built
    only when a city was identified — without one the portals would silently
    return all of Italy.
    """
    result = parse_query(data.query)
    searches = []
    for search in result["searches"]:
        params = schemas.AssistantParams(**search["params"])
        searches.append(schemas.AssistantSearch(
            params=params,
            interpretation=search["interpretation"],
            notes=search.get("notes", []),
            warnings=search["warnings"],
            urls=build_search_urls(params.model_dump()) if params.city else None,
        ))
    return schemas.AssistantOut(searches=searches)


# --- Email inbox import (IMAP, read-only) ---

@app.post("/api/email-import/test")
def email_import_test():
    """Verifies the IMAP credentials by opening INBOX read-only."""
    try:
        return email_import.test_connection()
    except email_import.ImapError as e:
        raise HTTPException(400, str(e))


@app.get("/api/email-import/progress")
def email_import_progress():
    """How far the running scan has got, for the UI to poll: fetching a
    thousand messages over IMAP takes minutes, and a button stuck on
    "Scanning…" is indistinguishable from a hung app."""
    return email_import.get_progress()


@app.post("/api/email-import/scan")
def email_import_scan(
    data: schemas.EmailImportScanIn, db: Session = Depends(get_db)
):
    """Scans the inbox for listing emails and stages what it finds for review.
    Deliberately a sync `def`: FastAPI then runs it in a threadpool, so the
    event loop stays free to answer /email-import/progress while it works."""
    try:
        return email_import.scan_inbox(
            db,
            mode=data.mode,
            senders=data.senders,
            since_days=data.since_days,
            max_emails=data.max_emails,
        )
    except email_import.ImapError as e:
        raise HTTPException(400, str(e))


@app.get("/api/email-import", response_model=list[schemas.ImportedListingOut])
def list_imported(
    db: Session = Depends(get_db),
    status: str = Query("pending", pattern="^(pending|accepted|discarded|all)$"),
    profile_id: int | None = None,
    contract: str | None = Query(None, pattern="^(sale|rent)$"),
    city: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    rooms: int | None = None,
    q: str | None = None,
):
    """Staged listings, filterable ad-hoc or by an existing search profile
    (profile_id derives contract, city and excluded keywords from it, so the
    user reviews the imports against the search they already monitor)."""
    keywords: list[str] = []
    if profile_id is not None:
        profile = db.get(SearchProfile, profile_id)
        if not profile:
            raise HTTPException(404, "Profile not found")
        criteria = email_import.profile_criteria(
            profile, load_settings().get("excluded_keywords", [])
        )
        contract = contract or criteria["contract"]
        city = city or criteria["city"]
        keywords = criteria["keywords"]

    query = select(ImportedListing)
    if status != "all":
        query = query.where(ImportedListing.status == status)
    if contract:
        query = query.where(ImportedListing.contract == contract)
    if min_price is not None:
        query = query.where(ImportedListing.price >= min_price)
    if max_price is not None:
        query = query.where(ImportedListing.price <= max_price)
    if rooms is not None:
        query = query.where(ImportedListing.rooms == rooms)
    items = list(db.scalars(query))

    if city:
        # emails rarely state the city as a structured field: match the
        # title/subject text too, otherwise the filter would hide everything
        needle = city.strip().lower()
        items = [
            i for i in items
            if needle in i.city.lower() or needle in i.title.lower()
            or needle in i.email_subject.lower()
        ]
    if q:
        needle = q.strip().lower()
        items = [
            i for i in items
            if needle in i.title.lower() or needle in i.email_subject.lower()
        ]
    if keywords:
        items = [
            i for i in items
            if find_excluded_keyword([i.title, i.email_subject], keywords) is None
        ]
    # newest email first; undated ones sink to the bottom
    items.sort(
        key=lambda i: (i.email_date is not None, i.email_date or i.created_at),
        reverse=True,
    )
    return items


@app.post("/api/email-import/{item_id}/accept")
def accept_imported(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ImportedListing, item_id)
    if not item:
        raise HTTPException(404, "Imported listing not found")
    prop = email_import.accept_import(db, item)
    return {"ok": True, "property_id": prop.id}


@app.post("/api/email-import/{item_id}/discard")
def discard_imported(item_id: int, db: Session = Depends(get_db)):
    """Discarded rows are kept (not deleted): they are what makes re-scanning
    the same inbox idempotent — a rejected listing must not reappear."""
    item = db.get(ImportedListing, item_id)
    if not item:
        raise HTTPException(404, "Imported listing not found")
    item.status = "discarded"
    db.commit()
    return {"ok": True}


@app.get("/api/email-import/check-progress")
def email_import_check_progress():
    """How far the availability check has got: one listing every few seconds."""
    return email_import.get_check_progress()


@app.post("/api/email-import/check")
def email_import_check(data: schemas.ImportCheckIn, db: Session = Depends(get_db)):
    """Asks the portals whether these staged listings still exist.

    Sync `def` for the same reason as the scan (invariant 15): FastAPI runs it
    in a threadpool, so /email-import/check-progress can answer while it works.
    The service caps live portal fetches per run (invariant 16); rows resolved
    without a fetch don't consume that budget, so repeat runs make progress.
    """
    items = [i for i in (db.get(ImportedListing, x) for x in data.ids) if i]
    if not items:
        raise HTTPException(400, "No listing to check")
    try:
        return email_import.check_availability(db, items)
    except email_import.ImapError as e:
        # "already running": same user-facing path as a refused scan
        raise HTTPException(400, str(e))


@app.post("/api/email-import/check/cancel")
def cancel_email_import_check():
    """Stops the running email-import availability check after its current
    listing — same semantics as the dashboard check's cancel. A no-op if
    nothing is running."""
    email_import.request_check_cancel()
    return {"ok": True}


@app.post("/api/email-import/bulk")
def bulk_imported(data: schemas.ImportBulkIn, db: Session = Depends(get_db)):
    items = [i for i in (db.get(ImportedListing, x) for x in data.ids) if i]
    for item in items:
        if data.action == "accept":
            email_import.accept_import(db, item)
        else:
            item.status = "discarded"
    db.commit()
    return {"ok": True, "processed": len(items)}


# --- Market velocity ---

@app.get("/api/market-velocity", response_model=schemas.MarketVelocityOut)
def market_velocity(
    db: Session = Depends(get_db),
    contract: str = Query("sale", pattern="^(sale|rent)$"),
    city: str | None = None,
):
    """Days-on-market and sell-through per neighborhood, plus agency pricing
    behavior. Values are computed from local scan history only, so they are
    meaningful once the database has been accumulating for a few weeks."""
    return compute_market_velocity(db, contract=contract, city=city)


# --- Historical price trends ---

@app.get("/api/pricing-trends/areas", response_model=list[schemas.TrendAreaOut])
def pricing_trend_areas(
    db: Session = Depends(get_db),
    contract: str = Query("sale", pattern="^(sale|rent)$"),
):
    """Areas with at least two daily snapshots — the ones worth charting."""
    return list_trend_areas(db, contract)


@app.get("/api/pricing-trends", response_model=schemas.PricingTrendOut)
def pricing_trends(
    db: Session = Depends(get_db),
    city: str = Query(..., min_length=1),
    zone: str = "",
    contract: str = Query("sale", pattern="^(sale|rent)$"),
):
    """Median €/sqm over time for one area (empty zone = whole city). The series
    is built from daily snapshots (pricing_snapshots), so it only starts saying
    something after the app has run for several days."""
    return get_trends(db, city=city, zone=zone, contract=contract)


# --- Scan ---

@app.post("/api/scrapers/trigger")
def trigger_scan(profile_id: int | None = None):
    if scan_state["running"]:
        return {"status": "already_running"}
    # a user-triggered scan is explicit intent: it runs even while automatic
    # scanning is paused (scanner.run_scan's `manual` flag)
    thread = threading.Thread(
        target=run_scan, args=(profile_id,), kwargs={"manual": True}, daemon=True)
    thread.start()
    return {"status": "started"}


@app.get("/api/scrapers/status")
def scraper_status():
    return {
        **scan_state,
        "next_auto_run": scheduler.next_run_time(),
        "paused": bool(load_settings().get("scanning_paused")),
    }


@app.post("/api/maintenance/repair-listings")
def repair_listings_endpoint(db: Session = Depends(get_db)):
    """Instantly repairs existing dashboard properties lacking city, zone, title, or photos."""
    from .services.repair_listings import repair_empty_listings_locally
    return repair_empty_listings_locally(db)


# Scoped, irreversible data resets (Settings → Data management). Each is a
# distinct deliberate choice, so they are separate scopes rather than flags on
# one call. `factory` and `dashboard` delete rows a running scan is writing, so
# they refuse while one is in flight; `factory` snapshots the DB first.
_RESET_SCOPES = ("email-import", "dashboard", "pricing-snapshots", "factory")


@app.post("/api/maintenance/reset/{scope}")
def maintenance_reset(scope: str, db: Session = Depends(get_db)):
    if scope not in _RESET_SCOPES:
        raise HTTPException(400, f"Unknown reset scope: {scope}")
    if scope in ("dashboard", "factory") and scan_state["running"]:
        raise HTTPException(
            409, "A scan is running: wait for it to finish before resetting"
        )
    fn = {
        "email-import": data_reset.reset_email_import,
        "dashboard": data_reset.clear_dashboard,
        "pricing-snapshots": data_reset.clear_pricing_snapshots,
        "factory": data_reset.factory_reset,
    }[scope]
    try:
        return fn(db)
    except data_reset.ResetError as e:
        raise HTTPException(500, str(e))


# --- Logs ---

LOG_PATH = BASE_DIR / "app.log"


@app.get("/api/logs/tail")
def logs_tail(lines: int = 200):
    """Last N lines of the running backend's own log file, for the dashboard's
    log viewer: without this, "is the check actually doing anything?" could
    only be answered by opening app.log in a text editor. Reads the whole
    current file rather than seeking from the end, which is fine at the
    1 MB `RotatingFileHandler` cap this project uses.

    Plain default (not `Query(..., ge=1, le=2000)`): this module's tests call
    endpoint functions directly rather than through TestClient (invariant-free
    of the real scheduler that the app lifespan would start), and a `Query`
    sentinel only resolves to a value through FastAPI's own dependency
    injection.
    """
    lines = max(1, min(lines, 2000))
    if not LOG_PATH.exists():
        return {"lines": [], "path": str(LOG_PATH)}
    with open(LOG_PATH, encoding="utf-8", errors="replace") as f:
        all_lines = f.read().splitlines()
    return {"lines": all_lines[-lines:], "path": str(LOG_PATH)}


# --- Settings ---

@app.get("/api/settings")
def get_settings():
    settings = load_settings()
    if settings.get("telegram_bot_token"):
        token = settings["telegram_bot_token"]
        settings["telegram_bot_token"] = token[:6] + "..." if len(token) > 6 else token
        settings["telegram_token_set"] = True
    else:
        settings["telegram_token_set"] = False
    # secrets never leave the backend in clear text
    settings["smtp_password_set"] = bool(settings.get("smtp_password"))
    settings["smtp_password"] = "***" if settings.get("smtp_password") else ""
    settings["imap_password_set"] = bool(settings.get("imap_password"))
    settings["imap_password"] = "***" if settings.get("imap_password") else ""
    settings["datadome_cookie_set"] = bool(settings.get("datadome_cookie"))
    settings["datadome_cookie"] = "***" if settings.get("datadome_cookie") else ""
    # whether the optional browser automation is installed, so the UI can show
    # the "grab it for me" button instead of a paste-only field
    from .services import cookie_harvester
    settings["datadome_harvester_available"] = cookie_harvester.is_available()
    settings["camoufox_available"] = cookie_harvester.is_camoufox_available()
    return settings


@app.put("/api/settings")
def update_settings(data: schemas.SettingsIn):
    values = data.model_dump(exclude_none=True)
    # do not overwrite secrets with their masked versions
    if values.get("telegram_bot_token", "").endswith("..."):
        values.pop("telegram_bot_token")
    if values.get("smtp_password") == "***":
        values.pop("smtp_password")
    if values.get("imap_password") == "***":
        values.pop("imap_password")
    if values.get("datadome_cookie") == "***":
        values.pop("datadome_cookie")
    save_settings(values)
    if "scan_interval_minutes" in values:
        scheduler.reschedule(int(values["scan_interval_minutes"]))
    if ("email_import_auto_scan" in values
            or "email_import_auto_scan_interval_hours" in values):
        scheduler.reschedule_email_import()
    return get_settings()


@app.post("/api/settings/datadome-refresh")
def datadome_refresh(
    portal: str = Query("immobiliare", pattern="^(immobiliare|idealista)$"),
):
    """Opens a local browser to harvest a fresh DataDome cookie and saves it.

    Headful (visible) on purpose: the user triggered it and is present, so if
    the portal shows a CAPTCHA they can solve it once — the persistent profile
    then remembers it. Sync `def` so FastAPI runs the minutes-long browser work
    in a threadpool without owning the event loop (same reasoning as the inbox
    scan, invariant 15)."""
    from .services import cookie_harvester
    if not cookie_harvester.is_available():
        raise HTTPException(400, cookie_harvester.UNAVAILABLE_MESSAGE)
    result = cookie_harvester.refresh_into_settings(portal, headless=False)
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result


@app.post("/api/settings/datadome-refresh/cancel")
def cancel_datadome_refresh():
    """Stops a running "Grab a fresh cookie now" at its next poll (a hard
    block page with no solvable widget otherwise polls for the full headful
    timeout with the visible window stuck open, invariant 16/18). A no-op if
    nothing is running."""
    from .services import cookie_harvester
    cookie_harvester.request_cancel_harvest()
    return {"ok": True}


# pip + a browser download: minutes, not forever. A hung index/mirror must
# not pin a threadpool worker for the process lifetime.
_INSTALL_TIMEOUT_SECONDS = 900


def _require_loopback(request: Request) -> None:
    """The install endpoints run `pip install` and download browser binaries:
    that is code execution on the host, and the API has no authentication.
    On the loopback bind (the default) this is moot; under `serve.bat lan`
    (0.0.0.0) or a Tailscale bind it would let any device on the network
    install arbitrary packages into the venv with one POST — so these two
    endpoints, alone, insist the caller is the local machine."""
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(
            403, "Installation endpoints only work from the PC running the "
                 "app (open the dashboard on http://127.0.0.1:8000)"
        )


@app.post("/api/settings/install-harvester")
def install_harvester(request: Request):
    """Install Playwright package and download Chromium binary into the active virtual environment."""
    import os
    import subprocess
    import sys
    from pathlib import Path
    from .services import cookie_harvester

    _require_loopback(request)
    if cookie_harvester.is_available():
        return {"ok": True, "message": "Playwright is already installed and available."}

    try:
        # 1. Install playwright pip package into current Python environment (.venv)
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"],
                       check=True, timeout=_INSTALL_TIMEOUT_SECONDS)

        # 2. Configure where to install browser binary: the current user's
        # existing ms-playwright cache when there is one (resolved via the
        # environment, never by iterating C:/Users — on a multi-profile
        # machine that picks whichever profile sorts first), else a
        # project-local folder.
        browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        if not browsers_path:
            if os.name == "nt":
                local_appdata = os.environ.get("LOCALAPPDATA")
                local = (Path(local_appdata) if local_appdata
                         else Path.home() / "AppData" / "Local")
                candidate = local / "ms-playwright"
                if candidate.exists():
                    browsers_path = str(candidate)
            if not browsers_path:
                from .config import BASE_DIR
                browsers_path = str(BASE_DIR / "browser_binaries")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path

        env = os.environ.copy()
        if browsers_path:
            env["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path

        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"],
                       check=True, env=env, timeout=_INSTALL_TIMEOUT_SECONDS)

        cookie_harvester._ensure_browsers_path()
        return {"ok": True, "message": "Successfully installed Playwright and Chromium."}
    except Exception as e:
        logging.getLogger(__name__).exception("Failed to install playwright/chromium")
        raise HTTPException(500, f"Installation failed: {type(e).__name__}: {e}")


@app.post("/api/settings/install-camoufox")
def install_camoufox(request: Request):
    """Install Camoufox (stealth Firefox) and fetch its browser binary into the
    active virtual environment. Optional upgrade over Chromium: it hides the
    automation signals DataDome fingerprints, so the check is challenged less."""
    import subprocess
    import sys
    from .services import cookie_harvester

    _require_loopback(request)
    try:
        if not cookie_harvester.is_camoufox_available():
            subprocess.run([sys.executable, "-m", "pip", "install", "camoufox"],
                           check=True, timeout=_INSTALL_TIMEOUT_SECONDS)
        # Downloads the patched Firefox (~150 MB) once; a no-op if already present.
        subprocess.run([sys.executable, "-m", "camoufox", "fetch"],
                       check=True, timeout=_INSTALL_TIMEOUT_SECONDS)
        return {"ok": True, "message": "Successfully installed Camoufox. Set the engine to auto or camoufox in Settings."}
    except Exception as e:
        logging.getLogger(__name__).exception("Failed to install camoufox")
        raise HTTPException(500, f"Installation failed: {type(e).__name__}: {e}")


@app.post("/api/settings/telegram-test")
def telegram_test():
    ok = notifier.send_test_message("telegram")
    if not ok:
        raise HTTPException(
            400,
            "Send failed: verify token, chat ID, and that notifications are enabled",
        )
    return {"ok": True}


@app.post("/api/settings/email-test")
def email_test():
    ok = notifier.send_test_message("email")
    if not ok:
        raise HTTPException(
            400,
            "Send failed: verify SMTP host/credentials, recipient, and that "
            "email notifications are enabled",
        )
    return {"ok": True}


# --- Static frontend (must stay last) ---
#
# Mounting at "/" makes this a catch-all, so it has to be declared after every
# API route or it would shadow them. `html=True` serves index.html for "/" and
# resolves the hashed asset names Vite emits.
#
# The mount is conditional because `frontend/dist` only exists after
# `npm run build`: in the dev flow Vite serves the app itself and the backend
# is API-only. A missing dist is therefore normal, not an error.
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:
    logging.getLogger(__name__).info(
        "frontend/dist not found: serving API only. Run `npm run build` in "
        "frontend/ to serve the dashboard from this port too."
    )
