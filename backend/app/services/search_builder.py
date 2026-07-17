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
# segment below and their comma-joined combinations).
#
# Room buckets are DISCRETE and exact — "quadrilocali-4" means exactly four.
# A comment here used to call it the portal's "4 or more" bucket; the portal's
# own UI disproves it: picking "2 o più locali" yields
# bilocali-2,trilocali-3,quadrilocali-4,5-locali-o-piu, and the totals are
# exactly additive (quadrilocali-4 = 367, 5-locali-o-piu = 141, both together
# = 508). While 4 was treated as the open-ended bucket, every "4+ rooms" search
# silently dropped all five-room flats — the failure shape of invariant 7.
IDEALISTA_ROOMS = {1: "monolocali-1", 2: "bilocali-2", 3: "trilocali-3",
                   4: "quadrilocali-4", 5: "5-locali-o-piu"}
IDEALISTA_MAX_ROOM_BUCKET = 5  # the only open-ended one: "5 locali o più"

# --- Feature filters -------------------------------------------------------
#
# Every mapping below is measured, never inferred from a portal's wording.
#
# Immobiliare renders ONE filter as a pretty path segment (/con-ascensore/) and
# the rest as query params; the params work on their own, which is what the
# builder uses — uniform, and the shape the user's own copied URLs already had.
# `fasciaPiano` was decoded from three combinations of the real UI:
# /con-piano-terra/?fasciaPiano[0]=20 = ground+middle and
# /con-piani-intermedi/?fasciaPiano[0]=30 = middle+top, so 20=middle, 30=top
# (two independent readings agree), leaving 10=ground.
IMMOBILIARE_FLOORS = {"ground": 10, "middle": 20, "top": 30}
# stato=N, read off the portal's own condition dropdown. "to_renovate" has no
# dropdown entry to read — the portal only ever renders it as the path segment
# /da-ristrutturare/, keeping it there even when another filter joins it — so 5
# was found by matching result totals: /da-ristrutturare/ and ?stato=5 both
# answer 1.816 against a 19.059 city.
IMMOBILIARE_CONDITION = {"new": 1, "good": 2, "excellent": 6, "to_renovate": 5}
#
# Idealista takes filters as comma-joined tokens in the con- segment. Each was
# confirmed live by watching its result total move; a token it does not know
# answers 404 rather than ignoring it, so nothing here passed silently.
#
# Guessing these is a trap worth remembering: probing found no elevator filter
# because every spelling tried was singular, and the portal's own UI writes
# "ascensori". A 404 means "not this word", never "no such filter" — when a
# token is wanted, read it off the portal's UI rather than inventing it.
IDEALISTA_FEATURES = {
    "balcony": "balcone",           # 3.477 -> 1.960
    "garden": "giardino",           # -> 1.203
    "parking": "garage",            # -> 763
    "elevator": "ascensori",        # 7.843 -> 5.331 (plural!)
    "exclude_auctions": "aste_no",  # 7.843 -> 6.899
    "pool": "piscina",              # 15.391 -> 201
}
IDEALISTA_FLOORS = {"ground": "piano-terra", "middle": "piani-intermedi",
                    "top": "ultimo-piano"}
IDEALISTA_CONDITION = {"new": "nuova-costruzione", "good": "buono-stato",
                       "to_renovate": "ristrutturare"}  # 15.391 -> 1.602
#
# "piscina" and "ristrutturare" were measured on Idealista months before they
# could be offered, because Immobiliare renders both only as path segments and
# keeps them there even when another filter joins them (/da-ristrutturare/?bagni=3
# is the portal's own output), so no query spelling ever surfaced to read. They
# stayed hidden rather than filter one portal and leave the other wide open — the
# silent asymmetry idealista_unsupported exists to prevent, in the direction
# nothing reports. Their query names were eventually found by matching totals
# instead of reading: ?stato=5 and ?piscina=1 each reproduce their path form's
# count exactly, while a bogus ?caratteristiche[]=piscina answers with the whole
# city (19.070) — Immobiliare ignores what it does not know and says nothing,
# which is why a control group is mandatory in any sweep here.
#
# Guessing loses in the other direction too: four spellings of an auction filter
# (escludi-aste, senza-asta, non-asta, no-aste) 404'd before the portal's own UI
# produced "aste_no" — the syntax was wrong, not just the word.


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
    min_sqm: int | None = None, balcony: bool = False, garden: bool = False,
    parking: bool = False, elevator: bool = False,
    exclude_auctions: bool = False, pool: bool = False, floor: str = "",
    condition: str = "",
    **_ignored,
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
    if balcony:
        query.append("balconeOterrazzo[]=balcone")
    if garden:
        query.append("giardino[]=10")  # 10 = private, 20 = shared
    if parking:
        query.append("boxAuto[]=1")  # 1 = single garage, 3 = double, 4 = space
    if elevator:
        query.append("ascensore=1")
    if exclude_auctions:
        query.append("noAste=1")
    if pool:
        query.append("piscina=1")
    if floor in IMMOBILIARE_FLOORS:
        query.append(f"fasciaPiano[]={IMMOBILIARE_FLOORS[floor]}")
    if condition in IMMOBILIARE_CONDITION:
        query.append(f"stato={IMMOBILIARE_CONDITION[condition]}")
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
    min_sqm: int | None = None, zone_page: bool = False, balcony: bool = False,
    garden: bool = False, parking: bool = False, elevator: bool = False,
    exclude_auctions: bool = False, pool: bool = False, floor: str = "",
    condition: str = "",
    **_ignored,
) -> str:
    base = "affitto-case" if contract == "rent" else "vendita-case"
    filters = []
    if max_price:
        filters.append(f"prezzo_{max_price}")
    if min_price:
        filters.append(f"prezzo-min_{min_price}")
    if min_sqm:
        filters.append(f"dimensione_{min_sqm}")
    if min_rooms or max_rooms:
        # room segments are discrete categories, not a minimum: "3+ rooms" is
        # the union trilocali-3 + quadrilocali-4 + 5-locali-o-piu, the last
        # being the portal's only open-ended bucket. An explicit max_rooms
        # narrows that union, otherwise a search the user asked to cap at 3
        # locali would still return 4-room flats — which Immobiliare's
        # localiMassimo does honour, so the two portals would disagree about
        # the same profile.
        #
        # Either bound alone is enough to build the union: gating this on
        # min_rooms once meant a cap-only search ("max 3 locali") emitted no
        # room segment at all, so Immobiliare filtered and Idealista returned
        # the whole city — the wider half reads as broken deduplication, not
        # as a missing filter.
        low = min(max(min_rooms or 1, 1), IDEALISTA_MAX_ROOM_BUCKET)
        high = (min(max_rooms, IDEALISTA_MAX_ROOM_BUCKET) if max_rooms
                else IDEALISTA_MAX_ROOM_BUCKET)
        for n in range(low, max(high, low) + 1):
            filters.append(IDEALISTA_ROOMS[n])
    # Fixed order, not set iteration: the same criteria must always produce a
    # byte-identical URL, or search_validator would read two spellings of one
    # search as two different searches (invariant 20's duplicate check
    # normalizes the query string, not the order of a path segment).
    for key, requested in (("balcony", balcony), ("garden", garden),
                           ("parking", parking), ("elevator", elevator),
                           ("exclude_auctions", exclude_auctions),
                           ("pool", pool)):
        if requested:
            filters.append(IDEALISTA_FEATURES[key])
    if floor in IDEALISTA_FLOORS:
        filters.append(IDEALISTA_FLOORS[floor])
    if condition in IDEALISTA_CONDITION:
        filters.append(IDEALISTA_CONDITION[condition])
    con_seg = f"con-{','.join(filters)}/" if filters else ""

    # Idealista DOES have zone pages, but they nest under a macro-area:
    # /vendita-case/milano/fiera-de-angeli/fiera/ is the portal's own three-level
    # URL. This two-level form is the special case where the zone *is* a
    # macro-area — /milano/forlanini/ is live with 124 listings, while
    # /milano/bovisa/ 404s because Bovisa's macro-area cannot be derived from its
    # name. Nothing offline can tell the two apart, so the zone page is used only
    # on positive proof — see resolve_idealista_url, which probes it once when the
    # user generates the search. `zone_page=True` is that proof, and the /cerca/
    # fallback below is what the other zones get until their macro-area is known.
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
    idealista, zone_page = (
        resolve_idealista_url(params) if verify
        else (build_idealista_url(**params), False)
    )
    return {
        "immobiliare": build_immobiliare_url(**params),
        "idealista": idealista,
        "idealista_zone_page": zone_page,
        "idealista_unsupported": idealista_unsupported(params),
    }


def idealista_unsupported(params: dict) -> list[str]:
    """Which of the requested filters Idealista cannot apply.

    Left unsaid, the Idealista half of a paired search would quietly be the
    wider one, and the extra listings would read as a deduplication failure
    rather than a filter that is not there.

    Two cases, both structural:
    - "excellent/renovated" condition: Immobiliare has stato=6 and Idealista's
      dropdown offers no equivalent.
    - a room cap of 5 or more: Idealista's top bucket is "5 locali o più", so
      any cap that needs it is open-ended, while Immobiliare's localiMassimo
      honours the cap exactly. A cap of 4 or less lands on discrete buckets and
      is expressible.

    Everything else once listed here turned out to exist under a name that had
    simply not been read off the portal yet — the elevator ("ascensori") and
    the auction exclusion ("aste_no"). Before adding an entry, check the
    portal's UI rather than a failed guess.
    """
    out = []
    if params.get("floor") and params["floor"] not in IDEALISTA_FLOORS:
        out.append("floor")
    if params.get("condition") and params["condition"] not in IDEALISTA_CONDITION:
        out.append("condition")
    max_rooms = params.get("max_rooms")
    if max_rooms and max_rooms >= IDEALISTA_MAX_ROOM_BUCKET:
        out.append("max_rooms")
    return out


def _safe_int(val: Any) -> int | None:
    """Coerce a single portal URL value into an int, or None if it holds no
    number. Callers pass one value (a query param already unwrapped from
    parse_qs's list, or a path token already split), never a collection."""
    if val is None:
        return None
    digits = re.sub(r"[^\d.]", "", str(val))
    if not digits:
        return None
    try:
        return int(float(digits))
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
    # Not every filter segment is spelled "con-": the condition ones are bare
    # adjectives ("da-ristrutturare", "nuove-costruzioni"), and the portal's own
    # /vendita-case/milano/da-ristrutturare/?bagni=3 would otherwise parse as a
    # district named "Da Ristrutturare".
    _NOT_A_ZONE = ("pag", "search-list", "con-", "?", "da-ristrutturare",
                   "nuove-costruzioni")

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
    # Immobiliare renders one filter as a path segment (/con-ascensore/) and
    # the rest as query params, so a filter must be looked for in both places
    # or a URL copied from the browser loses whichever one it made pretty.
    segs = set(segments)

    def _has(param: str, value: str = "", *, seg: str = "") -> bool:
        if seg and seg in segs:
            return True
        vals = qs.get(param) or qs.get(f"{param}[]") or qs.get(f"{param}[0]") or []
        return bool(vals) if not value else value in vals

    floor = ""
    for name, code in IMMOBILIARE_FLOORS.items():
        if str(code) in (qs.get("fasciaPiano[]") or qs.get("fasciaPiano[0]") or []):
            floor = name
    for name, seg in (("ground", "con-piano-terra"), ("middle", "con-piani-intermedi"),
                      ("top", "con-ultimo-piano")):
        if seg in segs:
            floor = name

    condition = ""
    for name, code in IMMOBILIARE_CONDITION.items():
        if str(code) in (qs.get("stato") or []):
            condition = name
    # the condition filters also travel as bare path segments
    for name, seg in (("to_renovate", "da-ristrutturare"),
                      ("new", "nuove-costruzioni")):
        if seg in segs:
            condition = name

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
        "balcony": _has("balconeOterrazzo", "balcone"),
        "garden": _has("giardino"),
        "parking": _has("boxAuto"),
        "elevator": _has("ascensore", seg="con-ascensore"),
        "exclude_auctions": _has("noAste"),
        "pool": _has("piscina", seg="con-piscina"),
        "floor": floor,
        "condition": condition,
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
    # Opaque zone ids and hand-drawn polygons carry no readable location: the
    # positional rule turned /multi/vendita-case/aOA,aOw/ into city "Multi",
    # zone "Vendita Case". Nothing to recover — leave the form blank rather
    # than prefill it with rubbish the user would then save.
    if segments and segments[0] in ("multi", "aree"):
        return _idealista_params("", "", "", contract, segments)
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
            # Idealista nests a zone under a macro-area:
            # /milano/fiera-de-angeli/fiera/ — three levels, the last being the
            # narrowest. Reading segment[1] named the macro-area ("Fiera De
            # Angeli") as the zone, so the form showed a search the URL was not.
            zone = _unslug_zone(loc_segments[-1])

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

    tokens = {f for s in segments if s.startswith("con-") for f in s[4:].split(",")}
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
        # Read back from the same table that writes them, so a token can never
        # be written and not parsed. The elevator and the auction exclusion were
        # hardcoded False here under a comment claiming Idealista had neither
        # filter; it has both ("ascensori", "aste_no"), so a profile built with
        # them lost them the moment the edit form re-parsed its own URL.
        **{key: token in tokens for key, token in IDEALISTA_FEATURES.items()},
        "floor": next((k for k, v in IDEALISTA_FLOORS.items() if v in tokens), ""),
        "condition": next((k for k, v in IDEALISTA_CONDITION.items() if v in tokens), ""),
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
        "max_rooms": None, "min_sqm": None, "balcony": False, "garden": False,
        "parking": False, "elevator": False, "exclude_auctions": False,
        "floor": "", "condition": "",
    }

