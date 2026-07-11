"""Automated DataDome cookie harvesting via a local browser (Playwright).

Why this exists: `curl_cffi` (the scrapers' HTTP client, see scrapers/base.py)
cannot *generate* a DataDome cookie, because the cookie is minted by JavaScript
running in a real browser and curl executes no JS. The manual workaround is to
open a portal page in your own browser, copy the `datadome` cookie value, and
paste it into Settings; the scrapers then inject it into every request. This
module automates the "open a browser and read the cookie" half, so the paste is
no longer a manual chore.

Every design choice here is deliberate:

  * OPTIONAL dependency. Playwright plus a browser binary is ~300 MB; the rest
    of the project runs on curl_cffi alone and targets low-power machines
    (Raspberry Pi). So Playwright is imported lazily and its absence is a
    graceful "not available", never an ImportError at import time. The offline
    test suite never launches a browser.

  * SAME MACHINE, SAME IP. A DataDome cookie is bound to the IP that earned it
    and lives ~1 hour, so it must be harvested on the box that runs the scans —
    which it is, since everything is local. A cookie minted on a cloud IP would
    be worthless (and cloud IPs are blocked harder anyway, invariant 8).

  * PERSISTENT PROFILE. The browser uses a persistent user-data-dir, so anything
    solved once — the DataDome cookie, a cookie-consent banner, even a CAPTCHA —
    survives into the next silent launch. This is what turns "solve a challenge
    every time" into "solve it once".

  * FAILS OPEN. Harvesting is best-effort. If the browser is unavailable, times
    out, or meets a CAPTCHA it cannot pass headless, it returns no cookie and
    the caller keeps whatever cookie it already had. It must never crash a scan —
    the same fail-open discipline as the availability probe (invariant 16).
"""
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..config import BASE_DIR, load_settings, save_settings

logger = logging.getLogger(__name__)

# Where the browser keeps its persistent profile (cookies, solved challenges).
# gitignored, like case.db and settings.json — it is local state, not code.
PROFILE_DIR = BASE_DIR / "browser_profile"

PORTAL_HOMES = {
    "immobiliare": "https://www.immobiliare.it/",
    "idealista": "https://www.idealista.it/",
}

UNAVAILABLE_MESSAGE = (
    "Automatic cookie grab needs Playwright, which is not installed. "
    "Install it once with:  pip install playwright  &&  playwright install chromium"
)

# A DataDome cookie lives ~1 hour; refresh a little before that so a scheduled
# scan never fires with a cookie that died minutes ago.
DEFAULT_TTL_MINUTES = 50

# How long to wait for the cookie to appear. Headless gets no help, so waiting
# longer than 45s only delays the scan it runs in front of. A headful grab is
# different: its whole point is that a human can solve a CAPTCHA, and they
# first have to notice the window — 45s regularly expired mid-solve, failing
# the exact scenario the visible browser exists for.
HEADLESS_TIMEOUT_SECONDS = 45
HEADFUL_TIMEOUT_SECONDS = 240

# Only one browser may touch the persistent profile at a time: two launches on
# the same user-data-dir race and Chromium refuses the second with a lock
# error. Same non-blocking-lock discipline as the scanner and inbox scan.
_harvest_lock = threading.Lock()


@dataclass
class HarvestResult:
    cookie: str | None = None
    error: str = ""


def is_available() -> bool:
    """True when Playwright can be imported. Cheap and side-effect free, so the
    UI and the scanner can gate on it without paying for a browser launch."""
    try:
        import playwright.sync_api  # type: ignore[import-not-found] # noqa: F401
        return True
    except Exception:
        return False


def _pick_datadome(cookies: list[dict]) -> str | None:
    """Return the value of the `datadome` cookie from a Playwright cookie list,
    or None. Kept pure so the selection rule is unit-testable without a browser.

    A DataDome clearance token is long; a stray empty or one-char `datadome`
    entry (which some challenge pages set as a placeholder) is not a cookie we
    want to inject, so anything shorter than a plausible token is ignored.
    """
    for c in cookies:
        if c.get("name") == "datadome":
            value = (c.get("value") or "").strip()
            if len(value) >= 8:
                return value
    return None


def cookie_is_stale(updated_at: str | None, ttl_minutes: int,
                    now: datetime) -> bool:
    """Whether a cookie saved at `updated_at` (ISO string) is past its TTL.

    An unknown or unparseable timestamp counts as stale: if we cannot prove the
    cookie is fresh, refreshing is the safe default. Pure and testable.
    """
    if not updated_at:
        return True
    try:
        saved = datetime.fromisoformat(updated_at)
    except ValueError:
        return True
    if saved.tzinfo is None:
        saved = saved.replace(tzinfo=timezone.utc)
    return now - saved >= timedelta(minutes=max(ttl_minutes, 1))


def _launch(p, headless: bool):
    """Open a persistent browser context, preferring a real installed browser
    (Chrome, then Edge) over the bundled Chromium: a real browser carries a far
    less bot-like fingerprint, which is the whole point against DataDome. Falls
    back to bundled Chromium when neither is installed."""
    PROFILE_DIR.mkdir(exist_ok=True)
    last_error: Exception | None = None
    for channel in ("chrome", "msedge", None):
        try:
            kwargs = {"user_data_dir": str(PROFILE_DIR), "headless": headless}
            if channel:
                kwargs["channel"] = channel
            return p.chromium.launch_persistent_context(**kwargs)
        except Exception as e:  # channel not installed, etc.
            last_error = e
    assert last_error is not None
    raise last_error


def harvest(portal: str = "immobiliare", headless: bool = True,
            timeout_seconds: int = HEADLESS_TIMEOUT_SECONDS) -> HarvestResult:
    """Launch a browser, load the portal home, and read its `datadome` cookie.

    Returns a HarvestResult; `cookie` is None on any failure, with a
    human-readable `error`. Never raises for an expected failure (missing
    Playwright, timeout, CAPTCHA) — only truly unexpected errors propagate as a
    logged error turned into a result.
    """
    if not is_available():
        return HarvestResult(error=UNAVAILABLE_MESSAGE)
    if not _harvest_lock.acquire(blocking=False):
        return HarvestResult(error="A cookie grab is already running.")
    home = PORTAL_HOMES.get(portal, PORTAL_HOMES["immobiliare"])
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
        import time

        with sync_playwright() as p:
            ctx = _launch(p, headless)
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.goto(home, wait_until="domcontentloaded",
                          timeout=timeout_seconds * 1000)
                deadline = time.monotonic() + timeout_seconds
                while time.monotonic() < deadline:
                    cookie = _pick_datadome(ctx.cookies())
                    if cookie:
                        logger.info("cookie-harvest: got datadome from %s", portal)
                        return HarvestResult(cookie=cookie)
                    page.wait_for_timeout(1500)
                return HarvestResult(error=(
                    "No datadome cookie appeared before timeout. A CAPTCHA may "
                    "be blocking — try the visible-browser grab and solve it once."
                ))
            finally:
                ctx.close()
    except Exception as e:  # unexpected: a browser crash, a Playwright bug
        logger.exception("cookie-harvest failed")
        return HarvestResult(error=f"{type(e).__name__}: {e}")
    finally:
        _harvest_lock.release()


def refresh_into_settings(portal: str = "immobiliare",
                          headless: bool = True) -> dict:
    """Harvest a cookie and, on success, persist it (with a timestamp) into
    settings.json so the scrapers pick it up on their next session."""
    timeout = HEADLESS_TIMEOUT_SECONDS if headless else HEADFUL_TIMEOUT_SECONDS
    result = harvest(portal, headless=headless, timeout_seconds=timeout)
    if not result.cookie:
        return {"ok": False, "error": result.error or "No cookie obtained"}
    now = datetime.now(timezone.utc)
    save_settings({
        "datadome_cookie": result.cookie,
        "datadome_cookie_updated_at": now.isoformat(),
    })
    return {
        "ok": True,
        "portal": portal,
        "updated_at": now.isoformat(),
        # never echo the full token back to the client
        "cookie_preview": result.cookie[:6] + "…",
    }


def maybe_auto_refresh(settings: dict) -> bool:
    """Refresh the cookie headless before a scan when the user opted in and the
    current cookie is missing or past its TTL. Best-effort: returns whether it
    actually refreshed, and never raises into the scan."""
    if not settings.get("datadome_auto_refresh") or not is_available():
        return False
    ttl = int(settings.get("datadome_cookie_ttl_minutes") or DEFAULT_TTL_MINUTES)
    fresh = settings.get("datadome_cookie") and not cookie_is_stale(
        settings.get("datadome_cookie_updated_at"), ttl, datetime.now(timezone.utc)
    )
    if fresh:
        return False
    try:
        return bool(refresh_into_settings(headless=True).get("ok"))
    except Exception:
        logger.exception("cookie-harvest: auto-refresh failed")
        return False
