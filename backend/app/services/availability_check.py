"""Live availability check (`AdProbe`) for properties already in the dashboard.

Asks the portals, on demand and one at a time, whether the ads behind a
`Property`'s `Listing` rows are still online. It features:
- Lock-protected batch run (`_check_run_lock`) with live progress polling
  (`_prop_check_progress`).
- Polite delay (`request_delay_seconds` & portal floors) between URL probes.
- Automatic DataDome cookie recovery if the portal blocks mid-batch.

The endpoint driving it is a sync `def` on purpose: FastAPI runs it in a
threadpool, so `/api/properties/check-progress` can still answer while a
minutes-long batch works. An `async def` would own the event loop for the whole
run and freeze the progress bar at 0% — exactly the "is it hung?" the bar
exists to answer. That is also why the progress dict below is module-level
(written by the worker thread, read by the poller) and cleared in a `finally`.
"""

import logging
import threading
import time
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..config import load_settings
from ..models import Property
from ..scrapers.base import AdProbe
from .timeutils import as_utc

logger = logging.getLogger(__name__)


class AvailabilityCheckError(Exception):
    """Raised when a check cannot start (e.g. lock already held)."""


# Serialized for a harsher reason than the scan: two concurrent batches double
# the request rate to the portals, and the pacing, the block-streak abort and
# the once-per-host warm-up all assume a single probe is talking to them.
# Threadpool execution means two requests genuinely can arrive at once — the
# dashboard is often open on phone and desktop at the same time — so the second
# run is refused with a readable error rather than allowed to race.
_check_run_lock = threading.Lock()

# The cap on live portal fetches per run. Few listings, on demand, spaced out:
# it is what keeps this from becoming a crawl of the whole dashboard.
MAX_CHECKS_PER_CALL = 50

# Idealista's own scraper raises its floor to 8s because "DataDome is sensitive
# to request frequency" there; an ad page is not gentler than a search page.
MIN_PROBE_DELAY = {"immobiliare": 6.0, "idealista": 8.0}

# Once the portal has started refusing, every further request digs the hole
# deeper — and the block lands on the IP the real scans need. Three in a row is
# an answer: stop, and tell the user why the batch ended early.
BLOCK_STREAK_ABORT = 3

# When checking large batches (e.g. 218 listings), allow up to 2 cookie refreshes
# or deep session resets before aborting.
MAX_COOKIE_REFRESHES_PER_CHECK = 2


def _try_cookie_recovery(probe, portal: str, settings: dict, summary: dict) -> bool:
    """Recover from a block during the availability check by minting a fresh
    DataDome cookie in a headless browser and rebuilding the probe's session
    around it, so the batch can carry on instead of giving up.

    Opt-in (`datadome_auto_refresh`) and best-effort: a missing browser, a
    CAPTCHA it cannot pass headless, or a refresh failure all return False and
    the caller aborts as before. This is the *same* mechanism the scanner runs
    before a scan (invariant 18) — here it fires reactively, on a block, which
    is exactly when the cookie has demonstrably burned.
    """
    if not settings.get("datadome_auto_refresh"):
        return False
    from . import cookie_harvester

    if not cookie_harvester.is_available():
        return False
    logger.info("availability check: portal blocking; grabbing a fresh DataDome cookie")
    try:
        result = cookie_harvester.refresh_into_settings(portal, headless=True)
    except Exception:
        logger.exception("availability check: cookie recovery failed")
        return False
    if not result.get("ok"):
        return False
    # Rebuild the probe around the new cookie, back to the preferred handshake,
    # and force a re-warm of the homepage so the fresh cookie is carried in.
    probe._imp_index = 0
    probe.session = probe._new_session()
    probe._warmed_hosts = set()
    probe.was_blocked = False
    summary["cookie_refreshed"] = summary.get("cookie_refreshed", 0) + 1
    return True


_prop_check_progress: dict = {"active": False, "done": 0, "total": 0, "gone": 0}
# Cooperative cancellation: the batch loop only owns the portal connection on
# its own thread, so there is no way to kill it from the outside. It polls
# this flag at the same per-property checkpoint as the probe budget cap
# (`MAX_CHECKS_PER_CALL`), so a cancel lands within one property's requests
# instead of needing to interrupt a live socket call.
_prop_check_cancel_event = threading.Event()


def get_prop_check_progress() -> dict:
    """Snapshot of the running dashboard properties availability check, for UI polling."""
    return dict(_prop_check_progress)


def request_cancel() -> None:
    """Signals a running batch to stop after its current property. A no-op
    when nothing is running -- the event is cleared at the start of the next
    batch regardless of whether a previous one ever consumed it."""
    _prop_check_cancel_event.set()


def _is_recently_checked(dt, hours: float = 6.0) -> bool:
    if dt is None or hours <= 0:
        return False
    now = datetime.now(UTC)
    return (now - as_utc(dt)).total_seconds() < hours * 3600


def check_properties_availability(
    db: Session, properties: list[Property], skip_recent_hours: float = 6.0
) -> dict:
    """Checks whether the given properties (`Property`) are still online on their portals.

    For each property, `AdProbe` checks all its associated `listings`.
    - If at least one listing answers `True` (still online), the property is marked active.
    - If ALL listings answer `False` (404/gone), `Property.status = "gone"` and `gone_at` is set.
    - If blocked or network error (`None`), the property status is untouched.
    """
    if not _check_run_lock.acquire(blocking=False):
        raise AvailabilityCheckError(
            "An availability check is already running (dashboard or email "
            "import): wait for it to finish"
        )
    _prop_check_cancel_event.clear()
    try:
        return _check_properties_availability_inner(db, properties, skip_recent_hours)
    finally:
        _check_run_lock.release()


def _check_properties_availability_inner(
    db: Session, properties: list[Property], skip_recent_hours: float = 6.0
) -> dict:
    settings = load_settings()
    configured = float(settings.get("request_delay_seconds") or 6.0)
    # The slowest portal among the listings sets the delay floor
    all_portals = [l.portal for p in properties for l in p.listings]
    delay = max([configured] + [MIN_PROBE_DELAY.get(portal, 0.0) for portal in all_portals])
    probe = AdProbe(delay_seconds=delay, cancel_event=_prop_check_cancel_event)

    summary = {
        "checked": 0,
        "gone": 0,
        "online": 0,
        "unknown": 0,
        "aborted": False,
        "capped": False,
        "cancelled": False,
        "last_error": None,
        "cookie_refreshed": 0,
        "transport": "fast requests (curl)",
    }
    _prop_check_progress.update(
        active=True,
        done=0,
        total=len(properties),
        gone=0,
        online=0,
        unknown=0,
        last_error=None,
        transport=summary["transport"],
    )
    logger.info(
        "availability_check: starting batch of %d properties (delay=%.1fs, skip_recent_hours=%.1f)",
        len(properties),
        delay,
        skip_recent_hours,
    )

    try:
        if settings.get("availability_browser_first") and hasattr(probe, "start_browser_session"):
            if probe.start_browser_session():
                probe._browser_primary = True
                summary["transport"] = getattr(probe, "browser_status", "") or "browser"
                logger.info(
                    "availability_check: running browser-first (curl_cffi bypassed) — %s",
                    summary["transport"],
                )
            else:
                # Surface WHY the browser did not take over (engine missing,
                # option off, session-0…) so the UI can explain instead of
                # silently falling back to the curl path that gets blocked.
                why = getattr(probe, "browser_status", "") or "unavailable"
                summary["transport"] = f"fast requests (curl) — browser {why}"
                logger.info(
                    "availability_check: browser-first requested but %s; using curl_cffi", why
                )
        _prop_check_progress.update(transport=summary["transport"])
        block_streak = 0
        refreshes_used = 0
        probes_used = 0
        for index, prop in enumerate(properties):
            if _prop_check_cancel_event.is_set():
                summary["cancelled"] = True
                logger.info(
                    "availability_check: cancelled by user after %d properties", summary["checked"]
                )
                break

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
                logger.info(
                    "availability_check: probe budget (%d) spent, stopping after %d properties",
                    MAX_CHECKS_PER_CALL,
                    index,
                )
                break

            if (
                skip_recent_hours > 0
                and len(properties) > 1
                and prop.listings
                and all(
                    _is_recently_checked(l.last_seen_at, skip_recent_hours) for l in prop.listings
                )
                and prop.status in ("active", "filtered", "hidden")
            ):
                summary["online"] += 1
                summary["checked"] += 1
                _prop_check_progress.update(done=index + 1, gone=summary["gone"])
                continue

            results = []
            for listing in prop.listings:
                probes_used += 1
                res = probe.check(listing.url)
                if res is not None:
                    listing.last_seen_at = datetime.now(UTC)
                results.append(res)
                if res is True and getattr(probe, "last_soup", None):
                    soup = probe.last_soup
                    if not listing.image_url:
                        og_img = soup.find("meta", property="og:image") or soup.find(
                            "meta", attrs={"name": "twitter:image"}
                        )
                        if og_img and og_img.get("content"):
                            listing.image_url = str(og_img["content"]).strip()[:500]
                    if not prop.image_url and listing.image_url:
                        prop.image_url = listing.image_url
                    from .listing_text import clean_title, is_bad_title

                    if is_bad_title(prop.title):
                        og_title = soup.find("meta", property="og:title")
                        if og_title and og_title.get("content"):
                            clean_og = clean_title(str(og_title["content"]))
                            if clean_og and not is_bad_title(clean_og):
                                prop.title = clean_og
                if res is None and getattr(probe, "last_error", None):
                    summary["last_error"] = probe.last_error

                block_streak = block_streak + 1 if probe.was_blocked else 0

                if _prop_check_cancel_event.is_set():
                    # Same priority as the browser-primary short-circuit below:
                    # none of the recovery levers (cookie refresh, TLS
                    # rotation, switching to the browser) are worth running
                    # once the user has asked to stop.
                    summary["cancelled"] = True
                    logger.info(
                        "availability_check: cancelled by user mid-property after %d properties",
                        summary["checked"],
                    )
                    break

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
                    if refreshes_used < MAX_COOKIE_REFRESHES_PER_CHECK and _try_cookie_recovery(
                        probe, listing.portal, settings, summary
                    ):
                        refreshes_used += 1
                        block_streak = 0
                        continue
                    if (
                        refreshes_used < MAX_COOKIE_REFRESHES_PER_CHECK + 2
                        and len(getattr(probe, "impersonations", [])) > 1
                    ):
                        logger.info(
                            "availability_check: portal rate limit / block streak reached, sleeping 12s and rotating session"
                        )
                        time.sleep(12.0)
                        probe._imp_index = (probe._imp_index + 1) % len(probe.impersonations)
                        if hasattr(probe, "_new_session"):
                            probe.session = probe._new_session()
                        probe._warmed_hosts = set()
                        probe.was_blocked = False
                        refreshes_used += 1
                        block_streak = 0
                        continue
                    if (
                        hasattr(probe, "start_browser_session")
                        and not getattr(probe, "_browser_primary", False)
                        and probe.start_browser_session()
                    ):
                        # Last resort, opt-in (invariant 18): switch the rest of
                        # the batch to the persistent browser instead of
                        # hammering a TLS session the portal already refused.
                        # Sticky (invariant 16): mark browser-primary so every
                        # remaining ad routes through it — and so the next block
                        # streak hits the short-circuit above and aborts instead
                        # of re-running these curl-only levers forever.
                        probe._browser_primary = True
                        summary["transport"] = getattr(probe, "browser_status", "") or "browser"
                        _prop_check_progress.update(transport=summary["transport"])
                        logger.info(
                            "availability_check: curl_cffi blocked repeatedly, switching the rest of the batch to the persistent browser session — %s",
                            summary["transport"],
                        )
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

            if summary["aborted"] or summary["cancelled"]:
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
                        prop.gone_at = datetime.now(UTC)
            else:
                summary["unknown"] += 1

            logger.info(
                "availability_check: [%d/%d] property %s -> %s (online=%d, gone=%d, unknown=%d)",
                index + 1,
                len(properties),
                prop.id,
                prop.status,
                summary["online"],
                summary["gone"],
                summary["unknown"],
            )
            summary["checked"] += 1
            prop.last_seen_at = datetime.now(UTC)
            db.commit()
            _prop_check_progress.update(
                done=index + 1,
                gone=summary["gone"],
                online=summary["online"],
                unknown=summary["unknown"],
                last_error=summary["last_error"],
            )

            if index + 1 < len(properties):
                probe.polite_sleep()
    finally:
        # hasattr: tests swap in fake probes without the browser machinery
        if hasattr(probe, "close_browser_session"):
            probe.close_browser_session()
        _prop_check_progress.update(active=False)

    logger.info("availability_check: completed %s", summary)
    return summary
