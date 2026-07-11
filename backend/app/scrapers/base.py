"""Scraper base: HTTP client with TLS impersonation, normalized listing dataclass,
and 3-strategy pipeline (JSON-LD -> embedded state -> heuristic parsing)
implemented in subclasses."""
import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

from curl_cffi import requests as curl_requests
from curl_cffi.requests.impersonate import BrowserTypeLiteral

logger = logging.getLogger(__name__)


class BlockedError(Exception):
    """The portal blocked the request (403/CAPTCHA DataDome etc.)."""


def detect_contract(search_url: str) -> str:
    """"sale" or "rent", inferred from the search URL path.

    Both portals encode the contract in the first path segment
    ("vendita-case" / "affitto-case"); Immobiliare's api-next fallback
    derives idContratto the same way.
    """
    path = (search_url or "").lower()
    return "rent" if "affitto" in path else "sale"


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
SQM_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*m[q²]", re.IGNORECASE)
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
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def parse_rooms(text: str) -> int | None:
    m = ROOMS_RE.search(text or "")
    return int(m.group(1)) if m else None


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
        self.session = self._new_session()

    def _new_session(self):
        session = curl_requests.Session(
            impersonate=self.impersonations[self._imp_index],
            timeout=30,
        )
        session.headers.update({
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.6",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        from ..config import load_settings
        settings = load_settings()
        try:
            proxy_url = (settings.get("proxy_url") or "").strip()
            if proxy_url:
                session.proxies = {"http": proxy_url, "https": proxy_url}

            # DataDome cookies are portal-specific: a cookie from one portal
            # is harmless on the other (the warm-up replaces it), but it will
            # not bypass anything there. The dot-prefix covers www. too.
            cookie_val = (settings.get("datadome_cookie") or "").strip()
            if cookie_val:
                session.cookies.set("datadome", cookie_val, domain=".immobiliare.it")
                session.cookies.set("datadome", cookie_val, domain=".idealista.it")
        except Exception as e:
            # A configured proxy that fails to apply means the user thinks
            # traffic is proxied when it is not: that must not be silent.
            if (settings.get("proxy_url") or "").strip():
                raise
            logger.warning("BaseScraper: failed to apply cookie settings: %s", e)
        return session

    def _rotate_session(self) -> bool:
        """Switch to the next impersonation profile. False if all exhausted."""
        if self._imp_index + 1 >= len(self.impersonations):
            return False
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

    def _fetch_once(self, url: str) -> str:
        resp = self.session.get(url, allow_redirects=True)
        if resp.status_code in (403, 429) or "captcha" in resp.text[:4000].lower():
            raise BlockedError(
                f"{self.portal}: blocked (HTTP {resp.status_code}) on {url}"
            )
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
                if page == 1:
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

    def __init__(self, delay_seconds: float = 6.0):
        super().__init__(delay_seconds=delay_seconds)
        self._warmed_hosts: set[str] = set()
        self.was_blocked = False
        self.last_error: str | None = None

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

    def check(self, url: str) -> bool | None:
        """True = still online, False = gone, None = could not tell."""
        self.was_blocked = False
        self.last_error = None
        self.warm_host(url)
        path = urlparse(url).path.rstrip("/")
        resp = None
        for attempt in (0, 1):
            try:
                resp = self.session.get(url, allow_redirects=True)
            except Exception as e:  # DNS, TLS, timeout: says nothing about the ad
                logger.info("ad-probe: %s -> unknown (%s)", url, e)
                self.last_error = f"Network error: {type(e).__name__}"
                return None
            blocked = (resp.status_code in (403, 429)
                       or "captcha" in resp.text[:4000].lower())
            if blocked and attempt == 0 and self._rotate_session():
                continue
            if blocked:
                logger.info("ad-probe: %s -> unknown (blocked)", url)
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
        page = resp.text.lower()
        return not any(marker in page for marker in AD_GONE_MARKERS)


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
    for _ in range(8):
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
