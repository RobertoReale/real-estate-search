"""Scan Orchestrator: executes active search profiles, normalizes,
deduplicates, filters by keywords, and sends Telegram notifications."""

import logging
import threading
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from ..config import load_settings
from ..database import SessionLocal
from ..models import Property, SearchProfile
from ..scrapers import get_scraper
from . import deal_score, notifier, pricing_stats
from .deduplicator import upsert_listing
from .filter_engine import find_excluded_keyword, parse_keywords_csv

logger = logging.getLogger(__name__)

# On the first scan of a profile *all* properties are "new": sending
# a notification for each would mean hundreds of Telegram messages.
# The first pass only builds the comparison baseline.
MAX_NOTIFICATIONS_PER_SCAN = 15

# A property not seen for this many days is marked "gone"
# (sold/withdrawn). The threshold is in days — and not "absent from latest scan" —
# to tolerate temporary portal blocks: a 403 lasting a few hours must not make
# half the database vanish. If the listing reappears, the scan automatically
# brings it back to "active".
GONE_AFTER_DAYS = 7

# Immobiliare exposes floor in structured form ("T" = ground, "S" =
# basement): must be translated into text, otherwise it escapes keyword filtering.
FLOOR_AS_TEXT = {
    "t": "piano terra",
    "pt": "piano terra",
    "s": "seminterrato",
    "sm": "seminterrato",
}

_scan_lock = threading.Lock()
scan_state = {
    "running": False,
    "last_started_at": None,
    "last_finished_at": None,
    "last_summary": "",
}


def run_scan(profile_id: int | None = None, manual: bool = False) -> dict:
    """Executes the scan of active profiles (or just one).
    Thread-safe: only one scan running at any given time.

    `manual=True` marks a scan the user explicitly asked for ("Scan now"),
    which bypasses the global `scanning_paused` switch: the pause is meant to
    stop the *scheduler* from touching the portals on its own, not to veto an
    explicit request. Scheduled runs call this with the default `manual=False`."""
    if not manual and load_settings().get("scanning_paused"):
        logger.info("Automatic scan skipped: scanning is paused")
        return {"status": "paused"}
    if not _scan_lock.acquire(blocking=False):
        return {"status": "already_running"}
    scan_state["running"] = True
    scan_state["last_started_at"] = datetime.now(UTC).isoformat()
    summary = {
        "new": 0,
        "updated": 0,
        "filtered": 0,
        "price_changes": 0,
        "gone": 0,
        "notified": 0,
        "health_alerts": 0,
        "blocked_portals": [],
        "errors": [],
    }
    try:
        settings = load_settings()
        # opt-in: refresh a stale/missing DataDome cookie in a local browser
        # before the scrapers build their sessions, so a scheduled scan starts
        # with a live cookie instead of one that expired since last time.
        # Best-effort and lazily imported (Playwright is optional); a failure
        # here must never stop the scan, so settings are simply re-read.
        from . import cookie_harvester

        if cookie_harvester.maybe_auto_refresh(settings):
            settings = load_settings()
        db = SessionLocal()
        try:
            query = select(SearchProfile).where(SearchProfile.is_active.is_(True))
            if profile_id:
                query = select(SearchProfile).where(SearchProfile.id == profile_id)
            for profile in list(db.scalars(query)):
                try:
                    _scan_profile(db, profile, settings, summary)
                except Exception as e:
                    # a broken profile must not prevent scanning the others
                    db.rollback()
                    logger.exception("Profile '%s' failed", profile.name)
                    summary["errors"].append(f"{profile.name}: {e}")
                    # an unhandled exception is a failure like any other:
                    # _scan_profile never got to record it, so record it here
                    # or the health streak would silently reset to zero
                    profile.last_run_at = datetime.now(UTC)
                    profile.last_run_status = "error"
                    profile.last_run_detail = str(e)[:300]
                _update_profile_health(profile, settings, summary)
                db.commit()
            # only on full scans: scanning a single profile says nothing
            # about properties belonging to other profiles. And only on
            # *clean* full scans: the day-based GONE_AFTER_DAYS threshold
            # absorbs a block lasting hours, but after weeks with the PC off
            # every property is already past the cutoff, so a single blocked
            # startup scan would mark the whole dashboard "gone" and stamp
            # fake gone_at dates into the days-on-market statistics. A stale
            # card until the next clean scan is the cheaper mistake.
            if profile_id is None:
                if summary["blocked_portals"] or summary["errors"]:
                    logger.info(
                        "skipping 'gone' marking: %d blocked portal(s), %d error(s) this scan",
                        len(summary["blocked_portals"]),
                        len(summary["errors"]),
                    )
                else:
                    summary["gone"] = _mark_vanished_properties(db)
                    db.commit()
                # Record today's median €/sqm for the trend charts. Idempotent
                # (one per day) and fail-open, so it is safe to call on every
                # full scan regardless of whether this one was clean.
                pricing_stats.maybe_snapshot(db)
        finally:
            db.close()
    except Exception as e:
        logger.exception("Scan failed")
        summary["errors"].append(str(e))
    finally:
        scan_state["running"] = False
        scan_state["last_finished_at"] = datetime.now(UTC).isoformat()
        scan_state["last_summary"] = (
            f"{summary['new']} new, {summary['updated']} updated, "
            f"{summary['filtered']} filtered, {summary['price_changes']} price changes"
        )
        _scan_lock.release()
    return {"status": "done", **summary}


def _mark_vanished_properties(db) -> int:
    """Marks "gone" those properties that no scan has seen for GONE_AFTER_DAYS
    days: almost always means sold or withdrawn from the market."""
    cutoff = datetime.now(UTC) - timedelta(days=GONE_AFTER_DAYS)
    count = 0
    query = select(Property).where(Property.status.in_(("active", "filtered")))
    for prop in db.scalars(query):
        last_seen = prop.last_seen_at
        if last_seen.tzinfo is None:
            # SQLite returns naive datetime: they were saved in UTC
            last_seen = last_seen.replace(tzinfo=UTC)
        if last_seen < cutoff:
            prop.status = "gone"
            # the listing disappeared when it was last seen, not today:
            # dating it "now" would inflate every days-on-market statistic
            # by GONE_AFTER_DAYS
            prop.gone_at = last_seen
            count += 1
    if count:
        logger.info("%d properties not seen for %d days marked as 'gone'", count, GONE_AFTER_DAYS)
    return count


def _update_profile_health(profile: SearchProfile, settings: dict, summary: dict) -> None:
    """Tracks the failure streak of a profile and alerts when it crosses the
    threshold, then announces the recovery.

    A broken scraper fails silently: it produces no listings, hence no
    notifications, which looks exactly like a quiet market. Nothing surfaced
    the `blocked`/`error` status outside the dashboard, so an outage could
    last days unnoticed. Alerting on a *streak* rather than a single failure
    is what makes the alert trustworthy: transient DataDome 403s are routine.
    """
    threshold = int(settings.get("health_alert_after_failures") or 0)
    # same routing as listing notifications: a profile that only wants email
    # must not have its outage announced on Telegram — and a muted one ([])
    # stays silent here too, outage included: "no notifications" means no
    # notifications. The streak is still counted, so the dashboard shows it.
    channels = notifier.profile_channels(profile.notify_channels)
    muted = channels is not None and not channels
    failures = profile.consecutive_failures or 0

    if profile.last_run_status in ("blocked", "error"):
        failures += 1
        profile.consecutive_failures = failures
        if muted or threshold <= 0 or failures < threshold or profile.health_alert_sent:
            return
        # the flag means "the user was actually told", so it is set only on a
        # delivered message: when no channel is configured broadcast() returns
        # False and the next scan retries instead of swallowing the outage
        if notifier.notify_scraper_failure(profile, failures, channels):
            profile.health_alert_sent = True
            summary["health_alerts"] += 1
        return

    if profile.health_alert_sent:
        notifier.notify_scraper_recovered(profile, failures, channels)
        summary["health_alerts"] += 1
    profile.consecutive_failures = 0
    profile.health_alert_sent = False


def _texts_for_filter(raw, prop: Property) -> list[str]:
    floors = [raw.floor or "", prop.floor or ""]
    floor_texts = [FLOOR_AS_TEXT.get(f.strip().lower(), "") for f in floors]
    return [raw.title, raw.description, prop.title, *floors, *floor_texts]


def _scan_profile(db, profile: SearchProfile, settings: dict, summary: dict) -> None:
    logger.info("Scanning profile '%s' (%s)", profile.name, profile.portal)
    # `last_run_at` alone is not a safe proxy for "first scan": a blocked/error
    # attempt with zero listings still stamps it further down, but never
    # builds a baseline, so `baseline_done` is what actually gates silence.
    is_first_run = not profile.baseline_done

    scraper = get_scraper(profile.portal)
    scraper.delay_seconds = float(settings.get("request_delay_seconds", 6.0))
    scraper.max_pages = int(settings.get("max_pages_per_search", 10))

    result = scraper.scrape(profile.search_url)
    profile.last_run_at = datetime.now(UTC)

    if result.blocked:
        profile.last_run_status = "blocked"
        profile.last_run_detail = "Portal temporarily blocked (anti-bot). Will retry on next scan."
        summary["blocked_portals"].append(profile.portal)
        if not result.listings:
            return
    elif result.error and not result.listings:
        profile.last_run_status = "error"
        profile.last_run_detail = result.error[:300]
        summary["errors"].append(result.error)
        return

    # profile keywords ADD to global keywords (the UI presents them as "extra"):
    # a profile must never lose base protection just because it added its own
    keywords = list(settings.get("excluded_keywords", []))
    keywords += [k for k in parse_keywords_csv(profile.excluded_keywords) if k not in keywords]

    new_properties: list[Property] = []
    price_drops: list[tuple[Property, float, float]] = []
    # (property, previous status) pairs that came back to life this scan:
    # "filtered" whose keyword no longer applies, "gone" that reappeared on
    # the portal. Without their own notification the transition was applied
    # silently — a returned listing is exactly as actionable as a new one.
    reactivated: list[tuple[Property, str]] = []

    for raw in result.listings:
        prop, is_new, price_changed = upsert_listing(db, raw, profile_id=profile.id)

        if prop.status in ("hidden", "sold"):
            # manually hidden, or confirmed sold, by the user: data is updated
            # (upsert already done) but the property must never become visible
            # again nor generate notifications. Both are user choices a scan
            # never reverts (invariant 5); a "sold" ad often stays online for
            # weeks as a "VENDUTO" re-post, so re-finding it is expected.
            continue

        kw = find_excluded_keyword(_texts_for_filter(raw, prop), keywords)
        if kw:
            if prop.status != "filtered":
                prop.status = "filtered"
                prop.filtered_reason = kw
                summary["filtered"] += 1
            continue

        if prop.status in ("filtered", "gone"):
            # "filtered": keyword no longer present (or user removed it);
            # "gone": listing reappeared on portal.
            # "hidden" instead NEVER reactivates: it is a user choice.
            reactivated.append((prop, prop.status))
            prop.status = "active"
            prop.filtered_reason = ""
            # back on the market: the previous "gone" date is void, otherwise
            # days-on-market would be measured against a listing that is
            # demonstrably still for sale
            prop.gone_at = None

        if is_new:
            summary["new"] += 1
            new_properties.append(prop)
        else:
            summary["updated"] += 1

        if price_changed and prop.price_history:
            # price_changed=True ensures that the last history row is the
            # variation just recorded (see upsert_listing)
            summary["price_changes"] += 1
            last = prop.price_history[-1]
            price_drops.append((prop, last.old_price or 0.0, last.new_price))

    profile.last_run_status = "blocked" if result.blocked else "ok"
    if not result.blocked:
        detail = (
            f"{len(result.listings)} listings across {result.pages_fetched} pages "
            f"(strategy: {result.strategy_used or 'N/A'})"
        )
        if is_first_run:
            detail += " — first scan: notifications suppressed"
        profile.last_run_detail = detail

    if is_first_run:
        profile.baseline_done = True
        logger.info(
            "Profile '%s': first scan, %d properties acquired without notifications",
            profile.name,
            len(new_properties),
        )
        return

    # per-profile channel routing: None = all enabled channels, [] = muted
    channels = notifier.profile_channels(profile.notify_channels)
    if channels is not None and not channels:
        # a muted search still fills the dashboard, it just never pings: bail
        # out before the (otherwise pointless) scoring pass and the broadcasts
        return
    # Deal Score for the new listings, so an undervalued one is flagged in the
    # notification itself (market position must be computed first — it feeds it).
    if new_properties:
        pricing_stats.annotate_market_position(db, new_properties)
        deal_score.annotate_deal_scores(db, new_properties)
    summary["notified"] += _dispatch_notifications(
        new_properties, price_drops, reactivated, channels
    )


def _dispatch_notifications(
    new_properties: list[Property],
    price_drops: list[tuple[Property, float, float]],
    reactivated: list[tuple[Property, str]] | None = None,
    channels: list[str] | None = None,
) -> int:
    """Dispatches notifications, capped to avoid flooding the channels.

    Every capped list announces its own overflow ("… and N more"): silently
    dropping the tail would make a busy scan under-report exactly when the
    most is happening."""
    sent = 0
    for prop in new_properties[:MAX_NOTIFICATIONS_PER_SCAN]:
        if notifier.notify_new_property(prop, channels):
            sent += 1

    remaining = len(new_properties) - MAX_NOTIFICATIONS_PER_SCAN
    if remaining > 0:
        notifier.broadcast(
            f"… and <b>{remaining}</b> more new properties. Open the dashboard to see them all.",
            channels,
        )

    for prop, old_price, new_price in price_drops[:MAX_NOTIFICATIONS_PER_SCAN]:
        if notifier.notify_price_drop(prop, old_price, new_price, channels):
            sent += 1
    remaining = len(price_drops) - MAX_NOTIFICATIONS_PER_SCAN
    if remaining > 0:
        notifier.broadcast(
            f"… and <b>{remaining}</b> more price changes. Open the dashboard to see them all.",
            channels,
        )

    for prop, previous in (reactivated or [])[:MAX_NOTIFICATIONS_PER_SCAN]:
        if notifier.notify_property_reactivated(prop, previous, channels):
            sent += 1
    remaining = len(reactivated or []) - MAX_NOTIFICATIONS_PER_SCAN
    if remaining > 0:
        notifier.broadcast(
            f"… and <b>{remaining}</b> more properties back on the market. "
            "Open the dashboard to see them all.",
            channels,
        )
    return sent
