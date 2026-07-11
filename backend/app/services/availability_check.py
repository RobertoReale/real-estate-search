"""Live availability check (`AdProbe`) for properties already in the dashboard.

Just like `services/email_import.py` checks `ImportedListing` rows against
the portals one at a time, this module checks `Property` rows (`Listing` URLs)
on demand. It features:
- Lock-protected batch run (`_prop_check_run_lock`) with live progress polling
  (`_prop_check_progress`).
- Polite delay (`request_delay_seconds` & portal floors) between URL probes.
- Automatic DataDome cookie recovery if the portal blocks mid-batch.
"""
import logging
import threading
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..config import load_settings
from ..models import Property
from ..scrapers.base import AdProbe
from .email_import import (
    BLOCK_STREAK_ABORT,
    MAX_CHECKS_PER_CALL,
    MAX_COOKIE_REFRESHES_PER_CHECK,
    MIN_PROBE_DELAY,
    _try_cookie_recovery,
)

logger = logging.getLogger(__name__)


class AvailabilityCheckError(Exception):
    """Raised when a check cannot start (e.g. lock already held)."""


_prop_check_progress: dict = {"active": False, "done": 0, "total": 0, "gone": 0}
_prop_check_run_lock = threading.Lock()


def get_prop_check_progress() -> dict:
    """Snapshot of the running dashboard properties availability check, for UI polling."""
    return dict(_prop_check_progress)


def check_properties_availability(db: Session, properties: list[Property]) -> dict:
    """Checks whether the given properties (`Property`) are still online on their portals.

    For each property, `AdProbe` checks all its associated `listings`.
    - If at least one listing answers `True` (still online), the property is marked active.
    - If ALL listings answer `False` (404/gone), `Property.status = "gone"` and `gone_at` is set.
    - If blocked or network error (`None`), the property status is untouched.
    """
    if not _prop_check_run_lock.acquire(blocking=False):
        raise AvailabilityCheckError(
            "A property availability check is already running: wait for it to finish"
        )

    settings = load_settings()
    configured = float(settings.get("request_delay_seconds") or 6.0)
    # The slowest portal among the listings sets the delay floor
    all_portals = [l.portal for p in properties for l in p.listings]
    delay = max([configured] + [MIN_PROBE_DELAY.get(portal, 0.0) for portal in all_portals])
    probe = AdProbe(delay_seconds=delay)

    summary = {
        "checked": 0, "gone": 0, "online": 0, "unknown": 0,
        "aborted": False, "last_error": None, "cookie_refreshed": 0,
    }
    _prop_check_progress.update(active=True, done=0, total=len(properties), gone=0)

    try:
        block_streak = 0
        refreshes_used = 0
        for index, prop in enumerate(properties):
            if not prop.listings:
                # No portal listings attached: nothing to check
                _prop_check_progress.update(done=index + 1, gone=summary["gone"])
                continue

            results = []
            for listing in prop.listings:
                res = probe.check(listing.url)
                listing.last_seen_at = datetime.now(timezone.utc)
                results.append(res)
                if res is True and getattr(probe, "last_soup", None):
                    soup = probe.last_soup
                    if not listing.image_url:
                        og_img = (soup.find("meta", property="og:image")
                                  or soup.find("meta", attrs={"name": "twitter:image"}))
                        if og_img and og_img.get("content"):
                            listing.image_url = str(og_img["content"]).strip()[:500]
                    if not prop.image_url and listing.image_url:
                        prop.image_url = listing.image_url
                    from .repair_listings import is_bad_title
                    if is_bad_title(prop.title):
                        og_title = soup.find("meta", property="og:title")
                        if og_title and og_title.get("content"):
                            from .email_import import _clean_title
                            clean_og = _clean_title(str(og_title["content"]))
                            if clean_og and not is_bad_title(clean_og):
                                prop.title = clean_og
                if res is None and getattr(probe, "last_error", None):
                    summary["last_error"] = probe.last_error

                block_streak = block_streak + 1 if probe.was_blocked else 0
                if block_streak >= BLOCK_STREAK_ABORT:
                    if (refreshes_used < MAX_COOKIE_REFRESHES_PER_CHECK
                            and _try_cookie_recovery(
                                probe, listing.portal, settings, summary)):
                        refreshes_used += 1
                        block_streak = 0
                        continue
                    if refreshes_used < MAX_COOKIE_REFRESHES_PER_CHECK + 2 and len(getattr(probe, "impersonations", [])) > 1:
                        import time
                        logger.info("availability_check: portal rate limit / block streak reached, sleeping 12s and rotating session")
                        time.sleep(12.0)
                        probe._imp_index = (probe._imp_index + 1) % len(probe.impersonations)
                        if hasattr(probe, "_new_session"):
                            probe.session = probe._new_session()
                        probe._warmed_hosts = set()
                        probe.was_blocked = False
                        refreshes_used += 1
                        block_streak = 0
                        continue
                    logger.warning(
                        "availability_check: portal blocking, stopping after %s properties",
                        summary["checked"],
                    )
                    summary["aborted"] = True
                    break

            if summary["aborted"]:
                break

            # Evaluate property status based on all its listings
            if any(r is True for r in results):
                # At least one listing is still active online!
                summary["online"] += 1
                if prop.status == "gone":
                    # Reappeared online
                    prop.status = "active"
                    prop.gone_at = None
            elif all(r is False for r in results) and results:
                # All listings are confirmed gone (404 / removed)
                summary["gone"] += 1
                if prop.status != "gone":
                    prop.status = "gone"
                    if prop.gone_at is None:
                        prop.gone_at = datetime.now(timezone.utc)
            else:
                summary["unknown"] += 1

            summary["checked"] += 1
            prop.last_seen_at = datetime.now(timezone.utc)
            db.commit()
            _prop_check_progress.update(done=index + 1, gone=summary["gone"])

            if index + 1 < len(properties):
                probe.polite_sleep()
    finally:
        _prop_check_progress.update(active=False)
        _prop_check_run_lock.release()

    logger.info("availability_check: completed %s", summary)
    return summary
