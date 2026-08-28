"""Import of the OMI quotations (services/omi_import.py).

Everything here runs against `fixtures/omi_valori_sample.csv` and
`fixtures/omi_zone_sample.csv`, which are **real rows from a real 2025/2
download**, not a file written from the format documentation. That distinction
is the point: a parser tested against an invention proves only that it agrees
with itself, and §8 of `implementation_plan.md` is a list of exactly that
mistake being made against real portals.

So the traps the real file contains are pinned here as behaviour: the title line
that is not the header, the semester that exists nowhere but that title, the
decimal commas, the trailing separator, and `LinkZona` — which looks like the
join key and matches nothing.

The corrupt-row cases are built by *mutating a copy* of the real fixture rather
than by hand-writing a broken file, so the "good" part of every such case is
still real data.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.config import save_settings
from app.database import Base, get_db
from app.models import OmiQuotation
from app.services import omi_import

FIXTURES = Path(__file__).parent / "fixtures"
VALORI = FIXTURES / "omi_valori_sample.csv"
ZONE = FIXTURES / "omi_zone_sample.csv"

# The fixture holds 10 real rows, each quoting a sale band and a rent band.
FIXTURE_ROWS = 10
FIXTURE_QUOTATIONS = FIXTURE_ROWS * 2


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _copy_supply(tmp_path: Path, valori_lines: list[str] | None = None) -> Path:
    """A throwaway directory holding the fixture supply, optionally with the
    prices file's data rows replaced."""
    directory = tmp_path / "supply"
    directory.mkdir(exist_ok=True)
    text = VALORI.read_text(encoding="utf-8")
    if valori_lines is not None:
        head = text.split("\n")[:2]
        text = "\n".join(head + valori_lines) + "\n"
    (directory / "prices.csv").write_text(text, encoding="utf-8")
    (directory / "zones.csv").write_text(ZONE.read_text(encoding="utf-8"), encoding="utf-8")
    return directory


def _data_lines() -> list[str]:
    return [ln for ln in VALORI.read_text(encoding="utf-8").split("\n")[2:] if ln.strip()]


def _written(tmp_path: Path, *data_lines: str) -> Path:
    """A prices file holding the real title + header and the given data rows."""
    head = VALORI.read_text(encoding="utf-8").split("\n")[:2]
    target = tmp_path / "prices.csv"
    target.write_text("\n".join(head + list(data_lines)) + "\n", encoding="utf-8")
    return target


# --- the format traps -------------------------------------------------------


def test_semester_comes_from_the_title_line():
    """No data row carries it, so a parser that only reads rows has no date at
    all — and an undated price band is a claim with no expiry."""
    semester, rows, _ = omi_import.read_quotations(VALORI)
    assert semester == "2025/2"
    assert all(r["semester"] == "2025/2" for r in rows)


def test_header_is_line_two_not_line_one():
    """Aimed at line 1, a DictReader names every column after the title
    sentence and every row comes out wrong without raising."""
    _semester, rows, skipped = omi_import.read_quotations(VALORI)
    assert skipped == 0
    assert len(rows) == FIXTURE_QUOTATIONS
    # Real values from the fixture's first row, which only parse correctly when
    # the header was read from line 2.
    first = rows[0]
    assert first["municipality_code"] == "F205"
    assert first["zone_code"] == "B12"
    assert first["property_type"] == "Abitazioni civili"
    assert first["conservation_state"] == "NORMALE"


def test_decimal_comma_is_a_decimal_point_not_a_thousands_separator():
    """`35,1` is thirty-five point one. float() raises on it, and stripping the
    comma turns it into 351 — an order of magnitude, silently."""
    assert omi_import._to_price("35,1") == pytest.approx(35.1)
    assert omi_import._to_price("16,5") == pytest.approx(16.5)
    _semester, rows, _ = omi_import.read_quotations(VALORI)
    rents = [r for r in rows if r["contract"] == "rent"]
    assert max(r["max_sqm_price"] for r in rents) < 100


def test_both_contracts_come_off_one_source_row():
    """Compr_* and Loc_* sit side by side; sale is €/m², rent is €/m² a month."""
    _semester, rows, _ = omi_import.read_quotations(VALORI)
    sale = [r for r in rows if r["contract"] == "sale"]
    rent = [r for r in rows if r["contract"] == "rent"]
    assert len(sale) == len(rent) == FIXTURE_ROWS
    assert min(r["min_sqm_price"] for r in sale) > 1000
    assert max(r["max_sqm_price"] for r in rent) < 100


def test_zone_descriptions_join_on_municipality_and_zone():
    """`LinkZona` is populated here and empty in the perimeters, so it joins
    nothing. The pair that works is Comune_amm + Zona."""
    descriptions = omi_import.read_zone_descriptions(ZONE)
    assert descriptions[("F205", "B12")].startswith("CENTRO STORICO")
    _semester, rows, _ = omi_import.read_quotations(VALORI, descriptions)
    assert all(r["zone_description"].startswith("CENTRO STORICO") for r in rows)


def test_zone_description_quotes_are_stripped():
    """The export wraps them in single quotes; they would otherwise be rendered."""
    descriptions = omi_import.read_zone_descriptions(ZONE)
    assert not any(d.startswith("'") or d.endswith("'") for d in descriptions.values())


def test_prices_import_without_the_zone_file():
    """Half a delivery still yields every number, just no descriptions."""
    _semester, rows, skipped = omi_import.read_quotations(VALORI)
    assert skipped == 0
    assert len(rows) == FIXTURE_QUOTATIONS
    assert all(r["zone_description"] == "" for r in rows)


# --- acceptance: the fixture imports ----------------------------------------


def test_the_fixture_imports(db, tmp_path):
    result = omi_import.import_quotations(db, _copy_supply(tmp_path))
    assert result["semester"] == "2025/2"
    assert result["imported"] == FIXTURE_QUOTATIONS
    assert result["skipped"] == 0
    assert db.scalar(select(OmiQuotation).where(OmiQuotation.zone_code == "B12")) is not None
    assert len(db.execute(select(OmiQuotation)).scalars().all()) == FIXTURE_QUOTATIONS


def test_reimporting_the_same_semester_leaves_the_row_count_unchanged(db, tmp_path):
    supply = _copy_supply(tmp_path)
    omi_import.import_quotations(db, supply)
    before = len(db.execute(select(OmiQuotation)).scalars().all())
    result = omi_import.import_quotations(db, supply)
    after = db.execute(select(OmiQuotation)).scalars().all()
    assert len(after) == before == FIXTURE_QUOTATIONS
    assert result["replaced"] == FIXTURE_QUOTATIONS


def test_two_semesters_coexist_and_the_newest_wins(db, tmp_path):
    """A re-import replaces its own semester only — the previous one is history
    the app is allowed to keep, and must not be widened into the new band."""
    supply = _copy_supply(tmp_path)
    omi_import.import_quotations(db, supply)

    older = tmp_path / "older"
    older.mkdir()
    text = VALORI.read_text(encoding="utf-8").replace("Semestre 2025/2", "Semestre 2025/1")
    (older / "prices.csv").write_text(text, encoding="utf-8")
    omi_import.import_quotations(db, older)

    assert len(db.execute(select(OmiQuotation)).scalars().all()) == FIXTURE_QUOTATIONS * 2
    assert omi_import.latest_semester(db) == "2025/2"
    found = omi_import.find_quotations(db, "F205", "B12")
    assert found and all(q.semester == "2025/2" for q in found)


def test_semesters_order_numerically_not_as_text():
    assert omi_import.semester_sort_key("2025/2") > omi_import.semester_sort_key("2025/1")
    assert omi_import.semester_sort_key("2025/1") > omi_import.semester_sort_key("2024/2")
    assert omi_import.semester_sort_key("2025/10") > omi_import.semester_sort_key("2025/2")


# --- acceptance: a corrupt row is counted and skipped ------------------------


def test_a_corrupt_row_is_counted_and_skipped_never_fatal(db, tmp_path):
    lines = _data_lines()
    broken = lines[0].replace(";8700;10900;", ";not-a-price;also-not;")
    broken = broken.replace(";25;35;", ";;;")
    supply = _copy_supply(tmp_path, [broken] + lines[1:])

    result = omi_import.import_quotations(db, supply)
    assert result["skipped"] == 1
    assert result["imported"] == (FIXTURE_ROWS - 1) * 2
    assert len(db.execute(select(OmiQuotation)).scalars().all()) == result["imported"]


def test_a_row_missing_its_zone_is_skipped(db, tmp_path):
    lines = _data_lines()
    without_zone = lines[0].replace(";B;B12;", ";B;;")
    supply = _copy_supply(tmp_path, [without_zone] + lines[1:])
    result = omi_import.import_quotations(db, supply)
    assert result["skipped"] == 1
    assert result["imported"] == (FIXTURE_ROWS - 1) * 2


def test_one_unusable_contract_does_not_lose_the_other(tmp_path):
    """A row quoting a sale band and no rent is a row, not a casualty."""
    lines = _data_lines()
    sale_only = lines[0].replace(";L;25;35;L;", ";L;;;L;")
    semester, rows, skipped = omi_import.read_quotations(_written(tmp_path, sale_only))
    assert semester == "2025/2"
    assert skipped == 0
    assert [r["contract"] for r in rows] == ["sale"]


def test_an_inverted_band_is_not_a_band(tmp_path):
    """min above max is corruption, and averaging it later would look sane."""
    lines = _data_lines()
    inverted = lines[0].replace(";8700;10900;", ";10900;8700;")
    _semester, rows, _skipped = omi_import.read_quotations(_written(tmp_path, inverted))
    assert [r["contract"] for r in rows] == ["rent"]


def test_a_zero_price_is_an_empty_cell_wearing_a_number():
    assert omi_import._to_price("0") is None
    assert omi_import._to_price("") is None
    assert omi_import._to_price("-1") is None


# --- refusals that are not "row problems" ------------------------------------


def test_a_file_that_is_not_an_omi_export_is_refused(tmp_path):
    """No semester on line 1 means the file is something else, or truncated —
    that is a refusal, not 40,000 skipped rows and a puzzling '0 imported'."""
    stray = tmp_path / "stray.csv"
    stray.write_text("id;name\n1;something\n", encoding="utf-8")
    with pytest.raises(omi_import.OmiImportError):
        omi_import.read_quotations(stray)


def test_a_directory_with_no_supply_in_it_is_refused(db, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(omi_import.OmiImportError):
        omi_import.import_quotations(db, empty)


def test_a_missing_directory_is_refused(db, tmp_path):
    with pytest.raises(omi_import.OmiImportError):
        omi_import.import_quotations(db, tmp_path / "nope")


def test_no_configured_directory_is_refused_by_name(db):
    """The default is empty and stays empty for anyone who never fetches the
    supply, so this is the message most users would ever see."""
    with pytest.raises(omi_import.OmiImportError) as excinfo:
        omi_import.import_quotations(db, None)
    assert "omi_input_dir" in str(excinfo.value)


# --- how the supply is found -------------------------------------------------


def test_the_two_files_are_told_apart_by_content_not_by_name(tmp_path):
    """Their real names carry the requester's codice fiscale, so nothing in this
    importer may depend on them. Names are deliberately swapped here."""
    directory = tmp_path / "supply"
    directory.mkdir()
    (directory / "zzz.csv").write_text(VALORI.read_text(encoding="utf-8"), encoding="utf-8")
    (directory / "aaa.csv").write_text(ZONE.read_text(encoding="utf-8"), encoding="utf-8")
    valori_path, zone_path = omi_import.resolve_supply(directory)
    assert valori_path.name == "zzz.csv"
    assert zone_path is not None and zone_path.name == "aaa.csv"


def test_the_supply_is_found_in_a_nested_directory(db, tmp_path):
    """The delivery arrives as an archive that extracts into its own folder."""
    nested = tmp_path / "root" / "extracted"
    nested.mkdir(parents=True)
    (nested / "prices.csv").write_text(VALORI.read_text(encoding="utf-8"), encoding="utf-8")
    result = omi_import.import_quotations(db, tmp_path / "root")
    assert result["imported"] == FIXTURE_QUOTATIONS


def test_the_configured_directory_is_used_when_no_path_is_given(db, tmp_path):
    supply = _copy_supply(tmp_path)
    save_settings({"omi_input_dir": str(supply)})
    result = omi_import.import_quotations(db, None)
    assert result["imported"] == FIXTURE_QUOTATIONS


# --- lookup ------------------------------------------------------------------


def test_lookup_returns_nothing_rather_than_failing_when_nothing_is_imported(db):
    """Fail open: no OMI data is 'no OMI benchmark', never a broken page."""
    assert omi_import.latest_semester(db) is None
    assert omi_import.find_quotations(db, "F205", "B12") == []
    assert omi_import.find_quotations(db, "", "") == []


def test_lookup_can_narrow_to_one_contract(db, tmp_path):
    omi_import.import_quotations(db, _copy_supply(tmp_path))
    sale = omi_import.find_quotations(db, "F205", "B12", contract="sale")
    assert sale and all(q.contract == "sale" for q in sale)
    assert omi_import.find_quotations(db, "F205", "ZZ99") == []


# --- the maintenance endpoint ------------------------------------------------


@pytest.fixture
def api():
    """`TestClient` without its context manager, like `test_routes.py`: entering
    it runs the lifespan, which starts the real scheduler and would have the
    suite scanning portals."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    main.app.dependency_overrides[get_db] = override_db
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_the_endpoint_reports_what_landed_and_what_was_skipped(api, tmp_path):
    """A partial import that reported only its successes would be
    indistinguishable from a complete one."""
    lines = _data_lines()
    broken = lines[0].replace(";8700;10900;", ";nope;nope;").replace(";25;35;", ";;;")
    supply = _copy_supply(tmp_path, [broken] + lines[1:])

    resp = api.post("/api/maintenance/omi-import", params={"path": str(supply)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["semester"] == "2025/2"
    assert body["imported"] == (FIXTURE_ROWS - 1) * 2
    assert body["skipped"] == 1


def test_the_endpoint_answers_400_when_the_supply_cannot_be_read(api, tmp_path):
    """An unreadable supply is the user's problem to fix, so it is a 400 with a
    reason — the same shape the geocoder and commute batches use."""
    resp = api.post("/api/maintenance/omi-import", params={"path": str(tmp_path / "nope")})
    assert resp.status_code == 400
    assert "omi_input_dir" in resp.json()["detail"]
