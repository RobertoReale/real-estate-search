"""Placing a property inside its OMI micro-zone.

`omi_import.py` brings in the prices, keyed by (comune, zone). This brings in
the perimeters those zone codes name, so a property that only has coordinates
can be told which zone it is in — without that, the quotations are a table
nothing can be looked up in.

The perimeters ship as **KML**, one file per comune, and only with the
*national* supply: a municipal delivery holds the prices and no geometry at all.

What the real 2025/2 delivery taught us, in the order it hurts:

* **It is 7 887 files and roughly 28 000 zones.** Stored whole that is ~340 MB
  of geometry in a SQLite file that also holds months of price history and gets
  snapshotted before every reset. So the import keeps only the comuni that have
  quotations already imported: a perimeter with no price behind it can produce
  no benchmark, and is pure weight.
* **Two of those files are not valid UTF-8** despite declaring it — a comune
  with an accent in its name (`FIÈ ALLO SCILIAR`). `ElementTree` aimed at the
  path raises `ParseError` and takes the other 7 885 with it, so the bytes are
  decoded leniently first. Same reasoning as the CSV importer next door: the
  mangled character is in a *name*, and the join keys (`F205`, `B12`) are ASCII
  by construction.
* **A zone is not one polygon.** It is a `MultiGeometry` of several, and those
  polygons have holes — a block inside the perimeter that belongs to a
  different zone. A parser that reads the first ring and stops is wrong only at
  addresses nobody thinks to check.
* **`LINKZONA` is present and empty**, the same trap `omi_import` records from
  the other side. The pair that joins is `CODCOM` + `CODZONA`.
* **The semester is in the document title and nowhere else**, exactly as it is
  in the CSV's title line.

Point-in-polygon is `geo_filter`'s ray casting, which was already there for the
map's drawn filter. Not `shapely`: GEOS is a compiled dependency and this app is
frozen into a PyInstaller bundle, where every native library is a new way for
the release to break on someone else's machine.

Two rules carried over from the importer next door. **A file that cannot be
read is skipped and counted, never fatal** — a national supply is thousands of
them and one bad byte must not lose the rest — and **fail open**: a property
with no coordinates, or one that falls in no zone, gets no OMI benchmark and no
error.

Paths never reach a message or a log line here. The Agenzia names each delivery
after the person who requested it, so the supply's own filenames carry a codice
fiscale.
"""

import json
import logging
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..models import OmiQuotation, OmiZone, Property
from .geo_filter import point_in_rings
from .omi_import import OmiImportError, semester_sort_key

logger = logging.getLogger(__name__)

# "MILANO (MI) Anno/Semestre 2025/2 generato il 12/03/2026 17:19" — the KML
# document title, which is where the comune's name and the semester both live.
_TITLE_PATTERN = re.compile(
    r"^(?P<name>.*?)\s*\((?P<prov>[A-Z]{2})\)\s*Anno/Semestre\s*(?P<year>\d{4})\s*/\s*(?P<half>[12])\b"
)

# Coordinates are delivered at 6 decimals (~0.1 m) and stored as delivered.
# Rounding is only to stop float repr from turning "9.244727" into eighteen
# characters across 28 000 zones.
_COORD_PRECISION = 6

# `{http://www.opengis.net/kml/2.2}Polygon` → `Polygon`. Matching on the local
# name rather than declaring the namespace: KML 2.1 and 2.2 differ only in that
# URI, and a file that omits it entirely still has to parse.
_NAMESPACE = re.compile(r"^\{[^}]*\}")


def _tag(element: ET.Element) -> str:
    return _NAMESPACE.sub("", element.tag)


def _first(element: ET.Element, name: str) -> ET.Element | None:
    """The first direct child with this local name."""
    for child in element:
        if _tag(child) == name:
            return child
    return None


def _descendants(element: ET.Element, name: str) -> list[ET.Element]:
    """Every descendant with this local name, at any depth.

    Depth-agnostic on purpose: a placemark's polygons sit inside a
    `MultiGeometry` when the zone has more than one, and directly under the
    `Placemark` when it has exactly one. Both shapes occur in the same delivery.
    """
    found: list[ET.Element] = []
    for child in element:
        if _tag(child) == name:
            found.append(child)
        found.extend(_descendants(child, name))
    return found


def parse_title(title: str) -> tuple[str, str]:
    """(municipality, semester) from a KML document title.

    Raises `OmiImportError` when the title is not one — an undated perimeter is
    not something to store, since "which semester is this" is the question the
    whole feature has to keep answering (the figures are dated or they are a
    claim with no expiry).
    """
    match = _TITLE_PATTERN.match((title or "").strip())
    if not match:
        raise OmiImportError(
            "The zone perimeter file does not name its comune and semester on the "
            "document title: this does not look like an OMI perimeter export."
        )
    return match.group("name").strip(), f"{match.group('year')}/{match.group('half')}"


def _parse_ring(ring: ET.Element) -> list[tuple[float, float]]:
    """One `LinearRing` → [(lat, lng), …].

    KML orders a coordinate `lng,lat,altitude`; every other coordinate in this
    codebase is (lat, lng), so the swap happens here once rather than at each
    use. A vertex that is not two numbers is dropped: it cannot be placed, and
    losing the whole perimeter over it would be the worse answer.
    """
    node = _first(ring, "coordinates")
    if node is None:
        return []
    vertices: list[tuple[float, float]] = []
    for chunk in (node.text or "").split():
        parts = chunk.split(",")
        if len(parts) < 2:
            continue
        try:
            lng, lat = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
            continue
        vertices.append((round(lat, _COORD_PRECISION), round(lng, _COORD_PRECISION)))
    return vertices


def _parse_boundary(polygon: ET.Element, name: str) -> list[list[tuple[float, float]]]:
    rings: list[list[tuple[float, float]]] = []
    for boundary in _descendants(polygon, name):
        for ring in _descendants(boundary, "LinearRing"):
            vertices = _parse_ring(ring)
            # Under three vertices is a degenerate ring — a marker, not an area.
            if len(vertices) >= 3:
                rings.append(vertices)
    return rings


def _parse_placemark(placemark: ET.Element) -> dict | None:
    """One zone, or None when the placemark carries no usable geometry."""
    data: dict[str, str] = {}
    for node in _descendants(placemark, "Data"):
        value = _first(node, "value")
        data[node.get("name", "")] = (value.text or "").strip() if value is not None else ""
    municipality_code = data.get("CODCOM", "").strip()
    zone_code = data.get("CODZONA", "").strip()
    if not municipality_code or not zone_code:
        return None

    polygons: list[dict] = []
    for polygon in _descendants(placemark, "Polygon"):
        outers = _parse_boundary(polygon, "outerBoundaryIs")
        if not outers:
            continue
        holes = _parse_boundary(polygon, "innerBoundaryIs")
        # One outer boundary per `Polygon` is what KML defines; taking [0] keeps
        # the holes attached to the ring they were authored against instead of
        # letting them cut across a sibling.
        polygons.append({"outer": outers[0], "holes": holes})
    if not polygons:
        return None
    return {
        "municipality_code": municipality_code,
        "zone_code": zone_code,
        "polygons": polygons,
    }


def read_perimeters(path: Path) -> tuple[str, str, list[dict]]:
    """One comune's KML → (municipality, semester, zones).

    The bytes are decoded leniently and handed back to the parser as UTF-8: two
    files in the real national supply declare UTF-8 and are not, and `ET.parse`
    on the path alone loses them entirely (see the module docstring).
    """
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise OmiImportError("A zone perimeter file could not be opened for reading.") from e
    try:
        root = ET.fromstring(raw.decode("utf-8", errors="replace").encode("utf-8"))
    except ET.ParseError as e:
        raise OmiImportError("A zone perimeter file is not well-formed XML.") from e

    title_node = next((el for el in root.iter() if _tag(el) == "name"), None)
    title = (title_node.text or "") if title_node is not None else ""
    municipality, semester = parse_title(title)
    zones = [z for z in (_parse_placemark(pm) for pm in _descendants(root, "Placemark")) if z]
    return municipality, semester, zones


def _bounds(polygons: list[dict]) -> tuple[float, float, float, float]:
    lats = [lat for polygon in polygons for lat, _ in polygon["outer"]]
    lngs = [lng for polygon in polygons for _, lng in polygon["outer"]]
    return min(lats), max(lats), min(lngs), max(lngs)


def _encode(polygons: list[dict]) -> str:
    return json.dumps(polygons, separators=(",", ":"))


def decode_rings(rings: str) -> list[dict]:
    """The stored geometry back as `[{"outer": [(lat, lng), …], "holes": [...]}]`.

    Tolerant of a row it cannot read: a zone whose geometry does not round-trip
    is one zone that never matches, not an exception thrown at whoever happened
    to be standing near it.
    """
    try:
        decoded = json.loads(rings or "[]")
    except ValueError:
        return []
    polygons: list[dict] = []
    for polygon in decoded if isinstance(decoded, list) else []:
        if not isinstance(polygon, dict):
            continue
        outer = [(float(v[0]), float(v[1])) for v in polygon.get("outer") or [] if len(v) >= 2]
        if len(outer) < 3:
            continue
        holes = [
            [(float(v[0]), float(v[1])) for v in hole if len(v) >= 2]
            for hole in polygon.get("holes") or []
        ]
        polygons.append({"outer": outer, "holes": [h for h in holes if len(h) >= 3]})
    return polygons


def wanted_municipalities(db: Session) -> set[str]:
    """The comuni worth storing perimeters for: the ones the quotations cover.

    This is the bound that keeps the table a sane size. The national supply is
    ~28 000 zones and ~340 MB of geometry, and a perimeter whose comune has no
    prices imported can never produce a benchmark — it would be weight in the
    database, in every backup, and in every bounding-box probe, in exchange for
    nothing. Import the quotations first; this follows them.
    """
    return set(db.execute(select(OmiQuotation.municipality_code).distinct()).scalars().all())


def resolve_perimeter_files(path: Path) -> list[Path]:
    """Every KML in the delivery, or the single file the caller named.

    Searched recursively, like `omi_import.resolve_supply`, because the archives
    nest. Sorted so a run is reproducible and its skip counts mean the same
    thing twice.
    """
    if not path.exists():
        raise OmiImportError(
            "The configured OMI directory does not exist. Check `omi_input_dir` in "
            "settings.json, and that the download was extracted there."
        )
    if path.is_file():
        return [path]
    files = sorted(path.rglob("*.kml"))
    if not files:
        raise OmiImportError(
            "No zone perimeters (.kml) were found in the configured directory. Only the "
            "*national* supply from the Agenzia delle Entrate carries them — a single-comune "
            "delivery holds the quotations and no geometry."
        )
    return files


def import_zones(db: Session, path: Path | str | None = None) -> dict:
    """Imports the zone perimeters for every comune that has quotations.

    Replacement is per semester and total, exactly as `import_quotations` does
    it: re-importing 2025/2 deletes the 2025/2 zones and writes the new ones, so
    a re-run leaves the count unchanged instead of doubling it. Other semesters
    are untouched — two coexist, and the newest wins at lookup.
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

    wanted = wanted_municipalities(db)
    if not wanted:
        raise OmiImportError(
            "No OMI quotations have been imported yet, so there is no comune to keep "
            "perimeters for. Import the quotations first: a perimeter with no prices "
            "behind it cannot produce a benchmark."
        )

    files = resolve_perimeter_files(Path(path).expanduser())
    rows: list[dict] = []
    semesters: set[str] = set()
    unreadable = 0
    for file in files:
        try:
            municipality, semester, zones = read_perimeters(file)
        except OmiImportError:
            # One unreadable comune out of thousands: counted, never fatal.
            unreadable += 1
            continue
        kept = [zone for zone in zones if zone["municipality_code"] in wanted]
        if not kept:
            continue
        semesters.add(semester)
        for zone in kept:
            min_lat, max_lat, min_lng, max_lng = _bounds(zone["polygons"])
            rows.append(
                {
                    "semester": semester,
                    "municipality_code": zone["municipality_code"],
                    "municipality": municipality,
                    "zone_code": zone["zone_code"],
                    "min_lat": min_lat,
                    "max_lat": max_lat,
                    "min_lng": min_lng,
                    "max_lng": max_lng,
                    "rings": _encode(zone["polygons"]),
                }
            )

    replaced = 0
    for semester in semesters:
        replaced += db.execute(
            select(func.count()).select_from(OmiZone).where(OmiZone.semester == semester)
        ).scalar_one()
        db.execute(delete(OmiZone).where(OmiZone.semester == semester))
    db.add_all([OmiZone(**row) for row in rows])
    db.commit()

    # Counts only: no path, and nothing derived from the delivery's filenames.
    logger.info(
        "OMI zones: %d perimeters for %d comuni, %d files unreadable, %d replaced",
        len(rows),
        len({row["municipality_code"] for row in rows}),
        unreadable,
        replaced,
    )
    return {
        "semesters": sorted(semesters),
        "imported": len(rows),
        "municipalities": len({row["municipality_code"] for row in rows}),
        # Both numbers, always, for the reason the quotations import reports
        # both of its own: an import that named only what it kept would look
        # identical whether the other 7 800 files were irrelevant or corrupt.
        "files_found": len(files),
        "files_unreadable": unreadable,
        "replaced": replaced,
    }


def latest_zone_semester(db: Session) -> str | None:
    """The newest imported perimeter semester, ordered numerically for the same
    reason `omi_import.latest_semester` is: a text `max()` answers "2025/2" over
    "2025/10" the day the format grows a digit."""
    semesters = db.execute(select(OmiZone.semester).distinct()).scalars().all()
    if not semesters:
        return None
    return max(semesters, key=semester_sort_key)


def find_zone(db: Session, lat: float, lng: float, semester: str | None = None) -> OmiZone | None:
    """The OMI zone a coordinate falls in, or None.

    Two zones can both claim a point that sits exactly on the boundary they
    share, because `point_in_polygon` counts on-edge as inside — deliberately,
    so a vertex-snapped listing is never dropped by both. The candidates are
    therefore ordered, and the first match wins: the same pin resolves to the
    same zone on every run, which is what makes the batch's output reproducible.
    """
    semester = semester or latest_zone_semester(db)
    if semester is None:
        return None
    candidates = db.scalars(
        select(OmiZone)
        .where(
            OmiZone.semester == semester,
            OmiZone.min_lat <= lat,
            OmiZone.max_lat >= lat,
            OmiZone.min_lng <= lng,
            OmiZone.max_lng >= lng,
        )
        .order_by(OmiZone.municipality_code, OmiZone.zone_code, OmiZone.id)
    ).all()
    for zone in candidates:
        for polygon in decode_rings(zone.rings):
            if point_in_rings(lat, lng, polygon["outer"], polygon["holes"]):
                return zone
    return None


def resolve_property_zones(db: Session) -> dict:
    """Fill `omi_zone_code` on every property, from its coordinates.

    User-triggered and never automatic, under the rule the commute annotation
    already follows: a grid render must not do geometry. Unlike that one this
    costs no network at all, only arithmetic, so there is nothing to pace, no
    budget to spend and no progress to poll — it runs to the end in one call.

    Every property with coordinates is recomputed rather than only the unplaced
    ones. The batch is cheap, and a run after a fresh import has to be able to
    *move* a property whose zone was redrawn — placing only the empty ones would
    leave last semester's answer sitting there looking current.

    A property with no coordinates is left exactly as it is: it was never placed
    by geometry, so there is nothing here that can honestly change it.
    """
    semester = latest_zone_semester(db)
    summary = {
        "semester": semester,
        "scanned": 0,
        "placed": 0,
        "moved": 0,
        "cleared": 0,
        "unplaced": 0,
        "no_coordinates": 0,
    }
    summary["no_coordinates"] = db.execute(
        select(func.count())
        .select_from(Property)
        .where((Property.latitude.is_(None)) | (Property.longitude.is_(None)))
    ).scalar_one()
    if semester is None:
        return summary

    properties = db.scalars(
        select(Property)
        .where(Property.latitude.is_not(None))
        .where(Property.longitude.is_not(None))
        .order_by(Property.id)
    ).all()
    for prop in properties:
        if prop.latitude is None or prop.longitude is None:
            continue  # the query excludes these; the check is for the type
        summary["scanned"] += 1
        zone = find_zone(db, prop.latitude, prop.longitude, semester)
        previous = (prop.omi_municipality_code, prop.omi_zone_code)
        if zone is None:
            summary["unplaced"] += 1
            if any(previous):
                summary["cleared"] += 1
            prop.omi_municipality_code = ""
            prop.omi_zone_code = ""
            continue
        summary["placed"] += 1
        if any(previous) and previous != (zone.municipality_code, zone.zone_code):
            summary["moved"] += 1
        prop.omi_municipality_code = zone.municipality_code
        prop.omi_zone_code = zone.zone_code
    db.commit()

    logger.info(
        "OMI zones: placed %d of %d properties (%d unplaced, %d without coordinates)",
        summary["placed"],
        summary["scanned"],
        summary["unplaced"],
        summary["no_coordinates"],
    )
    return summary
