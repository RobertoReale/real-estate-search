"""APScheduler: executes automatic scanning at configurable intervals
without blocking API requests."""
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import load_settings
from ..database import SessionLocal
from ..models import SearchProfile
from . import backup
from .scanner import run_scan

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()
JOB_ID = "auto-scan"
BACKUP_JOB_ID = "auto-backup"

# An interval trigger first fires one *full interval* after startup — and on a
# PC that is switched on occasionally that moment may never come: with an
# 8-hour interval, sessions shorter than 8 hours never run a scheduled scan at
# all. When the last scan is already older than the interval, run a catch-up
# scan shortly after startup instead of waiting a full interval again. The
# delay keeps rapid dev restarts (uvicorn --reload re-launches on every file
# save) from turning each save into a scan; once the catch-up has run,
# last_run_at is fresh and later restarts wait normally.
CATCHUP_DELAY_SECONDS = 120


def _scan_overdue(db: Session, interval_minutes: int) -> bool:
    """True when the newest scan across active profiles is older than the
    configured interval (or never happened). No active profiles means there is
    nothing to catch up on."""
    last_runs = list(db.scalars(
        select(SearchProfile.last_run_at)
        .where(SearchProfile.is_active.is_(True))
    ))
    if not last_runs:
        return False
    newest = max((t for t in last_runs if t is not None), default=None)
    if newest is None:
        return True
    if newest.tzinfo is None:
        # SQLite returns naive datetimes; values are written as UTC
        newest = newest.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - newest > timedelta(minutes=interval_minutes)


def start_scheduler():
    interval = int(load_settings().get("scan_interval_minutes", 60))
    scan_job_args = {}
    db = SessionLocal()
    try:
        if _scan_overdue(db, interval):
            first_run = datetime.now(timezone.utc) + timedelta(
                seconds=CATCHUP_DELAY_SECONDS)
            scan_job_args["next_run_time"] = first_run
            logger.info(
                "Last scan is older than the %s-minute interval: "
                "catch-up scan in %s seconds", interval, CATCHUP_DELAY_SECONDS,
            )
    finally:
        db.close()
    _scheduler.add_job(
        run_scan, "interval", minutes=interval, id=JOB_ID,
        max_instances=1, coalesce=True, **scan_job_args,
    )
    # freshness check at startup (see backup.py for why a daily job alone
    # would not be enough), plus a daily job for long-running sessions
    backup.maybe_backup()
    _scheduler.add_job(
        backup.maybe_backup, "interval", hours=24, id=BACKUP_JOB_ID,
        max_instances=1, coalesce=True,
    )
    _scheduler.start()
    logger.info("Scheduler started: scan every %s minutes", interval)


def reschedule(interval_minutes: int):
    if _scheduler.get_job(JOB_ID):
        _scheduler.reschedule_job(JOB_ID, trigger="interval", minutes=interval_minutes)
        logger.info("Scheduler updated: every %s minutes", interval_minutes)


def next_run_time() -> str | None:
    job = _scheduler.get_job(JOB_ID)
    return job.next_run_time.isoformat() if job and job.next_run_time else None


def shutdown():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
