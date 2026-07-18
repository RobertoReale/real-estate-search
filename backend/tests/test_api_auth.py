"""Optional shared-secret API token (invariant 14 relaxed to "bind address OR
token"). The middleware is driven directly with a fake request/call_next: a
TestClient would start the real scheduler via the app lifespan, which the rest
of the suite avoids for the same reason."""

import asyncio

from starlette.requests import Request

from app import main


def _request(path: str, headers: dict | None = None, method: str = "GET") -> Request:
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    return Request(scope)


async def _ok(_request):
    return "PASSED_THROUGH"


def _run(path, headers=None, method="GET"):
    return asyncio.run(main.require_api_token(_request(path, headers, method), _ok))


def _set_token(monkeypatch, token):
    monkeypatch.setattr(main, "load_settings", lambda: {"api_auth_token": token})


def test_open_when_no_token_is_set(monkeypatch):
    _set_token(monkeypatch, "")
    assert _run("/api/settings") == "PASSED_THROUGH"


def test_api_request_without_the_token_is_rejected(monkeypatch):
    _set_token(monkeypatch, "s3cret")
    resp = _run("/api/properties")
    assert resp.status_code == 401


def test_correct_bearer_token_passes(monkeypatch):
    _set_token(monkeypatch, "s3cret")
    assert _run("/api/properties", {"Authorization": "Bearer s3cret"}) == "PASSED_THROUGH"


def test_wrong_token_is_rejected(monkeypatch):
    _set_token(monkeypatch, "s3cret")
    assert _run("/api/properties", {"Authorization": "Bearer nope"}).status_code == 401


def test_non_api_paths_stay_open_so_the_spa_can_load(monkeypatch):
    _set_token(monkeypatch, "s3cret")
    # the built app and its assets are served from "/", not /api, and must load
    # unauthenticated so it can present the token prompt
    assert _run("/index.html") == "PASSED_THROUGH"
    assert _run("/") == "PASSED_THROUGH"


def test_cors_preflight_is_never_blocked(monkeypatch):
    _set_token(monkeypatch, "s3cret")
    # browsers send OPTIONS preflight without the Authorization header
    assert _run("/api/settings", method="OPTIONS") == "PASSED_THROUGH"
