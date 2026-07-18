"""Alembic adoption tests.

Alembic was introduced on top of the long-standing create_all + additive-ALTER
mechanism, not as a replacement. The risk the roadmap flagged was doing it
"without breaking existing case.db files": an existing DB has every table but no
`alembic_version`, and a naive `upgrade` would re-run the baseline's create_table
and blow up. These tests pin the adoption path (stamp-then-upgrade) and its
idempotence so a future migration author can trust the harness.
"""

from sqlalchemy import create_engine, inspect, text

from app import database


def _version(engine) -> str | None:
    insp = inspect(engine)
    if not insp.has_table("alembic_version"):
        return None
    with engine.connect() as conn:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()


def test_fresh_db_is_stamped_at_baseline(tmp_path, monkeypatch):
    """A brand-new DB is fully built by create_all; Alembic must record it at the
    baseline (so future upgrades apply only post-baseline migrations) rather than
    try to create the tables a second time."""
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    monkeypatch.setattr(database, "engine", engine)
    database.init_db()

    assert _version(engine) == "0001_baseline"
    tables = set(inspect(engine).get_table_names())
    assert {
        "properties",
        "listings",
        "price_history",
        "search_profiles",
        "imported_listings",
    } <= tables


def test_pre_alembic_db_is_adopted_not_rebuilt(tmp_path, monkeypatch):
    """An existing case.db predates Alembic: it has the tables but no
    alembic_version. Running upgrade blind would re-run the baseline create_table
    and fail — the whole point of stamping first. The additive migration must
    still fill in the columns this old partial table is missing."""
    db_file = tmp_path / "old.db"
    engine = create_engine(f"sqlite:///{db_file}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE properties (id INTEGER PRIMARY KEY, "
                "fingerprint VARCHAR, title VARCHAR)"
            )
        )
    monkeypatch.setattr(database, "engine", engine)

    database.init_db()  # must not raise

    assert _version(engine) == "0001_baseline"
    cols = {c["name"] for c in inspect(engine).get_columns("properties")}
    assert {"contract", "is_favorite", "notes"} <= cols


def test_migrations_are_idempotent(tmp_path, monkeypatch):
    """Every startup calls init_db; a second run must be a no-op, not a crash."""
    engine = create_engine(f"sqlite:///{tmp_path / 'twice.db'}")
    monkeypatch.setattr(database, "engine", engine)
    database.init_db()
    database.init_db()
    assert _version(engine) == "0001_baseline"


def test_script_directory_has_a_single_head():
    """Two heads mean someone branched the migration history without merging —
    `upgrade head` then becomes ambiguous. Catch it here, offline, instead of at
    a user's startup."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(database.ALEMBIC_INI))
    cfg.set_main_option("script_location", str(database.ALEMBIC_DIR))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert heads == ["0001_baseline"], f"expected one head, got {heads}"


def test_missing_alembic_degrades_to_additive(tmp_path, monkeypatch):
    """Alembic is a real dependency, but the app must still boot if the import
    fails on a stripped-down deploy: create_all + additive already guarantee a
    working schema, so a missing harness is a warning, not a fatal error."""
    import builtins

    real_import = builtins.__import__

    def _no_alembic(name, *args, **kwargs):
        if name == "alembic" or name.startswith("alembic."):
            raise ImportError("simulated missing alembic")
        return real_import(name, *args, **kwargs)

    engine = create_engine(f"sqlite:///{tmp_path / 'noalembic.db'}")
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(builtins, "__import__", _no_alembic)

    database.init_db()  # must not raise

    # schema is intact even though Alembic never ran
    assert inspect(engine).has_table("properties")
    assert _version(engine) is None  # no alembic_version table created
