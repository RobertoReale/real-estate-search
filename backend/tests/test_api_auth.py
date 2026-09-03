"""Invariant 14's two guards in `main.py`, which answer different halves of it.

`require_api_token` is the optional shared-secret token — the rule relaxed to
"bind address OR token", and what makes a wider bind safe to expose.
`reject_cross_site_writes` is the request the bind address cannot refuse at all,
because the browser forging it is itself on loopback.

Both are driven directly with a fake request/call_next: a TestClient would start
the real scheduler via the app lifespan, which the rest of the suite avoids for
the same reason."""

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


def test_the_backup_routes_are_behind_the_same_gate(monkeypatch):
    """Restoring overwrites the entire database and downloading hands the whole
    of it to whoever asked, which makes these the most powerful routes in the
    app. They add no access control of their own and need none: they are under
    /api like everything else and inherit the bind address plus the optional
    token — and that is the point of asserting it, because a route that
    overwrites the database must never become the reason to widen either."""
    _set_token(monkeypatch, "s3cret")
    restore = "/api/maintenance/backups/case-20260101-000000.db/restore"
    assert _run(restore, method="POST").status_code == 401
    assert _run("/api/maintenance/backups").status_code == 401
    assert _run(restore, {"Authorization": "Bearer s3cret"}, "POST") == "PASSED_THROUGH"


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


# --- The other half of invariant 14: the request the bind address cannot stop ---
#
# A cross-site form post is the one attack the loopback bind is no defence
# against, because the browser making it is itself on loopback. These drive
# `reject_cross_site_writes` the same way the token tests drive its neighbour.

APP_HOST = "127.0.0.1:8000"


def _origin(path, origin=None, method="POST", host=APP_HOST):
    headers = {"Host": host}
    if origin is not None:
        headers["Origin"] = origin
    return asyncio.run(main.reject_cross_site_writes(_request(path, headers, method), _ok))


def test_a_page_on_another_site_cannot_reset_the_database():
    """The finding this guard exists for. `POST /api/maintenance/reset/factory`
    takes no body, so a `<form>` on any site the user has open submits it as a
    simple request — no preflight, nothing for `allow_origins` to refuse — and
    the whole dashboard is gone. The response being unreadable cross-origin
    never mattered: the deletion had already happened."""
    resp = _origin("/api/maintenance/reset/factory", "https://evil.example")
    assert resp.status_code == 403
    # and the same for the two other routes that spend something real: the
    # user's residential IP, and the whole database
    assert _origin("/api/scrapers/trigger", "https://evil.example").status_code == 403
    assert (
        _origin(
            "/api/maintenance/backups/case-20260101-000000.db/restore", "https://evil.example"
        ).status_code
        == 403
    )


def test_the_dashboard_on_this_machine_is_unaffected():
    """Every legitimate client is same-origin or loopback: the packaged app and
    the phone load the SPA from the API's own origin, the Vite dev server sits
    on 5173, and the browser suite's `vite preview` proxies from 127.0.0.1."""
    assert _origin("/api/scrapers/trigger", f"http://{APP_HOST}") == "PASSED_THROUGH"
    assert _origin("/api/scrapers/trigger", "http://localhost:5173") == "PASSED_THROUGH"
    assert _origin("/api/scrapers/trigger", "http://127.0.0.1:4173") == "PASSED_THROUGH"


def test_a_phone_on_the_tailscale_bind_is_unaffected():
    """`serve.bat` binds a Tailscale address and serves the SPA from it, so the
    phone's origin is not loopback — it is the API's own. Same-origin is what
    lets this rule coexist with the one sanctioned wide bind (invariant 14)."""
    tailscale = "100.64.1.2:8000"
    assert (
        _origin("/api/scrapers/trigger", f"http://{tailscale}", host=tailscale) == "PASSED_THROUGH"
    )
    # ...and a stranger on that same network still cannot drive it from a page
    assert (
        _origin("/api/scrapers/trigger", "http://evil.example", host=tailscale).status_code == 403
    )


def test_a_client_that_states_no_origin_is_left_alone():
    """curl, a script, the test client. A browser always sends `Origin` on these
    methods, so an absent header is not the case being guarded — and refusing it
    would break every non-browser caller to prevent nothing."""
    assert _origin("/api/scrapers/trigger", None) == "PASSED_THROUGH"


def test_reads_and_preflight_are_untouched():
    """Only the methods a form can send cross-site are guarded. A GET changes
    nothing and its response is unreadable cross-origin anyway, and blocking the
    preflight would break the Vite dev server's own requests."""
    assert _origin("/api/properties", "https://evil.example", method="GET") == "PASSED_THROUGH"
    assert _origin("/api/settings", "https://evil.example", method="OPTIONS") == "PASSED_THROUGH"


def test_the_spa_itself_is_not_guarded():
    """The static mount is not /api and serves no state change; the guard has no
    business there (invariant 13 keeps it last, and this keeps it open)."""
    assert _origin("/index.html", "https://evil.example") == "PASSED_THROUGH"
