"""Running a scan and reporting on it: the manual trigger, the status the
dashboard falls back to, and the per-portal scraping health panel.

`/api/scrapers/status` used to be the busiest route in the app — polled every
30s, every 4s during a scan. `GET /api/events` (`services/events.py`) is what
the dashboard listens to instead, and the "did anything change?" fingerprint
moved there with it, since the stream is now its main reader.
"""

import threading

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import schemas
from ..config import load_settings
from ..database import get_db
from ..services import scheduler
from ..services.events import properties_version
from ..services.scanner import get_scan_journal, get_scan_progress, run_scan, scan_state

router = APIRouter()


@router.get("/api/scraper-health", response_model=schemas.ScraperHealthOut)
def scraper_health_endpoint(
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """Per-portal scraping health over the window: daily
    attempts/blocked/errors accumulated at scan time, the transport that
    carried the last scan, and the live per-profile failure streaks. This is
    the panel that turns "scans mysteriously stopped" into a visible trend and
    says when to add proxies or a scrape-API key."""
    from ..scrapers import transport_policy
    from ..services import scraper_health

    settings = load_settings()
    health = scraper_health.get_health(db, days=days)
    worst_streak = max((p["consecutive_failures"] for p in health["profiles"]), default=0)
    health["transport"] = transport_policy.decide(worst_streak, settings).label
    return health


@router.post("/api/scrapers/trigger", response_model=schemas.ScanTriggerOut)
def trigger_scan(profile_id: int | None = None, full: bool = False):
    """Start a scan now. `full=true` asks for a full sweep.

    An ordinary scan stops paging a search as soon as a page holds nothing new,
    which is fast and is partial; `full` is how the user demands the complete
    reading without waiting for `full_sweep_every_days` to come round. The scan
    surface being rebuilt (plan D.8) is where this belongs as a control — until
    then the query parameter is the whole of it.
    """
    if scan_state["running"]:
        return {"status": "already_running"}
    # a user-triggered scan is explicit intent: it runs even while automatic
    # scanning is paused (scanner.run_scan's `manual` flag)
    thread = threading.Thread(
        target=run_scan,
        args=(profile_id,),
        kwargs={"manual": True, "full_sweep": full},
        daemon=True,
    )
    thread.start()
    return {"status": "started"}


@router.get("/api/scrapers/status", response_model=schemas.ScraperStatusOut)
def scraper_status(db: Session = Depends(get_db)):
    """Everything the dashboard needs, in one answer.

    `GET /api/events` is how the dashboard normally learns all of this now, and
    this route is what it falls back to when that stream cannot be opened at all
    — an old backend behind a new build, a proxy that will not carry a streaming
    response. It is also the honest answer to "what is happening?" for anything
    that is not a browser, so it stays a plain request/response route and keeps
    the shape the stream's `status` topic sends.

    The live progress rides along rather than getting a route of its own
    precisely because this endpoint is the one a fallback client polls: a second
    poll beside it would double the traffic to say something about the same
    moment. The journal is the opposite case — it changes once per search, is
    read when somebody asks, and has its own route below.
    """
    return {
        **scan_state,
        "next_auto_run": scheduler.next_run_time(),
        "paused": bool(load_settings().get("scanning_paused")),
        "data_version": properties_version(db),
        "progress": get_scan_progress(),
    }


@router.get("/api/scans/journal", response_model=list[schemas.ScanJournalEntryOut])
def scan_journal():
    """The recent scans, per search, newest first.

    "Did it work?" is asked after a scan at least as often as during one, and
    for the person who left the room it is the only question. Readable when
    nothing is running, which is the state it is mostly read in.
    """
    return get_scan_journal()
