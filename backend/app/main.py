"""FastAPI entrypoint: the app object, its middleware, the order the routers are
registered in, and the static frontend mount.

The routes themselves live in `app/routers/`, one module per cohesive group.
What stays here is everything that is true of the *application* rather than of
one group of endpoints — and the registration order, which is load-bearing twice
over (see the two comments below).
"""

import hmac
import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import FRONTEND_DIST, LOG_PATH, load_settings
from .database import init_db
from .routers import (
    analytics,
    maintenance,
    profiles,
    properties,
    scans,
    searches,
    settings,
    system,
)
from .services import scheduler, telegram_bot

# Log both to console and rotating file: the scheduler runs overnight without
# anyone at the terminal, and without a log file it would be impossible to diagnose
# why a scan failed afterwards.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            LOG_PATH,
            maxBytes=1_000_000,
            backupCount=2,
            encoding="utf-8",
        ),
    ],
)
# Alembic's plugin-setup chatter at INFO floods app.log on every startup and
# buries the scan/probe lines the file exists to preserve.
logging.getLogger("alembic").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.start_scheduler()
    # Started unconditionally: the thread idles while Telegram is off, which is
    # what lets the notification buttons start working the moment the user
    # enables them, without a backend restart (services/telegram_bot.py).
    telegram_bot.start_polling()
    yield
    telegram_bot.stop_polling()
    scheduler.shutdown()


app = FastAPI(title="Real Estate Search", lifespan=lifespan)

# Only the Vite dev server needs CORS. The phone loads the built app from this
# same origin (see the StaticFiles mount at the bottom), so serving remote
# clients never requires widening this list — keep it that way.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_api_token(request: Request, call_next):
    """Optional shared-secret gate on /api (invariant 14 relaxed to "bind
    address **or** token").

    Off entirely when `api_auth_token` is empty — nothing changes for the
    loopback-only default. When set, every /api request must carry
    `Authorization: Bearer <token>`; the static SPA and any non-/api route stay
    open so the app can load and present its login prompt, and CORS preflight
    (OPTIONS, which browsers send without the header) is never blocked.
    """
    token = (load_settings().get("api_auth_token") or "").strip()
    if token and request.method != "OPTIONS" and request.url.path.startswith("/api/"):
        provided = request.headers.get("Authorization", "")
        # constant-time compare so a wrong token cannot be timed out character
        # by character
        if not hmac.compare_digest(provided, f"Bearer {token}"):
            return JSONResponse(
                {"detail": "Authentication required: provide the API token."},
                status_code=401,
            )
    return await call_next(request)


# --- Routers ---
#
# Starlette matches in registration order, so this list is the app's route
# table. Nothing here collides across modules (each owns its own /api prefix),
# but the order *within* `properties` does — its literal paths have to precede
# `/api/properties/{property_id}`, which is why that module keeps them in one
# deliberate sequence and says so.
app.include_router(properties.router)
app.include_router(profiles.router)
app.include_router(searches.router)
app.include_router(analytics.router)
app.include_router(scans.router)
app.include_router(maintenance.router)
app.include_router(settings.router)
app.include_router(system.router)


# --- Static frontend (must stay last) ---
#
# Mounting at "/" makes this a catch-all, so it has to be declared after every
# API route or it would shadow them — which now means after every
# `include_router` call above, not merely after the last `@app.get`. The failure
# is silent: the app still starts, still serves the dashboard, and answers 404
# for every /api request. `html=True` serves index.html for "/" and resolves the
# hashed asset names Vite emits.
#
# The mount is conditional because `frontend/dist` only exists after
# `npm run build`: in the dev flow Vite serves the app itself and the backend
# is API-only. A missing dist is therefore normal, not an error.
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:
    logging.getLogger(__name__).info(
        "frontend/dist not found: serving API only. Run `npm run build` in "
        "frontend/ to serve the dashboard from this port too."
    )
