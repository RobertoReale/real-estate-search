"""Placing a property inside its OMI micro-zone (services/omi_zones.py).

Every perimeter here is **verbatim from the real 2025/2 national delivery**, cut
down to two comuni so it can be committed: three Milan zones (`F205`), and the
two of a small neighbouring comune (`L704`) that has no quotations, which is
what the size bound is tested against.

The landmark points are the real reason to prefer real geometry. The Duomo
resolves to zone **B12** — the same `F205` + `B12` pair the quotations fixture
next door holds a price band for — and Milano Centrale to **C15**, which has a
hole in it. A hand-drawn square would have proved the ray casting agrees with
itself and nothing else.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.config import save_settings
from app.database import Base, get_db
from app.models import OmiQuotation, OmiZone, Property
from app.services import geo_filter, omi_import, omi_zones

FIXTURES = Path(__file__).parent / "fixtures"
MILAN_KML = FIXTURES / "omi_zones_sample.kml"
NEIGHBOUR_KML = FIXTURES / "omi_zones_neighbour_sample.kml"
VALORI = FIXTURES / "omi_valori_sample.csv"

# Real landmarks, and the zones the real perimeters put them in.
DUOMO = (45.46420, 9.19000)
CENTRALE = (45.48630, 9.20480)
# Inside C15's outer ring and inside its hole: the donut has to actually work.
C15_HOLE = (45.494198, 9.201203)
# Vedano al Lambro, ~17 km north: inside the neighbour fixture, outside Milan.
VEDANO = (45.61000, 9.27000)

MILAN_ZONES = {"B12", "C13", "C15"}
SEMESTER = "2025/2"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def quote(db, municipality_code="F205", zone_code="B12", semester=SEMESTER):
    """A minimal quotation, so `import_zones` has a comune to keep."""
    db.add(
        OmiQuotation(
            semester=semester,
            municipality_code=municipality_code,
            zone_code=zone_code,
            min_sqm_price=8700.0,
            max_sqm_price=10900.0,
        )
    )
    db.commit()


def supply(tmp_path: Path, *files: Path) -> Path:
    """A throwaway directory holding copies of the given fixture perimeters."""
    directory = tmp_path / "perimeters"
    directory.mkdir(exist_ok=True)
    for file in files:
        (directory / file.name).write_bytes(file.read_bytes())
    return directory


# --------------------------------------------------------------------------
# parsing the real KML
# --------------------------------------------------------------------------


def test_reads_comune_semester_and_zones_from_a_real_file():
    municipality, semester, zones = omi_zones.read_perimeters(MILAN_KML)
    assert municipality == "MILANO"
    assert semester == SEMESTER
    assert {z["zone_code"] for z in zones} == MILAN_ZONES
    assert {z["municipality_code"] for z in zones} == {"F205"}


def test_the_semester_comes_from_the_document_title_and_nowhere_else():
    """Same trap as the CSV's title line: no placemark carries the semester."""
    assert omi_zones.parse_title("MILANO (MI) Anno/Semestre 2025/2 generato il 12/03/2026") == (
        "MILANO",
        "2025/2",
    )
    with pytest.raises(omi_import.OmiImportError):
        omi_zones.parse_title("MILANO - Zona OMI B12")


def test_a_zone_keeps_every_polygon_and_every_hole():
    """A zone is a MultiGeometry with holes, not one ring. C15 has both."""
    _, _, zones = omi_zones.read_perimeters(MILAN_KML)
    c15 = next(z for z in zones if z["zone_code"] == "C15")
    assert sum(len(p["holes"]) for p in c15["polygons"]) == 1
    # ...and the vertices survived the lng,lat -> (lat, lng) swap.
    lats = [lat for p in c15["polygons"] for lat, _ in p["outer"]]
    lngs = [lng for p in c15["polygons"] for _, lng in p["outer"]]
    assert 45.0 < min(lats) and max(lats) < 46.0
    assert 9.0 < min(lngs) and max(lngs) < 10.0


def test_a_file_declaring_utf8_and_not_being_it_still_parses(tmp_path):
    """Two comuni in the real national supply do exactly this (an accent in the
    name). Aimed at the path, ElementTree raises and takes the delivery with it."""
    broken = tmp_path / "broken.kml"
    broken.write_bytes(MILAN_KML.read_bytes().replace(b"MILANO (MI)", b"MILAN\xbf (MI)"))
    municipality, semester, zones = omi_zones.read_perimeters(broken)
    assert semester == SEMESTER
    assert {z["zone_code"] for z in zones} == MILAN_ZONES
    # The mangled byte lands in the name and nowhere near the join keys.
    assert municipality.startswith("MILAN")


def test_a_file_that_is_not_xml_is_skipped_and_counted(db, tmp_path):
    quote(db)
    directory = supply(tmp_path, MILAN_KML)
    (directory / "truncated.kml").write_text("<?xml version='1.0'?><kml><Docu", encoding="utf-8")
    result = omi_zones.import_zones(db, directory)
    assert result["files_found"] == 2
    assert result["files_unreadable"] == 1
    assert result["imported"] == len(MILAN_ZONES)


# --------------------------------------------------------------------------
# the import, and the bound that keeps it a sane size
# --------------------------------------------------------------------------


def test_import_stores_the_perimeters_with_their_bounding_box(db, tmp_path):
    quote(db)
    result = omi_zones.import_zones(db, supply(tmp_path, MILAN_KML))
    assert result["imported"] == len(MILAN_ZONES)
    assert result["semesters"] == [SEMESTER]
    assert result["municipalities"] == 1

    b12 = db.scalar(select(OmiZone).where(OmiZone.zone_code == "B12"))
    assert b12 is not None
    assert b12.municipality == "MILANO"
    assert b12.municipality_code == "F205"
    assert b12.min_lat <= DUOMO[0] <= b12.max_lat
    assert b12.min_lng <= DUOMO[1] <= b12.max_lng
    assert len(json.loads(b12.rings)) >= 1


def test_only_comuni_with_quotations_are_kept(db, tmp_path):
    """The national supply is ~28 000 zones; a perimeter with no price behind it
    can produce no benchmark, so it is not stored."""
    quote(db)  # F205 only
    result = omi_zones.import_zones(db, supply(tmp_path, MILAN_KML, NEIGHBOUR_KML))
    assert result["files_found"] == 2
    assert {z.municipality_code for z in db.scalars(select(OmiZone))} == {"F205"}
    assert result["imported"] == len(MILAN_ZONES)


def test_the_neighbour_lands_once_it_has_quotations(db, tmp_path):
    quote(db)
    quote(db, municipality_code="L704", zone_code="B1")
    omi_zones.import_zones(db, supply(tmp_path, MILAN_KML, NEIGHBOUR_KML))
    assert {z.municipality_code for z in db.scalars(select(OmiZone))} == {"F205", "L704"}


def test_import_refuses_when_no_quotations_exist_yet(db, tmp_path):
    with pytest.raises(omi_import.OmiImportError, match="quotations"):
        omi_zones.import_zones(db, supply(tmp_path, MILAN_KML))


def test_a_directory_with_no_perimeters_says_the_supply_is_the_wrong_one(db, tmp_path):
    quote(db)
    empty = tmp_path / "prices-only"
    empty.mkdir()
    (empty / "valori.csv").write_bytes(VALORI.read_bytes())
    with pytest.raises(omi_import.OmiImportError, match="national"):
        omi_zones.import_zones(db, empty)


def test_reimporting_a_semester_replaces_it(db, tmp_path):
    quote(db)
    directory = supply(tmp_path, MILAN_KML)
    first = omi_zones.import_zones(db, directory)
    again = omi_zones.import_zones(db, directory)
    assert again["replaced"] == first["imported"]
    assert db.scalar(select(OmiZone.id).order_by(OmiZone.id)) is not None
    assert len(db.scalars(select(OmiZone)).all()) == first["imported"]


def test_two_semesters_coexist_and_the_newest_wins(db, tmp_path):
    quote(db)
    omi_zones.import_zones(db, supply(tmp_path, MILAN_KML))
    older = tmp_path / "older"
    older.mkdir()
    (older / "old.kml").write_bytes(
        MILAN_KML.read_bytes().replace(b"Anno/Semestre 2025/2", b"Anno/Semestre 2024/1")
    )
    omi_zones.import_zones(db, older)
    assert {z.semester for z in db.scalars(select(OmiZone))} == {"2024/1", SEMESTER}
    assert omi_zones.latest_zone_semester(db) == SEMESTER
    # ...and a lookup never reaches into the older set.
    newest = omi_zones.find_zone(db, *DUOMO)
    assert newest is not None and newest.semester == SEMESTER


def test_no_path_or_filename_reaches_the_error_messages(db, tmp_path):
    """The delivery's own names carry the requester's codice fiscale."""
    directory = tmp_path / "QIP0000000_AAAAAA00A00A000A"
    directory.mkdir()
    quote(db)
    with pytest.raises(omi_import.OmiImportError) as excinfo:
        omi_zones.import_zones(db, directory)
    assert "QIP" not in str(excinfo.value)
    assert str(directory) not in str(excinfo.value)


# --------------------------------------------------------------------------
# the geometry
# --------------------------------------------------------------------------


def test_a_point_inside_a_zone_resolves_to_it(db, tmp_path):
    quote(db)
    omi_zones.import_zones(db, supply(tmp_path, MILAN_KML))
    zone = omi_zones.find_zone(db, *DUOMO)
    assert zone is not None
    assert (zone.municipality_code, zone.zone_code) == ("F205", "B12")
    centrale = omi_zones.find_zone(db, *CENTRALE)
    assert centrale is not None and centrale.zone_code == "C15"


def test_a_point_outside_every_zone_resolves_to_nothing(db, tmp_path):
    quote(db)
    omi_zones.import_zones(db, supply(tmp_path, MILAN_KML))
    assert omi_zones.find_zone(db, 45.0703, 7.6869) is None  # Turin
    assert omi_zones.find_zone(db, *VEDANO) is None  # a comune not imported


def test_a_point_in_a_hole_is_outside_the_zone(db, tmp_path):
    """C15's inner boundary is a block that belongs to another zone. It is
    inside the outer ring, and it is not in C15."""
    quote(db)
    omi_zones.import_zones(db, supply(tmp_path, MILAN_KML))
    c15 = db.scalar(select(OmiZone).where(OmiZone.zone_code == "C15"))
    polygon = next(p for p in omi_zones.decode_rings(c15.rings) if p["holes"])
    assert geo_filter.point_in_polygon(*C15_HOLE, polygon["outer"]) is True
    assert geo_filter.point_in_rings(*C15_HOLE, polygon["outer"], polygon["holes"]) is False
    assert omi_zones.find_zone(db, *C15_HOLE) is None


def test_point_in_rings_without_holes_is_the_plain_polygon_test():
    square = [(0.0, 0.0), (0.0, 2.0), (2.0, 2.0), (2.0, 0.0)]
    assert geo_filter.point_in_rings(1.0, 1.0, square) is True
    assert geo_filter.point_in_rings(3.0, 1.0, square) is False


def test_decode_rings_survives_a_row_it_cannot_read():
    assert omi_zones.decode_rings("not json") == []
    assert omi_zones.decode_rings('[{"outer": [[1, 2], [3, 4]]}]') == []  # under 3 vertices


# --------------------------------------------------------------------------
# the batch that places the properties
# --------------------------------------------------------------------------


def add_property(db, lat, lng, **kwargs):
    prop = Property(fingerprint=f"p{lat}-{lng}", latitude=lat, longitude=lng, **kwargs)
    db.add(prop)
    db.commit()
    return prop


def test_the_batch_places_properties_and_leaves_the_rest_alone(db, tmp_path):
    quote(db)
    omi_zones.import_zones(db, supply(tmp_path, MILAN_KML))
    inside = add_property(db, *DUOMO)
    outside = add_property(db, 45.0703, 7.6869)
    nowhere = Property(fingerprint="no-pin")
    db.add(nowhere)
    db.commit()

    summary = omi_zones.resolve_property_zones(db)
    assert summary["scanned"] == 2
    assert summary["placed"] == 1
    assert summary["unplaced"] == 1
    assert summary["no_coordinates"] == 1
    assert summary["semester"] == SEMESTER

    db.refresh(inside)
    db.refresh(outside)
    db.refresh(nowhere)
    assert (inside.omi_municipality_code, inside.omi_zone_code) == ("F205", "B12")
    assert outside.omi_zone_code == ""
    assert nowhere.omi_zone_code == ""


def test_a_property_with_no_coordinates_is_never_touched(db, tmp_path):
    quote(db)
    omi_zones.import_zones(db, supply(tmp_path, MILAN_KML))
    # A placement made when it still had a pin: nothing here can honestly revise it.
    blind = Property(fingerprint="no-pin", omi_municipality_code="F205", omi_zone_code="B12")
    db.add(blind)
    db.commit()
    omi_zones.resolve_property_zones(db)
    db.refresh(blind)
    assert blind.omi_zone_code == "B12"


def test_the_batch_is_rerunnable_and_moves_a_redrawn_placement(db, tmp_path):
    quote(db)
    omi_zones.import_zones(db, supply(tmp_path, MILAN_KML))
    prop = add_property(db, *DUOMO, omi_municipality_code="F205", omi_zone_code="D99")
    summary = omi_zones.resolve_property_zones(db)
    assert summary["moved"] == 1
    db.refresh(prop)
    assert prop.omi_zone_code == "B12"
    # A second run finds nothing left to move.
    assert omi_zones.resolve_property_zones(db)["moved"] == 0


def test_a_placement_that_no_longer_holds_is_cleared(db, tmp_path):
    quote(db)
    omi_zones.import_zones(db, supply(tmp_path, MILAN_KML))
    stale = add_property(db, 45.0703, 7.6869, omi_municipality_code="F205", omi_zone_code="B12")
    summary = omi_zones.resolve_property_zones(db)
    assert summary["cleared"] == 1
    db.refresh(stale)
    assert stale.omi_zone_code == ""


def test_the_batch_does_nothing_when_no_perimeters_are_imported(db):
    prop = add_property(db, *DUOMO)
    summary = omi_zones.resolve_property_zones(db)
    assert summary["semester"] is None
    assert summary["scanned"] == 0
    db.refresh(prop)
    assert prop.omi_zone_code == ""


# --------------------------------------------------------------------------
# the endpoints, and the rule that the grid never does geometry
# --------------------------------------------------------------------------


@pytest.fixture
def api():
    """`TestClient` without its context manager, like `test_omi_import.py`:
    entering it runs the lifespan, which starts the real scheduler and would
    have the suite scanning portals.

    One shared session so a test can seed rows and read back what the endpoint
    wrote, rather than watching two connections disagree.
    """
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()

    def override_db():
        yield session

    main.app.dependency_overrides[get_db] = override_db
    client = TestClient(main.app)
    # setattr, not an assignment: TestClient has no such attribute and the
    # house style hangs test-only state on it this way (ruff's B010 is
    # ignored project-wide for exactly this).
    setattr(client, "session", session)
    yield client
    main.app.dependency_overrides.clear()
    session.close()


def test_the_endpoints_import_and_resolve(api, tmp_path):
    quote(api.session)
    add_property(api.session, *DUOMO)

    imported = api.post(
        "/api/maintenance/omi-zones-import",
        params={"path": str(supply(tmp_path, MILAN_KML))},
    )
    assert imported.status_code == 200
    assert imported.json()["imported"] == len(MILAN_ZONES)

    resolved = api.post("/api/maintenance/omi-zones-resolve")
    assert resolved.status_code == 200
    assert resolved.json()["placed"] == 1


def test_the_import_endpoint_reports_a_bad_supply_as_400(api, tmp_path):
    """The same shape the quotations import and the two batches use."""
    quote(api.session)
    response = api.post(
        "/api/maintenance/omi-zones-import", params={"path": str(tmp_path / "not-extracted")}
    )
    assert response.status_code == 400
    assert "omi_input_dir" in response.json()["detail"]


def test_the_resolve_endpoint_answers_with_nothing_imported(api):
    """Fail open: no perimeters is a set of zeroes, not an error."""
    response = api.post("/api/maintenance/omi-zones-resolve")
    assert response.status_code == 200
    assert response.json()["semester"] is None


def test_the_import_endpoint_falls_back_to_the_configured_directory(api, tmp_path):
    quote(api.session)
    save_settings({"omi_input_dir": str(supply(tmp_path, MILAN_KML))})
    response = api.post("/api/maintenance/omi-zones-import")
    assert response.status_code == 200
    assert response.json()["imported"] == len(MILAN_ZONES)


def test_the_grid_page_does_no_geometry(api, tmp_path, monkeypatch):
    """Acceptance: rendering the dashboard must not place anything. The stored
    column is the whole point — resolving on read would put ray casting over
    hundreds of vertices inside every card, on every card."""
    quote(api.session)
    api.post(
        "/api/maintenance/omi-zones-import",
        params={"path": str(supply(tmp_path, MILAN_KML))},
    )
    prop = add_property(api.session, *DUOMO)
    api.post("/api/maintenance/omi-zones-resolve")

    def explode(*args, **kwargs):
        raise AssertionError("the grid must not do geometry")

    monkeypatch.setattr(omi_zones, "find_zone", explode)
    monkeypatch.setattr(geo_filter, "point_in_polygon", explode)
    monkeypatch.setattr(geo_filter, "point_in_rings", explode)

    response = api.get("/api/properties")
    assert response.status_code == 200
    api.session.refresh(prop)
    assert prop.omi_zone_code == "B12"
