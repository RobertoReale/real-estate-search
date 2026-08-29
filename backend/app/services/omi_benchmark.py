"""The OMI band a property sits in, shown *beside* the listing median — never merged with it.

Two numbers now describe the same zone, and they measure different things:

* the **area median** (`pricing_stats.py`) is the middle of what comparable ads
  are **asking**, computed from the listings this app itself scraped;
* the **OMI band** (`omi_import.py`) is min/max €/m² the Agenzia delle Entrate
  derives from **recorded transactions**.

Asking prices sit systematically above transacted ones, so averaging the two, or
letting one stand in for the other, produces a figure that means nothing and
looks authoritative. Nothing here touches `deal_score`, `deal_label`,
`sqm_price_delta_pct` or the proposal range: the OMI figures are an extra,
labelled, dated reason line and a second column on screen (invariant 22).

**Which rows make the band.** A zone quotes several bands — by property type
(*Abitazioni civili*, *Box*, *Negozi*, …) and by conservation state (*NORMALE*,
*OTTIMO*) — and the app knows neither for a given ad: the portal does not
publish an OMI tipologia, and "renovated" in an agency's prose is not the
Agenzia's *OTTIMO*. So the band is the envelope of the **residential** rows for
the property's contract, lowest minimum to highest maximum, and the non-
residential ones are dropped: a flat measured against garage or shop prices is
not a benchmark, it is a coincidence. Picking one (type, state) row instead
would be precision this data cannot support — the range is wide because the
recorded reality is.

`RESIDENTIAL_TYPE_CODES` was read off the real 2025/2 delivery rather than off
the format documentation (see `docs/architecture.md`), and a type code the app
has never seen is excluded rather than folded in: an unknown tipologia silently
widening a residential band is the failure this whole module exists to avoid.

**And every figure says how old it is, and whose it is.** A band is a
measurement of a six-month window that ends: the semester travels with it
everywhere (an undated figure is a claim with no expiry), a band whose window
closed more than `STALE_AFTER_MONTHS` ago is *marked* stale rather than quietly
trusted, and the attribution the OMI licence requires is repeated wherever the
numbers go. Stale data is labelled, never withheld — recorded prices two years
old still beat asking prices alone, as long as the reader can see the date.

Fail open throughout, like everything else on this path: no quotations, no
placement, or a zone with only non-residential rows means **no OMI benchmark and
no error**.
"""

import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import OmiQuotation, Property
from .omi_import import latest_semester

# The wording the OMI licence requires next to the data. One constant so a new
# rendering cannot quietly ship without it, and Italian in both UI languages
# because it is the attribution the licence asks for, not a caption to translate.
ATTRIBUTION = "Fonte: Agenzia Entrate – OMI"

# How long after its own window closes a semester stops counting as current. The
# Agenzia publishes twice a year, so eighteen months is three missed releases —
# past "the refresh is overdue", short of "this is history".
STALE_AFTER_MONTHS = 18

# `Cod_Tip` values that are somewhere a person lives, measured against the real
# 2025/2 supply: 1 = Ville e Villini, 19 = Abitazioni signorili, 20 = Abitazioni
# civili, 21 = Abitazioni di tipo economico. The rest of that delivery is Box,
# Negozi, Uffici, Magazzini, Laboratori and Capannoni industriali.
RESIDENTIAL_TYPE_CODES = frozenset({"1", "19", "20", "21"})

_SEMESTER = re.compile(r"\s*(\d{4})\s*/\s*(\d+)\s*")


def format_semester(semester: str) -> str:
    """The semester as a date a reader can place: "2025/2" → "2nd half 2025".

    Anything that is not a semester is handed back untouched: a label the app
    cannot parse is still the label the import recorded, and dropping it would
    leave the figure undated — which is the one thing these numbers must never
    be."""
    match = _SEMESTER.fullmatch(semester or "")
    if not match:
        return semester or ""
    year, half = match.group(1), match.group(2)
    return f"{'1st' if half == '1' else '2nd' if half == '2' else half} half {year}"


def semester_end(semester: str | None) -> date | None:
    """The last day of the window a semester label covers, or None if unreadable."""
    match = _SEMESTER.fullmatch(semester or "")
    if not match:
        return None
    year, half = int(match.group(1)), match.group(2)
    if half == "1":
        return date(year, 6, 30)
    if half == "2":
        return date(year, 12, 31)
    return None


def is_stale(semester: str | None, today: date | None = None) -> bool:
    """Has this semester's window been closed for more than `STALE_AFTER_MONTHS`?

    Measured from the end of the window the label names, never from the import:
    a 2023/2 supply loaded this morning still describes 2023, and it is the age
    of the *measurement* the reader has to weigh.

    A label the app cannot parse is not called stale. `format_semester` keeps
    showing it verbatim, so the figure is still dated with whatever the import
    recorded — but inventing an age for a date we cannot read would be a firmer
    claim than the data supports, and this module never makes one of those.

    Counted in whole months, with no day arithmetic: a semester always ends on
    the last day of its month, so "months since that month" is already the exact
    age. Comparing days too would make 31 December age more slowly than 30 June,
    because no June has a 31st to reach."""
    end = semester_end(semester)
    if end is None:
        return False
    today = today or date.today()
    months = (today.year - end.year) * 12 + (today.month - end.month)
    return months > STALE_AFTER_MONTHS


def has_band(prop: Property) -> bool:
    """Does this property carry a complete, dated OMI band?

    The single condition every renderer asks. The modal, the print dossier and
    the reason line have to agree on when there is something to show — and
    therefore on when the attribution has to appear beside it."""
    return bool(
        getattr(prop, "omi_min_sqm_price", None)
        and getattr(prop, "omi_max_sqm_price", None)
        and getattr(prop, "omi_semester", None)
    )


def _fmt(value: float) -> str:
    """Thousands separated the Italian way, like every other price in this app."""
    return f"{value:,.0f}".replace(",", ".")


def _band_index(
    db: Session, pairs: set[tuple[str, str]]
) -> tuple[str | None, dict[tuple[str, str, str], tuple[float, float]]]:
    """(semester, {(municipality, zone, contract): (min, max)}) for the given zones.

    One query for the whole page, not one per card, and only the newest
    semester — `find_quotations` refuses to mix them for the same reason this
    does: a band widened with figures of two different dates carries no date at
    all."""
    semester = latest_semester(db)
    if semester is None or not pairs:
        return semester, {}
    # Filtered on the two columns separately and re-checked in Python: a row
    # value `IN` over pairs is not portable, and the cross product of one
    # page's zones is a handful of rows either way.
    rows = db.scalars(
        select(OmiQuotation).where(
            OmiQuotation.semester == semester,
            OmiQuotation.municipality_code.in_({m for m, _ in pairs}),
            OmiQuotation.zone_code.in_({z for _, z in pairs}),
        )
    ).all()
    index: dict[tuple[str, str, str], tuple[float, float]] = {}
    for row in rows:
        if (row.municipality_code, row.zone_code) not in pairs:
            continue
        if row.property_type_code not in RESIDENTIAL_TYPE_CODES:
            continue
        if not row.min_sqm_price or not row.max_sqm_price:
            continue
        key = (row.municipality_code, row.zone_code, row.contract)
        current = index.get(key)
        if current is None:
            index[key] = (row.min_sqm_price, row.max_sqm_price)
        else:
            index[key] = (
                min(current[0], row.min_sqm_price),
                max(current[1], row.max_sqm_price),
            )
    return semester, index


def annotate_omi_benchmark(db: Session, props: list[Property]) -> None:
    """Attaches the transient `omi_min_sqm_price` / `omi_max_sqm_price` /
    `omi_semester` read by `PropertyOut` and by the deal score's reason line.

    Transient, like the area median next to it, and for the same reason: the
    figures already live in `OmiQuotation`, so a copy on the property would be a
    second home for one fact and would go stale the moment a semester is
    re-imported. The lookup is an indexed read of a handful of rows — the
    expensive half, placing the property in its zone, is the persisted column
    `omi_zones.resolve_property_zones` writes.

    Run it before `deal_score.annotate_deal_scores`, which reads what it sets."""
    for prop in props:
        prop.omi_min_sqm_price = None
        prop.omi_max_sqm_price = None
        prop.omi_semester = None
        prop.omi_stale = False
    if not props:
        return
    pairs = {
        (p.omi_municipality_code, p.omi_zone_code)
        for p in props
        if p.omi_municipality_code and p.omi_zone_code
    }
    if not pairs:
        return
    semester, index = _band_index(db, pairs)
    if not index:
        return
    for prop in props:
        band = index.get((prop.omi_municipality_code, prop.omi_zone_code, prop.contract))
        if band is None:
            continue
        prop.omi_min_sqm_price = round(band[0], 2)
        prop.omi_max_sqm_price = round(band[1], 2)
        prop.omi_semester = semester
        prop.omi_stale = is_stale(semester)


def benchmark_reason(prop: Property) -> str | None:
    """The OMI figures as one reason line, or None when there are none.

    Says what the numbers are, when they were recorded, whether that is still
    recent, and whose they are — every time. A band presented as
    "3.100–4.200 €/sqm" next to a listing median is exactly the confusion this
    feature has to avoid, and an undated one is a claim with no expiry.

    It carries its own attribution rather than leaning on a neighbour's: this
    line also travels alone into the card's deal-score tooltip, far from the
    benchmark panel that labels the figures on the detail view."""
    low, high, semester = prop.omi_min_sqm_price, prop.omi_max_sqm_price, prop.omi_semester
    if not low or not high or not semester:  # `has_band`, spelled so it narrows
        return None
    dated = format_semester(semester)
    if is_stale(semester):
        dated += f", over {STALE_AFTER_MONTHS} months old"
    what = "rents" if prop.contract == "rent" else "sales"
    unit = "€/sqm per month" if prop.contract == "rent" else "€/sqm"
    return (
        f"OMI recorded {what} in this zone: {_fmt(low)}–{_fmt(high)} {unit} "
        f"({dated}) · {ATTRIBUTION}"
    )
