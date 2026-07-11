"""Alembic migration environment.

Two entry points share this file:
  * the `alembic` CLI, which derives the database URL from app.config.DB_PATH so
    it always hits the same file the app does;
  * database._run_migrations, which hands us a live connection via
    config.attributes["connection"] so migrations run on the app's own engine
    (respecting a monkeypatched engine in tests, and never opening a second
    handle to the same SQLite file).

`render_as_batch=True` is non-negotiable on SQLite: it lacks real ALTER TABLE,
so Alembic emits the copy-table-and-swap dance for any non-additive change —
exactly the operations that motivated adopting Alembic in the first place.
"""
from logging.config import fileConfig

from alembic import context

from app.config import DB_PATH
from app.database import Base
from app import models  # noqa: F401 - registers the tables on Base.metadata

config = context.config

if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        # A missing/oddly-shaped logging section must not stop a migration.
        pass

target_metadata = Base.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or f"sqlite:///{DB_PATH}"


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection", None)
    if connection is not None:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    from sqlalchemy import create_engine, pool

    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
