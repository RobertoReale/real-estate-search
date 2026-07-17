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
- Idealista zone searches go through its free-text endpoint,
  /cerca/<base>/con-<filters>/<Zone_City>/ — see build_idealista_url.

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


def cerca_location(city: str, zone: str = "") -> str:
    """"Milano" + "Udine Lambrate" -> "Udine_Lambrate_Milano".

    The free-text query Idealista's /cerca/ endpoint resolves server-side:
    words underscore-joined, zone first (it is the narrowing term), city last.
    """
    words = f"{zone} {city}".split() if zone else (city or "").split()
    return "_".join(w.title() if w.islower() else w for w in words)


def split_cerca_location(location: str) -> tuple[str, str]:
    """Inverse of cerca_location: "Udine_Lambrate_Milano" -> ("Milano",
    "Udine Lambrate").

    The split is ambiguous by construction — nothing in "Navigli_Sesto_San_
    Giovanni" marks where the zone ends — so known city spellings decide it,
    longest tail first. An unrecognised city falls back to "last token is the
    city", which is right for the one-word cities that dominate and wrong only
    for a multi-word city absent from CITY_SPELLINGS. That failure is safe:
    a wrong city blocks a cross-portal merge (invariant 1 demands proof of
    location), it can never forge one.
    """
    tokens = [t for t in (location or "").replace("%20", " ").split("_") if t]
    if not tokens:
        return "", ""
    try:
        from .query_parser import CITY_SPELLINGS
    except ImportError:
        CITY_SPELLINGS = {}
    for n in range(min(len(tokens), 4), 0, -1):
        proper = CITY_SPELLINGS.get(" ".join(tokens[-n:]).lower())
        if proper:
            return proper, " ".join(tokens[:-n]).title()
    return tokens[-1].title(), " ".join(tokens[:-1]).title()


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
    min_sqm: int | None = None, zone_page: bool = False, **_ignored,
) -> str:
    base = "affitto-case" if contract == "rent" else "vendita-case"
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
    con_seg = f"con-{','.join(filters)}/" if filters else ""

    # Idealista DOES have zone pages — /vendita-case/milano/forlanini/ is live,
    # 124 listings — but they are keyed by slugs of its own, and a zone's *name*
    # only sometimes happens to be one: /milano/bovisa/ and
    # /milano/udine-lambrate/ are 404s (with and without the province suffix;
    # measured live 2026-07-17, 7 of the 8 real searches in the database).
    # Nothing offline can tell the two apart, so the zone page is used only on
    # positive proof — see resolve_idealista_url, which probes it once when the
    # user generates the search. `zone_page=True` is that proof.
    if zone and zone_page:
        return (f"https://www.idealista.it/{base}/{_slug(city)}/{_slug(zone)}/"
                f"{con_seg}")
    # Unproven (or unprobed) zone: the free-text endpoint, which resolves the
    # location server-side and always answers. It honours the same con- filters
    # (the result total moves, 179 -> 112 with trilocali-3) and still paginates
    # with /lista-N.htm. It is a *text* search though, so it is broader than a
    # zone page — Forlanini gives 220 against the zone page's 124 — which is
    # why it is the fallback and not the first choice.
    if zone:
        return (f"https://www.idealista.it/cerca/{base}/{con_seg}"
                f"{cerca_location(city, zone)}/")
    # without a province the municipality usually is the province capital
    # (e.g. milano-milano).
    city_seg = f"{_slug(city)}-{_slug(province or city)}"
    return f"https://www.idealista.it/{base}/{city_seg}/{con_seg}"


def idealista_zone_page_url(city: str, zone: str, contract: str = "sale") -> str:
    """The bare zone page, no filters — what `probe_zone_page` asks about.

    Unfiltered on purpose: the question is "does Idealista know this zone
    slug?", and a filtered page can legitimately hold zero listings, which
    would read as "the slug is dead" and lose a perfectly good zone page.
    """
    base = "affitto-case" if contract == "rent" else "vendita-case"
    return f"https://www.idealista.it/{base}/{_slug(city)}/{_slug(zone)}/"


def probe_zone_page(url: str) -> bool | None:
    """True = the zone page exists and lists ads, False = 404, None = unknown.

    Fails open exactly like the availability probe (invariant 16): a DataDome
    block, a timeout or a 5xx answers None, never False. Here that matters less
    than it does there — both None and False land on /cerca/, which works — but
    the distinction keeps the caller's log honest about *why* it fell back.
    """
    from ..scrapers.base import AdProbe, BlockedError  # lazy: scrapers import us
    probe = AdProbe()
    try:
        probe.warm_host(url)
        html = probe.fetch(url)
    except BlockedError:
        return None
    except Exception as e:
        # raise_for_status turns the 404 into an HTTPError; anything else
        # (timeout, DNS, 5xx) is not the portal saying "no such zone".
        if "404" in str(e):
            return False
        return None
    return bool(re.search(r"/immobile/\d+", html)) or None


def resolve_idealista_url(params: dict, probe=None) -> tuple[str, bool]:
    """Returns (url, used_zone_page).

    A zone page is precise but only exists for the slugs Idealista recognises;
    /cerca/ is broader but universal. Nothing offline distinguishes the two, so
    this asks the portal once — at generate time, while the user is watching —
    and keeps the answer in the saved URL. Anything short of proof falls back to
    /cerca/, so a block or an outage costs precision, never a working search.
    """
    zone = (params.get("zone") or "").strip()
    if not zone:
        return build_idealista_url(**params), False
    check = probe or probe_zone_page
    ok = check(idealista_zone_page_url(
        params.get("city", ""), zone, params.get("contract", "sale")))
    if ok:
        return build_idealista_url(**{**params, "zone_page": True}), True
    return build_idealista_url(**params), False


def build_search_urls(params: dict, verify: bool = False) -> dict[str, Any]:
    """Returns {"immobiliare": url, "idealista": url} for the given params.

    `verify` costs one live request to Idealista, so it is opt-in: the UI sets
    it when the user presses Generate, and leaves it off when it is merely
    re-deriving a URL to prefill an edit form.
    """
    params = {k: v for k, v in params.items() if k != "verify"}
    idealista, zone_page = (
        resolve_idealista_url(params) if verify
        else (build_idealista_url(**params), False)
    )
    return {
        "immobiliare": build_immobiliare_url(**params),
        "idealista": idealista,
        "idealista_zone_page": zone_page,
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
    """Restores navigli -> Navigli, zona-navigli -> Navigli.

    Immobiliare prefixes some of its zone slugs with "zona-"
    (/vendita-case/milano/zona-navigli/). It is its own URL furniture, not part
    of the name: carried through, it reached Idealista's free-text search as
    "Zona Navigli Milano" — asking the portal to match the literal word "zona".
    """
    if not slug:
        return ""
    text = re.sub(r"^zona-", "", slug.strip())
    return text.replace("-", " ").strip().title()


def parse_immobiliare_url(url: str) -> dict[str, Any]:
    parsed = urlparse((url or "").strip())
    segments = [s for s in parsed.path.split("/") if s]
    contract = "rent" if segments and segments[0].startswith("affitto") else "sale"

    # "con-ascensore" & co. are FILTER segments, not zones: Immobiliare puts
    # them exactly where a zone would sit (/vendita-case/milano/con-ascensore/).
    # Reading one as a zone produced a search for a district named "Con
    # Ascensore" — and, once fed to build_idealista_url, the sibling URL
    # /vendita-case/milano/con-ascensore/con-prezzo_260000/ (two con- segments,
    # a guaranteed 404). Two such searches are saved in the live database.
    _NOT_A_ZONE = ("pag", "search-list", "con-", "?")

    city = ""
    zone = ""
    if segments and segments[0] in ("vendita-case", "affitto-case", "vendita", "affitto"):
        if len(segments) >= 2:
            city = _unslug_city(segments[1])
            if len(segments) >= 3 and not segments[2].startswith(_NOT_A_ZONE):
                zone = _unslug_zone(segments[2])
    elif segments and segments[0] not in ("search-list", "aree", "annunci"):
        city = _unslug_city(segments[0])
        if len(segments) >= 2 and not segments[1].startswith(_NOT_A_ZONE):
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
    # the contract segment leads the path on a city page but trails /cerca/,
    # so it is matched wherever it sits: keying off segments[0] read every
    # /cerca/ URL — zone searches, now all of them — as a sale.
    contract = "rent" if any(s.startswith("affitto") for s in segments) else "sale"

    city = ""
    zone = ""
    province = ""
    if segments and segments[0] == "cerca":
        # /cerca/<base>/con-<filters>/<Zone_City>/: the location is free text
        # and trails the filters, so it is found by exclusion, not by position.
        loc = next((s for s in segments[1:] if not s.startswith(
            ("vendita-", "affitto-", "con-", "lista-", "pag-"))), "")
        city, zone = split_cerca_location(loc)
        return _idealista_params(city, province, zone, contract, segments)

    loc_segments = []
    start_idx = 1 if segments[0] in ("vendita-case", "affitto-case", "vendita", "affitto") else 0
    for s in segments[start_idx:]:
        if s.startswith(("con-", "lista-", "pag-", "aree", "mappa")) or s == "?":
            break
        loc_segments.append(s)

    if loc_segments:
        tokens = [t for t in loc_segments[0].split("-") if t]
        if len(tokens) > 1:
            city = _unslug_city("-".join(tokens[:-1]))
            province = _unslug_city(tokens[-1])
        else:
            city = _unslug_city(loc_segments[0])
        if len(loc_segments) >= 2:
            zone = _unslug_zone(loc_segments[1])

    return _idealista_params(city, province, zone, contract, segments)


def _idealista_params(city: str, province: str, zone: str, contract: str,
                      segments: list[str]) -> dict[str, Any]:
    """Reads the con-… filter segment. Shared by both location grammars: the
    /cerca/ endpoint takes the very same filters as a city page (verified
    live), so parsing them twice would only let the two copies drift."""
    min_price = None
    max_price = None
    min_sqm = None
    rooms_found: list[int] = []

    # EVERY con- segment, not just the first: a URL carried over from
    # Immobiliare can hold two (/milano/con-ascensore/con-prezzo_260000/), and
    # stopping at the first one read the price/size filters as absent. That is
    # the dangerous direction — the rebuilt URL was a search for the whole of
    # Milano, ~7.800 listings instead of ~50.
    filters = [f.strip() for s in segments if s.startswith("con-")
               for f in s[4:].split(",") if f.strip()]
    if filters:
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

