"""Quick backend startup: python run.py

Binds to loopback unless APP_HOST says otherwise. That default is a safety
choice, not an oversight: the API has no authentication, so any host that can
reach the port can read the database and rewrite the settings. Widen it only to
an interface you trust — a Tailscale address (100.x.y.z) exposes the dashboard
to your own devices anywhere, while 0.0.0.0 exposes it to the whole LAN,
guests on the Wi-Fi included.
"""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("APP_HOST", "127.0.0.1"),
        port=int(os.environ.get("APP_PORT", "8000")),
        # opt-in: start.bat sets it for local development; serve.bat (phone
        # access) has no use for a file watcher
        reload=os.environ.get("APP_RELOAD", "0") == "1",
    )
