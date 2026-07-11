"""Periodic on-disk copies of case.db.

Months of price history and days-on-market data live in a single SQLite file
that no re-scan can rebuild: a disk failure or a botched migration would erase
them for good. The sqlite3 backup API takes a consistent snapshot even while
the app is writing, so copying is always safe.

A copy is taken at most once per BACKUP_EVERY. The freshness check runs at
startup rather than relying only on a scheduled job, because this app lives on
a PC that is switched on occasionally: a daily job on a process that rarely
lives 24 hours would never fire (the same reasoning as the scheduler's
catch-up scan). The backups folder is local — syncing it to a second drive or
a cloud-synced folder is up to the user (see README).
"""
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import BASE_DIR, DB_PATH

logger = logging.getLogger(__name__)

BACKUP_DIR = BASE_DIR / "backups"
BACKUP_EVERY = timedelta(hours=24)
BACKUP_KEEP = 14


def maybe_backup(db_path: Path = DB_PATH, backup_dir: Path = BACKUP_DIR,
                 force: bool = False) -> Path | None:
    """Copies the database unless a recent backup already exists.

    Returns the new backup file, or None when skipped. Never raises: a failed
    backup round must not take down the scheduler (or startup) with it. `force`
    bypasses the once-per-day throttle — used right before a destructive reset,
    where a snapshot must be taken no matter how recently one was.
    """
    try:
        if not db_path.exists():
            # fresh install: nothing to protect yet
            return None
        backup_dir.mkdir(parents=True, exist_ok=True)
        existing = sorted(
            backup_dir.glob("case-*.db"), key=lambda p: p.stat().st_mtime
        )
        if existing and not force:
            newest = datetime.fromtimestamp(
                existing[-1].stat().st_mtime, tz=timezone.utc
            )
            if datetime.now(timezone.utc) - newest < BACKUP_EVERY:
                return None
        target = backup_dir / f"case-{datetime.now():%Y%m%d-%H%M%S}.db"
        src = sqlite3.connect(db_path)
        try:
            dst = sqlite3.connect(target)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        # oldest copies beyond BACKUP_KEEP (counting the one just written)
        for old in existing[: max(0, len(existing) + 1 - BACKUP_KEEP)]:
            old.unlink()
        logger.info("DB backup written: %s", target.name)
        return target
    except Exception:
        logger.exception("DB backup failed")
        return None
