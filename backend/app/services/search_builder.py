"""Native search builder: generates portal search URLs from structured
parameters (city, contract, price range, rooms, surface), so the user does
not have to copy/paste URLs from the browser.

The generated URLs use only *documented-by-usage* formats:
- Immobiliare filters travel in the query string (prezzoMinimo/prezzoMassimo/
  localiMinimo/localiMassimo/superficieMinima) — the same names its own site
  and the api-next fallback already understand (see immobiliare.py, which
  passes query params through unchanged).
- Idealista filters travel in a "con-…" path segment; the city segment is
  "municipality-province" (see idealista._city_from_url, which parses it
  back the same way).

The UI always shows the generated URL with an "open in browser" link before
saving: if a portal changes its URL grammar, the user sees it immediately.
"""
import re
import unicodedata
from typing import Any
from urllib.parse import parse_qs, urlparse

# Idealista encodes room counts as named segments with a numeric suffix
# ("con-trilocali/" is a 404 — verified live on 2026-07-09, along with every
# segment below and their comma-joined combinations). "quadrilocali-4" is
# the portal's own "4 or more" bucket.
IDEALISTA_ROOMS = {1: "monolocali-1", 2: "bilocali-2", 3: "trilocali-3",
                   4: "quadrilocali-4"}


def _slug(name: str) -> str:
    """"Sesto San Giovanni" -> "sesto-san-giovanni" (accents stripped)."""
    text = unicodedata.normalize("NFKD", (name or "").strip().lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def build_immobiliare_url(
    city: str, contract: str = "sale", zone: str = "",
    min_price: int | None = None, max_price: int | None = None,
    min_rooms: int | None = None, max_rooms: int | None = None,
    min_sqm: int | None = None, **_ignored,
) -> str:
    base = "affitto-case" if contract == "rent" else "vendita-case"
    query = []
    if min_price:
        query.append(f"prezzoMinimo={min_price}")
    if max_price:
        query.append(f"prezzoMassimo={max_price}")
    if min_rooms:
        query.append(f"localiMinimo={min_rooms}")
    if max_rooms:
        query.append(f"localiMassimo={max_rooms}")
    if min_sqm:
        query.append(f"superficieMinima={min_sqm}")
    # zone slugs are best-effort (the portal's own naming is not knowable
    # offline), so the UI shows the URL for verification before saving.
    # The api-next fallback copes either way: it resolves the last path
    # segment via geographic autocomplete and falls back to the municipality
    # when the zone is not recognised (see immobiliare._api_params).
    path = f"{_slug(city)}/{_slug(zone)}" if zone else _slug(city)
    url = f"https://www.immobiliare.it/{base}/{path}/"
    return f"{url}?{'&'.join(query)}" if query else url


def build_idealista_url(
    city: str, contract: str = "sale", province: str = "", zone: str = "",
    min_price: int | None = None, max_price: int | None = None,
    min_rooms: int | None = None, max_rooms: int | None = None,
    min_sqm: int | None = None, **_ignored,
) -> str:
    base = "affitto-case" if contract == "rent" else "vendita-case"
    # city segment is "municipality-province"; without a province the
    # municipality usually is the province capital (e.g. milano-milano).
    # Zone pages use a different grammar the scraper already parses back
    # (idealista._city_from_url): /vendita-case/milano/navigli/ — bare
    # municipality (NO province suffix), zone as the next segment.
    if zone:
        city_seg = f"{_slug(city)}/{_slug(zone)}"
    else:
        city_seg = f"{_slug(city)}-{_slug(province or city)}"
    filters = []
    if max_price:
        filters.append(f"prezzo_{max_price}")
    if min_price:
        filters.append(f"prezzo-min_{min_price}")
    if min_sqm:
        filters.append(f"dimensione_{min_sqm}")
    if min_rooms:
        # room segments are discrete categories, not a minimum: "3+ rooms"
        # is the union trilocali-3 + quadrilocali-4 (the portal's 4-or-more).
        # An explicit max_rooms narrows that union, otherwise a search the
        # user asked to cap at 3 locali would still return 4-room flats —
        # which Immobiliare's localiMassimo does honour, so the two portals
        # would disagree about the same profile.
        low = min(max(min_rooms, 1), 4)
        high = min(max_rooms, 4) if max_rooms else 4
        for n in range(low, max(high, low) + 1):
            filters.append(IDEALISTA_ROOMS[n])
    url = f"https://www.idealista.it/{base}/{city_seg}/"
    return f"{url}con-{','.join(filters)}/" if filters else url


def build_search_urls(params: dict) -> dict[str, str]:
    """Returns {"immobiliare": url, "idealista": url} for the given params."""
    return {
        "immobiliare": build_immobiliare_url(**params),
        "idealista": build_idealista_url(**params),
    }


def _safe_int(val: Any) -> int | None:
    if val is None:
        return None
    if isinstance(val, list) and val:
        val = val[0]
    try:
        if isinstance(val, str):
            val = re.sub(r"[^\d.]", "", str(val))
        return int(float(val)) if val else None
    except (ValueError, TypeError):
        return None


def _unslug_city(slug: str) -> str:
    """Restores Sesto-San-Giovanni -> Sesto San Giovanni, checking known spellings."""
    if not slug:
        return ""
    text = slug.replace("-", " ").strip()
    try:
        from .query_parser import CITY_SPELLINGS
        for name, proper in CITY_SPELLINGS.items():
            if _slug(name) == slug or name.lower() == text:
                return proper
    except ImportError:
        pass
    return text.title()


def _unslug_zone(slug: str) -> str:
    """Restores navigli -> Navigli."""
    if not slug:
        return ""
    return slug.replace("-", " ").strip().title()


def parse_immobiliare_url(url: str) -> dict[str, Any]:
    parsed = urlparse((url or "").strip())
    segments = [s for s in parsed.path.split("/") if s]
    contract = "rent" if segments and segments[0].startswith("affitto") else "sale"

    city = ""
    zone = ""
    if segments and segments[0] in ("vendita-case", "affitto-case", "vendita", "affitto"):
        if len(segments) >= 2:
            city = _unslug_city(segments[1])
            if len(segments) >= 3 and not segments[2].startswith(("pag", "search-list", "?")):
                zone = _unslug_zone(segments[2])
    elif segments and segments[0] not in ("search-list", "aree", "annunci"):
        city = _unslug_city(segments[0])
        if len(segments) >= 2 and not segments[1].startswith(("pag", "search-list", "?")):
            zone = _unslug_zone(segments[1])

    qs = parse_qs(parsed.query)
    return {
        "city": city,
        "province": "",
        "zone": zone,
        "contract": contract,
        "min_price": _safe_int(qs.get("prezzoMinimo", [None])[0]),
        "max_price": _safe_int(qs.get("prezzoMassimo", [None])[0]),
        "min_rooms": _safe_int(qs.get("localiMinimo", [None])[0]),
        "max_rooms": _safe_int(qs.get("localiMassimo", [None])[0]),
        "min_sqm": _safe_int(qs.get("superficieMinima", [None])[0]),
    }


def parse_idealista_url(url: str) -> dict[str, Any]:
    parsed = urlparse((url or "").strip())
    segments = [s for s in parsed.path.split("/") if s]
    contract = "rent" if segments and segments[0].startswith("affitto") else "sale"

    loc_segments = []
    start_idx = 1 if segments and segments[0] in ("vendita-case", "affitto-case", "vendita", "affitto") else 0
    for s in segments[start_idx:]:
        if s.startswith(("con-", "lista-", "pag-", "aree", "mappa")) or s == "?":
            break
        loc_segments.append(s)

    city = ""
    province = ""
    zone = ""
    if len(loc_segments) >= 2:
        city_slug = loc_segments[0]
        zone = _unslug_zone(loc_segments[1])
        tokens = [t for t in city_slug.split("-") if t]
        if len(tokens) > 1:
            city = _unslug_city("-".join(tokens[:-1]))
            province = _unslug_city(tokens[-1])
        else:
            city = _unslug_city(city_slug)
    elif len(loc_segments) == 1:
        city_slug = loc_segments[0]
        tokens = [t for t in city_slug.split("-") if t]
        if len(tokens) > 1:
            city = _unslug_city("-".join(tokens[:-1]))
            province = _unslug_city(tokens[-1])
        else:
            city = _unslug_city(city_slug)

    min_price = None
    max_price = None
    min_sqm = None
    rooms_found: list[int] = []

    filter_seg = next((s for s in segments if s.startswith("con-")), "")
    if filter_seg:
        filters = [f.strip() for f in filter_seg[4:].split(",") if f.strip()]
        for f in filters:
            if f.startswith(("prezzo-min_", "prezzo-min-")):
                min_price = _safe_int(f.split("_")[-1] if "_" in f else f.split("-")[-1])
            elif f.startswith(("prezzo_", "prezzo-")) and not f.startswith("prezzo-min"):
                max_price = _safe_int(f.split("_")[-1] if "_" in f else f.split("-")[-1])
            elif f.startswith(("dimensione_", "dimensione-")):
                min_sqm = _safe_int(f.split("_")[-1] if "_" in f else f.split("-")[-1])
            else:
                for num, r_slug in IDEALISTA_ROOMS.items():
                    if f == r_slug or f.startswith(f"{r_slug[:-2]}-"):
                        if num not in rooms_found:
                            rooms_found.append(num)
                m = re.match(r"^[a-z]+-(\d+)$", f)
                if m:
                    rn = int(m.group(1))
                    if 1 <= rn <= 10 and rn not in rooms_found and not f.startswith(("prezzo", "dimensione")):
                        rooms_found.append(rn)

    min_rooms = None
    max_rooms = None
    if rooms_found:
        rooms_found.sort()
        min_rooms = rooms_found[0]
        if 4 in rooms_found:
            if min_rooms == 4:
                max_rooms = None
            elif len(rooms_found) == (4 - min_rooms + 1):
                max_rooms = None
            else:
                max_rooms = rooms_found[-1]
        else:
            max_rooms = rooms_found[-1]
            if max_rooms == min_rooms:
                max_rooms = min_rooms

    return {
        "city": city,
        "province": province,
        "zone": zone,
        "contract": contract,
        "min_price": min_price,
        "max_price": max_price,
        "min_rooms": min_rooms,
        "max_rooms": max_rooms,
        "min_sqm": min_sqm,
    }


def parse_search_url(url: str) -> dict[str, Any]:
    """Extracts search builder parameters from a portal URL."""
    url_str = (url or "").strip()
    if "idealista.it" in url_str:
        return parse_idealista_url(url_str)
    if "immobiliare.it" in url_str:
        return parse_immobiliare_url(url_str)
    return {
        "city": "", "province": "", "zone": "", "contract": "sale",
        "min_price": None, "max_price": None, "min_rooms": None,
        "max_rooms": None, "min_sqm": None,
    }

