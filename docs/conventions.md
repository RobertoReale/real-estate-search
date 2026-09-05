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

- **No component calls `api.*` directly.** Every read is a keyed query and every
  write a mutation, declared in `frontend/src/queries/` and used through its hook;
  `services/api.ts` stays the one place that knows about HTTP, and the two
  functions it exports that are *not* fetches (`exportUrl`, `backupUrl` build a
  URL for the browser to navigate to) are the only things a component imports
  from it. The rule buys three things that were each hand-rolled per component
  before, and each of which was a bug once: a slow answer for a filter the user
  has moved off cannot reach the screen, because a response belongs to the key it
  was asked for; a write says what it changed by naming a key prefix rather than
  by calling a `refresh()` its caller happened to own; and "loading" and "failed"
  are read off the query instead of being two more `useState` flags with a
  `finally` that can forget to clear them. Add the key to `queries/keys.ts` — a
  key spelled two ways is two caches that never hear about each other, which
  presents as a panel that silently stops refreshing.

- **A failed *operation* goes to the toast; a failed *read* stays where its data would
  have been.** `components/Toast.tsx` owns every `catch` in the frontend: no component
  keeps an error banner of its own, because eleven of them each printed `e.message` and
  stopped there — so "Failed to fetch" (the backend is not running) read exactly like a
  request the backend had considered and refused, and neither told the user what to do
  next. `toasts.fail(e, …)` adds that sentence from the *shape* of the failure rather than
  from its words, which is why `api.ts` throws `ApiError` carrying the status and uses
  status `0` for a request that never arrived. Three things stay out of it, and the reason
  is the same in each case — the message belongs where the user is already looking:
  a surface's own read state (the log tail, the scraper health strip, the backups list)
  renders in place, muted, not as an alert; form validation stays on the field it is about,
  with `aria-invalid` and `aria-describedby`; and the dashboard grid is the one operation
  that *does* toast, because it keeps the last answer on screen rather than blanking, so
  there is no hole to put a message in. Anything destructive that the backend can reverse
  (`hide`, "no longer on the market", the bulk equivalents) ships an Undo on its success
  toast — `bulk_action` accepting `restore` is what makes that possible, and it is the only
  caller of it, since no button sends `restore` on its own.

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
  2. `Button`'s default size carries `min-h-touch sm:min-h-0` — a 44 px touch target on a
     phone, the original density on a mouse-driven desktop. `--spacing-touch` is a named
     token precisely so the number is not retyped as `11` at each new control, and the
     `sm` size omits the minimum on purpose: the filter bar and the batch bar are measured
     for horizontal overflow at 390 px, and growing every dense button is a layout change
     wearing the clothes of a token change;
  3. full-height panels use `dvh`, never `vh`, since `vh` spans behind a mobile address
     bar and pushes a modal's footer buttons out of reach;
  4. a row of groups that cannot fit side by side must say so: a `flex` bar of controls
     needs `flex-wrap`, and a block that should claim its own line gets `w-full
     sm:w-auto`. Wrapping left implicit is how the filter bar's Grid/Map switch and the
     search rows' URLs each pushed the document 150 px past a 390 px viewport;
  5. **a utility passed from a call site does not automatically win.** Against the
     remaining `.btn-*`, `.input` and `.chip-*` classes it never does: they are defined in
     `index.css` outside any `@layer`, and un-layered CSS beats layered CSS whatever the
     selectors look like. Against a primitive it is worse than that, because it is not
     decidable by reading — `<Button className="px-2">` puts two utilities from the same
     group on one element, and Tailwind resolves those by stylesheet order rather than by
     the order of the class attribute. Either way, write `!px-2` when you mean it (as
     `AppShell.tsx`, `ProfileList.tsx` and `Calculators.tsx` do). A padding or width that
     "has no effect" is almost always this.

  Fixed widths (`w-36`, `w-56`) must always be written `w-full sm:w-36`. `.input` jumps to
  16 px below `sm`: anything smaller makes iOS Safari zoom in on focus and never zoom back
  out.

- **A component names a role, never a colour.** `src/styles/tokens.css` holds the design
  tokens in three layers: the palette ramps (`--clay-*` neutral, `--azure-*` accent, and
  the verdict ramps `--sage-*`/`--ochre-*`/`--garnet-*`), then the *roles* those ramps
  serve (`--surface`, `--ink-muted`, `--negative-ink`), then a Tailwind `@theme inline`
  block that turns every role into a utility. `inline` is the load-bearing word: it emits
  `background-color: var(--surface)` into the utility rather than the resolved literal, so
  re-pointing `--surface` inside `.dark` re-points every generated utility at once. That is
  why components carry **no `dark:` variants at all** — the one exception is the Leaflet
  tile filter, which inverts an image rather than picking a colour.

  Light and dark are written out **separately**, not derived from one another. Two things
  change shape rather than value between them: surfaces climb *away* from black as they
  come forward in dark, and elevation stops being a cast shadow — invisible on a dark
  ground — and becomes a lighter surface plus a brighter edge.

  `src/styles/tokens.test.ts` enforces the rule: it scans every `.tsx`/`.ts` under `src/`
  and fails on a Tailwind ramp utility (`bg-blue-600`, `dark:text-slate-500`), on
  `text-white`/`bg-black`, and on an arbitrary colour value (`bg-[#2563eb]`), which is the
  same thing wearing brackets. Roles that borrow a Tailwind ramp name are why the pattern
  insists on a numeric shade: `bg-neutral-soft` is what the rule asks for, `bg-neutral-500`
  is what it forbids.

- **Contrast is measured, not eyeballed.** The browser suite fails a screen carrying any
  *serious* `axe-core` violation, and colour contrast is the one that fires most. Two rules
  fall out of it, and both are written into the token file next to the values they explain:
  every light `*-ink` is the **700** step of its ramp, never the 600 — on a near-white card
  or its own 100-step chip the 600 step measures between 2.9:1 and 4.1:1, under the 4.5:1
  threshold; and every white-on-colour badge uses an **opaque** fill, since a 600 at 80%
  opacity over a property photo lands anywhere between 3.1 and 4.2:1 depending on the
  picture behind it — a defect that appears for some listings and not others. Hover states
  darken rather than lighten for the same reason.

  Dark mode needs its own floor, not the light one reused: `--clay-450` exists solely
  because `--ink-dim` at clay-500 clears 4.5:1 on white but only reaches 3.06:1 on the
  darkest panel it lands on. The consequence is that dim and muted sit closer together in
  dark than in light, which is what a dark ground costs rather than an oversight.

- **A screen composes a primitive; it does not draw a control.** `src/ui/` holds the
  sixteen — `Button`, `IconButton`, `Chip`, `Card`, `Field`, `Input`, `Select`, `Checkbox`,
  `Dialog`, `Sheet`, `Popover`, `Tooltip`, `Tabs`, `Toast`, `Skeleton`, `EmptyState` — and a
  new screen reaches for one rather than for a class string. Loudness is two declared axes,
  `variant` (`solid`/`outline`/`ghost`) × `tone` (`neutral`/`accent`/`positive`/`caution`/
  `negative`), written as a union in `ui/tone.ts` so a combination with no correct drawing
  fails `tsc` instead of rendering an undrawn one. That is the rule the batch bar broke:
  six buttons, six class strings, two of them hovering towards `caution` for adding and
  removing a favourite, and one with no border, no hover and **no focus ring at all**.
  Nothing had decided any of it, and nothing in the build could tell a variant somebody
  meant from one they mistyped.

  Everything with an overlay, a focus trap or an `aria-*` relationship is
  [Radix](https://www.radix-ui.com/) underneath. The reason is not convenience: focus
  trapping, Escape handling, `aria-expanded`/`aria-controls` wiring, typeahead in a listbox
  and the return of focus to whatever opened the thing are where hand-rolled overlays go
  wrong quietly, and Radix's are audited by people who do that full time. Where this
  codebase does add to them, it is because the default was wrong *here*: `Dialog` and
  `Sheet` remember the opener themselves (`ui/returnFocus.ts`), since Radix restores focus
  through its own `Trigger` and both of these are opened from a piece of state instead.

- **Icons come from `ui/icons.tsx`, and never from `lucide-react` directly.** The barrel
  names each drawing for the role it plays — `Delete`, not `Trash2` — for the same reason
  `tone.ts` names roles and not colours: a screen that imports `Wallet` to mean "asking
  price" has hidden the meaning in a call site nobody greps for, and a redrawn icon then
  costs a sweep instead of a line. Every icon defaults to `1em` and to `aria-hidden`, which
  is the whole accessibility contract: an icon beside a label would be read out twice, and
  an icon *without* a label is an `IconButton`, which cannot be built without the name.

  What this replaced was emoji, and emoji were never an icon set — the operating system
  drew them, differently on each one, at a size the font chose, in a colour nothing could
  change. They were also in the dictionaries rather than in the components (`"⚙️ Settings"`),
  which is why `ui/icons.test.ts` reads the source of `src/components`, `src/ui`,
  `src/routes`, `src/i18n` and `src/App.tsx` and fails on any `\p{Extended_Pictographic}`.
  A label is interface wherever it is stored.

  Five things kept their hand-rolled markup when the screens moved onto the primitives,
  and each is a decision rather than a leftover. **Native `<select>` stays native**: the
  browser suite drives a dropdown with Playwright's `selectOption`, which only works on a
  real `<select>`, and on a phone the platform picker is better than any listbox this app
  could draw. **The modal frames stay hand-rolled** — `PropertyModal`, `SettingsModal`,
  `LogViewer` and the search-profile delete dialog carry inventoried ids on their backdrop
  and their panel, and neither can be forwarded onto Radix's overlay. **The two
  select-all checkboxes stay native**, because their indeterminate state is set from a ref
  and moving them is a behaviour change in a bar the browser suite measures. **`PortalBadge`
  keeps its own tints**: `Chip`'s tones are verdicts, and nothing should be able to render
  "Idealista" in the colour that means "good deal". And **the navbar's icon-only controls
  are `Button` with an `aria-label`, not `IconButton`** — the latter is square by
  construction, and three 40 px squares are the 18 px that used to push that row past a
  390 px viewport.

  Two things stay out of `src/ui/`. Strings — every label a user reads is a prop, because
  the interface is Italian and a primitive that spelt its own close button would be one
  English word nobody could find. And decisions — `components/Toast.tsx` still owns *when* a
  message is raised and what advice goes on it; `ui/Toast.tsx` owns only its drawing.

---

## Testing

- **1025 backend tests** in `backend/tests/`, all offline (simulated HTML + in-memory
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

- **The frontend has unit tests too** (276 in thirty-five files: vitest +
  `@testing-library/react`, run `cd frontend && npm test`). They cover the pure logic that
  used to be invisible — the `propertyParams` codec in `services/api.ts` first, since a
  filter silently dropped from the querystring vanishes from both the grid and the export
  with nothing failing; then `routes/params.test.ts`, which is the same hazard aimed at the
  user rather than at the backend, since every assertion in it is about a link somebody
  sent to somebody else (a default that leaks makes an unreadable URL out of an untouched
  dashboard; a default dropped on the way back in hands the recipient a different grid);
  then `humanizeFloor`, and the i18n core (`i18n/i18n.test.ts`): key
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
  `styles/tokens.test.ts` is the odd one out — it asserts nothing about behaviour, it reads
  the source tree and fails on a hand-typed colour, because the alternative to a rule is
  six near-identical buttons that differ by accident and a build that cannot tell.

- **Component tests exist where the defect is only visible in a rendered tree.** Not for
  pixels — for six things a pure test cannot reach, each written after the bug it now
  guards: that a label actually names its control (`FiltersBar.test.tsx` uses
  `getByLabelText`, which only resolves through a real `htmlFor`/`id`), that a property card
  offers a focusable, named way into the listing *without* itself becoming a control that
  contains controls (`PropertyCard.test.tsx`), that a dialog whose data fails to
  load still renders something dismissable (`SettingsModal.test.tsx`), that a refresh on a
  timer never has two requests for the same thing in the air at once, since the older one
  answering last is the older one winning (`LogViewer.test.tsx`), and that the OMI band
  never reaches the screen undated, unmarked when out of date, or uncredited
  (`PropertyModal.test.tsx` — the attribution is a licence obligation, so a refactor that
  drops the line is a legal defect and not a cosmetic one, and the figures around it would
  still be right), and that a failure reaches the screen carrying what to do about it and
  a way to do it (`Toast.test.tsx`: a backend that never answered and one that considered
  the request and refused it produce different advice, and pressing Try again runs the
  retry exactly once and takes the message with it). `App.test.tsx` mounts under
  `StrictMode` on purpose: its double
  invocation of `useState` initializers is the bug, so nothing weaker reproduces it.

  The primitives in `src/ui/` are tested one file per component, and each of those files
  asks the same two questions: can it be operated with the keyboard alone, and does
  `axe-core` find anything in the tree it produces (`src/test/axe.ts`). The keyboard half is
  the point — an overlay is only as good as the way out of it, so the dialog test presses
  Escape, tabs round the trap and asserts the opener has the focus back, and the toast test
  reaches the Undo through the viewport hotkey. Three of the sixteen draw nothing
  interactive (`Chip`, `Card`, `Skeleton`); their keyboard test asserts the honest thing,
  which is that Tab passes them by rather than stopping on decoration.

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
  would make the inventory grow with the data instead of with the app. The primitives in
  `src/ui/` are the one place the scanner reads differently, and it is not a loophole
  either: the directory itself is skipped, because `Button` has no identity until a screen
  uses one, while the primitive names are demanded an id **everywhere else**, exactly as
  `<button>` is. Migrating a control from a lowercase tag to one of them changes nothing
  about what the gate asks of it — which is the point, since the alternative was a gate
  that shrank silently the day a screen stopped writing `<button>`.

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
