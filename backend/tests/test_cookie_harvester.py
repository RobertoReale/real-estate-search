"""Cookie harvester: the browser launch itself cannot be tested offline (it
needs a real browser and a live DataDome challenge, which the project has never
simulated — see developer notes §Testing). What IS testable is every decision *around*
the launch: which cookie to pick, that headless never gets to launch at all, and
the bookkeeping that records whether the cookie in hand still works. Those are
the parts that would silently misbehave, so those are the parts covered here."""

from types import SimpleNamespace

import pytest

from app.config import load_settings, save_settings
from app.scrapers import base
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


def test_refresh_refuses_headless_without_launching_anything(monkeypatch):
    """A headless grab is not a degraded grab, it is a destructive one: measured
    on 2026-09-12 it drew a `t=bv` CAPTCHA (nothing to solve) and burned the
    working cookie it presented on the way in. So the refusal has to come
    *before* the browser, not after a failed harvest."""

    def boom(*_a, **_k):
        raise AssertionError("a headless grab must never reach the browser")

    monkeypatch.setattr(ch, "harvest", boom)
    result = ch.refresh_into_settings(headless=True)
    assert result["ok"] is False
    assert "headless" in result["error"].lower()


def test_refresh_waits_for_a_human(monkeypatch):
    """The visible grab exists so a human can solve a CAPTCHA, but they first
    have to notice the window: with the old headless 45s deadline the harvest
    regularly expired mid-solve, failing the exact case it was built for."""
    seen = {}

    def fake_harvest(portal, headless, timeout_seconds):
        seen["headless"] = headless
        seen["timeout"] = timeout_seconds
        return ch.HarvestResult(error="stop here")

    monkeypatch.setattr(ch, "harvest", fake_harvest)
    monkeypatch.setattr(ch, "_is_session_zero_nt", lambda: False)
    ch.refresh_into_settings()
    assert seen["headless"] is False
    assert seen["timeout"] == ch.HEADFUL_TIMEOUT_SECONDS


def test_a_successful_grab_clears_an_earlier_refusal(monkeypatch):
    """Settings must stop asking for a cookie the moment it has been given one —
    a banner that outlives its own cause trains the user to ignore it."""
    monkeypatch.setattr(ch, "_is_session_zero_nt", lambda: False)
    monkeypatch.setattr(
        ch,
        "harvest",
        lambda portal, headless, timeout_seconds: ch.HarvestResult(cookie="freshTokenValue123"),
    )
    save_settings({"datadome_cookie": "oldTokenValue123"})
    ch.note_cookie_refused("immobiliare", "api-next", 403)
    assert load_settings()["datadome_cookie_refused_at"]

    result = ch.refresh_into_settings()
    assert result["ok"] is True
    # the token itself is never echoed back to the client
    assert "freshTokenValue123" not in str(result)
    after = load_settings()
    assert after["datadome_cookie"] == "freshTokenValue123"
    assert after["datadome_cookie_refused_at"] == ""
    assert after["datadome_cookie_refused_detail"] == ""


def test_refusal_is_recorded_once_and_names_what_refused_it():
    """This is what replaced the fifty-minute TTL. It must be idempotent: a
    blocked scan walking twenty pages describes one refusal, not twenty."""
    save_settings({"datadome_cookie": "someTokenValue123"})
    ch.note_cookie_refused("immobiliare", "api-next", 403)
    first = load_settings()
    assert first["datadome_cookie_refused_at"]
    assert "immobiliare" in first["datadome_cookie_refused_detail"]
    assert "403" in first["datadome_cookie_refused_detail"]

    ch.note_cookie_refused("immobiliare", "api-next", 429)
    assert load_settings()["datadome_cookie_refused_at"] == first["datadome_cookie_refused_at"]


def test_acceptance_clears_the_refusal_and_a_missing_cookie_records_nothing():
    save_settings({"datadome_cookie": "someTokenValue123"})
    ch.note_cookie_refused("immobiliare", "api-next", 403)
    ch.note_cookie_accepted()
    assert load_settings()["datadome_cookie_refused_at"] == ""

    # no cookie configured: there is nothing whose standing could be in question,
    # and a warning about a cookie the user never set is just noise
    save_settings({"datadome_cookie": ""})
    ch.note_cookie_refused("immobiliare", "api-next", 403)
    assert load_settings()["datadome_cookie_refused_at"] == ""


def test_recording_a_refusal_never_breaks_the_scrape_that_saw_it(monkeypatch):
    """Fail-open (invariant 18): custody bookkeeping runs inside the scrapers'
    retry ladder, and a settings file that cannot be written is not a reason for
    a scan to raise."""

    def boom(*_a, **_k):
        raise OSError("settings.json is read-only")

    monkeypatch.setattr(ch, "load_settings", boom)
    ch.note_cookie_refused("immobiliare", "api-next", 403)
    ch.note_cookie_accepted()


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
    from app.routers.settings import get_settings, update_settings

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
    # The one test in this module that needs the real Playwright package: its
    # monkeypatch target is a string, so pytest imports playwright.sync_api to
    # resolve it. Playwright is optional by design (invariant 18) and absent
    # from a default install, so skip here rather than at module level — the
    # other 18 tests cover pure decision logic and must keep running on a clean
    # machine, which is exactly what CI is.
    pytest.importorskip("playwright")

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


# --- the cookie the portal rotates back ----------------------------------
#
# Measured from this connection on 2026-09-18 and again on 2026-09-19: the
# first Immobiliare request of a run answers and every one after it is refused.
# Every session was seeded from the same pasted cookie and dropped the token
# DataDome had just reissued on the answered response, so each request arrived
# as a first-time visitor. The tests below pin the custody of that reissued
# value: kept on an answer, ignored on a refusal, per portal, and never shown.


class _FakeCookie:
    def __init__(self, name, value, domain):
        self.name = name
        self.value = value
        self.domain = domain


class _FakeJar:
    """Stands in for curl_cffi's cookie jar: iterable, one entry per domain."""

    def __init__(self, seeded):
        self.jar = [_FakeCookie("datadome", v, d) for d, v in seeded.items()]

    def rotate(self, domain, value):
        for cookie in self.jar:
            if cookie.domain == domain:
                cookie.value = value
                return
        self.jar.append(_FakeCookie("datadome", value, domain))


class _FakeSession:
    """Answers a scripted list of (status, the cookie the portal sets)."""

    def __init__(self, seeded, script, domain=".immobiliare.it"):
        self.cookies = _FakeJar(seeded)
        self._script = list(script)
        self._domain = domain
        self.requests = 0

    def get(self, *_a, **_k):
        status, rotated = self._script.pop(0)
        self.requests += 1
        if rotated:
            self.cookies.rotate(self._domain, rotated)
        return SimpleNamespace(status_code=status)


def _keeping(seeded, script, **kwargs):
    inner = _FakeSession(seeded, script, **kwargs)
    return inner, base._CookieKeepingSession(inner, seeded)


def test_cookie_for_prefers_what_the_portal_last_issued():
    save_settings({"datadome_cookie": "thePastedSeedValue"})
    assert ch.cookie_for("immobiliare") == "thePastedSeedValue"
    assert ch.cookie_for("idealista") == "thePastedSeedValue"

    ch.remember_rotated_cookie("immobiliare", "theRotatedImmobiliareValue")
    assert ch.cookie_for("immobiliare") == "theRotatedImmobiliareValue"
    # ...and only for the portal that issued it: DataDome scopes the token to
    # the site, so the other portal keeps falling back to the seed.
    assert ch.cookie_for("idealista") == "thePastedSeedValue"


def test_remember_rotated_cookie_refuses_junk_and_writes_once():
    save_settings({"datadome_cookie": "thePastedSeedValue"})
    assert ch.remember_rotated_cookie("immobiliare", "") is False
    assert ch.remember_rotated_cookie("immobiliare", "short") is False
    assert ch.remember_rotated_cookie("someOtherPortal", "aPlausibleTokenValue") is False
    assert ch.remember_rotated_cookie("immobiliare", "aPlausibleTokenValue") is True
    # A scan walking twenty answered pages carries the same cookie on each: the
    # second one must not rewrite settings.json.
    assert ch.remember_rotated_cookie("immobiliare", "aPlausibleTokenValue") is False


def test_a_freshly_minted_seed_drops_the_rotations_it_supersedes():
    save_settings({"datadome_cookie": "thePastedSeedValue"})
    ch.remember_rotated_cookie("immobiliare", "theRotatedImmobiliareValue")

    # the settings form posts every field, including the cookie it did not touch
    save_settings({"datadome_cookie": "thePastedSeedValue", "scan_interval_minutes": 30})
    assert ch.cookie_for("immobiliare") == "theRotatedImmobiliareValue"

    # a genuinely new seed belongs to a session the old rotations are not part of
    save_settings({"datadome_cookie": "aBrandNewPastedValue"})
    assert load_settings()["datadome_session_cookies"] == {}
    assert ch.cookie_for("immobiliare") == "aBrandNewPastedValue"


def test_the_session_keeps_the_cookie_an_answered_request_rotated():
    save_settings({"datadome_cookie": "thePastedSeedValue"})
    seeded = {".immobiliare.it": "thePastedSeedValue", ".idealista.it": "thePastedSeedValue"}
    inner, session = _keeping(seeded, [(200, "theValueThePortalReissued")])

    session.get("https://www.immobiliare.it/api-next/")
    assert ch.cookie_for("immobiliare") == "theValueThePortalReissued"
    # the portal that was never asked keeps the seed
    assert ch.cookie_for("idealista") == "thePastedSeedValue"
    assert inner.requests == 1


def test_the_session_ignores_the_cookie_a_refusal_rotated():
    """Every 403 measured on 2026-09-18 set a `datadome` cookie of its own.
    Storing it would replace a working token with a challenge one, so the write
    back happens on an answered response and nowhere else."""
    save_settings({"datadome_cookie": "thePastedSeedValue"})
    ch.remember_rotated_cookie("immobiliare", "theValueThatStillWorks")
    seeded = {".immobiliare.it": "theValueThatStillWorks"}
    _, session = _keeping(seeded, [(403, "theChallengeValue")])

    session.get("https://www.immobiliare.it/api-next/")
    assert ch.cookie_for("immobiliare") == "theValueThatStillWorks"


def test_a_cookie_less_rung_never_stores_what_it_was_handed():
    """`curl:<profile>` exists to measure what the portal gives a stranger. A
    rung that quietly kept a token would change what the next rung measures."""
    save_settings({"datadome_cookie": "thePastedSeedValue"})
    _, session = _keeping({}, [(200, "theValueGivenToAStranger")])
    session.keep_rotated = False

    session.get("https://www.immobiliare.it/api-next/")
    assert ch.cookie_for("immobiliare") == "thePastedSeedValue"


def test_a_new_session_is_seeded_per_portal():
    save_settings({"datadome_cookie": "thePastedSeedValue"})
    ch.remember_rotated_cookie("immobiliare", "theRotatedImmobiliareValue")

    from app.scrapers.immobiliare import ImmobiliareScraper

    session = ImmobiliareScraper()._new_session()
    by_domain = {c.domain: c.value for c in session.cookies.jar if c.name == "datadome"}
    assert by_domain[".immobiliare.it"] == "theRotatedImmobiliareValue"
    assert by_domain[".idealista.it"] == "thePastedSeedValue"


def test_the_rotated_cookies_are_scrubbed_out_of_what_the_user_reads():
    """They are as secret as the pasted one, and the scan journal quotes URLs
    and errors it did not compose. `SECRET_SETTINGS` is the list of fields the
    settings *form* owns, so this value rides in `secret_values` instead."""
    from app.config import secret_values
    from app.services.scanner import _without_secrets

    save_settings({"datadome_cookie": "thePastedSeedValue"})
    ch.remember_rotated_cookie("immobiliare", "theRotatedImmobiliareValue")
    settings = load_settings()

    assert "theRotatedImmobiliareValue" in secret_values(settings)
    scrubbed = _without_secrets("blocked with datadome=theRotatedImmobiliareValue", settings)
    assert "theRotatedImmobiliareValue" not in scrubbed


def test_the_rotated_cookies_never_reach_the_dashboard():
    from app.routers.settings import get_settings

    save_settings({"datadome_cookie": "thePastedSeedValue"})
    ch.remember_rotated_cookie("immobiliare", "theRotatedImmobiliareValue")
    assert "datadome_session_cookies" not in get_settings()
