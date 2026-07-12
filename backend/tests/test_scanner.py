"""Scanner test: notification suppression on first scan, send capping,
structured floor ("T") subjected to keyword filter, additive profile keywords,
"gone" marking, and protection of hidden properties."""
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Property, SearchProfile
from app.services import scanner
from app.scrapers.base import RawListing, ScrapeResult


def _prop(**kwargs) -> Property:
    base: dict[str, Any] = dict(title="Trilocale", city="Milano", floor="", sqm=90.0)
    base.update(kwargs)
    return Property(**base)


def _raw(**kwargs) -> RawListing:
    base: dict[str, Any] = dict(
        portal="immobiliare", portal_id="1", url="u", title="Trilocale")
    base.update(kwargs)
    return RawListing(**base)


def test_structured_ground_floor_is_recognized():
    """Immobiliare exposes floor="T": without translation, the filter wouldn't trigger."""
    texts = scanner._texts_for_filter(_raw(floor="T"), _prop(floor="T"))
    assert "piano terra" in texts


def test_structured_basement_is_recognized():
    texts = scanner._texts_for_filter(_raw(floor="S"), _prop(floor="S"))
    assert "seminterrato" in texts


def test_normal_floor_does_not_generate_misleading_text():
    texts = scanner._texts_for_filter(_raw(floor="3"), _prop(floor="3"))
    assert "piano terra" not in texts
    assert "seminterrato" not in texts


def test_limited_notifications_and_final_summary(monkeypatch):
    sent, summaries = [], []
    monkeypatch.setattr(scanner.notifier, "notify_new_property",
                        lambda p, channels=None: sent.append(p) or True)
    monkeypatch.setattr(scanner.notifier, "notify_price_drop",
                        lambda p, o, n, channels=None: True)
    monkeypatch.setattr(scanner.notifier, "broadcast",
                        lambda text, channels=None, subject=None:
                        summaries.append(text) or True)

    props = [_prop(title=f"Casa {i}") for i in range(40)]
    scanner._dispatch_notifications(props, [])

    assert len(sent) == scanner.MAX_NOTIFICATIONS_PER_SCAN
    assert len(summaries) == 1
    assert "25" in summaries[0]  # 40 - 15 remaining


def test_no_summary_if_below_cap(monkeypatch):
    summaries = []
    monkeypatch.setattr(scanner.notifier, "notify_new_property",
                        lambda p, channels=None: True)
    monkeypatch.setattr(scanner.notifier, "broadcast",
                        lambda text, channels=None, subject=None:
                        summaries.append(text) or True)

    scanner._dispatch_notifications([_prop(), _prop()], [])
    assert summaries == []


def test_price_drop_overflow_gets_its_own_summary(monkeypatch):
    """Regression: the "… and N more" overflow message existed only for new
    properties — price drops beyond the cap were dropped without a trace."""
    dropped, summaries = [], []
    monkeypatch.setattr(scanner.notifier, "notify_new_property",
                        lambda p, channels=None: True)
    monkeypatch.setattr(scanner.notifier, "notify_price_drop",
                        lambda p, o, n, channels=None: dropped.append(p) or True)
    monkeypatch.setattr(scanner.notifier, "broadcast",
                        lambda text, channels=None, subject=None:
                        summaries.append(text) or True)

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
    monkeypatch.setattr(scanner.notifier, "notify_new_property",
                        lambda p, channels=None: True)
    monkeypatch.setattr(scanner.notifier, "notify_property_reactivated",
                        lambda p, previous, channels=None:
                        reactivated.append((p.title, previous)) or True)
    monkeypatch.setattr(scanner.notifier, "broadcast",
                        lambda text, channels=None, subject=None: True)

    sent = scanner._dispatch_notifications(
        [], [], [(_prop(title="Tornato"), "gone")]
    )
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
            RawListing(portal="immobiliare", portal_id="1",
                       url="https://www.immobiliare.it/annunci/1/",
                       title="Trilocale", city="Milano", rooms=3, sqm=90.0,
                       price=300_000.0, address="Via Roma, 1"),
            RawListing(portal="immobiliare", portal_id="2",
                       url="https://www.immobiliare.it/annunci/2/",
                       title="Bilocale", city="Milano", rooms=2, sqm=60.0,
                       price=200_000.0, address="Via Roma, 2"),
        ]
        return result


def _run_profile(db, monkeypatch, profile) -> tuple[list, dict]:
    notified = []
    monkeypatch.setattr(scanner, "get_scraper", lambda portal: _FakeScraper())
    monkeypatch.setattr(scanner.notifier, "notify_new_property",
                        lambda p, channels=None: notified.append(p) or True)
    monkeypatch.setattr(scanner.notifier, "broadcast",
                        lambda t, channels=None, subject=None: True)
    summary = {"new": 0, "updated": 0, "filtered": 0, "price_changes": 0,
               "gone": 0, "notified": 0, "blocked_portals": [], "errors": []}
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
        name="Test", portal="immobiliare", search_url="u",
        last_run_at=datetime.now(timezone.utc), last_run_status="blocked",
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
    profile = SearchProfile(name="Test", portal="immobiliare", search_url="u",
                            excluded_keywords="giardino")

    class _KwScraper(_FakeScraper):
        def scrape(self, url):
            result = super().scrape(url)
            result.listings[0].title = "Trilocale in vendita all'asta"
            result.listings[1].title = "Bilocale con giardino"
            return result

    db.add(profile)
    db.commit()
    monkeypatch.setattr(scanner, "get_scraper", lambda portal: _KwScraper())
    monkeypatch.setattr(scanner.notifier, "notify_new_property",
                        lambda p, channels=None: True)
    monkeypatch.setattr(scanner.notifier, "broadcast",
                        lambda t, channels=None, subject=None: True)
    summary = {"new": 0, "updated": 0, "filtered": 0, "price_changes": 0,
               "gone": 0, "notified": 0, "blocked_portals": [], "errors": []}
    scanner._scan_profile(db, profile, {"excluded_keywords": ["asta"]}, summary)
    db.commit()

    # both global ("asta") and profile ("giardino") keywords trigger
    assert summary["filtered"] == 2


def test_properties_not_seen_for_days_become_gone(db):
    old = datetime.now(timezone.utc) - timedelta(days=scanner.GONE_AFTER_DAYS + 1)
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


def test_hidden_property_is_not_reactivated(db, monkeypatch):
    """"Hide property" must resist subsequent scans: hidden status
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


# --- scraper health alerting -----------------------------------------------

@pytest.fixture
def health(monkeypatch):
    """Captures health alerts instead of sending them. `delivered` simulates
    a channel that accepts (True) or drops (False) the message."""
    calls = {"failure": [], "recovery": [], "delivered": True}
    monkeypatch.setattr(
        scanner.notifier, "notify_scraper_failure",
        lambda p, failures, channels=None:
            calls["failure"].append(failures) or calls["delivered"],
    )
    monkeypatch.setattr(
        scanner.notifier, "notify_scraper_recovered",
        lambda p, failures, channels=None:
            calls["recovery"].append(failures) or True,
    )
    return calls


def _health_scan(db, profile, status, threshold=3) -> dict:
    """One scan outcome pushed through the health tracker."""
    profile.last_run_status = status
    summary = {"health_alerts": 0}
    scanner._update_profile_health(
        profile, {"health_alert_after_failures": threshold}, summary
    )
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
    monkeypatch.setattr(scanner, "load_settings",
                        lambda: {"excluded_keywords": [],
                                 "health_alert_after_failures": 2})

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
    stale.last_seen_at = datetime.now(timezone.utc) - timedelta(days=21)
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
    stale.last_seen_at = datetime.now(timezone.utc) - timedelta(days=21)
    db.commit()

    monkeypatch.setattr(scanner, "get_scraper", lambda portal: _FakeScraper())
    monkeypatch.setattr(scanner, "SessionLocal", lambda: db)
    monkeypatch.setattr(scanner, "load_settings", lambda: {"excluded_keywords": []})
    monkeypatch.setattr(scanner.notifier, "notify_new_property",
                        lambda p, channels=None: True)
    monkeypatch.setattr(scanner.notifier, "broadcast",
                        lambda t, channels=None, subject=None: True)

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
    monkeypatch.setattr(scanner, "load_settings",
                        lambda: {"excluded_keywords": [], "scanning_paused": True})

    assert scanner.run_scan()["status"] == "paused"

    # manual=True bypasses the pause: now the scraper is reached, and since it
    # raises, the profile is recorded as an error (proving it was invoked)
    result = scanner.run_scan(manual=True)
    assert result["status"] == "done"
    assert profile.last_run_status == "error"


def test_second_scan_notifies_only_new(db, monkeypatch):
    profile = SearchProfile(name="Test", portal="immobiliare", search_url="u")
    db.add(profile)
    db.commit()

    _run_profile(db, monkeypatch, profile)          # first pass: baseline
    notified, summary = _run_profile(db, monkeypatch, profile)  # same listings

    assert summary["new"] == 0
    assert summary["updated"] == 2
    assert notified == []
