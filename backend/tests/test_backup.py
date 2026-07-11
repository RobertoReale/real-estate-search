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


def test_stale_backup_is_replaced_and_rotation_prunes_oldest(
        db_file, tmp_path, monkeypatch):
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


def test_backup_failure_never_raises(tmp_path, monkeypatch):
    """The scheduler calls this at startup: an unwritable folder (locked
    drive, permissions) must log, not crash the app."""
    db = tmp_path / "case.db"
    sqlite3.connect(db).close()
    blocking_file = tmp_path / "backups"
    blocking_file.write_text("not a directory")
    assert backup.maybe_backup(db, blocking_file) is None
