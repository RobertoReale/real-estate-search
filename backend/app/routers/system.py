"""Operating the running process itself: restarting it, and reading its log.

Both exist because the app is often running with no terminal to reach — under
`serve.bat`, the NSSM service, or the packaged tray app. Without them, "apply
this update" and "is the check actually doing anything?" would both require
hunting for a console window that does not exist.

`LOG_PATH` comes from config: it follows the data directory, not the code, so a
packaged app writes its log somewhere the user can actually reach it.
"""

import logging
import os
import threading

from fastapi import APIRouter, HTTPException

from .. import schemas
from ..config import BASE_DIR, LOG_PATH
from ..services.scanner import scan_state

router = APIRouter()


def relaunch_argv(executable: str, argv: list[str]) -> list[str]:
    """The argv to hand `os.execv` so the process comes back.

    Windows has no real `execv`: the CRT joins the list into a single command
    line with spaces and quotes nothing, so one space anywhere in the path
    splits that element into two arguments. The replacement interpreter then
    took "C:\\Users\\Mario Rossi\\...\\python.exe" as "C:\\Users\\Mario" plus a
    stray script name, failed to open it, and exited — the backend went down and
    never came back. A space in the path is the ordinary case on Windows
    (`C:\\Program Files`, most user folders), and this is the one route whose
    whole purpose is being usable when there is no terminal to recover from.

    Pre-quoting each element is what survives that join. POSIX passes the list
    through untouched, where quotes would become part of the argument.
    """
    parts = [executable, *argv]
    if os.name != "nt":
        return parts
    return [f'"{part}"' for part in parts]


@router.post("/api/system/restart", response_model=schemas.RestartOut)
def system_restart():
    """Restart the backend process so a code update takes effect without hunting
    for the terminal window.

    Two paths, because `start.bat` runs uvicorn with `APP_RELOAD=1` (a file
    watcher) while `serve.bat` and a plain `run.py` do not:

    * reload on  -> touch a watched source file; uvicorn's own reloader kills and
      respawns the worker cleanly. Re-exec here would fight that supervisor and
      risk a port clash, so we let it do its job.
    * reload off -> re-exec the current process (`python run.py`), which rebinds
      the port fresh.

    Refused mid-scan (409): a scan writes the DB and the ListingProfile links,
    and yanking the process out from under it would leave them half-written —
    same guard the destructive resets use. The restart is deferred a beat so this
    HTTP response reaches the browser before the process goes down; the UI then
    polls until the API answers again and reloads itself.
    """
    if scan_state["running"]:
        raise HTTPException(409, "A scan is running: wait for it to finish before restarting")
    import sys
    import time

    reload_on = os.environ.get("APP_RELOAD") == "1"

    def _restart():
        time.sleep(0.5)  # let the response flush to the client first
        try:
            if reload_on:
                (BASE_DIR / "app" / "main.py").touch()
            else:
                os.execv(sys.executable, relaunch_argv(sys.executable, sys.argv))
        except Exception:
            logging.getLogger(__name__).exception("restart failed")

    threading.Thread(target=_restart, daemon=True).start()
    return {"ok": True, "reload": reload_on}


@router.get("/api/logs/tail", response_model=schemas.LogTailOut)
def logs_tail(lines: int = 200):
    """Last N lines of the running backend's own log file, for the dashboard's
    log viewer: without this, "is the check actually doing anything?" could
    only be answered by opening app.log in a text editor. Reads the whole
    current file rather than seeking from the end, which is fine at the
    1 MB `RotatingFileHandler` cap this project uses.

    Plain default (not `Query(..., ge=1, le=2000)`): this module's tests call
    endpoint functions directly rather than through TestClient (invariant-free
    of the real scheduler that the app lifespan would start), and a `Query`
    sentinel only resolves to a value through FastAPI's own dependency
    injection.
    """
    lines = max(1, min(lines, 2000))
    if not LOG_PATH.exists():
        return {"lines": [], "path": str(LOG_PATH)}
    with open(LOG_PATH, encoding="utf-8", errors="replace") as f:
        all_lines = f.read().splitlines()
    return {"lines": all_lines[-lines:], "path": str(LOG_PATH)}
