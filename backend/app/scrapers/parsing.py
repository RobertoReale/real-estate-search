"""Text -> value: the price/surface/room parsers every strategy shares, plus the
contract read off a search URL.

Pure and offline, which is why `test_property_based.py` can throw hypothesis at
them: the laws they must obey for *any* input are the cheapest coverage in the
project. The plausibility bounds are the load-bearing part — sale and rent
amounts live in disjoint ranges, and applying the sale bounds to a monthly rent
rejects every one of them (invariant 10).
"""

import re
from urllib.parse import parse_qs, urlparse


def detect_contract(search_url: str) -> str:
    """ "sale" or "rent", inferred from the search URL.

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


# --- Numerical helpers reused across all strategies ---

# Portals write prices both as "€ 250.000" and "399.000 €".
PRICE_RE = re.compile(r"€\s*([\d.,]+)|([\d.,]+)\s*€")
# "3.990 €/m²" is the price per square meter, not the property price
PRICE_PER_SQM_RE = re.compile(r"[\d.,]+\s*€\s*/\s*m", re.IGNORECASE)
# Large plots write the surface with a thousands separator ("5.000 m²"):
# the first alternative captures that form so it is not read as 5.0 sqm.
SQM_RE = re.compile(r"(\d{1,3}(?:\.\d{3})+|\d+(?:[.,]\d{1,2})?)\s*m[q²]", re.IGNORECASE)
ROOMS_RE = re.compile(r"(\d+)\s*local[ei]", re.IGNORECASE)

MIN_PRICE, MAX_PRICE = 10_000, 20_000_000
# Rents run 300–5,000 €/month: the sale bounds would reject every one of
# them, which is exactly what happened before rental support existed.
MIN_RENT, MAX_RENT = 100, 50_000


def _to_number(raw: str) -> float | None:
    """ "1.250.000" -> 1250000.0 (the period is the thousands separator)."""
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
