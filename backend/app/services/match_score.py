"""Smart Match Score: a compatibility percentage between a property and the
user's "dream home" preferences.

Pure weighted scoring over fields already in the DB — no external data, no AI,
computed per request like the market-position annotation. Each preference the
user set becomes one criterion scored in [0, 1]; the score is their average,
0–100. A preference left unset (0, or an empty list) does not count, so the
number only ever reflects criteria the user actually cares about — and with
everything unset there is no score at all (None), so the badge never appears.

Design choices worth stating, because unstated they read as bugs:
- A field the property is *missing* scores 0, not "skip": a listing with no
  price cannot be shown to match a budget. The one exception is floor, which is
  free text ("piano terra", "rialzato", "") and unparseable more often than
  not — scoring every such listing 0 on floor would drown out the real signal,
  so an unparseable floor drops the criterion instead.
- Numeric thresholds degrade linearly rather than snapping to 0/1: a €360k flat
  against a €350k budget is "almost", not "no". A 2-room flat against a 3-room
  wish scores 2/3, not 0.
"""

import re

from ..models import Property
from .filter_engine import _normalize, find_excluded_keyword


def _pos_int(value) -> int | None:
    """A configured numeric preference, or None when unset (0/blank/invalid)."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def prefs_from_settings(settings: dict) -> dict:
    return {
        "enabled": bool(settings.get("match_score_enabled")),
        "max_price": _pos_int(settings.get("dream_max_price")),
        "min_rooms": _pos_int(settings.get("dream_min_rooms")),
        "min_sqm": _pos_int(settings.get("dream_min_sqm")),
        "min_floor": _pos_int(settings.get("dream_min_floor")),
        "keywords": [k for k in (settings.get("dream_keywords") or []) if k.strip()],
        "zones": [z for z in (settings.get("dream_zones") or []) if z.strip()],
    }


_FLOOR_NUM_RE = re.compile(r"-?\d+")


def _parse_floor(floor: str) -> int | None:
    """A floor as an integer, or None when the free-text label can't be read.
    Ground floor ("piano terra") and mezzanine ("rialzato") count as 0."""
    norm = _normalize(floor)
    if not norm:
        return None
    # "R" is the portals' abbreviation for "piano rialzato": it arrives as the
    # bare token, never spelled out, so match it explicitly or the mezzanine
    # falls through to None and drops out of the "ground" band.
    if "terra" in norm or "rialzat" in norm or norm in ("r", "pr"):
        return 0
    m = _FLOOR_NUM_RE.search(norm)
    return int(m.group()) if m else None


def _at_least(value: float | None, minimum: int) -> float:
    """1.0 at or above the wish, degrading linearly towards 0 below it; a
    missing value scores 0 (it cannot be shown to meet the wish)."""
    if value is None:
        return 0.0
    if value >= minimum:
        return 1.0
    return max(0.0, value / minimum)


def _keyword_fraction(prop: Property, keywords: list[str]) -> float:
    """Fraction of desired features present in the property's text, matched on
    word boundaries and accent-insensitively (reusing the filter engine)."""
    texts = [prop.title, prop.address, prop.zone, *(l.description for l in prop.listings)]
    found = sum(1 for kw in keywords if find_excluded_keyword(texts, [kw]) is not None)
    return found / len(keywords)


def _zone_match(prop: Property, zones: list[str]) -> float:
    """Word-boundary matching via the filter engine, like every other keyword
    in the codebase: a bare substring test made a preferred zone "Isola"
    silently match "Isolabella"/"Isolotto" addresses."""
    texts = [prop.city, prop.zone, prop.address]
    return 1.0 if find_excluded_keyword(texts, zones) is not None else 0.0


def compute_match(prop: Property, prefs: dict) -> int | None:
    """Compatibility percentage (0–100), or None when scoring is off or no
    preference is configured."""
    if not prefs.get("enabled"):
        return None
    subs: list[float] = []

    if prefs["max_price"]:
        budget = prefs["max_price"]
        price = prop.current_min_price
        if price is None:
            subs.append(0.0)
        elif price <= budget:
            subs.append(1.0)
        else:
            # 1.0 at budget, reaching 0 at twice the budget
            subs.append(max(0.0, 1 - (price - budget) / budget))

    if prefs["min_rooms"]:
        subs.append(_at_least(prop.rooms, prefs["min_rooms"]))

    if prefs["min_sqm"]:
        subs.append(_at_least(prop.sqm, prefs["min_sqm"]))

    if prefs["min_floor"]:
        floor = _parse_floor(prop.floor)
        if floor is not None:  # unparseable floor: criterion dropped, not zeroed
            subs.append(1.0 if floor >= prefs["min_floor"] else 0.0)

    if prefs["keywords"]:
        subs.append(_keyword_fraction(prop, prefs["keywords"]))

    if prefs["zones"]:
        subs.append(_zone_match(prop, prefs["zones"]))

    if not subs:
        return None
    return round(100 * sum(subs) / len(subs))


def annotate_match_scores(props: list[Property], settings: dict) -> None:
    """Attaches the transient `match_score` read by PropertyOut."""
    prefs = prefs_from_settings(settings)
    for p in props:
        p.match_score = compute_match(p, prefs)
