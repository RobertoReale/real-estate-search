"""Scraper for Immobiliare.it.

Primary path: the internal JSON API `api-next` (`_api_search`). It returns
structured JSON that survives the portal's frequent HTML/CSS redesigns (the
same schema feeds their mobile apps and Next.js frontend), so it is the low-
maintenance, stable acquisition path. It is tried FIRST: HTML search pages are
almost always DataDome-blocked, so leading with them only spent a guaranteed-
blocked request on every scan — tightening the block on the residential IP the
scans depend on (invariant 8) — before falling through to the API anyway.

HTML safety net (tried only if the API yields nothing), from most stable to
most fragile:
  1. JSON-LD (Schema.org)      — present in HTML pages
  2. __NEXT_DATA__ (Next.js)   — embedded page state
  3. Heuristic parsing         — no CSS classes, only immutable patterns

Strategies 1-3 stay as a deliberate fallback for the day the internal endpoint
changes or is removed: they cost nothing while the API works, and a passive
safety net is cheaper than no fallback at all.
"""

import json
import logging
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

from .base import BaseScraper, RawListing, ScrapeResult
from .html_cards import extract_json_ld_blocks, find_card_container
from .parsing import (
    detect_contract,
    parse_price,
    parse_rooms,
    parse_sqm,
    plausible_price,
    to_float,
    to_int,
)
from .transport import BlockedError

logger = logging.getLogger(__name__)

AD_URL_RE = re.compile(r"immobiliare\.it/annunci/(\d+)")
# hrefs in search result pages are relative: "/annunci/123/"
AD_PATH_RE = re.compile(r"/annunci/(\d+)")

API_LISTINGS = "https://www.immobiliare.it/api-next/search-list/listings/"
API_GEO = "https://www.immobiliare.it/api-next/geography/autocomplete/"
# The page the session warms up on, and the Referer the api-next calls carry.
# Named alongside the two endpoints because it is the same kind of fact — a
# portal URL this scraper actually *requests*, as opposed to the listing URLs
# it merely builds for the user to click.
HOMEPAGE = "https://www.immobiliare.it/"

# types returned by geographical autocomplete
GEO_NAZIONE, GEO_REGIONE, GEO_PROVINCIA, GEO_COMUNE, GEO_MACROZONA = -1, 0, 1, 2, 3

# The one spelling of the zone-id parameter this scraper sends. A URL can carry
# it bare (`idMZona[]`) or indexed (`idMZona[0]`, `idMZona[1]`) — the portal's
# own map emits both, as `fasciaPiano` does — and the geography autocomplete
# resolves a path zone into a third copy of the same key. Left as they arrive,
# one selection travelled as up to three different parameters and nothing in
# the code said which of them the portal was expected to read.
API_ZONE_ID_PARAM = "idMZona[]"

# Neither the geography nor the zone ids "win": they are the area and the
# filter inside it, and dropping either scans for the wrong thing. The resolved
# geography is what stops api-next answering with the whole of Italy
# (invariant 7); the ids narrow the search within the municipality it names.
# That is the portal's own grammar — clicking districts on its map keeps the
# path at the bare comune and appends one `idMZona[]` per district — so the two
# are always sent together, exactly as the URL the user pasted carried them.
#
# Nothing caps the list except the request itself. A conservative HTTP
# request-line ceiling is 8192 bytes (the common server default); the endpoint,
# the resolved geography and the user's own filters fit inside a 1 KB budget of
# it, and every further id costs `idMZona%5B%5D=NNNNN&` — 20 bytes. That leaves
# (8192 - 1024) / 20 ≈ 358, rounded down to a round number below it. A real
# selection cannot reach it: Milano, the largest, has fewer than a hundred
# macrozones in total. The limit is named rather than assumed so a selection
# that somehow did exceed it is refused with the number stated, instead of
# spending a whole scan on a request the portal silently truncated. Splitting
# such a selection across several requests is deliberately not done here — one
# search must stay one request.
MAX_ZONE_IDS = 300

# How this endpoint says "I looked, and there are none": it states the size of
# the result set beside the page it is returning. That statement is the whole
# signal — an empty `results` list is only an *answer* about the market when the
# portal also counted what it matched, because a soft block is served as exactly
# the same HTTP 200 with the same empty list and no count at all. Both spellings
# occur depending on the search, so the rule reads whichever one is present and
# treats their joint absence as the block it is. This is the api-next twin of
# `page_text.text_says_no_results`, which does the same job for the HTML path.
API_TOTAL_KEYS = ("count", "totalAds")


class ImmobiliareScraper(BaseScraper):
    portal = "immobiliare"
    # TLS profiles: inherited from BaseScraper (Safari-first, plus the newer
    # rotation entries). No override here — a shorter local list once shadowed
    # the base list's anti-block additions, leaving the real scans on exactly
    # the three profiles DataDome had already started rejecting.
    # HTML search pages are blocked under any impersonation:
    # no point rotating, proceed directly to API fallback
    rotate_on_block = False

    def __init__(self, delay_seconds: float = 6.0, max_pages: int = 10):
        super().__init__(delay_seconds=delay_seconds, max_pages=max_pages)
        self._warmed = False
        # At most one reactive cookie recovery per scrape: a fresh headless
        # harvest is expensive and, against a hard block, retrying it in a loop
        # only hammers the IP the scans need (invariant 8/18).
        self._cookie_recovered = False

    def warm_session(self) -> None:
        """Visits the homepage to obtain the DataDome cookie."""
        if self._warmed:
            return
        try:
            self.session.get(HOMEPAGE, allow_redirects=True)
            self._warmed = True
        except Exception:
            logger.warning("immobiliare: unable to warm up session")

    # ------------------------------------------------------------------
    # Data conversion for structure used both by __NEXT_DATA__ and internal API
    # ------------------------------------------------------------------
    def _entry_to_listing(self, entry: dict) -> RawListing | None:
        estate = entry.get("realEstate", entry)
        if not isinstance(estate, dict) or "id" not in estate:
            return None
        props = (estate.get("properties") or [{}])[0]
        price_obj = estate.get("price") or props.get("price") or {}
        location = props.get("location") or {}
        floor = props.get("floor") or {}

        photos = (props.get("multimedia") or {}).get("photos") or [{}]
        urls = photos[0].get("urls", {}) if photos else {}
        image = urls.get("medium") or urls.get("small") or urls.get("large") or ""

        seo_url = (entry.get("seo") or {}).get("url")

        return RawListing(
            portal=self.portal,
            portal_id=str(estate["id"]),
            url=seo_url or f"https://www.immobiliare.it/annunci/{estate['id']}/",
            title=estate.get("title", "") or "",
            # structured data carries "price on request" placeholders (0/1)
            # and monthly instalments: same sanity gate as the scraped text
            price=plausible_price(to_float(price_obj.get("value")), self.contract),
            sqm=parse_sqm(str(props.get("surface", ""))),
            # "rooms" can be a range ("2 - 4"): in that case it remains None
            rooms=to_int(props.get("rooms")),
            floor=str(floor.get("abbreviation") or floor.get("value") or ""),
            city=location.get("city") or "",
            zone=location.get("macrozone") or location.get("microzone") or "",
            address=location.get("address") or "",
            latitude=to_float(location.get("latitude")),
            longitude=to_float(location.get("longitude")),
            agency=((estate.get("advertiser") or {}).get("agency") or {}).get("displayName", ""),
            description=props.get("description") or estate.get("caption") or "",
            image_url=image,
        )

    # ------------------------------------------------------------------
    # Strategy 1: JSON-LD (Schema.org)
    # ------------------------------------------------------------------
    def parse_json_ld(self, html: str, page_url: str) -> list[RawListing]:
        out = []
        for block in extract_json_ld_blocks(html):
            items = []
            if block.get("@type") == "ItemList":
                items = [
                    e.get("item", e)
                    for e in block.get("itemListElement", [])
                    if isinstance(e, dict)
                ]
            elif block.get("@type") in (
                "RealEstateListing",
                "Product",
                "Offer",
                "Apartment",
                "House",
                "SingleFamilyResidence",
            ):
                items = [block]
            for item in items:
                listing = self._from_schema_org(item)
                if listing:
                    out.append(listing)
        return out

    def _from_schema_org(self, item: dict) -> RawListing | None:
        url = item.get("url") or item.get("@id") or ""
        m = AD_URL_RE.search(url)
        if not m:
            return None
        offers = item.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        address = item.get("address") or {}
        geo = item.get("geo") or {}
        floor_size = item.get("floorSize") or {}
        image = item.get("image")
        if isinstance(image, list):
            image = image[0] if image else ""
        if isinstance(image, dict):
            image = image.get("url", "")
        return RawListing(
            portal=self.portal,
            portal_id=m.group(1),
            url=url,
            title=item.get("name", ""),
            price=plausible_price(to_float(offers.get("price")), self.contract),
            sqm=to_float(floor_size.get("value")),
            rooms=to_int(item.get("numberOfRooms")),
            city=address.get("addressLocality", "") if isinstance(address, dict) else "",
            zone=address.get("addressRegion", "") if isinstance(address, dict) else "",
            address=address.get("streetAddress", "") if isinstance(address, dict) else "",
            latitude=to_float(geo.get("latitude")) if isinstance(geo, dict) else None,
            longitude=to_float(geo.get("longitude")) if isinstance(geo, dict) else None,
            description=item.get("description", ""),
            image_url=image or "",
        )

    # ------------------------------------------------------------------
    # Strategy 2: __NEXT_DATA__
    # ------------------------------------------------------------------
    def parse_embedded_state(self, html: str, page_url: str) -> list[RawListing]:
        m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if not m:
            return []
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            return []
        out = []
        for entry in self._find_results(data):
            listing = self._entry_to_listing(entry)
            if listing:
                out.append(listing)
        return out

    def _find_results(self, data) -> list[dict]:
        """Recursively searches for results list without depending on exact
        path inside __NEXT_DATA__ (which changes across site versions)."""
        if isinstance(data, dict):
            for key in ("results", "resultsList"):
                v = data.get(key)
                if (
                    isinstance(v, list)
                    and v
                    and isinstance(v[0], dict)
                    and ("realEstate" in v[0] or "id" in v[0])
                ):
                    return v
            for v in data.values():
                found = self._find_results(v)
                if found:
                    return found
        elif isinstance(data, list):
            for v in data:
                found = self._find_results(v)
                if found:
                    return found
        return []

    # ------------------------------------------------------------------
    # Strategy 3: heuristic parsing without CSS classes
    # ------------------------------------------------------------------
    def parse_heuristic(self, html: str, page_url: str) -> list[RawListing]:
        soup = BeautifulSoup(html, "html.parser")

        anchors: dict[str, list] = {}
        for a in soup.find_all("a", href=True):
            href = str(a["href"])
            full = href if href.startswith("http") else f"https://www.immobiliare.it{href}"
            m = AD_URL_RE.search(full)
            if m:
                anchors.setdefault(m.group(1), []).append((a, full))

        out = []
        for ad_id, items in anchors.items():
            best, full = max(items, key=lambda t: len(t[0].get_text(strip=True)))
            container = find_card_container(items[0][0], AD_PATH_RE)
            text = container.get_text(" ", strip=True)
            img = container.find("img")
            out.append(
                RawListing(
                    portal=self.portal,
                    portal_id=ad_id,
                    url=full,
                    title=best.get_text(" ", strip=True) or best.get("title", ""),
                    price=parse_price(text, self.contract),
                    sqm=parse_sqm(text),
                    rooms=parse_rooms(text),
                    description=text[:800],
                    image_url=(img.get("src") or img.get("data-src") or "") if img else "",
                )
            )
        return out

    def next_page_url(self, search_url: str, page: int) -> str:
        parsed = urlparse(search_url)
        qs = parse_qs(parsed.query)
        qs["pag"] = [str(page)]
        return urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))

    # ------------------------------------------------------------------
    # Strategy 4: internal API api-next (fallback when HTML is blocked)
    # ------------------------------------------------------------------
    def _resolve_geography(self, query: str) -> dict[str, str]:
        """Translates a location name (municipality or zone) into geographical
        parameters required by the API. Returns {} if unresolved."""
        resp = self.session.get(
            API_GEO,
            params={"query": query},
            headers={"Referer": HOMEPAGE},
        )
        if resp.status_code != 200:
            return {}
        try:
            items = resp.json()
        except json.JSONDecodeError:
            return {}
        if not items:
            return {}

        item = items[0]
        params: dict[str, str] = {}
        by_type = {p["type"]: p["id"] for p in (item.get("parents") or [])}
        by_type[item["type"]] = item["id"]

        if GEO_NAZIONE in by_type:
            params["idNazione"] = by_type[GEO_NAZIONE]
        if GEO_REGIONE in by_type:
            params["fkRegione"] = by_type[GEO_REGIONE]
        if GEO_PROVINCIA in by_type:
            params["idProvincia"] = by_type[GEO_PROVINCIA]
        if GEO_COMUNE in by_type:
            params["idComune"] = by_type[GEO_COMUNE]
        if GEO_MACROZONA in by_type:
            params["idMZona[]"] = by_type[GEO_MACROZONA]
        return params

    def _absorb_query(
        self, params: dict[str, str | list[str]], query: str
    ) -> dict[str, str | list[str]]:
        """Copies the URL's own filters into the API params, with every zone-id
        spelling collapsed into the single repeated `API_ZONE_ID_PARAM` list.

        The filters (prezzoMassimo, superficieMinima, sorting, …) already use
        the names the API expects, so they pass through untouched. The zone ids
        do not: a bare list, an indexed list and the macrozone the geography
        resolved out of the path are three spellings of one selection, and
        merging them here is what makes "which parameter the portal is sent"
        a thing the code states rather than a consequence of dict ordering.

        The URL's ids beat the path-resolved one because they are exact — they
        are the portal's own keys, and a path slug is a best-effort name. A URL
        that names a zone in its path *and* lists ids in its query is therefore
        searched on the ids alone; the geography's municipality stays, since it
        is the area the ids are read inside (invariant 7).
        """
        from ..services.search_builder import IMMOBILIARE_ZONE_ID_RE, zone_id_list

        path_ids = params.pop(API_ZONE_ID_PARAM, [])
        url_ids: list[str] = []
        for key, values in parse_qs(query).items():
            if key in ("pag", "path"):
                continue
            if IMMOBILIARE_ZONE_ID_RE.match(key):
                url_ids.extend(values)
                continue
            params[key] = values[0] if len(values) == 1 else values

        ids = zone_id_list(url_ids or ([path_ids] if isinstance(path_ids, str) else path_ids))
        if ids:
            params[API_ZONE_ID_PARAM] = ids
        return params

    def _api_params(self, search_url: str) -> dict[str, str | list[str]] | None:
        """Constructs API parameters starting from the user-pasted search URL."""
        parsed = urlparse(search_url)
        segments = [s for s in parsed.path.split("/") if s]
        if not segments:
            return None
        params: dict[str, str | list[str]] = {}

        # Custom search list / polygon URLs (e.g. /search-list/)
        if segments[0] == "search-list":
            self._absorb_query(params, parsed.query)
            if "idContratto" not in params:
                params["idContratto"] = "1"
            if "idCategoria" not in params:
                params["idCategoria"] = "1"
            params["path"] = parsed.path
            return params

        # e.g. "vendita-case" -> contract 1 (sale) / 2 (rental)
        contract = "2" if segments[0].startswith("affitto") else "1"

        # the location is the last segment (municipality, or zone inside municipality)
        if len(segments) < 2:
            return None
        location_query = segments[-1].replace("-", " ")
        geo = self._resolve_geography(location_query)
        if not geo:
            # fall back to municipality if zone cannot be resolved
            geo = self._resolve_geography(segments[1].replace("-", " "))
        if not geo:
            return None

        params.update(geo)
        params["idContratto"] = contract
        params["idCategoria"] = "1"
        params["path"] = parsed.path
        return self._absorb_query(params, parsed.query)

    def _api_get(self, params, referer: str, page: int):
        """Single api-next page request. Reads `self.session` at call time so a
        rotation or a cookie recovery between attempts takes effect."""
        return self.session.get(
            API_LISTINGS,
            params={**params, "pag": str(page)},
            headers={"Referer": referer},
        )

    def _recover_cookie(self) -> bool:
        """Reactive DataDome cookie recovery when api-next answers 403/429 under
        every impersonation. Opt-in (`datadome_auto_refresh`) and best-effort —
        the SAME lever the availability check fires on a block
        (`availability_check._try_cookie_recovery`) and the scanner runs before a scan
        (invariant 18): mint a fresh cookie in a headless browser, rebuild the
        session around it, re-warm the homepage so the new cookie is carried in.
        Returns whether it recovered. Never raises into the scrape."""
        from ..config import load_settings

        if not load_settings().get("datadome_auto_refresh"):
            return False
        from ..services import cookie_harvester

        if not cookie_harvester.is_available():
            return False
        logger.info("immobiliare: api-next blocking; grabbing a fresh DataDome cookie")
        try:
            recovery = cookie_harvester.refresh_into_settings("immobiliare", headless=True)
        except Exception:
            logger.exception("immobiliare: reactive cookie recovery failed")
            return False
        if not recovery.get("ok"):
            return False
        self._imp_index = 0
        self.session = self._new_session()
        self._warmed = False
        self.warm_session()
        return True

    def _classify_empty_first_page(self, data: dict, result: ScrapeResult) -> None:
        """Decide what a first api-next page that yielded no listing *means*.

        Three different things arrive here looking identical, and leaving them
        identical is the defect: an empty 200 was recorded as a successful scan
        of a quiet market, which is also precisely how a soft block presents.
        Only the middle branch leaves `result` untouched, and an untouched
        result is what `ScrapeResult.outcome` reads as `no_results`.
        """
        if data["results"]:
            # entries came back and not one of them survived parsing: the
            # api-next twin of the HTML path's "no listings extracted" alarm,
            # and a change to the payload's shape rather than an empty market.
            result.error = (
                "immobiliare: API returned entries none of which could be parsed — "
                "possible change of internal endpoint"
            )
        elif any(k in data for k in API_TOTAL_KEYS):
            # the portal counted its own results and the count is zero: an
            # answer, and the one case the user is entitled to see as such.
            logger.info("immobiliare: the portal answered, no listing matches this search")
        else:
            result.blocked = True
            result.error = (
                "immobiliare: API answered with neither listings nor a result count — "
                "treating it as a block rather than as an empty market"
            )

    def _api_search(self, search_url: str, result: ScrapeResult) -> None:
        result.page_limit = self.max_pages
        params = self._api_params(search_url)
        if params is None:
            result.error = "immobiliare: unable to parse search URL (unrecognized location)"
            return
        zone_ids = params.get(API_ZONE_ID_PARAM) or []
        if len(zone_ids) > MAX_ZONE_IDS:
            # Refuse rather than send it: over the request-line budget the
            # portal truncates the query and answers 200 for a *different*,
            # wider search, which is indistinguishable from the one that was
            # asked for. search_validator says the same thing before the
            # profile is ever saved; this is the backstop for a URL that
            # reached a scan anyway.
            result.error = (
                f"immobiliare: {len(zone_ids)} zones selected, more than the {MAX_ZONE_IDS} "
                "a single search URL can carry — split it into several searches"
            )
            return

        referer = urlunparse(urlparse(search_url)._replace(query=""))
        known: set[str] = set()
        max_pages = self.max_pages

        for page in range(1, self.max_pages + 1):
            self.report_progress(phase="fetching", page=page)
            resp = self._api_get(params, referer, page)
            if resp.status_code in (403, 429) and self._rotate_session():
                # retry the same page under a different TLS impersonation
                resp = self._api_get(params, referer, page)
            if (
                resp.status_code in (403, 429)
                and not self._cookie_recovered
                and self._recover_cookie()
            ):
                # every handshake blocked: the cookie has demonstrably burned —
                # mint a fresh one once and retry the page through it
                self._cookie_recovered = True
                resp = self._api_get(params, referer, page)
            if resp.status_code in (403, 429):
                result.blocked = True
                result.error = f"immobiliare: API blocked (HTTP {resp.status_code})"
                return
            if resp.status_code != 200:
                result.error = f"immobiliare: API HTTP {resp.status_code}"
                return
            try:
                data = resp.json()
            except json.JSONDecodeError:
                result.error = "immobiliare: invalid API response"
                return
            if "results" not in data:
                result.error = (
                    "immobiliare: API response without results — "
                    "possible change of internal endpoint"
                )
                return

            if page == 1:
                # The endpoint states the size of its own result set beside the
                # page it returns — the same declaration `_classify_empty_first_page`
                # reads to tell an empty market from a soft block, used here for
                # the other question it answers: how much of it this scan is
                # about to take.
                result.total_pages = to_int(data.get("maxPages"))
                for key in API_TOTAL_KEYS:
                    total = to_int(data.get(key))
                    if total is not None:
                        result.total_listings = total
                        break
                max_pages = min(self.max_pages, result.total_pages or self.max_pages)
                # This is the one acquisition path that learns a real page
                # total, so it is the one whose progress may be stated as a
                # proportion at all — and only when `maxPages` was actually
                # there, since a `None` passed on is a watcher's cue to count
                # rather than to draw a bar.
                self.report_progress(
                    total_pages=result.total_pages,
                    total_listings=result.total_listings,
                )

            page_listings = []
            for entry in data["results"]:
                listing = self._entry_to_listing(entry)
                if listing and listing.url not in known:
                    listing.strategy = "api-next"
                    known.add(listing.url)
                    page_listings.append(listing)

            if not page_listings:
                if page == 1:
                    self._classify_empty_first_page(data, result)
                break
            result.listings.extend(page_listings)
            result.pages_fetched += 1
            result.strategy_used = "api-next"
            self.report_progress(page=page, listings=len(result.listings))

            if page >= max_pages:
                # `max_pages` is the smaller of the cap and the portal's own
                # page count, so the two reasons for stopping here are told
                # apart by which one won: a search the cap cut short is the
                # only one that leaves listings unseen, and the only one the
                # scan may say so about.
                if (result.total_pages or 0) > self.max_pages:
                    result.truncated_by = "page_limit"
                break
            self.polite_sleep()

    # ------------------------------------------------------------------
    def scrape(self, search_url: str) -> ScrapeResult:
        # `super().scrape()` sets self.contract, but the API path runs first and
        # needs it (rent vs sale price bounds), so resolve it up front.
        self.contract = detect_contract(search_url)
        self.warm_session()

        # Primary: internal api-next. Stable JSON, and it avoids spending a
        # guaranteed-blocked HTML request (and its TLS rotations) on every scan.
        primary = ScrapeResult()
        try:
            self._api_search(search_url, primary)
        except BlockedError as e:
            primary.blocked = True
            primary.error = str(e)
        except Exception as e:
            logger.exception("immobiliare: api-next failed")
            primary.error = str(e)

        if primary.listings:
            for listing in primary.listings:
                listing.contract = self.contract
            return primary

        if primary.outcome == "no_results":
            # The portal answered, and its answer was "none". Falling through
            # would spend a guaranteed-blocked HTML request to confirm what has
            # already been established, and the block it earns would overwrite
            # a clean answer with an alarm — the exact confusion this path
            # exists to remove.
            return primary

        # Fallback safety net: the api-next endpoint changed/was removed (or the
        # block also reached it). Try the HTML strategies 1-3 (super().scrape()).
        logger.info("immobiliare: api-next unusable, falling back to HTML strategies")
        html = super().scrape(search_url)
        if html.listings:
            return html
        # no path succeeded: keep the most informative signal
        html.blocked = html.blocked or primary.blocked
        html.error = html.error or primary.error
        return html
