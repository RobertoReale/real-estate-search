"""APScheduler: executes automatic scanning at configurable intervals
without blocking API requests."""

import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import load_settings
from ..database import SessionLocal
from ..models import SearchProfile
from . import backup, email_import, pricing_stats
from .scanner import run_scan
from .timeutils import as_utc

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()
JOB_ID = "auto-scan"
BACKUP_JOB_ID = "auto-backup"
EMAIL_IMPORT_JOB_ID = "auto-email-import"
SNAPSHOT_JOB_ID = "pricing-snapshot"


def _snapshot_job() -> None:
    """Daily/startup capture of the pricing medians for the trend charts.
    A scan usually beats it to today's snapshot (both are idempotent per day);
    this job covers long stretches with no scan and the moment right after
    startup, same reasoning as the backup freshness check."""
    db = SessionLocal()
    try:
        pricing_stats.maybe_snapshot(db)
    finally:
        db.close()


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
    last_runs = list(
        db.scalars(select(SearchProfile.last_run_at).where(SearchProfile.is_active.is_(True)))
    )
    if not last_runs:
        return False
    newest = max((t for t in last_runs if t is not None), default=None)
    if newest is None:
        return True
    return datetime.now(UTC) - as_utc(newest) > timedelta(minutes=interval_minutes)


def start_scheduler():
    interval = int(load_settings().get("scan_interval_minutes", 60))
    scan_job_args = {}
    db = SessionLocal()
    try:
        if _scan_overdue(db, interval):
            first_run = datetime.now(UTC) + timedelta(seconds=CATCHUP_DELAY_SECONDS)
            scan_job_args["next_run_time"] = first_run
            logger.info(
                "Last scan is older than the %s-minute interval: catch-up scan in %s seconds",
                interval,
                CATCHUP_DELAY_SECONDS,
            )
    finally:
        db.close()
    _scheduler.add_job(
        run_scan,
        "interval",
        minutes=interval,
        id=JOB_ID,
        max_instances=1,
        coalesce=True,
        **scan_job_args,
    )
    # freshness check at startup (see backup.py for why a daily job alone
    # would not be enough), plus a daily job for long-running sessions
    backup.maybe_backup()
    _scheduler.add_job(
        backup.maybe_backup,
        "interval",
        hours=24,
        id=BACKUP_JOB_ID,
        max_instances=1,
        coalesce=True,
    )
    _configure_email_import(load_settings())
    _snapshot_job()  # capture today's medians at startup if not done yet
    _scheduler.add_job(
        _snapshot_job,
        "interval",
        hours=24,
        id=SNAPSHOT_JOB_ID,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("Scheduler started: scan every %s minutes", interval)


def reschedule(interval_minutes: int):
    if _scheduler.get_job(JOB_ID):
        _scheduler.reschedule_job(JOB_ID, trigger="interval", minutes=interval_minutes)
        logger.info("Scheduler updated: every %s minutes", interval_minutes)


def _email_import_schedule(settings: dict) -> tuple[bool, int]:
    """Pure decision behind the inbox re-scan job: (enabled, interval_hours).

    Split from the APScheduler wiring so it can be tested offline, exactly like
    `_scan_overdue` — the wiring itself stays untested by design. The floor of 1
    hour mirrors the schema validator and guards against a hand-edited
    settings.json asking for a 0-hour (i.e. every-tick) mailbox hammering."""
    enabled = bool(settings.get("email_import_auto_scan"))
    hours = max(1, int(settings.get("email_import_auto_scan_interval_hours") or 24))
    return enabled, hours


def _configure_email_import(settings: dict) -> None:
    """Add, reschedule, or remove the opt-in inbox re-scan job to match the
    current settings. Called at startup and whenever the settings change, so the
    toggle in the UI takes effect without a restart. Not run at startup itself:
    the job must not reach into the mailbox merely because the app booted —
    the interval trigger (with coalesce) fires it, and covers downtime."""
    enabled, hours = _email_import_schedule(settings)
    existing = _scheduler.get_job(EMAIL_IMPORT_JOB_ID)
    if not enabled:
        if existing:
            _scheduler.remove_job(EMAIL_IMPORT_JOB_ID)
            logger.info("Email-import auto-scan disabled")
        return
    if existing:
        _scheduler.reschedule_job(EMAIL_IMPORT_JOB_ID, trigger="interval", hours=hours)
    else:
        _scheduler.add_job(
            email_import.auto_scan_job,
            "interval",
            hours=hours,
            id=EMAIL_IMPORT_JOB_ID,
            max_instances=1,
            coalesce=True,
        )
    logger.info("Email-import auto-scan every %s hours", hours)


def reschedule_email_import():
    """Reconfigure the inbox re-scan job from the persisted settings."""
    _configure_email_import(load_settings())


def next_run_time() -> str | None:
    job = _scheduler.get_job(JOB_ID)
    return job.next_run_time.isoformat() if job and job.next_run_time else None


def shutdown():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
