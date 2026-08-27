"""`AdProbe`: a scraper reduced to its TLS session, answering one question —
"does this ad page still exist?"

**It fails open** (invariant 16). Only a clear answer from the portal (404/410,
its own "non è più disponibile" copy, or a redirect that loses the ad path) may
become False; a block, a timeout or a 5xx answers None = unknown. The asymmetry
is the whole design: a dead ad shown as live costs one click, while a live ad
shown as dead invites the user to throw away a property they would have called
about.

The browser rungs below are optional and opt-in (invariant 18) and speak only
the `BrowserEngine` Protocol, so block/gone/cookie logic exists once,
engine-agnostic.
"""

import logging
import typing
from urllib.parse import urlparse

from .base import BaseScraper
from .browser_engine import PlaywrightEngine
from .page_text import has_block_marker, text_says_gone

logger = logging.getLogger(__name__)


class AdProbe(BaseScraper):
    """A scraper stripped down to its TLS session: it answers one question,
    "does this ad page still exist?", and parses nothing.

    Built for the email import, where links come from alerts that may be years
    old. The asymmetry of the two mistakes drives the whole design: calling a
    dead ad alive merely wastes a click, while calling a live ad dead invites
    the user to discard it — and a discard is remembered forever. So anything
    that is not a clear "gone" (a DataDome block, a timeout, a 5xx) answers
    **None: unknown**, never False.

    `was_blocked` reports whether the *last* check was refused by the portal
    rather than merely unreachable: the caller stops the batch on a streak of
    those instead of hammering a portal that has already said no.
    """

    portal = "ad-probe"
    # How long a headful CAPTCHA waits for the watching user to solve it before
    # giving up and treating the ad as blocked. Generous — solving a DataDome
    # slider/puzzle by hand takes a few tries — but bounded, so an ignored or
    # unattended window ends the batch instead of hanging the check forever.
    _HEADFUL_SOLVE_TIMEOUT_MS: int = 180_000

    def __init__(self, delay_seconds: float = 6.0, cancel_event: typing.Any = None):
        super().__init__(delay_seconds=delay_seconds)
        self._warmed_hosts: set[str] = set()
        self.was_blocked = False
        self.last_error: str | None = None
        self.last_soup: typing.Any = None
        # Optional threading.Event the caller sets to request an early stop.
        # Only consulted inside long, unbounded waits (the headful CAPTCHA
        # poll below) -- everywhere else the caller's own batch loop is
        # already the checkpoint, so there is nothing here to interrupt.
        self._cancel_event = cancel_event
        # Persistent Playwright fallback (opt-in, see start_browser_session).
        self._pw_pool: typing.Any = None
        self._pw: typing.Any = None
        self._browser_ctx: typing.Any = None
        self._browser_page: typing.Any = None
        # The BrowserEngine adapter the check logic actually drives
        # (scrapers/browser_engine.py): the ctx/page pair above stays around
        # for lifecycle management, but everything between goto and content
        # goes through this seam so a non-Playwright engine can drop in.
        self._engine: typing.Any = None
        self._browser_warmed_hosts: set[str] = set()
        # Browser-first mode: once set, `check()` skips curl_cffi entirely and
        # answers through the persistent Playwright context. The point is to
        # stop *re-earning* a DataDome 403 per ad on the residential IP once the
        # portal has already shown it will refuse the TLS session — every extra
        # 403 only tightens the block the real scans depend on (invariant 16).
        self._browser_primary = False
        # Headful browser: opt-in (`availability_browser_headful`), decided in
        # start_browser_session. When set, the persistent context launches
        # VISIBLE so the watching user can solve a CAPTCHA by hand.
        self._browser_headful = False
        # Set when the user asked for a visible window (`availability_browser_headful`)
        # but it got downgraded to headless because the process has no desktop
        # to draw one in (running as the NSSM service, Session 0). Distinct from
        # `_browser_headful=False` meaning "headful was never requested" — this
        # one needs a different, non-misleading message in browser_status.
        self._headful_forced_off = False
        # Human-readable diagnostic of the browser session's fate, surfaced to
        # the availability-check UI so "why didn't the window open?" is not a
        # mystery: engine missing, no browser option enabled, headless, headful…
        self.browser_status = ""

    def warm_host(self, url: str) -> None:
        """Picks up the portal's DataDome cookie from its homepage first.

        The scrapers do this before their first search page, and an ad page is
        no different: a session that lands on a deep URL having never seen the
        homepage is the easiest thing in the world to flag.
        """
        host = urlparse(url).netloc
        # recorded before the request: a homepage that fails to load must not
        # be retried before every single ad
        if not host or host in self._warmed_hosts:
            return
        self._warmed_hosts.add(host)
        try:
            self.session.get(f"https://{host}/", allow_redirects=True)
        except Exception:
            logger.warning("ad-probe: unable to warm up %s", host)

    def warm_session(self) -> None:
        """Called after an impersonation rotation: the new session is cold."""
        hosts, self._warmed_hosts = self._warmed_hosts, set()
        for host in hosts:
            self.warm_host(f"https://{host}/")

    def _ensure_pw_pool(self):
        """Every Playwright call funnels through this one dedicated thread:
        the sync API refuses to run on a thread that owns an asyncio loop, and
        its objects are greenlet-bound to the thread that created them — so
        creating the context on one thread and driving it from another crashes.
        """
        if self._pw_pool is None:
            from concurrent.futures import ThreadPoolExecutor

            self._pw_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="adprobe_pw")
        return self._pw_pool

    def _start_browser_session_inner(self) -> bool:
        from ..services import cookie_harvester

        # `p_factory` is called lazily by `_launch` — only if Camoufox is
        # skipped or fails. Starting a plain Playwright sync instance up front
        # (before Camoufox gets a turn) trips Camoufox's own "nested sync API"
        # guard and made it fail this way on every single launch.
        pw_holder: dict = {}

        def make_p():
            # Playwright is optional (invariant 18) and deliberately absent from
            # requirements.txt, so a clean checkout cannot resolve this import.
            from playwright.sync_api import sync_playwright  # pyright: ignore[reportMissingImports]

            pw = sync_playwright().start()
            pw_holder["pw"] = pw
            return pw

        # Headless by default: the launch is normally unattended (mid-batch,
        # nobody watching), and invariant 18 reserves the visible browser for
        # moments the user is present. The exception is the availability check's
        # opt-in headful mode (`availability_browser_headful`): the user clicked
        # "check online" and is watching the progress bar, so a window they can
        # solve a CAPTCHA in is legitimate — one solve primes the shared
        # persistent profile and the rest of the batch flows unchallenged.
        self._browser_ctx = cookie_harvester._launch(make_p, headless=not self._browser_headful)
        self._pw = pw_holder.get("pw")
        self._browser_page = (
            self._browser_ctx.pages[0] if self._browser_ctx.pages else self._browser_ctx.new_page()
        )
        self._browser_warmed_hosts = set()
        self._engine = PlaywrightEngine(self._browser_ctx, self._browser_page)
        engine = self._engine.engine_label
        if self._browser_headful:
            self.browser_status = f"{engine} (visible window)"
        elif self._headful_forced_off:
            self.browser_status = f"{engine} (headless — forced: running as a Windows service, no desktop to show a window on)"
        else:
            self.browser_status = f"{engine} (headless)"
        logger.info("ad-probe: browser session started — %s", self.browser_status)
        return True

    def start_browser_session(self) -> bool:
        """Opens a persistent Playwright context reused across ad checks.

        Opt-in via `datadome_auto_refresh` — the same switch that authorises
        every other unattended browser launch (invariant 18). Disabled or
        unavailable, it reports False and the caller aborts the batch as
        before, instead of launching a browser the user never asked for.
        """
        if self._browser_ctx:
            return True
        try:
            from ..services import cookie_harvester

            if not cookie_harvester.is_available():
                self.browser_status = "unavailable: browser engine not installed"
                return False
            from ..config import load_settings

            s = load_settings()
            # Any of these switches is an explicit opt-in to a browser launch
            # (invariant 18): the reactive cookie/refresh machinery, the
            # availability check's browser-first transport, or its headful
            # "let me solve the CAPTCHA myself" mode.
            if not (
                s.get("datadome_auto_refresh")
                or s.get("availability_browser_first")
                or s.get("availability_browser_headful")
            ):
                self.browser_status = "off: no browser option enabled in Settings"
                return False
            # Headful only where a human can actually see the window: a Windows
            # service runs in session 0 with no interactive desktop, so a
            # visible browser would hang invisibly — fall back to headless.
            headful_requested = bool(s.get("availability_browser_headful"))
            session_zero = cookie_harvester._is_session_zero_nt()
            self._browser_headful = headful_requested and not session_zero
            self._headful_forced_off = headful_requested and session_zero
            return self._ensure_pw_pool().submit(self._start_browser_session_inner).result()
        except Exception as e:
            logger.warning("ad-probe: start_browser_session failed: %s", e)
            self.browser_status = f"failed to launch: {type(e).__name__}"
            self.close_browser_session()
            return False

    def close_browser_session(self) -> None:
        """Closes any persistent Playwright context used by this probe."""
        try:
            if self._pw_pool is not None:
                try:
                    self._pw_pool.submit(self._close_browser_session_inner).result()
                finally:
                    self._pw_pool.shutdown(wait=False)
                    self._pw_pool = None
            else:
                self._close_browser_session_inner()
        except Exception:
            pass

    def _close_browser_session_inner(self) -> None:
        if self._browser_ctx:
            # engine-aware teardown: a Camoufox context owns its own Playwright
            # and must be closed through its launcher, not just .close()
            try:
                from ..services import cookie_harvester

                cookie_harvester._close_ctx(self._browser_ctx)
            except Exception:
                pass
            self._browser_ctx = None
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass
            self._pw = None
        self._browser_page = None
        self._engine = None

    def check(self, url: str) -> bool | None:
        """True = still online, False = gone, None = could not tell."""
        self.was_blocked = False
        self.last_error = None
        self.last_soup = None
        if self._browser_primary:
            return self._check_via_browser(url)
        self.warm_host(url)
        path = urlparse(url).path.rstrip("/")
        host = urlparse(url).netloc
        referer = f"https://{host}/"
        resp = None
        for attempt in (0, 1):
            try:
                # An ad page reached with no Referer at all is a bot tell; the
                # homepage is what a human arriving from the portal would carry.
                try:
                    self.session.headers["Referer"] = referer
                except Exception:
                    pass
                resp = self.session.get(url, allow_redirects=True)
            except Exception as e:  # DNS, TLS, timeout: says nothing about the ad
                logger.info("ad-probe: %s -> unknown (%s)", url, e)
                self.last_error = f"Network error: {type(e).__name__}"
                return None
            # Definitive "gone" (404/410 or the portal's own "no longer
            # available" copy) wins over the block heuristic below, for the same
            # reason as the browser path: a removed-ad page can carry DataDome's
            # anti-bot script, and "captcha" as a bare substring would otherwise
            # divert a plainly-gone ad down the blocked/None branch instead of
            # answering False. A real block carries neither signal.
            if resp.status_code in (404, 410) or text_says_gone(resp.text):
                return False
            blocked = (
                resp.status_code in (403, 429)
                or "captcha" in resp.text[:4000].lower()
                or has_block_marker(resp.text)
            )
            if blocked and attempt == 0 and self._rotate_session():
                continue
            if blocked:
                logger.info(
                    "ad-probe: %s -> unknown (blocked via curl_cffi), trying _browser_check fallback",
                    url,
                )
                browser_res = self._browser_check(url)
                if browser_res is not None:
                    return browser_res
                self.was_blocked = True
                self.last_error = f"Blocked by DataDome (HTTP {resp.status_code})"
                return None
            break
        assert resp is not None  # the loop always assigns before break/return
        if resp.status_code in (404, 410):
            return False
        if resp.status_code >= 400:
            self.last_error = f"Server error (HTTP {resp.status_code})"
            return None  # 5xx is the portal's problem, not the ad's
        # A portal may answer 200 with its own "not found" page, or bounce the
        # visitor to the search list. Losing the ad path on the way is proof.
        if path and path not in urlparse(str(resp.url)).path:
            return False
        is_online = not text_says_gone(resp.text)
        if is_online:
            try:
                from bs4 import BeautifulSoup

                self.last_soup = BeautifulSoup(resp.text, "html.parser")
            except Exception:
                pass
        return is_online

    def _check_via_browser(self, url: str) -> bool | None:
        """Browser-primary check: answer straight from the Playwright context,
        never touching curl_cffi. Used once the batch has switched to
        browser-first mode, so no further TLS 403 is earned per ad.

        A `None` here means the browser itself could not tell (a CAPTCHA it
        cannot pass headless, a 5xx). If the context is gone entirely, that is
        indistinguishable from a hard block, so `was_blocked` is raised to let
        the caller's streak logic decide to stop rather than loop forever.
        """
        res = self._browser_check(url)
        if res is None and not self._browser_ctx:
            self.was_blocked = True
            self.last_error = self.last_error or "Browser session unavailable"
        return res

    def _browser_check(self, url: str) -> bool | None:
        """Fallback to checking the ad URL in the persistent Playwright context.

        Gated behind `start_browser_session` (opt-in) and always executed on
        the probe's dedicated Playwright thread.
        """
        try:
            if not self.start_browser_session():
                return None
            return self._ensure_pw_pool().submit(self._browser_check_inner, url).result()
        except Exception as e:
            logger.warning("ad-probe: _browser_check fallback failed for %s (%s)", url, e)
            return None

    def _current_engine(self):
        """The BrowserEngine this probe drives. Normally built by
        `_start_browser_session_inner`; a bare page wired in directly (the
        offline tests do this) gets wrapped in the same Playwright adapter, so
        there is exactly one code path whichever way the browser arrived."""
        if self._engine is not None:
            return self._engine
        if self._browser_page is not None:
            return PlaywrightEngine(self._browser_ctx, self._browser_page)
        return None

    def _browser_check_inner(self, url: str) -> bool | None:
        try:
            eng = self._current_engine()
            if eng is None:
                return None
            host = urlparse(url).netloc
            home_ref = f"https://{host}/"
            if host not in self._browser_warmed_hosts:
                # domcontentloaded, not networkidle: ad-tech keeps portal
                # homepages busy forever, so networkidle just burns the timeout.
                home_status = eng.open(home_ref, timeout_ms=25000)
                if home_status is not None and home_status not in (403, 429):
                    self._browser_warmed_hosts.add(host)
                eng.wait(3000)

            status = eng.open(url, referer=home_ref, timeout_ms=25000)
            if status is None:
                return None
            # A real visitor lands, moves, glances, then the DOM is read: a page
            # with zero pointer events is itself a bot tell to DataDome's
            # behavioral scoring. Fail-open and gated by `browser_humanize`.
            eng.humanize()
            # A definitive "gone" answer (404/410 or the portal's own "no longer
            # available" copy) is authoritative and must be read BEFORE the block
            # heuristic below: a genuinely removed ad page still ships DataDome's
            # anti-bot script, so the bare "captcha" substring test would
            # otherwise misfile a plainly-gone ad as "not verifiable" — the
            # window shows the "non più disponibile" page yet the batch reports
            # 0 removed. A real CAPTCHA wall carries neither signal, so this
            # cannot swallow a genuine block.
            if self._engine_says_gone(status, eng):
                return False
            if (
                status in (403, 429)
                or "captcha" in eng.content()[:4000].lower()
                or has_block_marker(eng.content())
            ):
                eng.wait(5000)
                if "captcha" in eng.content()[:4000].lower():
                    if self._browser_headful and self._wait_for_human_solve(eng):
                        # The user solved the challenge in the visible window:
                        # the shared profile now holds a real DataDome cookie.
                        # Re-navigate to read the ad through the cleared session.
                        status = eng.open(url, referer=home_ref, timeout_ms=25000)
                        if status is None:
                            return None
                        if self._engine_says_gone(status, eng):
                            return False
                    else:
                        # Headless (or the headful window went unsolved): report
                        # it as a block so a browser-first batch can abort on a
                        # streak instead of grinding an all-unknown run at ~25s
                        # per ad.
                        self.was_blocked = True
                        self.last_error = "Blocked by DataDome (browser CAPTCHA)"
                        return None
                elif status in (403, 429) or has_block_marker(eng.content()):
                    # A soft 403 with no CAPTCHA markup, or DataDome's static
                    # "temporarily restricted" wall served 200: still the portal
                    # refusing. Stay fail-open (None, never False) but feed the
                    # caller's block streak, or a repeated soft block would never
                    # trigger the abort/recovery levers.
                    self.was_blocked = True
                    self.last_error = f"Blocked by DataDome (browser HTTP {status})"
                    return None
            path = urlparse(url).path.rstrip("/")
            if status in (404, 410):
                return False
            if status >= 400:
                return None
            if path and path not in urlparse(eng.url()).path:
                return False
            is_online = not text_says_gone(eng.content())
            if is_online:
                try:
                    from bs4 import BeautifulSoup

                    self.last_soup = BeautifulSoup(eng.content(), "html.parser")
                except Exception:
                    pass
            try:
                cookies = eng.cookies(home_ref)
                dd = [c["value"] for c in cookies if c["name"] == "datadome"]
                if dd and hasattr(self, "session") and self.session:
                    self.session.cookies.set("datadome", dd[0], domain=f".{host}")
            except Exception:
                pass
            return is_online
        except Exception as e:
            logger.warning("ad-probe: _browser_check fallback failed for %s (%s)", url, e)
            return None

    @staticmethod
    def _engine_says_gone(status: int | None, eng) -> bool:
        """A browser answer that definitively means "ad gone": a 404/410
        status or the portal's own "no longer available" copy in the rendered
        page. Deliberately excludes the block heuristic (403/CAPTCHA) so callers
        can consult it *before* that check — a removed-ad page can still carry
        DataDome's anti-bot script, and only these signals are unambiguous."""
        try:
            if status is not None and status in (404, 410):
                return True
            return text_says_gone(eng.content())
        except Exception:
            return False

    def _wait_for_human_solve(self, eng) -> bool:
        """Poll a visible CAPTCHA page until the user clears it, or time out.

        Runs on the probe's dedicated Playwright thread (the caller already
        does), so it may block that thread — the whole batch is single-file
        through it anyway, and the FastAPI worker that drives the check is a
        threadpool `def`, so the progress endpoint keeps answering (invariant
        15). Returns True once the challenge markup is gone.

        Not every block that lands here is a solvable widget: a hard
        "temporarily restricted" wall (no puzzle, just static text) never
        stops mentioning "captcha" in its own script tags, so without a way
        out this polls the full window on every one of them — and a user
        clicking "Stop" on the batch had no effect until it expired, since
        this loop is the one place a single property's check can run for
        minutes. `_cancel_event` is checked on the same cadence so a stop
        request lands within one poll instead of up to 180s later.
        """
        import time as _time

        # Drift the cursor toward the challenge region before handing off:
        # a session whose pointer approaches the widget reads as the human
        # who is about to solve it (and never hurts — fail-open).
        try:
            eng.humanize()
        except Exception:
            pass
        deadline = _time.monotonic() + self._HEADFUL_SOLVE_TIMEOUT_MS / 1000.0
        logger.info(
            "ad-probe: headful CAPTCHA — waiting up to %ds for the user to solve it",
            int(self._HEADFUL_SOLVE_TIMEOUT_MS / 1000),
        )
        while _time.monotonic() < deadline:
            if self._cancel_event is not None and self._cancel_event.is_set():
                logger.info("ad-probe: headful CAPTCHA wait cancelled by the user")
                return False
            eng.wait(3000)
            try:
                if "captcha" not in eng.content()[:4000].lower():
                    logger.info("ad-probe: headful CAPTCHA cleared by the user")
                    return True
            except Exception:
                # A navigation is likely in flight right after a solve; the ad
                # page reloads on its own, so keep polling rather than bail.
                pass
        logger.info("ad-probe: headful CAPTCHA not solved within the window")
        return False
