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
from app.models import (ImportedListing, Listing, ListingProfile, PriceHistory,
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


# --- deleting a search "with its results" (data_reset.profile_results) ---
#
# The provenance links (ListingProfile) are what makes this answerable at all:
# before them, nothing in the DB knew which search had produced which card.

def _seed_found(db, profile, portal_id="1", **over) -> Property:
    """A property found by `profile`, wired exactly as upsert_listing wires it."""
    prop = Property(fingerprint=f"fp{portal_id}", status="active", city="milano")
    for k, v in over.items():
        setattr(prop, k, v)
    db.add(prop)
    db.commit()
    listing = Listing(property_id=prop.id, portal="immobiliare",
                      portal_id=portal_id, url=f"u{portal_id}")
    db.add(listing)
    db.add(PriceHistory(property_id=prop.id, new_price=250000.0))
    db.commit()
    db.add(ListingProfile(listing_id=listing.id, profile_id=profile.id))
    db.commit()
    return prop


def test_profile_results_ignores_properties_it_never_found(db):
    """Untracked cards (imported by email, or predating the provenance links)
    are not this search's to delete: attribution is by recorded link, never by
    a guess at the search criteria, which would sweep up a sibling search's
    results in the same city."""
    prof = _seed_profile(db)
    _seed_found(db, prof, "1")
    _seed_dashboard(db)   # no link: nothing says this search found it

    out = data_reset.profile_results(db, prof.id)

    assert out["tracked"] == 1
    assert out["deletable"] == 1


def test_profile_results_spares_shared_and_curated(db):
    """The two exclusions the delete dialog reports. A property another search
    also found stays (that search still covers it, and the next scan would
    re-create a blank card anyway); a favorited or annotated one stays because
    the curation is hand-made and a re-scan cannot rebuild it (invariant 10)."""
    prof = _seed_profile(db)
    other = _seed_profile(db, name="other")
    _seed_found(db, prof, "1")                       # deletable
    _seed_found(db, prof, "2", is_favorite=True)     # curated
    _seed_found(db, prof, "3", notes="call agency")  # curated
    shared = _seed_found(db, prof, "4")
    db.add(ListingProfile(listing_id=shared.listings[0].id, profile_id=other.id))
    db.commit()

    out = data_reset.profile_results(db, prof.id)

    assert out["tracked"] == 4
    assert out["deletable"] == 1
    assert out["kept_shared"] == 1
    assert out["kept_curated"] == 2
    assert [p.id for p in out["properties"]] == [_id_of(db, "1")]


def _id_of(db, portal_id: str) -> int:
    listing = db.scalar(select(Listing).where(Listing.portal_id == portal_id))
    assert listing is not None
    return listing.property_id


def test_delete_profile_results_takes_the_whole_card_with_it(db):
    """Physical delete, unlike the reversible "hide" of DELETE /properties/{id}:
    that one hides because a scan would resurrect the ad, while here the search
    that produced the card is going away in the same transaction."""
    prof = _seed_profile(db)
    prop = _seed_found(db, prof, "1")
    imp = ImportedListing(portal="immobiliare", portal_id="9", url="u",
                          status="accepted", property_id=prop.id)
    db.add(imp)
    db.commit()

    out = data_reset.delete_profile_results(db, prof.id)
    db.commit()

    assert out["deletable"] == 1 and out["listings"] == 1
    assert _count(db, Property) == 0
    assert _count(db, Listing) == 0
    assert _count(db, PriceHistory) == 0
    assert _count(db, ListingProfile) == 0   # cascaded with the listing
    db.refresh(imp)
    assert imp.property_id is None           # never left pointing at a ghost
    assert _count(db, SearchProfile) == 1    # the profile itself is the caller's job


def test_deleting_a_profile_alone_leaves_its_results_standing(db):
    """The default answer to the dialog: the search goes, the dashboard stays.
    Only the provenance links die with it (ORM cascade)."""
    prof = _seed_profile(db)
    _seed_found(db, prof, "1")

    db.delete(prof)
    db.commit()

    assert _count(db, Property) == 1
    assert _count(db, Listing) == 1
    assert _count(db, ListingProfile) == 0
