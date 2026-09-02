"""Running a scan and reporting on it: the manual trigger, the dashboard's poll,
and the per-portal scraping health panel.

`/api/scrapers/status` is the busiest route in the app — the dashboard polls it
every 30s, every 4s during a scan — which is why the "did anything change?"
fingerprint lives here beside it rather than being answered by re-downloading
the grid.
"""

import threading

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import schemas
from ..config import load_settings
from ..database import get_db
from ..models import PriceHistory, Property
from ..services import scheduler
from ..services.scanner import get_scan_journal, get_scan_progress, run_scan, scan_state

router = APIRouter()


@router.get("/api/scraper-health")
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


@router.post("/api/scrapers/trigger")
def trigger_scan(profile_id: int | None = None):
    if scan_state["running"]:
        return {"status": "already_running"}
    # a user-triggered scan is explicit intent: it runs even while automatic
    # scanning is paused (scanner.run_scan's `manual` flag)
    thread = threading.Thread(
        target=run_scan, args=(profile_id,), kwargs={"manual": True}, daemon=True
    )
    thread.start()
    return {"status": "started"}


def _properties_version(db: Session) -> str:
    """A cheap fingerprint of the property set, for the dashboard's poll.

    This is the "did anything change?" half of the polling split. The dashboard
    used to answer that question by re-downloading every filtered property —
    market position, match score, deal score and provenance computed for each —
    every 30 seconds, and every 4 seconds during a scan. Now it polls this
    string and refetches the grid only when it moves.

    Two small aggregates. The per-status counts are what make it trustworthy:
    a new property raises one, and every lifecycle transition — a scan marking
    rows `gone`, the user hiding one or marking it `sold` — moves a row from one
    bucket to another, which the grid must reflect because those rows enter or
    leave it. Grouping rather than a single total is the difference: hiding a
    property leaves `count(*)` exactly where it was. `max(last_seen_at)` catches
    a scan that re-found existing listings and changed nothing else, and the
    newest price-history id catches a price change on a property already shown.

    Not a perfect change detector, and it does not try to be: editing notes or
    toggling a favourite moves none of these. Those are user actions, and the
    client that performs one already refreshes on the response — the poll is for
    what happens *elsewhere*, which is scans. The 30s idle poll is the backstop.
    """
    rows = db.execute(
        select(
            Property.status,
            func.count(Property.id),
            func.max(Property.id),
            func.max(Property.last_seen_at),
        ).group_by(Property.status)
    ).all()
    last_price = db.execute(select(func.max(PriceHistory.id))).scalar()
    buckets = ";".join(
        f"{status}:{count}:{max_id}:{last_seen}"
        for status, count, max_id, last_seen in sorted(rows, key=lambda r: r[0] or "")
    )
    return f"{buckets}|{last_price}"


@router.get("/api/scrapers/status", response_model=schemas.ScraperStatusOut)
def scraper_status(db: Session = Depends(get_db)):
    """Everything the dashboard needs to poll for, in one answer.

    The live progress rides along rather than getting a route of its own
    precisely because this endpoint is *already* the one polled every 4s during
    a scan: a second poll beside it would double the traffic to say something
    about the same moment. The journal is the opposite case — it changes once
    per search, is read when somebody asks, and has its own route below.
    """
    return {
        **scan_state,
        "next_auto_run": scheduler.next_run_time(),
        "paused": bool(load_settings().get("scanning_paused")),
        "data_version": _properties_version(db),
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
