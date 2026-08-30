"""Operations the user runs deliberately from Settings → Data management: the
opt-in geocoding batch, the opt-in commute batch, the scoped data resets, and
the backups — listing, taking, downloading, restoring and importing them.

`geocoder` and `commute` are imported inside each handler, not at module scope,
to keep the import graph of a normal request free of them — the same lazy
pattern the optional browser stack uses.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import backups_dir, engine_db_path, get_db
from ..services import backup, data_reset
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


# --- Backups (Settings → Data management) ---
#
# The copies in `backups/` were written for months and never read back, so the
# only way to use one was to stop the app and move files by hand — with the two
# WAL companions, which is the part nobody knows. These five routes are the way
# back in: what is there, take one now, download one, restore one, bring one in.
#
# **Invariant 14.** They live under `/api` like everything else and inherit the
# access control unchanged: loopback by default, `api_auth_token` when the bind
# is widened. Restoring overwrites the entire database, which makes it the most
# powerful endpoint in the app — and therefore the last one that may ever become
# a reason to open the bind further. It adds no auth of its own and asks for
# none.
#
# The literal `/import` path is registered before `/{name}` for the reason the
# properties module spells out: Starlette matches in registration order, and a
# path parameter declared first swallows every literal that follows it.


def _live_database() -> tuple[Path, Path]:
    """The database that is open right now, and the folder holding its copies.

    Resolved through the engine rather than `config.DB_PATH`, because the engine
    is the single symbol that decides which database the app talks to — a
    restore aimed anywhere else would be a restore of the wrong file.
    """
    db_path = engine_db_path()
    if db_path is None:
        raise HTTPException(503, "This instance has no database file to back up.")
    return db_path, backups_dir()


@router.get("/api/maintenance/backups")
def list_backups_endpoint():
    """The copies on disk, newest first, each with its date, size and schema
    revision. The folder is reported too: it is a real path on the user's own
    machine, and knowing it is what makes the copies usable outside the app."""
    _, folder = _live_database()
    return {"folder": str(folder), "backups": backup.list_copies(folder)}


@router.post("/api/maintenance/backups")
def create_backup_endpoint():
    """Take a copy now, ignoring the once-a-day throttle — the button pressed
    before doing something risky, where "there was already one this morning" is
    not the answer the user wants."""
    db_path, folder = _live_database()
    path = backup.maybe_backup(db_path, folder, force=True)
    if path is None:
        raise HTTPException(
            500,
            f"The copy could not be written. Check disk space and permissions for {folder}.",
        )
    return backup.describe(path)


@router.post("/api/maintenance/backups/import")
async def import_backup_endpoint(request: Request):
    """Bring in a `case.db` carried from another install.

    The body is the file itself, not a multipart form: this app ships with a
    deliberately small dependency set, and a raw body needs nothing that is not
    already installed. Streamed to a staging file rather than read into memory —
    a database is as large as the user's history, and this endpoint exists for
    the person whose history is long.

    The staged copy is validated before it is filed, and never touches the live
    database: importing puts it in the list, restoring is a separate, explicit
    step.
    """
    _, folder = _live_database()
    folder.mkdir(parents=True, exist_ok=True)
    # not `case-*.db`: a half-written upload must not appear in the listing, and
    # must never be a candidate for the rotation or for a restore
    staged = folder / f"import-{id(request):x}.part"
    try:
        with staged.open("wb") as fh:
            async for chunk in request.stream():
                fh.write(chunk)
        return backup.describe(backup.accept_import(staged, folder))
    except backup.RestoreError as e:
        raise HTTPException(400, str(e)) from e
    finally:
        # accept_import renamed it away on success and removed it on failure;
        # this catches the third case, a connection that dropped mid-upload
        staged.unlink(missing_ok=True)


@router.get("/api/maintenance/backups/{name}")
def download_backup_endpoint(name: str):
    """Hand a copy to the browser, so the user's data can leave the machine in a
    form that can come back. It is also the honest answer to "am I locked in?" —
    the file is a plain SQLite database, readable by anything."""
    _, folder = _live_database()
    try:
        path = backup.find(name, folder)
    except backup.RestoreError as e:
        raise HTTPException(404, str(e)) from e
    return FileResponse(path, media_type="application/vnd.sqlite3", filename=path.name)


@router.post("/api/maintenance/backups/{name}/restore")
def restore_backup_endpoint(name: str):
    """Replace the live database with one of the copies.

    Refused mid-scan (409) for the same reason the destructive resets and the
    restart are: a scan is writing properties and their profile links, and
    swapping the file under it would leave both half-written.

    The response names the copy of the *previous* state that was taken first, so
    the UI can say what to restore if this was the wrong file.
    """
    if scan_state["running"]:
        raise HTTPException(409, "A scan is running: wait for it to finish before restoring")
    db_path, folder = _live_database()
    try:
        source = backup.find(name, folder)
    except backup.RestoreError as e:
        raise HTTPException(404, str(e)) from e
    try:
        restored, safety = backup.restore(source, db_path, folder)
    except backup.RestoreError as e:
        raise HTTPException(400, str(e)) from e
    return {"restored": restored.name, "backup": safety.name if safety else None}
