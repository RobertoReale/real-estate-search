"""Opt-in geocoding backfill for the map. All offline: the Nominatim HTTP call
(`_nominatim_lookup`) is mocked, so the cache/batch/fail-open logic is exercised
with no network and no per-second wait."""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import GeocodeCache, Property
from app.services import geocoder


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch):
    # never actually pause a test for Nominatim's 1 req/sec policy
    monkeypatch.setattr(geocoder, "PACE_SECONDS", 0)


def _prop(**kw) -> Property:
    base = dict(fingerprint="fp", city="Milano", contract="sale")
    base.update(kw)
    return Property(**base)


def test_geocodes_a_property_with_an_address(db, monkeypatch):
    db.add(_prop(address="Via Dante 5", zone="Centro"))
    db.commit()
    monkeypatch.setattr(geocoder, "_nominatim_lookup", lambda q, base: (45.46, 9.19))

    summary = geocoder.geocode_missing_properties(db)
    assert summary["geocoded"] == 1
    prop = db.scalars(select(Property)).one()
    assert prop.latitude == 45.46 and prop.longitude == 9.19


def test_uses_zone_when_no_street_and_anchors_to_the_city(db, monkeypatch):
    db.add(_prop(address="", zone="Navigli"))
    db.commit()
    seen = {}
    monkeypatch.setattr(geocoder, "_nominatim_lookup",
                        lambda q, base: seen.setdefault("q", q) and None or (45.4, 9.1))
    # capture the query string properly
    def cap(q, base):
        seen["q"] = q
        return (45.4, 9.1)
    monkeypatch.setattr(geocoder, "_nominatim_lookup", cap)

    geocoder.geocode_missing_properties(db)
    assert seen["q"] == "Navigli, Milano, Italia"


def test_a_property_with_only_a_city_is_skipped(db, monkeypatch):
    # a bare city would drop every such listing on one downtown pin — never geocode it
    db.add(_prop(address="", zone=""))
    db.commit()
    called = {"n": 0}
    monkeypatch.setattr(geocoder, "_nominatim_lookup",
                        lambda q, base: called.update(n=called["n"] + 1) or (1, 1))

    summary = geocoder.geocode_missing_properties(db)
    assert called["n"] == 0 and summary["scanned"] == 0


def test_cache_hit_skips_the_network(db, monkeypatch):
    db.add(_prop(address="Via Dante 5"))
    db.add(GeocodeCache(query="via dante 5, milano, italia",
                        latitude=45.1, longitude=9.2))
    db.commit()

    def boom(q, base):
        raise AssertionError("must not hit the network on a cache hit")

    monkeypatch.setattr(geocoder, "_nominatim_lookup", boom)
    summary = geocoder.geocode_missing_properties(db)
    assert summary["cached"] == 1 and summary["geocoded"] == 1
    assert db.scalars(select(Property)).one().latitude == 45.1


def test_a_miss_is_cached_negatively_and_not_retried(db, monkeypatch):
    db.add(_prop(address="Nowhere Street"))
    db.commit()
    calls = {"n": 0}

    def miss(q, base):
        calls["n"] += 1
        return None

    monkeypatch.setattr(geocoder, "_nominatim_lookup", miss)
    geocoder.geocode_missing_properties(db)
    geocoder.geocode_missing_properties(db)  # second run must reuse the negative cache
    assert calls["n"] == 1
    row = db.scalars(select(GeocodeCache)).one()
    assert row.latitude is None  # negative result stored on purpose


def test_a_transient_error_leaves_coords_untouched_and_is_not_cached(db, monkeypatch):
    prop = _prop(address="Via Roma 1")
    db.add(prop)
    db.commit()

    def boom(q, base):
        raise ConnectionError("nominatim down")

    monkeypatch.setattr(geocoder, "_nominatim_lookup", boom)
    summary = geocoder.geocode_missing_properties(db)
    assert summary["not_found"] == 1
    prop = db.scalars(select(Property)).one()
    assert prop.latitude is None  # fail-open: never a wrong pin
    # a transient failure is NOT cached, so a later batch can retry
    assert db.scalars(select(GeocodeCache)).first() is None


def test_the_budget_caps_network_calls_and_reports_remaining(db, monkeypatch):
    monkeypatch.setattr(geocoder, "MAX_PER_CALL", 2)
    for i in range(5):
        db.add(_prop(fingerprint=f"fp{i}", address=f"Via Test {i}"))
    db.commit()
    monkeypatch.setattr(geocoder, "_nominatim_lookup", lambda q, base: (45.0, 9.0))

    summary = geocoder.geocode_missing_properties(db)
    assert summary["geocoded"] == 2
    assert summary["remaining"] == 3


def test_max_calls_none_processes_all_candidates(db, monkeypatch):
    monkeypatch.setattr(geocoder, "MAX_PER_CALL", 2)
    for i in range(5):
        db.add(_prop(fingerprint=f"fp{i}", address=f"Via Test {i}"))
    db.commit()
    monkeypatch.setattr(geocoder, "_nominatim_lookup", lambda q, base: (45.0, 9.0))

    summary = geocoder.geocode_missing_properties(db, max_calls=None)
    assert summary["geocoded"] == 5
    assert summary["remaining"] == 0
    assert not summary.get("cancelled")


def test_cancellation_stops_batch(db, monkeypatch):
    for i in range(5):
        db.add(_prop(fingerprint=f"fp{i}", address=f"Via Test {i}"))
    db.commit()

    def lookup_and_cancel(q, base):
        if "test 1" in q.lower():
            geocoder.request_cancel()
        return (45.0, 9.0)

    monkeypatch.setattr(geocoder, "_nominatim_lookup", lookup_and_cancel)
    summary = geocoder.geocode_missing_properties(db, max_calls=None)
    assert summary["geocoded"] == 2
    assert summary["cancelled"] is True
    assert summary["remaining"] == 3


def test_concurrent_run_raises_geocoder_error(db):
    assert geocoder._geocode_run_lock.acquire(blocking=False)
    try:
        with pytest.raises(geocoder.GeocoderError):
            geocoder.geocode_missing_properties(db)
    finally:
        geocoder._geocode_run_lock.release()


def test_geocode_endpoints_directly(db, monkeypatch):
    from app.main import geocode_cancel_endpoint, geocode_missing_endpoint, geocode_progress_endpoint

    prog = geocode_progress_endpoint()
    assert prog["active"] is False

    res_cancel = geocode_cancel_endpoint()
    assert res_cancel == {"ok": True}
    assert geocoder._geocode_cancel_event.is_set()

    # test endpoint triggers geocode_missing_properties
    for i in range(2):
        db.add(_prop(fingerprint=f"fp{i}", address=f"Via Test {i}"))
    db.commit()
    monkeypatch.setattr(geocoder, "_nominatim_lookup", lambda q, base: (45.0, 9.0))
    summary = geocode_missing_endpoint(db)
    assert summary["geocoded"] == 2


def test_clean_street_name():
    assert geocoder._clean_street_name("Via Tolmezzo, 2") == "Via Tolmezzo"
    assert geocoder._clean_street_name("Via Dante Alighieri 15/B - piano 3") == "Via Dante Alighieri"
    assert geocoder._clean_street_name("Corso Buenos Aires 45") == "Corso Buenos Aires"
    assert geocoder._clean_street_name("Via 24 Maggio") == "Via 24 Maggio"
    assert geocoder._clean_street_name("Viale 25 Aprile 12") == "Viale 25 Aprile"
    assert geocoder._clean_street_name("Piazza 5 Giornate, 10") == "Piazza 5 Giornate"


def test_is_valid_coordinate_for_city():
    # Milano center is valid
    assert geocoder.is_valid_coordinate_for_city(45.464, 9.190, "Milano") is True
    # Cernusco sul Naviglio (9.333) and Torino (7.68) are outside Milano bounding box
    assert geocoder.is_valid_coordinate_for_city(45.524, 9.333, "Milano") is False
    assert geocoder.is_valid_coordinate_for_city(45.070, 7.680, "Milano") is False


def test_is_in_city_validation():
    # Cernusco sul Naviglio or Torino must be rejected when Milano is requested
    cernusco_addr = {"road": "Via Tolmezzo", "house_number": "2", "town": "Cernusco sul Naviglio", "county": "Milano"}
    torino_addr = {"suburb": "Dergano", "city": "Torino"}
    milano_addr = {"road": "Via Tolmezzo", "suburb": "Feltre", "city": "Milano"}
    assert geocoder._is_in_city(cernusco_addr, "Milano") is False
    assert geocoder._is_in_city(torino_addr, "Milano") is False
    assert geocoder._is_in_city(milano_addr, "Milano") is True


def test_build_queries_fallback_order():
    prop = _prop(address="Via Tolmezzo, 2", zone="Udine", city="Milano")
    queries = geocoder.build_queries(prop)
    assert queries == [
        "Via Tolmezzo, 2, Milano, Italia",
        "Via Tolmezzo, Milano, Italia",
        "Udine, Milano, Italia",
    ]


def test_geocode_missing_properties_clears_out_of_bounds_existing_pins(db, monkeypatch):
    # A property originally geocoded wrongly to Cernusco sul Naviglio (45.524, 9.333)
    prop = _prop(address="Via Tolmezzo, 2", zone="Udine", city="Milano", latitude=45.524, longitude=9.333)
    db.add(prop)
    db.commit()

    # Mock lookup returning valid Milano coordinates on re-run
    monkeypatch.setattr(geocoder, "_nominatim_lookup", lambda q, base, **kw: (45.49, 9.23))
    summary = geocoder.geocode_missing_properties(db)
    assert summary["geocoded"] == 1
    db.refresh(prop)
    assert prop.latitude == 45.49 and prop.longitude == 9.23

