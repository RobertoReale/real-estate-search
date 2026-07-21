"""Application configuration: paths, defaults, and settings persisted to JSON file."""

import json
from datetime import UTC, datetime
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
    "nl_parser_backend": "deterministic",  # deterministic | llm
    "llm_base_url": "",  # OpenAI-compatible base, e.g. http://localhost:11434/v1
    "llm_api_key": "",  # blank for a local Ollama server
    "llm_model": "",  # e.g. "llama3.1" / "qwen2.5" / "gpt-4o-mini"
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
    # Agency names whose "AGENCY: ..." prefixes the repair maintenance strips
    # from imported titles (services/repair_listings.py). Seeded with the
    # agencies met so far so behavior is unchanged on existing data; a user in
    # another market appends their local agencies here instead of editing code.
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
# users paste them verbatim. smtplib/imaplib forward the spaces to the server,
# which answers with an opaque AUTHENTICATIONFAILED. No provider allows spaces
# in a password, so stripping them can only help.
_SPACELESS_SECRETS = (
    "smtp_password",
    "imap_password",
    "telegram_bot_token",
    "datadome_cookie",
    "scrape_api_key",
    "llm_api_key",
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
