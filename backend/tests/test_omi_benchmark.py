"""Both benchmarks, side by side, never merged (services/omi_benchmark.py).

The quotations here are imported from `fixtures/omi_valori_sample.csv` — real
rows from a real 2025/2 download — so the bands are the ones the Agenzia
actually publishes for Milan's `B12`, including the trap that makes this module
necessary: the zone quotes **Box** at 4.500–6.500 €/m² alongside flats at
8.700–20.000. A benchmark that folded the garages in would read as a plausible
number and be wrong about every apartment in the centre.

The load-bearing test is `test_the_deal_score_is_untouched_by_omi_data`: the
label, the score and the proposal range must come out byte-identical whether or
not a property has OMI figures. OMI records what deeds say and the median what
sellers ask; a score that quietly averaged the two would be meaningless and look
authoritative (invariant 22).
"""

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.database import Base, get_db
from app.models import Listing, OmiQuotation, Property
from app.services import exporter, omi_import
from app.services.deal_score import _score_property, annotate_deal_scores
from app.services.omi_benchmark import (
    ATTRIBUTION,
    STALE_AFTER_MONTHS,
    annotate_omi_benchmark,
    benchmark_reason,
    format_semester,
    is_stale,
    semester_end,
)
from app.services.pricing_stats import annotate_market_position

FIXTURES = Path(__file__).parent / "fixtures"
VALORI = FIXTURES / "omi_valori_sample.csv"
ZONE = FIXTURES / "omi_zone_sample.csv"

SEMESTER = "2025/2"
# What the real fixture quotes for F205/B12, residential rows only: the floor is
# "Abitazioni civili NORMALE" and the ceiling "Abitazioni signorili OTTIMO".
B12_SALE = (8700.0, 20000.0)
B12_RENT = (25.0, 57.0)
# ...and what would leak in if the non-residential rows were kept.
B12_BOX_MIN = 4500.0


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _supply(tmp_path: Path) -> Path:
    directory = tmp_path / "supply"
    directory.mkdir(exist_ok=True)
    (directory / "prices.csv").write_text(VALORI.read_text(encoding="utf-8"), encoding="utf-8")
    (directory / "zones.csv").write_text(ZONE.read_text(encoding="utf-8"), encoding="utf-8")
    return directory


def _imported(db, tmp_path: Path) -> None:
    omi_import.import_quotations(db, _supply(tmp_path))


def _semester(years_back: int = 0) -> str:
    """A semester label relative to today's.

    The fixture's own `2025/2` is a fixed point that drifts further into the past
    every day, and would cross the staleness threshold on its own in mid-2027 —
    turning a green suite red with no change behind it. A test that means
    "current" or "three years old" says so relative to the calendar instead."""
    today = date.today()
    return f"{today.year - years_back}/{1 if today.month <= 6 else 2}"


def _imported_as(db, tmp_path: Path, semester: str) -> None:
    """The same real supply, relabelled to another semester."""
    directory = tmp_path / f"supply-{semester.replace('/', '-')}"
    directory.mkdir(exist_ok=True)
    (directory / "prices.csv").write_text(
        VALORI.read_text(encoding="utf-8").replace(f"Semestre {SEMESTER}", f"Semestre {semester}"),
        encoding="utf-8",
    )
    (directory / "zones.csv").write_text(ZONE.read_text(encoding="utf-8"), encoding="utf-8")
    omi_import.import_quotations(db, directory)


def _property(
    db=None,
    *,
    zone_code="B12",
    municipality_code="F205",
    contract="sale",
    price=1_000_000.0,
    sqm=100.0,
) -> Property:
    prop = Property(
        fingerprint=f"p-{zone_code}-{contract}",
        title="",
        city="milano",
        zone="centro",
        contract=contract,
        current_min_price=price,
        sqm=sqm,
        status="active",
        omi_municipality_code=municipality_code,
        omi_zone_code=zone_code,
    )
    if db is not None:
        db.add(prop)
        db.commit()
    return prop


# --- the band ---------------------------------------------------------------


def test_the_band_is_the_residential_envelope(db, tmp_path):
    """Every residential row of the zone, lowest minimum to highest maximum: the
    app knows neither the OMI tipologia nor the conservation state of an ad, and
    picking one row would be precision this data cannot support."""
    _imported(db, tmp_path)
    prop = _property(db)
    annotate_omi_benchmark(db, [prop])
    assert (prop.omi_min_sqm_price, prop.omi_max_sqm_price) == B12_SALE
    assert prop.omi_semester == SEMESTER


def test_garages_and_shops_are_not_a_benchmark_for_a_flat(db, tmp_path):
    """B12 quotes Box at 4.500–6.500 €/m². Folded in, the floor of the band
    would drop by half and read as a perfectly plausible number."""
    _imported(db, tmp_path)
    box = (
        db.query(OmiQuotation)
        .filter_by(zone_code="B12", property_type="Box", contract="sale")
        .all()
    )
    assert box and min(q.min_sqm_price for q in box) == B12_BOX_MIN
    prop = _property(db)
    annotate_omi_benchmark(db, [prop])
    assert prop.omi_min_sqm_price == B12_SALE[0]


def test_a_type_the_app_has_never_seen_is_left_out(db, tmp_path):
    """An unknown tipologia silently widening a residential band is the failure
    this module exists to avoid, so it is excluded rather than folded in."""
    _imported(db, tmp_path)
    db.add(
        OmiQuotation(
            semester=SEMESTER,
            municipality_code="F205",
            zone_code="B12",
            property_type_code="99",
            property_type="Something the format grew later",
            contract="sale",
            min_sqm_price=1.0,
            max_sqm_price=99_000.0,
        )
    )
    db.commit()
    prop = _property(db)
    annotate_omi_benchmark(db, [prop])
    assert (prop.omi_min_sqm_price, prop.omi_max_sqm_price) == B12_SALE


def test_rent_reads_the_rent_band_and_sale_the_sale_band(db, tmp_path):
    _imported(db, tmp_path)
    sale, rent = _property(db), _property(db, contract="rent", price=2000.0)
    annotate_omi_benchmark(db, [sale, rent])
    assert (sale.omi_min_sqm_price, sale.omi_max_sqm_price) == B12_SALE
    assert (rent.omi_min_sqm_price, rent.omi_max_sqm_price) == B12_RENT


def test_only_the_newest_semester_is_read(db, tmp_path):
    """A band widened with figures of two dates carries no date at all."""
    _imported(db, tmp_path)
    older = tmp_path / "older"
    older.mkdir()
    (older / "prices.csv").write_text(
        VALORI.read_text(encoding="utf-8").replace("Semestre 2025/2", "Semestre 2024/1"),
        encoding="utf-8",
    )
    omi_import.import_quotations(db, older)
    prop = _property(db)
    annotate_omi_benchmark(db, [prop])
    assert prop.omi_semester == SEMESTER
    assert (prop.omi_min_sqm_price, prop.omi_max_sqm_price) == B12_SALE


def test_one_query_covers_a_whole_page(db, tmp_path):
    """The grid annotates fifty cards at once; a lookup per card would be fifty
    round trips for a table with three rows' worth of answers."""
    _imported(db, tmp_path)
    props = [
        _property(db),
        _property(db, zone_code="B13"),
        _property(db, zone_code="ZZ99"),
    ]
    annotate_omi_benchmark(db, props)
    assert props[0].omi_min_sqm_price == B12_SALE[0]
    assert props[1].omi_min_sqm_price == 6700.0  # B13's Abitazioni civili NORMALE
    assert props[2].omi_min_sqm_price is None


# --- fail open ---------------------------------------------------------------


def test_a_property_that_was_never_placed_gets_nothing_and_no_error(db, tmp_path):
    _imported(db, tmp_path)
    unplaced = _property(db, municipality_code="", zone_code="")
    annotate_omi_benchmark(db, [unplaced])
    assert unplaced.omi_min_sqm_price is None
    assert unplaced.omi_semester is None
    assert benchmark_reason(unplaced) is None


def test_no_quotations_imported_is_no_benchmark_never_a_failure(db):
    prop = _property(db)
    annotate_omi_benchmark(db, [prop])
    assert (prop.omi_min_sqm_price, prop.omi_semester) == (None, None)
    annotate_omi_benchmark(db, [])


def test_a_zone_with_only_non_residential_rows_shows_nothing(db):
    db.add(
        OmiQuotation(
            semester=SEMESTER,
            municipality_code="F205",
            zone_code="D99",
            property_type_code="13",
            property_type="Box",
            contract="sale",
            min_sqm_price=4500.0,
            max_sqm_price=6500.0,
        )
    )
    db.commit()
    prop = _property(db, zone_code="D99")
    annotate_omi_benchmark(db, [prop])
    assert prop.omi_min_sqm_price is None


def test_a_second_pass_clears_what_no_longer_applies(db, tmp_path):
    """Annotation is request-scoped; a stale figure surviving a re-annotation
    would be a benchmark for a zone the property is no longer in."""
    _imported(db, tmp_path)
    prop = _property(db)
    annotate_omi_benchmark(db, [prop])
    prop.omi_municipality_code = ""
    prop.omi_zone_code = ""
    annotate_omi_benchmark(db, [prop])
    assert prop.omi_min_sqm_price is None


# --- the two are never merged (invariant 22) ---------------------------------


def _scored(delta: float | None, band: tuple[float, float] | None) -> Property:
    prop = _property()
    prop.sqm_price_delta_pct = delta
    prop.area_median_scope = "zone"
    prop.area_median_sqm_price = 9000.0 if delta is not None else None
    prop.listings = [Listing(portal="immobiliare", portal_id="1", url="u", description="")]
    if band is not None:
        prop.omi_min_sqm_price, prop.omi_max_sqm_price = band
        prop.omi_semester = SEMESTER
    _score_property(prop, {})
    return prop


def test_the_deal_score_is_untouched_by_omi_data():
    """Acceptance: the label of a property with no OMI data is what it was before
    this feature existed — so the same property *with* it must score identically.
    The OMI figures buy one extra reason line and nothing else."""
    without = _scored(-16, None)
    with_omi = _scored(-16, B12_SALE)
    assert (without.deal_score, without.deal_label) == (with_omi.deal_score, with_omi.deal_label)
    assert without.target_price_low == with_omi.target_price_low
    assert without.target_price_high == with_omi.target_price_high
    assert without.expected_discount_pct == with_omi.expected_discount_pct
    extra = [r for r in with_omi.deal_reasons or [] if r not in (without.deal_reasons or [])]
    assert len(extra) == 1 and extra[0].startswith("OMI recorded sales")


def test_the_omi_figures_never_replace_the_listing_median():
    """The other half of the same rule: with OMI data present, the median-derived
    fields still describe the median."""
    prop = _scored(-16, B12_SALE)
    assert prop.area_median_sqm_price == 9000.0
    assert prop.sqm_price_delta_pct == -16
    assert prop.omi_min_sqm_price == B12_SALE[0]


def test_a_property_with_no_median_gets_no_score_even_with_omi_data():
    """OMI is not a fallback anchor: without comparables there is no score, and a
    band that quietly became one would be a different measurement wearing the
    same badge."""
    prop = _scored(None, B12_SALE)
    assert prop.deal_score is None
    assert prop.deal_label is None
    assert prop.deal_reasons == []


def test_the_reason_line_says_what_it_is_when_and_whose_it_is(db, tmp_path):
    """Every element in one string: the measurement, the band, the date it
    covers, and the credit the licence requires. Asserted whole, because each of
    the four has been the thing a rendering quietly dropped."""
    current = _semester()
    _imported_as(db, tmp_path, current)
    prop = _property(db)
    annotate_omi_benchmark(db, [prop])
    assert benchmark_reason(prop) == (
        f"OMI recorded sales in this zone: 8.700–20.000 €/sqm "
        f"({format_semester(current)}) · Fonte: Agenzia Entrate – OMI"
    )


def test_the_rent_reason_line_says_per_month(db, tmp_path):
    """OMI quotes rent as €/m² a *month*; the same number without that word is an
    absurdity nobody would question."""
    _imported(db, tmp_path)
    prop = _property(db, contract="rent", price=2000.0)
    annotate_omi_benchmark(db, [prop])
    line = benchmark_reason(prop) or ""
    assert line.startswith("OMI recorded rents in this zone: 25–57 €/sqm per month")


# --- ageing honestly: the date, the staleness, the credit -------------------


def test_a_semester_ends_when_its_own_half_ends():
    """Age is measured from the end of the window the label names, not from the
    import: a 2023/2 supply loaded this morning still describes 2023."""
    assert semester_end("2025/1") == date(2025, 6, 30)
    assert semester_end("2025/2") == date(2025, 12, 31)
    assert semester_end("later") is None


def test_a_band_goes_stale_eighteen_months_after_its_window_closes():
    """The boundary itself, from both sides. `2025/2` closes on 2025-12-31, so it
    is still current at eighteen months and stale the day after."""
    assert not is_stale("2025/2", today=date(2027, 6, 30))
    assert is_stale("2025/2", today=date(2027, 7, 1))


def test_figures_published_this_semester_are_never_stale():
    assert not is_stale("2026/1", today=date(2026, 8, 29))
    # ...including one whose window has not closed yet.
    assert not is_stale("2026/2", today=date(2026, 8, 29))


def test_a_label_the_app_cannot_read_is_not_called_stale():
    """`format_semester` still prints it, so the figure keeps the date the import
    recorded; inventing an age for a date we cannot parse would be a firmer claim
    than the data supports."""
    assert not is_stale("later")
    assert not is_stale("")
    assert not is_stale(None)


def test_a_three_year_old_supply_is_marked_stale(db, tmp_path):
    """Acceptance: old data is labelled, not silently trusted — and not withheld
    either, since the band is still the only recorded evidence there is."""
    old = _semester(years_back=3)
    _imported_as(db, tmp_path, old)
    prop = _property(db)
    annotate_omi_benchmark(db, [prop])
    assert prop.omi_stale is True
    assert (prop.omi_min_sqm_price, prop.omi_max_sqm_price) == B12_SALE
    line = benchmark_reason(prop) or ""
    assert f"over {STALE_AFTER_MONTHS} months old" in line


def test_a_current_supply_is_not_marked_stale(db, tmp_path):
    _imported_as(db, tmp_path, _semester())
    prop = _property(db)
    annotate_omi_benchmark(db, [prop])
    assert prop.omi_stale is False
    assert f"over {STALE_AFTER_MONTHS} months old" not in (benchmark_reason(prop) or "")


def test_a_second_pass_clears_a_stale_flag_that_no_longer_applies(db, tmp_path):
    """The flag is request-scoped like the band it describes; left behind, it
    would age a property that is no longer in an OMI zone at all."""
    _imported_as(db, tmp_path, _semester(years_back=3))
    prop = _property(db)
    annotate_omi_benchmark(db, [prop])
    assert prop.omi_stale is True
    prop.omi_zone_code = ""
    annotate_omi_benchmark(db, [prop])
    assert prop.omi_stale is False


def test_the_rent_reason_line_is_credited_too(db, tmp_path):
    """The licence does not care which band it is."""
    _imported(db, tmp_path)
    prop = _property(db, contract="rent", price=2000.0)
    annotate_omi_benchmark(db, [prop])
    assert (benchmark_reason(prop) or "").endswith(ATTRIBUTION)


def test_the_grid_serves_the_staleness_it_computed(api, tmp_path):
    """Served, not derived on the client: the screen and the print dossier have
    to age the same band the same way, so the threshold lives in one place."""
    _imported_as(api.session, tmp_path, _semester(years_back=3))
    _property(api.session)
    item = api.get("/api/properties").json()["items"][0]
    assert item["omi_stale"] is True
    assert item["omi_semester"] == _semester(years_back=3)


def test_a_property_with_no_band_is_not_stale_on_the_wire(api, tmp_path):
    """Absent data is not old data: a card with no band must not sprout a
    staleness warning about nothing."""
    _imported(api.session, tmp_path)
    _property(api.session, municipality_code="", zone_code="")
    item = api.get("/api/properties").json()["items"][0]
    assert item["omi_min_sqm_price"] is None
    assert item["omi_stale"] is False


def test_the_dossier_credits_the_agenzia_when_it_prints_a_band(db, tmp_path):
    """The printed page leaves the app entirely, so it carries its own credit."""
    _imported(db, tmp_path)
    prop = _property(db)
    annotate_omi_benchmark(db, [prop])
    assert ATTRIBUTION in exporter.properties_to_print_html([prop], "Shortlist")


def test_the_dossier_credits_nobody_when_no_band_reached_the_page(db):
    """An attribution on a dossier with no OMI figures on it credits a source the
    document never used."""
    prop = _property(db)
    prop.area_median_sqm_price = 9000.0
    prop.area_median_scope = "zone"
    assert ATTRIBUTION not in exporter.properties_to_print_html([prop], "Shortlist")


def test_the_dossier_says_when_the_band_it_prints_is_out_of_date(db, tmp_path):
    _imported_as(db, tmp_path, _semester(years_back=3))
    prop = _property(db)
    annotate_omi_benchmark(db, [prop])
    html = exporter.properties_to_print_html([prop], "Shortlist")
    assert f"over {STALE_AFTER_MONTHS} months old" in html


def test_a_semester_reads_as_a_date():
    assert format_semester("2025/2") == "2nd half 2025"
    assert format_semester("2026/1") == "1st half 2026"
    # A label the app cannot parse is still the label the import recorded:
    # dropping it would leave the figure undated.
    assert format_semester("later") == "later"
    assert format_semester("") == ""


# --- what reaches the screen and the dossier ---------------------------------


def test_the_dossier_prints_both_benchmarks_each_labelled(db, tmp_path):
    _imported(db, tmp_path)
    prop = _property(db)
    prop.area_median_sqm_price = 9000.0
    prop.area_median_scope = "zone"
    prop.sqm_price_delta_pct = 11.1
    annotate_omi_benchmark(db, [prop])
    html = exporter.properties_to_print_html([prop], "Shortlist")
    assert "Similar listings ask" in html
    assert "Recorded sales (OMI)" in html
    assert "8.700–20.000 €/sqm" in html
    assert "2nd half 2025" in html


def test_the_dossier_shows_the_median_alone_when_there_is_no_omi_data(db):
    prop = _property(db)
    prop.area_median_sqm_price = 9000.0
    prop.area_median_scope = "zone"
    html = exporter.properties_to_print_html([prop], "Shortlist")
    assert "Similar listings ask" in html
    assert "OMI" not in html


@pytest.fixture
def api():
    """`TestClient` without its context manager, like the OMI tests next door:
    entering it runs the lifespan, which starts the real scheduler."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()

    def override_db():
        yield session

    main.app.dependency_overrides[get_db] = override_db
    client = TestClient(main.app)
    setattr(client, "session", session)
    yield client
    main.app.dependency_overrides.clear()
    session.close()


def test_the_grid_serves_both_figures(api, tmp_path):
    _imported(api.session, tmp_path)
    _property(api.session)
    body = api.get("/api/properties").json()
    assert body["items"][0]["omi_min_sqm_price"] == B12_SALE[0]
    assert body["items"][0]["omi_max_sqm_price"] == B12_SALE[1]
    assert body["items"][0]["omi_semester"] == SEMESTER
    assert body["items"][0]["omi_zone_code"] == "B12"


def test_a_property_outside_any_imported_zone_serves_nulls(api, tmp_path):
    """Fail open all the way to the wire: the card shows the median alone."""
    _imported(api.session, tmp_path)
    _property(api.session, municipality_code="", zone_code="")
    item = api.get("/api/properties").json()["items"][0]
    assert item["omi_min_sqm_price"] is None
    assert item["omi_semester"] is None


def test_the_scan_notification_path_needs_no_omi_lookup(db, tmp_path):
    """`scanner` annotates the market position and the deal score for the alert
    it is about to send, and the alert carries the label only — so the OMI
    lookup is deliberately not on that path, and the score must still come out."""
    _imported(db, tmp_path)
    prop = _property(db, price=700_000.0)
    annotate_market_position(db, [prop])
    annotate_deal_scores(db, [prop])
    assert prop.omi_min_sqm_price is None
    assert benchmark_reason(prop) is None
