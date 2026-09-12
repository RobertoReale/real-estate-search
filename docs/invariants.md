# Invariants Not to Break

Twenty-nine rules, each with a history: a regression that actually happened on a real
portal or in a real database — or, for 22 to 29, the shipped defect the rule exists to
stop coming back in a new shape. They are not style preferences — a change that breaks one
of these breaks something a user will notice, usually silently.

The last six share one shape and it is worth naming, because it is what earned them a
place here rather than a comment: each is a case where the app knows its answer is
approximate, partial or incomplete, and the tempting simplification is to stop saying so.
Every one of them reads better with the rule broken, and every one of them is then wrong
in a way the user has no means of detecting.

Two of them (12 and 15) have been retired with the feature they protected. Their numbers
are **kept rather than renumbered**, because comments, tests and the audit checklist cite
these numbers by value.

Before editing code that touches one of these, look it up in
[`audit.md` §1](audit.md#1-invariant-audit-are-they-true-are-they-necessary), which maps
each invariant to its code home and its test file. See also
[`architecture.md`](architecture.md) for where each module lives and
[`conventions.md`](conventions.md) for how the code around them is written.

---

1. **Conservative deduplication.** Two listings merge ONLY with surface ±5% + identical
   rooms/floor (when known) + price ±5% against **every** listing already merged + **proof
   of location** (coordinates ≤60 m OR street + house number + city). Loosening any
   threshold previously merged 7 different apartments into one card
   ([`implementation_plan.md`](../implementation_plan.md#8-deviations-from-original-plan)
   §8.2). Tests in `test_deduplicator.py` encode real cases.

2. **Scrapers NEVER use CSS classes.** Only patterns the portal cannot change without
   breaking itself: URL `/annunci/<id>` or `/immobile/<id>`, `€`, `N locali` (rooms),
   `N m²`. Card boundary is "the last ancestor with only one listing"
   (`find_card_container`), not a fixed number of levels
   ([`implementation_plan.md`](../implementation_plan.md#8-deviations-from-original-plan)
   §8.3).

3. **First scan of a profile = zero notifications.** Only builds the baseline; otherwise
   hundreds of Telegram messages would flood the user
   ([`implementation_plan.md`](../implementation_plan.md#8-deviations-from-original-plan)
   §8.6). Gated by `SearchProfile.baseline_done`, not by `last_run_at is None`: an attempt that
   gets blocked/errored before fetching any listing still stamps `last_run_at` (scheduling
   needs it), but must not consume the silence — otherwise the next attempt, the first to
   actually see real listings, notifies every one of them as "new". The same flag now
   also decides that a first scan **reads every page it is allowed to** rather than
   stopping as soon as it recognises a page (`_sweeps_to_the_cap`): a search with no
   baseline has nothing to recognise, and it is the one run where taking the whole window
   is the entire point.

4. **Keywords on word boundaries**, never substrings: "asta" (auction) ⊄ "Castanese"
   ([`implementation_plan.md`](../implementation_plan.md#8-deviations-from-original-plan)
   §8.5). Profile keywords ADD up with global keywords.

5. **`hidden` status is sacred**: chosen by the user, it never becomes `active` again on
   its own (unlike `filtered` and `gone`), **and it is silent** — the scan keeps the row
   up to date but counts nothing and sends nothing for it, price cuts included. Hiding is
   how the user says "stop telling me about this one", so a status that survived while the
   notifications resumed would honour the letter and miss the point. DELETE on
   `/api/properties/{id}` hides rather than deletes: a physical deletion would be undone by
   the next scan finding the listing again.

6. **`price_changed` refers to the MINIMUM price of the Property**, not the individual
   listing: when True, `price_history[-1]` is always the change just recorded. This is the
   contract between `deduplicator.upsert_listing` and `scanner`.

7. **Immobiliare internal API: never call it without resolved geographical parameters**
   (`idComune` etc. via autocomplete): with only `path` it answers `200 OK` with all of
   Italy — a silent failure
   ([`implementation_plan.md`](../implementation_plan.md#3-resilience-surviving-html-changes)
   §3, strategy 4). **And a zone selection travels *beside* that geography, never instead
   of it**: the resolved municipality is the area the endpoint answers in, the repeated
   `idMZona[]` ids are the filter within it, and every id the URL carried is sent — that
   is the grammar the portal's own map emits when districts are clicked. Dropping the
   geography returns Italy; dropping or truncating the ids returns the whole comune. Both
   are 200s that look like results, which is why the count that cannot fit in one request
   is refused with the number named rather than sent (`immobiliare.MAX_ZONE_IDS`).

8. **TLS Impersonation: ordered list, Safari first.** DataDome rejects Chrome desktop on
   both portals (measured); rotation occurs only on block. If someday everything is
   blocked, updating `curl_cffi` and profile names (`safari184`, …) is the first thing to
   try. **The list is data, not code**: `tls_impersonations` in the settings holds it and
   defaults to `config.DEFAULT_TLS_IMPERSONATIONS` — the same sequence that used to be
   hardcoded in `base.py`, which now carries it only as the built-in fallback — so a new
   block wave is answered by editing settings rather than shipping a release. It is also
   **self-healing**: `resolve_impersonations` (`transport.py`) filters the configured names
   against what the installed `curl_cffi` actually supports, **logging every name it drops
   and why**, so a `pip install -U curl_cffi` that retires a name (or a typo in the
   setting) degrades gracefully instead of crashing the next live fetch or silently
   shortening the rotation. It never returns empty: a list where nothing survives the
   filter — or one emptied outright, which is what every settings.json written before this
   setting had a default contains — falls back to the built-in list, and worst case to the
   generic `"safari"` alias. The
   block-driven rotation also burns the session's **proxy** (`proxy_pool`, in
   `transport.py`): DataDome scores the exit IP as much as the handshake, so the rebuilt
   session changes both. With a configured scrape-API key the very top of the ladder is one
   escalation to the provider (`fetch()`), after which the scan carries on remotely — never
   a retry loop on the residential IP. Immobiliare's JSON path climbs the same ladder and
   ends at the same rung (`_api_page`): the api-next page the portal refused is asked of the
   provider, and once that has happened the remaining pages of *that* walk go the same way
   rather than each spending a request the portal has already demonstrated it will refuse.
   The call to the provider is **never** made on the portal's session — `new_scrape_api_session()`
   builds a plain one, because the portal's carries a DataDome cookie pinned to the portal,
   headers describing a navigation inside it, and a 30 s timeout that used to abort a page
   the provider had solved and already charged for; the provider's own documentation asks
   for 155 s. Whatever the provider refuses with becomes a `BlockedError` naming the
   provider's error code, and the credits every call cost — refused ones included — are
   logged, because the attempt is billed either way.

9. **Never merge across contracts.** The same physical house listed both for sale and for
   rent must remain two Properties: different price scale, different meaning for the user.
   `raw.contract` (derived from the search URL) is authoritative and heals mislabeled
   records on the next scan.

10. **User-curated fields (`is_favorite`, `notes`) are never touched by scans**; they
    change only via `PATCH /api/properties/{id}`. Rent price parsing uses its own
    plausibility bounds (100–50,000 €/month): the sale bounds would reject every monthly
    rent.

11. **Scraper health alerts fire on a streak, once per outage.** `consecutive_failures`
    counts `blocked`/`error` scans in a row — and **only** those: `no_results` is an
    answer from the portal, so it clears the streak exactly as `ok` does, or a search
    over a market that genuinely has nothing in it would alert as an outage. An
    unhandled exception counts as a failure, whether it was raised reading the portal or
    recording what came back, hence `run_scan` records `error` itself — and it is raised
    on the writing thread even when the portal was read on another one
    (`_Fetched.error`), so one host failing never cancels the other. The alert goes out at the
    `health_alert_after_failures` threshold and `health_alert_sent` suppresses repeats
    until recovery. That flag is set **only when `broadcast()` actually delivered**:
    otherwise an outage occurring while no channel is configured would be swallowed forever
    instead of retried. Alerting on a single failure is wrong by design — transient
    DataDome 403s are routine.

12. **RETIRED** — *Email import is strictly read-only on the mailbox.* The inbox import
    subsystem was removed: the service, its routes, its UI, the `imported_listings` table
    (dropped by Alembic migration `0002_drop_imports`) and its settings keys are all gone.
    The number is kept so 13-21 still mean what every comment and test that cites them
    says. What it protected is gone with it — there is no mailbox to open and no staged row
    to remember. The one idea worth carrying forward if the feature ever returns: a
    *discard* must be remembered forever, or a re-scan resurrects every listing the user
    already rejected.

13. **The `StaticFiles` mount at `/` must stay the last statement in `main.py`.** It is a
    catch-all: declared before any API route, it swallows that route and the API answers
    404 with no error anywhere. Since the routes moved into `app/routers/` this means
    **after every `include_router` call**, not merely after the last decorator — a new
    router added below the mount is shadowed exactly as a stray `@app.get` was. One
    consequence for the *test*, not the rule: `include_router` does not flatten its routes
    into `app.router.routes` (FastAPI keeps one opaque entry per router and descends into
    it when matching), so `test_static_frontend.py` walks back in through
    `original_router` — without that it would find zero `/api` paths and pass vacuously,
    which is the same silent green the file exists to prevent. **The mount now falls back
    to `index.html`** (`SpaFiles`), because the dashboard routes on the URL and
    `/listings/123` is a real address a user reloads, bookmarks or is sent — and that
    fallback is a second way to swallow the API, one the ordering rule above cannot see.
    Two kinds of 404 stay 404s: anything under `/api`, or a mistyped route reaches the
    client as a JSON parse error instead of a 404 it already handles; and anything with a
    file extension, or a missing asset surfaces in the browser's module loader, where the
    message names neither the file nor the cause. Both are asserted, and the `/api` guard
    is easy to get wrong — the mount hands the path down already normalised for the local
    filesystem, so on Windows it arrives with backslashes and a `startswith("api/")` test
    written for a URL silently never matches. The mount is conditional on
    `frontend/dist` existing, because the dev flow (`dev.bat`) has Vite serve the app
    instead — so a missing `dist` is normal, not a failure. `start.bat` is the user flow and
    builds `dist` before starting, so there the mount is always live. Serving the built app
    from the backend's own origin is also why remote clients need **no CORS entry**: the
    `allow_origins` list exists only for the Vite dev server, and widening it is never the
    fix for a phone that cannot reach the API.

14. **The bind address is the access control — unless the optional token is set.**
    `run.py` defaults to `127.0.0.1` deliberately; `APP_HOST` widens it. A Tailscale address
    (`100.x.y.z`) exposes the dashboard to the user's own devices, `0.0.0.0` to every device
    on the LAN. Never make a non-loopback bind the default. The one sanctioned way to safely
    widen the bind is the optional `api_auth_token`: when non-empty, the `require_api_token`
    middleware requires `Authorization: Bearer <token>` on every `/api` request (the static
    SPA and non-`/api` routes stay open so the app can load and present its `AuthGate`
    prompt; OPTIONS preflight is exempt). Empty by default, so the loopback-only assumption
    is unchanged for existing users — never add a "just expose it publicly" shortcut
    *without* that token in front. **A feature that needs to hear from the outside world
    polls for it instead**: the Telegram inline buttons (`services/telegram_bot.py`) take
    the `getUpdates` long poll rather than the webhook the Bot API also offers, precisely
    because a webhook is an inbound port in front of this API. Anything else arriving later
    — a second chat platform, a callback from a portal — takes the same shape. **The push
    the dashboard receives is the same shape read the other way**: `GET /api/events`
    (`services/events.py`) is a stream the *browser* opened, outbound-only over the origin it
    already loaded from, under `/api` so the token middleware covers it like everything else.
    That last part is why the client uses `fetch` rather than `EventSource` — `EventSource`
    cannot send an `Authorization` header, and a stream that stopped working the moment
    somebody set a token, or a second unauthenticated route carrying it, would each be this
    rule broken quietly. **The
    backups routes are the standing test of this rule**: `GET /api/maintenance/backups/{name}`
    hands over the whole database and `POST .../restore` overwrites it, which makes them the
    most powerful endpoints in the app. They add no access control of their own and need
    none — they are under `/api`, so the bind address and the optional token cover them —
    and a route that can overwrite the database must never become the argument for widening
    either (`test_api_auth.py` asserts they answer 401 without the token).

    **The bind address cannot refuse one kind of request, and that one is guarded
    separately.** A page on any site the user has open can submit a `<form method="post">`
    at `http://127.0.0.1:8000/api/...`; the browser sending it *is* on the loopback
    interface, so the bind is no answer, and a form post is a "simple request" — no
    preflight, so `allow_origins` never gets a say, and the response being unreadable
    cross-origin does not stop the request from happening. Every `/api` route that takes no
    body was reachable that way, `POST /api/maintenance/reset/factory` (the whole dashboard)
    and `POST /api/scrapers/trigger` (the user's residential IP, spent on the portals)
    included. `reject_cross_site_writes` in `main.py` refuses POST/PUT/PATCH/DELETE under
    `/api` unless the request is same-origin with its own `Host` header, comes from a
    loopback origin, or states no `Origin` at all — a browser always states one on those
    methods, so an absent header is a non-browser client and not the case being guarded.
    The three exemptions are exactly the legitimate clients and nothing else: the packaged
    app and the phone load the SPA from the API's own origin (invariant 13), the Vite dev
    server is on 5173, and the browser suite's `vite preview` proxies from 127.0.0.1. Never
    widen it to a named external origin — that is the same mistake as widening the bind,
    made in a different file.

    **Both guards key on the `/api` prefix, so the prefix is load-bearing.** Neither reads
    anything else about a request before handing it on, which makes "every route that
    changes something is under `/api`" part of this rule rather than an accident of the
    layout: outside it the app has the SPA mount and FastAPI's own docs routes, all of them
    reads. A webhook receiver or a one-off form handler mounted anywhere else would be
    exempt from both by construction, and nothing about it would look wrong. Give it an
    `/api` path, or widen the guards deliberately.

15. **RETIRED as written** — *`email_import_scan` is a sync `def` endpoint on purpose.*
    Its subject went with the inbox import; the number is kept rather than renumbering
    16-21. **The rule it encoded still binds the availability check**, which is the last
    long-running blocking endpoint: it is a sync `def` so FastAPI's threadpool keeps
    `/api/properties/check-progress` answerable instead of the event loop being owned for
    minutes and the progress bar freezing at 0%; its progress dict is module-level (written
    by the worker thread, read by the poller) and cleared in a `finally` so a failed run
    cannot leave the UI polling forever; and it takes a non-blocking module lock
    (`_check_run_lock`, like the scanner's `_scan_lock`), refusing a second run with a
    readable error — threadpool execution means two requests genuinely can arrive at once,
    and the dashboard is often open on phone and desktop together. That reasoning now lives
    in `availability_check.py`'s own docstring.

16. **The availability probe fails open.** `AdProbe.check()` (`scrapers/probe.py`) returns
    `True`/`False`/**`None` = unknown**, and only a clear answer from the portal (404/410,
    its own "non è più disponibile" page, or a redirect that loses the ad path) may become
    `False`. A DataDome block, a timeout or a 5xx must answer `None`, and
    `check_availability` then leaves `is_available` untouched. **The "gone" markers are
    matched against the page's VISIBLE text only** (`text_says_gone` → `_visible_text`,
    which strips `<script>/<style>/<template>/<noscript>`), never the raw HTML: every
    Immobiliare ad page — live OR removed — embeds the portal's i18n error dictionary,
    "non è più disponibile" included, inside its Next.js `__NEXT_DATA__` JSON, so a bare
    substring scan over the full HTML+JS reported *every live ad as gone* (measured on the
    real site). Symmetrically, DataDome's "Access is temporarily restricted" wall can arrive
    as HTTP 200 with no "captcha" in its markup: `has_block_marker` (matched against the RAW
    HTML, since one signal is a `<script>` src) keeps that a block (`None`), never a
    removal. The asymmetry is the point: a dead ad shown as live costs one click, while a
    live ad shown as dead invites the user to throw away a property they would otherwise
    have called about.

    This is the availability check's only contact with the portals, and it is guarded on
    four sides: on demand only, capped at `MAX_CHECKS_PER_CALL`, paced by
    `max(request_delay_seconds, MIN_PROBE_DELAY[portal])` — the slowest portal in the batch
    sets the pace, because Idealista's own scraper floors itself at 8s — and **abandoned
    after `BLOCK_STREAK_ABORT` refusals in a row**. `warm_host()` fetches the homepage once
    per host before the first ad page, exactly as the scrapers do, since a cold session
    landing on a deep URL carries no DataDome cookie. Only a refusal (`was_blocked`) counts
    towards the streak; a timeout is not the portal saying no. The reason for all of this is
    that the block lands on the residential IP the scheduled scans depend on — insisting
    there is far more expensive than a half-finished check.

    The one exception to "abandon on a streak" is **opt-in** (`datadome_auto_refresh`): on
    reaching the streak, `_try_cookie_recovery` mints a fresh cookie in a headless browser,
    rebuilds the probe's session around it, and carries on — bounded by
    `MAX_COOKIE_REFRESHES_PER_CHECK` per batch, so it is a couple of last-resort recoveries,
    not a retry loop. The same flag arms one further lever: a blocked probe may switch to a
    **persistent headless browser session** (`AdProbe.start_browser_session`, one launch per
    batch, all Playwright calls on one dedicated thread because the sync API is
    greenlet-bound to its creating thread) and finish the batch through it; with the flag
    off, that path reports failure and the batch aborts as before. That switch is **sticky,
    not per-ad**: it sets `AdProbe._browser_primary`, so every remaining listing goes
    straight through the browser instead of re-earning a curl_cffi 403 first — leaving curl
    as primary would spend a fresh block on each ad before falling back. The user can also
    request that transport **from the first ad** via `availability_browser_first`
    (invariant 18): the batch opens the browser up front and never touches curl_cffi, so it
    earns one real DataDome cookie and reuses it instead of a 403 per listing — slower per
    ad, but not interrupted by blocks.

    In browser-primary mode a headless CAPTCHA sets `was_blocked` too, so a browser the
    portal is *also* challenging still hits the streak — and there the abort is
    **immediate**: when `_browser_primary` is set the streak handler skips the curl-only
    recovery levers (fresh cookie, TLS rotation) entirely, because none can clear a browser
    CAPTCHA and each costs a headless relaunch or a 12s sleep, which is exactly what once
    left the progress bar frozen for minutes on an already-lost batch. The escape hatch from
    that abort is attended, not automatic: `availability_browser_headful` (invariant 18)
    opens the browser **visible** and waits for the user to solve the CAPTCHA by hand
    instead of counting it as a block. Past those levers the block just gets re-earned —
    never replace the abort with a "rest and retry" loop: against a hard block it turns a
    50-item batch into hours of hammering from the very IP the scans need, with the UI
    apparently frozen.

    The cap is enforced as a **live-fetch budget inside the batch loop**, not by slicing the
    ids in the endpoint: rows resolved without a fetch (recently verified, or tracked by the
    dashboard *and seen recently*) don't consume it, so a "select all" of hundreds
    progresses across repeated runs instead of re-spending every run on the same first fifty
    (`summary["capped"]` tells the UI to say "run it again to continue"). The dashboard
    short-circuit trusts an `active`/`filtered`/`hidden` property as "still online" **only
    while `last_seen_at` is within the trust window** (`max(48h, 2× scan interval)`): the
    status alone is not proof, because a blocked scan suspends gone-marking, so a removed ad
    keeps reading `active` for days — trusting it once reported "still online" for ads that
    in fact served the portal's "non più disponibile" page. Past the window the row falls
    through to the HTTP probe, the only thing that may answer `False`.

17. **Settings tests must not read the real `settings.json`.** `tests/conftest.py`
    repoints `config.SETTINGS_PATH` at a throwaway file for every test, because
    `load_settings()` reads from disk: without it, a developer machine with email configured
    turned `test_disabled_channels_send_nothing` into a test that logged into Gmail and sent
    a real message. The same disk-write hazard applies to any ad-hoc script calling
    `save_settings()` outside pytest — it hits the real file and can clobber the user's
    `datadome_cookie`/credentials, so use the throwaway path or don't call it.

18. **The cookie harvester is optional, opt-in, and fails open.**
    `services/cookie_harvester.py` automates what the user does by hand — open a browser,
    let it earn a DataDome cookie, save it — because `curl_cffi` cannot mint one (no JS
    engine). Playwright is **not** in `requirements.txt`: it plus a browser is ~300 MB and
    the project targets a Raspberry Pi, so it is imported lazily and `is_available()` gates
    every entry point; its absence degrades to the manual paste, never an `ImportError`.
    Auto-refresh before a scan is **opt-in** (`datadome_auto_refresh`, default off) — a scan
    must never launch a browser the user did not ask for — and `maybe_auto_refresh()` only
    re-harvests a cookie past its TTL (default 50 min, chosen to sit under a DataDome
    lifetime of ~60 that measurement has since disproved: a cookie 50 hours old still
    answered on 2026-09-12, and the vendor documents a lifetime of 7 days to a year —
    [`live-checks.md`](live-checks.md) §3). The harvest is
    **fail-open** like the availability probe (invariant 16): a missing browser, a timeout,
    or a headless CAPTCHA returns no cookie and the scan proceeds with whatever it had. A
    single `_harvest_lock` (like `_scan_lock`) serialises launches, because two browsers on
    the one persistent `browser_profile/` dir race and Chromium refuses the second.

    The manual API grab is **headful** on purpose (the user is present to solve a CAPTCHA
    once; the persistent profile then remembers it); the pre-scan auto-refresh is headless
    (unattended). The same `datadome_auto_refresh` flag also arms a **reactive** headless
    refresh inside the availability check (`_try_cookie_recovery`, invariant 16) and the
    probe's persistent browser fallback (`AdProbe.start_browser_session`, invariant 16):
    pre-scan it fires when the cookie is past its TTL, on a block it fires because the
    cookie has demonstrably burned. One further flag authorises an unattended launch:
    `availability_browser_first`, which makes the availability check run entirely through
    the persistent headless browser from the first ad (invariant 16);
    `AdProbe.start_browser_session` accepts *any* of these three switches
    (`datadome_auto_refresh`, `availability_browser_first`, `availability_browser_headful`)
    as the opt-in.

    Every **unattended** launch is headless. The one **attended** exception beyond the
    manual grab is `availability_browser_headful`: the availability check is user-triggered
    (they click "check online" and watch the progress bar, so a person is present), and with
    it on `start_browser_session` launches the persistent context **visible** so a DataDome
    CAPTCHA can be solved by hand — `AdProbe._browser_check_inner` calls
    `_wait_for_human_solve` (polls up to `_HEADFUL_SOLVE_TIMEOUT_MS`, bounded so an ignored
    window still ends the batch) instead of immediately marking `was_blocked`, and one solve
    primes the shared profile so the rest of the batch flows. It is gated on
    `not _is_session_zero_nt()`: a Windows service has no interactive desktop, so headful
    there would hang invisibly and degrades to headless. `_launch`'s `headless=` argument is
    the single knob for all of this.

    **Browser engine is pluggable and self-healing (`browser_engine`).** `_launch` prefers
    **Camoufox** (a stealth Firefox that hides the automation signals DataDome fingerprints)
    over Chromium when selected. Like Playwright, Camoufox is **not** in `requirements.txt`
    (its own ~150 MB browser); `is_camoufox_available()` gates it and `browser_engine` picks
    the engine — `"auto"` (default) uses Camoufox when the package is installed and falls
    back otherwise, so `pip install camoufox` is itself the opt-in; `"chromium"` pins the old
    path; `"camoufox"` forces it. **The Camoufox path must never break a working check**:
    `_launch_camoufox` returns `None` on any failure (its browser may be unfetched, or a
    Playwright↔juggler version mismatch — hence the required `no_viewport=True`, since a
    newer Playwright sends a `viewport.isMobile` the bundled Firefox rejects) and `_launch`
    carries on with Chromium. A Camoufox context owns its **own** Playwright, so teardown
    goes through `_close_ctx` (calls the launcher's `__exit__`), not a bare `.close()`; every
    launch tags the context with `_engine_label` for the diagnostic below.

    **Diagnostics: `AdProbe.browser_status` and the check's `transport`.** The availability
    check surfaces a human-readable `transport` string into its progress + summary
    ("camoufox (visible window)", "fast requests (curl) — browser off: no browser option
    enabled", …) so "why didn't the window open / why did it get blocked?" is answerable
    from the UI instead of the log — `start_browser_session` records the reason it did or
    didn't launch (engine missing, no option enabled, session-0, headful/headless).

    **The browser path also *behaves* (`scrapers/humanize.py`) and is driven through a seam
    (`scrapers/browser_engine.py`).** Every browser-rung page visit (probe check, headful
    solve hand-off, cookie harvest) runs `humanize` after navigation — Bézier mouse paths, a
    small scroll, a short dwell — because DataDome scores behavior and a bare `goto()` emits
    zero pointer events. It is gated by `browser_humanize` (default on), budgeted
    ~0.5–1.5 s/page, and **fail-open like everything on this rung**: any exception in the
    glue is swallowed, so it can never fail a check (invariant 16) — and it never touches the
    curl transport, which has no mouse. Past the launch, `_browser_check_inner`,
    `_wait_for_human_solve` and `_harvest_inner` speak only the `BrowserEngine` Protocol
    (open/content/title/url/cookies/humanize/wait/close), with `PlaywrightEngine` adapting
    today's Camoufox/Chromium context: block detection, gone detection and cookie export
    exist once, engine-agnostic (`test_browser_engine.py`'s FakeEngine proves it). A future
    stealth engine (Nodriver, SeleniumBase-CDP) is therefore an adapter, added **only** when
    the Scraper Health block-rate justifies its cost.

19. **`Property.source` is upgrade-only, and `"email"` is now a historical value.** It
    records how a property first entered the dashboard:
    `deduplicator.upsert_listing(..., source=)` defaults to `"scan"`, and the inbox import
    used to pass `"email"` on accept. **With the import cut nothing writes `"email"` any
    more**, but the column is deliberately kept: a user's existing database still holds rows
    that arrived that way, and they keep their badge, their Origin filter and their meaning
    — "no monitored search has ever found this". The upgrade rule still runs: such a row is
    promoted to `scan` the instant a scan re-finds it, and is **never** demoted. The column
    is additive (auto-migrates), and its **one-time backfill**
    (`database._backfill_property_source`, run only the first time the column appears)
    recovered the origin from `imported_listings`; that table is dropped by migration
    `0002_drop_imports`, so the backfill now checks it exists and skips when it does not —
    the one window where it still has something to read is a database old enough to predate
    the `source` column, where the additive step runs before Alembic drops the table.

    The dashboard grid exposes it as `source=`, plus a free-text `q=` (whitespace-tokenized:
    terms are AND-ed and each may match any of title/zone/address/city/**floor**/agency/
    description, so "attico navigli" finds a title+zone split no single substring would; a
    digit paired with **`piano` or the English `floor`** — "4 piano"/"floor 4" — is a
    floor-field-only query, since the box is read in both languages), a `zone=` filter, a `max_sqm=`
    cap (twin of `min_sqm`) and a `floor_band=` band (`ground`/`low`/`mid`/`high`/`top`,
    matched in Python via the shared `match_score._parse_floor`; an unreadable floor matches
    no band), a set of **advanced filters** behind the UI's collapsible "More filters" panel
    — `portal=` (`Property.listings.any(Listing.portal==…)`, "has an ad there", not "all ads
    there"), `agency=` (substring on `Listing.agency`), `merged_only=` (Python:
    `len(listings)>1`), a `min_sqm_price=`/`max_sqm_price=` €/sqm band (Python: derived
    `price÷sqm`, a card missing either drops out) and `deal=` (`undervalued`/`fair_plus`, a
    Python post-filter on the `deal_label` annotation **after** `annotate_deal_scores` —
    unscored cards, lacking a local median, fall out), a **geographic zone** drawn on the map
    (`center_lat`/`center_lng`/`radius_m` **or** `poly=`, mutually exclusive, a Python
    post-filter via `geo_filter`; a card with NULL coordinates can't be placed and **always
    drops out**, the silent asymmetry `MapView`'s banner + "N without coordinates" chip
    surface — see the *Map zone filter* row in
    [`architecture.md`](architecture.md#where-to-act-for-each-type-of-modification)) — and a
    `profile_id=` overlay ("Limit to a search") that restricts the grid to the properties a
    monitored search **actually found**, read from its `ListingProfile` provenance links (the
    card's "🔍 Found by"), via
    `Property.listings.any(Listing.profile_links.any(ListingProfile.profile_id==…))`. It is
    deliberately **not** a re-derivation of the search's contract/city (those overlap so
    heavily between searches that the filter appeared broken — it dropped nothing); rows
    carrying no links, such as the historical email imports, drop out because no search found
    them. Bulk curation goes through `POST /api/properties/bulk`
    (hide/restore/favorite/unfavorite/sold), which shares the single-item routes' semantics
    (hiding and marking sold stay reversible only via restore, invariant 5; `sold` is the
    confirmed-close state, see
    [Property Lifecycle](architecture.md#property-lifecycle-status)).

20. **Deleting a search may delete only what is provably its own.**
    `POST /api/search-profiles/bulk` with `action="delete", delete_results=true` is the one
    place a Property is *physically* deleted rather than hidden (invariant 5 hides because a
    scan would resurrect the ad — here the search that would re-find it dies in the same
    transaction). Ownership is read from the `ListingProfile` links the scanner writes,
    **never inferred from the search criteria**: two searches on one city overlap heavily,
    and a city+contract guess would delete the sibling search's cards. Four things are
    therefore spared, and the dialog reports each: a property **a surviving profile also
    found** (it still covers it), a **favorited or annotated** one (invariant 10: hand-made,
    unrebuildable), a **`sold`** one (its confirmed `sold_at` is hand-made market-velocity
    signal a re-scan can't rebuild — grouped under the same `kept_curated` count), and
    anything with **no link at all** — the historical email imports, and rows predating the
    links. That last one is a real gap, not an oversight: attribution accrues as scans run
    (the link is re-written on *every* scan, not just first sighting, so a search that starts
    covering a known ad becomes a finder of its own), and "not attributable" must fail
    towards keeping data. The purge does not commit — `routers/profiles.py`'s
    `bulk_profiles` deletes the profiles in the same transaction, so a failure cannot wipe
    the results while leaving the searches monitoring — and it is refused mid-scan (409),
    like the resets, since a scan in flight is writing the very links the decision reads.
    **`data_reset.profile_results` classifies a *set* of searches, not one**, and the
    single-row 🗑 is just a selection of one: "shared, so keep it" means shared with a search
    *outside the set* — deleting two searches one id at a time would spare the card they both
    found and leave it in the dashboard with nothing left to refresh it. The whole selection's
    counts are previewed by `POST /api/search-profiles/results` before the user chooses.

21. **A search can be silenced without being paused.** `notify_channels` has three states
    and the empty string can only express one, so muting rides on its own sentinel: `""` =
    all enabled channels, a CSV = those channels, `notifier.MUTED` (`"none"`) = notify
    nowhere. `notifier.profile_channels()` maps that to what `broadcast()` takes — `None` =
    all, `[]` = muted — which is why `broadcast` must never write `channels or CHANNELS`:
    that collapses `[]` back into "everything" and a muted search shouts on every channel.
    Muting covers **every** message the search can produce, scraper-health alerts included
    (invariant 11 still counts the streak, it just never announces it); the scanner returns
    before the deal-score pass, since that work only feeds a notification nobody will get.
    Pausing (`is_active=False`) is the other thing entirely — it stops the scan itself, so
    the listings stop arriving too.

22. **The OMI band is never substituted for the listing median, and neither is ever shown
    without saying which it is.** They answer the same question from opposite sides: the
    median (`pricing_stats.py`) is the middle of what comparable ads **ask**, computed from
    prices this app scraped; the OMI band (`omi_import.py`) is min/max €/m² the Agenzia
    delle Entrate derives from **recorded transactions**. Asking sits systematically above
    transacted, so averaging them, or letting one fill in where the other is missing,
    produces a number that means nothing and looks authoritative — which is precisely the
    failure the OMI import was added to end. v1.0.0 shipped a benchmark that compared a
    listing only against its neighbours' asking prices, so a uniformly overpriced zone read
    as "fair" and the app said so with confidence; a merged figure would restore that defect
    with a government source's name attached to it. Concretely: `omi_benchmark.py` writes
    only `omi_min_sqm_price`/`omi_max_sqm_price`/`omi_semester`/`omi_stale` and never touches
    `sqm_price_delta_pct`, `area_median_*`, `deal_score`, `deal_label` or the proposal range
    — the deal score's inputs are what they were before OMI existed, and the band is one
    extra reason line beside them. Every rendering (the detail's benchmark panel, the print
    dossier's key facts, the reason line itself) labels each figure with **whose** it is and
    dates the OMI one with its semester: an undated band is a claim with no expiry, and an
    unlabelled one is two different measurements wearing one name. The same rule carries two
    obligations that live or die with it. A band whose semester ended more than
    `STALE_AFTER_MONTHS` (18) ago is **marked out of date wherever it appears** — labelled,
    never withheld, since recorded prices two years old still beat asking prices alone, but a
    figure that ages silently is back to being trusted for a currency it no longer has. And
    the attribution the OMI licence requires (`omi_benchmark.ATTRIBUTION`, *Fonte: Agenzia
    Entrate – OMI*) travels with the figures: it is one constant read by every renderer, and
    it appears **only** where a band actually printed, since crediting the Agenzia on a
    dossier carrying none of its data names a source that document never used. The reason
    line repeats it rather than leaning on the panel above, because that line also travels
    alone into the card's deal-score tooltip. Regression tests in `test_omi_benchmark.py`
    (and `frontend/src/routes/property/Benchmarks.test.tsx` for the rendered panel) — the
    load-bearing one asserts that a property scores identically with and without OMI figures.
    On the grid the rule has a second guard, because the card shows **one** market statement
    and picking one is exactly where a substitution would be easy to make: `marketPosition`
    (`frontend/src/utils/marketPosition.ts`) chooses between the deal score and the listing
    median and reads no OMI field at all, which `marketPosition.test.ts` asserts by giving it
    a property whose only figures are a band.

23. **A subprocess whose output is committed is decoded explicitly, never by the platform's
    locale.** `subprocess.run(..., text=True)` picks the decoder from the *running machine*:
    UTF-8 on the Linux runner, cp1252 on this Windows checkout. Any tool whose bytes end up
    in a tracked file therefore produces a different file on each platform, and the one
    produced here is the wrong one. `scripts/gen_api_types.py` shipped exactly that from its
    first commit (`9da58dc`): `openapi-typescript` writes the schema descriptions as UTF-8,
    Windows decoded them as cp1252, and every em dash was committed as `â€"` — 36 of them in
    `frontend/src/types/api.ts`, and not one real one, for the file's entire life. The
    regenerate-and-diff gate could not see it: it re-ran the same wrong decode and compared
    the corruption against itself, green on this machine and red on the runner, which is
    where the defect finally surfaced. So `encoding="utf-8"` is passed alongside `text=True`
    wherever the captured output is written to a tracked file. The wider rule this belongs
    to, and the reason it is stated as an invariant rather than a preference: **a gate that
    reproduces the defect it is checking for is not a gate.** Both halves are asserted in
    `test_generated_artifacts.py` — that the generator names an explicit encoding, and that
    the committed `api.ts` carries no mojibake — because the second is what a reader would
    have noticed and the first is what stops it recurring.

24. **A zone centroid is never handed over as an address.** A listing whose portal
    publishes neither coordinates nor a street still gets a pin — the geocoder falls back
    to the district — and that pin is somewhere nobody lives. `Property.coordinate_source`
    records which of the two it was (`geocoder.SOURCE_ADDRESS` / `SOURCE_ZONE`) at the
    moment the pin is written, because after the fact a latitude and longitude look
    identical whatever produced them. Everything downstream reads it through
    `geocoder.is_approximate` rather than comparing the string: an *unknown* source — every
    row in a database upgraded from before the column existed — is **not** approximate, or
    the first run after the upgrade would put a warning over a whole map of pins that are
    very probably exact. The user meets the rule twice on the map, in the pin's own popup
    and as the count in the legend (`map.zoneCentroid` in [`limits.md`](limits.md)), and the
    scan reports `located` and `located_approximate` as two numbers rather than one. What
    the rule forbids is the shortcut of treating a placed pin as a located property: a
    district centre used for a distance, a commute or a radius filter answers a question
    about the district and presents it as an answer about the flat. Tests:
    `test_geocoder.py::test_a_pin_records_where_it_came_from` and
    `::test_an_unknown_source_is_not_called_approximate`.

25. **A listing that came back from outside the area asked for is reported, never
    dropped.** Portals answer a zone-narrowed search with strays — a zone matched by name
    rather than by id, a drawn polygon the portal has no field for — and the tidy-looking
    fix is to filter them out on the way in. That silently converts "the portal did not
    honour your zone" into "there is nothing there", which is the one conclusion the user
    would draw for themselves and act on. So `scanner._outside_requested_area` counts them
    into `summary["outside_area"]` and the per-search `ScanJournalEntryOut.outside_area`,
    the listing is saved like any other, and both ends are stated: the journal row says how
    many, the card says which (`scan.outsideArea`, `card.outsideArea`). The same rule holds
    for a search whose area was *drawn* rather than named, which is where the temptation is
    strongest because the polygon is exact and the portal's answer plainly is not. Tests:
    `test_scanner.py::test_an_out_of_area_listing_is_kept_not_dropped`,
    `::test_an_out_of_area_listing_from_a_drawn_search_is_kept_too` and
    `::test_the_profile_line_says_how_many_came_from_outside`.

26. **Determinate progress is drawn only against a total the portal actually stated.**
    `ScanProgressOut.total_pages` is `null` more often than not — Immobiliare declares a
    page count, Idealista frequently does not — and a progress bar needs a denominator, so
    the available shortcuts are to invent one (the page cap, the pages seen so far) or to
    draw a bar that fills and then keeps going. Both produce a bar that is wrong in the
    direction users trust: it says the scan is nearly done. `pageProportion`
    (`frontend/src/routes/activity/progress.ts`) is the single place that decision is made
    and it returns `null` where there is no declared total, which the screen renders as an
    indeterminate state and a page counter rather than as a fraction; where there *is* a
    total the done value is clamped to it, since a portal that under-declares must not
    produce "page 31 of 30". The rule is one function and not markup precisely so it is
    testable: `frontend/src/routes/activity/progress.test.ts` — "refuses a fraction where
    the portal declared no total" and "never runs past the total the portal stated".

27. **A stored secret is never overwritten by its own mask.** `GET /api/settings` returns
    every secret as `"***"` (`config.SECRET_SETTINGS`; the Telegram token as a truncated
    prefix), and the settings form writes the whole object back — so an untouched
    credential arrives at the server as the mask it was shown, and saving a scan interval
    would blank a working API key with no error and no way to notice until the next scan
    failed. `routers/settings.py` therefore treats the mask as "keep the stored one" and
    pops the field before saving, unmasking exactly the fields the read side masked. The
    two lists are hand-written and must keep agreeing, which is why the regression test is
    driven off `SECRET_SETTINGS` itself rather than off a copy of it: an eighth secret
    added to the read side alone breaks nothing visible and destroys a credential on the
    next unrelated save. The setup wizard reaches the same rule from the other side —
    `payloadFor` in `frontend/src/routes/setup/groups.ts` omits an untouched secret rather
    than posting it back — because five sequential saves must be a patch and not five
    replacements. Tests: `test_features.py::test_no_stored_secret_is_overwritten_by_its_own_mask`
    and `test_routes.py::test_a_saved_secret_survives_a_later_save_that_masks_it_back`.

28. **A quick scan never makes a completeness claim.** With `stop_when_nothing_new` on —
    the default, and a real saving: a routine scan drops from ten page-fetches to two — a
    search stops at the first page holding nothing it had not already seen. The pages it
    never reached can hold a price change, and nothing in the run can say they do not. So
    the kind of reading is recorded and reported rather than inferred: `mode` is `full` or
    `quick` on every journal row, `_quick_scan_note` says so in the detail line, and
    `stopped_because` names the early stop as the reason. The shortcut is bounded rather
    than trusted — `_sweeps_to_the_cap` forces a full sweep on a search's first scan and
    once every `full_sweep_every_days`, counted from a `last_full_sweep_at` that only a
    sweep which *got through* may stamp — and that bound is what entitles the `gone`
    marking to read absence as withdrawal at all (see
    [Property Lifecycle](architecture.md#property-lifecycle-status)). Turning the shortcut
    off must change speed and nothing else: it is a setting about how many requests to
    spend, never about what the scan is allowed to conclude. Tests:
    `test_scanner.py::test_a_quick_scan_says_it_was_one_rather_than_reading_as_complete`
    and `::test_stopping_early_is_a_speed_setting_and_never_a_behaviour_one`.

29. **A segmented search is complete only if its partition was proved total.** A search
    that overflows `max_pages_per_search` is re-run as several narrower ones — one per zone
    id where the selection allows it, price bands otherwise — and their results merged,
    which is the only way past a cap the portal imposes. The merge is where a gap becomes
    invisible: a band boundary off by one euro drops every listing at that price, and the
    result still arrives as one tidy list with a plausible count. So the partition is
    checked rather than assumed. `search_builder.price_bands`
    produces bands that meet without overlapping, `bands_are_total` asserts they cover
    `[low, high]` exactly, and `scanner._parts_cover_the_whole` refuses to call the run
    complete unless the parts account for the whole; a search that cannot be partitioned
    within `MAX_SEARCH_PARTS` (8) reports as truncated (`scan.pageCap`) instead of quietly
    reporting a subset. The rule to hold when adding a segmentation axis — rooms, surface,
    anything — is that the axis has to come with its own totality proof, because "these
    ranges look like they cover it" is exactly the reasoning that fails at a boundary.
    Tests: `test_search_builder.py::test_price_bands_leave_no_gap_and_no_overlap` and
    `test_scanner.py::test_a_partition_that_does_not_add_up_is_never_reported_as_complete`.
