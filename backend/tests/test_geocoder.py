"""Opt-in geocoding backfill for the map. All offline: the Nominatim HTTP call
(`_nominatim_lookup`) is mocked, so the cache/batch/fail-open logic is exercised
with no network and no per-second wait."""

import pytest
from sqlalchemy import create_engine, func, select
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
    monkeypatch.setattr(
        geocoder,
        "_nominatim_lookup",
        lambda q, base: seen.setdefault("q", q) and None or (45.4, 9.1),
    )

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
    monkeypatch.setattr(
        geocoder, "_nominatim_lookup", lambda q, base: called.update(n=called["n"] + 1) or (1, 1)
    )

    summary = geocoder.geocode_missing_properties(db)
    assert called["n"] == 0 and summary["scanned"] == 0


def test_cache_hit_skips_the_network(db, monkeypatch):
    db.add(_prop(address="Via Dante 5"))
    db.add(GeocodeCache(query="via dante 5, milano, italia", latitude=45.46, longitude=9.19))
    db.commit()

    def boom(q, base):
        raise AssertionError("must not hit the network on a cache hit")

    monkeypatch.setattr(geocoder, "_nominatim_lookup", boom)
    summary = geocoder.geocode_missing_properties(db)
    assert summary["cached"] == 1 and summary["geocoded"] == 1
    assert db.scalars(select(Property)).one().latitude == 45.46


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
    from app.routers.maintenance import (
        geocode_cancel_endpoint,
        geocode_missing_endpoint,
        geocode_progress_endpoint,
    )

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


def test_geocode_property_resolves_a_single_property_on_demand(db, monkeypatch):
    # Backs the card's "View on map" button: one property, filled in place.
    prop = _prop(address="Via Dante 5")
    db.add(prop)
    db.commit()
    monkeypatch.setattr(geocoder, "_nominatim_lookup", lambda q, base: (45.46, 9.19))
    coords = geocoder.geocode_property(db, prop)
    assert coords == (45.46, 9.19)
    assert prop.latitude == 45.46 and prop.longitude == 9.19


def test_geocode_property_fails_open_when_unresolved(db, monkeypatch):
    # An address too vague to place leaves the property un-pinned, never wrong.
    prop = _prop(address="Nowhere Street")
    db.add(prop)
    db.commit()
    monkeypatch.setattr(geocoder, "_nominatim_lookup", lambda q, base: None)
    assert geocoder.geocode_property(db, prop) is None
    assert prop.latitude is None and prop.longitude is None


def test_geocode_property_retries_a_stale_negative_cache(db, monkeypatch):
    # A transient empty answer from Nominatim gets frozen as a NULL cache row
    # (real case: "Viale Mario Rapisardi, 15, Milano" — a perfectly resolvable
    # address stuck behind a stale miss). The paced batch respects that cache to
    # stay under the rate limit, but the on-demand single-property path spends
    # at most a couple of requests, so it must re-ask instead of stranding the
    # property off the map forever.
    prop = _prop(address="Viale Mario Rapisardi, 15")
    db.add(prop)
    db.commit()
    # Seed the poisoned negative-cache rows for every query the property builds.
    for query in geocoder.build_queries(prop):
        db.add(GeocodeCache(query=geocoder._normalize(query), latitude=None, longitude=None))
    db.commit()

    # The batch stays blind to it (default respects the negative cache)...
    monkeypatch.setattr(geocoder, "_nominatim_lookup", lambda q, base: (45.52, 9.17))
    assert geocoder.geocode(db, geocoder.build_query(prop), "http://x", "Milano") is None

    # ...but the on-demand path retries and resolves it.
    coords = geocoder.geocode_property(db, prop)
    assert coords == (45.52, 9.17)
    assert prop.latitude == 45.52 and prop.longitude == 9.17


def test_clear_geocode_cache_drops_only_misses_by_default(db):
    # The maintenance "Retry failed lookups" button: forget the stuck NULL rows
    # so the paced batch re-queries them, but keep the positive lookups we
    # already paid for under the rate limit.
    db.add(GeocodeCache(query="via good, milano, italia", latitude=45.4, longitude=9.1))
    db.add(GeocodeCache(query="via bad, milano, italia", latitude=None, longitude=None))
    db.add(GeocodeCache(query="via worse, milano, italia", latitude=None, longitude=None))
    db.commit()

    cleared = geocoder.clear_geocode_cache(db)
    assert cleared == 2
    remaining = db.scalars(select(GeocodeCache)).all()
    assert [r.query for r in remaining] == ["via good, milano, italia"]

    # misses_only=False wipes everything, positive rows included.
    assert geocoder.clear_geocode_cache(db, misses_only=False) == 1
    assert db.scalars(select(GeocodeCache)).all() == []


def test_geocode_clear_cache_endpoint(db):
    from app.routers.maintenance import geocode_clear_cache_endpoint

    db.add(GeocodeCache(query="via bad, milano, italia", latitude=None, longitude=None))
    db.commit()
    assert geocode_clear_cache_endpoint(db) == {"cleared": 1}


def test_geocode_property_stops_and_fails_open_on_a_block(db, monkeypatch):
    # A 429/403 from Nominatim must not become a wrong pin, and must stop the
    # per-query loop rather than hammer the blocked host.
    import urllib.error

    prop = _prop(address="Via Roma 1", zone="Centro")
    db.add(prop)
    db.commit()

    def blocked(q, base):
        raise urllib.error.HTTPError("x", 429, "rate limited", None, None)  # type: ignore[arg-type]

    monkeypatch.setattr(geocoder, "_nominatim_lookup", blocked)
    assert geocoder.geocode_property(db, prop) is None
    assert prop.latitude is None


def test_geocode_single_property_endpoint(db, monkeypatch):
    from app.routers.properties import geocode_single_property

    prop = _prop(address="Via Dante 5")
    db.add(prop)
    db.commit()
    monkeypatch.setattr(geocoder, "_nominatim_lookup", lambda q, base: (45.46, 9.19))
    res = geocode_single_property(prop.id, db)
    assert res["located"] is True
    assert res["property"]["latitude"] == 45.46


def test_geocode_single_property_endpoint_already_located_skips_network(db, monkeypatch):
    from app.routers.properties import geocode_single_property

    prop = _prop(address="Via Dante 5", latitude=45.46, longitude=9.19)
    db.add(prop)
    db.commit()

    def boom(q, base):
        raise AssertionError("a located property must not hit the network")

    monkeypatch.setattr(geocoder, "_nominatim_lookup", boom)
    res = geocode_single_property(prop.id, db)
    assert res["located"] is True


def test_clean_street_name():
    assert geocoder._clean_street_name("Via Tolmezzo, 2") == "Via Tolmezzo"
    assert (
        geocoder._clean_street_name("Via Dante Alighieri 15/B - piano 3") == "Via Dante Alighieri"
    )
    assert geocoder._clean_street_name("Corso Buenos Aires 45") == "Corso Buenos Aires"
    assert geocoder._clean_street_name("Via 24 Maggio") == "Via 24 Maggio"
    assert geocoder._clean_street_name("Viale 25 Aprile 12") == "Viale 25 Aprile"
    assert geocoder._clean_street_name("Piazza 5 Giornate, 10") == "Piazza 5 Giornate"
    # "s.n.c" = "senza numero civico": agencies write it where a house number
    # goes, and Nominatim returns 0 results for "Via Camaldoli s.n.c" while
    # "Via Camaldoli" resolves — so the fallback query must strip it.
    assert geocoder._clean_street_name("Via Camaldoli s.n.c, Ponte Lambro") == "Via Camaldoli"
    assert geocoder._clean_street_name("Via Camaldoli snc") == "Via Camaldoli"
    assert geocoder._clean_street_name("Via Camaldoli s.n.c.") == "Via Camaldoli"


def test_snc_address_falls_back_to_the_bare_street(db, monkeypatch):
    # The real "Via Camaldoli s.n.c, Ponte Lambro" case: the first query keeps
    # "s.n.c" and misses, but the cleaned fallback "Via Camaldoli, Milano" hits.
    prop = _prop(address="Via Camaldoli s.n.c, Ponte Lambro", zone="")
    db.add(prop)
    db.commit()
    resolved = {"Via Camaldoli, Milano, Italia": (45.4414, 9.2660)}
    monkeypatch.setattr(geocoder, "_nominatim_lookup", lambda q, base: resolved.get(q))
    coords = geocoder.geocode_property(db, prop)
    assert coords == (45.4414, 9.2660)
    assert prop.latitude == 45.4414


def test_is_valid_coordinate_for_city():
    # Milano center is valid
    assert geocoder.is_valid_coordinate_for_city(45.464, 9.190, "Milano") is True
    # Cernusco sul Naviglio (9.333) and Torino (7.68) are outside Milano bounding box
    assert geocoder.is_valid_coordinate_for_city(45.524, 9.333, "Milano") is False
    assert geocoder.is_valid_coordinate_for_city(45.070, 7.680, "Milano") is False


def test_is_in_city_validation():
    # Cernusco sul Naviglio or Torino must be rejected when Milano is requested
    cernusco_addr = {
        "road": "Via Tolmezzo",
        "house_number": "2",
        "town": "Cernusco sul Naviglio",
        "county": "Milano",
    }
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


def test_each_query_carries_the_precision_it_would_buy():
    # The fallback to the zone was always there; what was missing is that a pin
    # resolved from it is a district and not a doorstep.
    prop = _prop(address="Via Tolmezzo, 2", zone="Udine", city="Milano")
    assert geocoder.build_located_queries(prop) == [
        ("Via Tolmezzo, 2, Milano, Italia", geocoder.SOURCE_ADDRESS),
        ("Via Tolmezzo, Milano, Italia", geocoder.SOURCE_ADDRESS),
        ("Udine, Milano, Italia", geocoder.SOURCE_ZONE),
    ]


def test_a_pin_records_where_it_came_from(db, monkeypatch):
    street = _prop(fingerprint="a", address="Via Dante 5", zone="Centro")
    district = _prop(fingerprint="b", address="", zone="Navigli")
    db.add_all([street, district])
    db.commit()
    resolved = {
        "Via Dante 5, Milano, Italia": (45.4660, 9.1900),
        "Navigli, Milano, Italia": (45.4520, 9.1750),
    }
    monkeypatch.setattr(geocoder, "_nominatim_lookup", lambda q, base, **kw: resolved.get(q))

    summary = geocoder.geocode_missing_properties(db)
    assert summary["geocoded"] == 2
    # One of the two is an address and one is a district: the batch says which.
    assert summary["approximate"] == 1
    assert street.coordinate_source == geocoder.SOURCE_ADDRESS
    assert district.coordinate_source == geocoder.SOURCE_ZONE
    assert geocoder.is_approximate(street.coordinate_source) is False
    assert geocoder.is_approximate(district.coordinate_source) is True


def test_an_unknown_source_is_not_called_approximate():
    # Every pin in an upgraded database has an empty source. Labelling those as
    # approximations would put a warning on the whole map on the first run after
    # the upgrade, for pins that are very probably exact.
    assert geocoder.is_approximate("") is False
    assert geocoder.is_approximate(None) is False


# --- Layer 2: what this database can already answer, with no network ---------


def test_offline_resolution_reuses_a_lookup_already_paid_for(db):
    # The whole point of the cache being keyed by query string: one property's
    # street answers every other property on it, for nothing.
    db.add(_prop(fingerprint="a", address="Via dei Tigli 4", zone="Isola"))
    db.add(_prop(fingerprint="b", address="Via dei Tigli 9", zone="Isola"))
    db.add(GeocodeCache(query="via dei tigli, milano, italia", latitude=45.487, longitude=9.188))
    db.commit()

    summary = geocoder.resolve_offline(db)
    assert summary["placed"] == 2 and summary["exact"] == 2
    for prop in db.scalars(select(Property)):
        assert prop.latitude == 45.487
        assert prop.coordinate_source == geocoder.SOURCE_ADDRESS


def test_offline_resolution_places_a_listing_inside_its_own_district(db):
    # No cache at all, but the district already holds pins the portal sent. Their
    # middle is somewhere in the right area, and is labelled as exactly that.
    db.add(
        _prop(fingerprint="a", zone="Isola", latitude=45.486, longitude=9.186, address="Via A 1")
    )
    db.add(
        _prop(fingerprint="b", zone="Isola", latitude=45.490, longitude=9.190, address="Via B 2")
    )
    db.add(_prop(fingerprint="c", zone="Isola", address="Via Sconosciuta 3"))
    db.commit()

    summary = geocoder.resolve_offline(db)
    assert summary["placed"] == 1 and summary["approximate"] == 1
    placed = db.scalar(select(Property).where(Property.fingerprint == "c"))
    assert placed is not None
    assert placed.coordinate_source == geocoder.SOURCE_ZONE
    assert placed.latitude == pytest.approx(45.488)
    assert placed.longitude == pytest.approx(9.188)
    # ...and it lands on neither of the two real addresses, so it can never be
    # read as one of them (geocoder.ZONE_CENTRE_MIN_PINS explains why).
    assert placed.latitude not in (45.486, 45.490)


def test_one_pin_is_not_a_district_centre(db):
    # With a single pin the "centre" would sit exactly on a real address and be
    # read as one, which is the confusion coordinate_source exists to prevent.
    db.add(
        _prop(fingerprint="a", zone="Isola", latitude=45.486, longitude=9.186, address="Via A 1")
    )
    db.add(_prop(fingerprint="b", zone="Isola", address="Via Sconosciuta 3"))
    db.commit()

    assert geocoder.resolve_offline(db)["placed"] == 0
    lonely = db.scalar(select(Property).where(Property.fingerprint == "b"))
    assert lonely is not None and lonely.latitude is None


def test_an_approximate_pin_never_becomes_another_districts_centre(db):
    # A centroid averaged out of centroids drifts, and there is no way back to a
    # real coordinate once it has. Only exact pins define a district.
    db.add(
        _prop(
            fingerprint="a",
            zone="Isola",
            latitude=45.486,
            longitude=9.186,
            coordinate_source=geocoder.SOURCE_ZONE,
        )
    )
    db.add(
        _prop(
            fingerprint="b",
            zone="Isola",
            latitude=45.490,
            longitude=9.190,
            coordinate_source=geocoder.SOURCE_ZONE,
        )
    )
    db.commit()
    assert geocoder._zone_centres(db) == {}


def test_what_this_pass_cannot_place_is_left_for_the_network(db, monkeypatch):
    """The ordering that makes the whole design work.

    Nothing cached, no district pins: the honest answer here is *no pin*, so the
    paced lookup that can find the real address still has a candidate when it
    runs. A comune-wide fallback would have placed this on Milano's centre and
    starved the layer that could have got it right — which is also why
    `geocode_missing_properties` has always refused a property with only a city.
    """
    db.add(_prop(fingerprint="a", city="Milano", address="Via Ignota 1", zone=""))
    db.commit()

    assert geocoder.resolve_offline(db)["placed"] == 0
    assert db.scalars(select(Property)).one().latitude is None

    monkeypatch.setattr(geocoder, "_nominatim_lookup", lambda q, base, **kw: (45.47, 9.19))
    assert geocoder.geocode_missing_properties(db)["geocoded"] == 1
    prop = db.scalars(select(Property)).one()
    assert prop.coordinate_source == geocoder.SOURCE_ADDRESS


def test_offline_resolution_leaves_a_placeless_property_alone(db):
    # No city means no comune, no district and no query: nothing can be said, so
    # nothing is written. Fail-open, like every other path in this module.
    db.add(_prop(fingerprint="a", city="", address="Via Ignota 1"))
    db.commit()

    assert geocoder.resolve_offline(db)["placed"] == 0
    assert db.scalars(select(Property)).one().latitude is None


def test_offline_resolution_writes_no_cache_row_and_opens_no_socket(db, monkeypatch):
    db.add(_prop(fingerprint="a", address="Via Ignota 1", zone="Isola"))
    db.commit()

    def boom(*args, **kwargs):
        raise AssertionError("the offline pass must never reach Nominatim")

    monkeypatch.setattr(geocoder, "_nominatim_lookup", boom)
    geocoder.resolve_offline(db)
    # No negative row either: a query this pass could not answer must look
    # untried to the network layer that gets it next.
    assert db.scalars(select(GeocodeCache)).all() == []


def test_offline_resolution_can_be_scoped_to_one_scans_imports(db):
    db.add(_prop(fingerprint="a", address="Via Ignota 1"))
    db.add(_prop(fingerprint="b", address="Via Ignota 2"))
    db.commit()
    mine = db.scalar(select(Property).where(Property.fingerprint == "a"))
    assert mine is not None

    assert geocoder.resolve_offline(db, property_ids={mine.id})["scanned"] == 1
    other = db.scalar(select(Property).where(Property.fingerprint == "b"))
    assert other is not None and other.latitude is None


def test_the_demo_corpus_gets_a_pin_for_every_property_without_a_request(db, monkeypatch):
    """The acceptance figures, recorded so a dropped coordinate field is visible.

    Layer 1 is whatever the ads carried, which in the corpus is 68 of 80 — the
    other 12 stand for the listings a portal publishes without coordinates, the
    normal case on Immobiliare. Layer 2 places all 12 from what the database
    already holds, and every one of them is labelled approximate: there is no
    cache to reuse here, so they can only be placed by their own district.
    """
    from app.services import demo_data

    def boom(*args, **kwargs):
        raise AssertionError("both layers must run with no network at all")

    monkeypatch.setattr(geocoder, "_nominatim_lookup", boom)
    demo_data.seed_demo(db)

    total = db.scalar(select(func.count()).select_from(Property))
    with_pin = db.scalar(
        select(func.count()).select_from(Property).where(Property.latitude.is_not(None))
    )
    assert (total, with_pin) == (80, 68)

    summary = geocoder.resolve_offline(db)
    assert summary == {"scanned": 12, "placed": 12, "exact": 0, "approximate": 12}

    with_pin = db.scalar(
        select(func.count()).select_from(Property).where(Property.latitude.is_not(None))
    )
    assert with_pin == 80
    approximate = [
        p for p in db.scalars(select(Property)) if geocoder.is_approximate(p.coordinate_source)
    ]
    assert len(approximate) == 12
    # Every one of them is inside Milano, and none is a copy of a real address.
    exact_pins = {
        (p.latitude, p.longitude)
        for p in db.scalars(select(Property))
        if p.coordinate_source == geocoder.SOURCE_PORTAL
    }
    for prop in approximate:
        assert geocoder.is_valid_coordinate_for_city(prop.latitude, prop.longitude, prop.city)
        assert (prop.latitude, prop.longitude) not in exact_pins


def test_geocode_missing_properties_clears_out_of_bounds_existing_pins(db, monkeypatch):
    # A property originally geocoded wrongly to Cernusco sul Naviglio (45.524, 9.333)
    prop = _prop(
        address="Via Tolmezzo, 2", zone="Udine", city="Milano", latitude=45.524, longitude=9.333
    )
    db.add(prop)
    db.commit()

    monkeypatch.setattr(geocoder, "_nominatim_lookup", lambda q, base, **kw: (45.49, 9.23))
    summary = geocoder.geocode_missing_properties(db)
    assert summary["geocoded"] == 1
    db.refresh(prop)
    assert prop.latitude == 45.49 and prop.longitude == 9.23


def test_geocode_missing_properties_aborts_on_rate_limit(db, monkeypatch):
    import email.message
    import urllib.error

    for i in range(5):
        db.add(_prop(fingerprint=f"fp{i}", address=f"Via Test {i}"))
    db.commit()

    called = {"n": 0}

    def lookup_rate_limit(q, base, **kw):
        called["n"] += 1
        if called["n"] == 2:
            raise urllib.error.HTTPError(
                "url", 429, "Too Many Requests", email.message.Message(), None
            )
        return (45.46, 9.19)

    monkeypatch.setattr(geocoder, "_nominatim_lookup", lookup_rate_limit)
    summary = geocoder.geocode_missing_properties(db, max_calls=None)
    assert summary["geocoded"] == 1
    assert summary["cancelled"] is True
    assert summary["remaining"] == 4
    assert "429" in geocoder._geocode_progress["last_error"]
