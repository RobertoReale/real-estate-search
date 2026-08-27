"""Optional engine: Idealista's official Search API (developers.idealista.com).

This is the one transport in the project that is *not* a workaround. It asks
Idealista for its own data, over OAuth2, with no DataDome in the way — no TLS
impersonation, no cookie, no browser, no proxy. It is therefore also the only
one that can go stale without anyone noticing, so it is built as a **second
engine behind `get_scraper`, never a replacement**: the HTML scraper stays
exactly as it was and takes over whenever this path cannot answer faithfully.

Three facts shape every decision below, and all three were established while
writing it:

1. **A key is issued by hand.** `developers.idealista.com` redirects to a single
   "get in touch and tell us a bit about your project" form; there is no
   self-service signup, and the technical documentation sits behind the same
   gate. So credentials are, and will remain, something the user pastes in —
   with none set this module does nothing at all.
2. **The request ceiling is not published anywhere.** It is agreed per key when
   the key is issued. An engine that cannot know its own budget must spend as
   little as it can: hence `idealista_api_max_pages` defaulting to **1** (one
   search request per profile scan, 50 listings) rather than reusing
   `max_pages_per_search`, whose 10 would be 10 requests per profile per hour.
   The access token is cached process-wide for the same reason — minting one
   costs a request like any other.
3. **The response field names are documented by third parties, not by a
   response we have seen.** Every read is therefore a defaulted `.get`: a
   renamed or absent field costs that one value, never the scan.

**The faithfulness rule.** A monitored search is a URL, and the URL's filters are
the search. This engine serves a search only when *every* filter in it maps to an
API parameter whose name and meaning are known; anything else falls back to the
HTML scraper. That is not caution for its own sake — the project's standing rule
is that portal filter tokens are measured against real result totals and never
inferred (see `services/search_builder.py`), and no total can be measured without
a key. The concrete casualty is rooms: this codebase counts Italian *locali*
while the API filters on `bedrooms`, and "locali − 1" is exactly the kind of
plausible guess that silently returns the wrong set. Declining is visible;
guessing is not.
"""

import base64
import json
import logging
import threading
import time
import urllib.parse
import urllib.request

from .base import RawListing, ScrapeResult
from .idealista import IdealistaScraper
from .parsing import detect_contract, plausible_price, to_float, to_int

logger = logging.getLogger(__name__)

TOKEN_URL = "https://api.idealista.com/oauth/token"
# Country in the path, and Italy is the only one this project monitors.
SEARCH_URL = "https://api.idealista.com/3.5/it/search"

# The API's own per-request ceiling.
MAX_ITEMS_PER_PAGE = 50

# No published rate limit either (see the module docstring), so one request per
# second is the conservative floor to pace pages at. With the default single
# page it never runs.
PAGE_DELAY_SECONDS = 1.0

_HTTP_TIMEOUT_SECONDS = 30
# Renew a little before the server would expire the token, so a scan that starts
# just under the wire does not fail its first search on a token that died in
# flight. The fallback TTL applies only if the response omits `expires_in`.
_TOKEN_SAFETY_MARGIN_SECONDS = 60.0
_FALLBACK_TOKEN_TTL_SECONDS = 3600.0

# Search-builder parameters this engine has no measured API parameter for. A URL
# carrying any of them is served by the HTML scraper instead — see the
# faithfulness rule in the module docstring.
UNMAPPED_FILTERS = (
    "zone",  # needs Idealista's internal locationId, which is not derivable offline
    "min_rooms",  # locali, and the API filters bedrooms — not the same count
    "max_rooms",
    "floor",
    "condition",
    "balcony",
    "garden",
    "parking",
    "elevator",
    "exclude_auctions",
    "pool",
)


class IdealistaApiError(Exception):
    """The official API could not answer. Always caught: the caller falls back."""


# (credentials, token, expiry). Process-wide and behind a lock for the same
# reason as the proxy pool's cool-downs: scraper instances are built per scan,
# and a token re-minted every scan is a request spent on nothing. Keyed by the
# credentials so editing them in Settings invalidates it without a restart.
_token_lock = threading.Lock()
_token_cache: tuple[tuple[str, str], str, float] | None = None


def credentials() -> tuple[str, str]:
    """(api_key, secret) from settings; ("", "") when the API is not configured."""
    from ..config import load_settings

    settings = load_settings()
    return (
        (settings.get("idealista_api_key") or "").strip(),
        (settings.get("idealista_api_secret") or "").strip(),
    )


def is_configured() -> bool:
    """Both halves of the credential present. This is the whole opt-in."""
    key, secret = credentials()
    return bool(key and secret)


def max_pages() -> int:
    """How many search requests one profile scan may spend. See docstring fact 2."""
    from ..config import load_settings

    try:
        configured = int(load_settings().get("idealista_api_max_pages") or 1)
    except (TypeError, ValueError):
        return 1
    return max(1, configured)


def _post_form(url: str, form: dict[str, str], headers: dict[str, str]) -> dict:
    """POST one form-encoded request and return the decoded JSON.

    The single network choke point, isolated exactly as `llm_parser`'s is so the
    tests drive the whole build-params → call → normalize path with nothing
    reaching a network. Plain `urllib`: this endpoint has no anti-bot to
    impersonate, and the project adds no dependency it does not need.
    """
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(form).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded", **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def access_token() -> str:
    """A cached OAuth2 access token, minting one only when the cache is cold."""
    global _token_cache

    key, secret = credentials()
    if not (key and secret):
        raise IdealistaApiError("no Idealista API credentials configured")

    with _token_lock:
        cached = _token_cache
    if cached and cached[0] == (key, secret) and cached[2] > time.monotonic():
        return cached[1]

    basic = base64.b64encode(f"{key}:{secret}".encode()).decode()
    try:
        payload = _post_form(
            TOKEN_URL,
            {"grant_type": "client_credentials", "scope": "read"},
            {"Authorization": f"Basic {basic}"},
        )
    except Exception as e:
        raise IdealistaApiError(f"token request failed: {e}") from e

    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise IdealistaApiError("the token response carried no access_token")
    ttl = to_float(payload.get("expires_in")) or _FALLBACK_TOKEN_TTL_SECONDS

    with _token_lock:
        _token_cache = (
            (key, secret),
            token,
            time.monotonic() + max(ttl - _TOKEN_SAFETY_MARGIN_SECONDS, 30.0),
        )
    return token


def unmapped_filters(params: dict) -> list[str]:
    """Which of the search's filters this engine cannot express, in URL order."""
    return [name for name in UNMAPPED_FILTERS if params.get(name)]


def search_plan(search_url: str) -> tuple[dict[str, str], str] | None:
    """(API parameters, comune) for a monitored search, or None to leave it to
    the scraper.

    The location travels as `center` + `distance` rather than Idealista's
    internal `locationId`, which cannot be resolved offline: the comuni
    gazetteer already holds a centroid and a size-scaled radius for every
    Italian comune (`services/geo_reference.py`), so the same data that decides
    whether a map pin is plausible also decides where to search. A comune the
    gazetteer does not know — or an ambiguous name like Castro BG vs Castro LE —
    answers None and the scraper takes it, exactly as `city_centroid` refuses to
    guess a pin.

    The comune comes back alongside the parameters because the caller needs it
    twice more (to narrow the circle's results, and to fill in a listing that
    names no municipality of its own), and re-parsing the URL for it would be a
    second reading that could disagree with this one.
    """
    from ..services import geo_reference
    from ..services.search_builder import parse_idealista_url

    params = parse_idealista_url(search_url)
    declined = unmapped_filters(params)
    if declined:
        logger.info(
            "idealista API: leaving this search to the scraper, no measured parameter for %s",
            ", ".join(declined),
        )
        return None

    city = (params.get("city") or "").strip()
    area = geo_reference.city_search_area(city)
    if not area:
        logger.info("idealista API: no known centroid for %r, using the scraper", city)
        return None
    lat, lng, radius_m = area

    out = {
        "country": "it",
        "locale": "it",
        "operation": "rent" if params.get("contract") == "rent" else "sale",
        "propertyType": "homes",
        "center": f"{lat:.6f},{lng:.6f}",
        "distance": str(int(radius_m)),
        "maxItems": str(MAX_ITEMS_PER_PAGE),
        "numPage": "1",
    }
    for param, key in (
        ("minPrice", "min_price"),
        ("maxPrice", "max_price"),
        ("minSize", "min_sqm"),
    ):
        value = params.get(key)
        if value:
            out[param] = str(int(value))
    return out, city


def search(params: dict[str, str]) -> dict:
    """One search request. Raises IdealistaApiError on anything that goes wrong."""
    try:
        payload = _post_form(SEARCH_URL, params, {"Authorization": f"Bearer {access_token()}"})
    except IdealistaApiError:
        raise
    except Exception as e:
        raise IdealistaApiError(f"search request failed: {e}") from e
    if not isinstance(payload, dict):
        raise IdealistaApiError(f"unexpected search response: {str(payload)[:200]}")
    return payload


def _element_to_listing(element: dict, contract: str, fallback_city: str) -> RawListing | None:
    """One `elementList` entry as the RawListing every other engine produces.

    Defensive throughout (docstring fact 3): the only field without which there
    is nothing to record is the ad id.
    """
    portal_id = str(element.get("propertyCode") or "").strip()
    if not portal_id:
        return None
    suggested = element.get("suggestedTexts")
    title = ""
    if isinstance(suggested, dict):
        title = str(suggested.get("title") or "").strip()
    address = str(element.get("address") or "").strip()
    return RawListing(
        portal="idealista",
        portal_id=portal_id,
        url=str(element.get("url") or f"https://www.idealista.it/immobile/{portal_id}/"),
        contract=contract,
        title=title or address,
        # "price on request" placeholders reach structured data too, exactly as
        # they reach the JSON-LD strategy: same guard, same bounds per contract.
        price=plausible_price(to_float(element.get("price")), contract),
        sqm=to_float(element.get("size")),
        rooms=to_int(element.get("rooms")),
        floor=str(element.get("floor") or ""),
        city=str(element.get("municipality") or "").strip() or fallback_city,
        zone=str(element.get("neighborhood") or element.get("district") or "").strip(),
        address=address,
        latitude=to_float(element.get("latitude")),
        longitude=to_float(element.get("longitude")),
        description=str(element.get("description") or ""),
        image_url=str(element.get("thumbnail") or ""),
        strategy="official-api",
    )


def _matches_city(listing: RawListing, city: str) -> bool:
    """Is this listing in the comune the search asked for?

    `center` + `distance` is a circle, so it reaches into neighbouring comuni —
    a Milano search would quietly return Sesto San Giovanni flats the equivalent
    portal page never shows. The API's own `municipality` is what narrows it
    back. A listing that carries no municipality is kept and stamped with the
    search's city, which is precisely what the HTML scraper does with every
    listing it parses (`_city_from_url`), so the two engines agree.
    """
    from ..services.geo_reference import same_comune

    if not city or not listing.city:
        return True
    return same_comune(listing.city, city)


def to_listings(payload: dict, contract: str, city: str) -> list[RawListing]:
    """`elementList` → RawListings, dropping anything outside the search's comune."""
    elements = payload.get("elementList")
    if not isinstance(elements, list):
        return []
    out = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        listing = _element_to_listing(element, contract, city)
        if listing is not None and _matches_city(listing, city):
            out.append(listing)
    return out


class IdealistaApiScraper(IdealistaScraper):
    """Idealista through its official API, falling back to the HTML scraper.

    A subclass rather than a sibling: everything except `scrape` — the parsing
    strategies, the pagination grammar, the TLS ladder — is what it falls back
    *to*, so inheriting it is what guarantees the fallback is the real scraper
    and not a second, drifting copy of it.
    """

    # Read by transport_policy.transport_used, so the Scraper Health panel says
    # which engine actually served the day's scans.
    used_official_api = False

    def scrape(self, search_url: str) -> ScrapeResult:
        result = self._scrape_via_api(search_url)
        if result is not None:
            self.used_official_api = True
            return result
        self.used_official_api = False
        return super().scrape(search_url)

    def _scrape_via_api(self, search_url: str) -> ScrapeResult | None:
        """The API path, or None when the HTML scraper should take this search.

        None on every failure, deliberately: an unmappable URL, an unknown
        comune, a refused key, an exhausted quota and a malformed response all
        mean the same thing to the caller — use the engine that is known to
        work. Fail-open is the house rule for optional paths, and here it has
        the full HTML scraper behind it.
        """
        contract = detect_contract(search_url)
        plan = search_plan(search_url)
        if plan is None:
            return None
        base_params, city = plan

        result = ScrapeResult(strategy_used="official-api")
        known: set[str] = set()
        for page in range(1, max_pages() + 1):
            try:
                payload = search({**base_params, "numPage": str(page)})
            except IdealistaApiError as e:
                # Mid-pagination this abandons the pages already collected: a
                # half-answered search would look to the scanner like listings
                # that vanished from the portal, and the HTML scraper is one
                # fallback away.
                logger.warning("idealista API: %s — falling back to the scraper", e)
                return None
            listings = [l for l in to_listings(payload, contract, city) if l.url not in known]
            known.update(l.url for l in listings)
            result.listings.extend(listings)
            result.pages_fetched += 1
            total_pages = to_int(payload.get("totalPages")) or 1
            if page >= total_pages or not listings:
                break
            time.sleep(PAGE_DELAY_SECONDS)

        if not result.listings:
            # Indistinguishable from a location that mapped badly, and the HTML
            # scraper can tell an empty search from a broken one by reading the
            # portal's own "nothing matched" page (invariant 16's rule, applied
            # to searches). Let it answer.
            logger.info("idealista API: no listings for %s, deferring to the scraper", search_url)
            return None
        self.contract = contract
        logger.info(
            "idealista API: %d listings over %d request(s)",
            len(result.listings),
            result.pages_fetched,
        )
        return result
