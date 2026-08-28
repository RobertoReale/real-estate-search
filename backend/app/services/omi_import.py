"""Import of the OMI quotations published by the Agenzia delle Entrate.

Every other price judgement this app makes is circular: a listing is compared
against the median of the asking prices the app itself scraped, so a uniformly
overpriced zone reads as fair. The OMI quotations are min/max €/m² per
homogeneous micro-zone derived from **recorded transactions** — the one
reference here that does not come from sellers.

**There is deliberately no downloader.** The supply sits behind a Fisconline /
Entratel session that needs SPID and a person, and scraping a government portal
is neither necessary nor welcome. The owner requests the file once a semester
and drops it in a directory; this module reads it from there.

What the real 2025/2 supply taught us, none of which is guessable from the
format documentation (all four cost a wrong parser that raises nothing):

* **Line 1 is a title, not the header.** The header is line 2. A `DictReader`
  aimed at the file takes `Quotazioni Immobiliari : Valori di Mercato…` as its
  field names and every row comes out wrong, silently.
* **The semester is only in that title line.** No data row carries it.
* **Semicolon-separated, with a trailing separator, and decimal commas.** `35,1`
  is thirty-five point one; `float()` raises on it, and stripping the comma
  turns it into 351.
* **`LinkZona` looks like the join key and is not.** It is populated here
  (`MI00003228`) but empty in the zone perimeters, so joining on it matches
  nothing and reports no error. The pair that joins is `Comune_amm` + `Zona`.

Two rules shape the error handling. **Malformed rows are skipped and counted,
never fatal** — a supply is tens of thousands of rows and one bad decimal must
not lose the other 40,000 — and the caller is always told both numbers, because
a silent partial import is worse than a refusal. And **fail open**: no OMI data
means no OMI benchmark, never a broken scan.

Paths are deliberately absent from every message and log line here. The Agenzia
names each delivery after the person who requested it, so the supply's own
filenames and folders carry a codice fiscale; the configured directory is
visible in Settings, which is where the user looks when one of these errors
tells them the supply could not be read.
"""

import csv
import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..models import OmiQuotation

logger = logging.getLogger(__name__)


class OmiImportError(Exception):
    """The supply could not be read at all — a missing directory, a file that is
    not an OMI export, an unreadable header. Distinct from a malformed *row*,
    which is counted and skipped rather than raised."""


# "Quotazioni Immobiliari : Valori di Mercato - Semestre 2025/2 - elaborazione…"
_SEMESTER_PATTERN = re.compile(r"Semestre\s*(\d{4})\s*/\s*([12])\b", re.IGNORECASE)

# The title line is also how the two files of a supply are told apart. Matching
# on content rather than on the filename is not fastidiousness: the filenames
# are the one part of the delivery that carries the requester's identity.
_VALORI_MARKER = "valori di mercato"
_ZONE_MARKER = "informazioni di zona"

# Columns the prices file must have for this parser to mean anything. Checked
# once against the header so a changed export fails loudly here instead of
# producing 40,000 skipped rows and a confusing "0 imported".
_VALORI_COLUMNS = ("Comune_amm", "Zona", "Compr_min", "Compr_max")
_ZONE_COLUMNS = ("Comune_amm", "Zona", "Zona_Descr")

# Each source row holds both contracts side by side. Rent is €/m² per *month*
# and sale is €/m² outright; they are stored as delivered and never mixed.
_CONTRACT_COLUMNS = {
    "sale": ("Compr_min", "Compr_max"),
    "rent": ("Loc_min", "Loc_max"),
}


def semester_sort_key(semester: str) -> tuple[int, int]:
    """Orders "YYYY/N" numerically. Text sort happens to work for today's
    one-digit halves and would quietly stop working if the format ever grew, so
    the comparison is on numbers everywhere that "newest wins"."""
    match = re.fullmatch(r"\s*(\d{4})\s*/\s*(\d+)\s*", semester or "")
    if not match:
        return (0, 0)
    return (int(match.group(1)), int(match.group(2)))


def _clean(value: str | None) -> str:
    """Trims a field, and unwraps the single quotes the zone descriptions arrive
    in (`'CENTRO STORICO - BRERA'`). A description is displayed verbatim, so the
    quotes would end up on screen."""
    text = (value or "").strip()
    if len(text) >= 2 and text.startswith("'") and text.endswith("'"):
        text = text[1:-1].strip()
    return text


def _to_price(value: str | None) -> float | None:
    """Italian decimal comma → float. Returns None for anything unusable, which
    is what makes a bad cell a skipped row instead of an exception."""
    text = (value or "").strip()
    if not text:
        return None
    try:
        price = float(text.replace(",", "."))
    except ValueError:
        return None
    # A zero or negative €/m² is not a price; it is an empty cell wearing a
    # number, and it would drag any later comparison towards "free".
    return price if price > 0 else None


def parse_semester(title_line: str) -> str:
    """Reads "2025/2" out of the file's title line — the only place it appears."""
    match = _SEMESTER_PATTERN.search(title_line or "")
    if not match:
        raise OmiImportError(
            "The file does not name its semester on the first line: this does not look "
            "like an OMI export, or only part of one was saved."
        )
    return f"{match.group(1)}/{match.group(2)}"


@contextmanager
def _open_supply(path: Path) -> Iterator[tuple[str, csv.DictReader]]:
    """Opens an OMI CSV positioned on its real header, yielding (title, reader).

    The single line of `readline()` before handing the handle to `DictReader` is
    the whole fix for the title-line trap: the header is line 2, and a reader
    aimed at line 1 names every column after a sentence.

    Decoding is lenient on purpose. The supply measured here is pure ASCII, but
    a comune with an accent in its name is one delivery away, and a mangled
    character in a zone *description* is cosmetic — it can never reach the join
    keys (`F205`, `B12`) or the prices, which are ASCII by construction. Losing
    a whole national import to one byte would be the worse failure.
    """
    try:
        handle = path.open(encoding="utf-8-sig", errors="replace", newline="")
    except OSError as e:
        raise OmiImportError("The OMI file could not be opened for reading.") from e
    with handle:
        title = handle.readline()
        if not title.strip():
            raise OmiImportError("The file is empty.")
        reader = csv.DictReader(handle, delimiter=";")
        if not reader.fieldnames:
            raise OmiImportError("The file has a title but no header row.")
        yield title, reader


def _require_columns(reader: csv.DictReader, columns: tuple[str, ...]) -> None:
    present = {(name or "").strip() for name in (reader.fieldnames or [])}
    missing = [name for name in columns if name not in present]
    if missing:
        raise OmiImportError(
            "The file is missing the columns this importer needs "
            f"({', '.join(missing)}). The export format may have changed."
        )


def _iter_rows(reader: csv.DictReader) -> Iterator[dict[str, str]]:
    """Rows with whitespace-trimmed keys and never a None value.

    The trailing `;` on every line gives the header an unnamed final column, and
    a short row hands `DictReader` a None it would otherwise pass to `.strip()`.
    """
    for row in reader:
        yield {(k or "").strip(): (v if isinstance(v, str) else "") for k, v in row.items()}


def read_zone_descriptions(path: Path) -> dict[tuple[str, str], str]:
    """Maps (municipality code, zone code) → zone description, from the zone
    file of the same delivery. Optional: an import given only the prices keeps
    every number and simply leaves the descriptions empty."""
    with _open_supply(path) as (_title, reader):
        _require_columns(reader, _ZONE_COLUMNS)
        descriptions: dict[tuple[str, str], str] = {}
        for row in _iter_rows(reader):
            municipality = _clean(row.get("Comune_amm"))
            zone = _clean(row.get("Zona"))
            description = _clean(row.get("Zona_Descr"))
            if municipality and zone and description:
                descriptions[(municipality, zone)] = description
        return descriptions


def read_quotations(
    path: Path,
    descriptions: dict[tuple[str, str], str] | None = None,
) -> tuple[str, list[dict], int]:
    """Parses the prices file into rows ready for `OmiQuotation`.

    Returns (semester, rows, skipped). One source row yields up to two rows —
    one per contract — and counts as skipped only when it yields none at all.
    """
    with _open_supply(path) as (title, reader):
        semester = parse_semester(title)
        _require_columns(reader, _VALORI_COLUMNS)
        descriptions = descriptions or {}
        rows: list[dict] = []
        skipped = 0
        for row in _iter_rows(reader):
            municipality_code = _clean(row.get("Comune_amm"))
            zone_code = _clean(row.get("Zona"))
            if not municipality_code or not zone_code:
                skipped += 1
                continue
            produced = 0
            for contract, (min_column, max_column) in _CONTRACT_COLUMNS.items():
                low = _to_price(row.get(min_column))
                high = _to_price(row.get(max_column))
                # A band whose halves are missing, or inverted, is not a band.
                # Dropping just this contract keeps the other one: a row may
                # legitimately quote a sale price and no rent.
                if low is None or high is None or low > high:
                    continue
                rows.append(
                    {
                        "semester": semester,
                        "municipality_code": municipality_code,
                        "municipality": _clean(row.get("Comune_descrizione")),
                        "zone_code": zone_code,
                        "zone_description": descriptions.get((municipality_code, zone_code), ""),
                        "property_type_code": _clean(row.get("Cod_Tip")),
                        "property_type": _clean(row.get("Descr_Tipologia")),
                        "conservation_state": _clean(row.get("Stato")),
                        "contract": contract,
                        "min_sqm_price": low,
                        "max_sqm_price": high,
                    }
                )
                produced += 1
            if not produced:
                skipped += 1
        return semester, rows, skipped


def resolve_supply(path: Path) -> tuple[Path, Path | None]:
    """Finds the prices file, and its zone file when present.

    Accepts either the CSV itself or the directory the delivery was extracted
    into (searched recursively — the archives nest). Files are identified by
    their title line, never by their name, because the names carry the
    requester's codice fiscale.
    """
    if not path.exists():
        raise OmiImportError(
            "The configured OMI directory does not exist. Check `omi_input_dir` in "
            "settings.json, and that the download was extracted there."
        )
    if path.is_file():
        return path, None

    valori: Path | None = None
    zone: Path | None = None
    for candidate in sorted(path.rglob("*.csv")):
        try:
            with candidate.open(encoding="utf-8-sig", errors="replace") as handle:
                title = handle.readline().lower()
        except OSError:
            continue
        if _VALORI_MARKER in title and valori is None:
            valori = candidate
        elif _ZONE_MARKER in title and zone is None:
            zone = candidate
    if valori is None:
        raise OmiImportError(
            "No OMI quotations file was found in the configured directory. Expected the "
            "extracted CSV export ('Valori di Mercato') from the Agenzia delle Entrate."
        )
    return valori, zone


def import_quotations(db: Session, path: Path | str | None = None) -> dict:
    """Imports one semester of OMI quotations, replacing that semester if it is
    already present.

    Replacement is per semester and total: re-importing 2025/2 deletes the 2025/2
    rows and writes the new ones, so a re-run leaves the row count unchanged
    instead of doubling it, and a municipal supply can be replaced by the
    national one without leaving half of the old import behind. Other semesters
    are untouched — two coexist, and `latest_semester` decides which one wins.
    """
    if path is None or path == "":
        from ..config import load_settings

        configured = (load_settings().get("omi_input_dir") or "").strip()
        if not configured:
            raise OmiImportError(
                "No OMI directory is configured. Set `omi_input_dir` in settings.json to "
                "the folder where the download was extracted."
            )
        path = configured

    supply = Path(path).expanduser()
    valori_path, zone_path = resolve_supply(supply)
    descriptions = read_zone_descriptions(zone_path) if zone_path else {}
    semester, rows, skipped = read_quotations(valori_path, descriptions)

    # Counted before the delete rather than read off the result's rowcount: the
    # count is reported back to the user, and a number that only exists as an
    # untyped DBAPI attribute is the kind that silently becomes -1 one driver
    # later.
    replaced = db.execute(
        select(func.count()).select_from(OmiQuotation).where(OmiQuotation.semester == semester)
    ).scalar_one()
    db.execute(delete(OmiQuotation).where(OmiQuotation.semester == semester))
    imported_at = datetime.now(UTC)
    db.add_all([OmiQuotation(imported_at=imported_at, **row) for row in rows])
    db.commit()

    # Counts only: no path, and nothing derived from the delivery's filenames.
    logger.info(
        "OMI import: semester %s, %d quotations, %d rows skipped, %d replaced",
        semester,
        len(rows),
        skipped,
        replaced,
    )
    return {
        "semester": semester,
        "imported": len(rows),
        "skipped": skipped,
        "replaced": replaced,
        "zones_described": len(descriptions),
    }


def latest_semester(db: Session) -> str | None:
    """The newest imported semester, or None when nothing has been imported.

    Ordered in Python rather than by SQL `max()`: the comparison is numeric on
    (year, half), and the day a "2025/10" exists a text `max()` would answer
    "2025/2" without complaining.
    """
    semesters = db.execute(select(OmiQuotation.semester).distinct()).scalars().all()
    if not semesters:
        return None
    return max(semesters, key=semester_sort_key)


def find_quotations(
    db: Session,
    municipality_code: str,
    zone_code: str,
    contract: str | None = None,
) -> list[OmiQuotation]:
    """Quotations for one zone, from the newest imported semester only.

    Never mixes semesters: an older import lingering for a zone the newest
    supply covers differently would otherwise widen the band with figures of two
    different dates, and the whole point of these numbers is that they carry one.
    Returns [] when nothing matches — the caller shows no OMI benchmark and no
    error (fail open).
    """
    if not municipality_code or not zone_code:
        return []
    newest = latest_semester(db)
    if newest is None:
        return []
    query = select(OmiQuotation).where(
        OmiQuotation.semester == newest,
        OmiQuotation.municipality_code == municipality_code,
        OmiQuotation.zone_code == zone_code,
    )
    if contract:
        query = query.where(OmiQuotation.contract == contract)
    return list(db.execute(query).scalars().all())
