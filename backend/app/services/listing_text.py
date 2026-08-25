"""Recognizing portal boilerplate in a listing's title and zone.

Portals auto-generate a title when the agency wrote none ("Appartamento in
vendita a Milano, Milano") and sometimes store that same phrase in the zone
field. Both read as data but carry no information, so the two features that
improve a property's text need to tell them apart from a real title:
`availability_check` overwrites a placeholder title with the ad page's
`og:title`, and `geocoder` refuses to geocode a placeholder zone — searching
Nominatim for "in vendita a Milano" would either fail or, worse, land the pin
on something unrelated.

The match is structural, not a list of known strings: the generic property
words plus "in vendita/affitto" plus an optional place tail that must resolve
to real comuni. An unrecognized tail means the title says something the portal
did not generate, so it is kept — this fails towards keeping the user's data,
like every other heuristic that touches an existing row.
"""

import re

from . import geo_reference


def _agency_prefixes() -> list[str]:
    """Agency names whose branding pollutes a listing title. Data-driven
    (settings `repair_agency_prefixes`, seeded with the agencies met so far)
    so a user in another market extends the list without a code change."""
    from ..config import load_settings

    values = load_settings().get("repair_agency_prefixes") or []
    return [str(v).strip().casefold() for v in values if str(v).strip()]


# The structural shape of a portal auto-title: optional generic property words,
# "in vendita/affitto", optionally anchored to place names. "Appartamento in
# vendita", "Residenziale in affitto a Milano, Milano" and their equivalents
# for ANY comune all match; a title carrying real information does not.
_PLACEHOLDER_RE = re.compile(
    r"^(?:(?:immobile|residenziale|appartamento|casa|attico|villa|loft"
    r"|monolocale|bilocale|trilocale|quadrilocale)\s+)*"
    r"(?:in\s+)?(?:vendita|affitto)"
    r"(?:\s+a\s+(?P<place>.+))?$"
)


def _place_tail_is_comuni(place: str | None) -> bool:
    """Is the "a <place>" tail made only of real comuni? The portal loves
    repeating itself ("a Milano, Milano"), so the tail is comma-separated and
    every segment must be in the gazetteer."""
    if not place:
        return False
    index = geo_reference.load_comuni()
    segments = [s.strip() for s in place.split(",") if s.strip()]
    return bool(segments) and all(seg in index for seg in segments)


def _is_placeholder_phrase(text: str) -> bool:
    """Does `text` match the auto-generated "<generic> in vendita a <comune>"
    shape? A tail-less phrase ("Appartamento in vendita") is boilerplate on its
    own; with a tail, the tail must be real comuni."""
    normalized = " ".join((text or "").casefold().strip(" .-").split())
    if not normalized:
        return False
    m = _PLACEHOLDER_RE.match(normalized)
    if not m:
        return False
    place = m.group("place")
    if not place:
        return True
    return _place_tail_is_comuni(place)


def is_placeholder_zone(zone: str) -> bool:
    """'In vendita a Milano' (or any comune) stored as a zone is portal
    boilerplate, not a place name. Unlike a title, a tail-less phrase is not
    enough here — the zone field is the place, so only the anchored form is
    recognizable as boilerplate."""
    z = " ".join((zone or "").casefold().split())
    m = _PLACEHOLDER_RE.match(z)
    if not m:
        return False
    return _place_tail_is_comuni(m.group("place"))


def is_bad_title(title: str) -> bool:
    """Is this title portal/agency boilerplate rather than a description of the
    property? Empty, "n/a", the auto-generated phrase, an agency's "ti propone"
    pitch, or anything carrying a configured agency name."""
    if not title:
        return True
    tl = " ".join(title.casefold().strip(" .-").split())
    if tl in ("", "n/a"):
        return True
    if _is_placeholder_phrase(tl):
        return True
    if "ti propone" in tl:
        return True
    for prefix in _agency_prefixes():
        if re.search(rf"(?<!\w){re.escape(prefix)}(?!\w)", tl):
            return True
    return False
