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
import time
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


def _is_recently_checked(dt, hours: float = 6.0) -> bool:
    if dt is None or hours <= 0:
        return False
    now = datetime.now(timezone.utc)
    dt_tz = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    return (now - dt_tz).total_seconds() < hours * 3600


def check_properties_availability(db: Session, properties: list[Property], skip_recent_hours: float = 6.0) -> dict:
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
    try:
        return _check_properties_availability_inner(db, properties, skip_recent_hours)
    finally:
        _prop_check_run_lock.release()


def _check_properties_availability_inner(db: Session, properties: list[Property], skip_recent_hours: float = 6.0) -> dict:
    settings = load_settings()
    configured = float(settings.get("request_delay_seconds") or 6.0)
    # The slowest portal among the listings sets the delay floor
    all_portals = [l.portal for p in properties for l in p.listings]
    delay = max([configured] + [MIN_PROBE_DELAY.get(portal, 0.0) for portal in all_portals])
    probe = AdProbe(delay_seconds=delay)

    summary = {
        "checked": 0, "gone": 0, "online": 0, "unknown": 0,
        "aborted": False, "capped": False, "last_error": None,
        "cookie_refreshed": 0,
    }
    _prop_check_progress.update(active=True, done=0, total=len(properties),
                                gone=0, online=0, unknown=0, last_error=None)
    logger.info("availability_check: starting batch of %d properties (delay=%.1fs, skip_recent_hours=%.1f)",
                len(properties), delay, skip_recent_hours)

    try:
        if settings.get("availability_browser_first") and hasattr(
                probe, "start_browser_session"):
            if probe.start_browser_session():
                probe._browser_primary = True
                logger.info("availability_check: running browser-first (curl_cffi bypassed)")
            else:
                logger.info("availability_check: browser-first requested but the browser is unavailable; using curl_cffi")
        block_streak = 0
        refreshes_used = 0
        probes_used = 0
        for index, prop in enumerate(properties):
            if not prop.listings:
                # No portal listings attached: nothing to check
                _prop_check_progress.update(done=index + 1, gone=summary["gone"])
                continue

            if probes_used >= MAX_CHECKS_PER_CALL:
                # The cap bounds portal fetches, not selection size: recently
                # verified properties skip for free, so a "select all" batch
                # advances by up to MAX_CHECKS_PER_CALL live probes per run
                # and the next run resumes past them (smart resume).
                summary["capped"] = True
                logger.info("availability_check: probe budget (%d) spent, "
                            "stopping after %d properties", MAX_CHECKS_PER_CALL, index)
                break

            if (skip_recent_hours > 0 and len(properties) > 1 and prop.listings
                    and all(_is_recently_checked(l.last_seen_at, skip_recent_hours) for l in prop.listings)
                    and prop.status in ("active", "filtered", "hidden")):
                summary["online"] += 1
                summary["checked"] += 1
                _prop_check_progress.update(done=index + 1, gone=summary["gone"])
                continue

            results = []
            for listing in prop.listings:
                probes_used += 1
                res = probe.check(listing.url)
                if res is not None:
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
                    if getattr(probe, "_browser_primary", False):
                        # Already running through the persistent headless
                        # browser and STILL blocked: the portal is challenging
                        # the browser itself (invariant 16). The curl_cffi levers
                        # below cannot clear a browser CAPTCHA — a fresh cookie
                        # relaunches a headless browser, TLS rotation sleeps 12s,
                        # and check() never even touches curl in this mode. That
                        # is exactly the grind that freezes the progress bar for
                        # minutes on an already-lost batch. Stop now.
                        logger.warning(
                            "availability_check: browser session also blocked, stopping after %s properties",
                            summary["checked"],
                        )
                        summary["aborted"] = True
                        break
                    if (refreshes_used < MAX_COOKIE_REFRESHES_PER_CHECK
                            and _try_cookie_recovery(
                                probe, listing.portal, settings, summary)):
                        refreshes_used += 1
                        block_streak = 0
                        continue
                    if refreshes_used < MAX_COOKIE_REFRESHES_PER_CHECK + 2 and len(getattr(probe, "impersonations", [])) > 1:
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
                    if (hasattr(probe, "start_browser_session")
                            and not getattr(probe, "_browser_primary", False)
                            and probe.start_browser_session()):
                        # Last resort, opt-in (invariant 18): switch the rest of
                        # the batch to the persistent browser instead of
                        # hammering a TLS session the portal already refused.
                        # Sticky (invariant 16): mark browser-primary so every
                        # remaining ad routes through it — and so the next block
                        # streak hits the short-circuit above and aborts instead
                        # of re-running these curl-only levers forever.
                        probe._browser_primary = True
                        logger.info("availability_check: curl_cffi blocked repeatedly, switching the rest of the batch to the persistent browser session")
                        time.sleep(6.0)
                        block_streak = 0
                        continue
                    # Every lever tried: insisting past here only deepens the
                    # block on the IP the scheduled scans depend on
                    # (invariant 16) — stop and tell the user why.
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

            logger.info("availability_check: [%d/%d] property %s -> %s (online=%d, gone=%d, unknown=%d)",
                        index + 1, len(properties), prop.id, prop.status,
                        summary["online"], summary["gone"], summary["unknown"])
            summary["checked"] += 1
            prop.last_seen_at = datetime.now(timezone.utc)
            db.commit()
            _prop_check_progress.update(done=index + 1, gone=summary["gone"],
                                        online=summary["online"],
                                        unknown=summary["unknown"],
                                        last_error=summary["last_error"])

            if index + 1 < len(properties):
                probe.polite_sleep()
    finally:
        # hasattr: tests swap in fake probes without the browser machinery
        if hasattr(probe, "close_browser_session"):
            probe.close_browser_session()
        _prop_check_progress.update(active=False)

    logger.info("availability_check: completed %s", summary)
    return summary
