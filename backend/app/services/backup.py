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
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..config import BACKUP_DIR, DB_PATH

logger = logging.getLogger(__name__)

BACKUP_EVERY = timedelta(hours=24)
BACKUP_KEEP = 14
PRE_UPGRADE_PREFIX = "case-pre-"


def _copy(db_path: Path, target: Path) -> None:
    """The one way this module copies a database: through the sqlite3 backup
    API, never as a file copy, so the un-checkpointed WAL comes with it."""
    src = sqlite3.connect(db_path)
    try:
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def _daily_copies(backup_dir: Path) -> list[Path]:
    """The rotating daily copies, oldest first.

    Pre-upgrade snapshots live in the same folder and share the `case-` prefix,
    but they are deliberately outside the rotation and are filtered out here so
    they neither satisfy the freshness gate nor count towards BACKUP_KEEP. A
    daily copy is one of fourteen; a pre-upgrade copy is the only image of the
    schema the user is leaving, and it is always the oldest file in the folder
    — counting it would make it the first thing pruned, which is exactly the
    file worth keeping longest.
    """
    return sorted(
        (p for p in backup_dir.glob("case-*.db") if not p.name.startswith(PRE_UPGRADE_PREFIX)),
        key=lambda p: p.stat().st_mtime,
    )


def maybe_backup(
    db_path: Path = DB_PATH, backup_dir: Path = BACKUP_DIR, force: bool = False
) -> Path | None:
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
        existing = _daily_copies(backup_dir)
        if existing and not force:
            newest = datetime.fromtimestamp(existing[-1].stat().st_mtime, tz=UTC)
            if datetime.now(UTC) - newest < BACKUP_EVERY:
                return None
        target = backup_dir / f"case-{datetime.now():%Y%m%d-%H%M%S}.db"
        _copy(db_path, target)
        # oldest copies beyond BACKUP_KEEP (counting the one just written)
        for old in existing[: max(0, len(existing) + 1 - BACKUP_KEEP)]:
            old.unlink()
        logger.info("DB backup written: %s", target.name)
        return target
    except Exception:
        logger.exception("DB backup failed")
        return None


def snapshot_before_migration(
    revision: str, db_path: Path = DB_PATH, backup_dir: Path = BACKUP_DIR
) -> Path | None:
    """Copies the database as it stands *before* a schema migration changes it.

    The daily copy above cannot serve this purpose, however recently it ran:
    it is scheduled from `scheduler.start_scheduler`, which starts after
    `init_db()` has already migrated, so on the one startup where "a botched
    migration" was the thing to protect against, the copy was taken after the
    event. This one is taken first, by `database._snapshot_before_upgrade`, and
    is named for the revision the database is leaving so the file says what it
    is a copy of. `_daily_copies` keeps it out of the rotation.

    Taken once per revision: if the snapshot is already there, an earlier
    attempt to leave the same revision made it, and that copy is the older and
    more faithful of the two.

    Never raises — a snapshot that cannot be written must not stop startup —
    but logs at error level rather than warning, because the outcome is a
    migration running with no net under it.
    """
    # the revision is read out of the database, so it never becomes a path
    target = backup_dir / f"{PRE_UPGRADE_PREFIX}{re.sub(r'[^A-Za-z0-9._-]', '_', revision)}.db"
    try:
        if not db_path.exists():
            return None
        if target.exists():
            return target
        backup_dir.mkdir(parents=True, exist_ok=True)
        _copy(db_path, target)
        logger.info("pre-upgrade DB snapshot written: %s", target.name)
        return target
    except Exception:
        logger.error(
            "could not snapshot the database before migrating it off %s: "
            "the migration is about to run with no backup to fall back on",
            revision,
            exc_info=True,
        )
        return None
