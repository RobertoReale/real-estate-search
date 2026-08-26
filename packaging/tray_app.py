"""Entry point for the packaged Windows app: a tray icon that owns the server.

There is no terminal window. The backend runs on a daemon thread, and the tray
icon is the whole user interface to the process — open the dashboard, open the
data folder, quit. Quitting through the menu is a clean shutdown, which matters
more here than it does for a console: SQLite is mid-WAL most of the time, and
the previous "close the black window" gesture was a kill.

**Adoption runs before anything else imports.** `app.main` configures logging
against `config.LOG_PATH` and `app.database` builds its engine from
`config.DB_PATH` at import time, so a database adopted after those imports
would be adopted into a path nobody is looking at any more.

The bind address stays loopback unless `APP_HOST` says otherwise (invariant 14):
packaging must not quietly widen an unauthenticated API to the network.
"""

import logging
import os
import sys
import threading
import webbrowser
from pathlib import Path

import pystray
import uvicorn
from PIL import Image

from app import config

logger = logging.getLogger(__name__)

HOST = os.environ.get("APP_HOST", "127.0.0.1")
PORT = int(os.environ.get("APP_PORT", "8000"))
# 0.0.0.0 is a bind address, not somewhere a browser can go.
BROWSABLE_HOST = "127.0.0.1" if HOST in ("0.0.0.0", "::") else HOST
DASHBOARD_URL = f"http://{BROWSABLE_HOST}:{PORT}"


def _icon_image() -> Image.Image:
    """The PWA icon the dashboard already uses, reused rather than redrawn."""
    return Image.open(Path(config.BASE_DIR) / "packaging" / "icon-512.png")


def _alert(title: str, message: str) -> None:
    """A message box, because a packaged app has no console to print to."""
    if os.name == "nt":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)  # pyright: ignore[reportAttributeAccessIssue]
    else:  # pragma: no cover - the package is Windows-only; Docker is the other target
        print(f"{title}: {message}", file=sys.stderr)


def main() -> int:
    # Before app.main and app.database are imported by uvicorn below.
    adopted = config.adopt_existing_data()

    server = uvicorn.Server(uvicorn.Config("app.main:app", host=HOST, port=PORT, log_config=None))
    thread = threading.Thread(target=server.run, daemon=True, name="uvicorn")
    thread.start()

    import open_dashboard  # bundled from scripts/, where start.bat uses it too

    def _first_open() -> None:
        if open_dashboard.wait_for_server(BROWSABLE_HOST, PORT):
            webbrowser.open(DASHBOARD_URL)
            return
        # The usual cause is another copy already running on this port - which
        # also means the dashboard the user wanted is already open somewhere.
        _alert(
            "Real Estate Search",
            f"The application could not start on port {PORT}.\n\n"
            "It is most often already running - check the notification area - "
            f"or another program is using the port. Set APP_PORT to choose "
            f"a different one.\n\nDetails are in:\n{config.LOG_PATH}",
        )

    threading.Thread(target=_first_open, daemon=True, name="open-dashboard").start()

    def _quit(icon: pystray.Icon) -> None:
        # Ask uvicorn to shut down and give it a moment to finish the request it
        # may be serving, rather than dropping the process on a live WAL write.
        server.should_exit = True
        thread.join(timeout=10)
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Open dashboard", lambda: webbrowser.open(DASHBOARD_URL), default=True),
        pystray.MenuItem("Open data folder", lambda: _open_folder(config.DATA_DIR)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", _quit),
    )
    tooltip = f"Real Estate Search - {DASHBOARD_URL}"
    if adopted:
        logger.info("adopted an existing database from %s", adopted)

    pystray.Icon("realestatesearch", _icon_image(), tooltip, menu).run()
    return 0


def _open_folder(path: Path) -> None:
    """Shows the user where their database and settings actually live.

    Packaged, that is no longer next to the program, so without this the answer
    is a support question rather than a menu item.
    """
    if os.name == "nt":
        os.startfile(path)  # pyright: ignore[reportAttributeAccessIssue]
    else:  # pragma: no cover - Windows-only package
        webbrowser.open(path.as_uri())


if __name__ == "__main__":
    raise SystemExit(main())
