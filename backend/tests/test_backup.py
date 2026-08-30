"""Automatic case.db backup: freshness gate, rotation, fail-safety — and the
way back from a copy.

The database is the only place price history and days-on-market data exist —
no re-scan can rebuild them — yet for months it lived as a single file with no
copy anywhere. `maybe_backup` runs at startup and daily: these tests pin down
that it is idempotent within 24h (dev restarts every few minutes must not pile
up copies), that rotation caps disk usage, and that it never raises (a failed
backup must not take startup down with it).

The second half of the file is `restore`, which is the reason the first half
exists. A copy nobody can put back is not a backup, and putting one back is the
single most destructive thing this app can do to a database — so what is pinned
here is the order of operations: nothing live is touched until the file has been
proved to be one of ours, the state being replaced is copied aside first, and
the swap goes through the SQLite backup API with the pool disposed, never a file
dropped over an open database.
"""

import os
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import database
from app.models import Property
from app.services import backup
from app.services.scanner import scan_state


@pytest.fixture
def db_file(tmp_path):
    path = tmp_path / "case.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (x)")
    conn.execute("INSERT INTO t VALUES (42)")
    conn.commit()
    conn.close()
    return path


def test_backup_is_a_readable_copy(db_file, tmp_path):
    target = backup.maybe_backup(db_file, tmp_path / "backups")
    assert target is not None and target.exists()
    conn = sqlite3.connect(target)
    assert conn.execute("SELECT x FROM t").fetchone() == (42,)
    conn.close()


def test_backup_captures_transactions_still_in_the_wal(tmp_path):
    """Under WAL, the newest commits are not in case.db yet.

    The database runs in WAL (database.py's connect PRAGMAs), where a commit
    lands in `case.db-wal` and only reaches `case.db` at a checkpoint. A backup
    that copied the file alone would therefore silently lose everything since
    the last checkpoint — the most recent scan being exactly what the user would
    miss. `maybe_backup` uses sqlite3's backup API, which reads through the WAL,
    so this holds without any checkpoint being forced first.
    """
    db_path = tmp_path / "case.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (x)")
    conn.execute("INSERT INTO t VALUES (42)")
    conn.commit()
    assert (tmp_path / "case.db-wal").exists(), "expected an un-checkpointed WAL"
    try:
        target = backup.maybe_backup(db_path, tmp_path / "backups")
        assert target is not None
        copy = sqlite3.connect(target)
        try:
            assert copy.execute("SELECT x FROM t").fetchone() == (42,)
        finally:
            copy.close()
    finally:
        # closing checkpoints, so it must happen after the backup is verified
        conn.close()


def test_missing_db_is_not_an_error(tmp_path):
    """Fresh install: there is nothing to protect yet, and no folder to create."""
    assert backup.maybe_backup(tmp_path / "case.db", tmp_path / "backups") is None
    assert not (tmp_path / "backups").exists()


def test_recent_backup_suppresses_a_new_one(db_file, tmp_path):
    backups = tmp_path / "backups"
    first = backup.maybe_backup(db_file, backups)
    assert first is not None
    assert backup.maybe_backup(db_file, backups) is None
    assert len(list(backups.glob("case-*.db"))) == 1


def test_stale_backup_is_replaced_and_rotation_prunes_oldest(db_file, tmp_path, monkeypatch):
    backups = tmp_path / "backups"
    backups.mkdir()
    # three pre-existing copies, all older than BACKUP_EVERY (mtime drives
    # both the freshness gate and the pruning order)
    for i, name in enumerate(["case-a.db", "case-b.db", "case-c.db"]):
        old = backups / name
        old.write_bytes(b"old")
        stale = time.time() - 3 * 24 * 3600 + i
        os.utime(old, (stale, stale))
    monkeypatch.setattr(backup, "BACKUP_KEEP", 3)

    target = backup.maybe_backup(db_file, backups)

    assert target is not None
    survivors = {p.name for p in backups.glob("case-*.db")}
    assert survivors == {"case-b.db", "case-c.db", target.name}


def test_a_pre_upgrade_snapshot_is_outside_the_rotation(db_file, tmp_path, monkeypatch):
    """The pre-upgrade copy shares the folder and the `case-` prefix with the
    daily ones, but it is not one of them.

    It must not be pruned: it is the only image of the schema the user is
    leaving, and being the oldest file there it is precisely what rotation
    would reach for first. It must not satisfy the freshness gate either, or a
    snapshot taken minutes ago at startup would suppress that day's ordinary
    backup.
    """
    backups = tmp_path / "backups"
    snapshot = backup.snapshot_before_migration("0001_baseline", db_file, backups)
    assert snapshot is not None and snapshot.name == "case-pre-0001_baseline.db"
    # two stale daily copies, both older than BACKUP_EVERY (mtime drives both
    # the freshness gate and the pruning order) — the snapshot is the newest
    # file in the folder, so counting it would suppress the backup below
    for i, name in enumerate(["case-a.db", "case-b.db"]):
        old = backups / name
        old.write_bytes(b"old")
        stale = time.time() - 3 * 24 * 3600 + i
        os.utime(old, (stale, stale))
    monkeypatch.setattr(backup, "BACKUP_KEEP", 2)

    target = backup.maybe_backup(db_file, backups)

    assert target is not None, "the snapshot satisfied the freshness gate"
    assert {p.name for p in backups.glob("case-*.db")} == {
        snapshot.name,
        "case-b.db",
        target.name,
    }


def test_a_retried_migration_keeps_the_first_snapshot(db_file, tmp_path):
    """One copy per revision, and it is the first one.

    A migration that failed is retried on the next startup, from the same
    revision. Re-copying would overwrite the pre-upgrade state with whatever
    the failed attempt left behind — the copy is worth having precisely
    because it predates all of that.
    """
    backups = tmp_path / "backups"
    first = backup.snapshot_before_migration("0001_baseline", db_file, backups)
    assert first is not None
    first.write_bytes(b"the original copy")

    again = backup.snapshot_before_migration("0001_baseline", db_file, backups)

    assert again == first
    assert first.read_bytes() == b"the original copy"


def test_a_snapshot_of_a_missing_db_is_not_an_error(tmp_path):
    """Same fresh-install reasoning as the daily copy: nothing to protect."""
    assert backup.snapshot_before_migration("0001_baseline", tmp_path / "case.db", tmp_path) is None


def test_backup_failure_never_raises(tmp_path, monkeypatch):
    """The scheduler calls this at startup: an unwritable folder (locked
    drive, permissions) must log, not crash the app."""
    db = tmp_path / "case.db"
    sqlite3.connect(db).close()
    blocking_file = tmp_path / "backups"
    blocking_file.write_text("not a directory")
    assert backup.maybe_backup(db, blocking_file) is None


def test_two_forced_copies_in_the_same_second_are_two_files(db_file, tmp_path):
    """The name carries the clock to the second, and forced copies are taken
    before every destructive step. Two of them inside one second used to be one
    file — the second silently overwriting the first, which in the restore path
    meant overwriting the very copy being restored from."""
    backups = tmp_path / "backups"

    first = backup.maybe_backup(db_file, backups, force=True)
    second = backup.maybe_backup(db_file, backups, force=True)

    assert first is not None and second is not None
    assert first != second
    assert first.exists() and second.exists()


# --- Restoring ---------------------------------------------------------------


def _copy_of(source, target):
    """A throwaway duplicate of a database, standing in for the file someone
    carried over from another machine. Through the backup API, not
    `write_bytes`: a live database keeps its newest commits in `case.db-wal`,
    so a byte copy of the one file arrives without the tables it was made for.
    """
    backup._copy(source, target)
    return target


@pytest.fixture
def live_db(tmp_path):
    """The app's own database, initialised and open, exactly as a restore finds
    it at runtime. `conftest.isolated_database` has already pointed
    `database.engine` at this file, so `engine_db_path()` resolves to it."""
    database.init_db()
    path = database.engine_db_path()
    assert path is not None
    return path


def _fingerprints() -> list[str]:
    """What the live database holds now, read through a fresh session."""
    with database.SessionLocal() as db:
        return sorted(db.scalars(select(Property.fingerprint)))


def _store(*fingerprints: str) -> None:
    with database.SessionLocal() as db:
        for fingerprint in fingerprints:
            db.add(Property(fingerprint=fingerprint, city="Milano"))
        db.commit()


def test_a_restore_brings_the_rows_back_with_the_app_still_connected(live_db, tmp_path):
    """The acceptance test for the whole feature, done the hard way.

    A session stays checked out across the restore, because that is the truth of
    this app: the pool holds connections and six background modules hold
    sessions, so a restore that only works on an idle process is a restore that
    fails the day it is needed. `restore` disposes the pool and goes through the
    SQLite backup API for exactly this reason — a file dropped over an open
    database leaves the old `case.db-wal` shadowing the pages just written.
    """
    backups = tmp_path / "backups"
    _store("keep-me", "and-me")
    # a connection checked out before the restore and still open after it,
    # holding no transaction — an idle pooled connection, which is what the app
    # has between requests
    held = database.SessionLocal()
    assert len(held.scalars(select(Property)).all()) == 2
    held.commit()

    snapshot = backup.maybe_backup(live_db, backups, force=True)
    assert snapshot is not None

    with database.SessionLocal() as db:
        for prop in db.scalars(select(Property)):
            db.delete(prop)
        db.commit()
    assert _fingerprints() == []

    restored, safety = backup.restore(snapshot, live_db, backups)

    assert restored == snapshot
    assert safety is not None and safety.exists(), "the state being replaced was not copied aside"
    assert _fingerprints() == ["and-me", "keep-me"]
    held.close()


def test_a_file_that_is_not_our_database_is_refused_and_changes_nothing(live_db, tmp_path):
    """Three ways an upload can be wrong, and none of them costs the user
    anything: the live database still holds its rows afterwards, and no copy was
    even taken — validation runs before the first destructive step, so a bad
    file never gets as far as the safety snapshot."""
    backups = tmp_path / "backups"
    _store("still-here")

    not_a_database = tmp_path / "holiday.jpg"
    not_a_database.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 200)
    with pytest.raises(backup.RestoreError, match="not a SQLite database"):
        backup.restore(not_a_database, live_db, backups)

    someone_elses = tmp_path / "recipes.db"
    with sqlite3.connect(someone_elses) as conn:
        conn.execute("CREATE TABLE recipes (name)")
    with pytest.raises(backup.RestoreError, match="not one of this app's"):
        backup.restore(someone_elses, live_db, backups)

    truncated = tmp_path / "half-a-download.db"
    truncated.write_bytes(backup.SQLITE_HEADER + b"\x00" * 400)
    with pytest.raises(backup.RestoreError):
        backup.restore(truncated, live_db, backups)

    assert _fingerprints() == ["still-here"]
    assert not backups.exists(), "a refused file still triggered a backup round"


def test_the_listing_says_what_each_copy_is(live_db, tmp_path):
    """Date, size and schema revision per copy, newest first, and each kind
    named — restoring a copy is a decision, and it cannot be made from a row of
    filenames alone."""
    backups = tmp_path / "backups"
    daily = backup.maybe_backup(live_db, backups, force=True)
    assert daily is not None
    pre = backup.snapshot_before_migration("0001_baseline", live_db, backups)
    assert pre is not None
    imported = backup.accept_import(_copy_of(live_db, tmp_path / "from-the-laptop.db"), backups)

    listed = backup.list_copies(backups)

    assert {entry["name"]: entry["kind"] for entry in listed} == {
        daily.name: "daily",
        pre.name: "pre-upgrade",
        imported.name: "imported",
    }
    for entry in listed:
        assert entry["size_bytes"] > 0
        assert entry["taken_at"]
        # every one of these is a copy of a migrated database, so the revision
        # is what makes "is this older than the code reading it?" answerable
        assert entry["revision"], f"no schema revision reported for {entry['name']}"


def test_a_damaged_copy_is_still_listed(db_file, tmp_path):
    """It is the copy the user most needs to be told about. Reading its revision
    fails; leaving the row out would let a broken file look like no file."""
    backups = tmp_path / "backups"
    backups.mkdir()
    (backups / "case-20200101-000000.db").write_bytes(b"not really a database")

    listed = backup.list_copies(backups)

    assert [entry["name"] for entry in listed] == ["case-20200101-000000.db"]
    assert listed[0]["revision"] is None


def test_a_crafted_name_cannot_reach_outside_the_backups_folder(db_file, tmp_path):
    """The name comes from a browser and picks the file that is about to be
    written over the live database. Matched against the folder's contents rather
    than joined onto its path, so a traversal is simply not in the list."""
    backups = tmp_path / "backups"
    taken = backup.maybe_backup(db_file, backups)
    assert taken is not None

    assert backup.find(taken.name, backups) == taken
    for crafted in ("../case.db", "..\\case.db", str(db_file), "case-*.db"):
        with pytest.raises(backup.RestoreError):
            backup.find(crafted, backups)


def test_an_imported_database_is_outside_the_rotation_too(live_db, tmp_path, monkeypatch):
    """A database carried in from another install is not one of fourteen.

    It shares the folder and the `case-` prefix with the daily copies, and it is
    the one file there that exists nowhere else — losing it to the rotation
    would mean the user's other machine was the only copy after all.
    """
    backups = tmp_path / "backups"
    imported = backup.accept_import(_copy_of(live_db, tmp_path / "carried-in.db"), backups)
    for i, name in enumerate(["case-a.db", "case-b.db"]):
        old = backups / name
        old.write_bytes(b"old")
        stale = time.time() - 3 * 24 * 3600 + i
        os.utime(old, (stale, stale))
    monkeypatch.setattr(backup, "BACKUP_KEEP", 2)

    target = backup.maybe_backup(live_db, backups)

    assert target is not None, "the imported copy satisfied the freshness gate"
    assert {p.name for p in backups.glob("case-*.db")} == {
        imported.name,
        "case-b.db",
        target.name,
    }


def test_a_rejected_upload_leaves_nothing_behind(tmp_path):
    """The staged file is deleted when it fails validation: an unusable file
    left in the folder would be offered for restoring like any other."""
    backups = tmp_path / "backups"
    backups.mkdir()
    staged = backups / "import-1.part"
    staged.write_bytes(b"nothing like a database")

    with pytest.raises(backup.RestoreError):
        backup.accept_import(staged, backups)

    assert not staged.exists()
    assert backup.list_copies(backups) == []


# --- The routes that put all of this on the dashboard ------------------------


@pytest.fixture
def api(live_db):
    """The HTTP surface, over the per-test database `conftest` provides.

    No context manager, for the reason `test_routes.py` gives: entering it runs
    the app lifespan, which starts the real scheduler. The backups routes take
    no database session, so there is nothing to override — they resolve the live
    file through the engine, which is exactly the behaviour under test.
    """
    from app import main

    return TestClient(main.app)


def test_the_routes_take_a_copy_and_then_list_it(api, tmp_path):
    taken = api.post("/api/maintenance/backups")
    assert taken.status_code == 200
    name = taken.json()["name"]

    listed = api.get("/api/maintenance/backups").json()

    assert listed["folder"] == str(tmp_path / "backups")
    assert [entry["name"] for entry in listed["backups"]] == [name]
    assert listed["backups"][0]["kind"] == "daily"


def test_a_database_carried_in_can_be_uploaded_and_then_restored(api, live_db, tmp_path):
    """The whole point of the feature, over HTTP: a `case.db` from another
    install arrives as a raw body, is filed among the copies, and only a second,
    explicit request puts it over the live database."""
    _store("from-the-old-laptop")
    carried = _copy_of(live_db, tmp_path / "laptop-case.db")
    with database.SessionLocal() as db:
        for prop in db.scalars(select(Property)):
            db.delete(prop)
        db.commit()
    assert _fingerprints() == []

    imported = api.post("/api/maintenance/backups/import", content=carried.read_bytes())
    assert imported.status_code == 200, imported.text
    assert imported.json()["kind"] == "imported"
    # filing it must not have touched anything live
    assert _fingerprints() == []

    restored = api.post(f"/api/maintenance/backups/{imported.json()['name']}/restore")

    assert restored.status_code == 200, restored.text
    assert restored.json()["restored"] == imported.json()["name"]
    assert restored.json()["backup"], "the state being replaced was not named"
    assert _fingerprints() == ["from-the-old-laptop"]


def test_a_copy_downloads_as_the_file_it_is(api):
    name = api.post("/api/maintenance/backups").json()["name"]

    resp = api.get(f"/api/maintenance/backups/{name}")

    assert resp.status_code == 200
    assert name in resp.headers["content-disposition"]
    assert resp.content.startswith(backup.SQLITE_HEADER)


def test_a_name_that_is_not_in_the_folder_is_a_404(api):
    assert api.get("/api/maintenance/backups/case-nope.db").status_code == 404
    assert api.post("/api/maintenance/backups/case-nope.db/restore").status_code == 404


def test_an_upload_that_is_not_a_database_is_refused(api):
    resp = api.post("/api/maintenance/backups/import", content=b"holiday photo")

    assert resp.status_code == 400
    assert "SQLite" in resp.json()["detail"]
    assert api.get("/api/maintenance/backups").json()["backups"] == []


def test_a_restore_is_refused_while_a_scan_is_running(api, monkeypatch):
    """Same guard as the destructive resets and the restart: a scan is writing
    properties and their profile links, and swapping the file under it would
    leave both half-written."""
    name = api.post("/api/maintenance/backups").json()["name"]
    monkeypatch.setitem(scan_state, "running", True)

    resp = api.post(f"/api/maintenance/backups/{name}/restore")

    assert resp.status_code == 409
