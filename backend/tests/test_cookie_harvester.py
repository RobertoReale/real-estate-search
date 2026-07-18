"""Cookie harvester: the browser launch itself cannot be tested offline (it
needs a real browser and a live DataDome challenge, which the project has never
simulated — see developer notes §Testing). What IS testable is every decision *around*
the launch: which cookie to pick, when a cookie is stale, and the scanner's
opt-in gating. Those are the parts that would silently misbehave, so those are
the parts covered here."""

from datetime import UTC, datetime, timedelta

import pytest

from app.services import cookie_harvester as ch


def test_pick_datadome_returns_the_token_value():
    cookies = [
        {"name": "sessionid", "value": "abc"},
        {"name": "datadome", "value": "aVeryLongClearanceTokenValue123"},
    ]
    assert ch._pick_datadome(cookies) == "aVeryLongClearanceTokenValue123"


def test_pick_datadome_ignores_placeholder_and_missing():
    # some challenge pages set a stub `datadome` before clearance: a one-char
    # value is not a token to inject
    assert ch._pick_datadome([{"name": "datadome", "value": "x"}]) is None
    assert ch._pick_datadome([{"name": "other", "value": "y" * 20}]) is None
    assert ch._pick_datadome([]) is None


def test_cookie_is_stale_true_when_unknown_or_unparseable():
    now = datetime(2026, 7, 11, tzinfo=UTC)
    # no timestamp: cannot prove freshness, so refresh
    assert ch.cookie_is_stale("", 50, now) is True
    assert ch.cookie_is_stale(None, 50, now) is True
    assert ch.cookie_is_stale("not-a-date", 50, now) is True


def test_cookie_is_stale_respects_ttl():
    now = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)
    fresh = (now - timedelta(minutes=10)).isoformat()
    old = (now - timedelta(minutes=55)).isoformat()
    assert ch.cookie_is_stale(fresh, 50, now) is False
    assert ch.cookie_is_stale(old, 50, now) is True


def test_cookie_is_stale_reattaches_utc_to_naive_timestamp():
    # save_settings writes an aware ISO string, but a hand-edited settings.json
    # could carry a naive one; comparing naive vs aware would raise
    now = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)
    naive_recent = datetime(2026, 7, 11, 11, 55).isoformat()  # no tzinfo
    assert ch.cookie_is_stale(naive_recent, 50, now) is False


def test_maybe_auto_refresh_is_noop_when_disabled():
    # opt-in: a scan must never launch a browser the user did not enable, even
    # if Playwright happens to be installed
    assert ch.maybe_auto_refresh({"datadome_auto_refresh": False}) is False


def test_maybe_auto_refresh_skips_a_fresh_cookie(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(ch, "is_available", lambda: True)
    monkeypatch.setattr(
        ch,
        "refresh_into_settings",
        lambda **_: called.__setitem__("n", called["n"] + 1) or {"ok": True},
    )
    fresh = datetime.now(UTC).isoformat()
    refreshed = ch.maybe_auto_refresh(
        {
            "datadome_auto_refresh": True,
            "datadome_cookie": "sometoken",
            "datadome_cookie_updated_at": fresh,
            "datadome_cookie_ttl_minutes": 50,
        }
    )
    assert refreshed is False
    assert called["n"] == 0, "a still-fresh cookie must not trigger a browser launch"


def test_maybe_auto_refresh_harvests_a_stale_cookie(monkeypatch):
    monkeypatch.setattr(ch, "is_available", lambda: True)
    monkeypatch.setattr(ch, "refresh_into_settings", lambda **_: {"ok": True})
    stale = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    assert (
        ch.maybe_auto_refresh(
            {
                "datadome_auto_refresh": True,
                "datadome_cookie": "sometoken",
                "datadome_cookie_updated_at": stale,
                "datadome_cookie_ttl_minutes": 50,
            }
        )
        is True
    )


def test_refresh_waits_longer_for_a_human_than_for_headless(monkeypatch):
    """The visible grab exists so a human can solve a CAPTCHA, but they first
    have to notice the window: with the headless 45s deadline the harvest
    regularly expired mid-solve, failing the exact case it was built for."""
    seen = {}

    def fake_harvest(portal, headless, timeout_seconds):
        seen[headless] = timeout_seconds
        return ch.HarvestResult(error="stop here")

    monkeypatch.setattr(ch, "harvest", fake_harvest)
    ch.refresh_into_settings(headless=False)
    ch.refresh_into_settings(headless=True)
    assert seen[True] == ch.HEADLESS_TIMEOUT_SECONDS
    assert seen[False] == ch.HEADFUL_TIMEOUT_SECONDS
    assert seen[False] > seen[True]


def test_harvest_fails_open_when_playwright_absent(monkeypatch):
    # the whole point of the optional dependency: no Playwright must degrade to
    # a clear message, never an ImportError crashing a scan
    monkeypatch.setattr(ch, "is_available", lambda: False)
    result = ch.harvest()
    assert result.cookie is None
    assert "Playwright" in result.error


def test_ensure_browsers_path_and_find_chromium(monkeypatch, tmp_path):
    # simulate a fake browser path candidate
    fake_candidate = tmp_path / "browser_binaries"
    fake_candidate.mkdir()
    fake_chrome_dir = fake_candidate / "chromium-1234" / "chrome-win"
    fake_chrome_dir.mkdir(parents=True)
    fake_exe = fake_chrome_dir / "chrome.exe"
    fake_exe.write_text("fake binary")

    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(fake_candidate))
    found = ch._find_chromium_executable()
    assert found == str(fake_exe)


def test_update_settings_preserves_harvester_flag(monkeypatch):
    from app import schemas
    from app.main import get_settings, update_settings

    monkeypatch.setattr(ch, "is_available", lambda: True)

    # get_settings should return datadome_harvester_available: true
    get_resp = get_settings()
    assert get_resp.get("datadome_harvester_available") is True

    # update_settings should also return datadome_harvester_available: true and save availability_browser_first
    put_resp = update_settings(
        schemas.SettingsIn(datadome_auto_refresh=True, availability_browser_first=True)
    )
    assert put_resp.get("datadome_harvester_available") is True
    assert put_resp.get("availability_browser_first") is True


def test_harvest_does_not_abort_on_403_when_headful(monkeypatch):
    class FakeResp:
        status = 403

    class FakePage:
        def __init__(self):
            self.title_val = "geo.captcha-delivery.com"
            self.checks = 0

        def goto(self, url, **kwargs):
            return FakeResp()

        def title(self):
            self.checks += 1
            if self.checks > 2:
                self.title_val = "Immobiliare.it - Annunci immobiliari"
            return self.title_val

        def content(self):
            return self.title_val

        def wait_for_timeout(self, ms):
            pass

    class FakeCtx:
        pages: list = []
        _page: FakePage

        def new_page(self):
            return FakePage()

        def cookies(self):
            if hasattr(self, "_page") and self._page.checks > 2:
                return [{"name": "datadome", "value": "clearanceCookieAfterSolving12345"}]
            return []

        def close(self):
            pass

    fake_ctx = FakeCtx()
    fake_ctx._page = FakePage()
    fake_ctx.pages = [fake_ctx._page]

    class FakePW:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakePW())
    monkeypatch.setattr(ch, "_launch", lambda p, headless: fake_ctx)

    res = ch._harvest_inner("immobiliare", headless=False, timeout_seconds=5.0)
    assert not res.error
    assert res.cookie == "clearanceCookieAfterSolving12345"


def test_harvest_inner_stops_promptly_when_cancelled(monkeypatch):
    """Regression: not every hard block page has a solvable widget -- a static
    "access is temporarily restricted" wall never stops mentioning "captcha"
    in its own resource URLs, so a headful grab facing one used to poll for
    the full timeout with no way to stop it from the UI, leaving the visible
    browser window stuck open. `request_cancel_harvest` must be picked up
    within one poll instead of running out the clock."""

    class FakeResp:
        status = 403

    class FakePage:
        def goto(self, url, **kwargs):
            return FakeResp()

        def content(self):
            return "geo.captcha-delivery.com blocked captcha"

        def title(self):
            return "captcha"

        def wait_for_timeout(self, ms):
            pass

    class FakeCtx:
        def __init__(self):
            self.pages = [FakePage()]

        def cookies(self):
            return []

        def close(self):
            pass

    monkeypatch.setattr(ch, "_launch", lambda p, headless: FakeCtx())
    ch.request_cancel_harvest()
    try:
        import time

        start = time.monotonic()
        res = ch._harvest_inner("immobiliare", headless=False, timeout_seconds=5.0)
        elapsed = time.monotonic() - start

        assert res.error == "Cancelled."
        assert elapsed < 1.0
    finally:
        ch._harvest_cancel_event.clear()


def test_harvest_clears_a_stale_cancel_flag_before_running(monkeypatch):
    """A cancel from a previous (already-finished) grab must not silently
    cancel the next one."""
    ch._harvest_cancel_event.set()
    monkeypatch.setattr(ch, "is_available", lambda: True)

    seen = {}

    def fake_inner(portal, headless, timeout_seconds):
        seen["cancel_set"] = ch._harvest_cancel_event.is_set()
        return ch.HarvestResult(cookie="abc123token")

    monkeypatch.setattr(ch, "_harvest_inner", fake_inner)
    result = ch.harvest()

    assert seen["cancel_set"] is False
    assert result.cookie == "abc123token"


def test_use_camoufox_respects_the_engine_setting(monkeypatch):
    """`browser_engine` picks the engine: "camoufox" forces it, "chromium" pins
    the old behaviour, and "auto" (default) follows whether the package is
    installed — so `pip install camoufox` is itself the opt-in."""
    monkeypatch.setattr(ch, "is_camoufox_available", lambda: True)
    monkeypatch.setattr("app.config.load_settings", lambda: {"browser_engine": "chromium"})
    assert ch._use_camoufox() is False
    monkeypatch.setattr("app.config.load_settings", lambda: {"browser_engine": "camoufox"})
    assert ch._use_camoufox() is True
    monkeypatch.setattr("app.config.load_settings", lambda: {"browser_engine": "auto"})
    assert ch._use_camoufox() is True
    monkeypatch.setattr(ch, "is_camoufox_available", lambda: False)
    assert ch._use_camoufox() is False


def test_close_ctx_prefers_the_camoufox_owner():
    """A Camoufox context owns its own Playwright and must be torn down through
    its launcher's __exit__; a Chromium context is closed directly."""
    events = []

    class Owner:
        def __exit__(self, *_a):
            events.append("owner_exit")

    class Ctx:
        _camoufox_owner: object = None

        def close(self):
            events.append("close")

    chromium_ctx = Ctx()
    ch._close_ctx(chromium_ctx)
    assert events == ["close"]

    events.clear()
    camoufox_ctx = Ctx()
    camoufox_ctx._camoufox_owner = Owner()
    ch._close_ctx(camoufox_ctx)
    assert events == ["owner_exit"]


def test_launch_falls_back_to_chromium_when_camoufox_fails(monkeypatch, tmp_path):
    """Camoufox must never break a working check: if its launch fails (its
    browser binary may simply not be fetched yet), `_launch` carries on with
    Chromium and tags the context so diagnostics still read right."""
    monkeypatch.setattr(ch, "_ensure_browsers_path", lambda: None)
    monkeypatch.setattr(ch, "PROFILE_DIR", tmp_path)
    monkeypatch.setattr(ch, "_use_camoufox", lambda: True)
    monkeypatch.setattr(ch, "_launch_camoufox", lambda headless: None)  # simulate failure
    monkeypatch.setattr(ch, "_find_chromium_executable", lambda: None)

    made = {}

    class FakeCtx:
        def add_init_script(self, _s):
            pass

    class FakeChromium:
        def launch_persistent_context(self, **kwargs):
            made["headless"] = kwargs.get("headless")
            return FakeCtx()

    class FakeP:
        chromium = FakeChromium()

    ctx = ch._launch(lambda: FakeP(), headless=True)
    assert made["headless"] is True
    assert getattr(ctx, "_engine_label", None) == "chromium"


def test_launch_does_not_start_plain_playwright_before_trying_camoufox(monkeypatch, tmp_path):
    """Regression: `_launch` used to receive an already-started plain Playwright
    sync instance from its caller. But Camoufox is itself built on Playwright's
    sync API, which refuses a second instance in a thread that already has one
    running — so that pre-started instance made Camoufox fail its own launch
    on every single check, with 'Sync API inside the asyncio loop', silently
    degrading to Chromium every time despite being installed and selected. The
    fix: `p_factory` must not be called at all when Camoufox succeeds."""
    monkeypatch.setattr(ch, "_ensure_browsers_path", lambda: None)
    monkeypatch.setattr(ch, "PROFILE_DIR", tmp_path)
    monkeypatch.setattr(ch, "_use_camoufox", lambda: True)

    class FakeCamoufoxCtx:
        _engine_label = "camoufox"

    monkeypatch.setattr(ch, "_launch_camoufox", lambda headless: FakeCamoufoxCtx())

    factory_calls = []

    def p_factory():
        factory_calls.append(1)
        raise AssertionError("plain Playwright must not be started when Camoufox succeeds")

    ctx = ch._launch(p_factory, headless=True)
    assert factory_calls == []
    assert getattr(ctx, "_engine_label", None) == "camoufox"


def test_launch_stops_playwright_when_every_channel_fails(monkeypatch, tmp_path):
    """Regression: when chrome/msedge/bundled Chromium all fail to launch (e.g.
    the Windows service runs as LocalSystem, whose profile has no browser
    binaries), `_launch` used to raise without stopping the plain Playwright
    instance it had just started. That leftover instance kept the calling
    thread marked as 'already hosting a Playwright sync API' — the next launch
    attempt on the same (often reused) thread then failed with the misleading
    'Sync API inside the asyncio loop' error, even for Camoufox, which starts
    its own separate instance. `_launch` must stop what it started before
    propagating the failure."""
    monkeypatch.setattr(ch, "_ensure_browsers_path", lambda: None)
    monkeypatch.setattr(ch, "PROFILE_DIR", tmp_path)
    monkeypatch.setattr(ch, "_use_camoufox", lambda: False)
    monkeypatch.setattr(ch, "_find_chromium_executable", lambda: None)

    stopped = []

    class FakeChromium:
        def launch_persistent_context(self, **kwargs):
            raise RuntimeError("Executable doesn't exist")

    class FakeP:
        chromium = FakeChromium()

        def stop(self):
            stopped.append(1)

    with pytest.raises(RuntimeError):
        ch._launch(lambda: FakeP(), headless=True)
    assert stopped == [1]
