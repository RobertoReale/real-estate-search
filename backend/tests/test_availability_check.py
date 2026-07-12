"""Tests for the dashboard availability check (services/availability_check.py).

The batch behavior encodes hard-won rules from invariant 16: the probe budget
bounds portal fetches per run (not the selection size), recently verified
properties skip for free so repeat runs resume, and a streak of refusals
aborts the batch instead of insisting against a portal that already said no —
the block would land on the IP the scheduled scans depend on.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Listing, Property
from app.services import availability_check
from app.services.availability_check import check_properties_availability
from app.services.email_import import BLOCK_STREAK_ABORT, MAX_CHECKS_PER_CALL


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def _property(db, portal_id: str, *, status: str = "active",
              last_seen_hours_ago: float | None = None) -> Property:
    prop = Property(fingerprint=f"fp-{portal_id}", title=f"Trilocale {portal_id}",
                    contract="sale", status=status, current_min_price=250_000.0)
    db.add(prop)
    db.flush()
    listing = Listing(
        property_id=prop.id, portal="immobiliare", portal_id=portal_id,
        url=f"https://www.immobiliare.it/annunci/{portal_id}/",
        price=250_000.0,
    )
    if last_seen_hours_ago is not None:
        listing.last_seen_at = datetime.now(timezone.utc) - timedelta(
            hours=last_seen_hours_ago)
    db.add(listing)
    db.commit()
    return prop


class _FakeProbe:
    """Offline stand-in: no browser machinery on purpose, so these tests also
    prove the services guard those calls with hasattr (fake probes predate
    the persistent browser session)."""
    def __init__(self, delay_seconds=6.0):
        self.was_blocked = False
        self.calls = 0

    def check(self, url) -> bool | None:
        self.calls += 1
        return True

    def polite_sleep(self):
        pass


def test_a_block_streak_aborts_instead_of_insisting(db, monkeypatch):
    """Regression: a "rest and continue" loop here once turned a hard DataDome
    block into an hours-long batch that hammered the portal from the same IP
    the scheduled scans use. Three refusals in a row must end the run."""
    props = [_property(db, str(100 + n)) for n in range(6)]

    class BlockingProbe(_FakeProbe):
        def check(self, url) -> bool | None:
            self.calls += 1
            self.was_blocked = True
            return None

    monkeypatch.setattr(availability_check, "AdProbe", BlockingProbe)
    summary = check_properties_availability(db, props, skip_recent_hours=0)

    assert summary["aborted"] is True
    assert summary["checked"] < len(props)
    # the block is not proof the ads are gone: statuses stay untouched
    assert all(p.status == "active" for p in props)


def test_the_probe_budget_caps_live_fetches_not_the_selection(db, monkeypatch):
    """"Select all" may hand over hundreds of ids; the cap must bound portal
    fetches per run while still walking the whole selection, so the next run
    (with the first slice freshly verified) resumes past it."""
    props = [_property(db, str(200 + n))
             for n in range(MAX_CHECKS_PER_CALL + 5)]

    monkeypatch.setattr(availability_check, "AdProbe", _FakeProbe)
    summary = check_properties_availability(db, props, skip_recent_hours=0)

    assert summary["capped"] is True
    assert summary["checked"] == MAX_CHECKS_PER_CALL
    assert summary["aborted"] is False


def test_recently_verified_properties_skip_without_spending_budget(db, monkeypatch):
    """Smart resume: a property whose listings were all seen minutes ago is
    counted online without a fetch. Sliced-by-ids capping used to make repeat
    runs re-spend the whole budget on the same first fifty ids."""
    fresh = [_property(db, str(300 + n), last_seen_hours_ago=0.5)
             for n in range(3)]
    stale = _property(db, "399", last_seen_hours_ago=48)

    probes = []

    class CountingProbe(_FakeProbe):
        def __init__(self, delay_seconds=6.0):
            super().__init__(delay_seconds)
            probes.append(self)

    monkeypatch.setattr(availability_check, "AdProbe", CountingProbe)
    summary = check_properties_availability(db, fresh + [stale],
                                            skip_recent_hours=6.0)

    assert summary["checked"] == 4
    assert summary["online"] == 4
    # only the stale one cost a portal fetch
    assert probes[0].calls == 1


def test_all_listings_gone_marks_the_property_gone(db, monkeypatch):
    prop = _property(db, "400")

    class GoneProbe(_FakeProbe):
        def check(self, url) -> bool | None:
            return False

    monkeypatch.setattr(availability_check, "AdProbe", GoneProbe)
    summary = check_properties_availability(db, [prop])

    assert summary["gone"] == 1
    assert prop.status == "gone"
    assert prop.gone_at is not None


def test_browser_primary_block_streak_aborts_without_grinding_curl_levers(db, monkeypatch):
    """Regression: a browser-first check whose headless browser is *itself*
    CAPTCHA-challenged used to grind for minutes with the progress bar frozen.
    On a block streak the code fell into the curl_cffi recovery levers — cookie
    refresh (relaunches a browser), TLS rotation (12s sleeps) — none of which
    can clear a browser CAPTCHA and none of which browser-primary check() even
    uses. It must abort straight on the streak (invariant 16)."""
    props = [_property(db, str(600 + n)) for n in range(10)]

    class BlockedBrowserProbe(_FakeProbe):
        def __init__(self, delay_seconds=6.0):
            super().__init__(delay_seconds)
            self._browser_primary = True

        def check(self, url) -> bool | None:
            self.calls += 1
            self.was_blocked = True
            self.last_error = "Blocked by DataDome (browser CAPTCHA)"
            return None

        def start_browser_session(self):
            return True

        def close_browser_session(self):
            pass

    probes = []

    def make_probe(*args, **kwargs):
        p = BlockedBrowserProbe(*args, **kwargs)
        probes.append(p)
        return p

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "curl_cffi cookie recovery must not run in browser-primary mode")

    monkeypatch.setattr(availability_check, "AdProbe", make_probe)
    monkeypatch.setattr(availability_check, "_try_cookie_recovery", fail_if_called)
    monkeypatch.setattr(availability_check, "load_settings",
                        lambda: {"availability_browser_first": True})

    summary = check_properties_availability(db, props, skip_recent_hours=0)

    assert summary["aborted"] is True
    # Stops the instant the streak trips: exactly BLOCK_STREAK_ABORT probes,
    # no grinding past it (the old code kept fetching for many more properties
    # while cycling the useless curl levers).
    assert probes[0].calls == BLOCK_STREAK_ABORT
    assert summary["checked"] < len(props)
    assert all(p.status == "active" for p in props)


def test_browser_first_setting_activates_browser_primary_on_probe(db, monkeypatch):
    prop = _property(db, "500")

    class BrowserProbe(_FakeProbe):
        def __init__(self, delay_seconds=6.0):
            super().__init__(delay_seconds)
            self._browser_primary = False
            self.started_browser = False

        def start_browser_session(self):
            self.started_browser = True
            return True

        def close_browser_session(self):
            pass

    probe_instances = []
    def fake_ad_probe(*args, **kwargs):
        p = BrowserProbe(*args, **kwargs)
        probe_instances.append(p)
        return p

    monkeypatch.setattr(availability_check, "AdProbe", fake_ad_probe)
    monkeypatch.setattr(availability_check, "load_settings", lambda: {"availability_browser_first": True})

    summary = check_properties_availability(db, [prop])
    assert summary["checked"] == 1
    assert len(probe_instances) == 1
    assert probe_instances[0].started_browser is True
    assert probe_instances[0]._browser_primary is True
