"""The scrape pipeline: the normalized listing dataclass and the 3-strategy
cascade (JSON-LD -> embedded state -> heuristic) subclasses implement.

Transport lives in `transport.py`, the text parsers in `parsing.py`, the page
predicates in `page_text.py` and the card-boundary climb in `html_cards.py`.
What is left here is the shape of a scrape and the loop that drives it.
"""

import logging
import random
import time
import typing
from dataclasses import dataclass, field

from curl_cffi import requests as curl_requests
from curl_cffi.requests.impersonate import BrowserTypeLiteral

from .page_text import text_says_no_results
from .parsing import detect_contract
from .transport import (
    BlockedError,
    build_scrape_api_request,
    proxy_pool,
    resolve_impersonations,
    scrape_api_config,
    unwrap_scrape_api_response,
)

logger = logging.getLogger(__name__)


@dataclass
class RawListing:
    """Normalized listing produced by any parsing strategy."""

    portal: str
    portal_id: str
    url: str
    contract: str = "sale"  # sale | rent
    title: str = ""
    price: float | None = None
    sqm: float | None = None
    rooms: int | None = None
    floor: str = ""
    city: str = ""
    zone: str = ""
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None
    agency: str = ""
    description: str = ""
    image_url: str = ""
    strategy: str = ""  # json-ld | embedded | heuristic (for diagnostics)

    def merge_missing(self, other: "RawListing") -> None:
        """Completes empty fields with those found by another strategy."""
        for f in (
            "title",
            "floor",
            "city",
            "zone",
            "address",
            "agency",
            "description",
            "image_url",
        ):
            if not getattr(self, f) and getattr(other, f):
                setattr(self, f, getattr(other, f))
        for f in ("price", "sqm", "rooms", "latitude", "longitude"):
            if getattr(self, f) is None and getattr(other, f) is not None:
                setattr(self, f, getattr(other, f))


@dataclass
class ScrapeResult:
    listings: list[RawListing] = field(default_factory=list)
    pages_fetched: int = 0
    strategy_used: str = ""
    blocked: bool = False
    error: str = ""


class BaseScraper:
    portal: str = ""
    # ORDERED list by preference, not random: portals only accept certain
    # TLS handshakes (Safari passes on both portals, Chrome does not).
    impersonations: list[BrowserTypeLiteral] = [
        "safari184",
        "chrome131_android",
        "safari180",
        # Appended July 2026 after the ad-probe measured all three profiles
        # above blocked by DataDome on Immobiliare: iOS Safari and Firefox
        # handshakes are scored on different fingerprint pools than desktop
        # Safari/Chrome, so they extend the rotation rather than replace it.
        "safari18_4_ios",
        "firefox147",
        # Current-generation Safari (26.x), added to keep the rotation abreast
        # of real browser evolution. It trails the measured-good profiles: an
        # untested handshake only gets tried once those ahead of it are blocked.
        "safari260",
    ]
    # if blocked, retry with the next impersonation profile
    rotate_on_block = True
    _warmed = False
    _current_proxy: str | None = None
    # Whether a configured scrape-API key routes fetches through the provider
    # from the start. True at class level so the non-scan paths (AdProbe, and
    # the availability check through it) keep using a set key unconditionally;
    # the scanner sets it
    # per profile from transport_policy.decide, where `scrape_api_mode=
    # "fallback"` (the default) starts on the free path and only escalates on
    # a block.
    use_scrape_api = True

    def __init__(self, delay_seconds: float = 6.0, max_pages: int = 10):
        self.delay_seconds = delay_seconds
        self.max_pages = max_pages
        self._imp_index = 0
        # set from the search URL at scrape() time; heuristic price parsing
        # needs it because rent and sale amounts live in disjoint ranges
        self.contract = "sale"
        # Effective, self-healing profile list. A non-empty `tls_impersonations`
        # setting overrides the code default portal-by-portal (the user's escape
        # hatch to react to a new block wave without a code change); either way
        # anything the installed curl_cffi no longer supports is filtered out.
        from ..config import load_settings

        configured = load_settings().get("tls_impersonations") or []
        self.impersonations = resolve_impersonations(configured, list(type(self).impersonations))
        self.session = self._new_session()

    def _new_session(self):
        session = curl_requests.Session(
            impersonate=self.impersonations[self._imp_index],
            timeout=30,
        )
        session.headers.update(
            {
                "Accept-Language": "it-IT,it;q=0.9,en;q=0.6",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        from ..config import load_settings

        settings = load_settings()
        # A configured proxy that fails to apply means the user thinks traffic
        # is proxied when it is not: that must not be silent, so no try here.
        # The pool hands out one proxy per session (sticky); a block burns it
        # via proxy_pool.burn in _rotate_session, so the rebuilt session exits
        # through a different IP.
        proxy_url = proxy_pool.pick(settings)
        self._current_proxy = proxy_url
        if proxy_url:
            session.proxies = {"http": proxy_url, "https": proxy_url}
        try:
            # DataDome cookies are portal-specific: a cookie from one portal
            # is harmless on the other (the warm-up replaces it), but it will
            # not bypass anything there. The dot-prefix covers www. too.
            cookie_val = (settings.get("datadome_cookie") or "").strip()
            if cookie_val:
                session.cookies.set("datadome", cookie_val, domain=".immobiliare.it")
                session.cookies.set("datadome", cookie_val, domain=".idealista.it")
        except Exception as e:
            # the cookie is best-effort (worst case: more blocks), unlike the proxy
            logger.warning("BaseScraper: failed to apply datadome cookie: %s", e)
        return session

    def _rotate_session(self) -> bool:
        """Switch to the next impersonation profile. False if all exhausted (or wrap around for ad-probe)."""
        # Rotation only ever happens on a block, and the block may be about the
        # exit IP as much as the TLS handshake: cool the proxy down so the
        # rebuilt session (and every other new session) picks a different one.
        proxy_pool.burn(self._current_proxy)
        if self._imp_index + 1 >= len(self.impersonations):
            if self.portal == "ad-probe" and len(self.impersonations) > 1:
                import time

                logger.info(
                    "ad-probe: impersonation cycle completed, resting 4s and wrapping around to %s",
                    self.impersonations[0],
                )
                time.sleep(4.0)
                self._imp_index = 0
            else:
                return False
        else:
            self._imp_index += 1
        logger.info(
            "%s: switching impersonation -> %s",
            self.portal,
            self.impersonations[self._imp_index],
        )
        self.session = self._new_session()
        self._warmed = False
        self.warm_session()
        return True

    def warm_session(self) -> None:
        """Hook: subclasses visit the homepage to acquire cookies."""

    def _fetch_via_scrape_api(self, url: str, provider: str, key: str) -> str:
        """Fetch through the configured scraping API instead of curl_cffi.

        The provider solves DataDome for us, so the returned HTML is fed to the
        exact same parsers. A provider-level refusal (bad key, quota exhausted,
        or a page the provider itself could not solve) surfaces as BlockedError,
        which the fetch() loop already knows how to rotate/abandon on.
        """
        req = build_scrape_api_request(provider, key, url)
        # curl_cffi's typed .request narrows `method` to a Literal and its
        # return to Response|None (streaming overload); we pass a runtime string
        # and always get a Response, so go through an untyped handle.
        send = typing.cast(typing.Any, self.session.request)
        resp = send(
            req.method,
            req.url,
            params=req.params,
            headers=req.headers,
            json=req.json_body,
            allow_redirects=True,
        )
        if resp.status_code in (401, 402, 403, 429):
            raise BlockedError(
                f"{self.portal}: scrape API ({provider}) refused (HTTP {resp.status_code}) on {url}"
            )
        resp.raise_for_status()
        return unwrap_scrape_api_response(provider, resp)

    def _fetch_once(self, url: str) -> str:
        provider, key = scrape_api_config()
        if key and self.use_scrape_api:
            return self._fetch_via_scrape_api(url, provider, key)
        resp = self.session.get(url, allow_redirects=True)
        if resp.status_code in (403, 429) or "captcha" in resp.text[:4000].lower():
            raise BlockedError(f"{self.portal}: blocked (HTTP {resp.status_code}) on {url}")
        # Idealista answers 404 for a search that simply matched nothing, serving
        # its "abbiamo guardato dappertutto" page in full — the same status a
        # dead slug gets. Raising here turned every empty search into a permanent
        # "Error: HTTP 404" on the dashboard, and fed the health streak
        # (invariant 11) until it alerted about a scraper that was working fine.
        if resp.status_code == 404 and text_says_no_results(resp.text):
            return resp.text
        resp.raise_for_status()
        return resp.text

    def fetch(self, url: str) -> str:
        last_error: BlockedError | None = None
        while True:
            try:
                return self._fetch_once(url)
            except BlockedError as e:
                last_error = e
                if not self.rotate_on_block or not self._rotate_session():
                    # top of the ladder (plan B.3): with the whole local
                    # rotation exhausted, a configured scrape API is the last
                    # rung before giving up — but only once (use_scrape_api
                    # flips), so an API refusal still terminates.
                    provider, key = scrape_api_config()
                    if key and not self.use_scrape_api:
                        logger.info(
                            "%s: local transports exhausted, escalating to scrape API (%s)",
                            self.portal,
                            provider,
                        )
                        self.use_scrape_api = True
                        continue
                    raise last_error from e

    def polite_sleep(self):
        time.sleep(self.delay_seconds * random.uniform(0.7, 1.4))

    # --- 3-Strategy Pipeline ---

    def parse_page(self, html: str, page_url: str) -> tuple[list[RawListing], str]:
        """Runs strategies in cascade; merges results by URL to enrich
        missing fields."""
        strategies = [
            ("json-ld", self.parse_json_ld),
            ("embedded", self.parse_embedded_state),
            ("heuristic", self.parse_heuristic),
        ]
        merged: dict[str, RawListing] = {}
        used = []
        for name, fn in strategies:
            try:
                found = fn(html, page_url)
            except Exception:
                logger.exception("%s: strategy %s failed", self.portal, name)
                found = []
            if found:
                used.append(name)
                for item in found:
                    item.strategy = item.strategy or name
                    key = item.url.split("?")[0].rstrip("/")
                    if key in merged:
                        merged[key].merge_missing(item)
                    else:
                        merged[key] = item
            # the first two strategies yield complete data: if one succeeds well, we stop
            if merged and name in ("json-ld", "embedded"):
                break
        return list(merged.values()), "+".join(used)

    def scrape(self, search_url: str) -> ScrapeResult:
        self.contract = detect_contract(search_url)
        result = ScrapeResult()
        url = search_url
        for page in range(1, self.max_pages + 1):
            try:
                html = self.fetch(url)
            except BlockedError as e:
                logger.warning(str(e))
                result.blocked = True
                result.error = str(e)
                break
            except Exception as e:
                logger.warning("%s: error fetching page %s: %s", self.portal, page, e)
                result.error = str(e)
                break
            listings, strategy = self.parse_page(html, url)
            result.pages_fetched += 1
            result.strategy_used = strategy or result.strategy_used
            if not listings:
                # An empty first page is only an alarm when the portal does not
                # say it meant it: "no listings extracted" is how a markup change
                # shows up, but a search whose filters match nothing looks
                # identical from here. Trusting the portal's own words keeps the
                # alarm for the case it was built for.
                if page == 1 and not text_says_no_results(html):
                    result.error = (
                        f"{self.portal}: no listings extracted — possible site "
                        "structure change, check logs"
                    )
                break
            before = len(result.listings)
            known = {l.url for l in result.listings}
            result.listings.extend(l for l in listings if l.url not in known)
            if len(result.listings) == before:  # page with only duplicates: stop
                break
            next_url = self.next_page_url(search_url, page + 1)
            if not next_url:
                break
            url = next_url
            self.polite_sleep()
        for listing in result.listings:
            listing.contract = self.contract
        return result

    # --- To be implemented in subclasses ---

    def parse_json_ld(self, html: str, page_url: str) -> list[RawListing]:
        raise NotImplementedError

    def parse_embedded_state(self, html: str, page_url: str) -> list[RawListing]:
        raise NotImplementedError

    def parse_heuristic(self, html: str, page_url: str) -> list[RawListing]:
        raise NotImplementedError

    def next_page_url(self, search_url: str, page: int) -> str | None:
        raise NotImplementedError
