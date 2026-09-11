"""The reference suite: one search per shape a user can actually create.

One search is not "every search". A city, a zone named in the path, zone ids in
the query, a drawn polygon, a radius around a point — these are different
grammars on the portal and different code paths here (`_api_params`,
`_absorb_query`, `search_builder`), and each of them has broken on its own at
least once. A run against a single Milano URL proves that one grammar still
parses and says nothing at all about the other four.

So the suite is a **tracked list**: public, generic searches over a large city,
chosen so that the set covers every shape and so that nothing in it is anybody's
business. Nothing here is read from `case.db` and nothing here is personal — the
list is in this file precisely so it can be reviewed, and so that a shape gained
or lost shows up in a diff.

Two things keep it inside the budget invariant 8 draws:

* it climbs **one rung per search** by default, stopping at the first that
  parses. The question is "does this shape still work", and past the first yes
  every further rung is a request that buys nothing;
* the request cap scales with the number of searches instead of staying at the
  single-URL default, because a cap set for one search would silently cut the
  suite off halfway and the missing rows would read as a pass.

The last two entries are the computed half of manual check 2. The same criteria
that were pasted in are put back through `search_builder` the way the form
builds them, and `--compare-form` sets the two totals side by side with what
`search_validator` says the restatement approximated or dropped. A form that
quietly builds a different search is a bug that only shows up as "the two
searches return different numbers", which is precisely what that table shows.
"""

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..services.search_builder import build_search_urls, parse_search_url
from ..services.search_validator import normalize_profile_url, zone_coverage_warnings
from .budget import DEFAULT_MAX_REQUESTS, Budget
from .report import OK_OUTCOMES, Attempt, Run, pages
from .rungs import portal_of, run_checks

# What one search costs when its cheapest rung answers: for Immobiliare the
# geography lookup plus the api-next page, for Idealista the HTML page alone.
# The third is the headroom for one rung that gets refused before another
# answers — past that the blocked streak is the right thing to stop the run, not
# a cap that would make an unfinished suite look like a finished one.
REQUESTS_PER_ENTRY = 3


@dataclass(frozen=True)
class Reference:
    """One search in the suite, and what it must still parse as.

    `expect` is the subset of `parse_search_url`'s output that defines the
    shape: it is asserted offline, so a URL edited into a different shape than
    its name claims fails in the test suite rather than in a live run three
    weeks later.
    """

    name: str
    portal: str
    shape: str
    url: str
    expect: dict[str, Any]
    # For a form-built entry: the pasted entry whose criteria it restates.
    restates: str = ""

    @property
    def is_form(self) -> bool:
        return self.shape == "form"


# The searches as a user would paste them. Milano because it is the largest
# market on both portals — every shape has listings in it, so an empty result is
# a finding rather than a coincidence — and because a public search over a whole
# city discloses nothing about what this installation actually watches.
PASTED: tuple[Reference, ...] = (
    Reference(
        name="imm-city",
        portal="immobiliare",
        shape="city",
        url="https://www.immobiliare.it/vendita-case/milano/",
        expect={"city": "Milano", "contract": "sale"},
    ),
    Reference(
        name="imm-zone-path",
        portal="immobiliare",
        shape="zone in the path",
        url=(
            "https://www.immobiliare.it/affitto-case/milano/bicocca/"
            "?prezzoMinimo=700&prezzoMassimo=1800&localiMinimo=2&localiMassimo=3"
        ),
        expect={
            "city": "Milano",
            "zone": "Bicocca",
            "contract": "rent",
            "min_price": 700,
            "max_price": 1800,
            "min_rooms": 2,
            "max_rooms": 3,
        },
    ),
    Reference(
        name="imm-zone-ids",
        portal="immobiliare",
        shape="zone ids in the query",
        url="https://www.immobiliare.it/vendita-case/milano/?idMZona[]=10046&idMZona[]=10047",
        expect={"city": "Milano", "zone_ids": ["10046", "10047"], "contract": "sale"},
    ),
    Reference(
        name="imm-polygon",
        portal="immobiliare",
        shape="drawn polygon",
        url=(
            "https://www.immobiliare.it/search-list/?idContratto=1&idCategoria=1"
            "&vrt=45.44,9.16;45.46,9.16;45.46,9.19;45.44,9.19"
        ),
        expect={"drawn_area": {"kind": "polygon", "points": 4}, "contract": "sale"},
    ),
    Reference(
        name="imm-radius",
        portal="immobiliare",
        shape="radius around a point",
        url=(
            "https://www.immobiliare.it/search-list/?idContratto=1&idCategoria=1"
            "&centro=45.4842,9.2126&raggio=2000"
        ),
        expect={
            "drawn_area": {"kind": "circle", "lat": 45.4842, "lng": 9.2126, "radius_m": 2000},
            "contract": "sale",
        },
    ),
    Reference(
        name="ide-city",
        portal="idealista",
        shape="city",
        url="https://www.idealista.it/vendita-case/milano-milano/",
        expect={"city": "Milano", "province": "Milano", "contract": "sale"},
    ),
    Reference(
        name="ide-zone",
        portal="idealista",
        shape="zone with filters",
        url="https://www.idealista.it/affitto-case/milano/forlanini/con-prezzo_1800,dimensione_60/",
        expect={
            "city": "Milano",
            "zone": "Forlanini",
            "contract": "rent",
            "max_price": 1800,
            "min_sqm": 60,
        },
    ),
)

# One per portal, restating a pasted entry's criteria through the builder the
# form uses. They are derived rather than written down: a URL typed out here
# would be a copy of the builder's output that stops agreeing with it silently,
# and agreeing with it is the whole point.
_RESTATED = {"immobiliare": "imm-zone-path", "idealista": "ide-zone"}


def _built(params: dict, portal: str) -> str:
    """What `build_search_urls` produces for `portal` from these criteria."""
    return str(build_search_urls(params).get(portal, ""))


def _form_entries() -> tuple[Reference, ...]:
    out = []
    for portal, source in _RESTATED.items():
        origin = next(e for e in PASTED if e.name == source)
        params = parse_search_url(origin.url)
        out.append(
            Reference(
                name=f"{origin.name}-form",
                portal=portal,
                shape="form",
                url=_built(params, portal),
                # The restatement must still parse as the same search it
                # restates: that is the assertion, and it is what a form
                # silently building something else would fail.
                expect=origin.expect,
                restates=origin.name,
            )
        )
    return tuple(out)


FORM: tuple[Reference, ...] = _form_entries()


def entries() -> tuple[Reference, ...]:
    """Every reference search, pasted ones first."""
    return PASTED + FORM


def by_name(name: str) -> Reference | None:
    return next((e for e in entries() if e.name == name), None)


# --- what makes the list trustworthy ------------------------------------


def complaints(entry: Reference) -> list[str]:
    """Everything wrong with one reference search, in plain words.

    Empty is the only acceptable answer, and the offline test asserts it for
    every entry. A reference search that no longer parses as its own shape is
    worse than no reference search at all: the run would still come back green
    while measuring something else.
    """
    out: list[str] = []
    if not entry.url:
        return [f"{entry.name}: no URL"]
    found = portal_of(entry.url)
    if found != entry.portal:
        out.append(f"{entry.name}: the URL belongs to {found or 'no portal'}, not {entry.portal}")
    params = parse_search_url(entry.url)
    for key, wanted in entry.expect.items():
        if params.get(key) != wanted:
            out.append(f"{entry.name}: {key} parsed as {params.get(key)!r}, expected {wanted!r}")
    for warning in zone_coverage_warnings(params):
        # A reference search must be unambiguous. One that the app itself would
        # warn about makes every number it produces arguable.
        out.append(f"{entry.name}: {warning}")
    if not normalize_profile_url(entry.url):
        out.append(f"{entry.name}: the validator cannot normalise this URL")
    return out


def suite_complaints() -> list[str]:
    """`complaints` for every entry, plus what only the whole list can be wrong
    about: two pasted searches that are really the same search."""
    out: list[str] = []
    for entry in entries():
        out += complaints(entry)
    seen: dict[str, str] = {}
    for entry in PASTED:
        key = normalize_profile_url(entry.url)
        if key in seen:
            out.append(f"{entry.name}: the same search as {seen[key]}")
        seen[key] = entry.name
    return out


# --- the form against the same search pasted in -------------------------

# The criteria a search is made of. Anything else `parse_search_url` returns is
# either derived from these or a default, and listing them keeps the comparison
# stable when the parser gains a field.
_CRITERIA = (
    "city",
    "province",
    "zone",
    "zones",
    "zone_ids",
    "drawn_area",
    "contract",
    "min_price",
    "max_price",
    "min_rooms",
    "max_rooms",
    "min_sqm",
    "balcony",
    "garden",
    "parking",
    "elevator",
    "exclude_auctions",
    "pool",
    "floor",
    "condition",
)


def _stated(params: dict) -> dict[str, Any]:
    """The criteria this search actually states — absent is not `False`."""
    return {k: params[k] for k in _CRITERIA if params.get(k) not in ("", None, False, [])}


@dataclass
class Restatement:
    """What the form makes of a pasted search's criteria."""

    entry: Reference
    url: str = ""
    # Empty when the builder produced a usable URL; otherwise why it could not.
    why_not: str = ""
    dropped: list[str] = field(default_factory=list)
    changed: dict[str, tuple[Any, Any]] = field(default_factory=dict)
    # `search_validator`'s and the builder's own provenance: what this selection
    # asked for that the URL about to be saved cannot carry.
    review: list[str] = field(default_factory=list)
    same_search: bool = False

    @property
    def notes(self) -> list[str]:
        """Everything a person needs told about this restatement, in one list."""
        if self.why_not:
            # There is no URL, so every criterion is lost and listing them one
            # by one adds nothing the sentence has not already said.
            return [self.why_not, *self.review]
        out = [*self.review]
        out += [f"{k} dropped" for k in self.dropped if f"{k} dropped" not in out]
        out += [f"{k}: {before!r} → {after!r}" for k, (before, after) in self.changed.items()]
        if self.url and not self.same_search and not self.dropped and not self.changed:
            # Idealista is the case: the form reaches a zone through `/cerca/`,
            # a free-text phrase, where the pasted URL used the zone page. Same
            # criteria, different grammar — and different grammars are exactly
            # what returns different totals, so it must not pass unremarked.
            out.append("the same criteria, in a grammar the pasted URL did not use")
        return out


def restate(entry: Reference) -> Restatement:
    """Rebuild `entry`'s criteria the way the form would, and say what changed.

    Offline and free: `build_search_urls` is called without `verify`, so it
    makes no request. This is manual check 2 computed — the check that used to
    be a person pasting a URL into the form, pressing Generate and comparing two
    result counts by eye.
    """
    params = parse_search_url(entry.url)
    built = build_search_urls(params)
    review = [*built["zone_warnings"], *(f"{f} dropped" for f in built["idealista_unsupported"])]
    url = str(built.get(entry.portal, ""))

    if not params.get("city"):
        # Every builder grammar starts from a place name. A search drawn on the
        # map has none, so what comes out is a URL with a hole in it rather than
        # a narrower search — which is the honest finding, not an error.
        return Restatement(
            entry=entry,
            why_not="the builder has no grammar for a search drawn on the map",
            dropped=sorted(_stated(params)),
            review=review or ["drawn_area dropped"],
        )

    rebuilt = _stated(parse_search_url(url))
    stated = _stated(params)
    return Restatement(
        entry=entry,
        url=url,
        dropped=sorted(k for k in stated if k not in rebuilt),
        changed={
            k: (stated[k], rebuilt[k]) for k in stated if k in rebuilt and rebuilt[k] != stated[k]
        },
        review=review,
        same_search=normalize_profile_url(url) == normalize_profile_url(entry.url),
    )


# --- running it ---------------------------------------------------------


def request_cap(refs: tuple[Reference, ...] | None = None) -> int:
    """How many requests one portal may take for a whole suite run.

    The single-URL default is a cap for one search. Left alone it would refuse
    the second half of the suite, and a refusal reads as "not checked" — the
    table would be short exactly where a person stops looking.
    """
    refs = entries() if refs is None else refs
    busiest = max(Counter(r.portal for r in refs).values(), default=0)
    return max(DEFAULT_MAX_REQUESTS, REQUESTS_PER_ENTRY * busiest)


def run_suite(
    *,
    budget: Budget,
    rung_filter: list[str] | None = None,
    out_root: Path | None = None,
    settings: dict | None = None,
    all_rungs: bool = False,
) -> Run:
    """Run every reference search the way a scan would: cheapest rung first,
    stopping at the first that parses. `all_rungs` asks for the full matrix
    instead, which is the same traffic as running each search on its own."""
    refs = entries()
    return run_checks(
        [r.url for r in refs],
        budget=budget,
        rung_filter=rung_filter,
        out_root=out_root,
        settings=settings,
        labels=[r.name for r in refs],
        stop_at_first=not all_rungs,
    )


def _for(run: Run, name: str) -> list[Attempt]:
    return pages(a for a in run.attempts if a.search == name)


def _winner(run: Run, name: str) -> Attempt | None:
    return next((a for a in _for(run, name) if a.outcome in OK_OUTCOMES), None)


def every_search_answered(run: Run) -> bool:
    """True when every reference search had a rung that parsed listings or
    proved the search matches nothing. This is what a suite run exits on: the
    per-portal verdict cannot answer it, because one working city search would
    cover for four broken shapes."""
    checked = [e for e in entries() if any(a.search == e.name for a in run.attempts)]
    return bool(checked) and all(_winner(run, e.name) is not None for e in checked)


def _cells(rows: list[list[str]]) -> str:
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return "\n".join(
        "  ".join(cell.ljust(w) for cell, w in zip(row, widths, strict=True)).rstrip()
        for row in rows
    )


def _count(attempt: Attempt | None) -> str:
    """What a search found, preferring the total the portal declared over the
    page it served. Empty when it declared none — invariant 26."""
    if attempt is None:
        return ""
    if attempt.declared_total is not None:
        return f"{attempt.declared_total:,}"
    return f"{attempt.listings} on p1" if attempt.listings else ""


def render_suite(run: Run) -> str:
    """One line per reference search: did this shape still work, and via what."""
    rows = [["SEARCH", "PORTAL", "SHAPE", "RESULT", "VIA", "ADS", "TOTAL", "TRIED"]]
    answered = 0
    for entry in entries():
        attempts = _for(run, entry.name)
        if not attempts:
            continue
        winner = _winner(run, entry.name)
        answered += 1 if winner else 0
        rows.append(
            [
                entry.name,
                entry.portal,
                entry.shape,
                winner.outcome if winner else "no rung worked",
                winner.rung if winner else "",
                str(winner.listings) if winner and winner.listings else "",
                _count(winner),
                str(len(attempts)),
            ]
        )
    checked = len(rows) - 1
    return f"{_cells(rows)}\n\n{answered} of {checked} reference searches answered"


def render_comparison(run: Run) -> str:
    """The pasted search and the same criteria built by the form, side by side.

    One row per pasted entry. `FORM` is filled where the suite ran the
    restatement and empty where it only computed it — the totals are the part
    that costs a request, and the review beside them does not.
    """
    rows = [["SEARCH", "PORTAL", "SHAPE", "PASTED", "FORM", "SAME SEARCH", "REVIEW"]]
    for entry in PASTED:
        again = restate(entry)
        counterpart = next((f for f in FORM if f.restates == entry.name), None)
        rows.append(
            [
                entry.name,
                entry.portal,
                entry.shape,
                _count(_winner(run, entry.name)),
                _count(_winner(run, counterpart.name)) if counterpart else "",
                "—" if again.why_not else ("yes" if again.same_search else "no"),
                "; ".join(again.notes),
            ]
        )
    return _cells(rows)
