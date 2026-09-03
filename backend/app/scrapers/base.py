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

from ..config import DEFAULT_TLS_IMPERSONATIONS
from .page_text import declared_result_total, text_says_no_results
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


def listing_key(url: str) -> str:
    """The identity two sightings of one ad are matched on.

    The path without the query string, which portals append per session and per
    referrer. `parse_page` merges a page's strategies on it, `merge_scrapes`
    merges a split search's parts on it, and the scanner recognises an ad it
    already holds by it — one definition rather than three copies, because three
    copies of "is this the same ad" drift into three different answers.
    """
    return url.split("?")[0].rstrip("/")


# "Does this search already hold this ad, unchanged?" — supplied by the caller,
# because the answer lives in the database and the scrape does not: the scanner
# reads it once on the thread that owns the session and hands the fetching
# thread a closure over a frozen copy (`scanner._recognises`).
KnownListing = typing.Callable[[RawListing], bool]


@dataclass
class ScrapeResult:
    listings: list[RawListing] = field(default_factory=list)
    pages_fetched: int = 0
    strategy_used: str = ""
    blocked: bool = False
    error: str = ""
    # What the portal said its whole result set was, when it says so at all.
    # `None` means "not declared" and must never be shown as a total: a page
    # count invented by the app is worse than no page count, because it reads
    # exactly like one the portal stated.
    total_pages: int | None = None
    total_listings: int | None = None
    # The page cap this scrape ran under (`max_pages_per_search`), carried so
    # the sentence the user reads takes the number from the scrape that was
    # actually capped rather than from a second reading of the setting.
    page_limit: int = 0
    # Why the walk stopped short of what the portal had, or "" when it did not.
    # Only `page_limit` today; a value here is a claim that listings exist which
    # this scan did not see, so it is set only where that is provably true.
    truncated_by: str = ""
    # How many narrower searches this result was assembled from, 0 when the
    # search ran as one — which is every scrape a scraper produces, since a
    # scrape is one search and the splitting is the scanner's (`_split_the_search`).
    # It is also the only thing that can clear `truncated_by`: a search that came
    # back in parts covered what a single walk could not.
    parts: int = 0
    # True when the walk stopped because a whole page held nothing this search
    # had not already seen, at the same price. With the ordering pinned
    # newest-first the arrivals are on page 1, so the tenth scan of an unchanged
    # search spent about a minute of deliberate waiting to re-read listings it
    # already had — and the saving here is requests *not made*, which is the one
    # kind of speed-up that also makes a block less likely.
    #
    # Recorded because it is a shortcut: a scrape that stopped here has not read
    # the whole result set and may never be reported as though it had
    # (`scanner._quick_scan_note`, `_stop_reason`).
    stopped_early: bool = False

    @property
    def truncated(self) -> bool:
        """Did this scrape stop before the portal ran out of listings?

        The stop condition is `max_pages_per_search`, ten pages by default, and
        for years a forty-page search returned its first ten and reported "N
        listings across 10 pages" — a sentence that sounds complete and is not.
        This is the flag that lets the scan say which of the two it is.

        The negative case is as load-bearing as the positive one: a search that
        fit inside the cap must never be reported as truncated, or the notice
        becomes noise and stops being read. So each acquisition path arms this
        only when it has the portal's own total in hand and is demonstrably
        short of it, or (on the HTML path, where no total is published) when it
        used its last permitted page on a full one with another still to come.
        """
        return bool(self.truncated_by)

    @property
    def outcome(self) -> str:
        """What this scrape actually established, in one word.

        `ok` / `no_results` / `blocked` / `error`. The distinction that matters
        is the middle one: **"the portal answered and listed nothing" is not
        "nothing came back"**, and flattening the two is what let a soft block
        be recorded as a healthy scan of a quiet market.

        `no_results` is therefore the *proved* case, never the default one. It
        is reached only by falling through every other branch, which each
        scraper path is responsible for arming: a page that came back empty
        without the portal's own "nothing matched" signal sets `error` (the
        HTML path's markup-change alarm) or `blocked` (an empty 200 on
        api-next, which is exactly what a soft block looks like). A partial
        scrape that was blocked mid-way stays `blocked` even though it carries
        listings — the answer is incomplete and the profile line has to say so.
        """
        if self.blocked:
            return "blocked"
        if self.listings:
            return "ok"
        if self.error:
            return "error"
        return "no_results"


def merge_scrapes(results: list[ScrapeResult]) -> ScrapeResult:
    """One result out of several searches over parts of the same criteria.

    Listings merge on their URL — the very key `parse_page` already merges a
    page's strategies on — because a partition can overlap at its edges and a
    portal can file one listing under two of its own zones. A listing arriving
    twice therefore costs one wasted parse and nothing else, which is what makes
    splitting a search cheap enough to be worth doing at all.

    What the portal said about the **whole** search is the first result's: its
    declared total, its page count, and the cap the walk ran under all describe
    the question that was asked, not the narrower ones asked afterwards.
    `truncated_by` is carried the same way and deliberately so — a merge cannot
    know whether the parts covered what the whole could not, so it leaves the
    pessimistic answer standing for the caller to clear on proof.
    """
    if not results:
        return ScrapeResult()
    first = results[0]
    merged = ScrapeResult(
        strategy_used=first.strategy_used,
        total_pages=first.total_pages,
        total_listings=first.total_listings,
        page_limit=first.page_limit,
        truncated_by=first.truncated_by,
    )
    known: set[str] = set()
    for result in results:
        merged.pages_fetched += result.pages_fetched
        merged.blocked = merged.blocked or result.blocked
        merged.error = merged.error or result.error
        merged.strategy_used = merged.strategy_used or result.strategy_used
        for listing in result.listings:
            key = listing_key(listing.url)
            if key not in known:
                known.add(key)
                merged.listings.append(listing)
    return merged


class BaseScraper:
    portal: str = ""
    # The rotation, ordered by preference. The names themselves are data
    # (`config.DEFAULT_TLS_IMPERSONATIONS`, which is also what the
    # `tls_impersonations` setting defaults to, with the measured history behind
    # each one); they appear here as the built-in fallback for the case where
    # that setting resolves to nothing usable.
    impersonations: list[BrowserTypeLiteral] = typing.cast(
        list[BrowserTypeLiteral], list(DEFAULT_TLS_IMPERSONATIONS)
    )
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
    # Who is watching this scrape, if anyone. The scanner sets it for the
    # duration of one profile so the dashboard can say which page is in flight
    # and how long the next pause is; every other caller leaves it None and the
    # reporting costs a single `is None` per page.
    on_progress: typing.Callable[..., None] | None = None

    def __init__(self, delay_seconds: float = 6.0, max_pages: int = 10):
        self.delay_seconds = delay_seconds
        self.max_pages = max_pages
        self._imp_index = 0
        # set from the search URL at scrape() time; heuristic price parsing
        # needs it because rent and sale amounts live in disjoint ranges
        self.contract = "sale"
        # Effective, self-healing profile list. `tls_impersonations` is what the
        # rotation actually uses (the user's escape hatch to react to a new block
        # wave without a code change); either way anything the installed
        # curl_cffi no longer supports is filtered out with a logged reason, and
        # a list nothing survives from falls back to the built-in default.
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
        # "The ladder is exhausted" cannot be read off _rotate_session alone:
        # for the ad-probe it deliberately WRAPS AROUND and so answers True
        # forever (the batch reuses one probe across ads, and the next ad must
        # not inherit a permanently refused rotation). Without a bound of its
        # own this loop therefore retried a persistently blocked portal for
        # ever — the caller's `except BlockedError` fail-open never ran, and
        # neither did the scrape-API escalation below. One full pass of the
        # ladder is the answer; past that the portal has said no.
        rotations_left = len(self.impersonations)
        while True:
            try:
                return self._fetch_once(url)
            except BlockedError as e:
                last_error = e
                if rotations_left > 0 and self.rotate_on_block and self._rotate_session():
                    rotations_left -= 1
                else:
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

    def report_progress(self, **facts) -> None:
        """Say what this scrape is doing, to whoever asked to be told.

        Facts only — a page number, a count, the seconds about to be spent
        waiting — never a sentence: the wording belongs to the caller, which is
        the side that knows whose scan this is and who is going to read it.

        A watcher that raises must not end the scrape it was only supposed to
        describe, so the callback is contained here. That is the same rule
        `scraper_health.record_scan` follows for the same reason.
        """
        if self.on_progress is None:
            return
        try:
            self.on_progress(**facts)
        except Exception:
            logger.exception("%s: progress callback failed", self.portal)

    def polite_sleep(self):
        seconds = self.delay_seconds * random.uniform(0.7, 1.4)
        # Announced before it is spent, and this is the reporting that matters
        # most: `request_delay_seconds` defaults to 6 and is paid between every
        # page, so most of a scan's wall clock is this line. Unannounced, the
        # longest thing the app does looks like the thing that hung.
        self.report_progress(phase="waiting", waiting_seconds=round(seconds, 1))
        time.sleep(seconds)

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
                    key = listing_key(item.url)
                    if key in merged:
                        merged[key].merge_missing(item)
                    else:
                        merged[key] = item
            # the first two strategies yield complete data: if one succeeds well, we stop
            if merged and name in ("json-ld", "embedded"):
                break
        return list(merged.values()), "+".join(used)

    def scrape(self, search_url: str, known: KnownListing | None = None) -> ScrapeResult:
        """Walk this search's pages, up to `max_pages`.

        `known` shortens the walk: given a way to ask "does the caller already
        hold this ad, unchanged?", the loop stops on the first *full* page where
        the answer is yes for every listing on it. Its correctness rests
        entirely on the ordering being pinned newest-first — on a relevance
        ranking, "everything on this page is known" says nothing whatsoever
        about the next one. Left `None` (a full sweep) the walk is exactly what
        it always was.
        """
        self.contract = detect_contract(search_url)
        result = ScrapeResult(page_limit=self.max_pages)
        url = search_url
        # The most listings any page of this search has yielded, which is the
        # only reading of "a full page" available here: no portal publishes its
        # page size, so the pages themselves are the measure. A page that comes
        # back shorter than that parsed incompletely — and an incomplete parse
        # must never end the walk, because reading a parse failure as "nothing
        # new" is how the app would go blind while reporting success.
        page_size = 0
        for page in range(1, self.max_pages + 1):
            self.report_progress(phase="fetching", page=page)
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
            if page == 1:
                # Read once, from the first page, because that is where the
                # portals print it — and read whether or not the scrape ends up
                # capped, since "47 listings, and the portal says it has 47" is
                # the statement that proves a scan complete.
                result.total_listings = declared_result_total(html)
                # Reported only because the portal published it. No HTML path
                # declares a page count anywhere, so the watcher is left with a
                # rising number and no percentage — which is the honest shape
                # of this scrape and must not be dressed up as a proportion.
                self.report_progress(total_listings=result.total_listings)
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
            # Judged before this page is folded in, and on the page size the
            # pages *before* it established, so a short page is measured against
            # a full one rather than against itself.
            nothing_new = (
                known is not None
                and len(listings) >= page_size
                and all(known(listing) for listing in listings)
            )
            page_size = max(page_size, len(listings))
            before = len(result.listings)
            seen = {l.url for l in result.listings}
            result.listings.extend(l for l in listings if l.url not in seen)
            self.report_progress(page=page, listings=len(result.listings))
            if len(result.listings) == before:  # page with only duplicates: stop
                break
            if nothing_new:
                # Recorded *after* the page was kept, so the ads on it still get
                # their `last_seen_at` refreshed and any price change on them is
                # still collected: this stops the walk, it does not discard the
                # page that stopped it.
                result.stopped_early = True
                break
            next_url = self.next_page_url(search_url, page + 1)
            if not next_url:
                break
            if page >= self.max_pages:
                # A full page, another one to go, and no permission left to
                # fetch it. No portal publishes a page count in its HTML, so
                # this is as far as the evidence goes — which is exactly why
                # the total the scan reports stays whatever the page declared,
                # `None` included, instead of being inferred from here.
                if result.total_listings is None or len(result.listings) < result.total_listings:
                    result.truncated_by = "page_limit"
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
