"""On-disk copies of case.db, and the way back from one.

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

Taking copies is only half of it. For as long as this folder was written but
never read back, the only way to use one was to stop the app, copy files by
hand, and know to bring `case.db-wal` and `case.db-shm` along — a backup the
person who needs it cannot use, which is the same as no backup. `list_copies`,
`validate` and `restore` are the other half, and `routers/maintenance.py` puts
them on the dashboard.
"""

import logging
import re
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..config import BACKUP_DIR, DB_PATH

logger = logging.getLogger(__name__)

BACKUP_EVERY = timedelta(hours=24)
BACKUP_KEEP = 14
PRE_UPGRADE_PREFIX = "case-pre-"
IMPORTED_PREFIX = "case-imported-"

# Copies the daily rotation must never reach for. Both are the only image of
# something that exists nowhere else — the schema an upgrade left behind, and a
# database the user carried here from another machine — and both look ancient
# beside the daily copies, which is precisely what rotation prunes first.
_OUTSIDE_ROTATION = (PRE_UPGRADE_PREFIX, IMPORTED_PREFIX)

# Every SQLite file starts with these bytes. Cheap and decisive: a JPEG, a
# settings.json or half a download is rejected before anything opens it.
SQLITE_HEADER = b"SQLite format 3\x00"

# Tables an uploaded file must carry to be one of ours. Not the whole schema —
# an older release's database is exactly what someone restores, and it will be
# missing whatever has been added since (init_db migrates it afterwards). These
# three have existed since the first release and no other application has them.
REQUIRED_TABLES = ("properties", "listings", "search_profiles")


class RestoreError(Exception):
    """A copy could not be used, and nothing live was touched finding out."""


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


def _free_name(backup_dir: Path) -> Path:
    """A daily-copy filename nothing is using yet.

    The name carries the wall clock to the second, which was fine while copies
    were only ever taken once a day. Forced copies are not: one is taken before
    a factory reset and before a restore, so two can easily land inside the same
    second — and the second one then silently overwrote the first. In the
    restore path that was destructive rather than merely wasteful, because the
    copy of the current database is taken *while* an equally fresh copy is being
    restored from: same second, same name, and the file being restored was
    replaced by the state it was supposed to replace.
    """
    stem = f"case-{datetime.now():%Y%m%d-%H%M%S}"
    target = backup_dir / f"{stem}.db"
    attempt = 2
    while target.exists():
        target = backup_dir / f"{stem}-{attempt}.db"
        attempt += 1
    return target


def _daily_copies(backup_dir: Path) -> list[Path]:
    """The rotating daily copies, oldest first.

    Pre-upgrade snapshots and imported databases live in the same folder and
    share the `case-` prefix, but they are deliberately outside the rotation and
    are filtered out here so they neither satisfy the freshness gate nor count
    towards BACKUP_KEEP. A daily copy is one of fourteen; the other two are the
    only image of the schema the user is leaving and of a database they carried
    here by hand, and both sort as the oldest files in the folder — counting
    them would make them the first thing pruned, which is exactly backwards.
    """
    return sorted(
        (p for p in backup_dir.glob("case-*.db") if not p.name.startswith(_OUTSIDE_ROTATION)),
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
        target = _free_name(backup_dir)
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


def _read_only(path: Path) -> sqlite3.Connection:
    """Opens a copy without being able to change it.

    `sqlite3.connect(path)` would create the file if it were missing and may
    write to it (a hot journal is rolled back on open). Everything here only
    ever *inspects* a copy, and the URI form is the one way to say so. Built
    through `as_uri()` rather than by string-joining, so a folder containing a
    `?` or a `#` does not silently become part of the query string.
    """
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def _revision_of(path: Path) -> str | None:
    """The Alembic revision a copy holds, or None if it records none.

    Shown beside each copy in the UI, because "which schema is this?" is the
    question that decides whether restoring it is a step back in time or a step
    into a database this build has never seen. Never raises: a copy too damaged
    to answer still has to appear in the list — it is precisely the one the user
    needs to be told about rather than shown nothing at all.
    """
    try:
        with closing(_read_only(path)) as conn:
            row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None


def describe(path: Path) -> dict:
    """One copy, as the dashboard lists it: when it was taken, how big it is,
    and which schema it holds."""
    stat = path.stat()
    if path.name.startswith(PRE_UPGRADE_PREFIX):
        kind = "pre-upgrade"
    elif path.name.startswith(IMPORTED_PREFIX):
        kind = "imported"
    else:
        kind = "daily"
    return {
        "name": path.name,
        "kind": kind,
        "size_bytes": stat.st_size,
        "taken_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
        "revision": _revision_of(path),
    }


def list_copies(backup_dir: Path = BACKUP_DIR) -> list[dict]:
    """Every copy in the folder, newest first. A missing folder is an empty
    list, not an error: it is what a fresh install has."""
    if not backup_dir.is_dir():
        return []
    return [
        describe(p)
        for p in sorted(backup_dir.glob("case-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    ]


def find(name: str, backup_dir: Path = BACKUP_DIR) -> Path:
    """The copy called `name`, looked up by listing the folder rather than by
    joining the name onto it.

    The name arrives from a browser, and it names a file that is about to be
    downloaded or written over the live database. Joined, `../../settings.json`
    would be a perfectly good path; matched against what the folder actually
    contains, it is simply not there.
    """
    if backup_dir.is_dir():
        for path in backup_dir.glob("case-*.db"):
            if path.name == name:
                return path
    raise RestoreError(f"There is no backup called {name}.")


def validate(path: Path) -> None:
    """Prove a file is a SQLite database carrying this application's schema.

    Every caller runs this **before** anything live is touched, so a file that
    is not what it claims to be costs the user nothing: the running database is
    still there, unchanged, and the error says which of the three things went
    wrong. The alternative — finding out halfway through the copy — is the one
    failure mode a restore feature can have that is worse than not having one.
    """
    try:
        with path.open("rb") as fh:
            header = fh.read(len(SQLITE_HEADER))
    except OSError as e:
        raise RestoreError(f"That file could not be read: {e}") from e
    if header != SQLITE_HEADER:
        raise RestoreError("That file is not a SQLite database.")
    try:
        with closing(_read_only(path)) as conn:
            if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RestoreError("That database file is damaged and cannot be restored.")
            tables = {
                row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
    except sqlite3.DatabaseError as e:
        raise RestoreError(f"That database could not be opened: {e}") from e
    missing = [t for t in REQUIRED_TABLES if t not in tables]
    if missing:
        raise RestoreError(
            "That database is not one of this app's: it has no " + ", ".join(missing) + " table."
        )


def accept_import(staged: Path, backup_dir: Path = BACKUP_DIR) -> Path:
    """File a database the user uploaded alongside the copies this app took.

    It is validated first and deleted if it fails, so an upload can never leave
    an unusable file sitting in the folder waiting to be restored by mistake.
    Landing it here rather than over the live database is what keeps "bring one
    in" separate from "restore this one": the upload is safe, the restore is the
    destructive step, and the user still has to ask for it.
    """
    try:
        validate(staged)
    except RestoreError:
        staged.unlink(missing_ok=True)
        raise
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{IMPORTED_PREFIX}{datetime.now():%Y%m%d-%H%M%S}.db"
    staged.replace(target)
    logger.info("imported a database from another install as %s", target.name)
    return target


def restore(
    source: Path, db_path: Path = DB_PATH, backup_dir: Path = BACKUP_DIR
) -> tuple[Path, Path | None]:
    """Replace the live database with a copy, and return (source, safety copy).

    The order is the whole of it:

    1. **Validate first.** A file that is not one of ours must cost nothing —
       see `validate`.
    2. **Copy the current database aside, forced**, exactly as `factory_reset`
       does. Restoring the wrong file is an ordinary mistake and there has to be
       a way back from it. A snapshot that cannot be written stops the restore:
       the promise is worth more than the convenience.
    3. **Dispose the pool, then copy through the backup API.** The app holds
       pooled connections and, under WAL, the newest commits live in
       `case.db-wal` until a checkpoint — dropping the file over the top would
       leave that WAL shadowing what was just restored. `_copy` writes through a
       connection of its own instead, so the replacement is journalled like any
       other write and the stale frames are superseded rather than replayed.
    4. **Re-initialise.** The copy may hold an older schema than this build, and
       `init_db` is the same path a startup takes: create_all, additive columns,
       then Alembic — including its own pre-upgrade snapshot if it migrates.

    Called with the *live* database's path, which is `database.engine_db_path()`
    and not necessarily `config.DB_PATH`.
    """
    validate(source)

    safety = maybe_backup(db_path, backup_dir, force=True)
    if safety is None and db_path.exists():
        raise RestoreError(
            "The current database could not be copied aside, so the restore was "
            "NOT performed. Check disk space and permissions for the backups folder."
        )

    from .. import database

    database.engine.dispose()
    _copy(source, db_path)
    database.init_db()
    logger.warning(
        "database restored from %s; the state it replaced is in %s",
        source.name,
        safety.name if safety else "no copy (there was no database yet)",
    )
    return source, safety
