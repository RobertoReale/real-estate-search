"""Transport ladder policy + persisted scraper health (plan-resilience B.3/B.5).

The pieces (TLS rotation, proxy pool, cookie recovery, browser, scrape API)
all existed; what was missing is the policy choosing between them from a
health signal, and any persisted visibility of the pipeline degrading. The
policy is pure (no network) exactly like the scheduler's decision helpers.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import config
from app.database import Base
from app.models import ScraperHealthSnapshot, SearchProfile
from app.scrapers import transport_policy
from app.scrapers.base import BaseScraper, BlockedError
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
        from app.scrapers.base import scrape_api_config

        provider, key = scrape_api_config()
        if key and self.use_scrape_api:
            return self._fetch_via_scrape_api(url, provider, key)
        raise BlockedError("test: local always blocked")


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
