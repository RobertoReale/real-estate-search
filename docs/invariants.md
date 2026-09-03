# Invariants Not to Break

Twenty-two rules, each with a history: a regression that actually happened on a real
portal or in a real database — or, for 22, the shipped defect the rule exists to stop
coming back in a new shape. They are not style preferences — a change that breaks one of
these breaks something a user will notice, usually silently.

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
   its own (unlike `filtered` and `gone`). DELETE on `/api/properties/{id}` hides rather
   than deletes: a physical deletion would be undone by the next scan finding the listing
   again.

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
   a retry loop on the residential IP.

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
    which is the same silent green the file exists to prevent. The mount is conditional on
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
    — a second chat platform, a callback from a portal — takes the same shape. **The
    backups routes are the standing test of this rule**: `GET /api/maintenance/backups/{name}`
    hands over the whole database and `POST .../restore` overwrites it, which makes them the
    most powerful endpoints in the app. They add no access control of their own and need
    none — they are under `/api`, so the bind address and the optional token cover them —
    and a route that can overwrite the database must never become the argument for widening
    either (`test_api_auth.py` asserts they answer 401 without the token).

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
    re-harvests a cookie past its TTL (default 50 min, under DataDome's ~60). The harvest is
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
    floor-field-only query, since the whole UI is English), a `zone=` filter, a `max_sqm=`
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
    extra reason line beside them. Every rendering (the modal's benchmark panel, the print
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
    (and `frontend/src/components/PropertyModal.test.tsx` for the rendered panel) — the
    load-bearing one asserts that a property scores identically with and without OMI figures.
