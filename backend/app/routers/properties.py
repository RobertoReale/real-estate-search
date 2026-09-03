"""The dashboard's own routes: the property grid, one property's card, the
curation actions, the shortlist export and the availability check.

Tags live here rather than in a router of their own because they exist only as
property categories — every one of their routes is reached from a card or from
the grid's filter bar.

**Route order inside this module is load-bearing.** Starlette matches in
registration order, so every literal path under `/api/properties/...` must be
declared before `/api/properties/{property_id}`: an int-typed path parameter
still matches the literal segment first and answers 422 before the literal
route is ever reached. `test_static_frontend.py` pins it.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..models import Property, Tag, property_tags
from ..services import availability_check, exporter
from .selection import annotate, parse_poly_param, select_properties

router = APIRouter()


@router.get("/api/properties", response_model=schemas.PropertyPage)
def list_properties(
    db: Session = Depends(get_db),
    # Paginated by default: the grid used to download the whole filtered set —
    # every property with its market position, deal score and provenance — and
    # the dashboard re-polled it every 30s, every 4s during a scan. `limit=0`
    # asks for everything, which the map (a pin per property) and "select all"
    # genuinely need; those are one-off user actions, not the poll.
    limit: int = Query(50, ge=0, le=5000),
    offset: int = Query(0, ge=0),
    # validated like `contract`/`sort`: a typo'd status would otherwise return
    # an empty list, indistinguishable from "no matches" — a silent failure
    status: str = Query("active", pattern="^(active|filtered|gone|hidden|sold|all)$"),
    contract: str | None = Query(None, pattern="^(sale|rent)$"),
    city: str | None = None,
    zone: str | None = None,
    q: str | None = None,
    source: str | None = Query(None, pattern="^(scan|email)$"),
    profile_id: int | None = None,
    tag: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_sqm: float | None = None,
    max_sqm: float | None = None,
    floor_band: str | None = Query(None, pattern="^(ground|low|mid|high|top)$"),
    rooms: int | None = None,
    portal: str | None = Query(None, pattern="^(immobiliare|idealista)$"),
    agency: str | None = None,
    deal: str | None = Query(None, pattern="^(undervalued|fair_plus)$"),
    min_sqm_price: float | None = None,
    max_sqm_price: float | None = None,
    merged_only: bool = False,
    center_lat: float | None = Query(None, ge=-90, le=90),
    center_lng: float | None = Query(None, ge=-180, le=180),
    radius_m: float | None = Query(None, ge=1, le=100_000),
    poly: str | None = None,
    only_price_drops: bool = False,
    only_favorites: bool = False,
    sort: str = Query(
        "newest",
        pattern="^(newest|price_asc|price_desc|sqm_price|match)$",
    ),
):
    items, total = select_properties(
        db,
        status=status,
        contract=contract,
        city=city,
        min_price=min_price,
        max_price=max_price,
        min_sqm=min_sqm,
        max_sqm=max_sqm,
        floor_band=floor_band,
        rooms=rooms,
        portal=portal,
        agency=agency,
        deal=deal,
        min_sqm_price=min_sqm_price,
        max_sqm_price=max_sqm_price,
        merged_only=merged_only,
        center_lat=center_lat,
        center_lng=center_lng,
        radius_m=radius_m,
        poly_vertices=parse_poly_param(poly),
        only_price_drops=only_price_drops,
        only_favorites=only_favorites,
        sort=sort,
        q=q,
        zone=zone,
        source=source,
        profile_id=profile_id,
        tag=tag,
        # 0 is the caller asking for the unbounded set, which select_properties
        # spells None (a literal LIMIT 0 would mean "no rows")
        limit=limit or None,
        offset=offset,
    )
    return {"items": items, "total": total, "limit": limit or None, "offset": offset}


@router.get("/api/properties/export")
def export_properties(
    db: Session = Depends(get_db),
    fmt: str = Query("html", pattern="^(html|markdown|csv|pdf)$"),
    title: str = "Property shortlist",
    status: str = Query("active", pattern="^(active|filtered|gone|hidden|sold|all)$"),
    contract: str | None = Query(None, pattern="^(sale|rent)$"),
    city: str | None = None,
    zone: str | None = None,
    q: str | None = None,
    source: str | None = Query(None, pattern="^(scan|email)$"),
    profile_id: int | None = None,
    tag: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_sqm: float | None = None,
    max_sqm: float | None = None,
    floor_band: str | None = Query(None, pattern="^(ground|low|mid|high|top)$"),
    rooms: int | None = None,
    portal: str | None = Query(None, pattern="^(immobiliare|idealista)$"),
    agency: str | None = None,
    deal: str | None = Query(None, pattern="^(undervalued|fair_plus)$"),
    min_sqm_price: float | None = None,
    max_sqm_price: float | None = None,
    merged_only: bool = False,
    center_lat: float | None = Query(None, ge=-90, le=90),
    center_lng: float | None = Query(None, ge=-180, le=180),
    radius_m: float | None = Query(None, ge=1, le=100_000),
    poly: str | None = None,
    only_price_drops: bool = False,
    only_favorites: bool = False,
    sort: str = Query("newest", pattern="^(newest|price_asc|price_desc|sqm_price|match)$"),
):
    """Download the currently-filtered shortlist as a self-contained dossier.

    Same selection as the grid, so the file mirrors what the user sees. Returned
    as an attachment (no server, no DB) that can be shared over chat or email —
    the reason the export exists rather than sharing the live dashboard. `pdf`
    is the exception: a print-ready report the browser saves as a PDF itself.

    No `limit`: a dossier holds the whole filtered shortlist, not the page the
    grid happens to be showing."""
    props, _total = select_properties(
        db,
        status=status,
        contract=contract,
        city=city,
        min_price=min_price,
        max_price=max_price,
        min_sqm=min_sqm,
        max_sqm=max_sqm,
        floor_band=floor_band,
        rooms=rooms,
        portal=portal,
        agency=agency,
        deal=deal,
        min_sqm_price=min_sqm_price,
        max_sqm_price=max_sqm_price,
        merged_only=merged_only,
        center_lat=center_lat,
        center_lng=center_lng,
        radius_m=radius_m,
        poly_vertices=parse_poly_param(poly),
        only_price_drops=only_price_drops,
        only_favorites=only_favorites,
        sort=sort,
        q=q,
        zone=zone,
        source=source,
        profile_id=profile_id,
        tag=tag,
    )
    clean_title = (title or "Property shortlist").strip()[:120] or "Property shortlist"
    # `pdf` is the only format served inline: it is a print-ready document that
    # raises the print dialog on load, so it has to be *opened*, not saved. A
    # downloaded copy would sit in the Downloads folder having printed nothing,
    # and the PDF the user is after is what the print dialog writes.
    disposition = "inline" if fmt == "pdf" else "attachment"
    if fmt == "csv":
        body = exporter.properties_to_csv(props)
        media, ext = "text/csv; charset=utf-8", "csv"
    elif fmt == "markdown":
        body = exporter.properties_to_markdown(props, clean_title)
        media, ext = "text/markdown; charset=utf-8", "md"
    elif fmt == "pdf":
        body = exporter.properties_to_print_html(props, clean_title)
        media, ext = "text/html; charset=utf-8", "print.html"
    else:
        body = exporter.properties_to_html(props, clean_title)
        media, ext = "text/html; charset=utf-8", "html"
    filename = f"dossier-{datetime.now(UTC):%Y%m%d}.{ext}"
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


@router.get("/api/properties/check-progress", response_model=schemas.AvailabilityCheckProgressOut)
def properties_check_progress():
    """Live progress of the ongoing dashboard properties availability check.

    Must stay registered before GET /api/properties/{property_id}: Starlette
    matches routes in registration order, and an int-typed path parameter
    still matches the literal segment "check-progress" first, turning every
    poll into a 422 instead of ever reaching this handler — the progress bar
    then never advances past its initial state.
    """
    return availability_check.get_prop_check_progress()


@router.get("/api/properties/{property_id}", response_model=schemas.PropertyOut)
def get_property(property_id: int, db: Session = Depends(get_db)):
    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")
    annotate(db, [prop])
    return prop


@router.patch("/api/properties/{property_id}", response_model=schemas.PropertyOut)
def patch_property(property_id: int, data: schemas.PropertyPatch, db: Session = Depends(get_db)):
    """Updates user-curated fields (favorite flag, personal notes, tags)."""
    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")
    if data.is_favorite is not None:
        prop.is_favorite = data.is_favorite
    if data.notes is not None:
        prop.notes = data.notes
    if data.tag_ids is not None:
        prop.tags = list(db.scalars(select(Tag).where(Tag.id.in_(data.tag_ids))))
    db.commit()
    db.refresh(prop)
    annotate(db, [prop])
    return prop


@router.delete("/api/properties/{property_id}", response_model=schemas.OkOut)
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


@router.post("/api/properties/{property_id}/restore", response_model=schemas.OkOut)
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
    prop.sold_at = None  # also the way back from a mistaken "Mark as sold"
    db.commit()
    return {"ok": True}


@router.post("/api/properties/{property_id}/sold", response_model=schemas.OkOut)
def mark_property_sold(property_id: int, db: Session = Depends(get_db)):
    """Marks the property as sold/rented out.

    Like hiding it, this removes the card from the active grid and stops scans
    from resurfacing or notifying it (invariant 5 — a user choice a scan never
    reverts). Unlike hiding, the property stays a *confirmed* market close:
    `sold_at` gives market_velocity a real sale date instead of the inferred
    "gone" heuristic. Reversible via /restore. This exists for the "VENDUTO"
    re-posts that stay online for weeks and would otherwise never leave the
    grid on their own."""
    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")
    prop.status = "sold"
    prop.sold_at = datetime.now(UTC)
    prop.filtered_reason = ""
    db.commit()
    return {"ok": True}


@router.post("/api/properties/bulk", response_model=schemas.BulkActionOut)
def bulk_properties(data: schemas.PropertyBulkIn, db: Session = Depends(get_db)):
    """Apply hide/restore/favorite/unfavorite to many properties at once.

    Same per-property semantics as the single-item routes (hiding stays
    reversible only via restore, invariant 5), just batched: the point is to
    let the user clear a dashboard cluttered by inbox imports in one gesture
    instead of opening cards one by one. Missing ids are skipped silently."""
    tag_obj = None
    if data.action in ("add_tag", "remove_tag"):
        if data.tag_id is None:
            raise HTTPException(400, "tag_id is required for add_tag/remove_tag")
        tag_obj = db.get(Tag, data.tag_id)
        if not tag_obj:
            raise HTTPException(404, "Tag not found")
    props = [p for p in (db.get(Property, x) for x in data.ids) if p]
    for prop in props:
        if data.action == "hide":
            prop.status = "hidden"
            prop.filtered_reason = ""
        elif data.action == "restore":
            prop.status = "active"
            prop.gone_at = None
            prop.sold_at = None
        elif data.action == "sold":
            prop.status = "sold"
            prop.sold_at = datetime.now(UTC)
            prop.filtered_reason = ""
        elif data.action == "favorite":
            prop.is_favorite = True
        elif data.action == "unfavorite":
            prop.is_favorite = False
        elif data.action == "add_tag" and tag_obj is not None:
            if tag_obj not in prop.tags:
                prop.tags.append(tag_obj)
        elif data.action == "remove_tag":
            if tag_obj in prop.tags:
                prop.tags.remove(tag_obj)
    db.commit()
    return {"ok": True, "processed": len(props)}


@router.get("/api/tags", response_model=list[schemas.TagOut])
def list_tags(db: Session = Depends(get_db)):
    """All user-defined tags with their usage count, feeding both the
    dashboard's tag filter dropdown and the per-property tag picker's
    autocomplete."""
    rows = db.execute(
        select(Tag, func.count(property_tags.c.property_id))
        .outerjoin(property_tags, property_tags.c.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(Tag.name)
    ).all()
    return [schemas.TagOut(id=tag.id, name=tag.name, count=count) for tag, count in rows]


@router.post("/api/tags", response_model=schemas.TagOut)
def create_tag(data: schemas.TagCreate, db: Session = Depends(get_db)):
    """Creates a tag, or returns the existing one on a case-insensitive name
    match: idempotent so the freeform "type and press Enter" UI can always
    POST without checking for a duplicate first."""
    name = data.name.strip()
    if not name:
        raise HTTPException(400, "Tag name cannot be empty")
    normalized = name.lower()
    existing = db.scalar(select(Tag).where(Tag.name_normalized == normalized))
    if existing:
        return schemas.TagOut(id=existing.id, name=existing.name)
    tag = Tag(name=name, name_normalized=normalized)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return schemas.TagOut(id=tag.id, name=tag.name)


@router.delete("/api/tags/{tag_id}", response_model=schemas.OkOut)
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    """Deletes a tag globally, detaching it from every property that carried
    it (the properties themselves are untouched). SQLite here has no FK
    cascade configured, so the association rows are removed explicitly in the
    same transaction before the Tag row itself."""
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    db.execute(delete(property_tags).where(property_tags.c.tag_id == tag_id))
    db.delete(tag)
    db.commit()
    return {"ok": True}


@router.post("/api/properties/check", response_model=schemas.AvailabilityCheckSummaryOut)
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
        raise HTTPException(400, str(e)) from e


@router.post("/api/properties/check/cancel", response_model=schemas.OkOut)
def cancel_properties_check():
    """Stops the running batch after its current property (invariant 16's
    pacing means each one can take several seconds, so this is not instant).
    A no-op if nothing is running."""
    availability_check.request_cancel()
    return {"ok": True}


@router.post("/api/properties/{property_id}/check", response_model=schemas.PropertyCheckOut)
def check_single_property(property_id: int, db: Session = Depends(get_db)):
    """Runs AdProbe live availability check on a single property."""
    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")
    try:
        summary = availability_check.check_properties_availability(db, [prop])
    except availability_check.AvailabilityCheckError as e:
        raise HTTPException(400, str(e)) from e
    annotate(db, [prop])
    return {
        "property": schemas.PropertyOut.model_validate(prop).model_dump(mode="json"),
        "summary": summary,
    }


@router.get("/api/properties/{property_id}/audit", response_model=schemas.ListingAuditOut | None)
def get_property_audit(property_id: int, db: Session = Depends(get_db)):
    """The stored reading of this listing's text, or null if none was asked for.

    Reads the row and nothing else — never the model — so the detail modal can
    show an audit the user already paid for without spending a request every
    time a card is opened. Same split as the commute annotation: what is cached
    is free, what costs something needs a press."""
    from ..services import listing_auditor

    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")
    return listing_auditor.stored_audit(db, prop)


@router.post("/api/properties/{property_id}/audit", response_model=schemas.ListingAuditOut)
def audit_property_listing(
    property_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
):
    """Reads this property's listing text with the configured model (opt-in).

    A sync `def` on purpose, like the availability check: a local model can take
    a minute to answer, and the threadpool keeps the rest of the API responsive
    meanwhile instead of the event loop being owned by one card's request.

    Everything that can go wrong — the feature off, no endpoint configured, an
    ad with no description, a model that does not answer — comes back as a
    readable 400. Nothing about the property changes either way."""
    from ..services import listing_auditor

    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")
    try:
        return listing_auditor.audit_property(db, prop, force=force)
    except listing_auditor.ListingAuditError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/api/properties/{property_id}/geocode", response_model=schemas.PropertyGeocodeOut)
def geocode_single_property(property_id: int, db: Session = Depends(get_db)):
    """On-demand geocoding for one property, backing the card's "View on map"
    when the pin is still missing. Reuses the cached, paced Nominatim path
    (`geocoder.geocode_property`); already-located properties short-circuit.
    Fail-open: a lookup the portal's address is too vague to resolve is not an
    error — `located` tells the UI whether a pin now exists."""
    from ..services import geocoder

    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")
    if prop.latitude is None or prop.longitude is None:
        geocoder.geocode_property(db, prop)
    annotate(db, [prop])
    return {
        "property": schemas.PropertyOut.model_validate(prop).model_dump(mode="json"),
        "located": prop.latitude is not None and prop.longitude is not None,
    }
