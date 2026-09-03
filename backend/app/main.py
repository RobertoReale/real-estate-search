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
from urllib.parse import urlparse

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


# Methods a page on another site can send here without the browser asking
# permission first. A plain `<form method="post">` submits as
# `application/x-www-form-urlencoded`, which is a "simple request": no preflight,
# so the `allow_origins` list above never gets a say, and the response being
# unreadable cross-origin does not stop the *request* from happening. Every /api
# route that takes no body was therefore reachable from any page the user
# happened to have open — `POST /api/maintenance/reset/factory` empties the
# dashboard, `POST /api/scrapers/trigger` spends the user's own residential IP on
# the portals. The bind address cannot answer this one (invariant 14): the
# browser making the request is on the loopback interface.
_CROSS_SITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Every origin this app is legitimately driven from is on this machine. The
# packaged app, `serve.bat` and the phone all load the SPA from the API's own
# origin (invariant 13), and the two Vite servers — dev on 5173, `vite preview`
# proxying the browser suite — are loopback. A page on the public web can be
# neither, and `Origin` is set by the browser itself, so a script cannot claim
# otherwise.
_LOCAL_ORIGIN_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _is_same_site(request: Request) -> bool:
    """May this request change something?

    An absent `Origin` is allowed on purpose: curl, a script, the test client.
    What is being guarded here is a *browser* forging a request in the user's
    session, and a browser always states its origin on the methods above — so no
    header at all is not the case this exists for, and refusing it would break
    every non-browser client for no gain.
    """
    origin = request.headers.get("origin", "")
    if not origin:
        return True
    parsed = urlparse(origin)
    if parsed.netloc and parsed.netloc == request.headers.get("host", ""):
        return True
    return parsed.hostname in _LOCAL_ORIGIN_HOSTS


@app.middleware("http")
async def reject_cross_site_writes(request: Request, call_next):
    """Refuse a state-changing /api call that came from another site.

    One header, checked before the route ever runs. It costs the legitimate
    clients nothing — they are all same-origin or loopback — and it is the only
    thing standing between "the API answers only on loopback" and a web page
    quietly factory-resetting the database of anyone who visits it while the app
    is running.
    """
    if request.method in _CROSS_SITE_METHODS and request.url.path.startswith("/api/"):
        if not _is_same_site(request):
            return JSONResponse(
                {
                    "detail": "This request came from another site and was refused. "
                    "Use the dashboard on this machine."
                },
                status_code=403,
            )
    return await call_next(request)


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
        # by character — on the ENCODED bytes, because compare_digest refuses
        # str arguments that are not pure ASCII. An accented token ("segretò"
        # is an entirely natural choice here) therefore raised TypeError out of
        # the middleware and turned every single /api request into a 500,
        # including the settings call the user would need to undo it.
        if not hmac.compare_digest(provided.encode("utf-8"), f"Bearer {token}".encode()):
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
