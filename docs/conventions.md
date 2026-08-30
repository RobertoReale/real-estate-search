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

- **Windows-only code carries a targeted type-check suppression.** `ctypes.windll` and
  friends do not exist off Windows, and the types are checked on Linux as well — CI runs
  there, because the Raspberry Pi is a real target — so a Windows-only call site needs a
  `# pyright: ignore[reportAttributeAccessIssue]` on the line itself. A local `pyright`
  run on Windows is green and cannot warn you about this. Same shape as the optional
  imports of `playwright` and `camoufox`: a targeted ignore at the call site, never a
  blanket rule disable, and never `pythonPlatform` pinned to Windows — that would silence
  the checker for one of the two platforms the app actually ships to.

- **Responsive UI: phone-first, desktop restored at `sm`.** The dashboard is served to
  phones (see `serve.bat`), so every control row must survive 390 px. Five patterns
  recur, each with a reason:
  1. dense control rows are `grid grid-cols-2 … sm:flex sm:flex-wrap`, and the
     `col-span-2` on wide fields needs no `sm:` prefix because `grid-column` is inert on a
     flex item;
  2. `.btn-primary`/`.btn-ghost` carry `min-h-11 sm:min-h-0` — a 44 px touch target on a
     phone, the original density on a mouse-driven desktop;
  3. full-height panels use `dvh`, never `vh`, since `vh` spans behind a mobile address
     bar and pushes a modal's footer buttons out of reach;
  4. a row of groups that cannot fit side by side must say so: a `flex` bar of controls
     needs `flex-wrap`, and a block that should claim its own line gets `w-full
     sm:w-auto`. Wrapping left implicit is how the filter bar's Grid/Map switch and the
     search rows' URLs each pushed the document 150 px past a 390 px viewport;
  5. **a utility cannot override a `.btn-*`, `.input` or `.chip-*` class.** Those are
     defined in `index.css` outside any `@layer`, and un-layered CSS beats layered CSS
     whatever the selectors look like — so `className="btn-ghost px-2"` renders at the
     `px-4` the component class carries, silently. Write `!px-2` when you mean it (as
     `Navbar.tsx` and `ProfileList.tsx` do). A padding or width that "has no effect" is
     almost always this.

  Fixed widths (`w-36`, `w-56`) must always be written `w-full sm:w-36`. `.input` jumps to
  16 px below `sm`: anything smaller makes iOS Safari zoom in on focus and never zoom back
  out.

- **Text and fills are chosen against the background, not by eye.** The browser suite
  fails a screen carrying any *serious* `axe-core` violation, and colour contrast is the
  one that fires most: against this app's own surfaces (`.glass` resolves to slate-100,
  `.panel` to slate-50) the stock 400 and 500 slate shades measure 2.5:1 and 4.3:1, both
  under the 4.5:1 threshold. Hence the light values in `index.css`: `t-muted`, `t-dim`,
  `accent-good` and `accent-bad` sit a step darker than they read as a design, and every
  white-on-colour badge uses an **opaque 700** fill — a 600 at 80% opacity over a
  property photo lands anywhere between 3.1 and 4.2:1 depending on the picture behind it,
  which is a defect that appears for some listings and not others. Hover states darken
  rather than lighten for the same reason. A genuinely three-step neutral scale needs a
  custom palette rather than stock `slate`, and does not exist yet.

---

## Testing

- **845 backend tests** in `backend/tests/`, all offline (simulated HTML + in-memory
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

- **The frontend has unit tests too** (69 in fourteen files: vitest +
  `@testing-library/react`, run `cd frontend && npm test`). They cover the pure logic that
  used to be invisible — the `propertyParams` codec in `services/api.ts` first, since a
  filter silently dropped from the querystring vanishes from both the grid and the export
  with nothing failing; then `humanizeFloor`, and the i18n core (`i18n/i18n.test.ts`): key
  parity between `en`/`it`, **matching `{placeholder}` sets per key** (a dropped `{count}`
  leaves a hole in one language only), no empty translation, interpolation, and the startup
  language resolution. `components/settings/sections.test.ts` is the same hazard one level
  up: the settings save is the **union of eight sections' payloads**, so a field dropped
  from one section's `write` stops persisting while the form still renders it and the
  request still returns 200 — the test pins the whole key set, the round-trip, and the "an
  empty secret field means keep the stored one" rule. `services/export.test.ts` pins the
  authenticated dossier path onto the *same* `exportUrl`, since a second querystring builder
  is how a dossier would stop mirroring the screen. `i18n/render.test.tsx` closes the gap
  `i18n.test.ts` cannot reach: it renders real components in **both** languages, because the
  dictionaries being correct as *data* says nothing about the module-level locale
  `I18nProvider` assigns during render — and that is the half `formatPrice`, `humanizeFloor`
  and MapView's tooltips depend on. Freeze it and the words still switch while the prices,
  dates and floor labels keep formatting the old way; nothing else in the suite notices.

- **Component tests exist where the defect is only visible in a rendered tree.** Not for
  pixels — for five things a pure test cannot reach, each written after the bug it now
  guards: that a label actually names its control (`FiltersBar.test.tsx` uses
  `getByLabelText`, which only resolves through a real `htmlFor`/`id`), that a property card
  offers a focusable, named way into the listing *without* itself becoming a control that
  contains controls (`PropertyCard.test.tsx`), that a dialog whose data fails to
  load still renders something dismissable (`SettingsModal.test.tsx`), that an effect's
  abandoned request cannot repaint the screen (`LogViewer.test.tsx`), and that the OMI band
  never reaches the screen undated, unmarked when out of date, or uncredited
  (`PropertyModal.test.tsx` — the attribution is a licence obligation, so a refactor that
  drops the line is a legal defect and not a cosmetic one, and the figures around it would
  still be right). `App.test.tsx` mounts under `StrictMode` on purpose: its double
  invocation of `useState` initializers is the bug, so nothing weaker reproduces it.

- **There is a third tier: the browser suite** (`frontend/e2e/`, run `cd frontend && npm
  run e2e`; `npm run e2e:browser` fetches Chromium the first time). It is the only thing
  here that runs the *assembled* product — the production build, served by `vite preview`
  against a real backend on a database seeded with the demo corpus — so it is where a
  defect that is invisible to every part in isolation gets caught. Its shape and the ports
  it owns are in [`architecture.md`](architecture.md#where-to-act-for-each-type-of-modification);
  the two rules that bind anything written into it are that it **never touches port 8000
  or `backend/case.db`**, and that it **never reaches the network** — an off-harness
  request is aborted and fails the test, because a suite that silently depends on a tile
  server or a placeholder-image service goes red on somebody else's outage, and portal
  traffic from a test run is spent against the residential IP the real scans need. A spec
  asserts what a user can see and name — a role, a label, visible text — and **never a CSS
  class**: the classes are being rewritten wholesale, and a suite pinned to one goes red on
  a rename while staying blind to a button that stopped working. The single exception is
  `data-action`, and it is the opposite case rather than a loophole: an identity a control
  *declares* in order to be named, kept in step with the inventory in `e2e/actions.ts` by a
  gate that fails the build if the two drift.

- **Which tier a new test goes in is decided by what the defect needs in order to be
  visible**, never by which harness is nearest to hand. Pure logic — a codec, a formatter,
  a dictionary, a payload built from eight sections — is a vitest, because a test that can
  be written against a function should be. A defect that is a *relationship between
  elements* — a label that must actually name its control, a dialog that must stay
  dismissable when its data never arrives — is a component test, since nothing weaker
  renders the relationship. Everything else is the browser suite: a real backend, the built
  bundle rather than the dev server, layout at a given width, tab order, and what a control
  actually does end to end. The rule cuts both ways and the second half is the one that
  gets forgotten — the browser suite costs around five minutes against six seconds, so
  putting something in it that a unit test could prove makes every future run slower for
  nothing, and it is the tier a hurried change is most tempted to reach for.

- **Every interactive control is inventoried, and that is a gate rather than a habit.**
  Any element in `src/` carrying an `onClick`, `onChange`, `onSubmit` or `onKeyDown` — or a
  `<form>` — declares a `data-action="<domain>.<verb>"`, and `e2e/actions.ts` carries one
  row per id saying what the control is and what it must do. **A change that adds, moves or
  removes a control updates that inventory and the spec that fires it, in the same commit.**
  Forgetting is not a matter of discipline: a handler with no id, an id with no row, a row
  with no control, or a row nothing exercised each fails `npm run e2e`, and the mechanism is
  described in [`architecture.md`](architecture.md#where-to-act-for-each-type-of-modification).
  A control the suite genuinely cannot fire costs a written reason in `blocked`, and that
  field is the one thing here worth being strict about: an empty escape hatch would keep the
  gate green by quietly shrinking what it checks, which is the failure mode this whole
  arrangement exists to prevent. One row per *control*, not per rendering — a checkbox
  inside a `.map` is one control the user meets several times, and splitting it per item
  would make the inventory grow with the data instead of with the app.

- **Every screen a journey reaches is held to two invariants**, applied by `checkScreen`
  at 390, 768 and 1440 px: the page must not scroll sideways, and `axe-core` must report no
  *serious* or *critical* violation. They are per-screen rather than per-test because they
  are properties of any screen the app can produce, and a journey that visits four of them
  should say which one broke. Both are soft assertions, so a run reports the whole list
  instead of the first item on it.

- **Tests DO NOT cover:** the real network fetch (DataDome cannot be simulated), the
  APScheduler wiring itself (its decision helpers — catch-up, backup freshness — are
  tested), and how the UI *looks*. Layout is now covered where it is objectively wrong — a
  page that scrolls sideways at 390 px, a control nothing can name — but nothing checks
  whether a screen reads well, and that judgement stays manual (`start.bat`). Leaflet is
  the one thing the *unit* tier cannot reach at all (`L.map` on jsdom's zero-sized container
  measures nothing), so the browser suite is where the map's pins are asserted; its
  drawing tools are still verified by hand.

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
| [`development-cycle.md`](development-cycle.md) | the procedure a change follows: the unit of work, the gates before the commit, when behaviour earns an invariant, and how a release is cut | the branch/commit convention, the gate timing, the automation that runs unasked, or the release procedure changes |
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
