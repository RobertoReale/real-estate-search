"""The engine seam for the browser rung: the minimum surface the two browser
consumers (the availability probe and the cookie harvest) actually need.

Why a seam: the whole browser path is Playwright's sync API on one dedicated
greenlet-bound thread (invariants 16/18), and Camoufox plugs in cleanly only
because it *is* Playwright. The candidate stealth engines (Nodriver,
SeleniumBase-CDP) are not — Nodriver is asyncio, SeleniumBase is WebDriver —
so driving them from `_browser_check_inner`/`_harvest_inner` directly would
mean per-engine copies of the block-detection and cookie-reading logic, the
exact "one fact, one implementation" trap the Conventions warn against.
Programming both consumers against this Protocol makes a future engine a
drop-in adapter instead of a fork.

`cookies()` is non-optional by design: whatever engine runs, the harvest must
end by exporting the DataDome cookie the curl_cffi transport (rung 0, the
workhorse) reuses. An engine that earns a cookie it can't export buys nothing
for the free path.

Only `PlaywrightEngine` exists today: extra engines are diversification, not a
new capability, and stay gated on scraper_health evidence (see
docs/plan-browser-humanization.md §2.4). Teardown of the underlying context is
NOT this adapter's job for the probe's persistent session — `AdProbe` owns its
context lifecycle (`_close_browser_session_inner`) exactly as before.
"""

from __future__ import annotations

import typing
from typing import Any, Protocol


class BrowserEngine(Protocol):
    """What a browser must offer to run an availability check or a harvest."""

    engine_label: str

    def open(self, url: str, referer: str | None = None, timeout_ms: int = 25000) -> int | None:
        """Navigate; returns the HTTP status, or None when the engine got no
        response at all (which callers treat as "could not tell")."""
        ...

    def content(self) -> str: ...

    def title(self) -> str: ...

    def url(self) -> str:
        """The page's current URL — a redirect that loses the ad path is one
        of the probe's definitive "gone" signals."""
        ...

    def cookies(self, url: str | None = None) -> list[dict]:
        """Playwright-shaped cookie dicts ({'name': …, 'value': …}), so the
        harvest can persist the DataDome cookie for the curl path."""
        ...

    def humanize(self, rng: Any = None) -> None:
        """Engine-native human-like input (see scrapers/humanize.py). Must be
        fail-open like everything else on this rung."""
        ...

    def wait(self, ms: float) -> None: ...

    def close(self) -> None: ...


class PlaywrightEngine:
    """Adapter over today's Camoufox/Chromium Playwright context + page.

    A thin translation layer, not an owner: it drives whatever (ctx, page)
    pair it is handed and only tears it down when `close()` is called — the
    probe's persistent session keeps its own lifecycle management.
    """

    def __init__(self, ctx: Any, page: Any, pw: Any = None):
        self.ctx = ctx
        self.page = page
        self.pw = pw
        self.engine_label = getattr(ctx, "_engine_label", "browser")

    def open(self, url: str, referer: str | None = None, timeout_ms: int = 25000) -> int | None:
        kwargs: dict[str, Any] = {"wait_until": "domcontentloaded", "timeout": timeout_ms}
        if referer:
            kwargs["referer"] = referer
        resp = self.page.goto(url, **kwargs)
        return None if resp is None else typing.cast(int, resp.status)

    def content(self) -> str:
        return self.page.content()

    def title(self) -> str:
        return self.page.title() or ""

    def url(self) -> str:
        return str(self.page.url)

    def cookies(self, url: str | None = None) -> list[dict]:
        return self.ctx.cookies(url) if url else self.ctx.cookies()

    def humanize(self, rng: Any = None) -> None:
        from . import humanize as _humanize

        _humanize.idle_browse(self.page, rng=rng)

    def wait(self, ms: float) -> None:
        self.page.wait_for_timeout(ms)

    def close(self) -> None:
        # Engine-aware teardown lives in cookie_harvester (_close_ctx knows a
        # Camoufox context owns its own Playwright); imported lazily to keep
        # this module import-light for the offline test suite.
        from ..services import cookie_harvester

        cookie_harvester._close_ctx(self.ctx)
        if self.pw is not None:
            try:
                self.pw.stop()
            except Exception:
                pass
