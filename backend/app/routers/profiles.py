"""Monitored searches: CRUD plus the bulk actions behind the SearchProfiles
panel.

The delete path is the subtle one — it is the single place a Property is
physically removed rather than hidden, and what it may remove is decided from
the ListingProfile provenance links, never from the search criteria
(invariant 20). `data_reset` owns that decision; this module only refuses it
mid-scan and keeps the profile deletion in the same transaction.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..models import SearchProfile
from ..scrapers import detect_portal
from ..services import data_reset
from ..services.scanner import scan_state
from ..services.search_validator import check_duplicate_profile

router = APIRouter()


@router.get("/api/search-profiles", response_model=list[schemas.SearchProfileOut])
def list_profiles(db: Session = Depends(get_db)):
    return list(db.scalars(select(SearchProfile).order_by(SearchProfile.id)))


@router.post("/api/search-profiles", response_model=schemas.SearchProfileOut)
def create_profile(data: schemas.SearchProfileIn, db: Session = Depends(get_db)):
    dup = check_duplicate_profile(db, data.search_url, data.excluded_keywords)
    if dup:
        raise HTTPException(
            status_code=400,
            detail=f"An identical monitored search already exists ('{dup.name}'): same URL and same excluded keywords.",
        )
    profile = SearchProfile(
        name=data.name,
        portal=detect_portal(data.search_url),
        search_url=data.search_url,
        excluded_keywords=data.excluded_keywords,
        notify_channels=data.notify_channels,
        is_active=data.is_active,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.put("/api/search-profiles/{profile_id}", response_model=schemas.SearchProfileOut)
def update_profile(profile_id: int, data: schemas.SearchProfileIn, db: Session = Depends(get_db)):
    profile = db.get(SearchProfile, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    dup = check_duplicate_profile(
        db, data.search_url, data.excluded_keywords, exclude_profile_id=profile_id
    )
    if dup:
        raise HTTPException(
            status_code=400,
            detail=f"An identical monitored search already exists ('{dup.name}'): same URL and same excluded keywords.",
        )

    if data.search_url != profile.search_url:
        # a new URL is a new search: the old baseline says nothing about it.
        # Left armed, the next scan would notify every listing of the new
        # search as "new" — the flood invariant 3 exists to prevent.
        profile.baseline_done = False
        profile.last_run_at = None
        profile.last_run_status = ""
        profile.last_run_detail = ""
        profile.consecutive_failures = 0
        profile.health_alert_sent = False
    profile.name = data.name
    profile.search_url = data.search_url
    profile.portal = detect_portal(data.search_url)
    profile.excluded_keywords = data.excluded_keywords
    profile.notify_channels = data.notify_channels
    profile.is_active = data.is_active
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/api/search-profiles/results")
def profile_results(data: schemas.SearchProfileIdsIn, db: Session = Depends(get_db)):
    """How many dashboard properties these searches produced, and how many of
    them deleting them would actually remove — the numbers the delete dialog
    shows before the user chooses. See data_reset.profile_results for what is
    spared. Asked about the whole selection at once, because "also found by
    another search" only means "another search that survives"."""
    summary = data_reset.profile_results(db, data.ids)
    summary.pop("properties")
    return summary


@router.post("/api/search-profiles/bulk")
def bulk_profiles(data: schemas.SearchProfileBulkIn, db: Session = Depends(get_db)):
    """Apply activate/pause/notify/delete to several monitored searches at once.

    The single-search buttons go through here too (a selection of one): the
    delete's ownership rules are subtle enough (invariant 20) that a second
    implementation for the one-item case would be a second thing to get wrong.
    Missing ids are skipped silently, as in the other bulk routes.
    """
    profiles = [p for p in (db.get(SearchProfile, x) for x in data.ids) if p]

    if data.action == "delete":
        if data.delete_results and scan_state["running"]:
            # a scan in flight is writing the very links this decision reads (and
            # would re-create the properties it deletes): same guard the resets use
            raise HTTPException(
                409,
                "A scan is running: wait for it to finish before deleting the results",
            )
        # results first, in the same transaction: the classification reads the
        # profiles' links, and deleting the profiles cascades them away
        results = (
            data_reset.delete_profile_results(db, [p.id for p in profiles])
            if data.delete_results
            else None
        )
        for profile in profiles:
            db.delete(profile)
        db.commit()
        return {"ok": True, "processed": len(profiles), "results": results}

    for profile in profiles:
        if data.action == "activate":
            profile.is_active = True
        elif data.action == "pause":
            profile.is_active = False
        elif data.action == "notify":
            profile.notify_channels = data.notify_channels
    db.commit()
    return {"ok": True, "processed": len(profiles)}
