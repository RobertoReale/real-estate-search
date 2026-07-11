"""Scraper for Idealista.

Idealista is protected by DataDome: Safari's TLS handshake passes, while Chrome desktop
handshakes are rejected. Search pages do not contain JSON-LD or a stable embedded
state, so in practice the heuristic strategy does the work — which is precisely why
it exists: it does not depend on any CSS class.

Temporary blocks (403/CAPTCHA) are expected and handled without failing the
entire scan.
"""
import json
import logging
import re
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

from .base import (
    BaseScraper, RawListing, extract_json_ld_blocks, find_card_container,
    parse_price, parse_rooms, parse_sqm, to_float, to_int,
)

logger = logging.getLogger(__name__)

AD_URL_RE = re.compile(r"idealista\.it/immobile/(\d+)")
# hrefs in search result pages are relative: "/immobile/123/"
AD_PATH_RE = re.compile(r"/immobile/(\d+)")
LISTA_RE = re.compile(r"/lista-\d+(?:\.htm)?")


class IdealistaScraper(BaseScraper):
    portal = "idealista"
    # only TLS profiles accepted by DataDome on the idealista.it domain
    impersonations = ["safari184", "safari180", "chrome131_android"]

    def __init__(self, delay_seconds: float = 10.0, max_pages: int = 10):
        # increased delay: DataDome is sensitive to request frequency
        super().__init__(delay_seconds=max(delay_seconds, 8.0), max_pages=max_pages)
        self._warmed = False

    def warm_session(self) -> None:
        """Visits the homepage to obtain the DataDome cookie."""
        if self._warmed:
            return
        try:
            self.session.get("https://www.idealista.it/", allow_redirects=True)
            self._warmed = True
        except Exception:
            logger.warning("idealista: unable to warm up session")

    def scrape(self, search_url: str):
        self.warm_session()
        return super().scrape(search_url)

    @staticmethod
    def _city_from_url(page_url: str) -> str:
        """Extracts the municipality from the search path.

        Real Idealista formats (city segment is "municipality-province"):
          /vendita-case/milano-milano/               -> Milano
          /vendita-case/sesto-san-giovanni-milano/   -> Sesto San Giovanni
          /vendita-case/milano/navigli/              -> Milano (zone page)
          /aree/vendita-case/?shape=...              -> "" (polygon: city unknown)

        Better "" than an incorrect city: the city enters the fingerprint and
        deduplication matching, so a wrong value would prevent cross-portal
        merging (or worse, create false merges).
        """
        segments = [s for s in urlparse(page_url).path.split("/") if s]
        # the city segment immediately follows "vendita-case"/"affitto-case"
        city_seg = ""
        for i, seg in enumerate(segments):
            if seg.startswith(("vendita-", "affitto-")) and i + 1 < len(segments):
                city_seg = segments[i + 1]
                break
        if not city_seg or city_seg.startswith("lista-"):
            return ""
        tokens = [t for t in city_seg.replace("%20", " ").split("-") if t]
        if not tokens:
            return ""
        # "municipality-province": the last token is the province and must be discarded;
        # with only one token (zone page), the segment is already the municipality
        city_tokens = tokens[:-1] if len(tokens) > 1 else tokens
        return " ".join(city_tokens).strip().title()

    # ------------------------------------------------------------------
    # Strategy 1: JSON-LD (rarely present, but most stable when available)
    # ------------------------------------------------------------------
    def parse_json_ld(self, html: str, page_url: str) -> list[RawListing]:
        city = self._city_from_url(page_url)
        out = []
        for block in extract_json_ld_blocks(html):
            items = []
            if block.get("@type") == "ItemList":
                items = [
                    e.get("item", e) for e in block.get("itemListElement", [])
                    if isinstance(e, dict)
                ]
            elif "offers" in block or block.get("@type") in (
                "RealEstateListing", "Product", "Apartment", "House"
            ):
                items = [block]
            for item in items:
                url = item.get("url") or item.get("@id") or ""
                m = AD_URL_RE.search(url)
                if not m:
                    continue
                offers = item.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                image = item.get("image")
                if isinstance(image, list):
                    image = image[0] if image else ""
                out.append(RawListing(
                    portal=self.portal,
                    portal_id=m.group(1),
                    url=url,
                    title=item.get("name", ""),
                    price=to_float(offers.get("price")),
                    city=city,
                    description=item.get("description", ""),
                    image_url=image if isinstance(image, str) else "",
                ))
        return out

    # ------------------------------------------------------------------
    # Strategy 2: embedded state in inline JS objects
    # ------------------------------------------------------------------
    def parse_embedded_state(self, html: str, page_url: str) -> list[RawListing]:
        city = self._city_from_url(page_url)
        out = []
        for m in re.finditer(
            r'(?:window\.__INITIAL_PROPS__|listingItems)\s*[:=]\s*(\[.*?\])\s*[,;}]',
            html, re.DOTALL,
        ):
            try:
                items = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                ad_id = item.get("adId") or item.get("propertyCode") or item.get("id")
                if not ad_id:
                    continue
                out.append(RawListing(
                    portal=self.portal,
                    portal_id=str(ad_id),
                    url=item.get("url")
                        or f"https://www.idealista.it/immobile/{ad_id}/",
                    title=item.get("title", "") or "",
                    price=to_float(item.get("price")),
                    sqm=to_float(item.get("size")),
                    rooms=to_int(item.get("rooms")),
                    latitude=to_float(item.get("latitude")),
                    longitude=to_float(item.get("longitude")),
                    city=item.get("municipality") or city,
                    address=item.get("address", ""),
                    description=item.get("description", ""),
                    image_url=item.get("thumbnail", ""),
                ))
            if out:
                break
        return out

    # ------------------------------------------------------------------
    # Strategy 3: heuristic card parsing — no CSS classes, only immutable
    # patterns (URL /immobile/<id>, € symbol, "N locali", "N m²")
    # ------------------------------------------------------------------
    def parse_heuristic(self, html: str, page_url: str) -> list[RawListing]:
        soup = BeautifulSoup(html, "html.parser")
        city = self._city_from_url(page_url)

        # a card contains multiple links to the same ad (photo, title, etc.):
        # we group by id and pick the one with the richest text
        anchors: dict[str, list] = {}
        for a in soup.find_all("a", href=True):
            href = str(a["href"])
            full = href if href.startswith("http") else f"https://www.idealista.it{href}"
            m = AD_URL_RE.search(full)
            if m:
                anchors.setdefault(m.group(1), []).append((a, full))

        out = []
        for ad_id, items in anchors.items():
            best, full = max(items, key=lambda t: len(t[0].get_text(strip=True)))
            title = best.get_text(" ", strip=True) or best.get("title", "")

            container = find_card_container(items[0][0], AD_PATH_RE)
            text = container.get_text(" ", strip=True)
            img = container.find("img")

            out.append(RawListing(
                portal=self.portal,
                portal_id=ad_id,
                url=full,
                title=title,
                price=parse_price(text, self.contract),
                sqm=parse_sqm(text),
                rooms=parse_rooms(text),
                city=city,
                address=self._address_from_title(title),
                # the card text contains the descriptive snippet:
                # needed for keyword filtering
                description=text[:800],
                image_url=(img.get("src") or img.get("data-src") or "") if img else "",
            ))
        return out

    @staticmethod
    def _address_from_title(title: str) -> str:
        """"Trilocale in Via Volvinio, 26, Stadera, Milano" -> "Via Volvinio, 26"."""
        m = re.search(r"\bin\s+(.+)", title or "")
        if not m:
            return ""
        parts = [p.strip() for p in m.group(1).split(",")]
        return ", ".join(parts[:2])

    def next_page_url(self, search_url: str, page: int) -> str:
        # Idealista paginates with /lista-N.htm in the path
        parsed = urlparse(search_url)
        path = LISTA_RE.sub("", parsed.path).rstrip("/")
        return urlunparse(parsed._replace(path=f"{path}/lista-{page}.htm"))
