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

  * SAME MACHINE, SAME IP. A cookie minted on a cloud IP would be worthless, and
    cloud IPs are blocked harder anyway (invariant 8), so the grab happens on the
    box that runs the scans — which it is, since everything is local. It is *not*
    short-lived: measured from this connection on 2026-09-12, a cookie 50 hours
    old still returned 25 listings, and DataDome documents a lifetime between
    seven days and a year (`docs/live-checks.md` §3). What ends it is a refusal,
    not a clock.

  * HEADFUL ONLY. A headless browser cannot mint: it draws a `t=bv` CAPTCHA with
    nothing to solve, and on the way out it presents — and burns — the cookie the
    profile already holds (`docs/live-checks.md` §5). So `refresh_into_settings`
    refuses to launch headless, and the cookie is renewed by a person pressing
    the button in Settings. A search that is refused while nobody is at the
    keyboard escalates to the paid rung instead.

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
import os
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..config import BASE_DIR, BROWSER_PROFILE_DIR, DATA_DIR, load_settings, save_settings

logger = logging.getLogger(__name__)

# Where the browser keeps its persistent profile (cookies, solved challenges).
# gitignored, like case.db and settings.json — it is local state, not code, and
# it follows the data directory so a packaged app does not throw away a solved
# CAPTCHA every time it exits.
PROFILE_DIR = BROWSER_PROFILE_DIR

PORTAL_HOMES = {
    "immobiliare": "https://www.immobiliare.it/",
    "idealista": "https://www.idealista.it/",
}

UNAVAILABLE_MESSAGE = (
    "Automatic cookie grab needs Playwright, which is not installed. "
    "Install it once with:  pip install playwright  &&  playwright install chromium"
)

HEADLESS_MINT_MESSAGE = (
    "A headless browser cannot earn a DataDome cookie — it is served a CAPTCHA "
    "with nothing to solve, and it burns the cookie already saved on the way out. "
    "Open Settings and press 'Grab a fresh cookie now', which uses a visible window."
)

# How long to wait for the cookie to appear. Headless gets no help, so waiting
# longer than 45s only delays whatever it runs in front of — it remains the
# default of the low-level `harvest()`, which nothing in the app now drives
# headless. A headful grab is different: its whole point is that a human can
# solve a CAPTCHA, and they first have to notice the window — 45s regularly
# expired mid-solve, failing the exact scenario the visible browser exists for.
HEADLESS_TIMEOUT_SECONDS = 45
HEADFUL_TIMEOUT_SECONDS = 240

# Only one browser may touch the persistent profile at a time: two launches on
# the same user-data-dir race and Chromium refuses the second with a lock
# error. Same non-blocking-lock discipline as the scanner and inbox scan.
_harvest_lock = threading.Lock()

# Cooperative cancellation for a headful grab: the wait loop below only
# early-exits on a block when headless (see `_harvest_inner`), so a headful
# run facing a hard block page with no solvable widget -- not every "Access
# is temporarily restricted" wall is a CAPTCHA a click can clear -- used to
# poll for the full HEADFUL_TIMEOUT_SECONDS with no way to stop it from the
# UI, leaving the visible browser window open the whole time.
_harvest_cancel_event = threading.Event()


def request_cancel_harvest() -> None:
    """Signals a running cookie grab to stop at its next poll. A no-op when
    nothing is running."""
    _harvest_cancel_event.set()


def _ensure_browsers_path() -> None:
    """Automatically discover and configure PLAYWRIGHT_BROWSERS_PATH when running as a
    Windows Service (e.g. NSSM under LocalSystem / NT AUTHORITY\\SYSTEM).

    When an admin user installs `playwright install chromium` in a terminal, the browser
    binaries go into C:\\Users\\<Admin>\\AppData\\Local\\ms-playwright. At PC startup, when
    LocalSystem runs the service, its profile is C:\\Windows\\System32\\config\\systemprofile
    where ms-playwright does not exist. This helper finds the installed Chromium in any
    user profile or in `BASE_DIR / browser_binaries` and sets PLAYWRIGHT_BROWSERS_PATH."""
    current_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if current_path and Path(current_path).exists():
        return

    candidates: list[Path] = [
        # The data directory first: packaged, it is the only one of the three
        # that survives a restart.
        DATA_DIR / "browser_binaries",
        BASE_DIR / "browser_binaries",
        BASE_DIR.parent / "browser_binaries",
    ]
    user_home = Path(os.path.expanduser("~"))
    default_cache = user_home / "AppData" / "Local" / "ms-playwright"
    if default_cache.exists():
        candidates.append(default_cache)

    if os.name == "nt":
        users_dir = Path("C:/Users")
        if users_dir.exists():
            for user_folder in users_dir.iterdir():
                if user_folder.is_dir() and user_folder.name not in (
                    "Public",
                    "Default",
                    "Default User",
                    "All Users",
                ):
                    ms_pw = user_folder / "AppData" / "Local" / "ms-playwright"
                    if ms_pw.exists():
                        candidates.append(ms_pw)

    for candidate in candidates:
        if candidate.exists() and any(candidate.iterdir()):
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(candidate)
            logger.info("cookie-harvest: auto-configured PLAYWRIGHT_BROWSERS_PATH to %s", candidate)
            return


def _find_chromium_executable() -> str | None:
    """Locate the explicit path to chrome.exe inside PLAYWRIGHT_BROWSERS_PATH or known profiles."""
    _ensure_browsers_path()
    pw_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    search_dirs = [Path(pw_path)] if pw_path else []

    if os.name == "nt":
        users_dir = Path("C:/Users")
        if users_dir.exists():
            for u in users_dir.iterdir():
                if u.is_dir() and u.name not in ("Public", "Default", "Default User", "All Users"):
                    search_dirs.append(u / "AppData" / "Local" / "ms-playwright")

    for d in search_dirs:
        if d.exists():
            for folder in sorted(d.iterdir(), reverse=True):
                if folder.is_dir() and "chromium" in folder.name.lower():
                    chrome_exe = folder / "chrome-win" / "chrome.exe"
                    if chrome_exe.exists():
                        return str(chrome_exe)
    return None


@dataclass
class HarvestResult:
    cookie: str | None = None
    error: str = ""


def is_available() -> bool:
    """True when Playwright can be imported. Cheap and side-effect free, so the
    UI and the scanner can gate on it without paying for a browser launch."""
    _ensure_browsers_path()
    try:
        import playwright.sync_api  # type: ignore[import-not-found] # noqa: F401

        return True
    except Exception:
        return False


def _pick_datadome(cookies: Sequence[Mapping[str, Any]]) -> str | None:
    """Return the value of the `datadome` cookie from a Playwright cookie list,
    or None. Kept pure so the selection rule is unit-testable without a browser.

    A DataDome clearance token is long; a stray empty or one-char `datadome`
    entry (which some challenge pages set as a placeholder) is not a cookie we
    want to inject, so anything shorter than a plausible token is ignored.
    """
    for c in cookies:
        if c.get("name") == "datadome":
            value = str(c.get("value") or "").strip()
            if len(value) >= 8:
                return value
    return None


# The cookie domain each portal issues on. DataDome tokens are per-site: the
# value immobiliare.it hands out means nothing to idealista.it, so they are
# stored and replayed apart even though a single pasted seed still starts both.
COOKIE_DOMAINS = {
    "immobiliare": ".immobiliare.it",
    "idealista": ".idealista.it",
}

_rotation_lock = threading.Lock()


def cookie_for(portal: str, settings: Mapping[str, Any] | None = None) -> str:
    """The `datadome` value to present to `portal`, newest first.

    The rotated token wins over the pasted seed. DataDome reissues the cookie on
    an answered request and then distrusts the value it superseded, so a session
    that always re-seeds the minted one arrives as a first-time visitor on every
    request — which is what made the *second* request of a run fail while the
    first answered (`docs/live-checks.md`). Falls back to the seed when the
    portal has not rotated anything yet.
    """
    data = settings if settings is not None else load_settings()
    rotated = data.get("datadome_session_cookies") or {}
    if isinstance(rotated, Mapping):
        value = str(rotated.get(portal) or "").strip()
        if value:
            return value
    return str(data.get("datadome_cookie") or "").strip()


def remember_rotated_cookie(portal: str, value: str) -> bool:
    """Persist the `datadome` value `portal` issued on an answered response.

    Called from the scrapers' session wrapper, so it runs on the scan's worker
    threads and on the live-check's: the read-modify-write of settings.json is
    held under a lock, and a value identical to the stored one writes nothing at
    all — a scan walking twenty answered pages must not write the file twenty
    times. Only ever called for an answered response: a 403 also arrives with a
    fresh `datadome` cookie, and storing *that* would overwrite a working token
    with a challenge one. Fails open like the rest of the custody bookkeeping.

    Returns True when settings were written.
    """
    value = (value or "").strip()
    if not value or len(value) < 8 or portal not in COOKIE_DOMAINS:
        return False
    try:
        with _rotation_lock:
            settings = load_settings()
            rotated = dict(settings.get("datadome_session_cookies") or {})
            if rotated.get(portal) == value:
                return False
            rotated[portal] = value
            save_settings({"datadome_session_cookies": rotated})
        logger.info(
            "cookie custody: %s rotated its DataDome cookie; kept for the next request", portal
        )
        return True
    except Exception:
        logger.exception("cookie custody: could not keep the rotated cookie for %s", portal)
        return False


def note_cookie_refused(portal: str, rung: str, status: int | None = None) -> None:
    """Record that the portal refused a request carrying the saved cookie.

    This is what replaced the fifty-minute TTL. A timer only ever *predicted*
    death — badly: a cookie sixty-one times past that TTL returned 25 listings
    on 2026-09-12, while the one that actually stopped working did so minutes
    after a headless browser presented it (`docs/live-checks.md` §§3-5). A
    refusal is the observable event, so it is the one the app records and shows.

    The detail is written for a person reading Settings, so it names the rung
    and the status rather than an internal enum; `status` is optional because
    not every caller has one number to blame (a block streak is three). Fail-open
    and idempotent: the file is written only on the transition into refusal, so
    a blocked scan walking twenty pages writes once.
    """
    _note_cookie_state(f"{portal} {rung} (HTTP {status})" if status else f"{portal} {rung}")


def note_cookie_accepted() -> None:
    """Record that the saved cookie was answered. Clears a previous refusal so
    Settings stops asking for a new cookie once the old one works again — a
    banner that survives its own cause is worse than no banner."""
    _note_cookie_state("")


def _note_cookie_state(detail: str) -> None:
    now = datetime.now(UTC).isoformat() if detail else ""
    try:
        settings = load_settings()
        if not settings.get("datadome_cookie"):
            return
        if bool(settings.get("datadome_cookie_refused_at")) == bool(detail):
            return
        save_settings(
            {
                "datadome_cookie_refused_at": now,
                "datadome_cookie_refused_detail": detail,
            }
        )
        if detail:
            logger.warning("cookie custody: the saved DataDome cookie was refused by %s", detail)
    except Exception:
        # Custody bookkeeping is never allowed to break the scrape it observes.
        logger.exception("cookie custody: could not record the cookie's standing")


def is_camoufox_available() -> bool:
    """True when the Camoufox package can be imported. Camoufox is a stealth
    Firefox build that hides the automation signals DataDome fingerprints, so a
    check running through it is challenged far less often. Optional and heavier
    than Chromium (its own ~150 MB browser, fetched once), so it is gated
    exactly like Playwright: importable → offer it, absent → stay on Chromium."""
    try:
        import camoufox.sync_api  # type: ignore[import-not-found] # noqa: F401

        return True
    except Exception:
        return False


def _use_camoufox() -> bool:
    """Whether this launch should use Camoufox. `browser_engine` picks it
    explicitly ("camoufox"), pins Chromium ("chromium"), or "auto" (default)
    uses Camoufox when it is installed and falls back otherwise — so installing
    the package is itself the opt-in."""
    from ..config import load_settings

    engine = str(load_settings().get("browser_engine") or "auto").lower()
    if engine == "chromium":
        return False
    if engine == "camoufox":
        return True
    return is_camoufox_available()


def _launch_camoufox(headless: bool) -> Any:
    """Start a persistent Camoufox (stealth Firefox) context on the shared
    profile. Returns a Playwright BrowserContext with the Camoufox owner and an
    engine label attached for teardown/diagnostics, or None on any failure so
    the caller falls back to Chromium — Camoufox must never break a working
    check (its browser binary may simply not be fetched yet)."""
    cam = None
    try:
        # Optional like Playwright (invariant 18): `pip install camoufox` is the
        # opt-in, so the import is unresolvable on a default install.
        from camoufox.sync_api import Camoufox  # pyright: ignore[reportMissingImports]

        # no_viewport=True is required against a newer Playwright (1.5x+): its
        # launch_persistent_context sends a `viewport.isMobile` field that the
        # Firefox build Camoufox bundles (older juggler protocol) rejects with
        # "Browser.setDefaultViewport … not described in this scheme", failing
        # the launch. Skipping the default viewport sidesteps it; Camoufox sizes
        # its own window from its fingerprint anyway.
        cam = Camoufox(
            persistent_context=True,
            user_data_dir=str(PROFILE_DIR),
            headless=headless,
            no_viewport=True,
        )
        ctx = cam.__enter__()  # start now; teardown is via _close_ctx below
        try:
            setattr(ctx, "_camoufox_owner", cam)  # keep launcher alive for teardown
            setattr(ctx, "_engine_label", "camoufox")
        except Exception:
            pass
        logger.info("cookie-harvest: launched Camoufox (stealth Firefox) persistent context")
        return ctx
    except Exception as e:
        logger.warning("cookie-harvest: Camoufox launch failed (%s), falling back to Chromium", e)
        # Camoufox.__enter__ calls PlaywrightContextManager.__enter__ (which
        # starts its own Playwright driver) *before* launching the browser
        # itself — so a failure past that point (e.g. the browser hanging
        # until its 180s launch timeout) leaves that driver instance running,
        # never reached by the `cam.__enter__()` call that raised. Camoufox's
        # own __exit__ is safe to call here: `self.browser` is still None
        # (never set on this failure path), so it skips closing a browser and
        # only stops the leftover Playwright instance. Skipping this leaves
        # the thread marked as "already hosting a Playwright sync API
        # session", so the very next launch on it — even the plain Chromium
        # fallback right below — fails with the misleading "Sync API inside
        # the asyncio loop" error instead of actually trying Chromium.
        if cam is not None:
            try:
                cam.__exit__(type(e), e, e.__traceback__)
            except Exception:
                pass
        return None


def _close_ctx(ctx) -> None:
    """Close a context from either engine. A Camoufox context owns its own
    Playwright, torn down through the launcher's __exit__; a Chromium context is
    closed directly (its Playwright is stopped by the caller)."""
    if ctx is None:
        return
    owner = getattr(ctx, "_camoufox_owner", None)
    try:
        if owner is not None:
            owner.__exit__(None, None, None)
        else:
            ctx.close()
    except Exception:
        pass


def _launch(p_factory, headless: bool) -> Any:
    """Open a persistent browser context. Prefers Camoufox (stealth Firefox)
    when selected — it hides the automation signals DataDome fingerprints — then
    a real installed browser (Chrome, then Edge) over the bundled Chromium: a
    real browser carries a far less bot-like fingerprint, which is the whole
    point against DataDome. Falls back to bundled Chromium when neither is
    installed.

    `p_factory` is a zero-arg callable that starts and returns a plain
    Playwright sync instance, called lazily — only once Camoufox has been
    skipped or has failed. Camoufox is itself built on Playwright's sync API,
    which refuses to start a second instance in a thread that already has one
    running ("Sync API inside the asyncio loop"); starting the plain instance
    up front, before Camoufox gets a turn, made Camoufox fail this guard on
    every single launch and silently fall back to Chromium every time."""
    _ensure_browsers_path()
    PROFILE_DIR.mkdir(exist_ok=True)
    if _use_camoufox():
        ctx = _launch_camoufox(headless)
        if ctx is not None:
            return ctx
        # Camoufox wanted but unavailable/failed: carry on with Chromium below.
    p = p_factory()
    last_error: Exception | None = None
    args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--no-sandbox",
    ]
    ignore_default_args = ["--enable-automation"]
    for channel in ("chrome", "msedge", None):
        try:
            kwargs = {
                "user_data_dir": str(PROFILE_DIR),
                "headless": headless,
                "args": args,
                "ignore_default_args": ignore_default_args,
            }
            if channel:
                kwargs["channel"] = channel
            else:
                exe_path = _find_chromium_executable()
                if exe_path:
                    kwargs["executable_path"] = exe_path
            ctx = p.chromium.launch_persistent_context(**kwargs)
            try:
                ctx.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )
                setattr(ctx, "_engine_label", "chromium")
            except Exception:
                pass
            return ctx
        except Exception as e:  # channel not installed, etc.
            last_error = e
    assert last_error is not None
    # Every channel failed: `p` never became a browser context, so nothing
    # else will ever stop it. Left running, it pins this thread as "already
    # hosting a Playwright sync instance" — the next launch attempt on the
    # same (often pooled/reused) thread then fails with the misleading
    # "Sync API inside the asyncio loop" error, even for Camoufox, which
    # starts its own separate instance and collides with the leftover one.
    try:
        p.stop()
    except Exception:
        pass
    raise last_error


def _is_page_blocked(eng) -> bool:
    """Whether the engine is looking at a challenge/block page. Takes anything
    speaking the BrowserEngine surface (title()/content()), so the block rule
    is written once for every engine."""
    try:
        title = (eng.title() or "").lower()
        if any(w in title for w in ("captcha", "blocked", "attention required", "datadome")):
            return True
        content = eng.content()[:4000].lower()
        if "geo.captcha-delivery.com" in content or (
            "datadome" in content and "captcha" in content
        ):
            return True
        return False
    except Exception:
        return False


def _harvest_inner(portal: str, headless: bool, timeout_seconds: float) -> HarvestResult:
    home = PORTAL_HOMES.get(portal, PORTAL_HOMES["immobiliare"])
    try:
        import time

        pw_holder: dict = {}

        def make_p():
            from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]

            pw = sync_playwright().start()
            pw_holder["pw"] = pw
            return pw

        ctx = _launch(make_p, headless)
        try:
            from ..scrapers.browser_engine import PlaywrightEngine

            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            eng = PlaywrightEngine(ctx, page)
            status = eng.open(home, timeout_ms=int(timeout_seconds * 1000))
            # A cookie earned by a session that also *behaved* is warmer: the
            # curl path reuses it, so the behavioral score it carries matters
            # beyond this one page. Fail-open, gated by `browser_humanize`.
            eng.humanize()
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                if _harvest_cancel_event.is_set():
                    logger.info("cookie-harvest: cancelled by user")
                    return HarvestResult(error="Cancelled.")
                blocked = _is_page_blocked(eng)
                if headless and (blocked or status in (403, 429)):
                    return HarvestResult(
                        error=f"Portal {portal} returned HTTP {status} (CAPTCHA / Blocked)"
                    )
                if not blocked:
                    cookie = _pick_datadome(eng.cookies())
                    if cookie:
                        logger.info("cookie-harvest: got datadome from %s", portal)
                        return HarvestResult(cookie=cookie)
                eng.wait(1500)
            return HarvestResult(
                error=(
                    "No datadome cookie appeared before timeout. A CAPTCHA may "
                    "be blocking — try the visible-browser grab and solve it once."
                )
            )
        finally:
            _close_ctx(ctx)
            if "pw" in pw_holder:
                pw_holder["pw"].stop()
    except Exception as e:  # unexpected: a browser crash, a Playwright bug
        logger.exception("cookie-harvest failed")
        return HarvestResult(error=f"{type(e).__name__}: {e}")


def harvest(
    portal: str = "immobiliare",
    headless: bool = True,
    timeout_seconds: float = HEADLESS_TIMEOUT_SECONDS,
) -> HarvestResult:
    """Launch a browser, load the portal home, and read its `datadome` cookie.

    Returns a HarvestResult; `cookie` is None on any failure, with a
    human-readable `error`. Never raises for an expected failure (missing
    Playwright, timeout, CAPTCHA) — only truly unexpected errors propagate as a
    logged error turned into a result.

    Every caller is a sync `def` endpoint or a scheduler thread, so the
    Playwright sync API can run right here: no thread with an asyncio loop
    ever reaches this function.
    """
    if not is_available():
        return HarvestResult(error=UNAVAILABLE_MESSAGE)
    if not _harvest_lock.acquire(blocking=False):
        return HarvestResult(error="A cookie grab is already running.")
    _harvest_cancel_event.clear()
    try:
        return _harvest_inner(portal, headless, timeout_seconds)
    finally:
        _harvest_lock.release()


def _is_session_zero_nt() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes

        session_id = ctypes.c_uint()
        ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session_id))
        return session_id.value == 0
    except Exception:
        return False


def _refresh_via_active_session_nt(portal: str) -> dict:
    import ctypes
    import subprocess
    import sys
    from ctypes import wintypes

    # `ctypes.windll` exists only on Windows, and this whole function is the NT
    # path (callers gate on os.name). Type-checking on Linux — which CI does,
    # because the Raspberry Pi is a target — otherwise reports four errors for
    # code that cannot run there.
    wtsapi32 = ctypes.windll.wtsapi32  # pyright: ignore[reportAttributeAccessIssue]
    kernel32 = ctypes.windll.kernel32  # pyright: ignore[reportAttributeAccessIssue]
    advapi32 = ctypes.windll.advapi32  # pyright: ignore[reportAttributeAccessIssue]
    userenv = ctypes.windll.userenv  # pyright: ignore[reportAttributeAccessIssue]

    session_id = kernel32.WTSGetActiveConsoleSessionId()
    if session_id == 0xFFFFFFFF:
        return {
            "ok": False,
            "error": "No active user desktop session found to display the browser window.",
        }

    h_token = wintypes.HANDLE()
    if not wtsapi32.WTSQueryUserToken(session_id, ctypes.byref(h_token)):
        return {
            "ok": False,
            "error": f"Failed to get user session token (Win32 error {kernel32.GetLastError()}).",
        }

    lpEnv = ctypes.c_void_p()
    if not userenv.CreateEnvironmentBlock(ctypes.byref(lpEnv), h_token, False):
        kernel32.CloseHandle(h_token)
        return {
            "ok": False,
            "error": f"Failed to create user environment block (Win32 error {kernel32.GetLastError()}).",
        }

    try:

        class STARTUPINFOW(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("lpReserved", wintypes.LPWSTR),
                ("lpDesktop", wintypes.LPWSTR),
                ("lpTitle", wintypes.LPWSTR),
                ("dwX", wintypes.DWORD),
                ("dwY", wintypes.DWORD),
                ("dwXSize", wintypes.DWORD),
                ("dwYSize", wintypes.DWORD),
                ("dwXCountChars", wintypes.DWORD),
                ("dwYCountChars", wintypes.DWORD),
                ("dwFillAttribute", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("wShowWindow", wintypes.WORD),
                ("cbReserved2", wintypes.WORD),
                ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
                ("hStdInput", wintypes.HANDLE),
                ("hStdOutput", wintypes.HANDLE),
                ("hStdError", wintypes.HANDLE),
            ]

        class PROCESS_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("hProcess", wintypes.HANDLE),
                ("hThread", wintypes.HANDLE),
                ("dwProcessId", wintypes.DWORD),
                ("dwThreadId", wintypes.DWORD),
            ]

        si = STARTUPINFOW()
        si.cb = ctypes.sizeof(STARTUPINFOW)
        si.lpDesktop = "winsta0\\default"

        pi = PROCESS_INFORMATION()

        cmd = [
            sys.executable,
            "-m",
            "app.services.cookie_harvester",
            "--portal",
            portal,
            "--refresh-headful",
        ]
        cmd_buf = ctypes.create_unicode_buffer(subprocess.list2cmdline(cmd))

        # CREATE_UNICODE_ENVIRONMENT (0x00000400) | CREATE_NO_WINDOW (0x08000000) = 0x08000400
        success = advapi32.CreateProcessAsUserW(
            h_token,
            None,
            cmd_buf,
            None,
            None,
            False,
            0x08000400,
            lpEnv,
            str(BASE_DIR),
            ctypes.byref(si),
            ctypes.byref(pi),
        )
        if not success:
            err = kernel32.GetLastError()
            return {
                "ok": False,
                "error": f"Failed to launch browser inside interactive session (Win32 error {err}).",
            }

        # Wait up to 5 minutes (300,000 ms) for the user to finish in the popup window
        kernel32.WaitForSingleObject(pi.hProcess, 300_000)
        exit_code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(pi.hProcess, ctypes.byref(exit_code))
        kernel32.CloseHandle(pi.hProcess)
        kernel32.CloseHandle(pi.hThread)

        if exit_code.value == 0:
            settings = load_settings()
            cookie = settings.get("datadome_cookie")
            if cookie:
                return {
                    "ok": True,
                    "portal": portal,
                    "updated_at": settings.get("datadome_cookie_updated_at"),
                    "cookie_preview": str(cookie)[:6] + "…",
                }
        return {
            "ok": False,
            "error": "Browser window closed or timed out before saving a fresh cookie.",
        }
    finally:
        if lpEnv:
            userenv.DestroyEnvironmentBlock(lpEnv)
        kernel32.CloseHandle(h_token)


def refresh_into_settings(portal: str = "immobiliare", headless: bool = False) -> dict:
    """Harvest a cookie and, on success, persist it (with a timestamp) into
    settings.json so the scrapers pick it up on their next session.

    **Headless is refused before anything is launched.** It is not a degraded
    grab, it is a destructive one: measured on 2026-09-12 (`docs/live-checks.md`
    §5) a headless run of this very function drew a `t=bv` CAPTCHA — the variant
    that presents nothing to solve — and the DataDome session it offered on the
    way in stopped being accepted fourteen minutes later, taking the working
    cookie in `settings.json` with it. The `headless=True` parameter is kept so
    an old caller gets this sentence instead of a browser.
    """
    if headless:
        return {"ok": False, "error": HEADLESS_MINT_MESSAGE}
    if _is_session_zero_nt():
        return _refresh_via_active_session_nt(portal)
    result = harvest(portal, headless=False, timeout_seconds=HEADFUL_TIMEOUT_SECONDS)
    if not result.cookie:
        return {"ok": False, "error": result.error or "No cookie obtained"}
    now = datetime.now(UTC)
    # The token belongs to the portal that issued it, so it is kept per portal
    # as well as in the shared seed: before this, minting for one portal
    # overwrote the other's working cookie with a value that had never been
    # valid there. The other portal's entry survives untouched — nothing about
    # this grab invalidates it.
    rotated = dict(load_settings().get("datadome_session_cookies") or {})
    rotated[portal] = result.cookie
    save_settings(
        {
            "datadome_cookie": result.cookie,
            "datadome_session_cookies": rotated,
            "datadome_cookie_updated_at": now.isoformat(),
            # a cookie just earned carries no refusal; leaving the old marker
            # would have Settings asking for the cookie it has just been given
            "datadome_cookie_refused_at": "",
            "datadome_cookie_refused_detail": "",
        }
    )
    return {
        "ok": True,
        "portal": portal,
        "updated_at": now.isoformat(),
        # never echo the full token back to the client
        "cookie_preview": result.cookie[:6] + "…",
    }


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Automated DataDome cookie harvesting CLI")
    parser.add_argument("--portal", default="immobiliare", choices=["immobiliare", "idealista"])
    parser.add_argument(
        "--refresh-headful", action="store_true", help="Run headful refresh_into_settings directly"
    )
    args = parser.parse_args()
    if args.refresh_headful:
        res = refresh_into_settings(args.portal, headless=False)
        if not res.get("ok"):
            print(f"Harvest failed: {res.get('error')}", file=sys.stderr)
            sys.exit(1)
        print(f"Successfully harvested and saved cookie for {args.portal}")
        sys.exit(0)
