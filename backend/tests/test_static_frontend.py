"""Tests for serving the built dashboard from the backend (phone access).

The failure these guard against is silent: mounting the static frontend at "/"
before the API routes makes the mount a catch-all that swallows every
`/api/...` request, and the app still starts, still serves the dashboard, and
answers 404 for data it used to return. Nothing is logged. Both the browser and
the phone then show an empty dashboard for what looks like a scraper problem.

The SPA fallback below is the same hazard with a second edge. The dashboard
routes on the URL, so the mount now answers `/listings/123` with `index.html`
rather than a 404 — and a fallback written one line too wide answers *everything*
that way, including the API paths this file exists to protect and the assets the
page needs to run. Both directions are asserted here, because both fail quietly:
one turns a mistyped route into a JSON parse error, the other into a blank page.
"""

from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.routing import Mount
from fastapi.testclient import TestClient

from app import main as app_main
from app.routers import (
    analytics,
    maintenance,
    profiles,
    properties,
    scans,
    searches,
    settings,
    system,
)

INDEX_HTML = "<!doctype html><title>dashboard</title><div id=root></div>"


@pytest.fixture
def spa_client(tmp_path: Path) -> TestClient:
    """The app as `main.py` assembles it, over a dist directory of our own.

    Every router, then `mount_frontend` last — the same order and the same mount
    the module uses, so what is asserted here is the production wiring rather
    than a second arrangement that happens to resemble it. A directory built for
    the test rather than the real `frontend/dist`, which exists only after
    `npm run build` and would make these tests pass or skip depending on what the
    developer ran last.
    """
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (dist / "assets" / "app.js").write_text("export const ok = 1;\n", encoding="utf-8")

    app = FastAPI()
    for router in (
        properties,
        profiles,
        searches,
        analytics,
        scans,
        maintenance,
        settings,
        system,
    ):
        app.include_router(router.router)
    app_main.mount_frontend(app, dist)
    return TestClient(app)


def _registration_order() -> list[tuple[int, object]]:
    """The app's routes in the order Starlette will try to match them, paired
    with their position in the top-level table.

    `include_router` does not flatten its routes into `app.router.routes`: the
    app holds one opaque entry per included router and matching descends into
    it. Walking only the top level therefore finds *no* `/api` path at all —
    which would quietly turn the assertion below into a tautology over an empty
    list, exactly the silent pass this file exists to prevent. `original_router`
    is the way back in; a route that has none is already a leaf (the openapi
    routes, the mount), and older FastAPI layouts that did flatten still work.
    """
    ordered: list[tuple[int, object]] = []
    for i, route in enumerate(app_main.app.router.routes):
        included = getattr(route, "original_router", None)
        if included is None:
            ordered.append((i, route))
        else:
            ordered.extend((i, sub) for sub in included.routes)
    return ordered


def _mount_indexes() -> list[int]:
    return [
        i for i, route in _registration_order() if isinstance(route, Mount) and route.path == ""
    ]
    # Starlette normalises a mount at "/" to an empty path prefix.


def test_static_mount_never_shadows_the_api():
    """Every /api route must be registered before the catch-all mount.

    Skips itself when `frontend/dist` is absent (the dev flow, where Vite
    serves the app): there is no mount to shadow anything.
    """
    mounts = _mount_indexes()
    if not mounts:
        return

    api_indexes = [
        i for i, route in _registration_order() if getattr(route, "path", "").startswith("/api")
    ]
    assert api_indexes, "no /api routes found: the app layout changed"
    assert max(api_indexes) < min(mounts), (
        "the static frontend mount precedes an /api route and will shadow it; "
        "the mount must stay the last `include_router`/statement in main.py"
    )


def test_literal_get_routes_precede_their_dynamic_sibling():
    """Starlette matches GET routes in registration order, and a bare
    `{property_id}: int` path parameter still matches the literal segment
    "check-progress" before FastAPI's own type validation rejects it — so a
    literal route registered afterwards is dead code, its every request
    answering 422 instead of reaching the handler. This silently broke the
    dashboard availability-check progress bar, which polls
    `/api/properties/check-progress` every second: every poll failed, the bar
    never advanced, and the check looked stuck even while it worked."""
    get_paths = [
        path
        for _i, route in _registration_order()
        if "GET" in getattr(route, "methods", ())
        and (path := getattr(route, "path", "")).startswith("/api/properties")
    ]
    dynamic_index = get_paths.index("/api/properties/{property_id}")
    for literal in ("/api/properties/check-progress", "/api/properties/export"):
        assert get_paths.index(literal) < dynamic_index, (
            f"{literal} must be registered before /api/properties/{{property_id}}"
        )


def test_a_bookmarked_route_is_answered_with_the_dashboard(spa_client: TestClient):
    """`/listings/123` is a place, and the browser asks this server for it on
    every reload, every pasted link and every restored tab. There is no such
    file: without the fallback the dashboard is reachable at "/" and nowhere
    else, which is the same as saying a property cannot be linked."""
    for path in ("/", "/listings", "/listings/123", "/settings", "/deep/unknown/place"):
        response = spa_client.get(path)
        assert response.status_code == 200, path
        assert "id=root" in response.text, path


def test_the_query_string_survives_the_fallback(spa_client: TestClient):
    """The filters travel with the link, and they are the client's to read."""
    response = spa_client.get("/listings/123?city=Milano&max_price=500000")
    assert response.status_code == 200
    assert "id=root" in response.text


def test_a_real_api_route_still_answers_with_the_mount_in_place(spa_client: TestClient):
    """The whole point of invariant 13, asserted through the app rather than
    through the route table: a live /api path answers its own data.

    `check-progress` because it reads process state and touches no database —
    what is being tested is which handler the request reached, not what that
    handler found."""
    response = spa_client.get("/api/properties/check-progress")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "active" in response.json()


def test_an_unknown_api_path_is_a_404_and_not_the_dashboard(spa_client: TestClient):
    """The fallback's most dangerous over-reach. An /api path nothing claims
    falls through to the mount, and answering it with HTML would report a typo
    in a route as a parse error in the client — the one place nobody would look
    for it."""
    response = spa_client.get("/api/there-is-no-such-route")
    assert response.status_code == 404
    assert "id=root" not in response.text


def test_a_missing_asset_stays_a_404(spa_client: TestClient):
    """A hashed asset that is not there means a stale index.html or a half-copied
    build. Handing the browser HTML with a `.js` content type moves that failure
    into the module loader, where the message names neither the file nor the
    cause."""
    response = spa_client.get("/assets/does-not-exist.js")
    assert response.status_code == 404
    assert "id=root" not in response.text


def test_a_real_asset_is_still_served_as_itself(spa_client: TestClient):
    """The other half of the same rule: the fallback must not have changed what
    happens when the file *is* there."""
    response = spa_client.get("/assets/app.js")
    assert response.status_code == 200
    assert "export const ok" in response.text


def test_a_write_to_an_unknown_path_is_never_the_dashboard(spa_client: TestClient):
    """Only a page load falls back. A POST that matched no route is a client
    calling something that does not exist, and answering it 200 with a page
    would let it believe the write landed."""
    response = spa_client.post("/listings/123")
    assert response.status_code != 200
    assert "id=root" not in response.text


def test_cors_stays_scoped_to_the_dev_server():
    """Remote clients load the built app from this same origin, so they need no
    CORS entry. A wildcard here would mean someone "fixed" a phone that could
    not reach the API by opening the API to every website the phone visits."""
    origins = [
        origin
        for middleware in app_main.app.user_middleware
        for origin in cast(list, middleware.kwargs.get("allow_origins", []))
    ]
    assert origins, "CORS middleware disappeared: the dev server needs it"
    assert "*" not in origins
    assert all("localhost" in o or "127.0.0.1" in o for o in origins)
