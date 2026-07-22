"""The BrowserEngine seam (scrapers/browser_engine.py): the probe and harvest
logic must be engine-agnostic. A FakeEngine speaking only the Protocol surface
proves the check's block detection, gone detection, cookie export and
fail-open behavior never reach for Playwright specifics — which is exactly
what lets a future non-Playwright engine (Nodriver, SeleniumBase-CDP) drop in
as an adapter instead of a fork.

Real engine launches stay in the documented untestable-network bucket, like
the Camoufox path.
"""

from app.scrapers.base import AdProbe
from app.services import cookie_harvester


class FakeEngine:
    engine_label = "fake"

    def __init__(self, status=200, html="<html><body>the ad</body></html>", final_url=None):
        self.status = status
        self.html = html
        self.final_url = final_url
        self.opened: list[str] = []
        self.cookie_reads = 0

    def open(self, url, referer=None, timeout_ms=25000):
        self.opened.append(url)
        return self.status

    def content(self):
        return self.html

    def title(self):
        return ""

    def url(self):
        return self.final_url or self.opened[-1]

    def cookies(self, url=None):
        self.cookie_reads += 1
        return [{"name": "datadome", "value": "exported-clearance-token-123"}]

    def humanize(self, rng=None):
        pass

    def wait(self, ms):
        pass

    def close(self):
        pass


def _probe_with(engine) -> AdProbe:
    probe = AdProbe()
    probe._engine = engine
    probe._browser_warmed_hosts = {"www.immobiliare.it"}
    return probe


AD = "https://www.immobiliare.it/annunci/12345/"


def test_fake_engine_live_ad_and_cookie_export():
    eng = FakeEngine(status=200)
    probe = _probe_with(eng)
    assert probe._browser_check_inner(AD) is True
    # The cookie the engine earned must be exported into the curl session:
    # an engine whose cookie can't be reused buys nothing for rung 0.
    assert eng.cookie_reads > 0
    assert "datadome" in str(probe.session.cookies)


def test_fake_engine_404_is_gone():
    assert _probe_with(FakeEngine(status=404))._browser_check_inner(AD) is False


def test_fake_engine_captcha_is_a_block_not_a_removal():
    probe = _probe_with(FakeEngine(status=200, html="<html>please solve the captcha</html>"))
    probe._browser_headful = False
    assert probe._browser_check_inner(AD) is None
    assert probe.was_blocked is True


def test_fake_engine_open_raising_fails_open():
    class ExplodingEngine(FakeEngine):
        def open(self, url, referer=None, timeout_ms=25000):
            raise RuntimeError("engine crashed mid-launch")

    probe = _probe_with(ExplodingEngine())
    # Invariant 16: an engine failure is "could not tell", never a crash and
    # never a wrong "gone".
    assert probe._browser_check_inner(AD) is None


def test_harvest_block_rule_is_engine_agnostic():
    # _is_page_blocked speaks the engine surface (title/content) only, so the
    # one block rule serves every engine.
    assert cookie_harvester._is_page_blocked(FakeEngine(html="geo.captcha-delivery.com …")) is True
    assert cookie_harvester._is_page_blocked(FakeEngine(html="<html>homepage</html>")) is False
