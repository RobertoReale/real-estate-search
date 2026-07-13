"""User-triggered data resets (Settings → Data management).

Each reset is scoped and irreversible. The dashboard is rebuildable by a scan,
so wiping it is cheap; the price history and days-on-market data are not, so a
factory reset takes a forced backup of case.db first (recoverable from
backend/backups/). Every function returns the row counts it removed, so the UI
can tell the user exactly what happened.
"""
import logging
from collections.abc import Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from ..config import DB_PATH
from ..models import (ImportedListing, Listing, ListingProfile, PriceHistory,
                      PricingSnapshot, Property, SearchProfile)

logger = logging.getLogger(__name__)


class ResetError(Exception):
    """A reset could not proceed safely (e.g. the pre-wipe backup failed)."""


def _count(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def profile_results(db: Session, profile_ids: Sequence[int]) -> dict:
    """Classifies the properties a set of monitored searches has produced, so
    deleting them can offer (and preview) "delete their results too".

    The set, not a single id, is what makes a bulk delete answerable: a property
    found by two of the searches being deleted is nobody's leftover, while one
    also found by a search that survives is (and stays). Passing one id is just
    the degenerate case.

    Provenance comes from the ListingProfile links the scanner writes, never
    from a guess at the search criteria: two searches on the same city overlap
    heavily, and inferring ownership from city+contract would delete cards the
    other one found. The consequence is that properties predating those links
    (nothing has re-found them since the feature shipped) are invisible here —
    deliberately, since "not attributable" must fail towards keeping data.

    Three exclusions, each protecting something a re-scan cannot rebuild:
      * `shared`: a search *outside the set* also found the ad. It stays; that
        search still covers it, and deleting would throw away its price history
        only for the next scan to re-create a blank card.
      * `favorite` / `noted`: hand-curated (invariant 10), the one thing in the
        dashboard that exists nowhere else.
    Returns the counts plus the Property objects that are actually deletable.
    """
    ids = list(profile_ids)
    mine = select(ListingProfile.listing_id).where(
        ListingProfile.profile_id.in_(ids)
    )
    shared_property_ids = set(db.scalars(
        select(Listing.property_id)
        .join(ListingProfile, ListingProfile.listing_id == Listing.id)
        .where(ListingProfile.profile_id.not_in(ids),
               Listing.property_id.in_(
                   select(Listing.property_id).where(Listing.id.in_(mine))
               ))
    ))
    props = list(db.scalars(
        select(Property).where(Property.id.in_(
            select(Listing.property_id).where(Listing.id.in_(mine))
        ))
    ))

    deletable: list[Property] = []
    kept_shared = kept_curated = 0
    for prop in props:
        if prop.id in shared_property_ids:
            kept_shared += 1
        elif prop.is_favorite or (prop.notes or "").strip():
            kept_curated += 1
        else:
            deletable.append(prop)

    return {
        "tracked": len(props),
        "deletable": len(deletable),
        "kept_shared": kept_shared,
        "kept_curated": kept_curated,
        "properties": deletable,
    }


def delete_profile_results(db: Session, profile_ids: Sequence[int]) -> dict:
    """Deletes the properties `profile_results` found to be these searches' own.

    A physical delete, not the reversible "hide" of DELETE /api/properties/{id}
    (invariant 5): that endpoint hides because a scan would re-find and
    resurrect the ad, whereas here the searches that produced these cards are
    being deleted in the same breath — nothing is left to bring them back.
    Does not commit: the caller deletes the profiles in the same transaction, so
    a failure cannot leave the results wiped and the searches still monitoring.
    """
    summary = profile_results(db, profile_ids)
    props = summary.pop("properties")
    listings = sum(len(p.listings) for p in props)
    ids = [p.id for p in props]
    if ids:
        # accepted inbox imports point at these properties: drop the reference
        # before the row goes, or the import stays wired to a ghost id
        db.execute(update(ImportedListing)
                   .where(ImportedListing.property_id.in_(ids))
                   .values(property_id=None))
    for prop in props:
        db.delete(prop)  # cascades listings (and their links) + price history
    db.flush()
    summary["listings"] = listings
    logger.info("Deleted results of search profiles %s: %s",
                list(profile_ids), summary)
    return summary


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
    # a Core delete skips the ORM cascade that would clear these links
    db.execute(delete(ListingProfile))
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
    for model in (PriceHistory, ListingProfile, Listing, ImportedListing,
                  PricingSnapshot, Property, SearchProfile):
        db.execute(delete(model))
    db.commit()
    logger.info("data-reset: factory reset %s (backup=%s)", counts,
                backup.name if backup else None)
    return {"scope": "factory", "deleted": counts,
            "backup": backup.name if backup else None}
