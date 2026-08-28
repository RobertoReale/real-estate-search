# Conventions

How code is written in this repository, how it is tested, and why the documentation is
treated as part of the change rather than as an afterthought.

See also [`architecture.md`](architecture.md) for where each module lives,
[`invariants.md`](invariants.md) for the rules that must not break, and
[`audit.md`](audit.md) for the periodic health check that enforces the rules below.

---

## Writing code

- **Reuse before you write. One fact, one implementation.** Before adding a function,
  endpoint, query or component, look for an existing one that already does the job (or
  most of it) and extend or share it instead of writing a parallel copy. This codebase is
  built that way on purpose and the pattern is load-bearing: the grid and the export share
  `select_properties` so a dossier always mirrors the screen; every portal fetch outside a
  scan goes through `AdProbe`; the title/zone boilerplate predicates live once in
  `services/listing_text.py`, read by both the availability check and the geocoder; keyword
  filtering is only ever `filter_engine.find_excluded_keyword`. Duplicated logic is how two
  paths start to disagree — the moment you copy a threshold, a parser or a selection query,
  one copy will be fixed and the other won't, and an invariant silently breaks in exactly
  one place. If reuse needs a small refactor (hoist a helper, add a parameter with a safe
  default, like `source=` on `upsert_listing`), do that refactor rather than fork. Only
  fork when the two callers genuinely need to diverge — and then say why in a comment, so
  the next reader doesn't "helpfully" re-merge them.

- **Mandatory English rule.** All code comments, docstrings, backend user messages, logs,
  commit messages, and documentation MUST be in **English**. Frontend UI strings are the
  one structured exception: they live in `frontend/src/i18n/`, where `en.ts` is the source
  of truth (write the English first) and `it.ts` carries its Italian counterpart. Never
  hardcode a user-facing string in a component — put it in both dictionaries and call
  `t()`, or the Italian UI silently keeps an English word. If explaining a rationale in
  comments, explain *why* (the history, the constraint), not *what*. Exception:
  exact domain-specific keywords used to match Italian portal listings
  (`DEFAULT_EXCLUDED_KEYWORDS`: "nuda proprietà", "piano terra", "asta", …) stay in
  Italian, since they must match the listing text verbatim.

- **Datetimes are always UTC-aware when written**, and SQLite gives them back naive — so
  whoever compares them must reattach the timezone. That reattachment lives in exactly one
  place, `services/timeutils.py` (`as_utc` / `as_utc_or_none`); call it rather than writing
  the two-line `replace(tzinfo=UTC)` again. It used to exist as five hand-rolled copies,
  and one copy forgetting it is a 500 in whichever screen it feeds.

- **The frontend talks to the backend ONLY via the Vite proxy** `/api` →
  `127.0.0.1:8000` (`vite.config.ts`): no absolute URLs in `api.ts`.

- **Responsive UI: phone-first, desktop restored at `sm`.** The dashboard is served to
  phones (see `serve.bat`), so every control row must survive 390 px. Three patterns
  recur, each with a reason:
  1. dense control rows are `grid grid-cols-2 … sm:flex sm:flex-wrap`, and the
     `col-span-2` on wide fields needs no `sm:` prefix because `grid-column` is inert on a
     flex item;
  2. `.btn-primary`/`.btn-ghost` carry `min-h-11 sm:min-h-0` — a 44 px touch target on a
     phone, the original density on a mouse-driven desktop;
  3. full-height panels use `dvh`, never `vh`, since `vh` spans behind a mobile address
     bar and pushes a modal's footer buttons out of reach.

  Fixed widths (`w-36`, `w-56`) must always be written `w-full sm:w-36`. `.input` jumps to
  16 px below `sm`: anything smaller makes iOS Safari zoom in on focus and never zoom back
  out.

---

## Testing

- **704 backend tests** in `backend/tests/`, all offline (simulated HTML + in-memory
  SQLite): no network, so always reproducible. `test_property_based.py` adds `hypothesis`
  property tests for the pure helpers (the dedup ±tolerance gate, haversine, the
  price/sqm/floor parsers): the laws they must obey for *any* input, complementing the
  enumerated regression cases.

- `conftest.py` repoints `config.SETTINGS_PATH` at a throwaway file for **every** test.
  Without it `load_settings()` reads the developer's real `settings.json`, so on a machine
  with email configured `test_disabled_channels_send_nothing` logged into Gmail and
  delivered an actual message ([invariant 17](invariants.md)). Any new test touching
  settings gets this isolation for free — do not remove it.

- **Every bug found on a real portal became a regression test** with comments explaining
  the backstory. Maintain this habit: if you fix behavior, add a test explaining "why".

- **The frontend has unit tests too** (32 in four files: vitest + `@testing-library/react`,
  run `cd frontend && npm test`). They cover the pure logic that used to be invisible — the
  `propertyParams` codec in `services/api.ts` first, since a filter silently dropped from
  the querystring vanishes from both the grid and the export with nothing failing; then
  `humanizeFloor`, and the i18n core (`i18n/i18n.test.ts`): key parity between `en`/`it`,
  **matching `{placeholder}` sets per key** (a dropped `{count}` leaves a hole in one
  language only), no empty translation, interpolation, and the startup language resolution.
  `components/settings/sections.test.ts` is the same hazard one level up: the settings save
  is the **union of eight sections' payloads**, so a field dropped from one section's
  `write` stops persisting while the form still renders it and the request still returns
  200 — the test pins the whole key set, the round-trip, and the "an empty secret field
  means keep the stored one" rule. The harness (jsdom + jest-dom) is set up for component
  tests too, but the point is the pure logic, not pixels.

- **Tests DO NOT cover:** the real network fetch (DataDome cannot be simulated), the
  APScheduler wiring itself (its decision helpers — catch-up, backup freshness — are
  tested), and the React components' rendered UI (still manual verification via
  `start.bat`).

- **The offline sandbox (`tests/mock_portal.py`) is where a whole-flow test goes.** The
  suite has always been offline, but offline *by substitution* — a fake session handed to a
  scraper, a monkeypatched `notify_new_property`. That proves each part and says nothing
  about the seams. `MockPortalServer` serves both portals over real HTTP on `127.0.0.1` and
  `MockSMTPServer` captures the notification over real SMTP, so `test_offline_sandbox.py`
  drives `run_scan` scrape → normalize → deduplicate → notify with nothing stubbed. Three
  things make it work and are the things to preserve: the scrapers request exactly the
  absolute URLs listed in `PORTAL_URL_ATTRS` (**a portal added there is a portal the
  sandbox can serve** — listing URLs are deliberately absent, they are data the user clicks,
  never fetched); the SMTP leg needs **no patching at all**, because `smtp_host`/`smtp_port`
  are settings, so what runs is the real `smtplib` exchange; and a `Flat` is rendered *per
  portal* from one description, so the cross-portal merge under test cannot quietly become
  two different apartments. `MockPortalServer.requested` is the proof the scrape stayed
  inside the sandbox — a scraper that went to the real portal is simply missing from it.
  `block_external_network` guards the Python-level paths as well, but **not** curl_cffi,
  which resolves inside libcurl where no monkeypatch reaches. There is no fake IMAP server:
  the inbox import that would have read one is gone ([invariant 12](invariants.md)), so the
  only mail server the flow still needs is the one it sends through.

- **To fetch a portal page live during verification, use `AdProbe` (`scrapers/probe.py`),
  not a raw browser.** `AdProbe().warm_host(url)` + `.fetch(url)` reuses the tuned TLS
  impersonation and, crucially, injects the user's real `datadome_cookie` from
  `settings.json` — so it succeeds where a cold Camoufox/Playwright launch earns a 403
  (curl_cffi cannot mint a DataDome cookie; a browser started from scratch has none). This
  is the reuse rule above, applied to throwaway tooling: before writing an ad-hoc script
  that talks to the portals, check what `scrapers/` already gives you. A whole session was
  lost to cold-browser 403s while this tool sat unused. Measure filters with a
  **known-good control** in the sweep (see the *Portal filter tokens* row in
  [`architecture.md`](architecture.md#where-to-act-for-each-type-of-modification)) —
  `AdProbe.fetch` raises `BlockedError` on a block, so a silent block-page measurement is
  easy to catch.

---

## Documentation Is Part of the Change

Treat the docs as code that happens to be prose: **a task is not finished until the .md
files still describe the program that exists.** Before committing, ask what the change made
untrue, and fix it in the same commit — a doc corrected three sessions later has already
misled someone. Stale documentation is worse than none: it is trusted, and it is wrong.

Each file has one job, and duplicating content between them is how they start to disagree.
Write a fact once, in the file that owns it:

| File | Owns | Update it when |
|---|---|---|
| [`../README.md`](../README.md) | what the user can do, and how | a user-facing feature, setting, or startup script changes |
| [`architecture.md`](architecture.md) | how the program is put together: the "Where to Act" map, the data schema, the property lifecycle, the migration strategy, the known fragilities | a file moves, a module is added, a schema concept changes |
| [`invariants.md`](invariants.md) | the rules that must not break, and the regression each one prevents | an invariant is added, retired, or its guard moves |
| [`conventions.md`](conventions.md) | how code is written and tested here | a convention is decided, or the test counts change |
| [`audit.md`](audit.md) | the procedure for a full-project audit: the green baseline, the module-by-module checklist, the invariant→test cross-check | the audit steps change, a module/invariant is added, or a new class of weak point is worth checking for |
| [`../implementation_plan.md`](../implementation_plan.md) | the historical record: why the design is what it is | a "reasonable" assumption is disproven by a real portal (add to §8) |

The rest of `docs/` is user-facing: [`using-the-app.md`](using-the-app.md),
[`features.md`](features.md), [`notifications.md`](notifications.md),
[`datadome.md`](datadome.md), [`availability-check.md`](availability-check.md),
[`remote-access.md`](remote-access.md).

Specifically:

- **Numbers rot silently.** The test count in [Testing](#testing) above and in
  `implementation_plan.md` §7 must match `pytest -q`; the file trees must list the files
  that exist. If a claim is checkable, check it rather than copying it forward.
- **A shipped feature that no .md mentions does not exist for the user.** Map view and
  price statistics both reached production invisible for months because nothing forced this
  check.
- **Document the limitation next to the feature.** Statistics that need three comparables,
  zone slugs that are a best guess: unstated, they read as bugs and get reported as bugs.
- **Prefer deleting to marking obsolete.** Git remembers. A "✅ all phases complete" table
  and a changelog of invariants already stated elsewhere are pure maintenance cost, and the
  second copy is the one that goes stale.
- **Do not open a second backlog inside the code.** No `TODO:` bullets filed for later, no
  "future work" sections in the docs — a deferred idea recorded in a comment is an idea
  nobody will find. It either gets done, gets an issue, or gets dropped.
