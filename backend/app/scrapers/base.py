"""Scraper base: HTTP client with TLS impersonation, normalized listing dataclass,
and 3-strategy pipeline (JSON-LD -> embedded state -> heuristic parsing)
implemented in subclasses."""
import base64
import json
import logging
import random
import re
import time
import typing
from dataclasses import dataclass, field
from urllib.parse import parse_qs, quote, urlparse

from curl_cffi import requests as curl_requests
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
    change the profile list and anything stale is quietly filtered out.
    """
    supported = supported_impersonations()
    seen: set[str] = set()
    out: list[str] = []
    for name in desired or []:
        if name in supported and name not in seen:
            seen.add(name)
            out.append(name)
    if not out:
        return resolve_impersonations(fallback) if fallback else ["safari"]
    # Names are validated members of BrowserTypeLiteral; the cast documents that
    # for the type checker without a per-element narrowing dance.
    return typing.cast(list[BrowserTypeLiteral], out)


class BlockedError(Exception):
    """The portal blocked the request (403/CAPTCHA DataDome etc.)."""


def detect_contract(search_url: str) -> str:
    """"sale" or "rent", inferred from the search URL.

    Both portals encode the contract in the first path segment
    ("vendita-case" / "affitto-case"); Immobiliare's api-next fallback
    derives idContratto the same way. Polygon/area searches
    ("/search-list/?...") carry no such segment: there the contract lives
    only in the `idContratto` query parameter (2 = rent), so a rental
    polygon search must be read from the query or it gets mislabeled
    "sale" — wrong Property.contract AND the sale price bounds applied to
    monthly rents.
    """
    url = search_url or ""
    if "affitto" in url.lower():
        return "rent"
    qs = parse_qs(urlparse(url).query)
    if (qs.get("idContratto") or [""])[0] == "2":
        return "rent"
    return "sale"


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
        for f in ("title", "floor", "city", "zone", "address", "agency",
                  "description", "image_url"):
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


# --- Numerical helpers reused across all strategies ---

# Portals write prices both as "€ 250.000" and "399.000 €".
PRICE_RE = re.compile(r"€\s*([\d.,]+)|([\d.,]+)\s*€")
# "3.990 €/m²" is the price per square meter, not the property price
PRICE_PER_SQM_RE = re.compile(r"[\d.,]+\s*€\s*/\s*m", re.IGNORECASE)
# Large plots write the surface with a thousands separator ("5.000 m²"):
# the first alternative captures that form so it is not read as 5.0 sqm.
SQM_RE = re.compile(r"(\d{1,3}(?:\.\d{3})+|\d+(?:[.,]\d{1,2})?)\s*m[q²]",
                    re.IGNORECASE)
ROOMS_RE = re.compile(r"(\d+)\s*local[ei]", re.IGNORECASE)

MIN_PRICE, MAX_PRICE = 10_000, 20_000_000
# Rents run 300–5,000 €/month: the sale bounds would reject every one of
# them, which is exactly what happened before rental support existed.
MIN_RENT, MAX_RENT = 100, 50_000


def _to_number(raw: str) -> float | None:
    """"1.250.000" -> 1250000.0 (the period is the thousands separator)."""
    raw = raw.strip().rstrip(".,")
    if not raw:
        return None
    try:
        return float(raw.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def parse_price(text: str, contract: str = "sale") -> float | None:
    """First plausible amount in text, ignoring price per m².

    In cards, the property price precedes any accessory amounts
    ("Box opz. 39.000 €"), so we pick the first value in range.
    The plausibility range depends on the contract: a 750 €/month rent is
    a perfectly valid price but would be noise on a sale card.
    """
    if not text:
        return None
    lo, hi = (MIN_RENT, MAX_RENT) if contract == "rent" else (MIN_PRICE, MAX_PRICE)
    cleaned = PRICE_PER_SQM_RE.sub(" ", text)
    for m in PRICE_RE.finditer(cleaned):
        value = _to_number(m.group(1) or m.group(2) or "")
        if value is not None and lo <= value <= hi:
            return value
    return None


def parse_sqm(text: str) -> float | None:
    m = SQM_RE.search(text or "")
    if not m:
        return None
    raw = m.group(1)
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        raw = raw.replace(".", "")  # "5.000" is five thousand, not five
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return None


def parse_rooms(text: str) -> int | None:
    m = ROOMS_RE.search(text or "")
    return int(m.group(1)) if m else None


def plausible_price(value: float | None, contract: str = "sale") -> float | None:
    """The same plausibility gate parse_price applies to scraped text, for the
    structured paths (JSON-LD, embedded state, api-next): a "price on request"
    placeholder (0/1) or a monthly instalment in the portal's own data would
    otherwise sail through unchecked while the identical value in card text
    gets rejected."""
    if value is None:
        return None
    lo, hi = (MIN_RENT, MAX_RENT) if contract == "rent" else (MIN_PRICE, MAX_PRICE)
    return value if lo <= value <= hi else None


def to_float(value) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def to_int(value) -> int | None:
    try:
        return int(float(value)) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


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
            raise BlockedError(f"zyte: unreadable response ({e})")
    # Scrapfly
    try:
        content = resp.json()["result"]["content"]
    except (ValueError, KeyError, TypeError) as e:
        raise BlockedError(f"scrapfly: unreadable response ({e})")
    return content or ""


class BaseScraper:
    portal: str = ""
    # ORDERED list by preference, not random: portals only accept certain
    # TLS handshakes (Safari passes on both portals, Chrome does not).
    impersonations: list[BrowserTypeLiteral] = [
        "safari184", "chrome131_android", "safari180",
        # Appended July 2026 after the ad-probe measured all three profiles
        # above blocked by DataDome on Immobiliare: iOS Safari and Firefox
        # handshakes are scored on different fingerprint pools than desktop
        # Safari/Chrome, so they extend the rotation rather than replace it.
        "safari18_4_ios", "firefox147",
        # Current-generation Safari (26.x), added to keep the rotation abreast
        # of real browser evolution. It trails the measured-good profiles: an
        # untested handshake only gets tried once those ahead of it are blocked.
        "safari260",
    ]
    # if blocked, retry with the next impersonation profile
    rotate_on_block = True
    _warmed = False

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
        self.impersonations = resolve_impersonations(
            configured, list(type(self).impersonations)
        )
        self.session = self._new_session()

    def _new_session(self):
        session = curl_requests.Session(
            impersonate=self.impersonations[self._imp_index],
            timeout=30,
        )
        session.headers.update({
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.6",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        })
        from ..config import load_settings
        settings = load_settings()
        # A configured proxy that fails to apply means the user thinks traffic
        # is proxied when it is not: that must not be silent, so no try here.
        proxy_url = (settings.get("proxy_url") or "").strip()
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
        if self._imp_index + 1 >= len(self.impersonations):
            if self.portal == "ad-probe" and len(self.impersonations) > 1:
                import time
                logger.info("ad-probe: impersonation cycle completed, resting 4s and wrapping around to %s", self.impersonations[0])
                time.sleep(4.0)
                self._imp_index = 0
            else:
                return False
        else:
            self._imp_index += 1
        logger.info(
            "%s: switching impersonation -> %s",
            self.portal, self.impersonations[self._imp_index],
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
            req.method, req.url, params=req.params,
            headers=req.headers, json=req.json_body, allow_redirects=True,
        )
        if resp.status_code in (401, 402, 403, 429):
            raise BlockedError(
                f"{self.portal}: scrape API ({provider}) refused "
                f"(HTTP {resp.status_code}) on {url}"
            )
        resp.raise_for_status()
        return unwrap_scrape_api_response(provider, resp)

    def _fetch_once(self, url: str) -> str:
        provider, key = scrape_api_config()
        if key:
            return self._fetch_via_scrape_api(url, provider, key)
        resp = self.session.get(url, allow_redirects=True)
        if resp.status_code in (403, 429) or "captcha" in resp.text[:4000].lower():
            raise BlockedError(
                f"{self.portal}: blocked (HTTP {resp.status_code}) on {url}"
            )
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
                    raise last_error

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


# What the portals write when the ad is gone. Kept in Italian for the same
# reason as DEFAULT_EXCLUDED_KEYWORDS: it must match their pages verbatim.
AD_GONE_MARKERS = (
    "non è presente sul nostro sito",     # Immobiliare's 404 page
    "non è più disponibile",              # both portals
    "annuncio non disponibile",
    "immobile non disponibile",
)

# What the portals write on a search whose filters matched nothing. Idealista
# serves this page with HTTP 404 — the very status a dead slug gets — so the
# status code alone cannot tell "no flats here today" from "no such zone": only
# the page can. Measured live on both portals; Immobiliare answers 200 instead,
# so it reaches us as an empty parse rather than an exception.
SEARCH_EMPTY_MARKERS = (
    "non abbiamo trovato quello che stavi cercando",   # Idealista
    "non ci sono annunci che corrispondano ai tuoi criteri",
    "non ci sono annunci per la tua ricerca",          # Immobiliare
)

# DataDome's interstitial "block" wall (the "Access is temporarily restricted"
# page). Not necessarily a solvable CAPTCHA widget — often just static text —
# but always a block, never the ad. Confirmed ABSENT from live ad pages, so it
# safely complements the 403/429 + "captcha" heuristic for a wall that arrives
# as HTTP 200 with the word "captcha" nowhere in its markup. Matched against the
# RAW HTML because one signal (`geo.captcha-delivery.com`) is a <script> src.
DATADOME_BLOCK_MARKERS = (
    "access is temporarily restricted",
    "we detected unusual activity",
    "geo.captcha-delivery.com",
    "please enable js and disable any ad blocker",
)


def _visible_text(html: str) -> str:
    """Lowercased text a human would actually see, with <script>/<style>/
    <template>/<noscript> stripped out.

    This matters because every Immobiliare ad page — live OR removed — embeds
    the portal's i18n error dictionary (including "non è più disponibile")
    inside its Next.js JSON. Matching the gone markers against the raw HTML+JS
    therefore reports *live* ads as gone; the rendered text carries the message
    only when the page truly is the gone page. Returns "" when the HTML can't be
    parsed: without proof we must not claim "gone" (invariant 16)."""
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "template", "noscript"]):
            tag.decompose()
        # Runs of whitespace collapse to one space: a reader does not see the
        # line break a portal happens to put inside a sentence, so a marker
        # phrase must not depend on where the markup wraps.
        return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).lower()
    except Exception:
        return ""


def text_says_gone(html: str) -> bool:
    """True when the page's VISIBLE text carries a portal "ad gone" message."""
    text = _visible_text(html)
    return any(m in text for m in AD_GONE_MARKERS)


def text_says_no_results(html: str) -> bool:
    """True when the page's VISIBLE text is the portal's own "nothing matched"
    page — a real answer about an empty search, not a failure.

    Visible text only, for the same reason as text_says_gone: the portals ship
    their i18n dictionaries inside the page's JSON, so a raw substring scan would
    call every page empty. Getting that backwards is the dangerous direction —
    it would silence the "no listings extracted" alarm that catches a portal
    changing its markup.
    """
    text = _visible_text(html)
    return any(m in text for m in SEARCH_EMPTY_MARKERS)


def has_block_marker(html: str) -> bool:
    """True when the raw HTML carries DataDome's interstitial-wall signature."""
    if not html:
        return False
    low = html.lower()
    return any(m in low for m in DATADOME_BLOCK_MARKERS)


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
            from playwright.sync_api import sync_playwright
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
        self._browser_page = self._browser_ctx.pages[0] if self._browser_ctx.pages else self._browser_ctx.new_page()
        self._browser_warmed_hosts = set()
        engine = getattr(self._browser_ctx, "_engine_label", "browser")
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
            if not (s.get("datadome_auto_refresh")
                    or s.get("availability_browser_first")
                    or s.get("availability_browser_headful")):
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
            if (resp.status_code in (404, 410)
                    or text_says_gone(resp.text)):
                return False
            blocked = (resp.status_code in (403, 429)
                       or "captcha" in resp.text[:4000].lower()
                       or has_block_marker(resp.text))
            if blocked and attempt == 0 and self._rotate_session():
                continue
            if blocked:
                logger.info("ad-probe: %s -> unknown (blocked via curl_cffi), trying _browser_check fallback", url)
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

    def _browser_check_inner(self, url: str) -> bool | None:
        try:
            page = self._browser_page
            if page is None:
                return None
            host = urlparse(url).netloc
            if host not in self._browser_warmed_hosts:
                # domcontentloaded, not networkidle: ad-tech keeps portal
                # homepages busy forever, so networkidle just burns the timeout.
                home = f"https://{host}/"
                resp_home = page.goto(home, wait_until="domcontentloaded", timeout=25000)
                if resp_home and resp_home.status not in (403, 429):
                    self._browser_warmed_hosts.add(host)
                page.wait_for_timeout(3000)

            home_ref = f"https://{host}/"
            resp = page.goto(url, referer=home_ref, wait_until="domcontentloaded", timeout=25000)
            if not resp:
                return None
            # A definitive "gone" answer (404/410 or the portal's own "no longer
            # available" copy) is authoritative and must be read BEFORE the block
            # heuristic below: a genuinely removed ad page still ships DataDome's
            # anti-bot script, so the bare "captcha" substring test would
            # otherwise misfile a plainly-gone ad as "not verifiable" — the
            # window shows the "non più disponibile" page yet the batch reports
            # 0 removed. A real CAPTCHA wall carries neither signal, so this
            # cannot swallow a genuine block.
            if self._page_says_gone(resp, page):
                return False
            if (resp.status in (403, 429)
                    or "captcha" in page.content()[:4000].lower()
                    or has_block_marker(page.content())):
                page.wait_for_timeout(5000)
                if "captcha" in page.content()[:4000].lower():
                    if self._browser_headful and self._wait_for_human_solve(page):
                        # The user solved the challenge in the visible window:
                        # the shared profile now holds a real DataDome cookie.
                        # Re-navigate to read the ad through the cleared session.
                        resp = page.goto(url, referer=home_ref,
                                         wait_until="domcontentloaded", timeout=25000)
                        if not resp:
                            return None
                        if self._page_says_gone(resp, page):
                            return False
                    else:
                        # Headless (or the headful window went unsolved): report
                        # it as a block so a browser-first batch can abort on a
                        # streak instead of grinding an all-unknown run at ~25s
                        # per ad.
                        self.was_blocked = True
                        self.last_error = "Blocked by DataDome (browser CAPTCHA)"
                        return None
                elif resp.status in (403, 429) or has_block_marker(page.content()):
                    # A soft 403 with no CAPTCHA markup, or DataDome's static
                    # "temporarily restricted" wall served 200: still the portal
                    # refusing. Stay fail-open (None, never False) but feed the
                    # caller's block streak, or a repeated soft block would never
                    # trigger the abort/recovery levers.
                    self.was_blocked = True
                    self.last_error = f"Blocked by DataDome (browser HTTP {resp.status})"
                    return None
            path = urlparse(url).path.rstrip("/")
            if resp.status in (404, 410):
                return False
            if resp.status >= 400:
                return None
            if path and path not in urlparse(str(page.url)).path:
                return False
            is_online = not text_says_gone(page.content())
            if is_online:
                try:
                    from bs4 import BeautifulSoup
                    self.last_soup = BeautifulSoup(page.content(), "html.parser")
                except Exception:
                    pass
            try:
                cookies = self._browser_ctx.cookies(home_ref)
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
    def _page_says_gone(resp, page) -> bool:
        """A browser response that definitively means "ad gone": a 404/410
        status or the portal's own "no longer available" copy in the rendered
        page. Deliberately excludes the block heuristic (403/CAPTCHA) so callers
        can consult it *before* that check — a removed-ad page can still carry
        DataDome's anti-bot script, and only these signals are unambiguous."""
        try:
            if resp is not None and resp.status in (404, 410):
                return True
            return text_says_gone(page.content())
        except Exception:
            return False

    def _wait_for_human_solve(self, page) -> bool:
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
        deadline = _time.monotonic() + self._HEADFUL_SOLVE_TIMEOUT_MS / 1000.0
        logger.info("ad-probe: headful CAPTCHA — waiting up to %ds for the user to solve it",
                    int(self._HEADFUL_SOLVE_TIMEOUT_MS / 1000))
        while _time.monotonic() < deadline:
            if self._cancel_event is not None and self._cancel_event.is_set():
                logger.info("ad-probe: headful CAPTCHA wait cancelled by the user")
                return False
            page.wait_for_timeout(3000)
            try:
                if "captcha" not in page.content()[:4000].lower():
                    logger.info("ad-probe: headful CAPTCHA cleared by the user")
                    return True
            except Exception:
                # A navigation is likely in flight right after a solve; the ad
                # page reloads on its own, so keep polling rather than bail.
                pass
        logger.info("ad-probe: headful CAPTCHA not solved within the window")
        return False


# How many DOM levels the card-boundary climb may ascend before giving up.
# Measured card depths on both portals sit at 3-5 levels; the margin absorbs a
# few wrapper divs from a redesign. Shared with the email extractor's
# identical climb so the two cannot drift apart.
MAX_CARD_CLIMB = 8


def find_card_container(anchor, ad_path_re: re.Pattern):
    """Climbs from the ad link up to its card container.

    The card boundary is defined without relying on CSS classes: we climb up until
    the ancestor contains links to **only one** ad. The first ancestor containing two
    belongs to the results grid, so we stop right before it.

    This prevents climbing up into the page footer (where random numbers would be
    read as prices and square footage) when a card does not expose a price.

    `ad_path_re` must also match relative hrefs ("/annunci/123/"):
    this is how portals link ads within results pages.
    """
    def ad_ids(node) -> set[str]:
        ids = set()
        for a in node.find_all("a", href=True):
            m = ad_path_re.search(a["href"])
            if m:
                ids.add(m.group(1))
        return ids

    container = node = anchor
    for _ in range(MAX_CARD_CLIMB):
        parent = node.parent
        if parent is None or len(ad_ids(parent)) > 1:
            break
        container = node = parent
    return container


def extract_json_ld_blocks(html: str) -> list[dict]:
    """Extracts all <script type="application/ld+json"> blocks as dicts."""
    blocks = []
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            blocks.extend(d for d in data if isinstance(d, dict))
        elif isinstance(data, dict):
            blocks.append(data)
    return blocks
