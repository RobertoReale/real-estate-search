# Resilience Plan — De-Milanization & Anti-Bot Diversification

Status: **implemented** (July 2026), except the optional polish in B.6.6
(ghost-cursor step, Nodriver/SeleniumBase engines) which remains open. Shipped:
A.2–A.5 (comuni gazetteer `geo_reference.py` + de-Milanized repair/geocoder
heuristics), B.4 (proxy pool with rotate-on-block), B.5 (ScraperHealthSnapshot
+ dashboard panel + transport-aware health alerts), B.3 (transport policy:
`scrape_api_mode="fallback"` ladder; rungs 2–3 stay reactive as designed).
Deviation worth noting: the flat 30 km plausibility radius of A.4 was replaced
by a **per-comune radius scaled on postal-code count** — a flat radius either
re-admitted the historical "Milano pin in Cernusco" bug (too wide) or rejected
half of Rome (too tight).

This is a design/execution plan, not a changelog. It targets the two
structural weaknesses that a full-project review flagged as the only ones
about *scope* rather than *care*:

1. **Milan-hardcoded heuristics** — city detection, coordinate validation, title
   and agency cleanup are wired to Milan and a fixed agency list, so they
   degrade silently on any other city.
2. **A single anti-bot point of failure** — the whole pipeline rests on getting
   past DataDome from one residential IP with one transport at a time.

Both are already *documented* as limitations (Known Fragilities table, invariant
8, the geocoder/repair rows). The goal here is to turn "documented limitation"
into "engineered mitigation" **without breaking the fail-open philosophy or any
invariant**. Every step below preserves: conservative dedup (1), scrapers never
using CSS classes (2), fail-open probes/geocoding (16, 18, 19), and the
loopback-first access model (14).

Read the two parts independently — they share no code and can ship in either
order. Priorities and a suggested sequence are at the end.

---

## Part A — De-Milanization of the heuristics

### A.1 The problem, grounded in the code

Three places encode "the world is Milan":

| File | What is hardcoded | Failure on another city |
|---|---|---|
| `services/repair_listings.py` | `KNOWN_CITIES` (≈70 literal city names), `is_bad_title` (literal placeholder strings like `"in vendita a milano, milano"` and a fixed agency list `gabetti`/`tempocasa`/…), `_extract_zone_and_title` (agency-prefix regexes for the same named agencies), and the fallback title `"Immobile residenziale - Milano"` | An ad in Bergamo whose subject is not in the 70-name list gets no city; a Cuneo agency's prefix is not stripped; the fallback literally writes "Milano" |
| `services/geocoder.py` | `KNOWN_CITY_BOXES` (26 hand-drawn lat/lon bounding boxes) drives `is_valid_coordinate_for_city` | A correct pin in Lecce is accepted only because the city is *not* in the box list (the `return True` default); a city that *is* in the list but whose box is slightly off silently rejects valid pins |
| `services/repair_listings.py` `_detect_city` | linear scan over `KNOWN_CITIES` with `\bword\b` | Cities outside the list are invisible; multi-word comuni ("Reggio Emilia") work only because they were remembered by hand |

The root cause is the same everywhere: **an enumerated allow-list stands in for
the authoritative set of Italian municipalities**, and Milan's exact string
shapes stand in for "a generic placeholder/agency pattern".

### A.2 The authoritative data source (offline, tiny, official)

Italy has a single canonical list of all ~7,900 municipalities, published by
ISTAT as a permanent-link CSV, refreshed a few times a year:

- `Elenco-comuni-italiani.csv` — comune name, province, region, ISTAT code.
- Municipality **centroids** (lat/lng) are available from GeoNames (`IT.txt`,
  `admin`/`populated place` rows) and, keyed by CAP, from `pgeocode` (a pure-
  Python offline library that ships GeoNames postal data). Either gives a
  `comune → (lat, lng)` centroid table.

Design decision: **bundle a pre-built, compressed dataset in the repo**, do not
fetch at runtime. ~7,900 rows of `name, province, region, lat, lng` is well
under 1 MB as CSV and far less as SQLite. This keeps the Raspberry-Pi/offline
guarantee intact (same spirit as invariant 18's "no network in the hot path")
and removes the ISTAT/GeoNames endpoints from the runtime's trust surface. A
tiny `scripts/build_comuni_dataset.py` (dev-only, like `requirements-dev.txt`)
regenerates it from the two sources when we choose to refresh.

### A.3 The creative shortcut: the user already told us the city

Before reaching for the 7,900-row table, note the app **already knows which
cities matter**: every `SearchProfile.search_url` encodes its city, and
`email_import.profile_criteria` already extracts it. The active profile set is a
tiny, self-adapting "cities I actually monitor" gazetteer. So the city detector
should consult, in order:

1. the cities of the user's **active search profiles** (already parsed, always
   correct for this user, near-zero cost) — this alone de-Milanizes the common
   case for free;
2. the **bundled ISTAT comuni index** (covers imports and ad-hoc text from
   anywhere in Italy);
3. only then give up (return `""`, never a Milan default).

This layering means the expensive general path is a safety net, and the fallback
title becomes `"Residential property - <detected zone or city>"` with **no
literal Milan anywhere**.

### A.4 Design

**A new module `services/geo_reference.py`** (one fact, one implementation —
Conventions), owning the comune data and exposing pure functions:

- `load_comuni() -> ComuneIndex` — lazy, cached, reads the bundled SQLite. Builds
  a normalized-name → `Comune(name, province, region, lat, lng)` map plus a set
  for fast membership. Multi-word and accented names normalized like
  `filter_engine._normalize`.
- `detect_city(text, profile_cities=()) -> str` — the layered detector of A.3.
  Replaces `repair_listings._detect_city`. Word-boundary matching reused from
  the filter engine (no new regex dialect).
- `city_centroid(city) -> tuple[float,float] | None` — replaces the hand-drawn
  boxes.
- `is_plausible_coordinate(lat, lng, city) -> bool` — **distance from the
  comune centroid ≤ R** (R generous, e.g. 30 km, to absorb large metros and
  frazioni) AND inside the Italy bbox. This is strictly better than boxes: it is
  correct for *every* comune, not 26, and it has no silent `return True` default
  — an unknown city falls back to the Italy-bbox check only, which is what the
  boxes' default already did, so no regression.

**Generalize the string heuristics** in `repair_listings.py`:

- `is_bad_title`: replace the literal Milan placeholder list with a **structural**
  matcher — a title is "bad" when it matches the shape
  `^(immobile |residenziale )?(appartamento|…)? in (vendita|affitto) a <comune>(, <comune>)?$`
  for *any* comune, plus the truly generic `n/a`/empty. The agency-name
  substrings become a small, data-driven list loaded from settings
  (`repair_agency_prefixes`, defaulting to the current names) so a user in
  another market extends it without a code change.
- `_extract_zone_and_title`: the agency-prefix strip becomes "strip a leading
  `SOMETHING:` when SOMETHING is title-case and ≤ 4 words" (the generic shape of
  "AGENCY NAME:"), not a fixed alternation of named agencies. Keep the current
  named list as a seed for the settings default so behavior is unchanged on
  Milan.

### A.5 Tasks

1. `scripts/build_comuni_dataset.py` (dev-only) → produces
   `backend/app/data/comuni.sqlite` from ISTAT CSV + GeoNames/pgeocode centroids.
   Commit the built artifact (it is product data, like a fixture).
2. `services/geo_reference.py` with the four pure functions + a `hypothesis`-
   friendly surface. Unit tests: known comuni resolve; a fake city outside Italy
   fails plausibility; a valid Lecce/Bolzano pin passes (the boxes never covered
   them); multi-word/accented names normalize.
3. Rewire `geocoder.is_valid_coordinate_for_city` → `geo_reference.is_plausible_coordinate`;
   delete `KNOWN_CITY_BOXES`. Keep the function name/signature so callers and
   tests don't churn.
4. Rewire `repair_listings._detect_city` → `geo_reference.detect_city(..., profile_cities=...)`;
   delete `KNOWN_CITIES`. Thread the active-profile city set in.
5. Generalize `is_bad_title` / `_extract_zone_and_title` as A.4; move the agency
   seed list to settings (`config.py`), additive.
6. Update docs: the Known Fragilities "repair writes Milan-shaped data" row and
   the geocoder/repair rows in CLAUDE.md — the limitation is being removed, so
   the row changes to describe the general path and its one remaining assumption
   (Italy-only).

### A.6 Invariant & risk notes

- **No behavior change on Milan**: every generalization keeps the current Milan
  strings as the seed default, so existing `test_repair_listings.py` cases stay
  green; add new-city cases beside them (the "regression test with a backstory"
  habit).
- **Fail-open preserved**: `detect_city` returns `""` (not a guess) when unsure;
  `is_plausible_coordinate` still never *invents* a pin, it only accepts/rejects
  — a rejected lookup leaves coordinates NULL exactly as today (geocoder is
  fail-open, invariant 16/19).
- **Size/offline**: the bundled SQLite is < 1 MB and read-only; no runtime
  fetch, so the Pi target and invariant-18 spirit hold.
- **Non-goal**: full international support. Scope stays Italy (the portals are
  Italian). "Italy-only" replaces "Milan-only" — a 300× widening, honestly
  bounded.

---

## Part B — Reducing the single anti-bot point of failure

### B.1 The problem, grounded in the code

`scrapers/base.py` already does more than most: Safari-first TLS impersonation
with self-healing profile resolution (invariant 8), reactive cookie recovery,
optional Camoufox stealth browser (invariant 18), an optional managed
scrape-API transport, and a single `proxy_url`. But the *composition* is manual
and the IP is singular:

- `proxy_url` is **one** proxy, injected as `session.proxies` (`base.py:384`).
  There is no pool and no rotation-on-block — the residential IP is a single
  point of failure, and DataDome scores IPs (2026 research below).
- The escalation between transports (TLS rotate → fresh cookie → browser →
  managed API) is partly reactive but not **driven by a health signal** and not
  **cost-aware**: there is no policy that says "the free path's block rate
  crossed X, escalate" and "we're healthy again, drop back to free".
- There is **no persisted block-rate observability**, so the user cannot see the
  pipeline degrading until scans simply stop finding listings.

### B.2 What the 2026 landscape says (research)

DataDome combines TLS/JA4 fingerprinting, IP reputation, JS challenges, and
per-customer behavioral ML into a trust score. Consistent findings across
current write-ups:

- **No single technique suffices**; you need fingerprint + behavior + proxy +
  (sometimes) JS execution aligned. A residential proxy with a mismatched TLS
  fingerprint still gets blocked — which is exactly why this project's
  Safari-first `curl_cffi` + real cookie approach works at all.
- **Benchmarks (May 2026)**: managed scraping APIs sustained ~**89%** over 24h on
  DataDome targets at the lowest cost-per-extraction; self-hosted
  **Camoufox + residential proxies** sustained ~**67%**. Raw `requests`/plain
  headless ≈ 0.
- **TLS/JA4 mismatch** is a millisecond-fast block signal — engine-level
  fingerprint tools (Camoufox, Patchright) beat proxy rotation alone. The
  project's pluggable `browser_engine` (Camoufox default when installed) is
  already the right instinct; Nodriver / SeleniumBase-CDP are named as strong
  open-source alternatives worth having as pluggable engines.
- **Behavioral signals** (mouse paths) matter for the browser path; a ghost-
  cursor step raises browser success — relevant only to the Camoufox/Playwright
  fallback, cheap to add.

Takeaway: the project already has the *pieces* the research recommends. The gap
is **orchestration, IP diversity, and observability**, plus formalizing the
managed API as the sanctioned high-success fallback rather than an afterthought.

### B.3 Design — a health-driven, cost-aware **transport ladder**

Introduce one policy object, `scrapers/transport_policy.py`, that chooses the
transport for the *next* fetch from a persisted health signal, and escalates
only as far as needed. Rungs, cheapest/most-local first:

| Rung | Transport | Cost | Where it already lives |
|---|---|---|---|
| 0 | `curl_cffi` + TLS rotation + user cookie | free | `base._fetch_once`, invariant 8 |
| 1 | + rotate residential **proxy from a pool** | ¢ | NEW pool (B.4); `proxy_url` today |
| 2 | fresh DataDome cookie via headless browser | free-ish | `cookie_harvester`, invariant 18 |
| 3 | Camoufox + residential proxy (+ ghost cursor) | free-ish | `browser_engine`, `AdProbe.start_browser_session` |
| 4 | **managed scrape API** (Scrapfly/Zyte/ScraperAPI) | € per call | `build_scrape_api_request`, already wired |

The policy is **budget-aware**: it stays on rung 0–1 while the per-portal block
rate is low, and only climbs when a sustained streak crosses a threshold —
reusing the exact signal invariant 11 already computes (`consecutive_failures`
per portal). When health recovers, it **descends** so the paid rung 4 is spent
only during an actual outage. This matches the benchmark economics: free path in
good weather (near-zero cost), managed API's 89% only when it's raining.

Crucially this is **orchestration over existing transports**, not new bypass
code — so invariants 8/16/18 (and their relaxations for the remote path) are
unchanged; the policy just picks which sanctioned path runs.

### B.4 Proxy pool (the missing IP diversity)

- Settings: add `proxy_urls` (list) alongside the existing `proxy_url` (kept as
  a one-element shorthand, backward compatible — additive, invariant-safe).
- `base.py`: pick a proxy **sticky per session**, **rotate on block** (a 403 or
  DataDome wall burns that IP for a cool-down), skip proxies in cool-down. This
  is the single most impactful change per the research (IP reputation is a core
  DataDome layer) and is small.
- Fail-open: an empty pool = today's behavior exactly (direct residential IP).

### B.5 Observability — "know when it's failing"

The real product need is *seeing* degradation. Add:

- A daily persisted `ScraperHealthSnapshot` (like `PricingSnapshot`): per portal,
  attempts / blocks / successes / transport-used. Written at scan completion.
- A small **Scraper Health** panel in the UI (dependency-free, like
  `PriceTrends`): block-rate trend per portal, current rung, last successful
  transport. This turns "scans mysteriously stopped" into a visible signal and
  tells the user *when* to add proxies or a scrape-API key.
- Surface the chosen rung in the existing scan summary/health alert (invariant
  11), so a health alert says *why* ("blocked on rungs 0–3, no scrape-API key
  configured — add one or a proxy pool").

### B.6 Tasks

1. `proxy_urls` pool + rotate-on-block + per-proxy cool-down in `base.py`;
   `proxy_url` becomes its one-element alias. Tests: rotation on `BlockedError`,
   cool-down skip, empty-pool == direct.
2. `scrapers/transport_policy.py`: pure decision fn `choose_rung(health, settings)
   -> Rung` + `on_result(...)` to update health. Fully unit-testable offline
   (no network), like the scheduler's decision helpers.
3. Wire the policy into `scanner`/`base._fetch_once` so each fetch asks the
   policy for its rung; keep every rung's implementation as-is.
4. `ScraperHealthSnapshot` model (additive column/table → auto-migrates) +
   `maybe_snapshot` at scan end; `GET /api/scraper-health`.
5. `components/ScraperHealth.tsx` panel; extend the health-alert text with the
   rung/`why`.
6. Optional, lower priority: ghost-cursor step on the browser rung; register
   Nodriver/SeleniumBase-CDP as additional `browser_engine` options (the plumbing
   already exists, invariant 18).
7. Docs: expand invariant 8/16/18 notes to describe the ladder and the pool;
   add a README "when scraping degrades" section pointing at the health panel.

### B.7 Invariant & risk notes

- **Fail-open everywhere**: a block still yields `None`/unknown, never a wrong
  answer (invariant 16). The ladder changes *what we try next*, never *how we
  interpret an ambiguous result*.
- **Cost is opt-in and bounded**: rung 4 needs a user-provided `scrape_api_key`
  (already the case); with no key the ladder simply tops out at rung 3 and the
  health panel says so — no surprise spend, consistent with the loopback-first,
  no-cloud default.
- **No new fingerprint/bypass tricks are invented** — this is composition and IP
  diversity over the transports the project already ships and documents. That
  keeps the change reviewable and the invariants intact.
- **Residential IP protection** (the reason invariant 16 paces so carefully) is
  *strengthened*: rotating proxies and escalating to a managed API off-loads
  pressure from the one IP the scheduled scans depend on.

---

## Suggested sequence & priority

1. **B.4 proxy pool** — highest impact-to-effort; directly attacks the single-IP
   risk with a small, additive change.
2. **A.2–A.4 comuni dataset + `geo_reference`** — removes the Milan cliff for
   every non-Milan user; self-contained and testable.
3. **B.5 observability** — cheap, and it makes every later tuning decision
   data-driven instead of guessed.
4. **B.3 transport policy** — the orchestration payoff, best done once the pool
   and health snapshot exist to feed it.
5. **A.5 heuristic generalization** + **B.6 optional engines/ghost-cursor** —
   polish once the structural pieces land.

Each item is independently shippable, keeps every invariant, and turns a
documented weakness into a measured, degradable system rather than a cliff.

---

## Sources

Anti-bot landscape and benchmarks (2026):
- [Scrapfly — How to Bypass DataDome (2026)](https://scrapfly.io/blog/posts/how-to-bypass-datadome-anti-scraping)
- [ZenRows — Bypass DataDome, Complete Guide 2026](https://www.zenrows.com/blog/datadome-bypass)
- [ScrapingBee — How to Bypass DataDome](https://www.scrapingbee.com/blog/how-to-bypass-datadome/)
- [ScrapeWise — Bypass DataDome 2026: 4 Methods Tested](https://scrapewise.ai/blogs/bypass-datadome-web-scraping-2026)
- [HumanBrowser — Best Residential Proxy for Scraping 2026](https://humanbrowser.cloud/blog/best-residential-proxy-scraping-2026)
- [Kameleo — Guide to Bypassing DataDome](https://kameleo.io/blog/guide-to-bypassing-datadome)

Address/geography data & tooling:
- [ISTAT — Elenco dei comuni italiani (CSV, official)](https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.csv)
- [ISTAT — Codici delle unità amministrative territoriali](https://www.istat.it/classificazione/codici-dei-comuni-delle-province-e-delle-regioni/)
- [openvenues/libpostal — international address parser](https://github.com/openvenues/libpostal)
- [pgeocode — offline geocoding of postal codes (GeoNames)](https://github.com/symerio/pgeocode)
