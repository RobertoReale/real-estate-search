"""SQLAlchemy connection to local SQLite database (case.db)."""
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger(__name__)

from .config import DB_PATH

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"
ALEMBIC_DIR = Path(__file__).resolve().parent.parent / "alembic"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


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

    There is no Alembic in this project: create_all only creates *missing
    tables*, so adding a column to a model would silently break every query
    against an existing case.db. Deleting the DB is not acceptable either —
    price history would be lost. Additive ALTER TABLE covers the only schema
    change made so far (new nullable/defaulted columns); anything more
    invasive is the trigger for finally introducing Alembic.

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
                ddl = f'ALTER TABLE {table.name} ADD COLUMN {column.name} ' \
                      f'{column.type.compile(engine.dialect)}'
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
                        value = value.astimezone(timezone.utc).replace(
                            tzinfo=None).isoformat(sep=" ")
                    conn.execute(
                        text(f"UPDATE {table.name} SET {column.name} = :v "
                             f"WHERE {column.name} IS NULL"),
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
    """
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE properties SET source = 'email' "
            "WHERE source = 'scan' AND id IN ("
            "  SELECT property_id FROM imported_listings "
            "  WHERE status = 'accepted' AND property_id IS NOT NULL"
            ")"
        ))


def _run_migrations():
    """Apply any authored Alembic migrations, and adopt pre-Alembic databases.

    Coexists with create_all + additive migrations on purpose (see the module
    docstring / CLAUDE.md invariant on migrations): those two keep the schema
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
    """
    try:
        from alembic import command
        from alembic.config import Config
    except ImportError:
        logger.warning(
            "alembic not installed: skipping migrations "
            "(schema still maintained by create_all + additive ALTER)"
        )
        return

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
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
                command.stamp(cfg, "0001_baseline")
            command.upgrade(cfg, "head")
    except Exception:
        logger.error("Alembic migration failed", exc_info=True)


def init_db():
    from . import models  # noqa: F401 - registers models on metadata
    Base.metadata.create_all(bind=engine)
    added = _apply_additive_migrations()
    if "properties.source" in added:
        _backfill_property_source()
    _run_migrations()
    with SessionLocal() as db:
        from .services.search_validator import deduplicate_search_profiles
        deduplicate_search_profiles(db)

