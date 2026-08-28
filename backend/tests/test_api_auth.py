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
        # latin-1, not utf-8: that is the codec ASGI servers and Starlette use
        # for header values, so it is what a browser's bytes turn back into.
        # Encoding the fixture any other way would model a request no client
        # ever sends and quietly mistranslate an accented token.
        "headers": [
            (k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (headers or {}).items()
        ],
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


def test_an_accented_token_works_instead_of_bricking_the_api(monkeypatch):
    """Regression: `hmac.compare_digest` refuses str arguments that are not pure
    ASCII, so an accented token — an entirely natural choice for an Italian user
    — raised TypeError out of the middleware and made EVERY /api request a 500.
    Not just the unauthenticated ones: the correct token crashed too, and the
    settings call needed to undo it is itself under /api, so the only way back
    was hand-editing settings.json. 'ò' is inside latin-1, which is how Starlette
    decodes header values, so the browser really does deliver this one."""
    _set_token(monkeypatch, "segretò")
    assert _run("/api/properties", {"Authorization": "Bearer segretò"}) == "PASSED_THROUGH"
    assert _run("/api/properties", {"Authorization": "Bearer segreto"}).status_code == 401
    assert _run("/api/properties").status_code == 401


def test_a_token_the_browser_cannot_send_fails_closed(monkeypatch):
    """Past latin-1 the browser refuses to put the value in a header at all, so
    the request arrives without one. That must still be a clean 401 — the point
    of the fix is that no token value can turn the gate into a crash."""
    _set_token(monkeypatch, "пароль")
    assert _run("/api/properties").status_code == 401
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
