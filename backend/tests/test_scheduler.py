"""Catch-up decision for the startup scan.

APScheduler's interval trigger first fires one full interval after startup.
This app runs on a PC that is switched on occasionally: with the default
8-hour interval, sessions shorter than 8 hours meant the scheduled scan
*never* ran — the log showed fifteen restarts over two days and not one
interval-triggered scan. `_scan_overdue` is the pure decision behind the
catch-up: these tests pin down when a startup scan is due. The APScheduler
wiring itself stays untested, like the rest of the scheduling machinery.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import SearchProfile
from app.services.scheduler import _scan_overdue


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def _profile(**kwargs) -> SearchProfile:
    base = dict(name="p", portal="immobiliare", search_url="u", is_active=True)
    base.update(kwargs)
    return SearchProfile(**base)


def test_no_profiles_means_no_catchup(db):
    """A fresh install has nothing to scan: firing a catch-up would only log noise."""
    assert _scan_overdue(db, 60) is False


def test_never_scanned_profile_is_overdue(db):
    db.add(_profile(last_run_at=None))
    db.commit()
    assert _scan_overdue(db, 60) is True


def test_recent_scan_is_not_overdue(db):
    db.add(_profile(last_run_at=datetime.now(timezone.utc) - timedelta(minutes=5)))
    db.commit()
    assert _scan_overdue(db, 60) is False


def test_stale_scan_is_overdue_even_when_sqlite_returns_naive(db):
    # SQLite strips tzinfo: the helper must reattach UTC, not crash on
    # naive-vs-aware comparison (project-wide convention, see developer notes)
    naive_stale = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=9)
    db.add(_profile(last_run_at=naive_stale))
    db.commit()
    assert _scan_overdue(db, 480) is True


def test_inactive_profiles_do_not_trigger_catchup(db):
    """A paused profile must not wake the scanner: the user disabled it."""
    db.add(_profile(is_active=False, last_run_at=None))
    db.commit()
    assert _scan_overdue(db, 60) is False


def test_newest_scan_wins_across_profiles(db):
    """One stale profile among fresh ones is the normal state right after a
    profile is added: the *newest* run decides, or every new profile would
    look like an outage."""
    db.add(_profile(name="fresh", last_run_at=datetime.now(timezone.utc)))
    db.add(_profile(name="stale", last_run_at=None))
    db.commit()
    assert _scan_overdue(db, 60) is False
