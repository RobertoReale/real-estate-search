"""Alembic adoption tests.

Alembic was introduced on top of the long-standing create_all + additive-ALTER
mechanism, not as a replacement. The risk the roadmap flagged was doing it
"without breaking existing case.db files": an existing DB has every table but no
`alembic_version`, and a naive `upgrade` would re-run the baseline's create_table
and blow up. These tests pin the adoption path (stamp-then-upgrade) and its
idempotence so a future migration author can trust the harness.
"""

import io
import logging
from datetime import datetime, timedelta

from sqlalchemy import create_engine, inspect, text

from app import database
from app.services import backup


def _head() -> str:
    """The revision `upgrade head` lands on. Read from the script directory
    rather than hardcoded, so authoring a migration does not mean editing the
    expected value into four separate tests."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(database.ALEMBIC_INI))
    cfg.set_main_option("script_location", str(database.ALEMBIC_DIR))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    assert head is not None, "the migration directory has no head"
    return head


def _version(engine) -> str | None:
    insp = inspect(engine)
    if not insp.has_table("alembic_version"):
        return None
    with engine.connect() as conn:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()


def _stamp(engine, revision: str) -> None:
    """Rewrite the recorded revision, so the next init_db has something to
    migrate. Cheaper and more direct than keeping an old database around."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM alembic_version"))
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:r)"), {"r": revision})


class _AdvancingClock:
    """Stands in for `datetime` inside `backup.py`, one day per round.

    `maybe_backup` names each copy after the wall clock and gates on the newest
    mtime, so twenty daily rounds inside one real second would be twenty writes
    to a single filename and the rotation under test would never run. Only the
    two members `maybe_backup` reads are provided.
    """

    offset = timedelta()

    @classmethod
    def now(cls, tz=None):
        return datetime.now(tz) + cls.offset

    @staticmethod
    def fromtimestamp(ts, tz=None):
        return datetime.fromtimestamp(ts, tz)


def test_fresh_db_is_stamped_at_baseline_then_upgraded(tmp_path, monkeypatch):
    """A brand-new DB is fully built by create_all; Alembic must record it at the
    baseline (rather than try to create the tables a second time) and then apply
    the post-baseline migrations from there, landing on the head."""
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    monkeypatch.setattr(database, "engine", engine)
    database.init_db()

    assert _version(engine) == _head()
    tables = set(inspect(engine).get_table_names())
    assert {"properties", "listings", "price_history", "search_profiles"} <= tables
    # dropped by 0002, and create_all never built it: the drop must be a no-op
    # here, not the failure that would strand the version at the baseline
    assert "imported_listings" not in tables


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

    assert _version(engine) == _head()
    cols = {c["name"] for c in inspect(engine).get_columns("properties")}
    assert {"contract", "is_favorite", "notes"} <= cols


def test_migrations_are_idempotent(tmp_path, monkeypatch):
    """Every startup calls init_db; a second run must be a no-op, not a crash."""
    engine = create_engine(f"sqlite:///{tmp_path / 'twice.db'}")
    monkeypatch.setattr(database, "engine", engine)
    database.init_db()
    database.init_db()
    assert _version(engine) == _head()


def test_script_directory_has_a_single_head():
    """Two heads mean someone branched the migration history without merging —
    `upgrade head` then becomes ambiguous. Catch it here, offline, instead of at
    a user's startup."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(database.ALEMBIC_INI))
    cfg.set_main_option("script_location", str(database.ALEMBIC_DIR))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert len(heads) == 1, f"expected one head, got {heads}"


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


def test_a_pending_migration_is_snapshotted_before_it_runs(tmp_path, monkeypatch):
    """The copy that protects against a botched migration must predate it.

    `backup.py` exists for exactly this, but its copy is scheduled by the
    scheduler, which starts after `init_db()` has already migrated — so the one
    snapshot that mattered was taken after the event. Here the database is put
    back at an older revision and started up: the copy must be on disk, named
    for the revision being left, and it must still be there twenty daily
    backups later, because a pre-upgrade copy is the last thing the rotation
    should reclaim and (being the oldest file in the folder) the first thing it
    would take.
    """
    db_file = tmp_path / "case.db"
    backups = tmp_path / "backups"
    engine = create_engine(f"sqlite:///{db_file}")
    monkeypatch.setattr(database, "engine", engine)

    database.init_db()
    assert not backups.exists(), "a fresh install has nothing to snapshot"

    _stamp(engine, "0001_baseline")
    database.init_db()

    snapshot = backups / "case-pre-0001_baseline.db"
    assert snapshot.exists(), "the migration ran without a copy taken first"
    assert _version(engine) == _head(), "the migration itself must still have run"

    monkeypatch.setattr(backup, "datetime", _AdvancingClock)
    for day in range(20):
        _AdvancingClock.offset = timedelta(days=day)
        assert backup.maybe_backup(db_file, backups) is not None

    assert snapshot.exists(), "the rotation pruned the pre-upgrade copy"
    dailies = [p for p in backups.glob("case-*.db") if p != snapshot]
    assert len(dailies) == backup.BACKUP_KEEP


def test_an_unmigrated_startup_snapshots_nothing(tmp_path, monkeypatch):
    """The snapshot is conditional on a migration actually being pending.

    Every ordinary startup runs `init_db()` against a database already at the
    head. Copying it each time would fill the backups folder with files the
    rotation is deliberately forbidden to reclaim.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'case.db'}")
    monkeypatch.setattr(database, "engine", engine)
    database.init_db()

    database.init_db()

    assert not list((tmp_path / "backups").glob("case-pre-*.db"))


def test_a_failed_snapshot_does_not_stop_the_migration(tmp_path, monkeypatch, caplog):
    """Fail-open, like every other step on this path — a copy that cannot be
    written must not keep the app from starting. But at error level, not
    warning: the migration is about to run with nothing to fall back on, and
    that is the one line the user would want to have seen afterwards."""
    db_file = tmp_path / "case.db"
    engine = create_engine(f"sqlite:///{db_file}")
    monkeypatch.setattr(database, "engine", engine)
    database.init_db()
    _stamp(engine, "0001_baseline")
    # a plain file where the backups folder wants to be: mkdir cannot succeed
    (tmp_path / "backups").write_text("not a directory")

    with caplog.at_level(logging.ERROR):
        database.init_db()  # must not raise

    assert _version(engine) == _head()
    assert any(
        record.levelno == logging.ERROR and "snapshot" in record.getMessage()
        for record in caplog.records
    ), "a missing pre-upgrade copy must be logged at error level"


def test_a_database_from_a_newer_build_is_explained_not_traced_back(tmp_path, monkeypatch, caplog):
    """The downgrade: an older program opening a database a newer one migrated.

    `upgrade head` cannot resolve a revision that is not in this build's script
    directory, so it raises and the fail-open handler prints an Alembic
    traceback — telling the user everything except the fact that mattered, which
    is that the schema on disk is ahead of the code reading it. Startup still
    has to continue (extra columns are harmless, and refusing to boot would be
    worse than the mismatch), but it says so in one line that names the revision
    and where the copy that undoes it lives.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'case.db'}")
    monkeypatch.setattr(database, "engine", engine)
    database.init_db()
    _stamp(engine, "9999_from_the_future")

    with caplog.at_level(logging.ERROR):
        database.init_db()  # must not raise

    said = [r for r in caplog.records if "9999_from_the_future" in r.getMessage()]
    assert len(said) == 1, f"expected exactly one line about the mismatch, got {len(said)}"
    assert "backups" in said[0].getMessage(), "the message must point at the copies"
    assert not any(r.exc_info for r in caplog.records), "a traceback was logged, not a message"
    assert _version(engine) == "9999_from_the_future", (
        "the recorded revision was rewritten by a build that cannot honour it"
    )
    assert not list((tmp_path / "backups").glob("case-pre-*.db")), (
        "nothing is migrating, so there is no pre-upgrade state to snapshot"
    )


def test_migrating_leaves_the_application_log_handlers_alone(tmp_path, monkeypatch):
    """Running migrations must not reconfigure the app's logging.

    `alembic/env.py` calls `fileConfig(alembic.ini)`, which REPLACES the root
    logger's handlers and level. Under the real startup order — `main.py` calls
    `basicConfig` at import, then the lifespan calls `init_db()` — that dropped
    the RotatingFileHandler writing `app.log` and reset the level from INFO to
    alembic.ini's WARNING. The file the scheduler's overnight failures were
    supposed to be diagnosed from, and that `/api/logs/tail` shows in the UI,
    then stayed empty for the life of the process.

    Only the `alembic` CLI may configure logging from the ini; when the app
    drives the migration it passes its own connection, and owns logging itself.
    """
    root = logging.getLogger()
    sentinel = logging.StreamHandler(io.StringIO())
    saved_handlers, saved_level = root.handlers[:], root.level
    root.handlers = [sentinel]
    root.setLevel(logging.INFO)
    try:
        engine = create_engine(f"sqlite:///{tmp_path / 'logging.db'}")
        monkeypatch.setattr(database, "engine", engine)

        database.init_db()

        assert root.handlers == [sentinel], "the migration replaced the app's log handlers"
        assert root.level == logging.INFO, "the migration reset the app's log level"
    finally:
        root.handlers, root.level = saved_handlers, saved_level
