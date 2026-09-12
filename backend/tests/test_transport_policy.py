"""Transport ladder policy + persisted scraper health.

The pieces (TLS rotation, proxy pool, cookie recovery, browser, scrape API)
all existed; what was missing is the policy choosing between them from a
health signal, and any persisted visibility of the pipeline degrading. The
policy is pure (no network) exactly like the scheduler's decision helpers.
"""

import time
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import config
from app.database import Base
from app.models import ScraperHealthSnapshot, SearchProfile
from app.scrapers import transport_policy
from app.scrapers.base import BaseScraper, RawListing
from app.scrapers.transport import BlockedError
from app.services import scraper_health


def _settings(**overrides) -> dict:
    s = dict(config.DEFAULT_SETTINGS)
    s.update(overrides)
    return s


def _db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


class TestDecide:
    def test_no_key_stays_local_with_no_fallback(self):
        d = transport_policy.decide(0, _settings())
        assert d.start_on_api is False and d.allow_api_fallback is False
        assert "local" in d.label

    def test_proxy_pool_shows_in_the_label(self):
        d = transport_policy.decide(0, _settings(proxy_urls=["http://p:1"]))
        assert "proxy pool" in d.label

    def test_key_with_default_mode_starts_local_with_api_fallback(self):
        # "fallback" is the default: a saved key is a safety net, not a toll on
        # every fetch — credits are spent only when the free path fails
        d = transport_policy.decide(0, _settings(scrape_api_key="k"))
        assert d.start_on_api is False and d.allow_api_fallback is True

    def test_always_mode_routes_everything_through_the_provider(self):
        d = transport_policy.decide(0, _settings(scrape_api_key="k", scrape_api_mode="always"))
        assert d.start_on_api is True

    def test_fallback_mode_starts_local_when_healthy(self):
        d = transport_policy.decide(0, _settings(scrape_api_key="k", scrape_api_mode="fallback"))
        assert d.start_on_api is False and d.allow_api_fallback is True

    def test_fallback_mode_escalates_on_the_streak(self):
        s = _settings(
            scrape_api_key="k",
            scrape_api_mode="fallback",
            transport_escalate_after_failures=2,
        )
        assert transport_policy.decide(1, s).start_on_api is False
        assert transport_policy.decide(2, s).start_on_api is True
        assert "escalated" in transport_policy.decide(2, s).label

    def test_recovery_descends_to_the_free_path(self):
        # the streak resets to 0 on a clean scan (invariant 11), so descending
        # is just deciding again with the reset streak
        s = _settings(scrape_api_key="k", scrape_api_mode="fallback")
        assert transport_policy.decide(0, s).start_on_api is False


class _AlwaysBlocked(BaseScraper):
    portal = "test"

    def __init__(self):
        super().__init__()
        self.api_calls = 0

    def _fetch_via_scrape_api(self, url: str, provider: str, key: str) -> str:
        self.api_calls += 1
        return "<html>solved</html>"

    def _fetch_once(self, url: str) -> str:
        from app.scrapers.transport import scrape_api_config

        provider, key = scrape_api_config()
        if key and self.use_scrape_api:
            return self._fetch_via_scrape_api(url, provider, key)
        raise BlockedError("test: local always blocked")


class _AlwaysBlockedProbe(_AlwaysBlocked):
    """The same always-refused transport wearing the ad-probe's portal name.

    That name is the whole point: `_rotate_session` wraps the impersonation
    index around instead of returning False for `portal == "ad-probe"`, because
    one probe is reused across a whole batch of ads and the next ad must not
    inherit an exhausted ladder. `fetch` has to bound itself in spite of that.
    """

    portal = "ad-probe"

    def __init__(self):
        super().__init__()
        self.local_calls = 0

    def _fetch_once(self, url: str) -> str:
        self.local_calls += 1
        # A regression is an endless loop, which would hang the suite instead
        # of failing it: stop well short of that and fail loudly.
        assert self.local_calls < 100, "fetch() never stopped rotating"
        return super()._fetch_once(url)


class TestFetchLadder:
    def test_exhausted_local_ladder_escalates_to_api_once(self):
        config.save_settings({"scrape_api_key": "k", "scrape_api_mode": "fallback"})
        scraper = _AlwaysBlocked()
        scraper.use_scrape_api = False  # what the scanner sets when healthy
        html = scraper.fetch("https://example.invalid/x")
        assert html == "<html>solved</html>"
        assert scraper.api_calls == 1
        assert scraper.use_scrape_api is True  # sticky for the rest of the scan

    def test_no_key_still_raises_after_rotation(self):
        scraper = _AlwaysBlocked()
        scraper.use_scrape_api = False
        try:
            scraper.fetch("https://example.invalid/x")
            raise AssertionError("must raise BlockedError")
        except BlockedError:
            pass

    def test_a_wrapping_rotation_still_gives_up(self, monkeypatch):
        """Regression: `_rotate_session` wraps around for the ad-probe rather
        than answering False, so `fetch` read "rotated fine" for ever and never
        reached the raise. `search_builder.probe_zone_page` fetches through an
        AdProbe and fails open on BlockedError — with the portal blocking, that
        handler never ran and "Generate" hung instead of falling back to the
        /cerca/ URL, re-earning a 403 per cycle on the residential IP."""
        monkeypatch.setattr(time, "sleep", lambda _s: None)  # the wrap's 4s rest
        scraper = _AlwaysBlockedProbe()
        scraper.use_scrape_api = False

        with pytest.raises(BlockedError):
            scraper.fetch("https://example.invalid/x")

        # one full pass of the ladder, not one pass per wrap, and not for ever
        assert scraper.local_calls <= len(scraper.impersonations) + 1

    def test_a_wrapping_rotation_still_escalates_to_the_api(self, monkeypatch):
        """The other half: the escalation lives behind the same exhausted-ladder
        branch, so a wrapping rotation locked a user with a configured
        scrape-API key out of the rung they had paid for."""
        monkeypatch.setattr(time, "sleep", lambda _s: None)
        config.save_settings({"scrape_api_key": "k", "scrape_api_mode": "fallback"})
        scraper = _AlwaysBlockedProbe()
        scraper.use_scrape_api = False

        assert scraper.fetch("https://example.invalid/x") == "<html>solved</html>"
        assert scraper.api_calls == 1


class TestHealthRecording:
    def test_accumulates_into_one_row_per_day_and_portal(self):
        db = _db()
        scraper_health.record_scan(db, "immobiliare", "ok", "local (curl_cffi)")
        scraper_health.record_scan(db, "immobiliare", "blocked", "local (curl_cffi)")
        scraper_health.record_scan(db, "immobiliare", "error", "managed scrape API")
        scraper_health.record_scan(db, "idealista", "ok", "local (curl_cffi)")
        db.commit()

        rows = list(db.scalars(select(ScraperHealthSnapshot)))
        assert len(rows) == 2
        immo = next(r for r in rows if r.portal == "immobiliare")
        assert immo.attempts == 3
        assert immo.successes == 1 and immo.blocked == 1 and immo.errors == 1
        assert immo.last_transport == "managed scrape API"

    def test_get_health_reports_rates_and_streaks(self):
        db = _db()
        db.add(
            SearchProfile(
                name="p1",
                portal="immobiliare",
                search_url="https://www.immobiliare.it/vendita-case/milano/",
                is_active=True,
                consecutive_failures=3,
                last_run_status="blocked",
            )
        )
        scraper_health.record_scan(db, "immobiliare", "blocked", "local (curl_cffi)")
        scraper_health.record_scan(db, "immobiliare", "ok", "local (curl_cffi)")
        db.commit()

        health = scraper_health.get_health(db)
        assert health["portals"][0]["portal"] == "immobiliare"
        assert health["portals"][0]["attempts"] == 2
        assert health["portals"][0]["block_rate"] == 0.5
        assert health["profiles"][0]["consecutive_failures"] == 3

    def test_window_excludes_old_rows(self):
        db = _db()
        old = ScraperHealthSnapshot(
            captured_on=(datetime.now(UTC) - timedelta(days=90)).date(),
            portal="immobiliare",
            attempts=5,
            blocked=5,
        )
        db.add(old)
        db.commit()
        health = scraper_health.get_health(db, days=30)
        assert health["portals"] == []

    def test_recording_is_fail_open(self):
        # a DB error while recording must not raise into the scan
        class Boom:
            def scalar(self, *a, **k):
                raise RuntimeError("boom")

        scraper_health.record_scan(Boom(), "immobiliare", "ok", "x")  # type: ignore[arg-type]


class TestCreditCeiling:
    """The money half of the policy.

    Scans run on a timer and the paid rung bills per page, so nobody ever
    decides to spend a free plan — it just goes. The ceiling is what turns that
    into a decision, and it has to hold on the *fallback* too: a blocked ladder
    is exactly when rung 4 gets reached for.
    """

    def test_no_ceiling_leaves_the_provider_its_own_quota_as_the_only_limit(self):
        s = _settings(scrape_api_key="k", scrape_api_monthly_credits=0)
        assert transport_policy.monthly_credit_budget(s) == 0
        assert transport_policy.budget_spent(10_000, s) is False
        assert transport_policy.decide(0, s, 10_000).allow_api_fallback is True

    def test_a_ceiling_that_is_not_a_number_is_no_ceiling(self):
        # settings.json is a file on disk that can be edited by hand, and a typo
        # in it must not become a ceiling of zero that quietly pauses the paid
        # rung for the rest of the month.
        for nonsense in ("", "lots", None, -5):
            s = _settings(scrape_api_monthly_credits=nonsense)
            assert transport_policy.monthly_credit_budget(s) == 0

    def test_reaching_the_ceiling_takes_the_paid_rung_off_the_ladder(self):
        s = _settings(scrape_api_key="k", scrape_api_mode="always", scrape_api_monthly_credits=900)
        assert transport_policy.decide(0, s, 875).start_on_api is True
        spent = transport_policy.decide(0, s, 900)
        # Both flags and not just the first: leaving the fallback on would keep
        # every blocked scan paying, and blocked is when it escalates.
        assert spent.start_on_api is False and spent.allow_api_fallback is False
        assert "paused" in spent.label and "900" in spent.label

    def test_the_ceiling_also_stops_the_escalation_a_failure_streak_would_earn(self):
        s = _settings(
            scrape_api_key="k",
            scrape_api_mode="fallback",
            transport_escalate_after_failures=2,
            scrape_api_monthly_credits=900,
        )
        assert transport_policy.decide(5, s, 100).start_on_api is True
        assert transport_policy.decide(5, s, 900).start_on_api is False

    def test_asked_without_the_budget_it_answers_without_the_budget(self):
        # How the health panel works out *which* searches the ceiling is
        # currently costing something: the same rules, with the money left out.
        s = _settings(scrape_api_key="k", scrape_api_mode="always", scrape_api_monthly_credits=1)
        assert transport_policy.decide(0, s).start_on_api is True


class TestCreditAccounting:
    def test_a_scan_records_what_the_provider_billed_it(self):
        db = _db()
        scraper_health.record_scan(
            db, "immobiliare", "ok", "managed scrape API", credits=75, api_calls=3
        )
        scraper_health.record_scan(
            db, "immobiliare", "ok", "managed scrape API", credits=25, api_calls=1
        )
        scraper_health.record_scan(db, "idealista", "ok", "local (curl_cffi)")
        db.commit()

        month = scraper_health.credits_this_month(db)
        assert month["spent"] == 100 and month["calls"] == 4
        # Nothing estimated: every one of those calls came with a price on it.
        assert month["estimated"] == 0
        immo = next(
            p for p in scraper_health.get_health(db)["portals"] if p["portal"] == "immobiliare"
        )
        assert immo["api_credits"] == 100 and immo["api_calls"] == 4

    def test_what_was_spent_before_the_first_belongs_to_the_month_before(self):
        # A calendar month rather than a rolling thirty days, because that is
        # the unit the providers reset a free plan on.
        db = _db()
        db.add(
            ScraperHealthSnapshot(
                captured_on=date(2026, 2, 27), portal="immobiliare", attempts=1, api_credits=800
            )
        )
        db.add(
            ScraperHealthSnapshot(
                captured_on=date(2026, 3, 2), portal="immobiliare", attempts=1, api_credits=50
            )
        )
        db.commit()
        assert scraper_health.credits_this_month(db, date(2026, 3, 5))["spent"] == 50

    def test_the_budget_names_the_searches_the_pause_is_costing(self):
        db = _db()
        db.add(
            SearchProfile(
                name="Trilocale Navigli",
                portal="immobiliare",
                search_url="https://www.immobiliare.it/vendita-case/milano/",
                is_active=True,
            )
        )
        db.add(
            SearchProfile(
                name="Archiviata",
                portal="idealista",
                search_url="https://www.idealista.it/vendita-case/milano/",
                is_active=False,
            )
        )
        for day, credits in ((date(2026, 3, 3), 400), (date(2026, 3, 7), 400)):
            db.add(
                ScraperHealthSnapshot(
                    captured_on=day, portal="immobiliare", attempts=1, api_credits=credits
                )
            )
        db.commit()

        s = _settings(scrape_api_key="k", scrape_api_mode="always", scrape_api_monthly_credits=750)
        budget = scraper_health.credit_budget(db, s, date(2026, 3, 9))
        assert budget["reached"] is True and budget["spent"] == 800
        # Since when: the day the running total crossed the ceiling, not the day
        # it was noticed and not the first day any money was spent at all.
        assert budget["reached_on"] == "2026-03-07"
        # A paused search is one whose next scan would have been paid for, so an
        # archived one is nobody's loss.
        assert [x["name"] for x in budget["searches"]] == ["Trilocale Navigli"]

    def test_under_the_ceiling_nobody_is_named_and_no_date_is_claimed(self):
        db = _db()
        scraper_health.record_scan(db, "immobiliare", "ok", "managed scrape API", credits=25)
        db.commit()
        budget = scraper_health.credit_budget(
            db, _settings(scrape_api_key="k", scrape_api_monthly_credits=900)
        )
        assert budget["reached"] is False
        assert budget["reached_on"] == "" and budget["searches"] == []

    def test_a_price_the_provider_never_stated_is_carried_as_estimated(self):
        # Invariant 26 applied to money: the total may only be stated flatly
        # when the whole of it came off a receipt.
        db = _db()
        scraper_health.record_scan(
            db, "immobiliare", "ok", "managed scrape API", credits=25, credits_estimated=25
        )
        db.commit()
        assert scraper_health.credits_this_month(db)["estimated"] == 25
        assert scraper_health.get_health(db)["portals"][0]["api_credits_estimated"] == 25


class _PaidPages(BaseScraper):
    """A scraper on which a page fetched is a page paid for.

    Nothing here goes near a provider: what is under test is *which pages are
    asked for at all*, since the bill is a count of exactly that.
    """

    portal = "test"

    def __init__(self, pages: int = 3):
        super().__init__(delay_seconds=0, max_pages=pages)
        self.fetched: list[str] = []

    def fetch(self, url: str) -> str:
        self.fetched.append(url)
        return "<html></html>"

    def parse_page(self, html: str, page_url: str):
        page = self.fetched.index(page_url) + 1
        listings = [
            RawListing(portal=self.portal, portal_id=f"{page}-{n}", url=f"https://x/{page}/{n}")
            for n in range(2)
        ]
        return listings, "test"

    def next_page_url(self, search_url: str, page: int) -> str | None:
        return f"{search_url}?page={page}"


class TestEarlyStopComesBeforeTheBill:
    """`stop_when_nothing_new` is decided on page 1, before page 2 is asked for.

    On the paid rung the order is the whole point: deciding after the fetch
    would buy the very page that proves the walk should already have ended.
    """

    def test_a_page_with_nothing_new_ends_the_walk_without_asking_for_the_next(self):
        scraper = _PaidPages()
        result = scraper.scrape("https://x/search", known=lambda _listing: True)
        assert result.stopped_early is True
        assert scraper.fetched == ["https://x/search"]

    def test_a_full_sweep_does_pay_for_the_rest(self):
        # The other half, or the test above would pass just as well on a
        # scraper that never walked anywhere.
        scraper = _PaidPages()
        result = scraper.scrape("https://x/search")
        assert result.stopped_early is False
        assert len(scraper.fetched) == 3
