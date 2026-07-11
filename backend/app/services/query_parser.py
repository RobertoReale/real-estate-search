"""Natural-language search assistant: turns "2-bedroom rental in Milan under
1200€" into the structured parameters the native search builder already
consumes (services/search_builder.py).

**Why a hand-written parser and not an LLM call.** The whole point of this
app is that it runs on the user's PC with no cloud account, no API key, and
no listing data leaving the machine. Routing every query through a remote
model would trade that for a marginal gain: the query space here is tiny
(city, contract, price, rooms, surface), and users type it in one of a dozen
shapes. So this module is deterministic, offline, unit-testable, and
answers in microseconds — and it *shows its work* (`interpretation`) so a
misreading is visible before any profile is created, instead of silently
producing a search URL for the wrong city.

The parser never guesses silently: anything it could not resolve comes back
in `warnings`, and the UI pre-fills the search builder form so the user
reviews and corrects before saving.

Bilingual by necessity: the portals are Italian, the users think in Italian,
but the roadmap's own example is in English.
"""
import re
import unicodedata

# Cities whose portal spelling differs from what a user may type (English
# exonyms, mostly). Multi-word entries are matched before single words, so
# "reggio emilia" never degrades into "reggio".
CITY_SPELLINGS: dict[str, str] = {
    "milan": "Milano", "milano": "Milano",
    "rome": "Roma", "roma": "Roma",
    "turin": "Torino", "torino": "Torino",
    "naples": "Napoli", "napoli": "Napoli",
    "florence": "Firenze", "firenze": "Firenze",
    "venice": "Venezia", "venezia": "Venezia",
    "genoa": "Genova", "genova": "Genova",
    "padua": "Padova", "padova": "Padova",
    "mantua": "Mantova", "mantova": "Mantova",
    "bologna": "Bologna", "palermo": "Palermo", "bari": "Bari",
    "catania": "Catania", "verona": "Verona", "messina": "Messina",
    "trieste": "Trieste", "brescia": "Brescia", "parma": "Parma",
    "modena": "Modena", "livorno": "Livorno", "cagliari": "Cagliari",
    "perugia": "Perugia", "salerno": "Salerno", "rimini": "Rimini",
    "ferrara": "Ferrara", "pescara": "Pescara", "monza": "Monza",
    "bergamo": "Bergamo", "como": "Como", "pisa": "Pisa", "lecce": "Lecce",
    "trento": "Trento", "bolzano": "Bolzano", "udine": "Udine",
    "ancona": "Ancona", "novara": "Novara", "varese": "Varese",
    "pavia": "Pavia", "cremona": "Cremona", "lodi": "Lodi",
    "piacenza": "Piacenza", "ravenna": "Ravenna", "siena": "Siena",
    "lucca": "Lucca", "prato": "Prato", "taranto": "Taranto",
    "foggia": "Foggia", "reggio emilia": "Reggio Emilia",
    "reggio calabria": "Reggio Calabria", "la spezia": "La Spezia",
    "sesto san giovanni": "Sesto San Giovanni",
    "cinisello balsamo": "Cinisello Balsamo",
    "san donato milanese": "San Donato Milanese",
    "castellanza": "Castellanza", "legnano": "Legnano", "busto arsizio":
    "Busto Arsizio", "rho": "Rho", "seregno": "Seregno", "desio": "Desio",
}

# Only the provinces of the non-capital municipalities listed above: for a
# provincial capital the search builder already defaults province = city.
PROVINCE_CODES: dict[str, str] = {
    "mi": "Milano", "rm": "Roma", "to": "Torino", "na": "Napoli",
    "fi": "Firenze", "ve": "Venezia", "ge": "Genova", "bo": "Bologna",
    "mb": "Monza", "va": "Varese", "co": "Como", "bg": "Bergamo",
    "bs": "Brescia", "pv": "Pavia", "no": "Novara", "pd": "Padova",
    "vr": "Verona", "ba": "Bari", "pa": "Palermo", "ct": "Catania",
}

RENT_WORDS = (
    "affitto", "affitti", "affittare", "affittasi", "locazione",
    "rent", "rental", "renting", "to let", "al mese", "/mese", "mensile",
    "mensili", "per month", "a month", "monthly",
)
SALE_WORDS = (
    "vendita", "vendesi", "comprare", "acquisto", "acquistare", "compro",
    "buy", "buying", "purchase", "for sale", "sale",
)

# Ordinals used by Italian portals for room counts.
ROOM_WORDS = {"monolocale": 1, "monolocali": 1, "bilocale": 2, "bilocali": 2,
              "trilocale": 3, "trilocali": 3, "quadrilocale": 4,
              "quadrilocali": 4}

# Units that disqualify a number from being read as a price ("80 mq").
UNIT_WORDS = (
    "mq", "m2", "m²", "mq.", "metri", "metro", "sqm", "sq m", "square",
    "locali", "locale", "stanze", "stanza", "vani", "vano", "camere",
    "camera", "bedroom", "bedrooms", "room", "rooms", "bagni", "bagno",
    "piano", "km",
)

MAX_WORDS = ("sotto", "sotto i", "under", "max", "massimo", "meno di",
             "fino a", "entro", "budget", "non oltre", "al massimo", "<")
MIN_WORDS = ("sopra", "almeno", "over", "min", "minimo", "piu di",
             "a partire da", "oltre", "at least", "starting", ">")

# 1.200 / 1200 / 1,2 / 300k / 300 mila / 1,2 mln
_NUMBER = r"\d{1,3}(?:\.\d{3})+|\d+(?:[.,]\d+)?"
# the trailing \b is what keeps "80 m2" from parsing as 80 million euros:
# the bare "m" multiplier only counts when nothing word-like follows it
_MULT = r"(?:k|mila|mln|mil|milioni|milione|m)?\b"
_CURRENCY = r"(?:\s*(?:€|euro|eur))?"
_MONEY_RE = re.compile(
    rf"({_NUMBER})\s*({_MULT}){_CURRENCY}", re.IGNORECASE
)


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _normalize(text: str) -> str:
    """Lowercase, accent-free, single-spaced: the form every regex expects."""
    return re.sub(r"\s+", " ", _strip_accents(text).lower()).strip()


def _parse_number(raw: str, multiplier: str) -> float:
    """"1.200" -> 1200, "1,2" + "mln" -> 1_200_000, "300" + "k" -> 300_000."""
    mult = multiplier.lower()
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        value = float(raw.replace(".", ""))       # dots are thousands
    else:
        value = float(raw.replace(",", "."))      # commas are decimals
    if mult in ("k", "mila"):
        return value * 1_000
    if mult in ("mln", "mil", "milioni", "milione", "m"):
        return value * 1_000_000
    return value


def _is_price_token(text: str, match: re.Match, value: float,
                    multiplier: str) -> bool:
    """A bare number is a price only if it is marked as money (€, k, mila,
    mln) or is too large to be anything else. Without this, "80 mq" and
    "3 locali" become a 80 € budget and a 3 € budget."""
    tail = text[match.end():match.end() + 12].strip()
    if tail.startswith(UNIT_WORDS):
        return False
    if multiplier or "€" in match.group(0) or "eur" in match.group(0).lower():
        return True
    return value >= 100


def _money_matches(text: str) -> list[tuple[int, int, float]]:
    """(start, end, value) for every token in `text` that reads as money."""
    found = []
    for m in _MONEY_RE.finditer(text):
        multiplier = m.group(2) or ""
        value = _parse_number(m.group(1), multiplier)
        if _is_price_token(text, m, value, multiplier):
            found.append((m.start(), m.end(), value))
    return found


def _keyword_before(text: str, start: int, words: tuple[str, ...]) -> bool:
    """True when one of `words` sits in the ~24 characters preceding a token:
    that is the window in which "under"/"sotto i"/"max" binds to a number."""
    window = text[max(0, start - 24):start]
    return any(re.search(rf"(?:^|\W){re.escape(w)}\W*$", window) for w in words)


def _parse_prices(text: str) -> tuple[int | None, int | None, list[str]]:
    """Returns (min_price, max_price, warnings)."""
    # An explicit range wins: "tra 200k e 300k" would otherwise be read as a
    # minimum ("da 200k") with a stray number after it.
    range_re = re.compile(
        rf"(?:tra|between|from|da)\s+({_NUMBER})\s*({_MULT}){_CURRENCY}"
        rf"\s*(?:e|and|a|to|-|–)\s*({_NUMBER})\s*({_MULT}){_CURRENCY}",
        re.IGNORECASE,
    )
    m = range_re.search(text)
    if m:
        low = _parse_number(m.group(1), m.group(2) or "")
        high = _parse_number(m.group(3), m.group(4) or "")
        if low >= 100 and high >= 100:
            low, high = sorted((low, high))
            return int(low), int(high), []

    tokens = _money_matches(text)
    min_price = max_price = None
    unbound: list[float] = []
    for start, _end, value in tokens:
        if _keyword_before(text, start, MAX_WORDS):
            max_price = value if max_price is None else min(max_price, value)
        elif _keyword_before(text, start, MIN_WORDS):
            min_price = value if min_price is None else max(min_price, value)
        else:
            unbound.append(value)

    warnings: list[str] = []
    if min_price is None and max_price is None and len(unbound) == 1:
        # "casa a Milano 300k" — a lone budget figure is a ceiling: nobody
        # searches for a house that costs *at least* what they can afford
        max_price = unbound[0]
    elif unbound and (min_price is not None or max_price is not None):
        warnings.append(
            "Ignored an ambiguous amount: "
            + ", ".join(f"{int(v):,}".replace(",", ".") + " €" for v in unbound)
        )
    elif len(unbound) > 1:
        low, high = min(unbound), max(unbound)
        return int(low), int(high), []

    to_int = lambda v: int(v) if v is not None else None  # noqa: E731
    return to_int(min_price), to_int(max_price), warnings


def _parse_rooms(text: str) -> tuple[int | None, int | None, list[str]]:
    """Returns (min_rooms, max_rooms, notes).

    Italian portals count *locali* (every room but kitchen and bathrooms),
    while "2-bedroom" counts bedrooms only. A 2-bedroom flat is a trilocale
    once the living room is counted, so bedrooms are translated with +1 and
    the assumption is stated out loud in the interpretation.
    """
    notes: list[str] = []
    for word, count in ROOM_WORDS.items():
        if re.search(rf"\b{word}\b", text):
            return count, count, notes

    at_least = re.compile(
        rf"(?:{'|'.join(re.escape(w) for w in MIN_WORDS)})\s*(\d+)\s*"
        r"\+?\s*(?:locali|stanze|vani|rooms?)"
    )
    m = at_least.search(text)
    if m:
        return int(m.group(1)), None, notes

    m = re.search(r"(\d+)\s*\+\s*(?:locali|stanze|vani|rooms?)", text)
    if m:
        return int(m.group(1)), None, notes

    m = re.search(r"(\d+)\s*(?:locali|locale|stanze|stanza|vani|vano)", text)
    if m:
        rooms = int(m.group(1))
        return rooms, rooms, notes

    # bedrooms: "2 camere", "2-bedroom", "two bedrooms"
    m = re.search(r"(\d+)\s*[- ]?\s*(?:camere(?: da letto)?|camera(?: da letto)?"
                  r"|bedrooms?|bed)", text)
    if m:
        bedrooms = int(m.group(1))
        rooms = bedrooms + 1
        notes.append(
            f"{bedrooms} bedroom{'s' if bedrooms > 1 else ''} read as "
            f"{rooms} locali (Italian portals count the living room too)"
        )
        return rooms, rooms, notes

    return None, None, notes


def _parse_sqm(text: str) -> tuple[int | None, list[str]]:
    """Only *minimum* surface exists in the builder's URL grammar. A number
    introduced by a MAX keyword ("max 100 mq") must therefore be dropped, not
    silently flipped into a minimum — which would search for the opposite of
    what was asked."""
    unit = r"(?:mq|m2|m²|metri quadri|metri quadrati|metri|sqm|square meters?)"
    warnings: list[str] = []
    for m in re.finditer(rf"(\d+)\s*{unit}", text):
        if _keyword_before(text, m.start(), MAX_WORDS):
            warnings.append(
                "Maximum surface is not supported by the portals' URL filters "
                "— ignored (use the dashboard's own filters instead)"
            )
            continue
        return int(m.group(1)), warnings
    return None, warnings


def _parse_contract(text: str) -> tuple[str, bool]:
    """Returns (contract, was_explicit). Sale is the default because it is
    the overwhelmingly common case — but the caller says so in the UI."""
    if any(re.search(rf"(?:^|\W){re.escape(w)}(?:\W|$)", text) for w in RENT_WORDS):
        return "rent", True
    if any(re.search(rf"(?:^|\W){re.escape(w)}(?:\W|$)", text) for w in SALE_WORDS):
        return "sale", True
    return "sale", False


def _parse_city(text: str, original: str) -> tuple[str, str]:
    """Returns (city, province), both possibly empty.

    Known municipalities are matched first (longest name first, so "reggio
    emilia" beats "reggio"). Only if none matches does the parser fall back
    to "the capitalized words after a locative preposition" — a guess, which
    is why the caller always shows it back to the user.
    """
    province = ""
    # a single word: "provincia di Monza e Brianza" is the province of Monza
    m = re.search(r"(?:provincia di|province of)\s+([a-z']{3,20})", text)
    if m:
        province = m.group(1).title()
    else:
        m = re.search(r"\(([a-z]{2})\)", text)
        if m and m.group(1) in PROVINCE_CODES:
            province = PROVINCE_CODES[m.group(1)]

    # longest first: "reggio emilia" must never degrade into "reggio"
    for name in sorted(CITY_SPELLINGS, key=len, reverse=True):
        if re.search(rf"(?:^|\W){re.escape(name)}(?:\W|$)", text):
            # a provincial capital needs no province: search_builder defaults
            # it to the city itself
            return CITY_SPELLINGS[name], province

    # fallback: "a Sesto Calende", "in Cernusco sul Naviglio". "zona" is NOT
    # a city preposition anymore: zone names are parsed (and blanked out)
    # separately by _parse_zone, so they can no longer masquerade as cities.
    m = re.search(r"(?:^|\W)(?:a|ad|in|near|vicino a)\s+"
                  r"([A-ZÀ-Þ][\w'’-]+(?:\s+[A-ZÀ-Þ][\w'’-]+){0,2})", original)
    if m:
        return m.group(1).strip(), province
    return "", province


# --- Zones -------------------------------------------------------------------

# Words that terminate a zone name: the capture regex is greedy on purpose
# (zone names can be multi-word, "Porta Romana") and is trimmed back here.
ZONE_STOP_WORDS = {
    "a", "ad", "in", "con", "sotto", "sopra", "max", "min", "minimo",
    "massimo", "fino", "entro", "tra", "da", "per", "e", "o", "oppure", "or",
    "budget", "almeno", "under", "over", "between", "from", "near", "vicino",
    "euro", "eur", "circa",
}

_ZONE_RE = re.compile(
    r"(?:^|\W)(?:zona|quartiere|rione|district)\s+"
    r"([A-Za-zÀ-ÿ'’\-]+(?:\s+[A-Za-zÀ-ÿ'’\-]+){0,3})",
    re.IGNORECASE,
)


def _parse_zone(original: str) -> tuple[str, str]:
    """Returns (zone, original-with-the-zone-span-blanked).

    Works on the *original* text to preserve accents in the zone name. The
    matched span is blanked (not removed: offsets stay valid) so the city
    fallback in _parse_city cannot re-read "Zona Navigli" as a city name.
    """
    m = _ZONE_RE.search(original)
    if not m:
        return "", original
    tokens: list[str] = []
    for tok in m.group(1).split():
        low = _normalize(tok).strip("'’-")
        # a known city ends the zone name: "zona Navigli Milano" is the
        # Navigli zone of Milan, not a zone called "Navigli Milano"
        if low in ZONE_STOP_WORDS or low in CITY_SPELLINGS:
            break
        tokens.append(tok)
    if not tokens:
        return "", original
    zone = " ".join(t.title() if t.islower() else t for t in tokens)
    # blank exactly the keyword + the accepted tokens, nothing further: any
    # trailing (rejected) token may be the city and must stay readable
    end = m.start(1)
    for count, tm in enumerate(re.finditer(r"\S+", original[m.start(1):]), 1):
        if count == len(tokens):
            end = m.start(1) + tm.end()
            break
    cleaned = original[:m.start()] + " " * (end - m.start()) + original[end:]
    return zone, cleaned


# --- Multiple alternatives ("bilocale in zona X o trilocale in zona Y") ------

# Disjunctions split the query into alternative searches. Whitespace around
# the connective is required: "o" is one letter and would otherwise tear
# words apart. "e"/"and" are NOT connectives here: they appear inside price
# ranges ("tra 200 e 300").
_ALT_SPLIT_RE = re.compile(r"\s*;\s*|\s+(?:oppure|or|o)\s+", re.IGNORECASE)

MAX_ALTERNATIVES = 5


def _parse_segment(original: str) -> dict:
    """Parses one alternative in isolation, tracking which fields the text
    set *explicitly* — inheritance between alternatives needs to know the
    difference between "no price given" and "price given elsewhere"."""
    zone, cleaned = _parse_zone(original)
    text = _normalize(cleaned)
    contract, contract_explicit = _parse_contract(text)
    city, province = _parse_city(text, cleaned)
    min_price, max_price, price_warnings = _parse_prices(text)
    min_rooms, max_rooms, room_notes = _parse_rooms(text)
    min_sqm, sqm_warnings = _parse_sqm(text)

    explicit = set()
    if contract_explicit:
        explicit.add("contract")
    if city:
        explicit.add("city")
    if zone:
        explicit.add("zone")
    if min_price is not None or max_price is not None:
        explicit.add("price")
    if min_rooms is not None:
        explicit.add("rooms")
    if min_sqm is not None:
        explicit.add("sqm")

    return {
        "text": original,
        "params": {
            "city": city, "province": province, "zone": zone,
            "contract": contract,
            "min_price": min_price, "max_price": max_price,
            "min_rooms": min_rooms, "max_rooms": max_rooms,
            "min_sqm": min_sqm,
        },
        "explicit": explicit,
        "notes": room_notes,
        "warnings": [*price_warnings, *sqm_warnings],
        "contract_assumed": not contract_explicit,
    }


def _inherit_context(items: list[dict]) -> None:
    """Fills each alternative's missing fields from its siblings.

    "bilocale a Milano zona Isola o trilocale zona Lambrate": the second
    alternative names no city, but everyone reading the sentence knows it is
    still Milan. The donor is the nearest alternative that set the field
    explicitly (previous ones first, then following — so shared context can
    sit on either side, as in "bilocale o trilocale a Milano").

    Location is a bundle: an alternative without its own city inherits
    city+province together, but the donor's *zone* is inherited only when
    the alternative has no zone of its own. An alternative with its own
    explicit city inherits no location at all — "trilocale a Milano zona
    Navigli o a Torino" must not put a Milanese zone in Turin.
    """
    def donor(i: int, field: str) -> dict | None:
        for j in [*range(i - 1, -1, -1), *range(i + 1, len(items))]:
            if field in items[j]["explicit"]:
                return items[j]
        return None

    for i, item in enumerate(items):
        p = item["params"]
        if "city" not in item["explicit"]:
            d = donor(i, "city")
            if d:
                p["city"] = d["params"]["city"]
                p["province"] = d["params"]["province"]
                if "zone" not in item["explicit"]:
                    p["zone"] = d["params"]["zone"]
        if "contract" not in item["explicit"]:
            d = donor(i, "contract")
            if d:
                p["contract"] = d["params"]["contract"]
                item["contract_assumed"] = False
        if "price" not in item["explicit"]:
            d = donor(i, "price")
            if d:
                p["min_price"] = d["params"]["min_price"]
                p["max_price"] = d["params"]["max_price"]
        if "rooms" not in item["explicit"]:
            d = donor(i, "rooms")
            if d:
                p["min_rooms"] = d["params"]["min_rooms"]
                p["max_rooms"] = d["params"]["max_rooms"]
        if "sqm" not in item["explicit"]:
            d = donor(i, "sqm")
            if d:
                p["min_sqm"] = d["params"]["min_sqm"]


def _interpretation(item: dict) -> list[str]:
    p = item["params"]
    unit = "€/month" if p["contract"] == "rent" else "€"
    money = lambda v: f"{v:,}".replace(",", ".")  # noqa: E731
    parts = [
        "Looking for a rental" if p["contract"] == "rent" else "Looking to buy"
    ]
    if item["contract_assumed"]:
        parts[0] += " (assumed — say “in affitto” or “to rent” to change)"
    if p["city"]:
        parts.append(
            f"in {p['city']}" + (f" ({p['province']})" if p["province"] else "")
        )
    if p["zone"]:
        parts.append(f"{p['zone']} area")
    if p["min_price"] and p["max_price"]:
        parts.append(
            f"between {money(p['min_price'])} and {money(p['max_price'])} {unit}"
        )
    elif p["max_price"]:
        parts.append(f"up to {money(p['max_price'])} {unit}")
    elif p["min_price"]:
        parts.append(f"from {money(p['min_price'])} {unit}")
    locali = "locale" if p["min_rooms"] == 1 else "locali"
    if p["min_rooms"] and p["max_rooms"] and p["min_rooms"] == p["max_rooms"]:
        parts.append(f"{p['min_rooms']} {locali}")
    elif p["min_rooms"]:
        parts.append(f"{p['min_rooms']}+ {locali}")
    if p["min_sqm"]:
        parts.append(f"at least {p['min_sqm']} sqm")
    return parts


def parse_query(query: str) -> dict:
    """Parses a free-text property search into search-builder parameters.

    Returns {"searches": [{"params", "interpretation", "notes", "warnings"}]}.
    One entry per alternative when the query contains disjunctions
    ("bilocale in zona X o trilocale in zona Y"), otherwise a single entry.
    Each `params` mirrors schemas.SearchBuilderIn; `city` may be empty, in
    which case the caller must not build URLs for that search (a city-less
    portal URL silently searches all of Italy — the same trap as
    invariant #7).
    """
    original = (query or "").strip()
    if not _normalize(original):
        return {"searches": [{
            "params": {}, "interpretation": [], "notes": [],
            "warnings": ["Type what you are looking for, in plain words."],
        }]}

    items: list[dict] = []
    for segment in _ALT_SPLIT_RE.split(original):
        if not segment.strip():
            continue
        parsed = _parse_segment(segment.strip())
        if items and not parsed["explicit"]:
            # spurious split ("2 o 3 locali": the segment "2" alone means
            # nothing) — glue it back onto the previous alternative
            items[-1] = _parse_segment(items[-1]["text"] + " " + segment)
        else:
            items.append(parsed)

    overflow_warning = ""
    if len(items) > MAX_ALTERNATIVES:
        overflow_warning = (
            f"Only the first {MAX_ALTERNATIVES} alternatives were kept — "
            "run the assistant again for the rest."
        )
        items = items[:MAX_ALTERNATIVES]

    _inherit_context(items)

    searches: list[dict] = []
    seen_params: list[dict] = []
    for item in items:
        if item["params"] in seen_params:  # "2 o 3 locali" style duplicates
            continue
        seen_params.append(item["params"])
        warnings = list(item["warnings"])
        if not item["params"]["city"]:
            warnings.insert(0, (
                "I could not tell which city you mean. Add it below — "
                "without a city the portals would return listings from all "
                "of Italy."
            ))
        notes = list(item["notes"])
        if item["params"]["zone"]:
            notes.append(
                f"Zone \"{item['params']['zone']}\" is matched best-effort: "
                "open the generated links to check the portal recognises it."
            )
        searches.append({
            "params": item["params"],
            "interpretation": _interpretation(item),
            "notes": notes,
            "warnings": warnings,
        })
    if overflow_warning:
        searches[0]["warnings"].append(overflow_warning)
    return {"searches": searches}
