"""Application configuration: paths, defaults, and settings persisted to JSON file."""
import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/ folder
DB_PATH = BASE_DIR / "case.db"
SETTINGS_PATH = BASE_DIR / "settings.json"
# Production build of the React app. When present the backend serves it at "/",
# so phones reach dashboard and API on a single origin (no Vite, no CORS).
# Absent in the dev flow, where Vite serves the app on :5173 and proxies /api.
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"

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
    # email channel (SMTP): works with any provider; for Gmail use an
    # app-specific password on port 587
    "email_enabled": False,
    "smtp_host": "",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_password": "",
    "email_from": "",
    "email_to": "",
    # email inbox import (IMAP, strictly read-only): lets the user mine years
    # of portal alert emails for listings; for Gmail use imap.gmail.com with
    # the same app-password mechanism as SMTP
    "imap_host": "",
    "imap_port": 993,
    "imap_user": "",
    "imap_password": "",
    # Opt-in periodic inbox re-scan (piggybacks on APScheduler). Off by default:
    # a scan opens an IMAP connection, and the app must not reach into the user's
    # mailbox on a schedule they never asked for. Newly staged listings wait
    # silently in the review queue — nothing enters the dashboard without an
    # explicit accept (invariant 12), so there is nothing to notify about.
    "email_import_auto_scan": False,
    "email_import_auto_scan_interval_hours": 24,
    "scan_interval_minutes": 60,
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
    "excluded_keywords": DEFAULT_EXCLUDED_KEYWORDS,
    "request_delay_seconds": 6.0,
    "max_pages_per_search": 10,
    # Scraper health alerting: notify after this many *consecutive* failed
    # scans of the same profile. A single blocked scan is a transient
    # DataDome 403, not a broken scraper — alerting on it trains the user to
    # ignore the alerts. 0 disables health alerting entirely.
    "health_alert_after_failures": 3,
    "proxy_url": "",
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
# users paste them verbatim. smtplib/imaplib forward the spaces to the server,
# which answers with an opaque AUTHENTICATIONFAILED. No provider allows spaces
# in a password, so stripping them can only help.
_SPACELESS_SECRETS = ("smtp_password", "imap_password", "telegram_bot_token", "datadome_cookie")


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
            "datadome_cookie_updated_at": datetime.now(timezone.utc).isoformat(),
        }
    settings.update({k: v for k, v in new_values.items() if k in DEFAULT_SETTINGS})
    for key in _SPACELESS_SECRETS:
        value = settings.get(key)
        if isinstance(value, str):
            settings[key] = "".join(value.split())
    SETTINGS_PATH.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return settings
