"""Tests for the user-triggered data resets (services/data_reset.py).

Offline, in-memory SQLite. The invariant that must not regress is the baseline
reset on a dashboard wipe: without it the next scan would treat every re-found
listing as new and flood the user with notifications (invariant 3).
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (ImportedListing, Listing, PriceHistory,
                        PricingSnapshot, Property, SearchProfile)
from app.services import data_reset


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def _count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def _seed_dashboard(db) -> Property:
    prop = Property(fingerprint="fp1", status="active", city="milano")
    db.add(prop)
    db.commit()
    db.add(Listing(property_id=prop.id, portal="immobiliare",
                   portal_id="1", url="u"))
    db.add(PriceHistory(property_id=prop.id, new_price=250000.0))
    db.commit()
    return prop


def _seed_profile(db, **over) -> SearchProfile:
    p = SearchProfile(
        name="p", portal="immobiliare", search_url="https://x",
        baseline_done=True, consecutive_failures=4, health_alert_sent=True,
        last_run_status="blocked", last_run_at=datetime.now(timezone.utc),
    )
    for k, v in over.items():
        setattr(p, k, v)
    db.add(p)
    db.commit()
    return p


def test_reset_email_import_clears_every_status(db):
    """The whole point is to forget past decisions and re-review: even the
    'discarded' rows (normally kept forever for idempotency, invariant 12) go."""
    for pid, status in (("1", "pending"), ("2", "discarded"), ("3", "accepted")):
        db.add(ImportedListing(portal="immobiliare", portal_id=pid,
                               url="u", status=status))
    db.commit()

    out = data_reset.reset_email_import(db)

    assert out["deleted"]["imported_listings"] == 3
    assert _count(db, ImportedListing) == 0


def test_clear_dashboard_deletes_listings_but_keeps_profiles(db):
    _seed_dashboard(db)
    _seed_profile(db)

    out = data_reset.clear_dashboard(db)

    assert out["deleted"] == {"price_history": 1, "listings": 1, "properties": 1}
    assert _count(db, Property) == 0
    assert _count(db, Listing) == 0
    assert _count(db, PriceHistory) == 0
    assert _count(db, SearchProfile) == 1   # profiles survive


def test_clear_dashboard_resets_the_baseline(db):
    """Invariant 3: a wiped dashboard with baseline_done still True would make
    the next scan notify on every re-found listing. The reset must re-arm the
    silent baseline and clear the stale run/health state with it."""
    _seed_dashboard(db)
    prof = _seed_profile(db)

    data_reset.clear_dashboard(db)
    db.refresh(prof)

    assert prof.baseline_done is False
    assert prof.last_run_at is None
    assert prof.last_run_status == ""
    assert prof.consecutive_failures == 0
    assert prof.health_alert_sent is False


def test_clear_dashboard_drops_dangling_import_references(db):
    """An accepted import points at a property we are about to delete: the
    reference must be nulled, not left dangling at a ghost id."""
    prop = _seed_dashboard(db)
    imp = ImportedListing(portal="immobiliare", portal_id="9", url="u",
                          status="accepted", property_id=prop.id)
    db.add(imp)
    db.commit()

    data_reset.clear_dashboard(db)
    db.refresh(imp)

    assert imp.property_id is None
    assert _count(db, ImportedListing) == 1   # the row itself is kept


def test_clear_pricing_snapshots_leaves_listings(db):
    _seed_dashboard(db)
    db.add(PricingSnapshot(captured_on=datetime.now(timezone.utc).date(),
                           city="milano", zone="", contract="sale",
                           median_sqm_price=3500.0, sample_count=5))
    db.commit()

    out = data_reset.clear_pricing_snapshots(db)

    assert out["deleted"]["pricing_snapshots"] == 1
    assert _count(db, PricingSnapshot) == 0
    assert _count(db, Property) == 1   # untouched


def test_factory_reset_empties_everything(db, monkeypatch, tmp_path):
    _seed_dashboard(db)
    _seed_profile(db)
    db.add(ImportedListing(portal="immobiliare", portal_id="1", url="u"))
    db.add(PricingSnapshot(captured_on=datetime.now(timezone.utc).date(),
                           city="milano", zone="", contract="sale",
                           median_sqm_price=3500.0, sample_count=5))
    db.commit()

    # no real DB file in this test: force the backup to a no-op, and point
    # DB_PATH at a missing file so the "backup failed" guard reads this as
    # the legitimate fresh-install case rather than a failed snapshot
    from app.services import backup
    monkeypatch.setattr(backup, "maybe_backup", lambda **k: None)
    monkeypatch.setattr(data_reset, "DB_PATH", tmp_path / "missing.db")

    out = data_reset.factory_reset(db)

    for model in (Property, Listing, PriceHistory, PricingSnapshot,
                  ImportedListing, SearchProfile):
        assert _count(db, model) == 0
    assert out["deleted"]["search_profiles"] == 1
    assert out["backup"] is None


def test_factory_reset_aborts_when_the_backup_fails(db, monkeypatch, tmp_path):
    """Regression: maybe_backup swallows failures and returns None, and the
    wipe proceeded anyway — contradicting the "recoverable from backups"
    promise. With a real DB file on disk and no snapshot, the reset must
    refuse and leave every row in place."""
    _seed_dashboard(db)
    db.commit()

    from app.services import backup
    monkeypatch.setattr(backup, "maybe_backup", lambda **k: None)
    real_db = tmp_path / "case.db"
    real_db.write_bytes(b"not empty")
    monkeypatch.setattr(data_reset, "DB_PATH", real_db)

    with pytest.raises(data_reset.ResetError):
        data_reset.factory_reset(db)
    assert _count(db, Property) > 0  # nothing was wiped
