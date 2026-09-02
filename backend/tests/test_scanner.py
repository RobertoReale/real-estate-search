"""Scanner test: notification suppression on first scan, send capping,
structured floor ("T") subjected to keyword filter, additive profile keywords,
"gone" marking, and protection of hidden properties."""

import json
import logging
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.database import Base
from app.models import Property, SearchProfile
from app.scrapers.base import RawListing, ScrapeResult
from app.scrapers.immobiliare import ImmobiliareScraper
from app.services import scanner
from app.services.search_builder import IMMOBILIARE_ZONE_ID_PARAM

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
        "truncated": 0,
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


# --- coordinates on the first run ------------------------------------------
#
# The map was emptiest on the run where it matters most. Coordinates arrive only
# when the portal chooses to send them, and everything else waited for someone
# to find the "Find coordinates" maintenance button — so the first scan of a new
# search drew a map full of holes at exactly the moment somebody is deciding
# whether this app works. A scan now closes that itself, in the two halves the
# geocoder is built around.


def _scan_with(db, monkeypatch, listings: list[RawListing], search_url: str = MILANO_URL) -> dict:
    """One full `run_scan` over a fake scraper returning `listings`."""
    db.add(SearchProfile(name="Milano", portal="immobiliare", search_url=search_url))
    db.commit()
    monkeypatch.setattr(scanner, "SessionLocal", lambda: db)
    monkeypatch.setattr(scanner, "get_scraper", lambda portal: _area_scraper(listings))
    monkeypatch.setattr(scanner.geocoder, "PACE_SECONDS", 0)
    return scanner.run_scan()


def test_a_scan_places_what_it_imported_from_what_it_already_knew(db, monkeypatch):
    """Two listings arrive with the portal's own pins and a third without. The
    district those two describe is enough to place the third, for nothing — and
    the pin it gets says it is a district and not a doorstep."""
    result = _scan_with(
        db,
        monkeypatch,
        [
            _listing("1", 90.0, title="Con pin A", zone="Isola", latitude=45.486, longitude=9.186),
            _listing("2", 70.0, title="Con pin B", zone="Isola", latitude=45.490, longitude=9.190),
            _listing("3", 60.0, title="Senza pin", zone="Isola"),
        ],
    )

    assert (result["located"], result["located_approximate"]) == (1, 1)
    placed = _by_title(db)["Senza pin"]
    assert placed.latitude == pytest.approx(45.488)
    assert placed.coordinate_source == scanner.geocoder.SOURCE_ZONE
    # ...and the two that arrived with pins are recorded as the portal's own.
    assert _by_title(db)["Con pin A"].coordinate_source == scanner.geocoder.SOURCE_PORTAL


def test_a_scan_asks_nominatim_only_for_what_it_could_not_place_itself(db, monkeypatch):
    """The paced half. It runs after the free half, over that scan's own
    imports, and never over the listing the free half already placed."""
    asked = []

    def lookup(query, base, **kwargs):
        asked.append(query)
        return (45.47, 9.19)

    monkeypatch.setattr(scanner.geocoder, "_nominatim_lookup", lookup)
    result = _scan_with(
        db,
        monkeypatch,
        [
            _listing("1", 90.0, title="Con pin A", zone="Isola", latitude=45.486, longitude=9.186),
            _listing("2", 70.0, title="Con pin B", zone="Isola", latitude=45.490, longitude=9.190),
            _listing("3", 60.0, title="Zona nota", zone="Isola"),
            _listing("4", 50.0, title="Zona ignota", zone="Lambrate"),
        ],
    )

    # Only the one district-less listing reached the network: the other three
    # were answered by the portal or by the district the scan had just learnt.
    assert asked == ["Via Roma, 4, Milano, Italia"]
    assert (result["located"], result["located_approximate"]) == (2, 1)
    assert _by_title(db)["Zona ignota"].coordinate_source == scanner.geocoder.SOURCE_ADDRESS


def test_turning_the_post_scan_lookup_off_still_places_what_is_free(db, monkeypatch):
    """The setting governs the requests, not the pins: the cache and the
    district centres cost nothing, so they are not something to opt out of."""

    def boom(*args, **kwargs):
        raise AssertionError("geocode_after_scan is off: no request may be made")

    monkeypatch.setattr(scanner.geocoder, "_nominatim_lookup", boom)
    monkeypatch.setattr(
        scanner, "load_settings", lambda: {**config.DEFAULT_SETTINGS, "geocode_after_scan": False}
    )
    result = _scan_with(
        db,
        monkeypatch,
        [
            _listing("1", 90.0, title="Con pin A", zone="Isola", latitude=45.486, longitude=9.186),
            _listing("2", 70.0, title="Con pin B", zone="Isola", latitude=45.490, longitude=9.190),
            _listing("3", 60.0, title="Senza pin", zone="Isola"),
            _listing("4", 50.0, title="Zona ignota", zone="Lambrate"),
        ],
    )

    assert result["located"] == 1
    assert _by_title(db)["Zona ignota"].latitude is None


def test_a_property_from_an_earlier_scan_is_not_swept_again(db, monkeypatch):
    """Bounded to what this scan touched. An address Nominatim has already
    declined must not be re-asked on every scheduled run for the rest of time."""
    old = _prop(title="Vecchio", fingerprint="old", city="Milano", zone="Isola")
    old.address = "Via Antica 1"
    db.add(old)
    db.commit()
    old.last_seen_at = datetime.now(UTC) - timedelta(days=3)
    db.commit()

    asked = []
    monkeypatch.setattr(
        scanner.geocoder,
        "_nominatim_lookup",
        lambda q, base, **kw: asked.append(q) or (45.47, 9.19),
    )
    _scan_with(db, monkeypatch, [_listing("1", 90.0, title="Nuovo", zone="Lambrate")])

    assert asked == ["Via Roma, 1, Milano, Italia"]
    assert old.latitude is None


def test_a_scan_survives_a_geocoder_that_fails(db, monkeypatch):
    """Fail-open: a map pin that cannot be worked out is not a reason for a scan
    to report an error over the listings it did collect."""

    def broken(*args, **kwargs):
        raise RuntimeError("the gazetteer is on fire")

    monkeypatch.setattr(scanner.geocoder, "resolve_offline", broken)
    monkeypatch.setattr(scanner.geocoder, "geocode_missing_properties", broken)
    result = _scan_with(db, monkeypatch, [_listing("1", 90.0, title="Nuovo", zone="Isola")])

    assert result["status"] == "done"
    assert result["errors"] == [] and result["new"] == 1
    assert result["located"] == 0


def test_a_manual_geocoding_batch_makes_the_scan_step_aside(db, monkeypatch):
    """The user pressed "Find coordinates" and it is still running. The scan
    reports no pins rather than fighting for the lock."""
    monkeypatch.setattr(
        scanner.geocoder, "_nominatim_lookup", lambda *a, **kw: pytest.fail("must not be reached")
    )
    assert scanner.geocoder._geocode_run_lock.acquire(blocking=False)
    try:
        result = _scan_with(db, monkeypatch, [_listing("1", 90.0, title="Nuovo", zone="Isola")])
    finally:
        scanner.geocoder._geocode_run_lock.release()

    assert result["status"] == "done" and result["located"] == 0


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


def _scan_outcome(db, profile, **settings) -> dict:
    """One scan plus the health bookkeeping `run_scan` performs after it, which
    is where the streak this asserts on is actually kept.

    `settings` overrides go to `_scan_profile`, which reads the page cap from
    them — the fixture's `max_pages` is overwritten there on every scan, so a
    test about the cap has to set it here and not on the scraper.
    """
    summary = _summary()
    summary["health_alerts"] = 0
    scanner._scan_profile(db, profile, {"excluded_keywords": [], **settings}, summary)
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


# --- "N listings across 10 pages" is not the same as "all of them" ----------
#
# The cap is `max_pages_per_search`, ten by default and one in this fixture. A
# search with more pages than that returned its first few and reported a count
# with no qualification — a sentence a user reads as complete. These two pin
# what the profile's own line now says, and, as importantly, what it does not
# say about a search that fit.


def _serve_api_pages(portal, *, total_pages: int, total_listings: int) -> None:
    portal.serve_json_pages(
        "/api-next/search-list/listings/",
        lambda page: mock_portal.immobiliare_api_page(
            [
                Flat(
                    ad_id=f"71{page:02d}{i}",
                    title=f"Trilocale {page}-{i}",
                    price=280_000 + i,
                    rooms=3,
                    sqm=95,
                    city="Torino",
                )
                for i in range(2)
            ],
            max_pages=total_pages,
            count=total_listings,
        ),
    )


def test_a_search_stopped_by_the_page_limit_names_both_numbers(db, portal, outcome_profile):
    """The acceptance: what came back, what the portal said it had, and the cap
    that stood between them — on the search's own line, where the user is
    already looking to find out how it went."""
    _serve_api_pages(portal, total_pages=3, total_listings=60)

    summary = _scan_outcome(db, outcome_profile, max_pages_per_search=1)

    detail = outcome_profile.last_run_detail
    assert "2 of about 60 listings" in detail
    assert "1 of 3 pages" in detail
    assert "stopped at the page limit of 1 page" in detail
    assert "narrow the search" in detail
    assert outcome_profile.last_run_status == "ok"
    assert summary["truncated"] == 1


def test_a_search_that_fit_is_reported_exactly_as_before(db, portal, outcome_profile):
    """One page on the portal, one page allowed: this scan holds everything
    there was. Saying otherwise here would be the false alarm that makes the
    real notice unreadable."""
    _serve_api_pages(portal, total_pages=1, total_listings=2)

    summary = _scan_outcome(db, outcome_profile, max_pages_per_search=1)

    detail = outcome_profile.last_run_detail
    assert detail.startswith("2 listings across 1 pages")
    assert "of about" not in detail
    assert "page limit" not in detail
    assert summary["truncated"] == 0


# --- a scan says what it is doing, while it does it -------------------------
#
# For several minutes the dashboard could say exactly one word, "scanning", and
# a working scan looked identical to a hung one. These drive `run_scan` itself
# against the loopback sandbox — a fake scraper handing back a finished
# `ScrapeResult` has no middle, and the middle is the whole subject.

IDEALISTA_SEARCH = "/vendita-case/torino-torino/"
# One path, two searches: `serve_answering` sees the query, so the sandbox can
# answer the same endpoint differently for each — which is how one scan is made
# to produce two different outcomes without a second portal.
TORINO_SEARCH = "/vendita-case/torino/"
ANSWERING_CAP = "300000"
REFUSING_CAP = "400000"

PROGRESS_SETTINGS: dict = {
    "excluded_keywords": [],
    "request_delay_seconds": 0,
    "max_pages_per_search": 2,
    # the post-scan sweep is the one part of a scan that would leave the
    # sandbox: it is G.8's, and it is off here so these stay offline
    "geocode_after_scan": False,
}


def _progress_flats(page: int, count: int = 2) -> list[Flat]:
    return [
        Flat(
            ad_id=f"9{page}{i}",
            title=f"Trilocale {page}-{i}",
            price=250_000 + i,
            rooms=3,
            sqm=90,
            city="Torino",
            latitude=45.07,
            longitude=7.68,
        )
        for i in range(count)
    ]


@pytest.fixture
def scan_db():
    """One in-memory database, seen the same way from every thread.

    `sqlite://` on the default pool gives each thread its own connection and so
    its own empty database: a scan started on a second thread would not even
    find `search_profiles`. `StaticPool` is what makes the watcher and the scan
    look at one database, which is the premise of watching a scan from outside
    it.
    """
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture
def live_scan(scan_db, portal, monkeypatch):
    """A real scan on the sandbox, ready to be started on its own thread.

    Returns the settings hook, so each test names the delay and the page cap it
    is about. `get_scraper` is deliberately *not* patched: which engine a portal
    gets, and the delay floor it carries, are part of what is being reported.
    """
    portal.install(monkeypatch)
    portal.serve_json("/api-next/geography/autocomplete/", mock_portal.immobiliare_geography())
    monkeypatch.setattr(scanner, "SessionLocal", lambda: scan_db)
    monkeypatch.setattr(scanner.notifier, "notify_new_property", lambda p, channels=None: True)
    monkeypatch.setattr(scanner.notifier, "broadcast", lambda t, channels=None, subject=None: True)

    def configure(**overrides) -> None:
        monkeypatch.setattr(scanner, "load_settings", lambda: {**PROGRESS_SETTINGS, **overrides})

    configure()
    return configure


def _watch(session, portal, name: str, portal_name: str, path: str) -> SearchProfile:
    profile = SearchProfile(name=name, portal=portal_name, search_url=portal.url(path))
    session.add(profile)
    session.commit()
    return profile


def _await_phase(phase: str, timeout: float = 15.0) -> dict:
    """The first progress snapshot in `phase`, or a failure naming what it saw."""
    deadline = time.monotonic() + timeout
    seen = ""
    while time.monotonic() < deadline:
        state = scanner.get_scan_progress()
        if state["phase"] == phase:
            return state
        seen = state["phase"]
        time.sleep(0.01)
    raise AssertionError(f"the scan never reported '{phase}' (last seen: '{seen}')")


def test_a_scan_says_which_search_and_which_page_while_it_runs(scan_db, portal, live_scan):
    """The acceptance, and it is read from another thread on purpose: a dict
    inspected only once the scan is over would pass while reporting nothing at
    all during the minutes that matter.

    The portal holds each page open until the watcher has looked, so what is
    asserted is the state at four exact moments rather than whatever a sleep
    happened to catch.
    """
    serving = threading.Semaphore(0)  # the portal: "I am about to answer a page"
    proceed = threading.Semaphore(0)  # the watcher: "I have looked, carry on"

    def render(page: int) -> dict:
        serving.release()
        assert proceed.acquire(timeout=20)
        return mock_portal.immobiliare_api_page(_progress_flats(page), max_pages=2, count=4)

    portal.serve_json_pages("/api-next/search-list/listings/", render)
    _watch(scan_db, portal, "Torino", "immobiliare", "/vendita-case/torino/")
    _watch(scan_db, portal, "Milano", "immobiliare", "/vendita-case/milano/")

    scan = threading.Thread(target=scanner.run_scan, kwargs={"manual": True}, daemon=True)
    scan.start()
    seen = []
    for _ in range(4):  # two searches, two pages each
        assert serving.acquire(timeout=30), "the scan never reached the portal"
        seen.append(scanner.get_scan_progress())
        proceed.release()
    scan.join(timeout=60)
    assert not scan.is_alive()

    assert [(s["profile"], s["portal"], s["page"]) for s in seen] == [
        ("Torino", "immobiliare", 1),
        ("Torino", "immobiliare", 2),
        ("Milano", "immobiliare", 1),
        ("Milano", "immobiliare", 2),
    ]
    assert [s["profile_index"] for s in seen] == [1, 1, 2, 2]
    assert all(s["active"] and s["profile_total"] == 2 for s in seen)
    # the second page knows what the first one read, and the portal's own page
    # total is there to be shown the count against
    assert seen[1]["listings"] == 2
    assert seen[1]["total_pages"] == 2 and seen[1]["total_listings"] == 4
    assert seen[1]["detail"] == "Torino on immobiliare: reading page 2 of 2"
    # and the next search starts from nothing: a page count or a page total
    # carried across would attribute one search's progress to another
    assert seen[2]["listings"] == 0 and seen[2]["total_pages"] is None
    assert seen[2]["detail"] == "Milano on immobiliare: reading page 1"
    # and it goes quiet again rather than leaving the last page on screen
    assert scanner.get_scan_progress() == dict(scanner._IDLE_PROGRESS)


def test_a_page_total_the_portal_never_declared_is_never_invented(scan_db, portal, live_scan):
    """The rule the shape exists to enforce: only a real total may be drawn as
    a proportion. Idealista's HTML pages publish no page count anywhere, so what
    a watcher gets is a rising count and nothing to divide it by — a bar that
    fills to 90% and stops teaches the user the app lies."""
    serving = threading.Semaphore(0)
    proceed = threading.Semaphore(0)

    def page(query: dict) -> mock_portal.Page:
        serving.release()
        assert proceed.acquire(timeout=20)
        return mock_portal.Page(mock_portal.idealista_results_page(_progress_flats(1)))

    portal.serve_answering(IDEALISTA_SEARCH, page)
    _watch(scan_db, portal, "Torino", "idealista", IDEALISTA_SEARCH)
    live_scan(max_pages_per_search=1)

    scan = threading.Thread(target=scanner.run_scan, kwargs={"manual": True}, daemon=True)
    scan.start()
    assert serving.acquire(timeout=30), "the scan never reached the portal"
    mid_scan = scanner.get_scan_progress()
    proceed.release()
    scan.join(timeout=60)
    assert not scan.is_alive()

    assert mid_scan["portal"] == "idealista" and mid_scan["page"] == 1
    assert mid_scan["total_pages"] is None
    assert mid_scan["detail"].endswith("reading page 1")


def test_a_polite_pause_is_reported_as_waiting_and_not_as_a_hang(scan_db, portal, live_scan):
    """`request_delay_seconds` is spent between every page, so most of a scan's
    wall clock is this pause. Named, it is the app working as designed; unnamed,
    it is the single most common reason a running scan is taken for a crashed
    one."""
    proceed = threading.Semaphore(0)

    def render(page: int) -> dict:
        if page > 1:
            assert proceed.acquire(timeout=20)
        return mock_portal.immobiliare_api_page(_progress_flats(page), max_pages=2, count=4)

    portal.serve_json_pages("/api-next/search-list/listings/", render)
    _watch(scan_db, portal, "Torino", "immobiliare", "/vendita-case/torino/")
    live_scan(request_delay_seconds=1.5)

    scan = threading.Thread(target=scanner.run_scan, kwargs={"manual": True}, daemon=True)
    scan.start()
    try:
        # the pause between page 1 and page 2 is 1.05-2.1s wide, so it is there
        # to be read rather than something a poll has to be lucky to catch
        waiting = _await_phase("waiting")
    finally:
        proceed.release()
    scan.join(timeout=60)
    assert not scan.is_alive()

    assert waiting["waiting_seconds"] > 0
    assert "pausing" in waiting["detail"] and "before the next page" in waiting["detail"]
    assert "keeps the portal answering" in waiting["detail"], "say why, or it reads as dead time"


def test_the_journal_keeps_one_line_per_search_with_the_outcome_it_ended_on(
    scan_db, portal, live_scan
):
    """ "Did it work?" is asked after a scan at least as often as during one,
    and for somebody who left the room it is the only question. One entry per
    search, in G.5's own words, readable once everything has stopped."""

    def answer(query: dict) -> mock_portal.Page:
        if (query.get("prezzoMassimo") or [""])[0] == REFUSING_CAP:
            return mock_portal.Page("refused", status=403)
        return mock_portal.Page(
            json.dumps(mock_portal.immobiliare_api_page(_progress_flats(1, 1))),
            content_type="application/json",
        )

    portal.serve_answering("/api-next/search-list/listings/", answer)
    # the HTML safety net behind the refused search, so its verdict is the block
    # api-next reported and not a 404 collected on the way past
    portal.serve(TORINO_SEARCH, "Access is temporarily restricted", status=403)
    _watch(
        scan_db, portal, "Answered", "immobiliare", f"{TORINO_SEARCH}?prezzoMassimo={ANSWERING_CAP}"
    )
    _watch(
        scan_db, portal, "Refused", "immobiliare", f"{TORINO_SEARCH}?prezzoMassimo={REFUSING_CAP}"
    )

    scanner.run_scan(manual=True)

    entries = scanner.get_scan_journal()
    # newest first: the search that ran last is the one being asked about
    assert [(e["profile"], e["portal"], e["outcome"]) for e in entries] == [
        ("Refused", "immobiliare", "blocked"),
        ("Answered", "immobiliare", "ok"),
    ]
    answered = entries[1]
    assert answered["pages"] == 1 and answered["listings"] == 1
    assert answered["stopped_because"] == "the portal had nothing more to give"
    assert answered["transport"] == "local (curl_cffi)"
    assert answered["started_at"] <= answered["finished_at"]
    assert "1 listings across 1 pages" in answered["detail"]
    assert entries[0]["stopped_because"] == "the portal refused the request"
    # it outlives the scan, which is the whole point of writing it down
    assert scanner.get_scan_progress()["active"] is False
    assert len(scanner.get_scan_journal()) == 2


def test_a_search_that_crashed_is_in_the_journal_too(scan_db, portal, live_scan, monkeypatch):
    """The run a user most wants to find afterwards is the one that fell over.
    `run_scan` catches the exception so the other searches still run — and the
    entry is written after that, so it reads the status the profile really
    ended on."""

    class _Exploding:
        delay_seconds = 0
        max_pages = 1
        on_progress = None

        def scrape(self, url):
            raise RuntimeError("the parser gave up")

    monkeypatch.setattr(scanner, "get_scraper", lambda _portal: _Exploding())
    _watch(scan_db, portal, "Torino", "immobiliare", "/vendita-case/torino/")

    scanner.run_scan(manual=True)

    entry = scanner.get_scan_journal()[0]
    assert entry["outcome"] == "error"
    assert entry["pages"] == 0 and entry["listings"] == 0
    assert entry["stopped_because"] == "the search could not be run at all"
    assert "the parser gave up" in entry["detail"]


def test_no_stored_secret_reaches_the_journal(scan_db, portal, live_scan, monkeypatch):
    """A search URL can carry an API key and an error message copies whatever
    URL it failed on, so the journal is one copy away from printing a
    credential on a screen the user is meant to read."""
    secret = "dd-cookie-9f3ab27c41"

    class _LeakingScraper:
        delay_seconds = 0
        max_pages = 1
        on_progress = None

        def scrape(self, url):
            return ScrapeResult(error=f"immobiliare: blocked on ?token={secret}")

    monkeypatch.setattr(scanner, "get_scraper", lambda _portal: _LeakingScraper())
    live_scan(datadome_cookie=secret)
    _watch(scan_db, portal, "Torino", "immobiliare", "/vendita-case/torino/")

    scanner.run_scan(manual=True)

    entry = scanner.get_scan_journal()[0]
    assert entry["outcome"] == "error"
    assert secret not in entry["detail"]
    assert "?token=***" in entry["detail"]


def test_the_journal_keeps_the_recent_scans_and_forgets_the_rest(scan_db, portal, live_scan):
    """Bounded on purpose: this is an in-memory record of the last handful of
    runs, not a second log file that grows for the life of the process."""
    scanner._journal.extend({"profile": str(n)} for n in range(scanner.MAX_JOURNAL_ENTRIES + 10))

    entries = scanner.get_scan_journal()

    assert len(entries) == scanner.MAX_JOURNAL_ENTRIES
    assert entries[0]["profile"] == str(scanner.MAX_JOURNAL_ENTRIES + 9)


def test_progress_that_cannot_be_recorded_never_takes_the_scan_down(
    scan_db, portal, live_scan, monkeypatch
):
    """A scan that failed *because* it was reporting on itself would be
    strictly worse than one that says nothing. Same rule as
    `scraper_health.record_scan`, and this is the assertion behind it."""
    portal.serve_json(
        "/api-next/search-list/listings/", mock_portal.immobiliare_api_page(_progress_flats(1, 1))
    )
    profile = _watch(scan_db, portal, "Torino", "immobiliare", "/vendita-case/torino/")

    def explode(state: dict) -> str:
        raise RuntimeError("the sentence could not be written")

    monkeypatch.setattr(scanner, "_progress_sentence", explode)

    summary = scanner.run_scan(manual=True)

    assert summary["status"] == "done"
    assert summary["new"] == 1
    assert profile.last_run_status == "ok"


# --- when there are more than fit, split the search -------------------------
#
# G.7 taught a scan to say "241 of about 1.050" instead of "241". This is the
# half that makes the apology unnecessary: a search with more results than
# `max_pages_per_search` can carry is run again as several narrower searches
# whose results do not overlap, and merged on the fingerprint that already
# deduplicates everything else.
#
# Three things have to hold or the split is worse than the truncation it
# replaces, and all three are below: the merge holds every listing exactly once;
# a partition whose parts do not add up to the whole is never reported as
# complete; and a search too big even for the part ceiling spends no extra
# request at all, because segmenting multiplies requests and requests are what
# get an IP blocked.

SPLIT_SEARCH = "/vendita-case/milano/"
SPLIT_ZONES = ("10046", "10047", "10048")


def _zone_flats(zone: str, count: int = 2) -> list[Flat]:
    return [
        Flat(
            ad_id=f"8{zone}{i}",
            title=f"Trilocale zona {zone}-{i}",
            price=300_000 + i,
            rooms=3,
            sqm=90,
            city="Milano",
            zone=zone,
        )
        for i in range(count)
    ]


def _zoned_answer(corpus: dict[str, list[Flat]], per_page: int):
    """An api-next that answers the zones it was *asked* for, and counts them.

    The whole search names every zone and gets a result set past the page cap;
    each part names one and gets a result set that fits. That difference is the
    entire subject, and it exists only on a portal reading `idMZona[]` off the
    request rather than serving one canned page to every caller.
    """

    def answer(query: dict[str, list[str]]) -> mock_portal.Page:
        asked = query.get(IMMOBILIARE_ZONE_ID_PARAM) or list(corpus)
        flats = [f for zone in asked for f in corpus.get(zone, [])]
        try:
            page = max(int((query.get("pag") or ["1"])[0]), 1)
        except ValueError:
            page = 1
        return mock_portal.Page(
            json.dumps(
                mock_portal.immobiliare_api_page(
                    flats[(page - 1) * per_page : page * per_page],
                    max_pages=max(1, -(-len(flats) // per_page)),
                    count=len(flats),
                )
            ),
            content_type="application/json",
        )

    return answer


def _serve_zoned_portal(portal, corpus: dict[str, list[Flat]], *, per_page: int = 2) -> None:
    portal.serve_answering("/api-next/search-list/listings/", _zoned_answer(corpus, per_page))


def _listing_requests(portal) -> list[str]:
    """Every api-next *search* request, which is what a split spends."""
    return [
        path
        for path in portal.requested
        if urlparse(path).path == "/api-next/search-list/listings/"
    ]


@pytest.fixture
def split_profile(db, portal, monkeypatch):
    """A three-zone Immobiliare search on the sandbox, scanned the real way."""
    portal.install(monkeypatch)
    portal.serve_json("/api-next/geography/autocomplete/", mock_portal.immobiliare_geography())
    monkeypatch.setattr(scanner, "get_scraper", lambda _portal: ImmobiliareScraper())
    monkeypatch.setattr(scanner.notifier, "notify_new_property", lambda p, channels=None: True)
    monkeypatch.setattr(scanner.notifier, "broadcast", lambda t, channels=None, subject=None: True)
    zones = "&".join(f"{IMMOBILIARE_ZONE_ID_PARAM}={zone}" for zone in SPLIT_ZONES)
    profile = SearchProfile(
        name="Milano", portal="immobiliare", search_url=portal.url(f"{SPLIT_SEARCH}?{zones}")
    )
    db.add(profile)
    db.commit()
    return profile


def _scan_split(db, profile, **settings) -> tuple[ScrapeResult, dict]:
    """One scan, and the scrape it ran on — the parts and the reason it stopped
    exist only there. The delay is zeroed because the pause between parts is
    real: they are consecutive searches against one host and owe it the same
    politeness every page does."""
    summary = _summary()
    result = scanner._scan_profile(
        db,
        profile,
        {
            "excluded_keywords": [],
            "max_pages_per_search": 1,
            "request_delay_seconds": 0,
            **settings,
        },
        summary,
    )
    db.commit()
    return result, summary


def test_a_search_too_big_for_the_cap_is_run_in_parts_and_reported_complete(
    db, portal, split_profile
):
    """The acceptance: three zones the cap cannot carry together and can carry
    one at a time. Every listing lands exactly once — a listing returned by two
    parts costs one wasted parse, because `upsert_listing` deduplicates it the
    way it deduplicates everything else — and the sentence the user reads stops
    apologising for a page limit that no longer cost them anything."""
    _serve_zoned_portal(portal, {zone: _zone_flats(zone) for zone in SPLIT_ZONES})

    result, summary = _scan_split(db, split_profile)

    assert result.parts == 3
    assert not result.truncated
    assert len(result.listings) == 6
    assert len({listing.url for listing in result.listings}) == 6
    assert db.query(Property).count() == 6
    assert summary["new"] == 6 and summary["truncated"] == 0

    detail = split_profile.last_run_detail
    assert detail.startswith("6 listings across 4 pages")
    assert "searched in 3 parts" in detail
    assert "covered the whole result set" in detail
    assert "page limit" not in detail


def test_a_partition_that_does_not_add_up_is_never_reported_as_complete(
    db, portal, split_profile, monkeypatch, caplog
):
    """A split that lost the middle zone is worse than the truncation it
    replaced, because the truncation at least announced itself. The portal
    counts each part for us, so the check is its arithmetic and not this app's:
    two parts declaring four results between them, against a whole of six,
    cannot have covered it — and what the scan keeps is the honest notice plus
    every listing the parts did bring back."""
    _serve_zoned_portal(portal, {zone: _zone_flats(zone) for zone in SPLIT_ZONES})
    base = split_profile.search_url.split("?")[0]
    monkeypatch.setattr(
        scanner,
        "segment_search",
        lambda *_a, **_k: [
            f"{base}?{IMMOBILIARE_ZONE_ID_PARAM}={SPLIT_ZONES[0]}",
            f"{base}?{IMMOBILIARE_ZONE_ID_PARAM}={SPLIT_ZONES[2]}",
        ],
    )

    with caplog.at_level(logging.ERROR):
        result, summary = _scan_split(db, split_profile)

    assert result.parts == 2
    assert result.truncated and summary["truncated"] == 1
    assert "not provably total" in caplog.text
    # kept, not discarded: a partition that cannot be proved total is still
    # four listings this scan did not have before
    assert len(result.listings) == 4
    detail = split_profile.last_run_detail
    assert "stopped at the page limit" in detail
    assert "still did not fit" in detail


def test_a_search_past_the_part_ceiling_keeps_the_notice_and_spends_nothing(
    db, portal, split_profile
):
    """ "Never split past the point of return." A search needing more parts than
    the ceiling allows would not fit in the ceiling's worth of parts either, so
    running them buys the same truncation notice at eight times the requests.
    It is refused before the first extra one, which is what the request log
    asserts here — degrading to the notice, not to more traffic."""
    _serve_zoned_portal(portal, {zone: _zone_flats(zone, 8) for zone in SPLIT_ZONES}, per_page=1)

    result, summary = _scan_split(db, split_profile)

    assert result.parts == 0
    assert result.truncated and summary["truncated"] == 1
    assert "stopped at the page limit" in split_profile.last_run_detail
    assert "parts" not in split_profile.last_run_detail
    assert len(_listing_requests(portal)) == 1


def test_a_part_that_still_does_not_fit_is_not_split_again(db, portal, split_profile):
    """The other half of the same rule: the recursion has no natural floor, and
    no depth at which a search is guaranteed to fit.

    The corpus is deliberately lopsided, because that is the only way a part
    overflows — an evenly divided search fits by construction. One district
    holds four of the six listings and is still two pages against a one-page
    cap, so the parts run once, keep what they got, and hand back G.7's notice:
    four searches, not four and then twelve.
    """
    lopsided = {SPLIT_ZONES[0]: _zone_flats(SPLIT_ZONES[0], 4)}
    lopsided.update({zone: _zone_flats(zone, 1) for zone in SPLIT_ZONES[1:]})
    _serve_zoned_portal(portal, lopsided)

    result, summary = _scan_split(db, split_profile)

    assert result.parts == 3
    assert result.truncated and summary["truncated"] == 1
    assert "still did not fit" in split_profile.last_run_detail
    assert len(result.listings) == 4
    assert len(_listing_requests(portal)) == 1 + 3


def test_splitting_a_search_is_one_setting_the_user_can_turn_off(db, portal, split_profile):
    """It multiplies requests, and requests are what get an IP blocked. Off, the
    scan is exactly the one search it always was, truncation notice included."""
    _serve_zoned_portal(portal, {zone: _zone_flats(zone) for zone in SPLIT_ZONES})

    result, summary = _scan_split(db, split_profile, split_large_searches=False)

    assert result.parts == 0
    assert result.truncated and summary["truncated"] == 1
    assert len(result.listings) == 2
    assert len(_listing_requests(portal)) == 1


def test_a_split_search_says_which_part_it_is_on_while_it_runs(scan_db, portal, live_scan):
    """ "Part 3 of 7", while it is happening, and read from another thread for
    the same reason G.9's own tests are: a dict inspected once the scan is over
    would pass while reporting nothing during the minutes that matter.

    Without it the page count restarts at 1 once per part and a watcher reads a
    scan that keeps starting over — and a scan quietly making several times the
    requests it made last week is precisely what the user has to be able to see.
    """
    serving = threading.Semaphore(0)
    proceed = threading.Semaphore(0)
    zoned = _zoned_answer({zone: _zone_flats(zone) for zone in SPLIT_ZONES}, per_page=2)

    def answer(query: dict[str, list[str]]) -> mock_portal.Page:
        serving.release()
        assert proceed.acquire(timeout=20)
        return zoned(query)

    portal.serve_answering("/api-next/search-list/listings/", answer)
    zones = "&".join(f"{IMMOBILIARE_ZONE_ID_PARAM}={zone}" for zone in SPLIT_ZONES)
    _watch(scan_db, portal, "Milano", "immobiliare", f"{SPLIT_SEARCH}?{zones}")

    scan = threading.Thread(target=scanner.run_scan, kwargs={"manual": True}, daemon=True)
    scan.start()
    seen = []
    for _ in range(5):  # two pages of the whole search, then one page per part
        assert serving.acquire(timeout=30), "the scan never reached the portal"
        seen.append(scanner.get_scan_progress())
        proceed.release()
    scan.join(timeout=60)
    assert not scan.is_alive()

    assert [(s["part"], s["part_total"], s["page"]) for s in seen] == [
        (0, 0, 1),
        (0, 0, 2),
        (1, 3, 1),
        (2, 3, 1),
        (3, 3, 1),
    ]
    assert seen[3]["detail"] == "Milano on immobiliare, part 2 of 3: reading page 1"
    # and the ordinary case says nothing about parts it does not have
    assert seen[0]["detail"] == "Milano on immobiliare: reading page 1"
