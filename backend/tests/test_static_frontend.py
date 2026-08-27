"""Tests for serving the built dashboard from the backend (phone access).

The failure these guard against is silent: mounting the static frontend at "/"
before the API routes makes the mount a catch-all that swallows every
`/api/...` request, and the app still starts, still serves the dashboard, and
answers 404 for data it used to return. Nothing is logged. Both the browser and
the phone then show an empty dashboard for what looks like a scraper problem.
"""

from typing import cast

from fastapi.routing import Mount

from app import main as app_main


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
