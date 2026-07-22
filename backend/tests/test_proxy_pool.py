"""Proxy pool: IP diversity for the anti-bot transport.

The single `proxy_url` was a second single point of failure next to the
residential IP: DataDome scores IP reputation, so one blocked exit address
took every subsequent fetch down with it. The pool rotates on block with a
per-proxy cool-down; an empty pool must stay byte-for-byte today's direct
behavior.
"""

from app import config
from app.scrapers import base
from app.scrapers.base import BaseScraper, BlockedError, ProxyPool


def _settings(**overrides) -> dict:
    s = dict(config.DEFAULT_SETTINGS)
    s.update(overrides)
    return s


class TestConfiguredProxies:
    def test_empty_settings_mean_no_pool(self):
        assert ProxyPool.configured_proxies(_settings()) == []

    def test_proxy_url_is_a_one_element_shorthand(self):
        s = _settings(proxy_url="http://one:3128")
        assert ProxyPool.configured_proxies(s) == ["http://one:3128"]

    def test_pool_merges_legacy_single_first_and_dedupes(self):
        s = _settings(
            proxy_url=" http://one:3128 ",
            proxy_urls=["http://one:3128", "", "http://two:3128", None],
        )
        assert ProxyPool.configured_proxies(s) == ["http://one:3128", "http://two:3128"]


class TestPick:
    def test_empty_pool_picks_none(self):
        assert ProxyPool().pick(_settings()) is None

    def test_prefers_configured_order(self):
        pool = ProxyPool()
        s = _settings(proxy_urls=["http://one:1", "http://two:2"])
        assert pool.pick(s) == "http://one:1"

    def test_burned_proxy_is_skipped_until_cooldown_expires(self):
        pool = ProxyPool(cooldown_seconds=3600)
        s = _settings(proxy_urls=["http://one:1", "http://two:2"])
        pool.burn("http://one:1")
        assert pool.pick(s) == "http://two:2"
        # cool-down over: the preferred proxy is eligible again
        pool._burned_at["http://one:1"] -= 7200
        assert pool.pick(s) == "http://one:1"

    def test_all_burned_falls_back_to_least_recently_burned_never_direct(self):
        # With every proxy cooling the pool must still answer with a proxy:
        # the user configured a pool expecting traffic to be proxied, and a
        # silent direct connection would expose the residential IP.
        pool = ProxyPool(cooldown_seconds=3600)
        s = _settings(proxy_urls=["http://one:1", "http://two:2"])
        pool.burn("http://one:1")
        pool.burn("http://two:2")
        assert pool.pick(s) == "http://one:1"

    def test_burn_none_is_a_noop(self):
        pool = ProxyPool()
        pool.burn(None)
        assert pool._burned_at == {}


class _BlockedScraper(BaseScraper):
    portal = "test"

    def _fetch_once(self, url: str) -> str:
        raise BlockedError("test: always blocked")


class TestSessionIntegration:
    def test_no_pool_means_direct_session(self):
        scraper = BaseScraper()
        assert scraper._current_proxy is None
        assert not scraper.session.proxies

    def test_session_is_sticky_on_one_proxy(self, monkeypatch):
        monkeypatch.setattr(
            base,
            "proxy_pool",
            ProxyPool(cooldown_seconds=3600),
        )
        config.save_settings({"proxy_urls": ["http://one:1", "http://two:2"]})
        scraper = BaseScraper()
        assert scraper._current_proxy == "http://one:1"
        assert scraper.session.proxies == {"http": "http://one:1", "https": "http://one:1"}

    def test_block_burns_the_proxy_and_rotation_moves_to_the_next(self, monkeypatch):
        fresh = ProxyPool(cooldown_seconds=3600)
        monkeypatch.setattr(base, "proxy_pool", fresh)
        config.save_settings({"proxy_urls": ["http://one:1", "http://two:2"]})
        scraper = _BlockedScraper()
        assert scraper._current_proxy == "http://one:1"
        try:
            scraper.fetch("https://example.invalid/x")
        except BlockedError:
            pass
        # every rotation burned its proxy; the first rotation moved to proxy two
        assert "http://one:1" in fresh._burned_at
        assert "http://two:2" in fresh._burned_at
