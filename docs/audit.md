# Full-Project Audit Playbook

This file exists so a full audit of the project can be run **fast and the same way every
time**. It is a *procedure*, not a second copy of the architecture: the source of truth for
what each module does and why is [`architecture.md`](architecture.md) and
[`invariants.md`](invariants.md), plus
[`../implementation_plan.md`](../implementation_plan.md) for the historical "why". This
file only tells you **what to check, in what order, and how to know it is still true**.
When a check here and those files disagree, they are authoritative — fix whichever is
stale.

> Golden rule of this repo (see [`conventions.md`](conventions.md)): **one fact, one
> place.** Do not copy invariant text, thresholds or module descriptions into this file.
> Link to them.

Run an audit when you want a verdict on the current state, or before starting work that
touches a fragile area (the `scrapers/` package, the deduplicator, the migrations).

---

## 0. Green baseline (run first, every audit)

Nothing else matters until these are green. Run them before reading a single line of code,
and again before committing any audit fix.

```bash
# backend tests (offline, deterministic — no network)
cd backend && .venv\Scripts\python -m pytest tests -q

# backend static types (the venv is pinned in backend/pyproject.toml)
cd backend && pyright

# backend lint and formatting — hard gates, like pyright
cd backend && .venv\Scripts\ruff check app tests
cd backend && .venv\Scripts\ruff format --check app tests

# frontend types + production build, then its unit tests
cd frontend && npm run build
cd frontend && npm test

# the browser suite: the production build served against a real backend on a
# throwaway database, and every control in the app driven at least once
# (`npm run e2e:browser` fetches Chromium the first time)
cd frontend && npm run e2e
```

Expected today: **872 passed + 1 skipped** (873 collected; the skip needs the optional
Playwright), **pyright 0 errors**, **ruff clean**, **vite build OK**, **69 frontend tests**,
and **35 browser tests** (15 journeys, then 20 that hold the run to the control inventory).
The last of those prints the two numbers worth reading: **222 interactive elements, 230
inventoried actions**, of which **228 exercised and 2 declared unreachable with a written
reason**. If a test number changed, that is not a failure — it is a documentation trigger
(see §4).

`ruff format --check` belongs in this list and is easy to forget: CI's lint step runs
`ruff check` *and* `ruff format --check`, so a baseline that names only the first is green
locally and red on the very next push.

`npm run e2e` is the slow one — around five minutes against the six seconds the rest of this
list costs — and it is on it anyway, because it is the only gate that runs the *assembled*
product and the only one that can notice a control that quietly stopped working. Two things
turn it red that nothing else here can: a screen that scrolls sideways or fails an `axe-core`
check at 390, 768 or 1440 px, and a control added without an entry in `frontend/e2e/actions.ts`.
CI runs it on every push, so skipping it locally moves the failure rather than avoiding it.

To fetch a portal page live during verification, use `AdProbe` (`scrapers/probe.py`), never
a cold browser — it injects the real `datadome_cookie`. See
[`conventions.md` → Testing](conventions.md#testing) for the exact snippet and why.

---

## 1. Invariant audit (are they *true*, are they *necessary*?)

The 22 invariants live in [`invariants.md`](invariants.md). Each one has: a history (a real
past regression, or for 22 the shipped defect it keeps from returning), a code home, and at
least one regression test. To audit an invariant:

1. **Necessary?** Read its paragraph. Every invariant records a bug that actually
   happened — if you cannot find the regression it prevents, that is the finding. None are
   currently redundant.
2. **True in code?** Open the code home (below) and confirm the guard is still there and
   still shaped the way the invariant describes.
3. **Covered?** `grep` the tests for the invariant number or its keyword; a claim with no
   test is a gap to report.

| # | Topic | Primary code home | Test file |
|---|---|---|---|
| 1 | Conservative dedup (±5%, location proof) | `services/deduplicator.py` `_matches_property` | `test_deduplicator.py` |
| 2 | Scrapers never use CSS classes | `scrapers/html_cards.py` `find_card_container` | `test_scrapers.py` |
| 3 | First scan = zero notifications (`baseline_done`) | `services/scanner.py` `_scan_profile` | `test_scanner.py` |
| 4 | Keywords on word boundaries | `services/filter_engine.py` | `test_filter_engine.py` |
| 5 | `hidden`/`sold` are sacred (scan never reverts) | `services/scanner.py`, `routers/properties.py` DELETE route | `test_scanner.py`, `test_dashboard_management.py` |
| 6 | `price_changed` = minimum-price change | `services/deduplicator.py` `_refresh_min_price` | `test_deduplicator.py` |
| 7 | Immobiliare API needs resolved geo params | `scrapers/immobiliare.py` | `test_scrapers.py` |
| 8 | TLS impersonation list, Safari first, self-healing | `scrapers/transport.py` `resolve_impersonations` | `test_scrapers.py` |
| 9 | Never merge across contracts | `services/deduplicator.py` `_find_matching_property` | `test_deduplicator.py` |
| 10 | User-curated fields untouched by scans | `services/deduplicator.py`, `routers/properties.py` PATCH | `test_deduplicator.py` |
| 11 | Health alert fires on a streak, once | `services/scanner.py` `_update_profile_health` | `test_scanner.py` |
| 12 | *retired with the inbox import (see [`invariants.md`](invariants.md))* | — | — |
| 13 | StaticFiles mount stays last in `main.py` | `main.py` (bottom: after every `include_router`) | `test_static_frontend.py` |
| 14 | Unauthenticated API → bind address is the control | `run.py`; `services/telegram_bot.py` (polls, never a webhook) | `test_api_auth.py`, `test_telegram_actions.py` |
| 15 | *retired as written; the sync-`def` + module-lock rule now binds the availability check* | `services/availability_check.py`, `routers/properties.py` | `test_availability_check.py` |
| 16 | Availability probe fails open; every batch guard | `scrapers/probe.py` `AdProbe`, `scrapers/page_text.py`, `services/availability_check.py` | `test_availability_check.py`, `test_scrapers.py` |
| 17 | Settings tests must not read real `settings.json` | `tests/conftest.py` | (all tests) |
| 18 | Cookie harvester optional/opt-in/fail-open; engines | `services/cookie_harvester.py` `_launch`, `scrapers/probe.py` | `test_cookie_harvester.py`, `test_scrapers.py` |
| 19 | `Property.source` upgrade-only ("email" now historical) | `services/deduplicator.py` | `test_dashboard_management.py` |
| 20 | Delete-a-search removes only provably-its-own | `services/data_reset.py` `profile_results` | `test_data_reset.py` |
| 21 | A search can be silenced without being paused | `services/notifier.py` `profile_channels`, `services/scanner.py` | `test_scanner.py`, `test_features.py` |
| 22 | OMI band never replaces the listing median, and neither is shown unlabelled | `services/omi_benchmark.py`, `services/deal_score.py` `_score_property`, `services/exporter.py` `_print_facts`, `frontend/src/components/PropertyModal.tsx` `PriceBenchmarks` | `test_omi_benchmark.py` |

---

## 2. Module-by-module review order

Review in dependency order (leaves first), so a bug is understood before its callers. For
each module: confirm it still matches its
[`architecture.md`](architecture.md#where-to-act-for-each-type-of-modification) row, has no
logic that contradicts an invariant, and that its tests still exercise the tricky path.

1. **Scraping core** — `scrapers/transport.py` (8), `parsing.py`, `page_text.py` (16),
   `html_cards.py` (2), then `base.py` (the pipeline) and `probe.py` (16, 18), then
   `immobiliare.py` (7), `idealista.py`.
2. **Pure services** — `filter_engine.py` (4), `deduplicator.py` (1, 6, 9, 10, 19),
   `search_builder.py` (portal tokens — **measured, never guessed**, see the two token rows
   in [`architecture.md`](architecture.md#where-to-act-for-each-type-of-modification)),
   `query_parser.py`, `match_score.py`, `deal_score.py`, `pricing_stats.py`,
   `market_velocity.py`.
3. **Stateful services** — `scanner.py` (3, 9, 11, 21), `notifier.py` (21),
   `telegram_bot.py` (5, 10, 14), `availability_check.py` (15, 16), `cookie_harvester.py`
   (18), `search_validator.py`, `data_reset.py` (3, 5, 10, 20), `backup.py`,
   `scheduler.py`, `exporter.py`.
4. **Edges** — `models.py` / `schemas.py` (keep aligned with `frontend/src/types/`),
   `database.py` (additive + Alembic migrations — run `test_migrations.py`), `config.py`,
   `routers/` (one module per route group; `selection.py` is the shared grid/map/export
   query), `main.py` (middleware + registration order; mount last, invariant 13).
5. **Frontend** — types match `schemas.py`; phone-first responsive rules
   ([`conventions.md`](conventions.md#writing-code)). Not covered by automated tests: verify
   via `scripts\windows\start.bat`.

---

## 3. Known weak points to check explicitly

These are the real fragilities. They are not bugs, but they are where bugs will appear —
audit them on purpose.

- **`listing_text.py` is a heuristic, not a parser** (`is_bad_title`,
  `is_placeholder_zone`). It decides whether a title or zone is portal boilerplate from its
  structure plus the comuni gazetteer, so a comune name that is also an ordinary word can
  fool it. Both readers fail towards keeping the existing text. Flagged in
  [`architecture.md` → Known Fragilities](architecture.md#known-fragilities--how-to-recognize-them).
- **Physical Property deletion happens in more than one place.** Invariant 20 owns the
  *user-facing* delete (`data_reset.delete_profile_results`), and
  `clear_dashboard`/`factory_reset` delete all of them. When auditing "what can remove a
  card", check all three, not just invariant 20's.
- **Live scraping cannot be tested offline** (DataDome). The suite simulates the portal
  HTML; the real fetch is only ever verified by hand with `AdProbe`. Treat a green suite as
  "logic is correct", not "the portal still parses".
- **Portal filter tokens rot when the portals change their UI.** Every token in
  `search_builder.py` was measured against a portal result total, never inferred. Re-measure
  with a known-good control before trusting a sweep (see the token rows in
  [`architecture.md`](architecture.md#where-to-act-for-each-type-of-modification)).
- **`Property.last_seen_at` is freshened by the availability check** even on an
  `unknown`/blocked probe result (`availability_check.py`). That can delay scheduled
  gone-marking by up to `GONE_AFTER_DAYS`. Intended (we did contact the ad), but re-check if
  gone-marking ever looks lazy.

---

## 4. Documentation consistency (numbers rot silently)

[`conventions.md` → Documentation Is Part of the
Change](conventions.md#documentation-is-part-of-the-change) owns this rule; the audit
enforces it:

- The test count must match `pytest -q` in **both**
  [`conventions.md` → Testing](conventions.md#testing) **and** `implementation_plan.md` §7.
  (These drifted apart once — 330 vs 401 — fixed.)
- The file trees in `implementation_plan.md` §6 and the "Where to Act" table in
  [`architecture.md`](architecture.md#where-to-act-for-each-type-of-modification) must list
  every file in `backend/app/**`. A shipped module absent from the docs "does not exist for
  the user".
- Every backend service should have a "Where to Act" row. Cross-check with:
  ```bash
  ls backend/app/services/*.py
  ```

---

## 5. What a clean audit looks like

- §0 baseline all green.
- Every invariant traced to live code and a test.
- No `backend/app/**` file missing from the docs.
- Doc numbers match `pytest`.
- Weak points in §3 re-confirmed as "known and contained", not "surprising".

Record anything that failed these as a fix in the same session, with a test when it is a
code fix.
