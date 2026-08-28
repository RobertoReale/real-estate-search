"""Getting bytes off a portal without being refused: TLS impersonation, the
residential proxy pool, and the optional scraping-API transport.

This is the layer DataDome argues with, and every constant in it is measured
rather than reasoned about (invariant 8). Nothing here parses HTML or knows what
a listing is — it answers "how do we make the request, and what do we do when
the answer is no".
"""

import base64
import logging
import threading
import time
import typing
from dataclasses import dataclass
from urllib.parse import quote

from curl_cffi.requests.impersonate import BrowserTypeLiteral

logger = logging.getLogger(__name__)


def supported_impersonations() -> frozenset[str]:
    """Profile names the *installed* curl_cffi actually accepts.

    curl_cffi is pinned open-ended (invariant 8) and both adds new browser
    fingerprints and drops names as the browsers they mimic age out. An unknown
    name raises only when a real fetch runs — never in a test — so resolving the
    configured list against this set is what lets a routine `pip install -U
    curl_cffi` degrade gracefully instead of breaking every scrape until someone
    edits the code.
    """
    return frozenset(typing.get_args(BrowserTypeLiteral))


def resolve_impersonations(
    desired: list[str], fallback: list[str] | None = None
) -> list[BrowserTypeLiteral]:
    """Keep only the supported names from `desired`, order and Safari-first
    preference preserved, duplicates dropped.

    Never returns empty: an all-unsupported list falls back to `fallback`
    (itself resolved), and finally to the generic "safari" alias curl_cffi
    always ships — a blocked default beats a crash. This is the runtime half of
    the TLS-rotation maintenance loop: the user (or a curl_cffi upgrade) can
    change the profile list and anything stale is filtered out.

    Every drop is logged with its reason. Now that the list is a setting anyone
    can edit, a silent filter is how a typo becomes "the rotation is shorter
    than I configured it to be" with nothing anywhere to say so.
    """
    supported = supported_impersonations()
    seen: set[str] = set()
    out: list[str] = []
    dropped: list[str] = []
    for name in desired or []:
        if name in seen or name in dropped:
            continue
        if name in supported:
            seen.add(name)
            out.append(name)
        else:
            dropped.append(name)
    if dropped:
        logger.warning(
            "TLS impersonation: dropping %s — unknown to the installed curl_cffi "
            "(a retired profile name, or a typo)",
            ", ".join(dropped),
        )
    if not out:
        if fallback:
            if desired:
                logger.warning(
                    "TLS impersonation: nothing in the configured list survived, "
                    "falling back to the built-in default"
                )
            else:
                # Every settings.json written before the list became a setting
                # holds an empty one, and it means "use the default" rather than
                # a misconfiguration — warning on it would fire on every session
                # a normal upgrade builds.
                logger.debug("TLS impersonation: no list configured, using the built-in default")
            return resolve_impersonations(fallback)
        logger.warning(
            'TLS impersonation: nothing usable and no fallback left, using the generic "safari"'
        )
        return ["safari"]
    # Names are validated members of BrowserTypeLiteral; the cast documents that
    # for the type checker without a per-element narrowing dance.
    return typing.cast(list[BrowserTypeLiteral], out)


class BlockedError(Exception):
    """The portal blocked the request (403/CAPTCHA DataDome etc.)."""


# --- Residential proxy pool ------------------------------------------------
#
# DataDome scores IP reputation, so one blocked address must not take the whole
# pipeline down with it. The pool is deliberately simple: a session picks one
# proxy at creation (sticky — mid-session IP hops are themselves a bot signal),
# a block puts that proxy in a cool-down, and the next session skips proxies
# still cooling. An empty pool means direct connection, today's behavior.

# Long enough for DataDome's short-lived IP flags to decay, short enough that a
# small pool is not starved for a whole scan cycle.
PROXY_COOLDOWN_SECONDS = 900.0


class ProxyPool:
    """Process-wide registry of configured proxies and their cool-downs.

    State is module-level on purpose: scraper sessions come and go (every TLS
    rotation builds a new one), but "this exit IP was just blocked" must
    survive them or each new session re-spends a block on the same proxy.
    """

    def __init__(self, cooldown_seconds: float = PROXY_COOLDOWN_SECONDS):
        self.cooldown_seconds = cooldown_seconds
        self._burned_at: dict[str, float] = {}
        self._lock = threading.Lock()

    @staticmethod
    def configured_proxies(settings: dict) -> list[str]:
        """The effective pool: `proxy_urls` plus the legacy single `proxy_url`
        (kept as a one-element shorthand), order preserved, blanks and
        duplicates dropped."""
        urls: list[str] = []
        single = (settings.get("proxy_url") or "").strip()
        if single:
            urls.append(single)
        for raw in settings.get("proxy_urls") or []:
            if isinstance(raw, str):
                candidate = raw.strip()
                if candidate and candidate not in urls:
                    urls.append(candidate)
        return urls

    def pick(self, settings: dict) -> str | None:
        """Choose the proxy for a new session, skipping those in cool-down.

        With every proxy cooling, the least-recently-burned one is returned
        rather than None: the user configured a pool expecting traffic to be
        proxied, and silently going direct would expose the residential IP —
        the exact failure mode the existing "no try around session.proxies"
        comment guards against.
        """
        pool = self.configured_proxies(settings)
        if not pool:
            return None
        now = time.monotonic()
        with self._lock:
            available = [
                p
                for p in pool
                if now - self._burned_at.get(p, -self.cooldown_seconds) >= self.cooldown_seconds
            ]
            if available:
                return available[0]
            return min(pool, key=lambda p: self._burned_at.get(p, 0.0))

    def burn(self, proxy: str | None) -> None:
        """Record a block on `proxy`, starting its cool-down."""
        if not proxy:
            return
        with self._lock:
            self._burned_at[proxy] = time.monotonic()
        logger.info("proxy pool: cooling down %s after a block", _mask_proxy(proxy))


def _mask_proxy(proxy: str) -> str:
    """Log-safe proxy label: credentials stripped ('user:pass@host' -> 'host')."""
    return proxy.rsplit("@", 1)[-1]


proxy_pool = ProxyPool()


# --- Optional scraping-API transport (Scrapfly / ScraperAPI / Zyte) ----------
#
# These providers are NOT proxies: you hand them the *target* URL and they
# return the already-solved HTML, DataDome and all. So the whole point is that
# every parser downstream still receives ordinary HTML — the only thing that
# changes is the single choke point that fetches it (`_fetch_once`). Kept as
# free module functions so they are unit-testable without a live network: a
# test asserts the request is rewritten to the provider and the wrapper JSON is
# unwrapped back to raw HTML.


@dataclass
class _ScrapeApiRequest:
    method: str
    url: str
    params: dict | None = None
    headers: dict | None = None
    json_body: dict | None = None


def scrape_api_config() -> tuple[str, str]:
    """(provider, key) from settings; key is "" when the local path should run."""
    from ..config import load_settings

    s = load_settings()
    provider = (s.get("scrape_api_provider") or "scrapfly").strip().lower()
    key = (s.get("scrape_api_key") or "").strip()
    return provider, key


def build_scrape_api_request(provider: str, key: str, url: str) -> _ScrapeApiRequest:
    """Turn a target URL into the provider call that returns its solved HTML.

    `asp`/anti-bot and Italian geo are requested where the provider supports
    them (DataDome lives on .it and geo-checks the exit IP); `render_js` stays
    off — the parsers read the server HTML, not a hydrated DOM, and JS rendering
    both costs more credits and is unnecessary here.
    """
    if provider == "scraperapi":
        # ScraperAPI answers with the raw target HTML directly (no JSON wrapper).
        return _ScrapeApiRequest(
            method="GET",
            url="https://api.scraperapi.com/",
            params={"api_key": key, "url": url, "country_code": "it"},
        )
    if provider == "zyte":
        # Zyte wants a POST with the key as HTTP Basic username (empty password)
        # and returns the body base64-encoded under httpResponseBody.
        token = base64.b64encode(f"{key}:".encode()).decode()
        return _ScrapeApiRequest(
            method="POST",
            url="https://api.zyte.com/v1/extract",
            headers={"Authorization": f"Basic {token}"},
            json_body={"url": url, "httpResponseBody": True},
        )
    # Default: Scrapfly. GET with the target URL encoded into the query string;
    # asp=true turns on its anti-scraping-protection (DataDome) solver.
    return _ScrapeApiRequest(
        method="GET",
        url=(
            "https://api.scrapfly.io/scrape"
            f"?key={quote(key, safe='')}&asp=true&render_js=false"
            f"&country=it&url={quote(url, safe='')}"
        ),
    )


def unwrap_scrape_api_response(provider: str, resp) -> str:
    """Extract the target HTML from the provider's response.

    Scrapfly wraps it in JSON (`result.content`), Zyte base64-encodes it under
    `httpResponseBody`, ScraperAPI returns it verbatim. A shape that does not
    match is a provider/quota error dressed as 200, so raising BlockedError
    routes it into the same rotate/fallback path as any other refusal.
    """
    if provider == "scraperapi":
        return resp.text
    if provider == "zyte":
        try:
            data = resp.json()
            body = data.get("httpResponseBody") or data.get("browserHtml")
            if not body:
                raise BlockedError(f"zyte: no HTML in response: {str(data)[:200]}")
            if data.get("browserHtml"):
                return body
            return base64.b64decode(body).decode("utf-8", "replace")
        except (ValueError, KeyError) as e:
            raise BlockedError(f"zyte: unreadable response ({e})") from e
    # Scrapfly
    try:
        content = resp.json()["result"]["content"]
    except (ValueError, KeyError, TypeError) as e:
        raise BlockedError(f"scrapfly: unreadable response ({e})") from e
    return content or ""
