"""Operations the user runs deliberately from Settings → Data management: the
opt-in geocoding batch and the scoped data resets.

`geocoder` is imported inside each handler, not at module scope, to keep the
import graph of a normal request free of it — the same lazy pattern the optional
browser stack uses.
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
