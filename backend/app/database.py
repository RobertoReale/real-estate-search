"""SQLAlchemy connection to local SQLite database (case.db)."""
import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger(__name__)

from .config import DB_PATH

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


def _apply_additive_migrations():
    """Adds columns that exist in the models but not in the on-disk DB.

    There is no Alembic in this project: create_all only creates *missing
    tables*, so adding a column to a model would silently break every query
    against an existing case.db. Deleting the DB is not acceptable either —
    price history would be lost. Additive ALTER TABLE covers the only schema
    change made so far (new nullable/defaulted columns); anything more
    invasive is the trigger for finally introducing Alembic.
    """
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
                    ddl += f" DEFAULT '{default}'"
                conn.execute(text(ddl))
                logger.info("DB migration: added %s.%s", table.name, column.name)


def init_db():
    from . import models  # noqa: F401 - registers models on metadata
    Base.metadata.create_all(bind=engine)
    _apply_additive_migrations()
