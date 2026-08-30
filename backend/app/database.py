"""SQLAlchemy connection to local SQLite database (case.db)."""

import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import BASE_DIR, DB_PATH

logger = logging.getLogger(__name__)

# Migration scripts are code, so they follow BASE_DIR (the bundle when packaged,
# `backend/` from a checkout) rather than the data directory the database lives
# in. Packaging must copy both of these in, or every install would run with an
# un-upgraded schema and the fail-open Alembic step would say so only in the log.
ALEMBIC_INI = BASE_DIR / "alembic.ini"
ALEMBIC_DIR = BASE_DIR / "alembic"

# The revision every pre-Alembic database is adopted at (see `_run_migrations`).
# Named once: `_snapshot_before_upgrade` has to agree with the stamp about which
# revision such a database is leaving, or it would name the snapshot after one
# thing and the migration would run from another.
BASELINE_REVISION = "0001_baseline"


def _sqlite_pragmas(dbapi_conn, _record):
    """Per-connection PRAGMAs, applied on every new pooled connection.

    They are not persisted in the connection string and `journal_mode` is the
    only one of the three that sticks to the file, so this has to run per
    connection, not once at startup.

    The problem they solve is concurrency. `check_same_thread=False` lets any
    thread use a connection, and six background modules (scanner, geocoder,
    availability check, harvester, scheduler) write alongside FastAPI's
    threadpool — under the default rollback journal a writer locks out readers
    entirely, so the losers got an immediate `database is locked`.

    - WAL: readers no longer block on the single writer, which is the shape of
      this workload (one scan writing, the dashboard polling).
    - busy_timeout: the second writer *waits* up to 5s for the lock instead of
      failing instantly. WAL still serialises writers; this is what makes that
      serialisation invisible rather than an error.
    - synchronous=NORMAL: safe under WAL (a crash can lose the last commits but
      cannot corrupt the file) and much faster than FULL's fsync per commit.
    """
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


def make_engine(url: str):
    """The one place an engine for this app is built.

    Shared with the test fixtures on purpose: an engine created by hand would
    silently lack the PRAGMAs above, so a concurrency regression would pass its
    test and only appear in production.
    """
    eng = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(eng, "connect", _sqlite_pragmas)
    return eng


engine = make_engine(f"sqlite:///{DB_PATH}")

# Deliberately unbound: the bind is chosen per session, in SessionLocal below.
_session_factory = sessionmaker(autoflush=False, expire_on_commit=False)


def SessionLocal() -> Session:
    """Opens a session on whatever `engine` is *now*, not at import time.

    `sessionmaker(bind=engine)` at module level captured the engine the instant
    this file was first imported, and that single line made the database
    impossible to redirect. Anything that swapped `database.engine` — the test
    fixtures, most visibly — kept getting sessions on the real `case.db`, so
    `init_db()`'s closing `deduplicate_search_profiles(db)` ran over the
    developer's own searches. Worse, `scanner` and `scheduler` do
    `from ..database import SessionLocal`, which copies the bound factory into
    their namespace: patching `database.SessionLocal` could not reach them at
    all, and each had to be patched separately.

    Keeping the name a callable that resolves the module global on every call
    fixes both. The from-imports hold this function rather than a frozen bind,
    so redirecting the engine redirects every caller at once, and the engine
    stays the single symbol that decides which database the app talks to.
    """
    return _session_factory(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _apply_additive_migrations() -> set[str]:
    """Adds columns that exist in the models but not in the on-disk DB.

    This runs *before* Alembic (see `_run_migrations` below), and the two divide
    the work rather than competing. `create_all` only creates missing **tables**,
    so adding a column to a model would otherwise silently break every query
    against an existing case.db — and deleting the database is not an option,
    since months of price history live there and no re-scan can rebuild them.

    Additive ALTER TABLE covers the common case completely: a new nullable or
    defaulted column needs no migration and never will, which keeps the ordinary
    "add a field to a model" change a one-line edit. Alembic's job starts where
    this cannot follow — a rename, a drop, a type change — so by the time it
    runs, every current table and column already exists and it only has to apply
    what was authored deliberately.

    Returns the set of "table.column" names newly created, so callers can run
    a one-time backfill exactly when a column first appears (never again).
    """
    added: set[str] = set()
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in inspector.get_table_names():
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                ddl = (
                    f"ALTER TABLE {table.name} ADD COLUMN {column.name} "
                    f"{column.type.compile(engine.dialect)}"
                )
                default = getattr(column.default, "arg", None)
                if isinstance(default, bool):
                    ddl += f" DEFAULT {int(default)}"
                elif isinstance(default, (int, float)):
                    ddl += f" DEFAULT {default}"
                elif isinstance(default, str):
                    # doubled quotes, not raw interpolation: a default
                    # containing an apostrophe must not break the DDL
                    escaped = default.replace("'", "''")
                    ddl += f" DEFAULT '{escaped}'"
                conn.execute(text(ddl))
                if callable(default):
                    # callable defaults (e.g. utcnow) cannot become a DDL
                    # literal, so existing rows just got NULL — which a
                    # non-Optional model field / Pydantic schema would then
                    # turn into 500s on every old row. Backfill once with a
                    # value computed now, stored the way the ORM stores it
                    # (naive UTC ISO string: SQLite drops tzinfo anyway).
                    try:
                        # SQLAlchemy wraps callables to take an execution
                        # context; a plain zero-arg callable is also legal
                        value = default(None)
                    except TypeError:
                        value = default()
                    if isinstance(value, datetime):
                        value = value.astimezone(UTC).replace(tzinfo=None).isoformat(sep=" ")
                    conn.execute(
                        text(
                            f"UPDATE {table.name} SET {column.name} = :v "
                            f"WHERE {column.name} IS NULL"
                        ),
                        {"v": value},
                    )
                added.add(f"{table.name}.{column.name}")
                logger.info("DB migration: added %s.%s", table.name, column.name)
    return added


def _backfill_property_source():
    """One-time backfill for the new `properties.source` column.

    The additive ALTER stamps every existing row with the default ("scan"),
    but a dashboard built before this column had plenty of email-imported
    properties — the very set the user needs to prune. `imported_listings`
    remembers which ones (status='accepted', property_id set), so recover the
    origin from there. Run only the first time the column appears (see
    init_db), otherwise it would fight the email->scan upgrade in
    deduplicator.upsert_listing on every startup.

    The inbox import is gone and its table with it (migration 0002), so this
    only still has a source to read on a database old enough to predate the
    `source` column: there the additive step runs before Alembic drops the
    table, and the origins are recovered in that one window. Past it the table
    is absent and there is nothing to recover — not a failure, so skip rather
    than raise, or an upgrade would die on a missing table.
    """
    with engine.begin() as conn:
        if not inspect(conn).has_table("imported_listings"):
            return
        conn.execute(
            text(
                "UPDATE properties SET source = 'email' "
                "WHERE source = 'scan' AND id IN ("
                "  SELECT property_id FROM imported_listings "
                "  WHERE status = 'accepted' AND property_id IS NOT NULL"
                ")"
            )
        )


def _engine_db_path() -> Path | None:
    """The file the current engine writes to, or None if it is not one.

    Not `config.DB_PATH`: `engine` is the single symbol that decides which
    database the app talks to (see `SessionLocal`), and the test fixtures and
    the demo seeder both redirect it. A snapshot resolved against DB_PATH while
    the engine pointed elsewhere would copy the wrong database, into the wrong
    folder, and call it a backup of this one.
    """
    name = engine.url.database
    if not name or name == ":memory:":
        return None
    return Path(name)


def _current_revision() -> str | None:
    """The Alembic revision recorded in the database, or None if it has none."""
    if not inspect(engine).has_table("alembic_version"):
        return None
    with engine.connect() as conn:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()


def _snapshot_before_upgrade(script_dir) -> None:
    """Copy the database aside when this startup is about to change its schema.

    `services/backup.py` names "a botched migration" as the thing it exists to
    protect against, but its copy is scheduled from `scheduler.start_scheduler`,
    which runs *after* `init_db()`: on the one startup where that copy mattered
    it was taken after the migration it was insuring against. Taking it here
    puts it back on the right side of the event.

    Only when the recorded revision and the script head actually differ, so an
    ordinary startup — every startup, once the schema has settled — writes
    nothing at all.

    Fail-open, like everything else on this path: working out *whether* to
    snapshot reads the database, and a failure there must not stop startup
    either. Logged at error level rather than warning, because the user is
    about to migrate without a net and that is worth seeing.
    """
    from .services.backup import snapshot_before_migration

    try:
        head = script_dir.get_current_head()
        # A pre-Alembic database has no alembic_version row, and `_run_migrations`
        # is about to stamp it at the baseline — so the baseline is the revision
        # it is leaving, and the one to name the copy after.
        current = _current_revision() or BASELINE_REVISION
        if head is None or current == head:
            return
        db_path = _engine_db_path()
        if db_path is None:
            return
    except Exception:
        logger.error("could not read the schema revision before migrating", exc_info=True)
        return

    # beside the database it protects: that is config.BACKUP_DIR in production,
    # and it follows the engine anywhere the engine has been redirected
    snapshot_before_migration(current, db_path, db_path.parent / "backups")


def _run_migrations(protect_data: bool = False):
    """Apply any authored Alembic migrations, and adopt pre-Alembic databases.

    Coexists with create_all + additive migrations on purpose (see the module
    docstring / docs/architecture.md on migrations): those two keep the schema
    working for every *additive* change and always run first, so by the time we
    get here every current table already exists. Alembic's job starts at the
    first change they cannot express — a rename, a drop, a type change.

    Adoption is the delicate part. An existing case.db has the tables but no
    `alembic_version`; running `upgrade` blind would re-run the baseline's
    create_table and fail. So we **stamp** such a DB at the baseline first
    (record "you already have this schema") and only then upgrade, which applies
    solely the migrations authored *after* the baseline — nothing today, the
    real ones tomorrow.

    Fail-open like the rest of the app: the schema is already guaranteed by the
    steps above, so a migration harness problem is logged, not fatal. A genuine
    post-baseline migration failure surfaces loudly (error + traceback) without
    taking startup down with it.

    `protect_data` says the database existed before this startup, and is what
    makes the pre-upgrade snapshot conditional — see `init_db`.
    """
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        from alembic import command
    except ImportError:
        logger.warning(
            "alembic not installed: skipping migrations "
            "(schema still maintained by create_all + additive ALTER)"
        )
        return

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    if protect_data:
        _snapshot_before_upgrade(ScriptDirectory.from_config(cfg))
    inspector = inspect(engine)
    has_version = inspector.has_table("alembic_version")
    has_schema = inspector.has_table("properties")
    try:
        # A plain connect(), not begin(): Alembic opens and commits its own
        # transaction per command via context.begin_transaction().
        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            if has_schema and not has_version:
                # Pre-Alembic DB (or a fresh one just built by create_all):
                # mark it at the baseline instead of trying to recreate tables.
                command.stamp(cfg, BASELINE_REVISION)
            command.upgrade(cfg, "head")
    except Exception:
        logger.error("Alembic migration failed", exc_info=True)


def init_db():
    from . import models  # noqa: F401 - registers models on metadata

    # Read before create_all, which is about to create the file: the absence of
    # the database is the only reliable sign of a fresh install, and a fresh
    # install has nothing to protect. Without this every first run would leave
    # behind a pre-upgrade snapshot of an empty database — and one that is
    # exempt from the rotation, so it would never be cleaned up either.
    db_path = _engine_db_path()
    had_database = db_path is not None and db_path.exists()

    Base.metadata.create_all(bind=engine)
    added = _apply_additive_migrations()
    if "properties.source" in added:
        _backfill_property_source()
    _run_migrations(protect_data=had_database)
    with SessionLocal() as db:
        from .services.search_validator import deduplicate_search_profiles

        deduplicate_search_profiles(db)
