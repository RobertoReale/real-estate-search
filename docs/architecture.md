# Architecture

How this program is put together, and **where to act** for each kind of change.

A local platform (Windows PC / Raspberry Pi) that monitors real estate listings —
sale and rental — on **Immobiliare.it** and **Idealista**, deduplicates identical
properties published several times by different agencies, filters by keywords, and
notifies via Telegram and Email. Stack: **Python 3.11 + FastAPI + SQLite** (backend),
**React + Vite + Tailwind 4** (frontend). No cloud service is required: everything runs
on `localhost`.

Companion documents:

- [`invariants.md`](invariants.md) — the twenty-two rules that must not break, each with
  the regression it prevents. Every "invariant N" below refers to that file.
- [`conventions.md`](conventions.md) — how code is written here, and how it is tested.
- [`audit.md`](audit.md) — the procedure for a full-project health check.
- [`../implementation_plan.md`](../implementation_plan.md) — the historical record: why
  the design is what it is.

> Before modifying the scrapers or the deduplication logic, read
> [§8 of `implementation_plan.md`](../implementation_plan.md#8-deviations-from-original-plan).
> It lists the "obvious" assumptions that turned out to be false on real portals. Every
> regression described there has an automated test covering it.

---

## Where to Act for Each Type of Modification

| You want to modify… | File | Notes |
|---|---|---|
| REST Routes / API | `backend/app/routers/<group>.py` | One module per cohesive group — `properties` (grid, card, curation, tags, export, availability), `profiles`, `searches` (URL builder + NL assistant), `analytics`, `scans`, `maintenance`, `settings`, `system` — each owning an `APIRouter` and writing its paths **in full** (no `prefix=`), so a URL is still greppable from its decorator. `main.py` keeps only what is true of the *application*: file logging, CORS, the auth middleware, the `include_router` order and the static mount. **Adding a route means picking the module its neighbours live in**, not starting a new one; a genuinely new group gets a module *and* an `include_router` line above the mount (invariant 13) |
| Property selection for grid / map / export | `backend/app/routers/selection.py` | `select_properties` is the single query+annotation path all three go through, which is what keeps a dossier mirroring the screen. Not a router: it lives in `routers/` rather than `services/` because it answers in HTTP terms (an unknown `profile_id` is a 404, a malformed `poly` a 400). Also owns `annotate`/`annotate_provenance` and the floor-band matcher |
| Bind address / port | `backend/run.py` | `APP_HOST`/`APP_PORT`; loopback by default (API is unauthenticated) |
| PWA manifest & icons | `frontend/public/` | copied verbatim into `dist/` by Vite |
| DB Models | `backend/app/models.py` | additive columns auto-migrate: see below |
| SQLite engine / connection PRAGMAs | `backend/app/database.py` | `make_engine` is the **only** place an engine is built — production and the test fixtures alike, so a hand-rolled engine cannot silently lack the PRAGMAs. `SessionLocal` is a **function**, not a bound `sessionmaker`: it reads the module-global `engine` on every call, so `engine` is the single symbol that decides which database the app talks to. Bound at import it froze one engine into `scanner`/`scheduler`'s `from ..database import SessionLocal`, out of reach of any patch. See the concurrency note below |
| Non-additive schema changes (rename/drop/retype) | `backend/alembic/versions/` | `alembic revision --autogenerate`; applied at startup by `database._run_migrations()` |
| Request/Response schemas | `backend/app/schemas.py` | Pydantic v2 |
| Settings & defaults | `backend/app/config.py` | persisted in `settings.json` inside `DATA_DIR` (see the row below) |
| Where user data lives (DB, settings, log, backups, browser profile) | `backend/app/config.py` (`BASE_DIR` vs `DATA_DIR`) | **Two roots, and confusing them destroys data.** `BASE_DIR` = code and read-only assets (`sys._MEIPASS` when frozen, else `backend/`); `DATA_DIR` = the user's own files. In a source checkout they are the same folder, which is why the split went unnoticed until packaging — under PyInstaller `BASE_DIR` is a **temp directory deleted on exit**, so a `case.db` resolved against it would take the entire price history with it every quit, silently. `DATA_DIR` resolves: `APP_DATA_DIR` env → per-user app data when frozen (`%LOCALAPPDATA%\RealEstateSearch`) → `BASE_DIR` otherwise (so existing checkouts are untouched). Everything the user owns hangs off it: `DB_PATH`, `SETTINGS_PATH`, `LOG_PATH`, `BACKUP_DIR`, `BROWSER_PROFILE_DIR`, and the `browser_binaries` lookup. Migration scripts and `comuni.sqlite` are code, so they stay on `BASE_DIR`. `adopt_existing_data()` copies a previous install's `case.db` in when the data dir has none — **through SQLite's backup API**, never a file copy, or the un-checkpointed WAL would be dropped; it never overwrites an existing database. `test_data_dir.py` pins all of it |
| Immobiliare scraping | `backend/app/scrapers/immobiliare.py` | api-next JSON is the **primary** path (tried first, stable schema); HTML strategies 1-3 are the fallback safety net. Reactive opt-in cookie recovery on a 403 (`_recover_cookie`, invariant 18) |
| Idealista scraping | `backend/app/scrapers/idealista.py` | currently heuristic parsing (strategy #3) works |
| Idealista's **official API** (optional second engine) | `backend/app/scrapers/idealista_api.py` + the `get_scraper` branch in `scrapers/__init__.py` | `idealista_api_key` + `idealista_api_secret` (both, or it is not configured) swap `get_scraper("idealista")` for `IdealistaApiScraper` — a **subclass** of `IdealistaScraper`, so the fallback *is* the real scraper rather than a second copy of it. OAuth2 client-credentials, one process-wide cached token, plain `urllib` (no anti-bot to impersonate, no new dependency). **The faithfulness rule: it serves a search only when every filter in the URL maps to an API parameter whose meaning is known**, and falls back otherwise — `UNMAPPED_FILTERS` lists what it declines and why. Rooms are the case to remember: this codebase counts *locali*, the API filters `bedrooms`, and "locali − 1" is an inference, which §8.12 of `implementation_plan.md` is the standing warning about. Location travels as `center`+`distance` from `geo_reference.city_search_area` (no offline `locationId`), so results are narrowed back to the comune by the API's own `municipality` — a circle otherwise reaches into neighbouring comuni the portal page never shows. Fail-open at every step (refused key, quota, malformed payload, **zero results**) → the scraper answers, since only it can read the portal's own "nothing matched" page. Budget: `idealista_api_max_pages` **defaults to 1**, deliberately not `max_pages_per_search` — the per-key request ceiling is agreed by hand and published nowhere. `transport_policy.transport_used` reports `"idealista official API"` so the health panel names the engine that actually served the scan |
| Common scraping infrastructure | `backend/app/scrapers/` (split by concern: `transport.py` TLS+proxies+scrape-API, `parsing.py` price/sqm/rooms/contract, `page_text.py` gone/empty/block predicates, `html_cards.py` card boundary, `base.py` the scrape pipeline, `probe.py` AdProbe) | TLS client, price/sqm parser, card boundaries; injects `datadome_cookie` and a proxy from settings. `ProxyPool` (module singleton `proxy_pool`) merges `proxy_urls` + the legacy `proxy_url` into one pool: one proxy per session (sticky), a block cools it down (`_rotate_session` burns it), the next session exits elsewhere; all cooling → least-recently-burned, **never silently direct** |
| End-to-end test of the whole flow (or teaching the sandbox a new portal) | `backend/tests/mock_portal.py` + `tests/test_offline_sandbox.py` | Both portals on loopback HTTP, the notification on loopback SMTP, `run_scan` driven with nothing stubbed. A new portal is one row in `PORTAL_URL_ATTRS` (the absolute URLs its scraper *requests*) plus a page renderer. See [`conventions.md` → Testing](conventions.md#testing) for what must stay true |
| A populated dashboard without a scan (demo corpus) | `backend/app/services/demo_data.py` + `scripts/seed_demo.py` | Eighty properties across eight Milan districts, both contracts, `active`/`gone`/`hidden`, twelve of them found on both portals, price drops, favourites, tags, a missing photo, a missing pin, and three monitored searches in the three health states the panel can show — written into an **empty** database in about a second, where a scan takes forty minutes and needs the portals to answer. Seeded, so the same corpus every run (that is what lets a browser test or a screenshot compare against it); the timestamps are offsets from `now` rather than fixed dates, or the newest listing would age into an abandoned dashboard and days-on-market would grow without limit — pass `now` to pin those too. **Refuses a database that already holds anything** (`DatabaseNotEmpty`, exit 1 from the script): invented rows merged into real listings cannot be separated again. Everything is invented — addresses assembled from two word lists, agencies, ad ids — with nothing copied or derived from a scraped database or an OMI delivery, because this code ships in the repository and in the release bundle. Ad and search URLs sit on the RFC 2606 `.invalid` host and the photos travel *inside* the row as SVG data URIs, so the corpus renders with the network unplugged and neither a click nor a "Scan now" on demo data can reach a portal. Built through the ORM, never SQL, which is what keeps it from drifting from the schema: `Tag` needs `name_normalized` (the tag filter matches on it), `PriceHistory` is `old_price`/`new_price`/`changed_at`, `gone_at` is the **last sighting** and not the day it was noticed (`scanner._mark_vanished_properties`), and `fingerprint` comes from `deduplicator.fingerprint_for` so a demo property carries exactly the value a scan would have stamped |
| Transport choice (free path vs paid scrape API) | `backend/app/scrapers/transport_policy.py` | Pure decisions (no network), like the scheduler's helpers. `decide(consecutive_failures, settings)`: no key → local; `scrape_api_mode="fallback"` (default) → start local, escalate to the API on the invariant-11 streak (`transport_escalate_after_failures`) or mid-scan when `fetch()` exhausts the local ladder (`use_scrape_api` flips once); `"always"` → key routes everything unconditionally. Recovery descends automatically: the streak resets, the next `decide` is local again. NB: the scan path only — AdProbe/on-demand checks keep a set key always-on (`BaseScraper.use_scrape_api` class default) |
| Scraper health history (block-rate trend) | `backend/app/services/scraper_health.py` + `ScraperHealthSnapshot` (`models.py`) | `record_scan` accumulates each profile scan into today's per-portal row (upsert-accumulate, NOT once-per-day like PricingSnapshot: a block *rate* needs every scan counted); fail-open, never takes a scan down. `GET /api/scraper-health` + `frontend/src/components/ScraperHealth.tsx` (dependency-free panel, like PriceTrends) |
| Italian comuni gazetteer (city detection + pin plausibility) | `backend/app/services/geo_reference.py` + `backend/app/data/comuni.sqlite` | Offline index of all ~7,900 ISTAT comuni with GeoNames centroids (~830 KB, committed like a fixture; regenerate with `scripts/build_comuni_dataset.py`, dev-only). `detect_city` is layered: the user's own profile cities first, then the index (longest n-gram match, single tokens < 4 chars ignored — "Re" VB collides with everything); returns `""` when unsure, **never a default**. `is_plausible_coordinate` = Italy bbox + distance from the comune centroid ≤ a per-comune radius scaled on its postal-code count (Milano ≈ 12 km rejects the historical Cernusco mis-pin; a village floors at 8 km); unknown/ambiguous comune (Castro BG vs LE) degrades to bbox-only, exactly the old boxes' default |
| Scraping-API transport (optional) | `backend/app/scrapers/transport.py` (`build_scrape_api_request`/`unwrap_scrape_api_response`) + `base.py` (`_fetch_via_scrape_api`) | When `scrape_api_key` is set AND the scraper's `use_scrape_api` is on, `_fetch_once` routes each page through Scrapfly/ScraperAPI/Zyte (they solve DataDome and return the target HTML), so every parser is unchanged; empty key keeps the local curl_cffi/browser path. `use_scrape_api` defaults True (a set key = today's always-on behavior, and what AdProbe keeps); the scanner sets it per profile from `transport_policy.decide` (see that row). Relaxes invariants 8/16/18 for the remote path — those guard the *local*, residential-IP transport |
| Natural-language parsing with a language model (optional) | `backend/app/services/llm_parser.py` | Behind `nl_parser_backend="llm"`; OpenAI-compatible (`llm_base_url`/`llm_api_key`/`llm_model`, e.g. local Ollama). Returns the SAME `{"searches":[…]}` shape as `query_parser` via the shared `build_search_entry`, and **falls back to the deterministic parser on any failure** — the default path is untouched. Dispatched by `query_parser.parse_query_auto`. `chat_completion`/`extract_json` are public because `listing_auditor` reads them too — one OpenAI-compatible client in this project, not two |
| Reading a listing's own text (optional) | `backend/app/services/listing_auditor.py` + `PropertyAudit` (`models.py`) + `POST/GET /api/properties/{id}/audit` + the panel in `PropertyModal.tsx` | Behind `listing_audit_enabled` (default off) on the **same** endpoint as the row above; **never automatic** — only the card's button spends a request, so no scan, grid render or batch can reach a model. What comes back is bounded before it is stored (`_clean_audit`: fixed vocabularies for `condition`/`tenant`, `MAX_ITEMS`/`MAX_ITEM_CHARS` on each list) because a card renders it straight, and the prompt names "unknown" and the empty list as the correct answers — a model that *invents* a defect is worse than no auditor, which is also why the panel carries the disclaimer and says which model read it. Cached in `PropertyAudit` keyed by a sha256 of the exact text sent (plus the model name): re-opening a card is free, a rewritten ad is flagged `stale` and re-read rather than answered from a row about text nobody can see. The GET reads that row and only that row — the same cache-only/paid-press split as the commute annotation. The audit dies with its property: ORM cascade, plus an explicit `delete(PropertyAudit)` in `data_reset`'s two Core-delete paths (the `property_tags` trap) |
| Geocoding missing map coordinates | `backend/app/services/geocoder.py` + `GeocodeCache` | Opt-in `POST /api/maintenance/geocode-missing`: batched, paced (Nominatim 1 req/s), **caches every lookup incl. misses**, fail-open (a failed lookup never writes a wrong pin). `nominatim_url` is self-hostable for offline use. `geocode_property` is the single-property, on-demand path (shares `geocode()`'s cache/fail-open) behind `POST /api/properties/{id}/geocode`, backing the card's "View on map" jump — not gated by the batch's `_geocode_run_lock`, and it passes `retry_negative=True` so it re-asks a *cached miss* instead of stranding a resolvable address behind a stale NULL (a transient empty Nominatim answer becomes a permanent miss for the paced batch, which keeps its rate budget; the on-demand path spends at most a couple of requests, so it can afford to retry). `clear_geocode_cache(misses_only=True)` (behind `POST /api/maintenance/geocode-clear-cache`, UI's "🧹 Retry failed lookups" next to Find coordinates) drops the stuck NULL rows so the *batch* re-asks them too, keeping the paid-for positive lookups; touches only the lookup cache, never a property's coordinates |
| Commute time to the user's saved places | `backend/app/services/commute.py` + `CommuteCache` (`models.py`) + `frontend/src/components/settings/CommuteSection.tsx` | Travel time/distance from each pin to the places the user actually goes (`commute_points`: name + address-or-pin + mode car/foot/bike; `commute_enabled` off by default). **The annotation is cache-only** — `annotate_commutes` runs inside `select_properties` on every grid page, so it must never route; filling the cache is the user-triggered `POST /api/maintenance/commutes` batch (paced 1 req/s, `MAX_PER_CALL` budget, progress + cancel + clear-cache endpoints), exactly the split `geocoder.py` makes. A saved place given as an address is resolved through **`geocoder.geocode`**, never a second address→coordinates path. One **`/table`** request per (property, mode) — OSRM answers a whole one-to-many matrix at once, so N places cost 1 request, not N. Fail-open: a routed "no way through" caches a NULL row, a *transport* failure caches nothing so a later run retries. `osrm_url` is self-hostable, and **must be** for real walking/cycling times — the public demo server is built on the driving network alone and answers 200 for `/walking/` with car routing (§8.16 of `implementation_plan.md`) |
| OMI quotations (the benchmark from outside the app) | `backend/app/services/omi_import.py` + `OmiQuotation` (`models.py`) + `POST /api/maintenance/omi-import` | Min/max €/m² per micro-zone from the Agenzia delle Entrate's Osservatorio, derived from **recorded transactions** — the one price reference here that is not the app's own scraped asking prices, which is what makes the deal judgement non-circular. **There is deliberately no downloader**: the supply is behind a SPID-authenticated session, so the owner requests it once a semester and the importer reads it from `omi_input_dir`. Four traps, all measured against the real 2025/2 delivery and all silent when got wrong — **line 1 is a title and the header is line 2** (a `DictReader` aimed at the file names every column after a sentence), **the semester exists only in that title line**, **semicolons + a trailing separator + decimal commas** (`35,1` is 35.1; stripping the comma gives 351), and **`LinkZona` is not the join key** — it is populated in the CSV and empty in the KML perimeters, so joining on it matches nothing and reports no error; the pair that joins is `Comune_amm` + `Zona`. One source row carries both contracts (`Compr_*`, `Loc_*`) and becomes up to two rows. Malformed rows are **skipped and counted, never fatal**, and the endpoint always reports both numbers — a partial import that named only its successes would look exactly like a complete one. Re-importing a semester replaces it wholesale; two semesters coexist and `latest_semester`/`find_quotations` never mix them. **Nothing is ever derived from the delivery's filenames**: the Agenzia names each one after the requester's codice fiscale, so the two files are told apart by their title line, and no path reaches a message or a log line |
| Placing a property in its OMI zone | `backend/app/services/omi_zones.py` + `OmiZone` (`models.py`) + `Property.omi_municipality_code`/`omi_zone_code` + `POST /api/maintenance/omi-zones-import` and `/omi-zones-resolve` | The perimeters the quotations' `zone_code` names, so coordinates can be turned into a zone — without them that table is one nothing can be looked up in. KML, and **only in the national supply**: a municipal delivery has the prices and no geometry. Ray casting is `geo_filter.point_in_rings`, reusing the map filter's own — **not `shapely`**, whose GEOS is a compiled library and this app is frozen into a PyInstaller bundle. Measured against the real 2025/2 delivery: **7 887 files, ~28 000 zones, ~340 MB of geometry**, so the import keeps only the comuni that already have quotations (a perimeter with no price behind it can produce no benchmark) — Milan alone is 43 zones and 254 KB. Run it *after* the quotations; with none imported it answers 400 saying so. Three traps from that delivery: **two files declare UTF-8 and are not** (an accent in the comune name), and `ET.parse` on the path loses the other 7 885 with them, so the bytes are decoded leniently first; **a zone is a `MultiGeometry` with holes**, not one ring, and a parser that stops at the first is wrong only at addresses nobody checks; **the semester is in the document title alone**, exactly as in the CSV. Replacement is per semester and total, two coexist, newest wins. **The placement is persisted and only the batch writes it** — same cache-only rule as the commute annotation, and the reason a grid page does no geometry at all. Fail open: no coordinates, or a pin in no zone, means no benchmark and no error |
| Showing the two price benchmarks | `backend/app/services/omi_benchmark.py` + `PropertyOut.omi_*` (`schemas.py`) + `frontend/src/components/PropertyModal.tsx` (`PriceBenchmarks`) + `exporter.py` `_print_facts` | Turns a placed property into the OMI band for its zone and hands it to the screen **beside** the listing median, never merged into it (invariant 22): one is what comparable ads *ask*, the other what the tax authority records sales at, and asking sits systematically above transacted. `annotate_omi_benchmark` sets the transient `omi_min_sqm_price`/`omi_max_sqm_price`/`omi_semester` and is called from `routers/selection.py` **before** the deal score, which reads them for one extra reason line and nothing else — score, label and proposal range are computed from the median exactly as they were before OMI existed. **The band is the envelope of the zone's residential rows** (lowest min to highest max, `RESIDENTIAL_TYPE_CODES` = the `Cod_Tip` values measured in the real delivery: 1, 19, 20, 21): a zone also quotes Box, Negozi and Uffici, and a flat benchmarked against garages is a coincidence, not a reference. The app knows neither an ad's OMI tipologia nor its conservation state, so picking one (type, state) row would be precision this data cannot support — the range is wide because the recorded reality is. One query per page, newest semester only, and every rendering carries the semester: an undated band is a claim with no expiry. Fail open — nothing imported, or a property in no zone, means no benchmark and no error |
| Map zone filter (radius / polygon) | `backend/app/services/geo_filter.py` + `select_properties` (`routers/selection.py`) + `frontend/src/components/MapView.tsx` | Pure, offline geometry (`haversine_m`, `point_in_polygon` ray-casting with on-edge = inside, `parse_polygon` codec). Drawn on the map, but it only produces filter params (`center_lat`/`center_lng`/`radius_m` **or** `poly="lat,lng;…"`, mutually exclusive) that enter the shared `select_properties` post-filter — so grid, map and export show the same set (the "dossier mirrors the screen" convention). A malformed `poly` is an explicit 400 (`parse_poly_param`), never a silently-ignored filter. **Properties with NULL coordinates always drop out** — they can't be placed in a zone — which is the silent asymmetry invariant 19 warns about: `MapView` shows a persistent banner + the "N without coordinates" chip while a zone is active, with a **Find coordinates** button wired to the batch geocoder |
| Restart the backend from the UI | `backend/app/routers/system.py` (`POST /api/system/restart`) | Settings → *Restart backend*. Two paths: `APP_RELOAD=1` (dev.bat) → touch a watched source file so uvicorn's reloader respawns cleanly; reload off (start.bat / serve.bat / plain run.py / the packaged tray app) → `os.execv` the process. **Kept deliberately** rather than retired with the tray app: serve.bat and the NSSM service both run with no terminal to hunt for, so it is their only in-app way to apply an update. Verified against the frozen build — it re-execs, the API comes back, and exactly one tray process remains (no orphaned icon). Refused mid-scan (409), deferred a beat so the HTTP response flushes first; the UI (`components/settings/SystemSection.tsx`) then polls `getScanStatus` until the API answers and reloads |
| API auth token (optional) | `backend/app/main.py` (`require_api_token` middleware) | `api_auth_token` empty = open (invariant 14 unchanged); set = every `/api` request needs `Authorization: Bearer <token>`. Static SPA + non-`/api` stay open so the app can load and show the prompt (`frontend/src/components/AuthGate.tsx`); OPTIONS preflight never blocked. Token returned in clear to an authenticated caller so Settings can show/clear it. **The header is the only channel**, so anything the browser reaches by *navigating* rather than fetching has to be routed through an authenticated request instead — that is why the dossier export has a second path (row below) |
| Automatic DataDome cookie | `backend/app/services/cookie_harvester.py` | OPTIONAL Playwright browser that harvests+saves the cookie; opt-in, fail-open, persistent profile |
| Browser behavioral humanization ("ghost cursor") | `backend/app/scrapers/humanize.py` | Bézier mouse paths + a small scroll on every browser-path page (probe check, headful solve, cookie harvest) — DataDome scores behavior, and a bare `goto()` emits zero pointer events. Pure geometry (`bezier_path`, hypothesis-tested) + fail-open glue: any exception is swallowed (invariant 16), `browser_humanize` (default on) pins the old bare-goto path when off. Vendored on purpose — the Python ghost-cursor ports are stale or drag in a patched Playwright |
| Browser engine seam | `backend/app/scrapers/browser_engine.py` | `BrowserEngine` Protocol (open/content/title/url/cookies/humanize/wait/close) — the minimum surface the availability check and the cookie harvest need, so a future non-Playwright stealth engine (Nodriver, SeleniumBase-CDP) is a drop-in adapter, not a fork of the block/gone/cookie logic. `PlaywrightEngine` wraps today's Camoufox/Chromium ctx+page; `cookies()` is non-optional (the harvest must export the DataDome cookie the curl path reuses). Add engines only when the Scraper Health block-rate justifies the cost |
| Deduplication rules | `backend/app/services/deduplicator.py` | read docstring BEFORE tweaking thresholds |
| Keyword filtering | `backend/app/services/filter_engine.py` | word boundaries, accent-insensitive |
| Property tags (user categories) | `backend/app/models.py` (`Tag`, `property_tags`), `routers/properties.py` (`/api/tags` CRUD, `PropertyPatch.tag_ids` full-replace, bulk `add_tag`/`remove_tag`) + the `tag=` filter in `routers/selection.py` | free-form, many-to-many, case-insensitive dedup on create; frontend `TagPicker.tsx` shared by `PropertyCard`/`PropertyModal`; user-curated like `is_favorite`/`notes` — never touched by scans |
| Scan orchestration | `backend/app/services/scanner.py` | notifications, statuses, "gone" marking, scraper health streak; `run_scan(manual=)` gates the global `scanning_paused` switch (automatic scans skip, a user-triggered "Scan now" bypasses) |
| Notifications (Telegram + Email) | `backend/app/services/notifier.py` | channel-based `broadcast()`; Bot API + stdlib smtplib, no external library. `telegram_api()` is the single Bot API entry point (fail-open, returns the `result` or `None`), so sending and polling cannot drift apart. `property_keyboard()`/`map_url()` compose the inline buttons **here**, because a keyboard is part of composing the message — `reply_markup` rides through `broadcast()` to Telegram alone (email has no buttons) |
| Telegram inline buttons (the press side) | `backend/app/services/telegram_bot.py` | **Long poll, never a webhook**: a webhook needs an inbound port in front of an API whose access control *is* the loopback bind (invariant 14), so one daemon thread holds `getUpdates` (outbound only) and `main.lifespan` starts it. Presses dispatch through `routers.properties.bulk_properties` — the dashboard's own curation path — so ⭐/🚫 mean one thing, not two (invariants 5 and 10 hold in one place). Favourite and Hide are **toggles** and the keyboard is redrawn from the updated row after every press, or a day-old message starts lying about the property's state. **`seen` writes nothing on purpose**: the dashboard has no server-side seen concept (its "New" badge is a per-device `localStorage` threshold in `App.tsx`), so persisting one would invent a concept no screen shows. Only the configured `telegram_chat_id` may act. The thread idles and re-reads settings each pass rather than being restarted on a settings change — **two pollers on one token split the updates at random**, so there must only ever be one |
| Pricing statistics (€/sqm medians) | `backend/app/services/pricing_stats.py` | zone→city fallback, min 3 comparables, segmented by contract; also daily `PricingSnapshot` capture (`maybe_snapshot`) feeding the trend charts. `area_comparables` returns the listings behind an area's median for the chart's "show the listings" drill-down — necessarily the *current* set (a snapshot stores only median + count, never members); shares `_comparable_filter` with the median computation so membership can't drift. Backs `GET /api/pricing-trends/comparables` |
| UI: price trend charts | `frontend/src/components/PriceTrends.tsx` | dependency-free inline SVG; consumes `/api/pricing-trends`. "🔍 Show the listings behind this median" fetches `/api/pricing-trends/comparables` and opens each in the shared `PropertyModal` (via `onOpenProperty`); labeled as today's set, since past points keep no membership |
| Smart Match Score ("dream home") | `backend/app/services/match_score.py` | offline weighted %; annotated per request like pricing_stats; prefs in settings (`match_score_enabled`, `dream_*`) |
| Deal Score (congruity vs fair value) | `backend/app/services/deal_score.py` | €/sqm gap + condition cues + agency discount → score & proposal range; needs `annotate_market_position` first; also flagged in `notifier.notify_new_property` |
| Shortlist export (HTML/MD/CSV dossier + printable PDF) | `backend/app/services/exporter.py` | `GET /api/properties/export?fmt=`; reuses `select_properties` (`routers/selection.py`) so the file mirrors the grid; passes **no `limit`** — a dossier holds the whole filtered shortlist, not the page the grid is showing. Self-contained (inline CSS), offline bar remote thumbnails. **`fmt=pdf` ships no PDF engine, deliberately**: `properties_to_print_html` renders a paginated report (one property per page: gallery, key facts, price timeline, viewing checklist) that raises `window.print()` on load, and the browser's own *Save as PDF* writes the file. A server-side renderer would mean either a second layout in a foreign drawing model (reportlab/fpdf2) that drifts from this one, or a toolchain the frozen Windows build cannot carry (weasyprint wants GTK/Pango) — and it would have to **download the portal CDN photos**, i.e. portal traffic outside `AdProbe` on the residential IP the scans depend on. It is therefore the one format served **inline**, not as an attachment: a print-ready document that got saved instead of opened has printed nothing. `_gallery_urls`/`_history_rows`/`_fmt_date` are shared helpers, not a fork of the card renderer. On the frontend, `FiltersBar` normally just **navigates** to that URL (`window.open` for the PDF, a transient anchor for the rest) and lets the browser name and save the file. That breaks the moment `api_auth_token` is set — a navigation carries no `Authorization` header, so every export met the middleware's 401 and the dossier arrived as a page of JSON — so when a token is present, and only then, the export goes through `services/api.ts`'s `fetchExport`: the **same** `exportUrl`, fetched authenticated and handed to the browser as a blob keeping the response's own filename |
| Grid pagination + the dashboard poll | `backend/app/routers/selection.py` (`select_properties`) + `routers/properties.py` (`list_properties`) + `routers/scans.py` (`_properties_version`) + `frontend/src/App.tsx` | `GET /api/properties` answers `{items,total,limit,offset}` (`schemas.PropertyPage` ↔ `types/index.ts` `PropertyPage`), default `limit=50`, **`limit=0` = everything**. The window is applied **last, in Python, after the post-filters and the sort** — floor band, price drops, merged-only, the €/sqm band, the drawn zone, `deal=` and `sort=match` all live outside SQL, so a statement-level `LIMIT` would page over the *pre-filter* set: holed pages, a `total` counting invisible rows, an order that shifts as pages arrive. Market position and deal score are annotated **on the page only** unless `deal=` is filtering (then they must exist for every candidate first) — they are per-property lookups, so the values are identical either way. The **map and "select all" ask for `limit=0`**: a map missing pins past the first page is not a map, and a "select all" that quietly meant "select the loaded 60" would betray its own label. Those are deliberate clicks; the *poll* was the ceiling. **Polling is split from data**: the dashboard polls `/api/scrapers/status`, which carries a `data_version` fingerprint (`_properties_version`: per-status counts + max id + max `last_seen_at` + newest price-history id), and refetches the grid only when it moves. Per-status counts, not one total — hiding a property leaves `count(*)` unchanged while removing it from the grid |
| Market velocity (days-on-market, agencies) | `backend/app/services/market_velocity.py` | reads `Property.gone_at`; same min-3-sample rule |
| Natural-language search assistant | `backend/app/services/query_parser.py` | deterministic and offline **by default**; multi-alternative ("o"/"oppure") + zones; output feeds the search builder. An **optional** language-model backend (`nl_parser_backend="llm"`, see `llm_parser.py`) emits the same shape and falls back here on failure — the deterministic path stays the default and is never disturbed |
| Search URL generation | `backend/app/services/search_builder.py` | structured params → portal URLs; **offline and pure except `resolve_idealista_url`**. **Every portal token in here is measured, never inferred — see the rules below before adding one.** Idealista nests zones under a macro-area (`/vendita-case/milano/fiera-de-angeli/fiera/`, three levels, both live); `/milano/forlanini/` works because Forlanini *is* a macro-area, while `/milano/bovisa/` 404s because its macro-area is not derivable from the name. So `resolve_idealista_url` probes `/city/<name>/` **once**, when the user presses Generate (`verify=true` on `POST /api/search-builder`; off elsewhere, since the UI also re-derives URLs to prefill forms). **Only a positive answer buys the zone page** — 404, block and timeout all fall back to `/cerca/<base>/con-<filters>/<Zone_City>/`, which always answers but is a *text* search, so it is broader (Forlanini: 220 vs 124) and the UI says which one it got. A plain city keeps the canonical `municipality-province` page. `cerca_location`/`split_cerca_location` are the shared codec — `idealista._city_from_url` parses `/cerca/` back with them. **`/multi/…/aOA,aOw/` (opaque zone ids) and `/aree/?shape=` (polygon) must yield NO city**: the ids once parsed as one, and a bogus city silently blocks every merge (invariant 1). Immobiliare zone slugs stay best-effort (api-next resolves them via autocomplete, invariant 7) |
| Portal filter tokens (`IDEALISTA_FEATURES`, `IMMOBILIARE_FLOORS`, …) | `backend/app/services/search_builder.py` | **Read the token off the portal's own UI; do not guess it.** Six spellings of `ascensore` all 404'd and "Idealista has no elevator filter" shaped a whole design — the portal writes `ascensori`. Four more guesses at an auction filter 404'd before its UI gave `aste_no`: the *syntax* was wrong (underscore, like `prezzo_380000`), not just the word. A 404 means "not this word", never "no such filter". Verify by watching the portal's **result total** move (`3.477 → 1.960` for `balcone`), never the card count (a page holds 30 either way), and put a **known-good control** in every sweep — one run reported the proven `ascensore=1` as fake because it was silently measuring a block page. Idealista 404s unknown tokens; Immobiliare **ignores** them and answers 200 unfiltered (invariant 7's shape). Only offer a filter once **both** portals' spellings are known: a filter applied to one side alone is the same silent asymmetry, in the direction `idealista_unsupported` cannot report — `piscina` and `ristrutturare` stayed unexposed for months for exactly this, until Immobiliare's query names (`piscina=1`, `stato=5`) were found by matching result totals (the portal renders them only as path segments, so they never surfaced as a query to read) |
| Duplicate-search prevention | `backend/app/services/search_validator.py` | `check_duplicate_profile` gates create/update in `routers/profiles.py` (409/400); `deduplicate_search_profiles` runs once at startup (`database.init_db`). Two searches are equal when normalized URL (trailing slash / `id`,`imm_source`,`pag` / query order stripped) AND normalized keywords (lowercased, sorted, deduped) match. Merging relinks `ListingProfile` to the oldest canonical profile — never drops provenance (invariant 20) |
| "Is this ad still online?" probe | `backend/app/scrapers/probe.py` (`AdProbe`) | a scraper reduced to its TLS session; fails open (`None` = unknown) |
| Dashboard availability batch | `backend/app/services/availability_check.py` | on-demand batch that drives `AdProbe` over `Property` listings (`GET/POST /api/properties/*/check-availability`); enforces every guard in invariant 16 (`_check_run_lock`, probe budget, block-streak abort, browser fallback, transport diagnostics). **Owns the pacing constants** (`MAX_CHECKS_PER_CALL`, `MIN_PROBE_DELAY`, `BLOCK_STREAK_ABORT`, `MAX_COOKIE_REFRESHES_PER_CHECK`) and `_try_cookie_recovery` — the values are measured, do NOT change or fork them. Its route is a sync `def` so the threadpool keeps `/check-progress` answerable while a minutes-long batch runs |
| Portal boilerplate in a title or zone | `backend/app/services/listing_text.py` | `is_bad_title` / `is_placeholder_zone`: does this text describe the property, or is it the portal's auto-generated "Appartamento in vendita a Milano, Milano"? Structural match (generic words + vendita/affitto + a place tail that must resolve to real comuni via `geo_reference.load_comuni`), never a list of known strings, and it **fails towards keeping** — an unrecognized tail means the text says something. Two readers: `availability_check` overwrites a placeholder title with the ad page's `og:title`, `geocoder` refuses to look up a placeholder zone. Agency branding also marks a title bad, from the settings-driven `repair_agency_prefixes` |
| Reattaching UTC to a datetime read back from SQLite | `backend/app/services/timeutils.py` | `as_utc` / `as_utc_or_none`. SQLite has no timezone type, so every aware datetime the ORM writes comes back **naive**, while anything just built in memory is aware — and `SessionLocal` uses `expire_on_commit=False`, so one session can hold both kinds in a single list. Comparing them raises `TypeError`. This lived as five hand-rolled copies (scanner, scheduler, availability check, market velocity, harvester); one copy forgetting the reattachment is a 500 in whichever screen it feeds, so it lives here once |
| Periodic scanning | `backend/app/services/scheduler.py` | APScheduler; catch-up scan on startup when the last scan is older than the interval |
| Automatic DB backup | `backend/app/services/backup.py` | two kinds of copy. `maybe_backup`: daily copy of `case.db` into `backend/backups/` (rotation: 14), checked at startup; `force=True` bypasses the throttle before a reset. `snapshot_before_migration`: taken by `database._snapshot_before_upgrade` *before* a pending migration runs, named `case-pre-<revision>.db` for the revision being left, and **exempt from the rotation** (see [Migrations](#migrations-additive-automatic--alembic-for-the-rest)) |
| Deleting a search "with its results" | `backend/app/services/data_reset.py` (`profile_results`/`delete_profile_results`) | attribution comes from `ListingProfile`, never from the search criteria; spares shared + curated (invariant 20) |
| User data resets ("start fresh") | `backend/app/services/data_reset.py` | scoped, irreversible wipes (`POST /api/maintenance/reset/{scope}`); **clearing the dashboard MUST re-arm `baseline_done=False` on every profile** (invariant 3) or the next scan notifies on every re-found listing; factory reset backs up first |
| UI: grid/filters/modals | `frontend/src/components/*.tsx` | state in `App.tsx`, API in `services/api.ts` |
| UI: the monitored-searches panel | `frontend/src/hooks/useSearchProfiles.ts` + `frontend/src/components/searchProfiles/*.tsx` | Same shape as the settings split: the hook owns the whole state machine (five mutually exclusive modes — closed/url/builder/assistant/multi — plus every mutation), and each file under `searchProfiles/` is one view over it. The panels take the whole hook object rather than a hand-picked slice: they are views over one machine, not reusable widgets, and twenty threaded props would only hide that. `SearchProfiles.tsx` is now just the mode switcher and the composition. **`constants.ts`'s `UNSUPPORTED_LABELS` must stay in step with `search_builder.idealista_unsupported`**, or the form promises a filter Idealista cannot apply |
| A setting's UI (add/move/remove a field) | `frontend/src/components/settings/<Section>.tsx` | One file per section (Telegram, Email, Scanning, Match, Commute, Assistant, Scraping, System), each exporting a `useXSection()` hook that owns its fields and a component that renders them. `SettingsModal.tsx` is only the shell: it loads once, hands each section its slice, and owns the three genuinely shared things — the busy marker, the feedback line, the save. A field is declared in **one** place: `useSectionState(initial, read, write)` in `settings/state.ts` pairs "how to seed it from `Settings`" with "how to send it back", so a new setting cannot be half-wired the way it could when 40 `useState` calls, a `hydrate` and a `payload` all had to be edited in step. **Secrets are write-only**: `read` returns `""` and `write` omits the key unless the field was typed into — an empty box means "keep the stored one", never "erase it". `sections.test.ts` pins the composed payload, because a key dropped from a `write` still renders, still saves 200, and just never persists |
| UI: map view | `frontend/src/components/MapView.tsx` | Leaflet + OSM; `divIcon` pins, z-index tamed in `index.css` |
| UI language (English / Italian) | `frontend/src/i18n/` (`index.tsx` + `en.ts` + `it.ts`) | Dependency-free, like the SVG charts: a flat dictionary plus `{placeholder}` interpolation is the whole need. **`en.ts` owns the key set and `it.ts` is typed `Dict` (= `typeof en`)** — a key added to one language and forgotten in the other is a `tsc -b` failure, not a half-English screen; `t()` takes `keyof Dict`, so a typo is a compile error too. Components call `useT()`; the module-level `translateCurrent`/`formatNumber`/`formatDate` serve the places that have no hook (`services/api.ts`'s `formatPrice`, `utils/format.ts`, MapView's raw-HTML tooltips, the class-component `ErrorBoundary`) — `I18nProvider` mirrors the locale into a module variable **during render**, since an effect would leave the first frame after a switch formatted the old way. Choice persisted in `localStorage` per device, like the theme toggle beside it in `Navbar`. **Backend-produced text stays English** (scan summaries, the availability check's `transport`, API errors): it crosses the wire already rendered |
| TS Types | `frontend/src/types/index.ts` | keep aligned with `schemas.py` |

---

## Property Lifecycle (`status`)

```
active ──keyword found──▶ filtered ──keyword removed──▶ active
active ──not seen for GONE_AFTER_DAYS (7) days──▶ gone ──reappears──▶ active
any ──user presses "Hide"──▶ hidden ──user presses "Restore"──▶ active
any ──user marks "Sold"──▶ sold ──user presses "Restore"──▶ active
```

Marking `gone` happens only during **complete and clean** scans: all profiles, none
`blocked`/`error`. The day-based threshold absorbs a block lasting hours, but after weeks
with the PC off every property is already past the cutoff — a single blocked startup scan
would mark the whole dashboard `gone` and poison `gone_at` (days-on-market) with fake
dates.

`sold` is a user-set, sacred state exactly like `hidden`
([invariant 5](invariants.md) — a scan never reverts it; needed because a "VENDUTO"
re-post stays online for weeks and the scan keeps re-finding it). It differs from `hidden`
in that it is kept as a **confirmed market close**: `Property.sold_at` gives
`market_velocity` a real sale date, distinct from the merely-inferred `gone`. It leaves
the active grid (and "All") like `hidden`, has its own status filter, and
`POST /api/properties/{id}/sold` + bulk `action="sold"` set it; `/restore` clears
`sold_at`. `market_velocity` counts `sold` in the closed set and breaks out
`sold`/`median_days_to_sold`/`sold_properties` as the confirmed subset.

---

## Data Schema (Concepts)

- **Property** = deduplicated physical property (one per real house), with `contract`
  ("sale"|"rent"), `source` ("scan"|"email"; "email" only on rows predating the retired
  inbox import, see invariant 19), `status` (incl. user-set `sold` with `sold_at` =
  confirmed close, see Property Lifecycle), and user-curated `is_favorite`/`notes`.
- **Listing** = an ad on a portal (N per Property; logical key `portal + portal_id`).
- **ListingProfile** = which searches have found a Listing (many-to-many, written by
  `upsert_listing` on every scan). Provenance, not origin: `Property.source` says how a
  card first arrived, these say who keeps finding it — the difference is what makes
  "delete this search with its results" answerable (invariant 20). Surfaced to the UI as
  `PropertyOut.found_by` (a `{id,name}` list, shown as the card's "🔍 Found by"): a
  transient field set by `routers/selection.py`'s `annotate_provenance` — one query joins
  listings→links→profiles for the whole result set, never per property, and a
  `PropertyOut.found_by` before-validator coerces the unannotated `None` to `[]` so any
  serialization path degrades to "no provenance" instead of a 500.
- **PriceHistory** = variations of the *minimum* price of the Property, ordered by id.
- **SearchProfile** = a monitored search URL + extra keywords + `notify_channels` (CSV of
  "telegram"/"email"; empty = all enabled channels, `"none"` = muted, invariant 21).
- **CommuteCache** = one routed leg — a property's pin to one of the user's saved places,
  on one travel mode — keyed by `"{mode}|{olat},{olng}|{dlat},{dlng}"` at 5 decimals
  (`commute.cache_key`). Same memory trick as GeocodeCache and for the same reason: a NULL
  distance/duration is a **negative** answer cached on purpose (OSRM looked, there is no
  way through), while a *transport* failure is deliberately not stored so the next batch
  retries it. Keyed by coordinates, not property id, so two flats in one building share
  the answer — and so the rows survive a dashboard reset, like the geocode cache.
- **GeocodeCache** = one remembered geocoding lookup, keyed by normalized query string. A
  row exists once a query has been tried; a NULL lat/lng is a **negative** result cached
  on purpose (never ask Nominatim again), which is what keeps the opt-in batch inside the
  1-req/s free limit. A failed lookup never overwrites a property's coordinates
  (fail-open, never a wrong pin).
- **OmiQuotation** = one OMI price band: min/max €/m² for a (semester, municipality, zone,
  property type, conservation state, contract). Imported from the Agenzia delle Entrate
  file the owner downloads once a semester, never fetched. **Not interchangeable with the
  listing median** and never to be averaged with it: these are *recorded transaction*
  prices, the median is what sellers are *asking*, and asking sits systematically above
  transacted. `municipality_code` is the national comune code (`F205`), not the ISTAT one,
  because that is what the zone perimeters are keyed by; it is indexed with `zone_code` as
  the pair a lookup starts from. Two semesters coexist and the newest wins
  (`omi_import.latest_semester`, ordered numerically — a text `max()` would answer "2025/2"
  over "2025/10"). Absent data means no OMI benchmark and no error.
- **OmiZone** = the perimeter of one OMI micro-zone, and the only thing that can turn a
  property's coordinates into the `zone_code` `OmiQuotation` is keyed by. `rings` is the
  geometry as JSON — a list of polygons, each `{"outer", "holes"}` of `[lat, lng]`
  vertices, because a zone genuinely is several polygons and genuinely has holes. The four
  `min_`/`max_` columns are their bounding box, indexed, so a lookup discards almost every
  zone before any ray casting happens. Keyed by `municipality_code` + `zone_code` for the
  reason the quotations are: `B12` exists in most of Italy. Two semesters coexist and the
  newest wins (`omi_zones.latest_zone_semester`). A point on a boundary two zones share is
  inside both (on-edge counts as inside), so candidates are ordered and the first match
  wins — the same pin resolves the same way on every run.
- **`Property.omi_municipality_code` / `omi_zone_code`** = where the batch placed that
  property. Persisted, and written *only* by `omi_zones.resolve_property_zones`: storing
  the answer is what lets a grid read a column instead of ray-casting hundreds of vertices
  per card. Empty means not placed — no coordinates, or a pin in no imported zone — and
  both are ordinary. A property with no coordinates is left untouched rather than cleared:
  geometry never placed it, so nothing here can honestly revise it.
- **`Property.omi_min_sqm_price` / `omi_max_sqm_price` / `omi_semester` / `omi_stale`** = the
  OMI band of the zone the property was placed in, the semester it was recorded in, and
  whether that semester is old enough to stop being current. **Transient**, set per request
  by `omi_benchmark.annotate_omi_benchmark` like the area median beside it: the figures live
  in `OmiQuotation`, so a persisted copy would be a second home for one fact and would go
  stale on the next import. The expensive half — placing the property — is the persisted
  pair above. Shown next to the median and never merged with it (invariant 22).
  `omi_stale` is *derived* from the semester (`omi_benchmark.is_stale`, threshold
  `STALE_AFTER_MONTHS`) rather than stored beside it, and served to the client rather than
  recomputed there, so the dashboard and the print dossier age the same band identically.
  Age is counted in whole months from the **end of the semester's own window**, never from
  the import: a 2023/2 supply loaded this morning still describes 2023.
- **PricingSnapshot** = one median €/sqm reading per (day, city, zone, contract);
  `zone=""` is the whole-city aggregate. Written at most once per day (scan completion or
  the daily scheduler job) so the trend charts have history the instantaneous medians
  never kept. City/zone stored normalized (lowercased), matching the median keys.

---

## Concurrency: WAL + `busy_timeout`, set per connection

`database._sqlite_pragmas` runs on SQLAlchemy's `connect` event (via `make_engine`, which
every engine in the project including the test fixtures goes through) and sets
`journal_mode=WAL`, `busy_timeout=5000`, `synchronous=NORMAL`. The workload demands it:
`check_same_thread=False` plus writers in the scanner, geocoder, availability check,
harvester and scheduler, all alongside FastAPI's threadpool — under the default rollback
journal a writer locks readers out entirely and the losers got an intermittent
`database is locked`. WAL keeps readers running during a write; `busy_timeout` makes the
*second writer wait* instead of failing instantly (WAL still serialises writers — the
timeout is what makes that invisible); `synchronous=NORMAL` is safe under WAL and drops
the fsync-per-commit cost.

It must be per **connection**, not once at startup: only `journal_mode` sticks to the
file, so a one-shot setup would leave `busy_timeout` at 0 on every connection the pool
opens afterwards — which is exactly the one a background thread gets. `test_database.py`
pins all three and runs two threads writing concurrently.

**Consequence:** `case.db-wal` / `case.db-shm` sit next to the database and hold the
newest commits until a checkpoint, so they are user data (gitignored with it), and **any
copy of the database must go through SQLite's backup API or `VACUUM INTO`, never a file
copy** — `services/backup.py` already uses `sqlite3.Connection.backup`, and
`test_backup.py` pins that an un-checkpointed transaction survives the copy.

---

## Migrations: additive automatic + Alembic for the rest

`init_db()` runs three steps in order (`database.py`): `create_all` (creates missing
tables), `_apply_additive_migrations()` (adds columns present in the models but missing on
disk via `ALTER TABLE ADD COLUMN` with their default, so `case.db` and its price history
survive new columns), then `_run_migrations()` (Alembic, which takes a pre-upgrade snapshot
first — see below).

**Adding a plain nullable/defaulted column still needs no migration** — the additive step
handles it, and that remains the path for additive changes. Alembic
(`backend/alembic/`, config `backend/alembic.ini`) is the harness for the first change the
additive step *cannot* express: a rename, a drop, a type change. Author those with
`cd backend && alembic revision --autogenerate -m "..."`, review the generated
`batch_alter_table` (SQLite has no real ALTER — `render_as_batch=True` does
copy-and-swap), and they apply on the next startup.

Existing databases predate Alembic (tables but no `alembic_version`): `_run_migrations()`
**stamps** them at `0001_baseline` before upgrading, so the baseline's `create_table`
never re-runs against tables that already exist. The whole Alembic step is fail-open
(create_all + additive already guarantee a working schema), and a missing `alembic`
install degrades to a warning — but a genuine post-baseline migration failure is logged
loudly with a traceback.

**A pending migration is snapshotted before it runs.** `_snapshot_before_upgrade()` compares
the recorded revision (or `0001_baseline` for a database that has none) against the script
head, and when they differ calls `backup.snapshot_before_migration()` for a copy named
`case-pre-<revision>.db`, beside the database rather than at `config.BACKUP_DIR` — the
engine, not `DB_PATH`, decides which database is live. It is skipped on a fresh install
(`init_db` reads whether the file existed *before* `create_all` created it) and taken once
per revision, so a retried migration does not overwrite the state that predates the first
attempt. That copy is **exempt from the 14-copy daily rotation** (`backup._daily_copies`
filters the prefix out): it is the oldest file in the folder, so counting it would make it
the first thing pruned. The daily copy cannot do this job at all — it is scheduled from
`scheduler.start_scheduler`, which starts after `init_db()` has already migrated.
Fail-open like the rest of the path, but logged at **error** level: startup continues,
and the line says the migration is running with nothing to fall back on.

**Downgrading is not supported, and it says so.** The reverse of an upgrade — an older
build opening a database a newer one has already migrated — arrives as an
`alembic_version` naming a revision that build's script directory does not contain, so
`upgrade head` cannot resolve it and raises. `_is_from_a_newer_build()` catches that case
first (the recorded revision is not among `walk_revisions()`), skips both the migration and
the pre-upgrade snapshot (nothing is being left, so naming a copy after it would be a lie),
and logs **one error line** naming the revision and the backups folder instead of an
Alembic traceback. Startup then continues against the newer schema, which normally works —
the models ignore columns they do not know about — but "normally works" is stated, not
assumed. The way back is to reinstall the newer version, or to restore the
`case-pre-<revision>.db` the newer version wrote before it migrated.

**The upgrade is proved against a database an older release wrote.**
`backend/tests/fixtures/legacy_v1.db` is the schema release 1.0.0 shipped, holding the demo
corpus plus the fields only a user produces (notes, favourites, tags, a property marked
sold); `test_upgrade_path.py` puts a copy of it through `init_db()` and compares every row,
column by column, against what it held before. That is a different question from
`test_migrations.py`, whose databases are all built by the code under test seconds earlier
and can therefore only agree with themselves. The fixture is committed rather than
generated for the same reason — one built from today's models is today's schema wearing an
old name. It is synthetic (`fixtures/build_legacy_v1.py` rebuilds it from
`services/demo_data.py` and documents what is in it), and it stays frozen: **an authored
migration that cannot carry it forward is the migration that would have cost a real user
their history.**

---

## Known Fragilities & How to Recognize Them

| Symptom | Probable Cause | Where to Look |
|---|---|---|
| Profile in state "Error: no listing extracted" | Portal changed HTML structure. A search that merely matched nothing does **not** land here: `text_says_no_results` (`page_text.py`) reads the portal's own "nothing matched" page and reports 0 listings with no error — Idealista serves that page with **HTTP 404**, the same status as a dead slug, so only the visible text tells them apart (invariant 16's rule, applied to searches) | log in `backend/app.log`; test strategies one by one in tests |
| Immobiliare blocked even on API | `api-next` endpoint changed or DataDome tightened | `immobiliare.py` strategy 4; consider the scrape-API transport |
| Idealista always "Blocked" | Aged TLS fingerprint | update `curl_cffi` (`pip install -U curl_cffi`), then reorder or extend the `tls_impersonations` setting — the rotation is data, so this needs no release; unknown names are dropped with a logged reason, and emptying it restores `config.DEFAULT_TLS_IMPERSONATIONS` |
| Listings with absurd prices (40 sqm everywhere) | Broken card boundary | `find_card_container` in `html_cards.py` + `*_footer` tests |
| No cross-portal merging | City mismatching | `_city_from_url` (Idealista) and normalization in `deduplicator.py` |
| A real title is mistaken for portal boilerplate (or vice versa) | `is_bad_title`/`is_placeholder_zone` are a structural heuristic, not a parser: a comune name that *is* an ordinary word ("Terrazzo" VR, "Paese" TV) can make a genuine phrase look auto-generated, and an agency absent from `repair_agency_prefixes` keeps its branding. Italy-only by design; both readers fail towards keeping the existing text | `listing_text.py`, `geo_reference.py`; `test_listing_text.py`, `test_geo_reference.py` |
