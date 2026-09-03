"""Scan Orchestrator: executes active search profiles, normalizes,
deduplicates, filters by keywords, and sends Telegram notifications."""

import logging
import threading
import typing
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import partial

from sqlalchemy import select

from ..config import SECRET_SETTINGS, load_settings
from ..database import SessionLocal
from ..models import Listing, ListingProfile, Property, SearchProfile
from ..scrapers import get_scraper, transport_policy
from ..scrapers.base import KnownListing, RawListing, ScrapeResult, listing_key, merge_scrapes
from . import (
    deal_score,
    geo_filter,
    geo_reference,
    geocoder,
    notifier,
    pricing_stats,
    scraper_health,
)
from .deduplicator import upsert_listing
from .filter_engine import find_excluded_keyword, parse_keywords_csv
from .search_builder import MAX_SEARCH_PARTS, parse_search_url, segment_search, zone_names
from .timeutils import as_utc

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
    "r": "piano rialzato",
    "pr": "piano rialzato",
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

# ---------------------------------------------------------------------------
# What a scan is doing while it runs, and what it did once it is over
# ---------------------------------------------------------------------------
#
# A scan is the longest thing this app does and used to be the only one that
# reported nothing until it was finished: `scan_state` above is a flag and a
# sentence written at the end, so for several minutes the dashboard could say
# exactly one word. The app already does this properly elsewhere — the
# availability check keeps `_prop_check_progress` and drives a real bar off it —
# and the shape here is deliberately that one: a module-level dict written by
# the scanning threads, copied out on read by whoever polls, and never a database
# write per page. Threads, plural, since the portals are read at the same time as
# each other: `_SearchProgress` is how one slot still only ever holds one
# search's facts.
#
# Two things, because "is it working?" and "did it work?" are different
# questions asked at different moments. The progress dict answers the first and
# exists only while a scan runs; the journal answers the second and outlives it.

_progress_lock = threading.Lock()

# The empty state, and the shape of every reply. `total_pages` is `None`
# whenever the portal did not declare one, and that is load-bearing: only a
# real total may be drawn as a proportion, and a count that rises with no
# percentage is the honest rendering of every path that has none to give.
_IDLE_PROGRESS: dict = {
    "active": False,
    "phase": "idle",
    "detail": "",
    "profile": "",
    "profile_index": 0,
    "profile_total": 0,
    "portal": "",
    # Which narrower search of a split one this is, and how many there are.
    # Both 0 for the ordinary case of a search that ran as one, which is what
    # keeps "part 3 of 7" off every screen that has no parts to report.
    "part": 0,
    "part_total": 0,
    "page": 0,
    "total_pages": None,
    "listings": 0,
    "total_listings": None,
    "transport": "",
    "waiting_seconds": 0.0,
}
_scan_progress: dict = dict(_IDLE_PROGRESS)

# One entry per profile per scan, newest last. Enough to cover the last handful
# of scans across a few searches, which is the span "did last night's run work?"
# actually needs. It lives in memory with the progress dict rather than in the
# database: a scan writes one entry per profile, and the point of the precedent
# being followed is that observability owns no schema and no transaction.
MAX_JOURNAL_ENTRIES = 40
_journal: deque[dict] = deque(maxlen=MAX_JOURNAL_ENTRIES)

# A credential nobody would issue is not worth mangling a sentence for: below
# this length a blanket replace would shred the text it was meant to protect,
# and every secret this app stores — a cookie, a bot token, an API key — is far
# longer than it.
MIN_REDACTED_SECRET = 6


def get_scan_progress() -> dict:
    """Snapshot of the scan in flight, for the dashboard's poll."""
    with _progress_lock:
        return dict(_scan_progress)


def get_scan_journal() -> list[dict]:
    """The recent per-profile scan entries, newest first.

    Deliberately not `app.log`. `/api/logs/tail` already tails the Python
    logger, which is the right tool for diagnosing a crash and the wrong one for
    "is my search working?" — module names, levels and tracebacks are an
    engineer's artifact. These entries are written for the person who uses the
    app: which search, on which portal, how many pages, how many listings, how
    it ended and why it stopped.
    """
    with _progress_lock:
        return list(reversed(_journal))


def _progress_sentence(state: dict) -> str:
    """One line saying what is happening now, from the facts already recorded."""
    who = f"{state['profile']} on {state['portal']}" if state["profile"] else ""
    if who and state["part_total"]:
        # A split search makes the same profile fetch the same-looking page
        # several times over; without this the watcher sees the page count reset
        # to 1 twice and reads it as a scan that restarted.
        who += f", part {state['part']} of {state['part_total']}"
    phase = state["phase"]
    if phase == "waiting":
        # The important one. `request_delay_seconds` defaults to 6 and is spent
        # between every page, so most of a scan's wall clock is this pause —
        # unnamed, the app's most deliberate behaviour reads as a hang.
        return (
            f"{who}: pausing {state['waiting_seconds']:g}s before the next page, "
            "which is what keeps the portal answering"
        )
    if phase == "fetching":
        page = f"page {state['page'] or 1}"
        if state["total_pages"]:
            page += f" of {state['total_pages']}"
        return f"{who}: reading {page}"
    if phase == "saving":
        return f"{who}: saving what came back"
    if phase == "locating":
        return "Placing the new listings on the map"
    if phase == "starting":
        return f"Starting {who}" if who else "Starting the scan"
    return ""


def _set_progress(*, reset: bool = False, **facts) -> None:
    """Record what the scan is doing now.

    Never raises — every write to the dict goes through here for that reason
    alone. A scan that failed *because* it was reporting on itself would be a
    strictly worse product than one that says nothing, so this follows
    `scraper_health.record_scan`'s rule exactly: swallow, log, carry on. The
    lock is held for the update alone and never across a request.
    """
    try:
        with _progress_lock:
            if reset:
                _scan_progress.update(_IDLE_PROGRESS)
            _scan_progress.update(facts)
            _scan_progress["detail"] = _progress_sentence(_scan_progress)
    except Exception:
        logger.exception("scan: progress could not be recorded")


class _SearchProgress:
    """One search's own progress, published whole into the dict above.

    Two hosts are read at the same time now, and there is one slot to say so in.
    A write carrying only what changed would leave the rest of the sentence
    belonging to the other portal — "Roma on idealista: reading page 2 of 4",
    where the 4 was Immobiliare's page count — and a number attributed to the
    wrong search is worse than no number at all.

    So each search keeps its own state and publishes it complete: whichever host
    wrote last, what a watcher reads is one portal's honest snapshot instead of
    a blend of two. One instance per search, written only by the thread fetching
    it and by the writer thread once that has finished, so it needs no lock of
    its own — the shared dict's is inside `_set_progress`.
    """

    def __init__(self, search: "_SearchToRun") -> None:
        self.state: dict = dict(_IDLE_PROGRESS)
        self.set(
            active=True,
            phase="starting",
            profile=search.name,
            portal=search.portal,
            profile_index=search.index,
            profile_total=search.total,
        )

    def set(self, **facts) -> None:
        self.state.update(facts)
        _set_progress(**self.state)

    def scraped(self, scraper, settings: dict, **facts) -> None:
        """The scrapers' end of the same dict: their page facts, plus the transport.

        The transport is re-read on every call rather than once per profile
        because a fully blocked local ladder escalates to the paid API
        *mid-scrape* (`base.fetch`), and watching that happen is exactly what a
        user wants to see when a scan starts going wrong.
        """
        try:
            facts["transport"] = transport_policy.transport_used(scraper, settings)
        except Exception:
            logger.exception("scan: the transport in use could not be named")
        self.set(**facts)


def _begin_scan() -> None:
    _set_progress(reset=True, active=True, phase="starting")


def _end_scan() -> None:
    """Back to silence. Leaving the last page on screen would say a scan is
    still reading it, which is exactly the kind of stale number this replaces."""
    _set_progress(reset=True)


def _without_secrets(text: str, settings: dict) -> str:
    """Scrub every stored credential out of text written for the user to read.

    A search URL can carry an API key and an error message copies whatever URL
    it failed on, so the journal is one copy away from publishing a secret on a
    screen. Redacting the *values* rather than looking for key-shaped strings is
    what makes that hold for a message nobody has thought of yet.
    """
    for key in SECRET_SETTINGS:
        value = settings.get(key)
        if isinstance(value, str) and len(value.strip()) >= MIN_REDACTED_SECRET:
            text = text.replace(value.strip(), "***")
    return text


def _stop_reason(result: ScrapeResult | None) -> str:
    """Why this search stopped when it did, in the user's terms."""
    if result is None:
        return "the search could not be run at all"
    if result.blocked:
        return "the portal refused the request"
    if result.error:
        return "the search ran into an error"
    if result.stopped_early:
        return "a whole page held nothing this search had not already seen"
    if result.truncated:
        pages = "page" if result.page_limit == 1 else "pages"
        return f"the page limit of {result.page_limit} {pages}"
    if result.parts:
        return f"every one of the {result.parts} parts was read to the end"
    if not result.listings:
        return "the portal had nothing to list"
    return "the portal had nothing more to give"


def _record_journal(
    profile: SearchProfile,
    fetched: "_Fetched",
    result: ScrapeResult | None,
    settings: dict,
) -> None:
    """Close one profile's line in the journal. Never raises into the scan.

    Written after the profile's own status and detail have settled, which is
    why a crashed profile still earns an entry: `run_scan` has stamped `error`
    on it by then, and a search that blew up is precisely one the user wants to
    find afterwards.

    The transport comes off this search's own progress rather than off the
    shared dict, which now holds whichever host reported last: reading it there
    would file Idealista's transport under an Immobiliare search whenever the
    two overlapped.
    """
    try:
        started_at = fetched.started_at
        transport = fetched.progress.state.get("transport") or ""
        _journal.append(
            {
                "profile_id": profile.id,
                "profile": profile.name,
                "portal": profile.portal,
                "started_at": started_at.isoformat(),
                "finished_at": datetime.now(UTC).isoformat(),
                "pages": result.pages_fetched if result else 0,
                "listings": len(result.listings) if result else 0,
                # G.5's word, taken from the profile rather than recomputed, so
                # the journal and the search's own line can never disagree.
                "outcome": profile.last_run_status or "error",
                "detail": _without_secrets(profile.last_run_detail or "", settings),
                "transport": transport,
                "stopped_because": _stop_reason(result),
                # Which kind of scan this was, taken from what was asked for
                # rather than from how it ended: a quick scan that happened to
                # read every page is still the scan the user was given, and the
                # line beside it already says where it stopped and why.
                "mode": "full" if fetched.search.seen is None else "quick",
            }
        )
    except Exception:
        logger.exception("scan: journal entry could not be recorded")


@dataclass(frozen=True)
class _SearchToRun:
    """What reading one search off a portal needs, copied out of the ORM object.

    A `SearchProfile` belongs to the session that loaded it, and the writing
    thread commits between profiles — which expires every instance, so an
    attribute read from a fetching thread would send a second thread back into
    a `Session` that is not its own. Copying the handful of fields the portal
    half actually uses is what makes the two halves independent, and it is also
    the line between them: nothing on the fetching side can touch the database,
    because it holds nothing that could.
    """

    id: int
    index: int
    total: int
    name: str
    portal: str
    search_url: str
    consecutive_failures: int
    # Every ad this search already holds, as (listing key, price) pairs — or
    # `None`, which means "read to the cap whatever you recognise": a full
    # sweep. Copied out with the rest and for the same reason. Recognising a
    # page is a database question, and the thread that fetches the page holds
    # nothing it could ask one with.
    seen: frozenset[tuple[str, float | None]] | None = None


@dataclass
class _Fetched:
    """One search, as it came back off its portal. No database in sight."""

    search: _SearchToRun
    progress: _SearchProgress
    started_at: datetime
    scraper: typing.Any = None
    result: ScrapeResult | None = None
    # Whatever the fetch raised, carried rather than thrown: a portal that blew
    # up on one host must not cancel the other, so the failure travels back to
    # the writing thread as a value and is raised there, inside the per-profile
    # `try` that has always contained it.
    error: Exception | None = None


def _already_seen(db, profile_id: int) -> frozenset[tuple[str, float | None]]:
    """Every ad this search has brought back before, and what it cost then.

    Read here, on the thread that owns the session, and handed to the fetching
    thread as a frozen value — the same rule `_SearchToRun` exists to enforce.

    The price is half the key on purpose. An ad this search already holds *at a
    different price* is news: it is exactly what `upsert_listing` reports as a
    price change and what the user is notified about. So a page carrying one is
    not a page with nothing new on it, and the walk goes on.
    """
    return frozenset(
        (listing_key(url), price)
        for url, price in db.execute(
            select(Listing.url, Listing.price)
            .join(ListingProfile, ListingProfile.listing_id == Listing.id)
            .where(ListingProfile.profile_id == profile_id)
        )
    )


def _sweeps_to_the_cap(profile: SearchProfile, settings: dict, full_sweep: bool) -> bool:
    """Does this search read every page it is allowed to, or stop as soon as it
    stops recognising anything new?

    The early stop is a shortcut and never the only path, because it cannot see
    a price change on page 6. So a full sweep runs: when the user asks for one;
    on the **first scan of a search**, where `baseline_done` is already the flag
    for exactly this (invariant 3) and where there is nothing to recognise
    anyway; and once every `full_sweep_every_days` after that, counted from the
    last sweep that got through. Either the switch or a period of zero turns the
    shortcut off entirely, which is the setting for someone who would rather
    spend the requests.
    """
    if full_sweep or not settings.get("stop_when_nothing_new", True):
        return True
    if not profile.baseline_done:
        return True
    every = int(settings.get("full_sweep_every_days", 7) or 0)
    if every <= 0:
        return True
    last = profile.last_full_sweep_at
    return last is None or datetime.now(UTC) - as_utc(last) >= timedelta(days=every)


def _recognises(seen: frozenset[tuple[str, float | None]] | None) -> KnownListing | None:
    """The scrape's end of `_already_seen`: a predicate over one listing.

    `None` for a full sweep, which is what `BaseScraper.scrape` reads as "walk
    every page you are allowed to" — the behaviour that existed before any of
    this, unchanged.
    """
    if seen is None:
        return None

    def known(listing: RawListing) -> bool:
        return (listing_key(listing.url), listing.price) in seen

    return known


def _searches_to_run(
    db, profiles: list[SearchProfile], settings: dict, full_sweep: bool = False
) -> list[_SearchToRun]:
    return [
        _SearchToRun(
            id=profile.id,
            index=index,
            total=len(profiles),
            name=profile.name,
            portal=profile.portal,
            search_url=profile.search_url,
            consecutive_failures=profile.consecutive_failures or 0,
            seen=(
                None
                if _sweeps_to_the_cap(profile, settings, full_sweep)
                else _already_seen(db, profile.id)
            ),
        )
        for index, profile in enumerate(profiles, start=1)
    ]


def _fetch_searches(searches: list[_SearchToRun], settings: dict) -> typing.Iterator[_Fetched]:
    """Every search, read off its portal — the hosts at the same time.

    Every delay in this app is owed to *one* host: `polite_sleep` spends six
    seconds so that Immobiliare is not asked too often, and Idealista's own
    floor exists for Idealista — though the scan does not currently apply that
    floor, which is a finding of its own (`docs/roadmap.md`) and not this
    function's to fix. Read strictly one after another, those seconds were
    also spent not talking to the other portal, so most of a scan was the app
    waiting for a host it was not addressing. One worker per host spends them
    where they are owed and nowhere else: the rate at either portal is exactly
    what it was, and a two-portal scan costs the longer half instead of the sum.

    The shape is deliberate on all three counts:

    - **per host, not per profile.** One single-worker pool per portal, so two
      Immobiliare searches stay as serial with respect to each other as they
      have always been. The concurrency is between hosts and nowhere else.
    - **fetching is concurrent, writing is not.** This yields; the caller
      writes. Nothing here holds a session, and `_SearchToRun` is what
      guarantees it.
    - **in the order they were asked for**, not the order they finish. The
      writes are what the database ends up holding, so their order cannot
      depend on which portal happened to answer first — that is the difference
      between a performance switch and a behaviour switch.
    """
    if len({search.portal for search in searches}) < 2 or not settings.get(
        "scan_portals_concurrently", True
    ):
        # One host, or the user turned it off: no pool, no threads, and the
        # path the scan took before this existed, unchanged.
        for search in searches:
            yield _fetch_search(search, settings)
        return

    pools: dict[str, ThreadPoolExecutor] = {}
    try:
        pending: list[Future[_Fetched]] = []
        for search in searches:
            pool = pools.get(search.portal)
            if pool is None:
                pool = pools[search.portal] = ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix=f"scan-{search.portal}"
                )
            pending.append(pool.submit(_fetch_search, search, settings))
        for future in pending:
            yield future.result()
    finally:
        for pool in pools.values():
            pool.shutdown(wait=True, cancel_futures=True)


def _fetch_search(search: _SearchToRun, settings: dict) -> _Fetched:
    """Read one search off its portal. Never raises, never touches the database.

    A scraper instance is built *here*, per search, and never shared: it holds a
    `curl_cffi` session, an impersonation index, the proxy it is exiting
    through and a warmed flag, and `_rotate_session` mutates all four. One
    instance seen by two threads would rotate under the other's feet.
    """
    logger.info("Scanning profile '%s' (%s)", search.name, search.portal)
    fetched = _Fetched(
        search=search, progress=_SearchProgress(search), started_at=datetime.now(UTC)
    )
    try:
        scraper = get_scraper(search.portal)
        scraper.delay_seconds = float(settings.get("request_delay_seconds", 6.0))
        scraper.max_pages = int(settings.get("max_pages_per_search", 10))
        # health-driven transport choice: with scrape_api_mode=
        # "fallback" the scan starts on the free local path and only spends the
        # paid API when this profile's failure streak says local is down; the
        # default "always" keeps a configured key routing everything as before.
        decision = transport_policy.decide(search.consecutive_failures, settings)
        scraper.use_scrape_api = decision.start_on_api
        # live reporting, for the minutes this next line takes
        scraper.on_progress = partial(fetched.progress.scraped, scraper, settings)
        fetched.scraper = scraper

        result = scraper.scrape(search.search_url, known=_recognises(search.seen))
        if result.truncated:
            # More listings than one search can carry. Ask the portal again in
            # narrower pieces rather than report the first ten pages of it.
            result = _split_the_search(scraper, search, result, fetched.progress, settings)
        fetched.result = result
    except Exception as e:
        fetched.error = e
    return fetched


def run_scan(profile_id: int | None = None, manual: bool = False, full_sweep: bool = False) -> dict:
    """Executes the scan of active profiles (or just one).
    Thread-safe: only one scan running at any given time.

    `manual=True` marks a scan the user explicitly asked for ("Scan now"),
    which bypasses the global `scanning_paused` switch: the pause is meant to
    stop the *scheduler* from touching the portals on its own, not to veto an
    explicit request. Scheduled runs call this with the default `manual=False`.

    `full_sweep=True` is the other explicit request: read every page the cap
    allows, whatever is already recognised. It is the on-demand half of the rule
    that the early stop is a shortcut and never the only path — the scheduled
    half is `full_sweep_every_days`, which `_sweeps_to_the_cap` applies per
    search without needing a job of its own."""
    if not manual and load_settings().get("scanning_paused"):
        logger.info("Automatic scan skipped: scanning is paused")
        return {"status": "paused"}
    if not _scan_lock.acquire(blocking=False):
        return {"status": "already_running"}
    scan_state["running"] = True
    started_at = datetime.now(UTC)
    scan_state["last_started_at"] = started_at.isoformat()
    _begin_scan()
    summary = {
        "new": 0,
        "updated": 0,
        "filtered": 0,
        "price_changes": 0,
        "gone": 0,
        "notified": 0,
        "health_alerts": 0,
        # how many of the listings that came back were outside the area their
        # search asked for. Counted, never dropped — see _outside_requested_area.
        "outside_area": 0,
        # how many searches stopped at the page limit with listings still to
        # collect. A scan that cannot say this cannot claim it found everything.
        "truncated": 0,
        # how many of the listings this scan touched got a map pin out of it,
        # and how many of those are a district centre rather than an address.
        "located": 0,
        "located_approximate": 0,
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
            profiles = list(db.scalars(query))
            by_id = {profile.id: profile for profile in profiles}
            # The portals are read on their own threads; everything below this
            # loop is this one. `_fetch_searches` hands the results back in the
            # order the profiles were listed, so what the database ends up
            # holding does not depend on which host answered first.
            searches = _searches_to_run(db, profiles, settings, full_sweep)
            for fetched in _fetch_searches(searches, settings):
                profile = by_id[fetched.search.id]
                result = fetched.result
                try:
                    if fetched.error is not None:
                        raise fetched.error
                    result = _record_scrape(db, profile, fetched, settings, summary)
                except Exception as e:
                    # a broken profile must not prevent scanning the others
                    db.rollback()
                    logger.exception("Profile '%s' failed", profile.name)
                    summary["errors"].append(f"{profile.name}: {e}")
                    # an unhandled exception is a failure like any other:
                    # nothing got to record it, so record it here or the health
                    # streak would silently reset to zero
                    profile.last_run_at = datetime.now(UTC)
                    profile.last_run_status = "error"
                    profile.last_run_detail = str(e)[:300]
                # after the branch above, so the entry reads the status this
                # profile actually ended on, crash included
                _record_journal(profile, fetched, result, settings)
                _update_profile_health(profile, settings, summary)
                db.commit()
            _locate_scanned_properties(db, settings, started_at, summary)
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
        _end_scan()
        scan_state["running"] = False
        scan_state["last_finished_at"] = datetime.now(UTC).isoformat()
        last_summary = (
            f"{summary['new']} new, {summary['updated']} updated, "
            f"{summary['filtered']} filtered, {summary['price_changes']} price changes"
        )
        if summary["truncated"]:
            # The one thing this line could not previously say: whether the
            # numbers in front of it are the whole answer. Which searches, and
            # of how many listings, is on each search's own line.
            searches = "search" if summary["truncated"] == 1 else "searches"
            last_summary += f" — {summary['truncated']} {searches} stopped at the page limit"
        scan_state["last_summary"] = last_summary
        _scan_lock.release()
    return {"status": "done", **summary}


def _locate_scanned_properties(db, settings: dict, started_at: datetime, summary: dict) -> None:
    """Give the listings this scan just touched a pin, before anyone asks.

    The first scan of a new search is the run where the map matters most and the
    run where it was emptiest: coordinates arrive only when the portal chooses to
    send them, and everything else waited for a person to find the "Find
    coordinates" maintenance button. So the scan does it, in the two halves the
    geocoder is built around — the free one always, the paced one on a budget.

    The candidates are the properties this scan saw and still cannot place,
    identified by `last_seen_at`: `upsert_listing` stamps it on every listing it
    writes, so "seen since the scan started" is exactly what this scan imported
    or refreshed, with no bookkeeping threaded through `_scan_profile`.

    Fail-open, twice over. A geocoding batch the user started by hand holds the
    lock and this one steps aside; anything else that goes wrong is logged and
    the scan finishes. A scan must never fail because a map pin could not be
    worked out.
    """
    _set_progress(phase="locating")
    ids = set(
        db.scalars(
            select(Property.id)
            .where(Property.latitude.is_(None))
            .where(Property.city != "")
            # naive, because that is how SQLite holds it: the ORM writes an
            # aware UTC value and the stored text carries no offset (timeutils).
            .where(Property.last_seen_at >= started_at.replace(tzinfo=None))
        )
    )
    if not ids:
        return
    try:
        offline = geocoder.resolve_offline(db, property_ids=ids)
        summary["located"] += offline["placed"]
        summary["located_approximate"] += offline["approximate"]
    except Exception:
        db.rollback()
        logger.exception("scan: offline coordinate resolution failed")

    if not settings.get("geocode_after_scan", True):
        return
    try:
        # `max_calls=-1` is the geocoder's own per-run cap, and the pacing and
        # cancel path inside it are untouched: this is the maintenance batch,
        # pointed at one scan's worth of properties.
        batch = geocoder.geocode_missing_properties(db, property_ids=ids)
        summary["located"] += batch["geocoded"]
        summary["located_approximate"] += batch["approximate"]
    except geocoder.GeocoderError:
        logger.info("scan: a geocoding batch is already running, skipping the post-scan sweep")
    except Exception:
        db.rollback()
        logger.exception("scan: post-scan geocoding failed")


def _mark_vanished_properties(db) -> int:
    """Marks "gone" those properties that no scan has seen for GONE_AFTER_DAYS
    days: almost always means sold or withdrawn from the market."""
    cutoff = datetime.now(UTC) - timedelta(days=GONE_AFTER_DAYS)
    count = 0
    query = select(Property).where(Property.status.in_(("active", "filtered")))
    for prop in db.scalars(query):
        # No None guard: `properties.last_seen_at` is NOT NULL in the schema
        # (default `utcnow`), so SQLite itself refuses a row without it.
        last_seen = as_utc(prop.last_seen_at)
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

    Only `blocked` and `error` count. `no_results` is an answer, so it clears
    the streak exactly as `ok` does — a search over a market that genuinely has
    nothing in it must not accumulate towards an outage alert.
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


@dataclass(frozen=True)
class RequestedArea:
    """What a monitored search asked the portal for, read back from its own URL.

    The search URL is the only statement of intent a scan has: nothing else on
    `SearchProfile` records a location. Parsing it back is therefore how "what
    was asked for" is known, and it is the same parser the builder form uses, so
    the two can never disagree about what a URL says.

    `circle` is the comune as the offline gazetteer knows it — a centroid and a
    size-scaled radius, the very area `is_plausible_coordinate` measures a pin
    against — so the area a scan is judged against and the area a pin is
    believed in are one definition, not two.

    `drawn` is the other kind of area entirely: the geometry an Immobiliare map
    URL states outright — a hand-drawn perimeter, an isochrone the portal
    computed, or a centre and a radius. Where the comune circle is a gazetteer
    guess at the shape of a town, this *is* the boundary the user asked for, so
    it is kept apart rather than merged into `circle` and is the evidence
    `_outside_requested_area` reaches for first.
    """

    city: str = ""
    zones: tuple[str, ...] = ()
    zone_ids: tuple[str, ...] = ()
    circle: geo_filter.Circle | None = None
    drawn: tuple[geo_filter.Area, ...] = ()


def requested_area(search_url: str) -> RequestedArea:
    params = parse_search_url(search_url)
    city = (params.get("city") or "").strip()

    # A polygon and a radius are a union, not a contradiction: `point_in_any`
    # answers "inside any of these", which is the generous direction and so the
    # one that cannot invent a disagreement out of a URL carrying both.
    drawn: list[geo_filter.Area] = []
    if params.get("drawn_polygon"):
        perimeter: geo_filter.Perimeter = {"outer": list(params["drawn_polygon"])}
        drawn.append(perimeter)
    if params.get("drawn_circle"):
        drawn.append(params["drawn_circle"])

    return RequestedArea(
        city=city,
        zones=tuple(zone_names(params.get("zone") or "", params.get("zones"))),
        zone_ids=tuple(params.get("zone_ids") or ()),
        circle=geo_reference.city_search_area(city) if city else None,
        drawn=tuple(drawn),
    )


def _outside_requested_area(area: RequestedArea, raw: RawListing, prop: Property) -> bool | None:
    """Did this listing come back from outside what its search asked for?

    True = outside, False = inside, and **None = cannot tell** — the third
    answer is the one that matters. Asking a portal for a zone is not the same
    as getting one, so the result is checked here rather than trusted; but a
    check that guessed when it had nothing to go on would accuse the portal of
    a mistake the app cannot demonstrate, and the flag would stop meaning
    anything. Every branch below either proves a disagreement or declines to
    have an opinion.

    The evidence, strongest first:

    1. **the boundary the search drew.** A perimeter or a radius out of the
       URL's own map params, and the only piece of evidence here that is exact:
       the user drew it, or the portal computed it, and either way it is the
       question rather than an approximation of it. So it decides alone — a
       comune name or a district text cannot overrule a line on a map, and a
       perimeter deliberately drawn across a comune border would otherwise be
       reported as disagreeing with itself.
    2. **the comune, by name.** A listing whose city is a different comune is
       outside whatever the search asked for, zones or no zones.
    3. **the comune, by coordinates.** The pin against the comune's own circle,
       which is what catches a listing filed under the right city name and
       plainly somewhere else.
    4. **the zones, by name.** The requested zone names against the listing's
       own zone text, word-bound and accent-insensitive — `find_excluded_keyword`
       is exactly that matcher, and a second copy of it here would be a second
       set of rules for "does this text name this place".

    An exactly known area does not abolish the third answer. A listing the
    portal sent with no coordinates cannot be placed against a polygon at all,
    and "the boundary is exact" is not a licence to have an opinion about a
    listing that is not on the map: it falls through to the evidence below,
    which for a pure map URL names no comune and so answers None.

    Zone *ids* are deliberately absent from step 4. Immobiliare's `idMZona[]`
    values are opaque numbers the portal alone can resolve, and a listing's zone
    text can never match one, so a search that carries ids and no names is
    judged on the comune alone. Reading "no name matched" out of ids nobody can
    name would flag every listing of a perfectly good multi-zone search.
    """
    lat = raw.latitude if raw.latitude is not None else prop.latitude
    lng = raw.longitude if raw.longitude is not None else prop.longitude

    if area.drawn and lat is not None and lng is not None:
        return not geo_filter.point_in_any(lat, lng, area.drawn)

    if not area.city:
        # A search with no readable location asks for nothing this can check —
        # a URL from an unknown portal, or one whose location is an opaque id,
        # or a map URL whose geometry could not be read (search_builder logs
        # that one). A drawn area that placed nothing lands here too.
        return None

    city = (raw.city or prop.city or "").strip()
    placed = False

    if city:
        if not geo_reference.same_comune(city, area.city):
            return True
        placed = True
    if lat is not None and lng is not None and area.circle is not None:
        if not geo_filter.point_in_any(lat, lng, [area.circle]):
            return True
        placed = True

    if area.zones:
        zone_text = (raw.zone or prop.zone or "").strip()
        # The address is searched for a match but never counts as evidence on
        # its own: a street name that happens to carry the district is a bonus,
        # while "Via Roma, 9" says nothing about which district Via Roma is in.
        if find_excluded_keyword([zone_text, raw.address or prop.address], list(area.zones)):
            return False
        # A listing that names *some* district, and not one of the requested
        # ones, is the disagreement this exists to report. One that names no
        # district at all is not evidence of anything.
        return True if zone_text else None
    return False if placed else None


def _truncation_note(result: ScrapeResult) -> str:
    """What a search owes the user when the page limit cut it short.

    "N listings across 10 pages" is a sentence that sounds complete, and for a
    search with forty pages of results it was not: `max_pages_per_search`
    stopped it at ten and nothing said so. The note names the cap that did it
    and what to do about it, and it is deliberately absent from every search
    that fit — a truncation warning on a complete answer teaches the user to
    ignore the one that matters.
    """
    if not result.truncated:
        return ""
    pages = "page" if result.page_limit == 1 else "pages"
    note = f" — stopped at the page limit of {result.page_limit} {pages}"
    if result.total_listings is None and result.total_pages is None:
        # The HTML paths, where no portal publishes a total: all that is known
        # is that the last permitted page was full, so that is all it claims.
        return note + ", so the portal may have more"
    return note + ": raise it, or narrow the search"


def _split_note(result: ScrapeResult) -> str:
    """What a search that had to be run in parts owes the user.

    The other half of `_truncation_note`, and the reason this task exists: a
    search bigger than the page limit used to end in an apology, and now it can
    end in a fact — but only when the portal's own counts say the parts covered
    it. A split that fell short says so instead, beside the truncation notice it
    did not manage to remove.

    Deliberately no second number: `found` above already says how many listings
    came back, and a completeness claim carrying a slightly different total
    (duplicates across parts, a listing published between two requests) reads as
    an arithmetic error in the one sentence that has to be trusted.
    """
    if not result.parts:
        return ""
    if result.truncated:
        return f" (searched in {result.parts} parts, and still did not fit)"
    return f" — searched in {result.parts} parts, which between them covered the whole result set"


def _quick_scan_note(result: ScrapeResult) -> str:
    """What a search that stopped as soon as it recognised everything owes the user.

    The saving is real — a routine scan drops from ten page-fetches to two — and
    so is what it costs: the pages this walk never reached could hold a price
    change, and nothing here can say they do not. So the line says which of the
    two kinds of scan this was, for the same reason `_truncation_note` exists. A
    partial reading reported in the words of a complete one is the one sort of
    wrong the user has no way of detecting for themselves, and it is why a
    completeness claim is only ever made about a walk that was not cut short.
    """
    if not result.stopped_early:
        return ""
    pages = "page" if result.pages_fetched == 1 else "pages"
    return (
        f" — a quick scan: it stopped after {result.pages_fetched} {pages}, where nothing "
        "was new, so this is not a full reading of the search"
    )


def _parts_needed(result: ScrapeResult) -> int:
    """How many narrower searches this one would have to become to fit.

    Off the portal's own page count, so a search whose total was never declared
    is never split: without the portal's arithmetic there is nothing to size the
    split with, and — the half that matters more — nothing to check it against
    afterwards.
    """
    if result.total_pages is None or result.page_limit <= 0:
        return 0
    return -(-result.total_pages // result.page_limit)


def _parts_cover_the_whole(whole: ScrapeResult, parts: list[ScrapeResult]) -> bool:
    """Did the parts, between them, account for everything the portal declared?

    The check is the portal's arithmetic and not this app's: each part is
    counted by the same endpoint that counted the whole, and the counts have to
    add up. A partition that silently lost the 300,000-310,000 euro slice is
    worse than the truncation it replaced, because the truncation announced
    itself — so anything short of agreement leaves the truncation notice alone.

    The comparison is "at least", not "exactly", and the direction is the whole
    point. **A gap can only make the sum fall short**, which is the case being
    guarded against. Overlapping parts and a listing published between the two
    requests can only make it exceed, and neither loses anything. A listing
    *withdrawn* between them makes it fall short too and costs the completeness
    claim — a search reported as truncated when it was probably complete, which
    is the error worth making in this direction.
    """
    if whole.total_listings is None:
        return False
    totals = [part.total_listings for part in parts]
    if any(total is None for total in totals):
        return False
    return sum(total for total in totals if total is not None) >= whole.total_listings


def _split_the_search(
    scraper,
    search: _SearchToRun,
    whole: ScrapeResult,
    progress: _SearchProgress,
    settings: dict,
) -> ScrapeResult:
    """Run a truncated search again as several narrower ones, and merge them.

    Every exit before the parts run returns `whole` untouched, which is G.7's
    behaviour exactly: what was collected is kept and reported as truncated. The
    split is an improvement on that answer, never a replacement for it.

    **It does not recurse.** A part that is still too big keeps the truncation
    notice rather than being split again: the recursion has no natural floor —
    each level multiplies the requests, and requests are what get an IP blocked
    — and there is no depth at which a search is guaranteed to fit.
    """
    if not settings.get("split_large_searches", True):
        return whole
    needed = _parts_needed(whole)
    if needed < 2:
        return whole
    if needed > MAX_SEARCH_PARTS:
        # The ceiling is refused *here*, before a single extra request: a
        # search this big would not fit in `MAX_SEARCH_PARTS` parts either, so
        # spending them would buy a truncation notice at eight times the price.
        logger.info(
            "Profile '%s': %s pages would take %d parts, past the %d allowed — "
            "leaving the search truncated rather than spending the requests",
            search.name,
            whole.total_pages,
            needed,
            MAX_SEARCH_PARTS,
        )
        return whole
    urls = segment_search(search.search_url, search.portal, needed)
    if not urls:
        logger.info(
            "Profile '%s': no axis splits this search into %d parts that provably cover it",
            search.name,
            needed,
        )
        return whole

    logger.info(
        "Profile '%s': %s pages do not fit in %d — running it as %d narrower searches",
        search.name,
        whole.total_pages,
        whole.page_limit,
        len(urls),
    )
    parts: list[ScrapeResult] = []
    for index, url in enumerate(urls, start=1):
        # Reset what belonged to the previous part for the same reason a new
        # search starts from nothing: a page number carried over attributes one
        # part's progress to the next.
        progress.set(
            phase="starting",
            part=index,
            part_total=len(urls),
            page=0,
            total_pages=None,
            listings=0,
            total_listings=None,
        )
        # The parts are consecutive searches against one host, so they owe it
        # the same pause every page of one search owes it.
        scraper.polite_sleep()
        parts.append(scraper.scrape(url))

    merged = merge_scrapes([whole, *parts])
    merged.parts = len(urls)
    unfinished = [p for p in parts if p.truncated or p.outcome not in ("ok", "no_results")]
    if unfinished:
        # Blocked, errored, or still over the cap: each leaves listings this
        # scan did not see, so the notice stays. Checked before the totals,
        # because a part blocked half way through still declared the count it
        # read on its first page and would otherwise add up perfectly.
        logger.info(
            "Profile '%s': %d of the %d parts did not finish — keeping the truncation notice",
            search.name,
            len(unfinished),
            len(urls),
        )
        return merged
    if not _parts_cover_the_whole(whole, parts):
        logger.error(
            "Profile '%s': the %d parts declare %s results between them against the portal's "
            "%s for the whole search — the split is not provably total, so it is not reported "
            "as complete",
            search.name,
            len(urls),
            sum(p.total_listings or 0 for p in parts),
            whole.total_listings,
        )
        return merged
    merged.truncated_by = ""
    return merged


def _scan_profile(
    db, profile: SearchProfile, settings: dict, summary: dict, full_sweep: bool = False
) -> ScrapeResult:
    """One search, read and then recorded, both on this thread.

    The scan itself no longer goes through here — it reads the portals on their
    own threads and writes on one (`_fetch_searches` and `_record_scrape`
    below). This is the two halves back to back, which is what a caller holding
    a session and wanting one search scanned means by it.
    """
    fetched = _fetch_search(_searches_to_run(db, [profile], settings, full_sweep)[0], settings)
    if fetched.error is not None:
        raise fetched.error
    return _record_scrape(db, profile, fetched, settings, summary)


def _record_scrape(
    db, profile: SearchProfile, fetched: _Fetched, settings: dict, summary: dict
) -> ScrapeResult:
    """Write down what one search brought back, and what it established.

    Every database write a scan performs is here, and this runs on one thread:
    the portals are read at the same time as each other, but what came back is
    written down one search after another, in the order they were listed.
    Returns the scrape it recorded, so the caller can journal how it went
    without a second reading of anything.
    """
    result = fetched.result
    assert result is not None  # `_fetch_searches` yields an error or a result
    scraper = fetched.scraper
    # `last_run_at` alone is not a safe proxy for "first scan": a blocked/error
    # attempt with zero listings still stamps it further down, but never
    # builds a baseline, so `baseline_done` is what actually gates silence.
    is_first_run = not profile.baseline_done

    fetched.progress.set(phase="saving")
    profile.last_run_at = datetime.now(UTC)
    # observability: accumulate this scan into today's per-portal
    # health row. transport_used re-reads the scraper because a blocked local
    # ladder may have escalated to the API mid-scan.
    outcome = result.outcome
    scraper_health.record_scan(
        db, profile.portal, outcome, transport_policy.transport_used(scraper, settings)
    )

    if result.blocked:
        profile.last_run_status = "blocked"
        profile.last_run_detail = "Portal temporarily blocked (anti-bot). Will retry on next scan."
        summary["blocked_portals"].append(profile.portal)
        if not result.listings:
            return result
    elif outcome == "error":
        profile.last_run_status = "error"
        profile.last_run_detail = result.error[:300]
        summary["errors"].append(result.error)
        return result

    if fetched.search.seen is None and not result.blocked:
        # This search read every page it was allowed to, and got through. That
        # is what the next sweep is counted from — and only a scan that got
        # through may stamp it, or a fortnight of blocks would read as a
        # fortnight of complete readings and the sweep would never come round.
        profile.last_full_sweep_at = datetime.now(UTC)

    # profile keywords ADD to global keywords (the UI presents them as "extra"):
    # a profile must never lose base protection just because it added its own
    keywords = list(settings.get("excluded_keywords", []))
    keywords += [k for k in parse_keywords_csv(profile.excluded_keywords) if k not in keywords]

    # what this search actually asked the portal for, so what came back can be
    # checked against it rather than assumed to match. Read once per profile:
    # it is a URL parse plus a gazetteer lookup, and it cannot change mid-scan.
    area = requested_area(profile.search_url)
    outside_area = 0

    new_properties: list[Property] = []
    price_drops: list[tuple[Property, float, float]] = []
    # (property, previous status) pairs that came back to life this scan:
    # "filtered" whose keyword no longer applies, "gone" that reappeared on
    # the portal. Without their own notification the transition was applied
    # silently — a returned listing is exactly as actionable as a new one.
    reactivated: list[tuple[Property, str]] = []

    for raw in result.listings:
        prop, is_new, price_changed = upsert_listing(db, raw, profile_id=profile.id)

        # Before any status branch: a hidden or filtered listing is still a
        # listing the portal returned, and the count is about what the portal
        # sent back, not about what the dashboard ends up showing.
        outside = _outside_requested_area(area, raw, prop)
        if outside is not None:
            prop.outside_requested_area = outside
            if outside:
                outside_area += 1

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

    summary["outside_area"] += outside_area
    if outside_area:
        logger.info(
            "Profile '%s': %d of %d listings came back outside the requested area",
            profile.name,
            outside_area,
            len(result.listings),
        )

    profile.last_run_status = outcome
    if outcome == "no_results":
        # Said as the portal's own statement, because that is what it is. The
        # user reading this line is entitled to know they are looking at an
        # answer about the market and not at a search that failed quietly —
        # the two used to produce the same word.
        profile.last_run_detail = "The portal answered: no listing matches this search"
    elif not result.blocked:
        found = str(len(result.listings))
        pages = str(result.pages_fetched)
        if result.truncated:
            summary["truncated"] += 1
            # Both numbers come from the portal's own declaration, never from
            # the app's arithmetic, and each is printed only where the portal
            # made it: a search whose total went unstated says how many it
            # took and nothing about how many it missed.
            if result.total_listings is not None:
                found += f" of about {result.total_listings:,}"
            # Not against a split search's page count: that is the pages of
            # several narrower searches, and the portal's total describes the
            # one wide search nobody ran to the end. "80 of 42 pages" is the
            # shape of the nonsense being avoided.
            if result.total_pages is not None and not result.parts:
                pages += f" of {result.total_pages}"
        detail = (
            f"{found} listings across {pages} pages (strategy: {result.strategy_used or 'N/A'})"
        )
        detail += _truncation_note(result)
        detail += _split_note(result)
        detail += _quick_scan_note(result)
        # said on the profile's own line, because it is a fact about *this*
        # search: the portal was asked for an area and answered with something
        # else. Kept, not dropped — the count is how the user finds out.
        if outside_area:
            detail += f" — {outside_area} outside the requested area"
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
        return result

    # per-profile channel routing: None = all enabled channels, [] = muted
    channels = notifier.profile_channels(profile.notify_channels)
    if channels is not None and not channels:
        # a muted search still fills the dashboard, it just never pings: bail
        # out before the (otherwise pointless) scoring pass and the broadcasts
        return result
    # Deal Score for the new listings, so an undervalued one is flagged in the
    # notification itself (market position must be computed first — it feeds it).
    if new_properties:
        pricing_stats.annotate_market_position(db, new_properties)
        deal_score.annotate_deal_scores(db, new_properties)
    summary["notified"] += _dispatch_notifications(
        new_properties, price_drops, reactivated, channels
    )
    return result


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
