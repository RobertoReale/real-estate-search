"""Scanner test: notification suppression on first scan, send capping,
structured floor ("T") subjected to keyword filter, additive profile keywords,
"gone" marking, and protection of hidden properties."""

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Property, SearchProfile
from app.scrapers.base import RawListing, ScrapeResult
from app.scrapers.immobiliare import ImmobiliareScraper
from app.services import scanner

from . import mock_portal
from .mock_portal import Flat, MockPortalServer


def _prop(**kwargs) -> Property:
    base: dict[str, Any] = dict(title="Trilocale", city="Milano", floor="", sqm=90.0)
    base.update(kwargs)
    return Property(**base)


def _raw(**kwargs) -> RawListing:
    base: dict[str, Any] = dict(portal="immobiliare", portal_id="1", url="u", title="Trilocale")
    base.update(kwargs)
    return RawListing(**base)


def test_structured_ground_floor_is_recognized():
    """Immobiliare exposes floor="T": without translation, the filter wouldn't trigger."""
    texts = scanner._texts_for_filter(_raw(floor="T"), _prop(floor="T"))
    assert "piano terra" in texts


def test_structured_basement_is_recognized():
    texts = scanner._texts_for_filter(_raw(floor="S"), _prop(floor="S"))
    assert "seminterrato" in texts


def test_structured_mezzanine_is_recognized():
    """floor="R" is the portals' abbreviation for "piano rialzato": without the
    translation an excluded keyword "rialzato" never sees it (the word lives only
    on the ad detail page, which the scan doesn't fetch) and it stays active."""
    texts = scanner._texts_for_filter(_raw(floor="R"), _prop(floor="R"))
    assert "piano rialzato" in texts


def test_normal_floor_does_not_generate_misleading_text():
    texts = scanner._texts_for_filter(_raw(floor="3"), _prop(floor="3"))
    assert "piano terra" not in texts
    assert "seminterrato" not in texts


def test_limited_notifications_and_final_summary(monkeypatch):
    sent, summaries = [], []
    monkeypatch.setattr(
        scanner.notifier, "notify_new_property", lambda p, channels=None: sent.append(p) or True
    )
    monkeypatch.setattr(scanner.notifier, "notify_price_drop", lambda p, o, n, channels=None: True)
    monkeypatch.setattr(
        scanner.notifier,
        "broadcast",
        lambda text, channels=None, subject=None: summaries.append(text) or True,
    )

    props = [_prop(title=f"Casa {i}") for i in range(40)]
    scanner._dispatch_notifications(props, [])

    assert len(sent) == scanner.MAX_NOTIFICATIONS_PER_SCAN
    assert len(summaries) == 1
    assert "25" in summaries[0]  # 40 - 15 remaining


def test_no_summary_if_below_cap(monkeypatch):
    summaries = []
    monkeypatch.setattr(scanner.notifier, "notify_new_property", lambda p, channels=None: True)
    monkeypatch.setattr(
        scanner.notifier,
        "broadcast",
        lambda text, channels=None, subject=None: summaries.append(text) or True,
    )

    scanner._dispatch_notifications([_prop(), _prop()], [])
    assert summaries == []


def test_price_drop_overflow_gets_its_own_summary(monkeypatch):
    """Regression: the "… and N more" overflow message existed only for new
    properties — price drops beyond the cap were dropped without a trace."""
    dropped, summaries = [], []
    monkeypatch.setattr(scanner.notifier, "notify_new_property", lambda p, channels=None: True)
    monkeypatch.setattr(
        scanner.notifier,
        "notify_price_drop",
        lambda p, o, n, channels=None: dropped.append(p) or True,
    )
    monkeypatch.setattr(
        scanner.notifier,
        "broadcast",
        lambda text, channels=None, subject=None: summaries.append(text) or True,
    )

    drops = [(_prop(title=f"Casa {i}"), 300_000.0, 280_000.0) for i in range(20)]
    scanner._dispatch_notifications([], drops)

    assert len(dropped) == scanner.MAX_NOTIFICATIONS_PER_SCAN
    assert len(summaries) == 1
    assert "5" in summaries[0]  # 20 - 15 remaining price changes


def test_reactivated_properties_are_notified(monkeypatch):
    """Regression: a "gone" listing reappearing (or a "filtered" one whose
    keyword no longer applies) was flipped back to active in silence — a
    returned listing is exactly as actionable as a new one."""
    reactivated = []
    monkeypatch.setattr(scanner.notifier, "notify_new_property", lambda p, channels=None: True)
    monkeypatch.setattr(
        scanner.notifier,
        "notify_property_reactivated",
        lambda p, previous, channels=None: reactivated.append((p.title, previous)) or True,
    )
    monkeypatch.setattr(
        scanner.notifier, "broadcast", lambda text, channels=None, subject=None: True
    )

    sent = scanner._dispatch_notifications([], [], [(_prop(title="Tornato"), "gone")])
    assert sent == 1
    assert reactivated == [("Tornato", "gone")]


# --- first scan: acquires without notifying --------------------------------


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


class _FakeScraper:
    """Returns two listings without touching the network."""

    def __init__(self):
        self.delay_seconds = 0
        self.max_pages = 1

    def scrape(self, url):
        result = ScrapeResult(pages_fetched=1, strategy_used="fake")
        result.listings = [
            RawListing(
                portal="immobiliare",
                portal_id="1",
                url="https://www.immobiliare.it/annunci/1/",
                title="Trilocale",
                city="Milano",
                rooms=3,
                sqm=90.0,
                price=300_000.0,
                address="Via Roma, 1",
            ),
            RawListing(
                portal="immobiliare",
                portal_id="2",
                url="https://www.immobiliare.it/annunci/2/",
                title="Bilocale",
                city="Milano",
                rooms=2,
                sqm=60.0,
                price=200_000.0,
                address="Via Roma, 2",
            ),
        ]
        return result


def _summary() -> dict:
    return {
        "new": 0,
        "updated": 0,
        "filtered": 0,
        "price_changes": 0,
        "gone": 0,
        "notified": 0,
        "outside_area": 0,
        "blocked_portals": [],
        "errors": [],
    }


def _run_profile(db, monkeypatch, profile) -> tuple[list, dict]:
    notified = []
    monkeypatch.setattr(scanner, "get_scraper", lambda portal: _FakeScraper())
    monkeypatch.setattr(
        scanner.notifier, "notify_new_property", lambda p, channels=None: notified.append(p) or True
    )
    monkeypatch.setattr(scanner.notifier, "broadcast", lambda t, channels=None, subject=None: True)
    summary = _summary()
    scanner._scan_profile(db, profile, {"excluded_keywords": []}, summary)
    db.commit()
    return notified, summary


def test_first_scan_acquires_without_notifying(db, monkeypatch):
    """Regression: on first scan every property is "new"; notifying all
    would mean hundreds of Telegram messages."""
    profile = SearchProfile(name="Test", portal="immobiliare", search_url="u")
    db.add(profile)
    db.commit()

    notified, summary = _run_profile(db, monkeypatch, profile)

    assert summary["new"] == 2
    assert notified == [], "first scan must not send notifications"
    assert db.query(Property).count() == 2
    assert "first scan" in profile.last_run_detail


def test_blocked_first_attempt_does_not_consume_baseline(db, monkeypatch):
    """Regression: a profile whose very first scan attempt got blocked/errored
    (zero listings) still had `last_run_at` stamped for scheduling purposes.
    Using `last_run_at is None` as the "first scan" proxy meant the *next*
    attempt — the one that actually saw real listings for the first time —
    was no longer treated as first-run, and fired a notification for every
    property as if each were newly discovered. `baseline_done` must be the
    only thing that gates the silence, independent of `last_run_at`."""
    profile = SearchProfile(
        name="Test",
        portal="immobiliare",
        search_url="u",
        last_run_at=datetime.now(UTC),
        last_run_status="blocked",
        baseline_done=False,
    )
    db.add(profile)
    db.commit()

    notified, summary = _run_profile(db, monkeypatch, profile)

    assert summary["new"] == 2
    assert notified == [], "a prior blocked attempt must not skip the silent baseline scan"
    assert profile.baseline_done is True


def test_profile_keywords_add_to_global(db, monkeypatch):
    """Regression: profile keywords previously replaced global keywords, but
    UI presents them as "extra"."""
    profile = SearchProfile(
        name="Test", portal="immobiliare", search_url="u", excluded_keywords="giardino"
    )

    class _KwScraper(_FakeScraper):
        def scrape(self, url):
            result = super().scrape(url)
            result.listings[0].title = "Trilocale in vendita all'asta"
            result.listings[1].title = "Bilocale con giardino"
            return result

    db.add(profile)
    db.commit()
    monkeypatch.setattr(scanner, "get_scraper", lambda portal: _KwScraper())
    monkeypatch.setattr(scanner.notifier, "notify_new_property", lambda p, channels=None: True)
    monkeypatch.setattr(scanner.notifier, "broadcast", lambda t, channels=None, subject=None: True)
    summary = _summary()
    scanner._scan_profile(db, profile, {"excluded_keywords": ["asta"]}, summary)
    db.commit()

    # both global ("asta") and profile ("giardino") keywords trigger
    assert summary["filtered"] == 2


def test_properties_not_seen_for_days_become_gone(db):
    old = datetime.now(UTC) - timedelta(days=scanner.GONE_AFTER_DAYS + 1)
    p_old = _prop(title="Sparito", fingerprint="a")
    p_new = _prop(title="Recente", fingerprint="b")
    db.add_all([p_old, p_new])
    db.commit()
    p_old.last_seen_at = old
    db.commit()

    count = scanner._mark_vanished_properties(db)
    db.commit()

    assert count == 1
    assert p_old.status == "gone"
    assert p_new.status == "active"


def test_gone_marking_handles_aware_and_naive_timestamps_together(db):
    """SQLite returns naive datetimes, but a property written earlier in the
    same session still carries the aware value it was built with
    (`expire_on_commit=False`). Both shapes must survive the comparison."""
    old_naive = (datetime.now(UTC) - timedelta(days=scanner.GONE_AFTER_DAYS + 1)).replace(
        tzinfo=None
    )
    old_aware = datetime.now(UTC) - timedelta(days=scanner.GONE_AFTER_DAYS + 1)
    p1 = _prop(title="Naive", fingerprint="a")
    p2 = _prop(title="Aware", fingerprint="b")
    db.add_all([p1, p2])
    db.commit()
    p1.last_seen_at = old_naive
    p2.last_seen_at = old_aware
    db.commit()

    assert scanner._mark_vanished_properties(db) == 2


def test_hidden_property_is_not_reactivated(db, monkeypatch):
    """ "Hide property" must resist subsequent scans: hidden status
    never returns to active on its own (unlike filtered/gone)."""
    profile = SearchProfile(name="Test", portal="immobiliare", search_url="u")
    db.add(profile)
    db.commit()

    _run_profile(db, monkeypatch, profile)  # baseline: creates 2 properties
    prop = db.query(Property).first()
    prop.status = "hidden"
    db.commit()

    notified, _ = _run_profile(db, monkeypatch, profile)
    db.refresh(prop)
    assert prop.status == "hidden"
    assert notified == []


def test_sold_property_is_not_reactivated(db, monkeypatch):
    """ "Mark as sold" is a user choice a scan never reverts (like "hidden",
    invariant 5): a "VENDUTO" re-post often stays online for weeks, so the scan
    keeps re-finding it — it must stay sold and silent, not bounce back to
    active and notify as if new."""
    profile = SearchProfile(name="Test", portal="immobiliare", search_url="u")
    db.add(profile)
    db.commit()

    _run_profile(db, monkeypatch, profile)  # baseline: creates 2 properties
    prop = db.query(Property).first()
    prop.status = "sold"
    db.commit()

    notified, _ = _run_profile(db, monkeypatch, profile)
    db.refresh(prop)
    assert prop.status == "sold"
    assert notified == []


# --- scraper health alerting -----------------------------------------------


@pytest.fixture
def health(monkeypatch):
    """Captures health alerts instead of sending them. `delivered` simulates
    a channel that accepts (True) or drops (False) the message."""
    calls = {"failure": [], "recovery": [], "delivered": True}
    monkeypatch.setattr(
        scanner.notifier,
        "notify_scraper_failure",
        lambda p, failures, channels=None: calls["failure"].append(failures) or calls["delivered"],
    )
    monkeypatch.setattr(
        scanner.notifier,
        "notify_scraper_recovered",
        lambda p, failures, channels=None: calls["recovery"].append(failures) or True,
    )
    return calls


def _health_scan(db, profile, status, threshold=3) -> dict:
    """One scan outcome pushed through the health tracker."""
    profile.last_run_status = status
    summary = {"health_alerts": 0}
    scanner._update_profile_health(profile, {"health_alert_after_failures": threshold}, summary)
    db.commit()
    return summary


@pytest.fixture
def profile(db):
    p = SearchProfile(name="Milano", portal="immobiliare", search_url="u")
    db.add(p)
    db.commit()
    return p


def test_single_failure_does_not_alert(db, profile, health):
    """DataDome hands out 403s that clear within the hour: alerting on the
    first one would train the user to ignore the alerts."""
    _health_scan(db, profile, "blocked")

    assert health["failure"] == []
    assert profile.consecutive_failures == 1


def test_alert_fires_once_the_streak_reaches_the_threshold(db, profile, health):
    for _ in range(3):
        _health_scan(db, profile, "blocked")

    assert health["failure"] == [3]
    assert profile.health_alert_sent is True


def test_ongoing_outage_does_not_re_alert_every_scan(db, profile, health):
    """A portal blocked for a week must send one message, not one per scan."""
    for _ in range(10):
        _health_scan(db, profile, "error")

    assert health["failure"] == [3]
    assert profile.consecutive_failures == 10


def test_undelivered_alert_is_retried_on_the_next_scan(db, profile, health):
    """`health_alert_sent` means "the user was told". If no channel is
    configured broadcast() returns False, and swallowing the outage there
    would defeat the whole feature."""
    health["delivered"] = False
    for _ in range(4):
        _health_scan(db, profile, "blocked")

    assert health["failure"] == [3, 4]
    assert profile.health_alert_sent is False


def test_recovery_is_announced_and_resets_the_streak(db, profile, health):
    for _ in range(3):
        _health_scan(db, profile, "blocked")
    summary = _health_scan(db, profile, "ok")

    assert health["recovery"] == [3]
    assert summary["health_alerts"] == 1
    assert profile.consecutive_failures == 0
    assert profile.health_alert_sent is False


def test_recovery_is_silent_if_no_alert_was_sent(db, profile, health):
    """Two blocked scans below the threshold, then success: the user never
    heard about a problem, so "recovered" would be a message about nothing."""
    _health_scan(db, profile, "blocked")
    _health_scan(db, profile, "blocked")
    _health_scan(db, profile, "ok")

    assert health["recovery"] == []
    assert profile.consecutive_failures == 0


def test_threshold_zero_disables_alerting(db, profile, health):
    for _ in range(20):
        _health_scan(db, profile, "blocked", threshold=0)

    assert health["failure"] == []
    assert profile.consecutive_failures == 20  # still tracked, just not alerted


def test_crashed_profile_counts_as_a_failure(db, profile, health, monkeypatch):
    """A profile whose scrape raises never reaches the code that records
    `last_run_status`: without an explicit write here the streak would reset
    to zero on every crash and the alert would never fire."""

    class _Boom:
        delay_seconds = 0
        max_pages = 1

        def scrape(self, url):
            raise RuntimeError("connection reset")

    monkeypatch.setattr(scanner, "get_scraper", lambda portal: _Boom())
    monkeypatch.setattr(scanner, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        scanner,
        "load_settings",
        lambda: {"excluded_keywords": [], "health_alert_after_failures": 2},
    )

    scanner.run_scan()
    assert profile.consecutive_failures == 1
    assert profile.last_run_status == "error"
    assert health["failure"] == []

    result = scanner.run_scan()
    assert health["failure"] == [2]
    assert result["health_alerts"] == 1


class _BlockedScraper:
    """Simulates DataDome refusing the very first request."""

    delay_seconds = 0
    max_pages = 1

    def scrape(self, url):
        result = ScrapeResult(pages_fetched=0, strategy_used="fake")
        result.blocked = True
        return result


def test_blocked_full_scan_does_not_mark_gone(db, profile, monkeypatch):
    """Regression: after weeks with the PC off, *every* property is past the
    GONE_AFTER_DAYS cutoff — the day-based threshold only absorbs blocks
    shorter than the cutoff while the app keeps scanning. A single blocked
    startup scan used to mark the whole dashboard "gone" and stamp fake
    gone_at dates into the days-on-market statistics before any listing
    could be re-seen. A stale card until the next clean scan is the cheaper
    mistake."""
    stale = _prop(title="Ancora online", fingerprint="a")
    db.add(stale)
    db.commit()
    stale.last_seen_at = datetime.now(UTC) - timedelta(days=21)
    db.commit()

    monkeypatch.setattr(scanner, "get_scraper", lambda portal: _BlockedScraper())
    monkeypatch.setattr(scanner, "SessionLocal", lambda: db)
    monkeypatch.setattr(scanner, "load_settings", lambda: {"excluded_keywords": []})

    result = scanner.run_scan()

    assert result["blocked_portals"] == ["immobiliare"]
    assert result["gone"] == 0
    assert stale.status == "active"
    assert stale.gone_at is None


def test_clean_full_scan_still_marks_gone(db, profile, monkeypatch):
    """Counterpart of the guard above: when every profile scanned cleanly,
    the vanished properties must still be swept."""
    stale = _prop(title="Sparito davvero", fingerprint="zzz")
    db.add(stale)
    db.commit()
    stale.last_seen_at = datetime.now(UTC) - timedelta(days=21)
    db.commit()

    monkeypatch.setattr(scanner, "get_scraper", lambda portal: _FakeScraper())
    monkeypatch.setattr(scanner, "SessionLocal", lambda: db)
    monkeypatch.setattr(scanner, "load_settings", lambda: {"excluded_keywords": []})
    monkeypatch.setattr(scanner.notifier, "notify_new_property", lambda p, channels=None: True)
    monkeypatch.setattr(scanner.notifier, "broadcast", lambda t, channels=None, subject=None: True)

    result = scanner.run_scan()

    assert result["gone"] == 1
    assert stale.status == "gone"


def test_paused_skips_automatic_scan_but_manual_runs(db, profile, monkeypatch):
    """The global pause stops the *scheduler* from touching the portals (to rest
    the residential IP), but a user-triggered "Scan now" is explicit intent and
    must run anyway. A scraper that raises when called proves the automatic run
    never reached it."""

    class _MustNotScrape:
        delay_seconds = 0
        max_pages = 1

        def scrape(self, url):
            raise AssertionError("paused automatic scan must not touch the portal")

    monkeypatch.setattr(scanner, "get_scraper", lambda portal: _MustNotScrape())
    monkeypatch.setattr(scanner, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        scanner, "load_settings", lambda: {"excluded_keywords": [], "scanning_paused": True}
    )

    assert scanner.run_scan()["status"] == "paused"

    # manual=True bypasses the pause: now the scraper is reached, and since it
    # raises, the profile is recorded as an error (proving it was invoked)
    result = scanner.run_scan(manual=True)
    assert result["status"] == "done"
    assert profile.last_run_status == "error"


def test_a_muted_search_scans_but_never_notifies(db, monkeypatch):
    """A search the user has silenced keeps filling the dashboard — it just
    never pings. The empty string cannot say this (it means "all channels"),
    so the mute rides on its own sentinel. The control is the test below: same
    scan, same two brand-new properties, two notifications."""
    muted = SearchProfile(
        name="Muted",
        portal="immobiliare",
        search_url="u",
        baseline_done=True,
        notify_channels=scanner.notifier.MUTED,
    )
    db.add(muted)
    db.commit()

    notified, summary = _run_profile(db, monkeypatch, muted)

    assert summary["new"] == 2
    assert summary["notified"] == 0
    assert notified == []
    assert db.query(Property).count() == 2  # scanned all the same


def test_the_same_scan_notifies_when_the_search_is_not_muted(db, monkeypatch):
    """Control for the mute above: with the default channels (empty = all), the
    identical scan on an identical profile sends both notifications."""
    profile = SearchProfile(name="Loud", portal="immobiliare", search_url="u", baseline_done=True)
    db.add(profile)
    db.commit()

    notified, summary = _run_profile(db, monkeypatch, profile)

    assert summary["new"] == 2
    assert len(notified) == 2


def test_a_muted_search_keeps_its_health_alert_to_itself(db, monkeypatch):
    """ "No notifications" includes the scraper-health alert: the streak is still
    counted (the dashboard shows it), it is just never announced."""
    alerts = []
    monkeypatch.setattr(
        scanner.notifier,
        "notify_scraper_failure",
        lambda p, n, channels=None: alerts.append(p) or True,
    )
    profile = SearchProfile(
        name="Muted",
        portal="immobiliare",
        search_url="u",
        notify_channels=scanner.notifier.MUTED,
        last_run_status="blocked",
        consecutive_failures=2,
    )

    scanner._update_profile_health(
        profile, {"health_alert_after_failures": 3}, {"health_alerts": 0}
    )

    assert alerts == []
    assert profile.consecutive_failures == 3
    assert not profile.health_alert_sent


def test_second_scan_notifies_only_new(db, monkeypatch):
    profile = SearchProfile(name="Test", portal="immobiliare", search_url="u")
    db.add(profile)
    db.commit()

    _run_profile(db, monkeypatch, profile)  # first pass: baseline
    notified, summary = _run_profile(db, monkeypatch, profile)  # same listings

    assert summary["new"] == 0
    assert summary["updated"] == 2
    assert notified == []


# --- listings that came back from outside the requested area ---------------
#
# Search URLs are fixture *strings* here — the portal's own grammar, nothing
# fetched. Asking a portal for a district is not the same as getting one: it
# decides, and a listing it files under the next district still arrives. What
# these pin is that the disagreement is reported and the listing is kept.

NAVIGLI_URL = "https://www.immobiliare.it/vendita-case/milano/navigli/"
MILANO_URL = "https://www.immobiliare.it/vendita-case/milano/"
# What the portal's own map produces for a multi-district selection: the path
# stays at the bare comune and the districts ride along as opaque ids.
MULTIZONE_URL = "https://www.immobiliare.it/vendita-case/milano/?idMZona[]=10046&idMZona[]=10047"

# Somewhere in the Navigli, and Rome — 480 km outside any circle Milano has.
IN_MILANO = (45.4500, 9.1750)
IN_ROMA = (41.9028, 12.4964)


def _listing(portal_id: str, sqm: float, **kwargs) -> RawListing:
    """One listing, distinct enough from its siblings that the conservative
    deduplication leaves it standing alone (fingerprint = city + rooms + sqm)."""
    base: dict[str, Any] = dict(
        portal="immobiliare",
        portal_id=portal_id,
        url=f"https://www.immobiliare.it/annunci/{portal_id}/",
        title="Trilocale",
        city="Milano",
        rooms=3,
        sqm=sqm,
        price=300_000.0,
        address=f"Via Roma, {portal_id}",
    )
    base.update(kwargs)
    return RawListing(**base)


def _area_scraper(listings: list[RawListing]):
    class _S:
        def __init__(self):
            self.delay_seconds = 0
            self.max_pages = 1

        def scrape(self, url):
            return ScrapeResult(listings=list(listings), pages_fetched=1, strategy_used="fake")

    return _S()


def _scan_area(db, monkeypatch, search_url: str, listings: list[RawListing], profile=None):
    if profile is None:
        profile = SearchProfile(name="Zone", portal="immobiliare", search_url=search_url)
        db.add(profile)
        db.commit()
    monkeypatch.setattr(scanner, "get_scraper", lambda portal: _area_scraper(listings))
    monkeypatch.setattr(scanner.notifier, "notify_new_property", lambda p, channels=None: True)
    monkeypatch.setattr(scanner.notifier, "broadcast", lambda t, channels=None, subject=None: True)
    summary = _summary()
    scanner._scan_profile(db, profile, {"excluded_keywords": []}, summary)
    db.commit()
    return profile, summary


def _by_title(db) -> dict[str, Property]:
    return {p.title: p for p in db.query(Property).all()}


def test_a_zone_search_counts_and_flags_what_came_back_from_elsewhere(db, monkeypatch):
    """The acceptance case: the portal answers a Navigli search with listings
    from Navigli's neighbours, and the scan has to say so."""
    _, summary = _scan_area(
        db,
        monkeypatch,
        NAVIGLI_URL,
        [
            _listing(
                "1",
                90.0,
                title="Dentro",
                zone="Navigli",
                latitude=IN_MILANO[0],
                longitude=IN_MILANO[1],
            ),
            _listing("2", 70.0, title="Distretto accanto", zone="Città Studi"),
            _listing("3", 80.0, title="Altro comune", city="Monza", zone="Centro"),
            _listing("4", 60.0, title="Senza zona", zone=""),
        ],
    )

    assert summary["outside_area"] == 2
    props = _by_title(db)
    assert props["Distretto accanto"].outside_requested_area is True
    assert props["Altro comune"].outside_requested_area is True
    assert props["Dentro"].outside_requested_area is False
    # no district on the listing is not evidence of a wrong one: unjudged, so
    # left exactly as it was rather than accused
    assert props["Senza zona"].outside_requested_area is False


def test_an_out_of_area_listing_is_kept_not_dropped(db, monkeypatch):
    """A listing on a boundary, or one the portal files under the next
    district, is often precisely the one the user wants. Deleting it would turn
    a visible annoyance into an invisible one, so all three survive the scan
    with their status untouched."""
    _scan_area(
        db,
        monkeypatch,
        NAVIGLI_URL,
        [
            _listing("1", 90.0, title="Dentro", zone="Navigli"),
            _listing("2", 70.0, title="Distretto accanto", zone="Città Studi"),
            _listing("3", 80.0, title="Altro comune", city="Monza", zone="Centro"),
        ],
    )

    props = _by_title(db)
    assert len(props) == 3
    assert {p.status for p in props.values()} == {"active"}


def test_the_profile_line_says_how_many_came_from_outside(db, monkeypatch):
    profile, _ = _scan_area(
        db,
        monkeypatch,
        NAVIGLI_URL,
        [
            _listing("1", 90.0, title="Dentro", zone="Navigli"),
            _listing("2", 70.0, title="Distretto accanto", zone="Città Studi"),
        ],
    )

    assert "1 outside the requested area" in profile.last_run_detail


def test_a_scan_that_agrees_with_its_search_says_nothing_about_area(db, monkeypatch):
    """A false alarm here would be as bad as the silence it replaces."""
    profile, summary = _scan_area(
        db,
        monkeypatch,
        NAVIGLI_URL,
        [_listing("1", 90.0, title="Dentro", zone="Navigli")],
    )

    assert summary["outside_area"] == 0
    assert "outside" not in profile.last_run_detail


def test_coordinates_outside_the_comune_are_outside_the_area(db, monkeypatch):
    """The city text says Milano and the pin is in Rome: the comune's own
    circle is what catches a listing whose label agrees and whose location does
    not."""
    _, summary = _scan_area(
        db,
        monkeypatch,
        MILANO_URL,
        [
            _listing("1", 90.0, title="Dentro", latitude=IN_MILANO[0], longitude=IN_MILANO[1]),
            _listing("2", 70.0, title="A Roma", latitude=IN_ROMA[0], longitude=IN_ROMA[1]),
        ],
    )

    assert summary["outside_area"] == 1
    assert _by_title(db)["A Roma"].outside_requested_area is True


def test_a_city_search_never_flags_on_the_district(db, monkeypatch):
    """A search for the whole comune asked for no district, so no district it
    gets back can disagree with it."""
    _, summary = _scan_area(
        db,
        monkeypatch,
        MILANO_URL,
        [
            _listing("1", 90.0, title="Navigli", zone="Navigli"),
            _listing("2", 70.0, title="Citta Studi", zone="Città Studi"),
        ],
    )

    assert summary["outside_area"] == 0


def test_zone_ids_alone_never_flag_a_district(db, monkeypatch):
    """`idMZona[]` values are opaque numbers only the portal can resolve, so a
    listing's district text can never match one. Reading "no match" out of that
    would flag every listing of a perfectly good multi-district search — the
    comune still applies, the districts cannot."""
    _, summary = _scan_area(
        db,
        monkeypatch,
        MULTIZONE_URL,
        [
            _listing("1", 90.0, title="Un distretto qualsiasi", zone="Città Studi"),
            _listing("2", 70.0, title="Altro comune", city="Monza", zone="Centro"),
        ],
    )

    assert summary["outside_area"] == 1
    props = _by_title(db)
    assert props["Un distretto qualsiasi"].outside_requested_area is False
    assert props["Altro comune"].outside_requested_area is True


def test_a_search_with_no_readable_location_judges_nothing(db, monkeypatch):
    """Most of this suite's profiles carry `search_url="u"`. A check with an
    opinion about those would mark the whole dashboard out of area."""
    _, summary = _scan_area(
        db,
        monkeypatch,
        "u",
        [_listing("1", 90.0, title="Ovunque", city="Monza", zone="Centro")],
    )

    assert summary["outside_area"] == 0
    assert _by_title(db)["Ovunque"].outside_requested_area is False


def test_a_wider_search_clears_the_flag_its_narrower_sibling_set(db, monkeypatch):
    """Two searches can both find one property. The flag records the last
    judgement that could actually be made, so a city-wide search re-finding a
    listing its zone-search sibling flagged clears it — otherwise a property
    stays accused by a search that no longer covers it."""
    listings = [_listing("1", 90.0, title="Zona accanto", zone="Città Studi")]
    _scan_area(db, monkeypatch, NAVIGLI_URL, listings)
    assert _by_title(db)["Zona accanto"].outside_requested_area is True

    wider = SearchProfile(name="Tutta Milano", portal="immobiliare", search_url=MILANO_URL)
    db.add(wider)
    db.commit()
    _scan_area(db, monkeypatch, MILANO_URL, listings, profile=wider)

    assert _by_title(db)["Zona accanto"].outside_requested_area is False


# --- "nothing found" is not "ok" -------------------------------------------
#
# Three different events used to reach the dashboard as the same word: a portal
# that answered with an empty market, one that did not really answer at all,
# and one that answered with listings. What these pin is the sentence the user
# ends up reading and the failure streak underneath it — a portal that said
# "none" has answered, and must not accumulate towards an outage alert the way
# a block does.
#
# They run against the loopback sandbox rather than a fake scraper on purpose:
# what separates the outcomes is the *payload*, so the payload has to come over
# HTTP from something that can be made to send each of them in turn.

OUTCOME_SEARCH = "/vendita-case/torino/"

OUTCOME_FLAT = Flat(
    ad_id="70001",
    title="Trilocale via Sacchi",
    price=280_000,
    rooms=3,
    sqm=95,
    city="Torino",
    zone="Centro",
    street="Via Sacchi",
    civic="8",
)

# A search results page with a grid and nothing in it, and — deliberately —
# without the portal's own "nothing matched" wording. This is what the HTML
# safety net is served in the block test below, so that the `blocked` verdict
# under assertion can only have come from the api-next classification: this
# page produces an *error* on the HTML path, never a block.
_EMPTY_HTML_NO_MARKER = "<html><body><main></main></body></html>"


@pytest.fixture
def portal():
    with MockPortalServer() as server:
        yield server


@pytest.fixture
def outcome_profile(db, portal, monkeypatch):
    """A real `ImmobiliareScraper` aimed at the sandbox, driven through the
    scanner's own path, with the geography already resolvable (invariant 7)."""
    portal.install(monkeypatch)
    portal.serve_json("/api-next/geography/autocomplete/", mock_portal.immobiliare_geography())
    monkeypatch.setattr(
        scanner, "get_scraper", lambda _portal: ImmobiliareScraper(delay_seconds=0, max_pages=1)
    )
    monkeypatch.setattr(scanner.notifier, "notify_new_property", lambda p, channels=None: True)
    monkeypatch.setattr(scanner.notifier, "broadcast", lambda t, channels=None, subject=None: True)
    profile = SearchProfile(
        name="Torino", portal="immobiliare", search_url=portal.url(OUTCOME_SEARCH)
    )
    db.add(profile)
    db.commit()
    return profile


def _scan_outcome(db, profile) -> dict:
    """One scan plus the health bookkeeping `run_scan` performs after it, which
    is where the streak this asserts on is actually kept."""
    summary = _summary()
    summary["health_alerts"] = 0
    scanner._scan_profile(db, profile, {"excluded_keywords": []}, summary)
    scanner._update_profile_health(profile, {"health_alert_after_failures": 3}, summary)
    db.commit()
    return summary


def _serve_blocked(portal) -> None:
    portal.serve_json("/api-next/search-list/listings/", {"detail": "blocked"}, status=403)
    portal.serve(
        OUTCOME_SEARCH, "<html><body>Access is temporarily restricted</body></html>", status=403
    )


def _serve_api(portal, flats, *, declare_count: bool = True) -> None:
    portal.serve_json(
        "/api-next/search-list/listings/",
        mock_portal.immobiliare_api_page(flats, declare_count=declare_count),
    )


def test_a_blocked_scan_opens_the_failure_streak(db, portal, outcome_profile):
    _serve_blocked(portal)

    summary = _scan_outcome(db, outcome_profile)

    assert outcome_profile.last_run_status == "blocked"
    assert outcome_profile.consecutive_failures == 1
    assert summary["blocked_portals"] == ["immobiliare"]


def test_the_portal_answering_none_is_an_answer_and_clears_the_streak(db, portal, outcome_profile):
    """The case this task exists for: an empty result set that the portal
    counted is a statement about the market, not a failed scan. It closes the
    streak a preceding block opened, and it says so in words."""
    _serve_blocked(portal)
    _scan_outcome(db, outcome_profile)
    assert outcome_profile.consecutive_failures == 1

    _serve_api(portal, [])
    already_requested = len(portal.requested)
    summary = _scan_outcome(db, outcome_profile)

    assert outcome_profile.last_run_status == "no_results"
    assert outcome_profile.consecutive_failures == 0
    assert "portal answered" in outcome_profile.last_run_detail
    assert summary["blocked_portals"] == [] and summary["errors"] == []
    # and it stopped there: confirming an answer by spending a
    # guaranteed-blocked HTML request would turn it back into an alarm
    second_scan = [urlparse(p).path for p in portal.requested[already_requested:]]
    assert OUTCOME_SEARCH not in second_scan


def test_a_scan_that_finds_listings_is_ok(db, portal, outcome_profile):
    _serve_api(portal, [OUTCOME_FLAT])

    summary = _scan_outcome(db, outcome_profile)

    assert outcome_profile.last_run_status == "ok"
    assert outcome_profile.consecutive_failures == 0
    assert summary["new"] == 1
    assert "1 listings" in outcome_profile.last_run_detail


def test_an_empty_api_page_that_states_no_count_is_a_block(db, portal, outcome_profile):
    """A soft block IS an empty 200: the portal serves the same status and the
    same empty list, minus any statement of how many results it matched. Read
    as `no_results` it would report a working search over an empty market,
    which is the most expensive way this can be wrong.

    The HTML safety net is served an empty page here, so it contributes an
    error and never a block — the `blocked` verdict under assertion can only
    have come from the api-next page above.
    """
    _serve_api(portal, [], declare_count=False)
    portal.serve(OUTCOME_SEARCH, _EMPTY_HTML_NO_MARKER)

    summary = _scan_outcome(db, outcome_profile)

    assert outcome_profile.last_run_status == "blocked"
    assert outcome_profile.consecutive_failures == 1
    assert summary["blocked_portals"] == ["immobiliare"]
