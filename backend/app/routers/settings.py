"""Reading and writing `settings.json`, plus the actions the Settings dialog
triggers directly: the notification tests, the DataDome cookie grab, and the
two optional-browser installers.

**Secrets never leave the backend in clear text.** `get_settings` masks each one
and adds a `*_set` boolean beside it, and `update_settings` drops a value that
came back still masked — an untouched field must mean "keep the stored one",
never "erase it".
"""

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from .. import schemas
from ..config import DATA_DIR, load_settings, save_settings
from ..services import notifier, scheduler

router = APIRouter()


@router.get("/api/settings")
def get_settings():
    settings = load_settings()
    if settings.get("telegram_bot_token"):
        token = settings["telegram_bot_token"]
        settings["telegram_bot_token"] = token[:6] + "..." if len(token) > 6 else token
        settings["telegram_token_set"] = True
    else:
        settings["telegram_token_set"] = False
    # secrets never leave the backend in clear text
    settings["smtp_password_set"] = bool(settings.get("smtp_password"))
    settings["smtp_password"] = "***" if settings.get("smtp_password") else ""
    settings["datadome_cookie_set"] = bool(settings.get("datadome_cookie"))
    settings["datadome_cookie"] = "***" if settings.get("datadome_cookie") else ""
    settings["scrape_api_key_set"] = bool(settings.get("scrape_api_key"))
    settings["scrape_api_key"] = "***" if settings.get("scrape_api_key") else ""
    settings["llm_api_key_set"] = bool(settings.get("llm_api_key"))
    settings["llm_api_key"] = "***" if settings.get("llm_api_key") else ""
    # Both halves are secret, and both are reported: an API key saved without
    # its secret is not configured, and the UI has to be able to say so.
    settings["idealista_api_key_set"] = bool(settings.get("idealista_api_key"))
    settings["idealista_api_key"] = "***" if settings.get("idealista_api_key") else ""
    settings["idealista_api_secret_set"] = bool(settings.get("idealista_api_secret"))
    settings["idealista_api_secret"] = "***" if settings.get("idealista_api_secret") else ""
    # whether the optional browser automation is installed, so the UI can show
    # the "grab it for me" button instead of a paste-only field
    from ..services import cookie_harvester

    settings["datadome_harvester_available"] = cookie_harvester.is_available()
    settings["camoufox_available"] = cookie_harvester.is_camoufox_available()
    return settings


@router.put("/api/settings")
def update_settings(data: schemas.SettingsIn):
    values = data.model_dump(exclude_none=True)
    # do not overwrite secrets with their masked versions
    if values.get("telegram_bot_token", "").endswith("..."):
        values.pop("telegram_bot_token")
    if values.get("smtp_password") == "***":
        values.pop("smtp_password")
    if values.get("datadome_cookie") == "***":
        values.pop("datadome_cookie")
    if values.get("scrape_api_key") == "***":
        values.pop("scrape_api_key")
    if values.get("llm_api_key") == "***":
        values.pop("llm_api_key")
    if values.get("idealista_api_key") == "***":
        values.pop("idealista_api_key")
    if values.get("idealista_api_secret") == "***":
        values.pop("idealista_api_secret")
    save_settings(values)
    if "scan_interval_minutes" in values:
        scheduler.reschedule(int(values["scan_interval_minutes"]))
    return get_settings()


@router.post("/api/settings/datadome-refresh")
def datadome_refresh(
    portal: str = Query("immobiliare", pattern="^(immobiliare|idealista)$"),
):
    """Opens a local browser to harvest a fresh DataDome cookie and saves it.

    Headful (visible) on purpose: the user triggered it and is present, so if
    the portal shows a CAPTCHA they can solve it once — the persistent profile
    then remembers it. Sync `def` so FastAPI runs the minutes-long browser work
    in a threadpool without owning the event loop (same reasoning as the
    availability check, invariant 15)."""
    from ..services import cookie_harvester

    if not cookie_harvester.is_available():
        raise HTTPException(400, cookie_harvester.UNAVAILABLE_MESSAGE)
    result = cookie_harvester.refresh_into_settings(portal, headless=False)
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result


@router.post("/api/settings/datadome-refresh/cancel")
def cancel_datadome_refresh():
    """Stops a running "Grab a fresh cookie now" at its next poll (a hard
    block page with no solvable widget otherwise polls for the full headful
    timeout with the visible window stuck open, invariant 16/18). A no-op if
    nothing is running."""
    from ..services import cookie_harvester

    cookie_harvester.request_cancel_harvest()
    return {"ok": True}


# pip + a browser download: minutes, not forever. A hung index/mirror must
# not pin a threadpool worker for the process lifetime.
_INSTALL_TIMEOUT_SECONDS = 900


def _require_loopback(request: Request) -> None:
    """The install endpoints run `pip install` and download browser binaries:
    that is code execution on the host, and the API has no authentication.
    On the loopback bind (the default) this is moot; under `serve.bat lan`
    (0.0.0.0) or a Tailscale bind it would let any device on the network
    install arbitrary packages into the venv with one POST — so these two
    endpoints, alone, insist the caller is the local machine."""
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(
            403,
            "Installation endpoints only work from the PC running the "
            "app (open the dashboard on http://127.0.0.1:8000)",
        )


@router.post("/api/settings/install-harvester")
def install_harvester(request: Request):
    """Install Playwright package and download Chromium binary into the active virtual environment."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    from ..services import cookie_harvester

    _require_loopback(request)
    if cookie_harvester.is_available():
        return {"ok": True, "message": "Playwright is already installed and available."}

    try:
        # 1. Install playwright pip package into current Python environment (.venv)
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "playwright"],
            check=True,
            timeout=_INSTALL_TIMEOUT_SECONDS,
        )

        # 2. Configure where to install browser binary: the current user's
        # existing ms-playwright cache when there is one (resolved via the
        # environment, never by iterating C:/Users — on a multi-profile
        # machine that picks whichever profile sorts first), else a
        # project-local folder.
        browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        if not browsers_path:
            if os.name == "nt":
                local_appdata = os.environ.get("LOCALAPPDATA")
                local = Path(local_appdata) if local_appdata else Path.home() / "AppData" / "Local"
                candidate = local / "ms-playwright"
                if candidate.exists():
                    browsers_path = str(candidate)
            if not browsers_path:
                # The data directory, not the bundle: a packaged app's code
                # lives in a temp folder that is wiped on exit, and a ~150 MB
                # browser download would be re-fetched every single run.
                browsers_path = str(DATA_DIR / "browser_binaries")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path

        env = os.environ.copy()
        if browsers_path:
            env["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path

        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            env=env,
            timeout=_INSTALL_TIMEOUT_SECONDS,
        )

        cookie_harvester._ensure_browsers_path()
        return {"ok": True, "message": "Successfully installed Playwright and Chromium."}
    except Exception as e:
        logging.getLogger(__name__).exception("Failed to install playwright/chromium")
        raise HTTPException(500, f"Installation failed: {type(e).__name__}: {e}") from e


@router.post("/api/settings/install-camoufox")
def install_camoufox(request: Request):
    """Install Camoufox (stealth Firefox) and fetch its browser binary into the
    active virtual environment. Optional upgrade over Chromium: it hides the
    automation signals DataDome fingerprints, so the check is challenged less."""
    import subprocess
    import sys

    from ..services import cookie_harvester

    _require_loopback(request)
    try:
        if not cookie_harvester.is_camoufox_available():
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "camoufox"],
                check=True,
                timeout=_INSTALL_TIMEOUT_SECONDS,
            )
        # Downloads the patched Firefox (~150 MB) once; a no-op if already present.
        subprocess.run(
            [sys.executable, "-m", "camoufox", "fetch"],
            check=True,
            timeout=_INSTALL_TIMEOUT_SECONDS,
        )
        return {
            "ok": True,
            "message": "Successfully installed Camoufox. Set the engine to auto or camoufox in Settings.",
        }
    except Exception as e:
        logging.getLogger(__name__).exception("Failed to install camoufox")
        raise HTTPException(500, f"Installation failed: {type(e).__name__}: {e}") from e


@router.post("/api/settings/telegram-test")
def telegram_test():
    ok = notifier.send_test_message("telegram")
    if not ok:
        raise HTTPException(
            400,
            "Send failed: verify token, chat ID, and that notifications are enabled",
        )
    return {"ok": True}


@router.post("/api/settings/email-test")
def email_test():
    ok = notifier.send_test_message("email")
    if not ok:
        raise HTTPException(
            400,
            "Send failed: verify SMTP host/credentials, recipient, and that "
            "email notifications are enabled",
        )
    return {"ok": True}
