"""Commute times to the user's saved places. All offline: the OSRM HTTP call
(`_osrm_table`) is mocked, so the cache/batch/fail-open logic is exercised with
no network and no per-second wait.

The two properties worth pinning hardest are the ones a later change is most
likely to break by "helpfully" optimising: the annotation must never reach the
network (it runs on every grid page), and a transport failure must not be
cached as an answer (or one blocked afternoon would permanently blank a card's
commute)."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import save_settings
from app.database import Base
from app.models import CommuteCache, GeocodeCache, Property
from app.services import commute


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
    # never actually pause a test for the routing server's pacing
    monkeypatch.setattr(commute, "PACE_SECONDS", 0)


def _prop(**kw) -> Property:
    base = dict(fingerprint="fp", city="Milano", contract="sale", latitude=45.46, longitude=9.19)
    base.update(kw)
    return Property(**base)


OFFICE = {"name": "Office", "lat": 45.48, "lng": 9.20, "mode": "car"}


def _settings(points, **extra) -> dict:
    return {"commute_enabled": True, "commute_points": points, **extra}


# --- reading the user's saved places ---------------------------------------


def test_points_are_empty_while_the_feature_is_off():
    # Off by default, like the match score: nothing configured, nothing shown.
    assert (
        commute.points_from_settings({"commute_enabled": False, "commute_points": [OFFICE]}) == []
    )


def test_a_point_with_no_name_or_no_target_is_dropped():
    points = commute.points_from_settings(
        _settings(
            [
                {"name": "", "lat": 45.4, "lng": 9.1},  # unlabelled: unanswerable
                {"name": "Nowhere"},  # no address and no pin
                {"name": "Work", "address": "Via Dante 5, Milano"},
                OFFICE,
            ]
        )
    )
    assert [p["name"] for p in points] == ["Work", "Office"]


def test_an_unknown_mode_falls_back_instead_of_losing_the_other_points():
    points = commute.points_from_settings(
        _settings([{**OFFICE, "mode": "teleport"}, {**OFFICE, "name": "Metro", "mode": "foot"}])
    )
    assert [p["mode"] for p in points] == ["car", "foot"]


def test_half_a_coordinate_pair_is_not_a_pin():
    # A latitude with no longitude would place the point on the prime meridian.
    points = commute.points_from_settings(
        _settings(
            [{"name": "Half", "lat": 45.4}, {"name": "Half+addr", "lat": 45.4, "address": "x"}]
        )
    )
    assert [p["name"] for p in points] == ["Half+addr"]
    assert points[0]["lat"] is None  # falls back to geocoding the address


# --- the annotation stays offline ------------------------------------------


def test_annotation_reads_the_cache_and_never_the_network(db, monkeypatch):
    prop = _prop()
    db.add(prop)
    db.commit()
    db.add(
        CommuteCache(
            leg=commute.cache_key("car", 45.46, 9.19, 45.48, 9.20),
            distance_m=3200.0,
            duration_s=780.0,
        )
    )
    db.commit()

    def _boom(*a, **kw):  # pragma: no cover - the point is that it never runs
        raise AssertionError("the annotation must not route: it runs on every grid page")

    monkeypatch.setattr(commute, "_osrm_table", _boom)

    commute.annotate_commutes(db, [prop], _settings([OFFICE]))
    assert prop.commutes == [
        {"name": "Office", "mode": "car", "distance_m": 3200.0, "duration_s": 780.0}
    ]


def test_an_unrouted_leg_is_simply_absent(db):
    prop = _prop()
    db.add(prop)
    db.commit()
    commute.annotate_commutes(db, [prop], _settings([OFFICE]))
    assert prop.commutes == []


def test_a_property_with_no_pin_gets_no_commute(db):
    prop = _prop(latitude=None, longitude=None)
    db.add(prop)
    db.commit()
    commute.annotate_commutes(db, [prop], _settings([OFFICE]))
    assert prop.commutes == []


def test_an_address_point_uses_a_cached_geocode_but_never_asks_for_one(db, monkeypatch):
    from app.services import geocoder

    prop = _prop()
    db.add(prop)
    db.add(GeocodeCache(query="via dante 5, milano", latitude=45.48, longitude=9.20))
    db.commit()
    db.add(
        CommuteCache(
            leg=commute.cache_key("car", 45.46, 9.19, 45.48, 9.20),
            distance_m=1000.0,
            duration_s=300.0,
        )
    )
    db.commit()
    monkeypatch.setattr(
        geocoder,
        "_nominatim_lookup",
        lambda *a, **kw: pytest.fail("the annotation must not geocode either"),
    )

    commute.annotate_commutes(
        db, [prop], _settings([{"name": "Work", "address": "Via Dante 5, Milano"}])
    )
    assert prop.commutes and prop.commutes[0]["name"] == "Work"


# --- the batch --------------------------------------------------------------


def test_the_batch_routes_and_caches_each_leg(db, monkeypatch):
    db.add(_prop())
    db.commit()
    save_settings(_settings([OFFICE, {**OFFICE, "name": "Gym", "lat": 45.50, "lng": 9.22}]))
    monkeypatch.setattr(
        commute, "_osrm_table", lambda o, dests, profile, base: [(3200.0, 780.0), (5000.0, 900.0)]
    )

    summary = commute.compute_missing_commutes(db)
    assert summary["routed"] == 2 and summary["scanned"] == 1
    assert db.scalar(select(CommuteCache).where(CommuteCache.distance_m == 5000.0)) is not None


def test_two_places_on_one_mode_cost_a_single_request(db, monkeypatch):
    # OSRM's /table answers a whole one-to-many matrix at once: three saved
    # places must not become three requests against a courtesy server.
    db.add(_prop())
    db.commit()
    save_settings(
        _settings(
            [
                OFFICE,
                {**OFFICE, "name": "Gym", "lat": 45.50, "lng": 9.22},
                {**OFFICE, "name": "Metro", "lat": 45.47, "lng": 9.18, "mode": "foot"},
            ]
        )
    )
    calls = []

    def fake(origin, dests, profile, base):
        calls.append(profile)
        return [(1.0, 2.0)] * len(dests)

    monkeypatch.setattr(commute, "_osrm_table", fake)
    commute.compute_missing_commutes(db)
    # one per distinct mode, not one per place
    assert sorted(calls) == ["driving", "walking"]


def test_a_cached_leg_is_not_re_routed(db, monkeypatch):
    db.add(_prop())
    db.commit()
    db.add(
        CommuteCache(
            leg=commute.cache_key("car", 45.46, 9.19, 45.48, 9.20),
            distance_m=10.0,
            duration_s=20.0,
        )
    )
    db.commit()
    save_settings(_settings([OFFICE]))
    monkeypatch.setattr(
        commute,
        "_osrm_table",
        lambda *a, **kw: pytest.fail("an already-routed leg must cost no request"),
    )

    summary = commute.compute_missing_commutes(db)
    assert summary["cached"] == 1 and summary["routed"] == 0


def test_no_route_is_an_answer_and_is_remembered(db, monkeypatch):
    # OSRM looked and found no way through: asking again would spend a request
    # to be told the same thing, so the NULL row is cached on purpose.
    db.add(_prop())
    db.commit()
    save_settings(_settings([OFFICE]))
    monkeypatch.setattr(commute, "_osrm_table", lambda o, d, p, b: [None])

    summary = commute.compute_missing_commutes(db)
    assert summary["unreachable"] == 1
    row = db.scalars(select(CommuteCache)).one()
    assert row.distance_m is None and row.duration_s is None


def test_a_transport_failure_caches_nothing_so_a_later_run_retries(db, monkeypatch):
    db.add(_prop())
    db.commit()
    save_settings(_settings([OFFICE]))

    def boom(*a, **kw):
        raise TimeoutError("router unreachable")

    monkeypatch.setattr(commute, "_osrm_table", boom)
    summary = commute.compute_missing_commutes(db)

    assert summary["routed"] == 0 and summary["remaining"] == 1
    assert db.scalars(select(CommuteCache)).all() == []  # nothing frozen as an answer

    # the retry succeeds and the card gets its commute
    monkeypatch.setattr(commute, "_osrm_table", lambda o, d, p, b: [(100.0, 200.0)])
    assert commute.compute_missing_commutes(db)["routed"] == 1


def test_a_malformed_answer_is_not_cached_either(db, monkeypatch):
    db.add(_prop())
    db.commit()
    save_settings(_settings([OFFICE]))
    monkeypatch.setattr(commute, "_osrm_table", lambda o, d, p, b: None)

    assert commute.compute_missing_commutes(db)["routed"] == 0
    assert db.scalars(select(CommuteCache)).all() == []


def test_the_batch_does_nothing_while_the_feature_is_off(db, monkeypatch):
    db.add(_prop())
    db.commit()
    save_settings({"commute_enabled": False, "commute_points": [OFFICE]})
    monkeypatch.setattr(commute, "_osrm_table", lambda *a, **kw: pytest.fail("nothing to route to"))

    summary = commute.compute_missing_commutes(db)
    assert summary["points"] == 0 and summary["scanned"] == 0


def test_properties_without_a_pin_are_not_candidates(db, monkeypatch):
    db.add(_prop())
    db.add(_prop(latitude=None, longitude=None))
    db.commit()
    save_settings(_settings([OFFICE]))
    monkeypatch.setattr(commute, "_osrm_table", lambda o, d, p, b: [(1.0, 2.0)])

    assert commute.compute_missing_commutes(db)["scanned"] == 1


def test_the_budget_caps_the_requests_and_reports_the_rest(db, monkeypatch):
    # Distinct pins on purpose: the cache is keyed by coordinates, so three
    # listings in the same building would legitimately share one routed leg
    # (see the test below) and never reach the budget at all.
    for i in range(3):
        db.add(_prop(latitude=45.40 + i / 100, longitude=9.10 + i / 100))
    db.commit()
    save_settings(_settings([OFFICE]))
    calls = []
    monkeypatch.setattr(
        commute,
        "_osrm_table",
        lambda o, d, p, b: (calls.append(1), [(1.0, 2.0)])[1],
    )

    summary = commute.compute_missing_commutes(db, max_calls=2)
    assert len(calls) == 2
    assert summary["remaining"] == 1  # "run it again to continue"


def test_two_listings_at_one_address_share_the_routed_leg(db, monkeypatch):
    # The cache is keyed by coordinates, not by property id: two flats in the
    # same building have the same commute, and routing it twice would spend a
    # request to learn that.
    db.add(_prop())
    db.add(_prop())
    db.commit()
    save_settings(_settings([OFFICE]))
    calls = []
    monkeypatch.setattr(
        commute, "_osrm_table", lambda o, d, p, b: (calls.append(1), [(1.0, 2.0)])[1]
    )

    summary = commute.compute_missing_commutes(db)
    assert len(calls) == 1
    assert summary["routed"] == 1 and summary["cached"] == 1


def test_a_second_batch_is_refused_rather_than_run_twice(db, monkeypatch):
    save_settings(_settings([OFFICE]))
    commute._commute_run_lock.acquire()
    try:
        with pytest.raises(commute.CommuteError):
            commute.compute_missing_commutes(db)
    finally:
        commute._commute_run_lock.release()


def test_clearing_the_cache_forgets_every_leg(db):
    db.add(CommuteCache(leg="car|1,1|2,2", distance_m=1.0, duration_s=2.0))
    db.add(CommuteCache(leg="car|1,1|3,3", distance_m=None, duration_s=None))
    db.commit()
    # Positive rows go too, unlike the geocoder's misses-only clear: a moved
    # office pin makes exactly the *successful* answers the wrong ones.
    assert commute.clear_commute_cache(db) == 2
    assert db.scalars(select(CommuteCache)).all() == []


# --- the OSRM request shape -------------------------------------------------


def test_the_table_request_sends_lng_lat_and_reads_the_source_row(monkeypatch):
    # OSRM speaks lng,lat — the reverse of every other coordinate in this
    # project — and row 0 of the matrix is the source against itself.
    seen = {}

    class FakeResponse:
        def read(self):
            return b'{"code":"Ok","durations":[[0,780.5]],"distances":[[0,3200.5]]}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        seen["url"] = req.full_url
        return FakeResponse()

    monkeypatch.setattr(commute.urllib.request, "urlopen", fake_urlopen)

    out = commute._osrm_table((45.46, 9.19), [(45.48, 9.20)], "driving", "http://osrm.test")
    assert out == [(3200.5, 780.5)]
    assert "/table/v1/driving/9.19,45.46;9.2,45.48?" in seen["url"]
    assert "sources=0" in seen["url"]


def test_a_no_route_code_is_an_answer_not_a_failure(monkeypatch):
    class FakeResponse:
        def read(self):
            return b'{"code":"NoRoute"}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(commute.urllib.request, "urlopen", lambda req, timeout=0: FakeResponse())
    # one None per destination — cacheable — rather than None for the whole call
    assert commute._osrm_table(
        (45.4, 9.1), [(45.5, 9.2), (45.6, 9.3)], "driving", "http://osrm.test"
    ) == [
        None,
        None,
    ]


def test_an_error_code_is_a_failure_and_caches_nothing(monkeypatch):
    class FakeResponse:
        def read(self):
            return b'{"code":"InvalidQuery"}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(commute.urllib.request, "urlopen", lambda req, timeout=0: FakeResponse())
    assert commute._osrm_table((45.4, 9.1), [(45.5, 9.2)], "driving", "http://osrm.test") is None
