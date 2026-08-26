"""Where the user's data lives, and how a packaged app finds data that predates it.

In a source checkout the code and the data share one folder, so nothing here
ever mattered. Packaging separates them: under PyInstaller the code is unpacked
into a temporary directory that is deleted on exit, and a `case.db` resolved
against it would be destroyed on every quit. Worse, it would fail *quietly* —
the app opens, works, and is simply empty, with months of price history sitting
untouched in the folder the old install used. These tests pin both halves: the
paths land somewhere durable, and an existing database is adopted rather than
ignored.
"""

import sqlite3

import pytest

from app import config


@pytest.fixture
def wal_database(tmp_path):
    """A database with a committed row still sitting in the WAL.

    Deliberately left open: closing checkpoints the WAL back into `case.db`,
    which would make a plain file copy look correct and hide the bug this
    fixture exists to expose.
    """
    source_dir = tmp_path / "old-install"
    source_dir.mkdir()
    conn = sqlite3.connect(source_dir / "case.db")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE price_history (price)")
    conn.execute("INSERT INTO price_history VALUES (420000)")
    conn.commit()
    assert (source_dir / "case.db-wal").exists(), "expected an un-checkpointed WAL"
    yield source_dir
    conn.close()


# --- where the paths resolve ---------------------------------------------


def test_a_source_checkout_keeps_its_data_in_backend(monkeypatch):
    """The developer flow must be exactly as it was: backend/case.db.

    Anything else would strand an existing checkout's database and price
    history behind a path change nobody asked for.

    `SETTINGS_PATH` is checked through the resolver rather than the module
    global, because conftest's autouse fixture repoints that global at a
    throwaway file for every test (invariant 17).
    """
    monkeypatch.delenv("APP_DATA_DIR", raising=False)
    assert config.DATA_DIR == config.BASE_DIR
    assert config.DB_PATH == config.BASE_DIR / "case.db"
    assert config._resolve_data_dir(config.BASE_DIR) == config.BASE_DIR


def test_app_data_dir_wins_over_everything(tmp_path, monkeypatch):
    """The explicit answer, and what the Docker image points at its volume."""
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "elsewhere"))
    assert config._resolve_data_dir(config.BASE_DIR) == (tmp_path / "elsewhere").resolve()


def test_frozen_resolves_to_a_per_user_folder_not_the_bundle(tmp_path, monkeypatch):
    """Frozen, the data must leave the bundle: the bundle is a temp directory.

    Not the folder beside the executable either — an app installed under
    `C:\\Program Files` cannot write there.
    """
    monkeypatch.delenv("APP_DATA_DIR", raising=False)
    monkeypatch.setattr(config, "_is_frozen", lambda: True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))

    resolved = config._resolve_data_dir(tmp_path / "bundle")

    assert resolved != tmp_path / "bundle"
    assert "RealEstateSearch" in str(resolved) or "real-estate-search" in str(resolved)


# --- adopting a database from an earlier install --------------------------


def test_an_existing_database_is_adopted_not_ignored(wal_database, tmp_path):
    """The whole point of the task: months of history must not be abandoned.

    The row under test is still in the WAL, so this also pins that the adoption
    goes through SQLite's backup API. A `shutil.copy` of `case.db` alone would
    produce a readable database that is missing the most recent scans — the
    failure would look like "some listings disappeared", not like a bad copy.
    """
    data_dir = tmp_path / "new-install"

    adopted = config.adopt_existing_data(data_dir, [wal_database])

    assert adopted == wal_database
    copy = sqlite3.connect(data_dir / "case.db")
    try:
        assert copy.execute("SELECT price FROM price_history").fetchone() == (420000,)
    finally:
        copy.close()


def test_the_settings_travel_with_the_database(wal_database, tmp_path):
    """They hold the Telegram token and the DataDome cookie.

    Left behind, the user gets a working dashboard that cannot notify and a
    scraper that has to earn its cookie from scratch.
    """
    (wal_database / "settings.json").write_text('{"telegram_chat_id": "123"}', encoding="utf-8")
    data_dir = tmp_path / "new-install"

    config.adopt_existing_data(data_dir, [wal_database])

    assert '"telegram_chat_id": "123"' in (data_dir / "settings.json").read_text(encoding="utf-8")


def test_live_data_is_never_overwritten(wal_database, tmp_path):
    """Adoption is a first-run action. Running it against a database already in
    use would replace real data with a stale copy — irreversibly, and with the
    good version gone."""
    data_dir = tmp_path / "new-install"
    data_dir.mkdir()
    conn = sqlite3.connect(data_dir / "case.db")
    conn.execute("CREATE TABLE price_history (price)")
    conn.execute("INSERT INTO price_history VALUES (999)")
    conn.commit()
    conn.close()

    assert config.adopt_existing_data(data_dir, [wal_database]) is None

    conn = sqlite3.connect(data_dir / "case.db")
    try:
        assert conn.execute("SELECT price FROM price_history").fetchone() == (999,)
    finally:
        conn.close()


def test_nothing_to_adopt_is_not_an_error(tmp_path):
    """A genuinely fresh install: start empty, quietly."""
    data_dir = tmp_path / "new-install"
    assert config.adopt_existing_data(data_dir, [tmp_path / "nowhere"]) is None
    assert not (data_dir / "case.db").exists()


def test_an_unreadable_candidate_does_not_hide_a_good_one(wal_database, tmp_path):
    """Candidates are guesses, so one of them being junk is expected.

    A folder holding something that is not a database must not end the search
    and leave the real one — later in the list — unadopted.
    """
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "case.db").write_text("this is not a database", encoding="utf-8")

    adopted = config.adopt_existing_data(tmp_path / "new-install", [broken, wal_database])

    assert adopted == wal_database


def test_the_data_directory_is_never_adopted_from_itself(wal_database):
    """A candidate list that includes the destination must not copy a database
    over itself: the backup API would be reading and writing one file."""
    assert config.adopt_existing_data(wal_database, [wal_database]) is None
