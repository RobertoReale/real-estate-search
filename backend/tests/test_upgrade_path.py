"""The upgrade, proved on a database an older release actually wrote.

`test_migrations.py` proves the migration *harness* behaves: a pre-Alembic
database is adopted rather than rebuilt, a pending migration is snapshotted
before it runs, a second startup is a no-op. What it never does is open a
database from an older release and count what is still in it afterwards — every
database in that file was built by the code under test, in the test, seconds
earlier, and so it can only ever agree with itself.

This file starts from `fixtures/legacy_v1.db`, which is the schema release 1.0.0
shipped, carrying the demo corpus plus the things only a user produces: notes,
favourites, tags, a property marked sold. A copy of it is put through `init_db()`
exactly as a startup would, and then every row is counted and compared, column by
column, against what was there before. It is the test behind `README.md`'s claim
that updating keeps what you have collected, and that claim is worded to be worth
exactly what this proves: an older release's database, opened by this code, still
holds every row it held. Not that any migration written in future is safe — that
is what the pre-upgrade copy is for.

The fixture is synthetic and is rebuilt by `fixtures/build_legacy_v1.py`, which
documents what is in it. No address, agency, portal id or URL in it is anyone's.
"""

import shutil
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import inspect, select, text

from app import database
from app.models import Property, SearchProfile

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "legacy_v1.db"

# What release 1.0.0 recorded in `alembic_version`. A fact about that release,
# so it is written down here rather than read from the script directory: the day
# the head moves, this must not move with it.
LEGACY_REVISION = "0002_drop_imports"


@pytest.fixture
def legacy_db(tmp_path, monkeypatch):
    """A private copy of the fixture, with `database.engine` pointed at it.

    Copied because `init_db()` writes: a test running against the checked-in file
    would upgrade the fixture in place, and every run after the first would start
    from an already-migrated database and prove nothing at all.
    """
    db_file = tmp_path / "data" / "case.db"
    db_file.parent.mkdir()
    shutil.copy(FIXTURE, db_file)
    engine = database.make_engine(f"sqlite:///{db_file}")
    monkeypatch.setattr(database, "engine", engine)
    yield engine
    engine.dispose()


def _head() -> str:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(database.ALEMBIC_INI))
    cfg.set_main_option("script_location", str(database.ALEMBIC_DIR))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    assert head is not None, "the migration directory has no head"
    return head


def _tables(engine) -> list[str]:
    return [t for t in inspect(engine).get_table_names() if t != "alembic_version"]


def _layout(engine) -> dict[str, list[str]]:
    """Every table, with the columns it has *right now*.

    Taken before the upgrade and reused after it, so the comparison reads the old
    columns out of the new database: a column the upgrade added cannot pad out a
    row whose old values it changed.
    """
    inspector = inspect(engine)
    return {table: [c["name"] for c in inspector.get_columns(table)] for table in _tables(engine)}


def _census(engine, layout: dict[str, list[str]]) -> dict[str, list[tuple]]:
    """Every row of every table, sorted, so the comparison does not depend on the
    order SQLite happens to return."""
    census: dict[str, list[tuple]] = {}
    with engine.connect() as conn:
        for table, columns in layout.items():
            names = ", ".join(f'"{c}"' for c in columns)
            rows = conn.execute(text(f"SELECT {names} FROM {table}")).all()
            # keyed on repr: a row mixing None with a string is not orderable,
            # and the key only has to be stable, not meaningful
            census[table] = sorted((tuple(row) for row in rows), key=repr)
    return census


def _scalar(engine, sql: str):
    with engine.connect() as conn:
        return conn.execute(text(sql)).scalar()


def test_the_fixture_is_still_the_database_release_1_wrote(legacy_db):
    """The guard the rest of this file rests on.

    Every assertion below is vacuous against a fixture that has already been
    upgraded — the data would survive because nothing would happen to it. So:
    the recorded revision is 1.0.0's, and the current models genuinely describe
    columns this database does not have. The second half is the one that keeps
    holding as the schema moves on, since the fixture never will.
    """
    assert _scalar(legacy_db, "SELECT version_num FROM alembic_version") == LEGACY_REVISION

    on_disk = _layout(legacy_db)
    behind = {
        f"{table.name}.{column.name}"
        for table in database.Base.metadata.sorted_tables
        for column in table.columns
        if column.name not in on_disk.get(table.name, [])
    }
    assert behind, "the fixture already has every column the current models describe"
    assert _scalar(legacy_db, "SELECT count(*) FROM properties") > 0


def test_the_upgrade_loses_no_row_and_changes_no_value(legacy_db):
    """The whole promise, in one comparison.

    Not a count: counts stay right while an ALTER quietly rewrites a column, and
    a rebuilt table is exactly how a value goes missing without anything failing.
    Every row is read through the columns release 1.0.0 wrote it with, before and
    after, and the two have to be the same set.
    """
    layout = _layout(legacy_db)
    before = _census(legacy_db, layout)

    database.init_db()

    after = _census(legacy_db, layout)
    assert {t: len(rows) for t, rows in after.items()} == {
        t: len(rows) for t, rows in before.items()
    }
    assert after == before


def test_the_schema_reaches_the_current_models(legacy_db):
    """Surviving is half of it: the upgraded database also has to be one the
    current code can serve, or the next query is the failure instead."""
    database.init_db()

    assert _scalar(legacy_db, "SELECT version_num FROM alembic_version") == _head()

    on_disk = _layout(legacy_db)
    missing = [
        f"{table.name}.{column.name}"
        for table in database.Base.metadata.sorted_tables
        for column in table.columns
        if column.name not in on_disk.get(table.name, [])
    ]
    assert not missing, f"the upgrade left the schema short of the models: {missing}"


def test_the_user_s_own_work_is_all_still_there(legacy_db):
    """The half of the database no scan can rebuild.

    A property found again by tomorrow's scan comes back on its own; the note
    written about it does not, nor the tag, nor the fact that it was marked sold
    six months ago. Read before the upgrade with SQL (the models cannot open the
    old schema) and after it through the models themselves, which is how the
    application will read it.
    """
    with legacy_db.connect() as conn:
        curated = {
            row[0]: (row[1], bool(row[2]), row[3])
            for row in conn.execute(text("SELECT id, status, is_favorite, notes FROM properties"))
        }
        tagged: dict[int, list[str]] = {}
        for property_id, name in conn.execute(
            text(
                "SELECT pt.property_id, t.name FROM property_tags pt JOIN tags t ON t.id = pt.tag_id"
            )
        ):
            tagged.setdefault(property_id, []).append(name)
        history: dict[int, list[tuple]] = {}
        for property_id, old_price, new_price, changed_at in conn.execute(
            text(
                "SELECT property_id, old_price, new_price, changed_at FROM price_history ORDER BY id"
            )
        ):
            history.setdefault(property_id, []).append((old_price, new_price, changed_at))
        searches = sorted(
            conn.execute(
                text(
                    "SELECT name, portal, search_url, is_active, consecutive_failures FROM search_profiles"
                )
            ).all()
        )

    # the fixture has to actually contain each of these, or the comparisons below
    # would all hold over nothing
    assert {"hidden", "sold"} <= {status for status, _, _ in curated.values()}
    assert any(favorite for _, favorite, _ in curated.values())
    assert [notes for _, _, notes in curated.values() if notes]
    assert tagged and history and searches

    database.init_db()

    with database.SessionLocal() as db:
        properties = db.scalars(select(Property)).all()
        assert {p.id: (p.status, p.is_favorite, p.notes) for p in properties} == curated
        assert {p.id: sorted(t.name for t in p.tags) for p in properties if p.tags} == {
            property_id: sorted(names) for property_id, names in tagged.items()
        }
        assert {
            p.id: [(h.old_price, h.new_price, h.changed_at) for h in p.price_history]
            for p in properties
            if p.price_history
        } == {
            # SQL hands back the stored text, the models a datetime: parse rather
            # than compare the two spellings of the same instant
            property_id: [
                (old, new, datetime.fromisoformat(changed)) for old, new, changed in changes
            ]
            for property_id, changes in history.items()
        }
        assert (
            sorted(
                (p.name, p.portal, p.search_url, p.is_active, p.consecutive_failures)
                for p in db.scalars(select(SearchProfile))
            )
            == searches
        )
        # a sold property keeps the date it was sold on, which is what market
        # velocity measures its window against
        sold = [p for p in properties if p.status == "sold"]
        assert sold and all(p.sold_at is not None for p in sold)


def test_the_upgrade_is_idempotent_on_a_migrated_database(legacy_db):
    """The second startup after an update, and every one after that. The first
    run is the migration; the rest must be a no-op over the same data rather than
    a second pass at it."""
    database.init_db()
    layout = _layout(legacy_db)
    once = _census(legacy_db, layout)

    database.init_db()

    assert _census(legacy_db, layout) == once
