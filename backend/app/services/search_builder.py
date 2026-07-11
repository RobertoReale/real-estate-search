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
