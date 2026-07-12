"""User-triggered data resets (Settings → Data management).

Each reset is scoped and irreversible. The dashboard is rebuildable by a scan,
so wiping it is cheap; the price history and days-on-market data are not, so a
factory reset takes a forced backup of case.db first (recoverable from
backend/backups/). Every function returns the row counts it removed, so the UI
can tell the user exactly what happened.
"""
import logging

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from ..config import DB_PATH
from ..models import (ImportedListing, Listing, PriceHistory, PricingSnapshot,
                      Property, SearchProfile)

logger = logging.getLogger(__name__)


class ResetError(Exception):
    """A reset could not proceed safely (e.g. the pre-wipe backup failed)."""


def _count(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def reset_email_import(db: Session) -> dict:
    """Wipes every staged inbox listing so the import can be redone from zero.

    This deliberately drops the `discarded` rows too — normally kept forever as
    the memory that makes a re-scan idempotent (invariant 12). That is the whole
    point here: the user is asking to forget those decisions and re-review the
    inbox afresh, so the next scan will re-stage listings previously rejected.
    """
    n = _count(db, ImportedListing)
    db.execute(delete(ImportedListing))
    db.commit()
    logger.info("data-reset: cleared %d imported listings", n)
    return {"scope": "email-import", "deleted": {"imported_listings": n}}


def clear_dashboard(db: Session) -> dict:
    """Deletes all scanned properties (and their listings/price history), then
    resets every search profile to a fresh baseline. A scan rebuilds the grid.

    Resetting `baseline_done` is not optional (invariant 3): with the dashboard
    empty but the baseline flag left on, the next scan would treat every
    re-found listing as brand new and fire a notification for each one. Clearing
    it makes the next scan a silent baseline again.
    """
    counts = {
        "price_history": _count(db, PriceHistory),
        "listings": _count(db, Listing),
        "properties": _count(db, Property),
    }
    db.execute(delete(PriceHistory))
    db.execute(delete(Listing))
    # accepted imports pointed at properties we are about to delete: drop the
    # dangling reference so a later enrich/re-scan does not chase a ghost id
    db.execute(update(ImportedListing)
               .where(ImportedListing.property_id.is_not(None))
               .values(property_id=None))
    db.execute(delete(Property))
    db.execute(update(SearchProfile).values(
        baseline_done=False,
        last_run_at=None,
        last_run_status="",
        last_run_detail="",
        consecutive_failures=0,
        health_alert_sent=False,
    ))
    db.commit()
    logger.info("data-reset: cleared dashboard %s", counts)
    return {"scope": "dashboard", "deleted": counts}


def clear_pricing_snapshots(db: Session) -> dict:
    """Drops the daily median history behind the price-trend charts, leaving the
    listings themselves untouched — a fresh start for the trend series only."""
    n = _count(db, PricingSnapshot)
    db.execute(delete(PricingSnapshot))
    db.commit()
    logger.info("data-reset: cleared %d pricing snapshots", n)
    return {"scope": "pricing-snapshots", "deleted": {"pricing_snapshots": n}}


def factory_reset(db: Session) -> dict:
    """Empties the whole database — dashboard, profiles, imports, snapshots —
    back to a fresh install. `settings.json` (credentials, cookie) is kept.

    A forced backup is taken first, so even this is recoverable from
    backend/backups/. Children are deleted before parents (SQLite does not
    enforce the FKs, but a clean order keeps this correct if it ever does)."""
    from .backup import maybe_backup
    backup = maybe_backup(force=True)
    if backup is None and DB_PATH.exists():
        # maybe_backup swallows its own failures (disk full, locked file) and
        # returns None; wiping anyway would contradict the "recoverable from
        # backend/backups/" promise this function is built on. A fresh install
        # (no DB file yet) is the only legitimate None.
        raise ResetError(
            "Pre-reset backup failed: the factory reset was NOT performed. "
            "Check disk space/permissions for backend/backups/ and retry."
        )
    counts = {
        "price_history": _count(db, PriceHistory),
        "listings": _count(db, Listing),
        "properties": _count(db, Property),
        "pricing_snapshots": _count(db, PricingSnapshot),
        "imported_listings": _count(db, ImportedListing),
        "search_profiles": _count(db, SearchProfile),
    }
    for model in (PriceHistory, Listing, ImportedListing, PricingSnapshot,
                  Property, SearchProfile):
        db.execute(delete(model))
    db.commit()
    logger.info("data-reset: factory reset %s (backup=%s)", counts,
                backup.name if backup else None)
    return {"scope": "factory", "deleted": counts,
            "backup": backup.name if backup else None}
