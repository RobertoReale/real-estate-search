"""Automatic case.db backup: freshness gate, rotation, and fail-safety.

The database is the only place price history and days-on-market data exist —
no re-scan can rebuild them — yet for months it lived as a single file with no
copy anywhere. `maybe_backup` runs at startup and daily: these tests pin down
that it is idempotent within 24h (dev restarts every few minutes must not pile
up copies), that rotation caps disk usage, and that it never raises (a failed
backup must not take startup down with it).
"""

import os
import sqlite3
import time

import pytest

from app.services import backup


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
