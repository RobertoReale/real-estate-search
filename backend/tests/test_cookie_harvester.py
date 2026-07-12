"""Cookie harvester: the browser launch itself cannot be tested offline (it
needs a real browser and a live DataDome challenge, which the project has never
simulated — see developer notes §Testing). What IS testable is every decision *around*
the launch: which cookie to pick, when a cookie is stale, and the scanner's
opt-in gating. Those are the parts that would silently misbehave, so those are
the parts covered here."""
from datetime import datetime, timedelta, timezone

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
    now = datetime(2026, 7, 11, tzinfo=timezone.utc)
    # no timestamp: cannot prove freshness, so refresh
    assert ch.cookie_is_stale("", 50, now) is True
    assert ch.cookie_is_stale(None, 50, now) is True
    assert ch.cookie_is_stale("not-a-date", 50, now) is True


def test_cookie_is_stale_respects_ttl():
    now = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(minutes=10)).isoformat()
    old = (now - timedelta(minutes=55)).isoformat()
    assert ch.cookie_is_stale(fresh, 50, now) is False
    assert ch.cookie_is_stale(old, 50, now) is True


def test_cookie_is_stale_reattaches_utc_to_naive_timestamp():
    # save_settings writes an aware ISO string, but a hand-edited settings.json
    # could carry a naive one; comparing naive vs aware would raise
    now = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)
    naive_recent = datetime(2026, 7, 11, 11, 55).isoformat()  # no tzinfo
    assert ch.cookie_is_stale(naive_recent, 50, now) is False


def test_maybe_auto_refresh_is_noop_when_disabled():
    # opt-in: a scan must never launch a browser the user did not enable, even
    # if Playwright happens to be installed
    assert ch.maybe_auto_refresh({"datadome_auto_refresh": False}) is False


def test_maybe_auto_refresh_skips_a_fresh_cookie(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(ch, "is_available", lambda: True)
    monkeypatch.setattr(ch, "refresh_into_settings",
                        lambda **_: called.__setitem__("n", called["n"] + 1) or {"ok": True})
    fresh = datetime.now(timezone.utc).isoformat()
    refreshed = ch.maybe_auto_refresh({
        "datadome_auto_refresh": True,
        "datadome_cookie": "sometoken",
        "datadome_cookie_updated_at": fresh,
        "datadome_cookie_ttl_minutes": 50,
    })
    assert refreshed is False
    assert called["n"] == 0, "a still-fresh cookie must not trigger a browser launch"


def test_maybe_auto_refresh_harvests_a_stale_cookie(monkeypatch):
    monkeypatch.setattr(ch, "is_available", lambda: True)
    monkeypatch.setattr(ch, "refresh_into_settings", lambda **_: {"ok": True})
    stale = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    assert ch.maybe_auto_refresh({
        "datadome_auto_refresh": True,
        "datadome_cookie": "sometoken",
        "datadome_cookie_updated_at": stale,
        "datadome_cookie_ttl_minutes": 50,
    }) is True


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
    import os
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
    from app.main import get_settings, update_settings
    from app import schemas

    monkeypatch.setattr(ch, "is_available", lambda: True)

    # get_settings should return datadome_harvester_available: true
    get_resp = get_settings()
    assert get_resp.get("datadome_harvester_available") is True

    # update_settings should also return datadome_harvester_available: true and save availability_browser_first
    put_resp = update_settings(schemas.SettingsIn(datadome_auto_refresh=True, availability_browser_first=True))
    assert put_resp.get("datadome_harvester_available") is True
    assert put_resp.get("availability_browser_first") is True

