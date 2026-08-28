"""Application configuration: paths, defaults, and settings persisted to JSON file.

**Two roots, and the difference matters.** `BASE_DIR` is where the code and its
read-only assets live; `DATA_DIR` is where the user's own data lives. In a
source checkout they are the same folder (`backend/`), which is why the split
went unnoticed for so long — packaging is what separates them. Under
PyInstaller the code is unpacked into a temporary directory that is **deleted
when the app exits**, so a `case.db` resolved against it would take the user's
entire price history with it on every quit, silently, and the app would open
empty the next morning with nothing to recover.

`DATA_DIR` therefore resolves, in order:

1. `APP_DATA_DIR`, when set — the explicit answer, and what the Docker image
   points at its volume.
2. A per-user application-data folder, when frozen. Not the folder next to the
   executable: an app installed under `C:\\Program Files` cannot write there.
3. `BASE_DIR` otherwise, so an existing development checkout keeps reading and
   writing exactly the `backend/case.db` it always has.
"""

import json
import logging
import os
import shutil
import sqlite3
import sys
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _is_frozen() -> bool:
    """True inside a PyInstaller bundle, where `__file__` is a temp directory."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def _bundle_dir() -> Path:
    if _is_frozen():
        return Path(str(getattr(sys, "_MEIPASS"))).resolve()
    return Path(__file__).resolve().parent.parent  # backend/ folder


def _default_data_dir(bundle: Path) -> Path:
    if not _is_frozen():
        return bundle
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        root = Path(local) if local else Path.home() / "AppData" / "Local"
        return root / "RealEstateSearch"
    xdg = os.environ.get("XDG_DATA_HOME")
    return (Path(xdg) if xdg else Path.home() / ".local" / "share") / "real-estate-search"


def _resolve_data_dir(bundle: Path) -> Path:
    override = os.environ.get("APP_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return _default_data_dir(bundle)


BASE_DIR = _bundle_dir()
DATA_DIR = _resolve_data_dir(BASE_DIR)

# SQLite will not create a missing parent directory, and neither will the
# settings writer. Fail-open: an unwritable location must surface as the real
# error from whoever tries to use it, not as an import that never completes.
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except OSError:  # pragma: no cover - depends on filesystem permissions
    logger.warning("could not create the data directory %s", DATA_DIR)

DB_PATH = DATA_DIR / "case.db"
SETTINGS_PATH = DATA_DIR / "settings.json"
LOG_PATH = DATA_DIR / "app.log"
BACKUP_DIR = DATA_DIR / "backups"
# Playwright's persistent profile: browser state the user has earned (a solved
# DataDome CAPTCHA lives here), so it belongs with their data, not the bundle.
BROWSER_PROFILE_DIR = DATA_DIR / "browser_profile"

# Production build of the React app. When present the backend serves it at "/",
# so phones reach dashboard and API on a single origin (no Vite, no CORS).
# Absent in the dev flow, where Vite serves the app on :5173 and proxies /api.
# Packaged, it is copied into the bundle beside the code it is served by.
FRONTEND_DIST = (BASE_DIR if _is_frozen() else BASE_DIR.parent) / "frontend" / "dist"


def _copy_database(source: Path, target: Path) -> None:
    """Copies a database through SQLite's backup API, never as a file copy.

    Under WAL the newest commits sit in `case.db-wal` until a checkpoint, so
    copying the one file drops however much of the recent history has not been
    folded back in yet. The backup API reads them together and takes a
    consistent snapshot even if something else is mid-write — the same reason
    `services/backup.py` uses it.
    """
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)


def _legacy_data_candidates() -> list[Path]:
    """Folders that may hold a database from before this install.

    Only meaningful when frozen: a source checkout already reads its own
    `backend/` and has nothing to adopt. The executable's own folder comes
    first because dropping `case.db` next to the program is what someone
    carrying their data across does without being told to.
    """
    if not _is_frozen():
        return []
    exe_dir = Path(sys.executable).resolve().parent
    return [exe_dir, exe_dir / "backend", exe_dir.parent / "backend"]


def adopt_existing_data(
    data_dir: Path | None = None, candidates: list[Path] | None = None
) -> Path | None:
    """Adopts a previous install's `case.db` when the data directory has none.

    Returns the folder adopted from, or None when there was nothing to do. Call
    it once, before anything opens the database or reads the settings.

    The alternative — starting empty next to a perfectly good database — is the
    single most expensive way this packaging step can fail: the price history
    it would abandon is months of daily readings the portals themselves do not
    keep, and nothing in the UI would suggest the data still exists on disk.
    """
    data_dir = DATA_DIR if data_dir is None else data_dir
    candidates = _legacy_data_candidates() if candidates is None else candidates

    target = data_dir / "case.db"
    if target.exists():
        return None  # live data: never overwrite it, whatever else is lying around

    for source_dir in candidates:
        source = source_dir / "case.db"
        if not source.is_file() or source_dir.resolve() == data_dir.resolve():
            continue
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            _copy_database(source, target)
        except (OSError, sqlite3.Error):
            # A candidate that cannot be read is not a reason to give up: the
            # next one may be the real database.
            logger.warning("could not adopt the database at %s", source, exc_info=True)
            target.unlink(missing_ok=True)
            continue

        # The settings carry the Telegram token and the DataDome cookie, so
        # leaving them behind would mean a working database with no way to
        # notify and a scraper that has to earn its cookie again.
        settings_source = source_dir / "settings.json"
        if settings_source.is_file() and not (data_dir / "settings.json").exists():
            try:
                shutil.copy2(settings_source, data_dir / "settings.json")
            except OSError:
                logger.warning("adopted the database but not the settings at %s", settings_source)

        logger.info("adopted an existing database from %s", source_dir)
        return source_dir

    return None


DEFAULT_EXCLUDED_KEYWORDS = [
    "nuda proprietà",
    "nuda proprieta",
    "asta giudiziaria",
    "asta",
    "seminterrato",
    "piano terra",
]

DEFAULT_SETTINGS = {
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "telegram_enabled": False,
    # Inline buttons (favourite / seen / hide / map) on every property
    # notification, and the long poll that collects the presses
    # (services/telegram_bot.py). On by default, because buttons that arrive
    # without a poller behind them would do nothing when tapped — the two are
    # one feature. Turning it off restores plain notifications and closes the
    # poll, which is the switch for anyone who would rather the backend held no
    # standing connection to api.telegram.org.
    "telegram_actions_enabled": True,
    # email channel (SMTP): works with any provider; for Gmail use an
    # app-specific password on port 587
    "email_enabled": False,
    "smtp_host": "",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_password": "",
    "email_from": "",
    "email_to": "",
    "scan_interval_minutes": 60,
    # Global pause for automatic (scheduled) scans. When on, the scheduler's
    # scans return immediately without touching the portals — the point is to
    # rest the residential IP DataDome watches (e.g. while away) without having
    # to deactivate every profile one by one. A manual "Scan now" is explicit
    # intent and bypasses it (see scanner.run_scan's `manual` flag).
    "scanning_paused": False,
    # Smart Match Score ("dream home"): an offline, weighted compatibility
    # percentage shown on each card. Off by default — with nothing configured
    # there is nothing to score against, so no badge appears. Every numeric
    # preference uses 0 to mean "no constraint" (a None would be unclearable,
    # since the settings PUT drops None-valued fields). Keywords are desired
    # features matched in the listing text; zones are preferred city/zone names.
    "match_score_enabled": False,
    "dream_max_price": 0,
    "dream_min_rooms": 0,
    "dream_min_sqm": 0,
    "dream_min_floor": 0,
    "dream_keywords": [],
    "dream_zones": [],
    # Natural-language search assistant backend. "deterministic" (default) is
    # the hand-written offline parser (services/query_parser.py); "llm" routes
    # the query through an OpenAI-compatible chat endpoint that returns the same
    # structured params, then FALLS BACK to the deterministic parser on any
    # failure. Point llm_base_url at Ollama (http://localhost:11434/v1) for a
    # free, fully-offline local model, or at a free cloud tier. See IMPROVEMENTS.md.
    # Geocoding endpoint for the opt-in "backfill missing map coordinates"
    # maintenance action (services/geocoder.py). Public Nominatim by default
    # (1 request/second, cached so a batch stays inside it); point it at a
    # self-hosted instance for unlimited, fully-offline use.
    "nominatim_url": "https://nominatim.openstreetmap.org",
    # Commute times to the places the user actually goes (services/commute.py).
    # Off by default: with no saved place there is nothing to route to, so no
    # badge appears — the same stance as the Smart Match Score above. Each point
    # is {"name", "address" or "lat"/"lng", "mode"}; an address is resolved once
    # through the ordinary geocoder and remembered in its cache. `mode` is
    # car | foot | bike.
    "commute_enabled": False,
    "commute_points": [],
    # OSRM routing endpoint. The public demo server is a courtesy instance built
    # on the DRIVING network alone: it accepts the walking and cycling profiles
    # and answers with car routing, so "on foot" is only truly on foot against a
    # self-hosted OSRM — which is what this setting is for.
    "osrm_url": "https://router.project-osrm.org",
    "nl_parser_backend": "deterministic",  # deterministic | llm
    "llm_base_url": "",  # OpenAI-compatible base, e.g. http://localhost:11434/v1
    "llm_api_key": "",  # blank for a local Ollama server
    "llm_model": "",  # e.g. "llama3.1" / "qwen2.5" / "gpt-4o-mini"
    # Opt-in reading of a listing's own text by that same model
    # (services/listing_auditor.py): the costs the price does not include, a
    # sitting tenant, the condition, the weak points worth raising in a
    # negotiation. Off by default and never automatic — only the button on a
    # property's card spends a request, so a scan is untouched by this. It
    # reuses llm_base_url/llm_api_key/llm_model above rather than a second
    # endpoint: there is one model to configure, not two.
    "listing_audit_enabled": False,
    "excluded_keywords": DEFAULT_EXCLUDED_KEYWORDS,
    "request_delay_seconds": 6.0,
    "max_pages_per_search": 10,
    # Scraper health alerting: notify after this many *consecutive* failed
    # scans of the same profile. A single blocked scan is a transient
    # DataDome 403, not a broken scraper — alerting on it trains the user to
    # ignore the alerts. 0 disables health alerting entirely.
    "health_alert_after_failures": 3,
    "proxy_url": "",
    # Optional residential proxy pool. `proxy_url` stays as the one-element
    # shorthand; this list adds IP diversity: each scraper session sticks to one
    # proxy, and a block puts that proxy in a cool-down so the next session (or
    # the next TLS rotation) exits through a different IP. DataDome scores IP
    # reputation, so burning one address must not burn them all. Empty list +
    # empty proxy_url = direct connection, exactly today's behavior.
    "proxy_urls": [],
    # Optional scraping API that solves DataDome server-side (Scrapfly /
    # ScraperAPI / Zyte). Unlike a proxy these are not transparent: the scraper
    # POSTs the *target* URL to the provider and gets back the solved HTML, so
    # every existing parser is untouched. Empty key = the local curl_cffi/
    # browser path stays in charge (the free, offline default). This trades the
    # residential-IP fragility (invariants 8/16/18) for a paid — but free-tier-
    # capable — dependency.
    "scrape_api_provider": "scrapfly",  # scrapfly | scraperapi | zyte
    "scrape_api_key": "",
    # How the configured scrape API is spent (scrapers/transport_policy.py).
    # "fallback" (default) = each scan starts on the free local path and
    # escalates to the paid API only when blocked (mid-scan, after the TLS
    # rotation is exhausted) or when the profile's failure streak says the
    # local path is down (transport_escalate_after_failures) — the cost-aware
    # ladder: free path in good weather, the provider's success rate only
    # during an actual outage. "always" = a set key routes every fetch through
    # the provider unconditionally.
    "scrape_api_mode": "fallback",  # fallback | always
    "transport_escalate_after_failures": 2,
    # Idealista's official Search API (developers.idealista.com), the one
    # transport that asks the portal for its own data instead of working around
    # its anti-bot. Both halves empty (the default) = the HTML scraper alone,
    # exactly today's behavior; a key issued to you plus its secret turns on the
    # second engine described in scrapers/idealista_api.py, which still falls
    # back to the scraper for any search it cannot express faithfully.
    "idealista_api_key": "",
    "idealista_api_secret": "",
    # Search requests one profile scan may spend on that API. Deliberately NOT
    # max_pages_per_search: keys are issued by hand with a per-key ceiling that
    # is published nowhere, so the default spends one request (50 listings) per
    # profile scan and the user raises it once they know their own budget.
    "idealista_api_max_pages": 1,
    # TLS impersonation override (advanced). Empty = use each scraper's built-in,
    # empirically-ordered list (invariant 8). A non-empty list of curl_cffi
    # profile names (e.g. ["safari260", "safari184"]) replaces it for every
    # scraper; unsupported names are silently filtered at runtime, so this is the
    # zero-code way to rotate handshakes when a new DataDome wave lands.
    "tls_impersonations": [],
    "datadome_cookie": "",
    # Automatic DataDome cookie refresh via a local browser (optional, needs
    # Playwright — see services/cookie_harvester.py). Opt-in: a scan must not
    # launch a browser the user never asked for. updated_at/ttl let the scanner
    # decide when the cookie is stale enough to re-harvest before a scan.
    "datadome_auto_refresh": False,
    "datadome_cookie_updated_at": "",
    "datadome_cookie_ttl_minutes": 50,
    # Availability check transport. When on, the "is this ad still online?"
    # batch runs entirely through a persistent headless browser (Playwright)
    # instead of curl_cffi, so it earns a real DataDome cookie once and reuses
    # it — no per-ad 403 on the residential IP. Opt-in like every unattended
    # browser launch (invariant 18); degrades to curl_cffi if Playwright is
    # absent. Slower per ad, but it does not get interrupted by blocks.
    "availability_browser_first": False,
    # Availability check: open the browser VISIBLE so a CAPTCHA can be solved by
    # hand. The check is user-triggered (they click "check online" and watch the
    # progress bar), so unlike a scan a person is present — invariant 18's "every
    # unattended launch is headless" still holds. One manual solve mints a real
    # DataDome cookie in the shared persistent profile, so the rest of the batch
    # flows without further challenges. Ignored when running as a Windows service
    # (session 0 has no interactive desktop): it degrades to headless.
    "availability_browser_headful": False,
    # Which browser engine the optional browser paths (cookie grab, availability
    # check) use. "auto" (default) prefers Camoufox — a stealth Firefox build
    # that hides the automation signals DataDome fingerprints, so it is
    # challenged far less often — when the package is installed, and falls back
    # to Chromium otherwise (so installing Camoufox is itself the opt-in).
    # "chromium" pins the current behaviour; "camoufox" forces it (and still
    # falls back to Chromium if the launch fails, e.g. its browser is unfetched).
    "browser_engine": "auto",
    # Human-like mouse movement + a small scroll on every browser-path page
    # (scrapers/humanize.py): DataDome scores behavior too, and a bare goto()
    # produces zero pointer events — itself a bot tell. Default on because the
    # browser rung is already opt-in and the cost is ~0.5-1.5s per page, well
    # inside the probe's pacing (invariant 16). Off pins the bare-goto behavior.
    "browser_humanize": True,
    # Agency names whose branding marks a title as boilerplate rather than a
    # description of the property (services/listing_text.py `is_bad_title`, so
    # the availability check may replace it with the ad page's og:title).
    # Seeded with the agencies met so far so behavior is unchanged on existing
    # data; a user in another market appends their local agencies here instead
    # of editing code.
    "repair_agency_prefixes": [
        "affiliato",
        "gabetti",
        "tempocasa",
        "studio quattro",
        "strategie immobiliari",
        "dhome real estate",
        "cosetta fiori",
    ],
    # Optional shared-secret API token. Empty (default) = the API is open and
    # the bind address is the only access control (invariant 14). A non-empty
    # value requires every /api request to carry `Authorization: Bearer <token>`,
    # which makes a wider bind (LAN, Tailscale) safe to expose. Returned in clear
    # to an already-authenticated caller so the Settings UI can show/clear it —
    # emptying the field disables auth again.
    "api_auth_token": "",
}


def load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    if SETTINGS_PATH.exists():
        try:
            settings.update(json.loads(SETTINGS_PATH.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return settings


# Gmail shows app passwords as four groups of four ("abcd efgh ijkl mnop") and
# users paste them verbatim. smtplib forwards the spaces to the server,
# which answers with an opaque AUTHENTICATIONFAILED. No provider allows spaces
# in a password, so stripping them can only help.
_SPACELESS_SECRETS = (
    "smtp_password",
    "telegram_bot_token",
    "datadome_cookie",
    "scrape_api_key",
    "llm_api_key",
    "idealista_api_key",
    "idealista_api_secret",
)


def save_settings(new_values: dict) -> dict:
    settings = load_settings()
    # The updated_at timestamp is metadata about the cookie, so it follows the
    # cookie wherever the new value comes from. Without this, a cookie pasted
    # by hand kept the old timestamp: the UI showed a stale "Last refreshed"
    # and the auto-refresh (cookie_harvester.maybe_auto_refresh) judged the
    # fresh paste stale and launched a browser for nothing on the next scan.
    # The harvester passes its own timestamp explicitly, which wins below.
    if new_values.get("datadome_cookie") and "datadome_cookie_updated_at" not in new_values:
        new_values = {
            **new_values,
            "datadome_cookie_updated_at": datetime.now(UTC).isoformat(),
        }
    settings.update({k: v for k, v in new_values.items() if k in DEFAULT_SETTINGS})
    for key in _SPACELESS_SECRETS:
        value = settings.get(key)
        if isinstance(value, str):
            settings[key] = "".join(value.split())
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    return settings
