"""Waits for the backend to answer, then opens the dashboard in the browser.

`start.bat` runs the server in the foreground so that one window is the whole
application — closing it stops the app. That leaves nobody to open the browser
*after* the server is listening, and opening it before produces a connection
error on first run, when migrations and the startup backup can take a few
seconds. So this runs alongside: it polls the port and opens the page the
moment it answers.

Polling the port rather than sleeping a fixed number of seconds because the
delay is not constant - a large `case.db` with a pending Alembic upgrade is
slow exactly once, on the run where a stale guess would be most annoying.
"""

import os
import socket
import sys
import time
import webbrowser

TIMEOUT_SECONDS = 60.0
POLL_INTERVAL = 0.3


def wait_for_server(host: str, port: int, timeout: float = TIMEOUT_SECONDS) -> bool:
    """True once something accepts a connection on host:port, False on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            probe.settimeout(1.0)
            if probe.connect_ex((host, port)) == 0:
                return True
        time.sleep(POLL_INTERVAL)
    return False


def main() -> int:
    # The same environment variables run.py reads, so `APP_PORT=9000 start.bat`
    # opens the right page instead of a hardcoded 8000.
    port = int(os.environ.get("APP_PORT", "8000"))
    host = os.environ.get("APP_HOST", "127.0.0.1")
    # 0.0.0.0 is a bind address, not somewhere a browser can go.
    reachable = "127.0.0.1" if host in ("0.0.0.0", "::") else host

    if not wait_for_server(reachable, port):
        print(
            f"[WARN] The backend did not answer on {reachable}:{port} within "
            f"{TIMEOUT_SECONDS:.0f}s - not opening the browser. "
            "The server window above says why.",
            file=sys.stderr,
        )
        return 1

    webbrowser.open(f"http://{reachable}:{port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
