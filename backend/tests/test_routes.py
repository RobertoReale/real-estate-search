"""End-to-end tests of the HTTP layer itself.

Every other test in the suite calls the services directly, so `main.py` — the
largest file in the backend — was only ever exercised through its helpers: the
route wiring around them (query validation, status codes, response
serialization, route registration order) had no coverage at all. That wiring is
exactly where a bug is invisible from the inside: a filter dropped from a
signature still returns 200 with the unfiltered grid, and a path route shadowed
by another one 422s forever (the reason `/api/properties/check-progress` is
registered before `/api/properties/{property_id}` and says so in a comment).

`TestClient(app)` is used WITHOUT its context manager on purpose: entering it
runs the FastAPI lifespan, which starts the real APScheduler and would have the
test suite scanning portals. The DB dependency is overridden with an in-memory
SQLite session, so nothing touches `case.db` either.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config, main
from app.database import Base, get_db
from app.models import Listing, Property


@pytest.fixture
def client():
    # StaticPool: an in-memory SQLite database lives inside its *connection*, so
    # the default pool would hand the seeding session and the request sessions
    # two different (empty) databases.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = override_db
    session = Session()
    _seed(session)
    session.close()
    # no `with`: entering the context manager runs the lifespan (init_db against
    # the real case.db + the APScheduler start), which the whole suite avoids
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def _seed(db) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)  # as SQLite hands them back
    rows = [
        dict(title="Trilocale Isola", city="Milano", zone="Isola", sqm=100.0, price=400_000.0),
        dict(title="Bilocale Prati", city="Roma", zone="Prati", sqm=55.0, price=250_000.0),
        # deliberately ragged: no price, no surface, no city — the shapes that
        # make a derived value (€/sqm, a sort key) blow up if left unguarded
        dict(title="", city="", zone="", sqm=None, price=None),
    ]
    for i, r in enumerate(rows):
        prop = Property(
            fingerprint=f"fp{i}",
            title=r["title"],
            city=r["city"],
            zone=r["zone"],
            sqm=r["sqm"],
            contract="sale",
            status="active",
            current_min_price=r["price"],
            first_price=r["price"],
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(prop)
        db.flush()
        db.add(
            Listing(
                property_id=prop.id,
                portal="immobiliare",
                portal_id=str(1000 + i),
                url=f"https://www.immobiliare.it/annunci/{1000 + i}/",
                price=r["price"],
                agency="Studio Rossi" if i == 0 else "",
                first_seen_at=now,
                last_seen_at=now,
            )
        )
    db.commit()


# --- grid: filters actually reach the query ---------------------------------


def test_grid_returns_active_properties_with_provenance_field(client):
    api = client
    resp = api.get("/api/properties")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3
    # found_by is a transient annotation: an un-annotated serialization path
    # used to 500 on the missing attribute, hence the before-validator
    assert all(item["found_by"] == [] for item in body)


@pytest.mark.parametrize(
    "params,expected",
    [
        ({"city": "milano"}, 1),
        ({"q": "trilocale"}, 1),
        ({"agency": "rossi"}, 1),
        ({"min_price": 300_000}, 1),
        ({"max_price": 300_000}, 1),
        ({"min_sqm": 60}, 1),
        ({"zone": "prati"}, 1),
        ({"merged_only": True}, 0),
        ({"min_sqm_price": 5_000}, 0),
    ],
)
def test_each_filter_narrows_the_grid(client, params, expected):
    """A filter silently dropped from the route signature still answers 200
    with the *unfiltered* grid — the failure mode that has no symptom."""
    api = client
    resp = api.get("/api/properties", params=params)
    assert resp.status_code == 200
    assert len(resp.json()) == expected


@pytest.mark.parametrize("sort", ["newest", "price_asc", "price_desc", "sqm_price", "match"])
def test_every_sort_survives_missing_prices_and_surfaces(client, sort):
    """The ragged row carries neither price nor surface: each sort key has to
    have its own fallback or the whole grid 500s."""
    api = client
    resp = api.get("/api/properties", params={"sort": sort, "status": "all"})
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.parametrize(
    "params",
    [
        {"status": "nonsense"},
        {"sort": "cheapest"},
        {"contract": "leasing"},
        {"portal": "casa.it"},
        {"floor_band": "basement"},
        {"deal": "bargain"},
        {"center_lat": 200, "center_lng": 9, "radius_m": 100},
    ],
)
def test_invalid_enum_params_are_rejected_not_ignored(client, params):
    """A typo'd value must not degrade to "no filter": that returns the whole
    grid as if the filter applied, which reads as a bug in the data."""
    api = client
    assert api.get("/api/properties", params=params).status_code == 422


def test_malformed_polygon_is_a_400_not_a_silent_pass(client):
    api = client
    assert api.get("/api/properties", params={"poly": "not-a-polygon"}).status_code == 400
    ok = api.get("/api/properties", params={"poly": "45.4,9.1;45.5,9.2;45.45,9.3"})
    assert ok.status_code == 200


def test_unknown_profile_overlay_is_404(client):
    api = client
    assert api.get("/api/properties", params={"profile_id": 9999}).status_code == 404


# --- route registration order ----------------------------------------------


def test_check_progress_is_not_shadowed_by_the_id_route(client):
    """Registered before `/api/properties/{property_id}`: Starlette matches in
    order, and the int path param would turn every poll into a 422 — the
    progress bar then never advances (comment in main.py says exactly this)."""
    api = client
    resp = api.get("/api/properties/check-progress")
    assert resp.status_code == 200
    assert "active" in resp.json()


def test_export_is_not_shadowed_by_the_id_route(client):
    api = client
    resp = api.get("/api/properties/export", params={"fmt": "csv"})
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]


# --- export mirrors the grid ------------------------------------------------


@pytest.mark.parametrize("fmt,marker", [("csv", "Title"), ("markdown", "#"), ("html", "<html")])
def test_export_formats_render(client, fmt, marker):
    api = client
    resp = api.get("/api/properties/export", params={"fmt": fmt})
    assert resp.status_code == 200
    assert marker.lower() in resp.text.lower()


def test_export_applies_the_same_filters_as_the_grid(client):
    """The dossier "mirrors the screen" convention: both go through
    `_select_properties`, so a filter must reach the file too."""
    api = client
    grid = api.get("/api/properties", params={"city": "milano"}).json()
    dossier = api.get("/api/properties/export", params={"fmt": "csv", "city": "milano"}).text
    assert len(grid) == 1
    assert "Trilocale Isola" in dossier
    assert "Bilocale Prati" not in dossier


# --- lifecycle transitions through the HTTP layer ---------------------------


def test_hide_then_restore_round_trip(client):
    api = client
    pid = api.get("/api/properties").json()[0]["id"]
    assert api.delete(f"/api/properties/{pid}").status_code == 200
    assert api.get(f"/api/properties/{pid}").json()["status"] == "hidden"
    assert pid not in [p["id"] for p in api.get("/api/properties").json()]
    assert api.post(f"/api/properties/{pid}/restore").status_code == 200
    assert api.get(f"/api/properties/{pid}").json()["status"] == "active"


def test_sold_records_a_confirmed_close_date_and_restore_clears_it(client):
    api = client
    pid = api.get("/api/properties").json()[0]["id"]
    api.post(f"/api/properties/{pid}/sold")
    sold = api.get(f"/api/properties/{pid}").json()
    assert sold["status"] == "sold"
    assert sold["sold_at"] is not None
    api.post(f"/api/properties/{pid}/restore")
    assert api.get(f"/api/properties/{pid}").json()["sold_at"] is None


def test_patch_updates_curated_fields_only(client):
    api = client
    pid = api.get("/api/properties").json()[0]["id"]
    resp = api.patch(f"/api/properties/{pid}", json={"is_favorite": True, "notes": "da vedere"})
    assert resp.status_code == 200
    assert resp.json()["is_favorite"] is True
    assert resp.json()["notes"] == "da vedere"
    assert len(api.get("/api/properties", params={"only_favorites": True}).json()) == 1


def test_missing_property_is_404_on_every_single_item_route(client):
    api = client
    assert api.get("/api/properties/9999").status_code == 404
    assert api.patch("/api/properties/9999", json={"notes": "x"}).status_code == 404
    assert api.delete("/api/properties/9999").status_code == 404
    assert api.post("/api/properties/9999/restore").status_code == 404
    assert api.post("/api/properties/9999/sold").status_code == 404


def test_bulk_skips_unknown_ids_instead_of_failing_the_batch(client):
    api = client
    ids = [p["id"] for p in api.get("/api/properties").json()] + [9999]
    resp = api.post("/api/properties/bulk", json={"ids": ids, "action": "favorite"})
    assert resp.status_code == 200
    assert resp.json()["processed"] == 3


def test_bulk_add_tag_requires_a_tag_id(client):
    api = client
    resp = api.post("/api/properties/bulk", json={"ids": [1], "action": "add_tag"})
    assert resp.status_code == 400


# --- tags -------------------------------------------------------------------


def test_tag_creation_is_idempotent_case_insensitively(client):
    api = client
    first = api.post("/api/tags", json={"name": "Da visitare"}).json()
    again = api.post("/api/tags", json={"name": "da VISITARE"}).json()
    assert first["id"] == again["id"]
    assert len(api.get("/api/tags").json()) == 1


def test_tag_filter_and_deletion(client):
    api = client
    tag = api.post("/api/tags", json={"name": "Preferiti"}).json()
    pid = api.get("/api/properties").json()[0]["id"]
    api.patch(f"/api/properties/{pid}", json={"tag_ids": [tag["id"]]})
    assert len(api.get("/api/properties", params={"tag": "preferiti"}).json()) == 1
    assert api.delete(f"/api/tags/{tag['id']}").status_code == 200
    assert api.get("/api/tags").json() == []
    # the property survives its tag being deleted globally
    assert api.get(f"/api/properties/{pid}").status_code == 200


def test_empty_tag_name_is_rejected(client):
    api = client
    assert api.post("/api/tags", json={"name": "   "}).status_code == 400


# --- search profiles --------------------------------------------------------


def test_creating_a_duplicate_search_is_refused(client):
    api = client
    payload = {
        "name": "Milano vendita",
        "search_url": "https://www.immobiliare.it/vendita-case/milano/",
        "excluded_keywords": "asta",
    }
    assert api.post("/api/search-profiles", json=payload).status_code == 200
    dup = api.post("/api/search-profiles", json={**payload, "name": "Copia"})
    assert dup.status_code == 400
    assert len(api.get("/api/search-profiles").json()) == 1


def test_updating_a_missing_profile_is_404(client):
    api = client
    resp = api.put(
        "/api/search-profiles/9999",
        json={"name": "x", "search_url": "https://www.immobiliare.it/vendita-case/milano/"},
    )
    assert resp.status_code == 404


# --- read-only analytics endpoints answer on an empty/ragged DB -------------


@pytest.mark.parametrize(
    "path,params",
    [
        ("/api/market-velocity", {}),
        ("/api/market-velocity", {"contract": "rent", "city": "Milano"}),
        ("/api/pricing-trends/areas", {}),
        ("/api/pricing-trends", {"city": "milano", "zone": "isola"}),
        ("/api/pricing-trends/comparables", {"city": "milano"}),
        ("/api/scraper-health", {}),
        ("/api/scrapers/status", {}),
        ("/api/tags", {}),
        ("/api/search-profiles", {}),
        ("/api/email-import/progress", {}),
        ("/api/email-import/check-progress", {}),
    ],
)
def test_analytics_endpoints_answer_without_history(client, path, params):
    """None of these may 500 on a database that has not accumulated snapshots
    yet — which is every database on day one."""
    api = client
    assert api.get(path, params=params).status_code == 200


def test_pricing_trends_requires_a_city(client):
    api = client
    assert api.get("/api/pricing-trends").status_code == 422


# --- optional auth token (invariant 14) -------------------------------------


def test_token_gate_blocks_api_but_not_the_app_shell(client, monkeypatch):
    """With `api_auth_token` set every /api call needs the bearer header, while
    non-/api routes stay open so the SPA can load and show its prompt."""
    api = client
    monkeypatch.setattr(config, "load_settings", lambda: {"api_auth_token": "s3cret"})
    monkeypatch.setattr(main, "load_settings", lambda: {"api_auth_token": "s3cret"})
    assert api.get("/api/properties").status_code == 401
    assert api.get("/api/properties", headers={"Authorization": "Bearer wrong"}).status_code == 401
    ok = api.get("/api/properties", headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200
    # no dist/ in a test run, so the SPA mount is absent: the point is only that
    # the middleware did not answer 401 for a non-/api path
    assert api.get("/does-not-exist").status_code != 401
