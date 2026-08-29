"""Operations the user runs deliberately from Settings → Data management: the
opt-in geocoding batch, the opt-in commute batch, and the scoped data resets.

`geocoder` and `commute` are imported inside each handler, not at module scope,
to keep the import graph of a normal request free of them — the same lazy
pattern the optional browser stack uses.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import data_reset
from ..services.scanner import scan_state

router = APIRouter()


@router.post("/api/maintenance/geocode-missing")
def geocode_missing_endpoint(db: Session = Depends(get_db)):
    """Fills in map coordinates for properties that have an address/zone but no
    pin, via Nominatim (opt-in, batched, paced, cached). Fails open: a lookup
    that cannot resolve leaves the property untouched."""
    from ..services import geocoder

    try:
        return geocoder.geocode_missing_properties(db, max_calls=None)
    except geocoder.GeocoderError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/api/maintenance/geocode-progress")
def geocode_progress_endpoint():
    from ..services import geocoder

    return geocoder.get_geocode_progress()


@router.post("/api/maintenance/geocode-cancel")
def geocode_cancel_endpoint():
    from ..services import geocoder

    geocoder.request_cancel()
    return {"ok": True}


@router.post("/api/maintenance/geocode-clear-cache")
def geocode_clear_cache_endpoint(db: Session = Depends(get_db)):
    """Forget cached geocoding *misses* so the next "Find coordinates" retries
    them. A transient empty answer from Nominatim gets frozen as a permanent
    NULL that the paced batch never re-asks; this clears exactly those rows,
    keeping the positive lookups we already paid for. Only touches the lookup
    cache, never a property's coordinates."""
    from ..services import geocoder

    cleared = geocoder.clear_geocode_cache(db, misses_only=True)
    return {"cleared": cleared}


@router.post("/api/maintenance/commutes")
def compute_commutes_endpoint(db: Session = Depends(get_db)):
    """Routes every property/saved-place pair that is not cached yet, via OSRM
    (opt-in, batched, paced, cached). Fails open: a leg that cannot be routed
    leaves that card with no commute rather than a made-up number.

    Sync `def` like the availability check, and for the same reason (invariant
    15's surviving rule): a batch over hundreds of pins is minutes of blocking
    work, so it belongs on the threadpool where `/commute-progress` stays
    answerable instead of owning the event loop and freezing the progress bar.
    """
    from ..services import commute

    try:
        return commute.compute_missing_commutes(db, max_calls=None)
    except commute.CommuteError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/api/maintenance/commute-progress")
def commute_progress_endpoint():
    from ..services import commute

    return commute.get_commute_progress()


@router.post("/api/maintenance/commute-cancel")
def commute_cancel_endpoint():
    from ..services import commute

    commute.request_cancel()
    return {"ok": True}


@router.post("/api/maintenance/commute-clear-cache")
def commute_clear_cache_endpoint(db: Session = Depends(get_db)):
    """Forget every routed leg so the next run recomputes them — what the user
    presses after moving a saved place, since the cached answer to the old pin
    is otherwise the one thing that keeps looking right."""
    from ..services import commute

    cleared = commute.clear_commute_cache(db)
    return {"cleared": cleared}


@router.post("/api/maintenance/omi-import")
def omi_import_endpoint(path: str = "", db: Session = Depends(get_db)):
    """Imports one semester of OMI quotations from the file the owner downloaded
    (services/omi_import.py). `path` overrides the configured `omi_input_dir`
    for a one-off import; empty uses the setting.

    Always answers with both numbers — how many quotations landed and how many
    source rows were skipped — because a partial import that reports only its
    successes is indistinguishable from a complete one.
    """
    from ..services import omi_import

    try:
        return omi_import.import_quotations(db, path or None)
    except omi_import.OmiImportError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/maintenance/omi-zones-import")
def omi_zones_import_endpoint(path: str = "", db: Session = Depends(get_db)):
    """Imports the OMI zone perimeters (KML) from the same delivery
    (services/omi_zones.py). `path` overrides `omi_input_dir` for a one-off.

    **Runs after the quotations, not before**: it keeps perimeters only for the
    comuni those cover, because the national supply is ~28 000 zones and a
    perimeter with no price behind it can produce no benchmark. With nothing
    imported yet this answers 400 saying so, rather than storing 340 MB of
    geometry nobody can look anything up in.

    Sync `def` like the batches above: reading thousands of files is seconds of
    blocking work that belongs on the threadpool, not on the event loop.
    """
    from ..services import omi_zones

    try:
        return omi_zones.import_zones(db, path or None)
    except omi_zones.OmiImportError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/maintenance/omi-zones-resolve")
def omi_zones_resolve_endpoint(db: Session = Depends(get_db)):
    """Places every property with coordinates inside its OMI micro-zone.

    The user-triggered half of the same split the geocoder and the commute batch
    make: the answer is stored on the property, so a grid page reads a column
    instead of ray-casting hundreds of vertices per card. Offline and
    arithmetic-only — nothing to pace, so no progress or cancel endpoint.

    Fails open: a property with no coordinates, or a pin that falls in no
    imported zone, is reported in the counts and gets no OMI benchmark. Never an
    error.
    """
    from ..services import omi_zones

    return omi_zones.resolve_property_zones(db)


# Scoped, irreversible data resets (Settings → Data management). Each is a
# distinct deliberate choice, so they are separate scopes rather than flags on
# one call. `factory` and `dashboard` delete rows a running scan is writing, so
# they refuse while one is in flight; `factory` snapshots the DB first.
_RESET_SCOPES = ("dashboard", "pricing-snapshots", "factory")


@router.post("/api/maintenance/reset/{scope}")
def maintenance_reset(scope: str, db: Session = Depends(get_db)):
    if scope not in _RESET_SCOPES:
        raise HTTPException(400, f"Unknown reset scope: {scope}")
    if scope in ("dashboard", "factory") and scan_state["running"]:
        raise HTTPException(409, "A scan is running: wait for it to finish before resetting")
    fn = {
        "dashboard": data_reset.clear_dashboard,
        "pricing-snapshots": data_reset.clear_pricing_snapshots,
        "factory": data_reset.factory_reset,
    }[scope]
    try:
        return fn(db)
    except data_reset.ResetError as e:
        raise HTTPException(500, str(e)) from e
