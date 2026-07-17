# Roadmap

Conventions and architecture details are documented in developer notes. Completed
items are not tracked here once shipped — the code, its tests, and internal
developer tables are the source of truth for what already exists; this
file only lists what's still ahead.

Ordered by feasibility: easy items reuse infrastructure that already exists
(scheduler, `pricing_stats.py`, `deduplicator.py`); hard items depend on
messy external data or unresolved disambiguation/deduplication problems.
Ideas with low expected value relative to their cost (redundant with
existing keyword filtering, statistically unsound given the app's own
biased data, or working against the project's careful anti-spam and
no-cloud design) were considered and dropped rather than listed here.

An item that would relax a documented invariant or a README claim **names it
explicitly** (e.g. "Relaxes invariant 16"). That is deliberate: the invariants
must keep describing the program that exists today, so the relaxation lands in
the *same commit* that ships the feature — never pre-emptively here. This file
is the map of what to change; it is not itself the change.

---

## Advanced Decision Intelligence & Negotiation Features

These three features transform the platform from a unified local scraper into an active **decision-making engine and negotiation assistant**, leveraging the local SQLite history (`case.db`) to provide insights that no commercial portal allows.

### 1. Ghost Price & Re-listing Memory (Recycled Ad Tracker) — *Feasibility: Medium*
When a property fails to sell after several months, agencies often delete the ad (`status = 'gone'`) and re-publish it weeks later with fresh photos and a new or slightly lowered price to reset the "days on market" counter on portals.
- Extend `deduplicator.py` matching rules (`location + sqm + rooms + floor`) against **properties in `status = 'gone'` older than 30–180 days**.
- When a match is found across re-publications or different agencies, instead of creating a brand new property, **re-link it to the historical "dead" record** and attach a prominent badge:
  `👻 IMMOBILE RICICLATO — Originally listed Jan 2026 at €430k by Agency A (unsold after 160 days). Re-listed today by Agency B at €389k (-9.5%). Total days on market: 245.`
- Provides immense negotiation leverage during property visits against fixed-price claims or synthetic urgency.

### 2. Red Flags Audit & Total Cost of Ownership (`TCO Calculator`) — *Feasibility: Easy/Medium*
Agencies frequently bury critical legal or structural drawbacks in lengthy text descriptions or technical fields (e.g., "locato fino al 2028", "nuda proprietà", "spese condominiali €3,800/anno", "diritto di superficie", "senza ascensore al 4° piano").
- **Automated Red/Yellow/Green Flag Extraction:** Extend `filter_engine.py` / text parsing into a structured audit summary on each card:
  - 🚩 **Red Flags (Legal/Occupancy):** Occupied by tenant with active lease, right of surface ("diritto di superficie"), pending extraordinary roof/facade costs.
  - ⚠️ **Yellow Flags (Structural/Ongoing Costs):** No elevator > 2nd floor, central heating without independent metering, high condo fees (> €250/month).
  - 🟢 **Green Flags (Value Adds):** Recently renovated, energy class A/B, included garage/box, independent heating.
- **Real Monthly TCO Calculator:** Compute realistic monthly living costs combining estimated mortgage payment (`estimated 80% LTV over 30 years at current average rate`) + `condo fees` + `renovation sinking fund buffer` (if condition requires work).

---

## Medium — doable, but with real unknowns

### 1. Neighborhood Services & Safety
- Query OpenStreetMap/Overpass API to evaluate amenities (schools, transit, supermarkets, green spaces) within walking distance.
- Pull municipal safety indices or noise pollution data.
- The API is well-documented and free, but needs reliable geocoding and handling of a free external service's rate limits/timeouts.

### 2. Proxy / scraping-API transport (and the fallbacks it enables)
The highest-leverage change on this list. Almost all of the project's most
fragile code — the cookie harvester, the Camoufox/Playwright fallback, the
block-streak/abort machinery — exists only because scans run from a **residential
IP** DataDome learns to recognize. Routing portal traffic through a rotating
residential proxy, or a DataDome-solving scraping API (Scrapfly/ScraperAPI/Zyte),
removes that root cause and, as a bonus, makes **detail-page fetching** feasible
(recovering the lat/lng missing on ~70% of Immobiliare listings — see item 5).
- Tier A (transparent proxy) is nearly free of code: `scrapers/base.py` already
  injects `proxy_url` into the curl_cffi session — it is mostly config + docs +
  confirming `AdProbe` shares the plumbing.
- Tier B (scraping API) is a small adapter at the single `_fetch_once` choke
  point: rewrite the request to the provider's endpoint and unwrap its JSON, with
  the local path kept as fallback when no key is set.
- Keeping browserless/Apify fallbacks ready for an `api-next` shutdown is the
  same mechanism.
- **Relaxes invariants 8, 16, 18** (they guard the *local* transport; a
  proxy/API path bypasses the residential-IP concern) and **softens README's "no
  cloud required" claim** — the shipping commit must update all four. Recurring
  cost is the honest downside, but a free scraping-API tier (~1,000 calls/month)
  can cover a low-frequency personal scanner.

### 3. Richer Natural-Language Query Parser — category-based proximity
Extend `services/query_parser.py` to understand more descriptive, qualitative
criteria beyond city/price/rooms/sqm — e.g. "quiet residential area", "close to
schools", "low reported crime" — by resolving them against neutral, factual
open data sources (municipal safety indices, OpenStreetMap amenity density,
noise pollution maps — see "Neighborhood Services & Safety" above) rather than
free-text guessing. Overpass + geocoding cover this "category" case directly —
it's work, but not an open research problem.

Any such criterion must be a neutral, factual measure (safety statistics,
amenities, noise, transit) and never a proxy for the ethnic, racial, religious
or national composition of a neighborhood's residents — filtering housing
search results on that basis is housing discrimination and out of scope for
this project, not just unimplemented.

Separately, the *core* free-text parse (city/price/rooms/zone) could gain an
optional LLM backend behind a settings flag, emitting the exact structured
params the deterministic parser already produces and **falling back to it** on
any failure or when no backend is configured. This can stay **offline and free**
via a local model (Ollama), which is what keeps it palatable. **Relaxes the
"deterministic and offline (no LLM)" property of `services/query_parser.py`** —
so it is an *optional, non-default* backend, and the shipping commit updates that
module's docstring/claim rather than removing the deterministic path.

### 4. Read-Only Guest Mode & Tokenized Share Links via Tailscale
- When sharing the live dashboard over LAN or Tailscale (`serve.bat lan` / `serve.bat tailscale`), today any connected device gets unauthenticated full read-write access (`CLAUDE.md` invariant 14), meaning guests can delete profiles, hide properties, or alter settings.
- Introduce an optional read-only guest scope (`/shared/dossier/{token}` or a read-only middleware switch): visitors with the link can explore interactive maps, view photos, and check price charts of specifically shared properties/shortlists, while all mutation endpoints (`POST/PATCH/DELETE` on properties, profiles, settings, and scans) return `403 Forbidden`.
- The simplest first step is a single optional bearer token (setting `api_auth_token`) gating all `/api` routes, attached by `services/api.ts` and stored client-side; empty = today's behavior, so nothing changes for existing loopback users. Entirely free (code only, no external service). **Relaxes invariant 14** to "the bind address **or** a token is the access control" — the shipping commit updates that invariant.

### 5. Backfill missing map coordinates via geocoding
Today ~70% of Immobiliare listings arrive with no lat/lng and ~77 carry only a
zone, so the map is sparse. A geocoder turns "zone + city" (or a full address)
into real pins.
- New `services/geocoder.py`, pure except the outbound call, fail-open (no coords
  on failure — never a wrong pin). **Cache every lookup** by normalized query
  string so the same address is never geocoded twice — this is what keeps it
  inside a free rate limit. Call it from an **opt-in, batched** maintenance
  endpoint, exactly like `repair_listings`, never inside the hot scan path.
- **Free** via **Nominatim (OpenStreetMap)**: the public instance allows 1 req/s
  (ample for a cached opt-in batch) and is self-hostable for unlimited offline
  use. Detail-page fetching (item 2) is the other source of the same data.
- **Relaxes the offline-by-design principle** (one outbound, opt-in, cached call)
  — the shipping commit notes it next to the map feature in README.

---

## Hard — messy external data, disambiguation, or missing data volume

### 1. Official Valuation (OMI)
- Fetch official real estate valuations (OMI - Osservatorio del Mercato Immobiliare) from the Italian Revenue Agency to compare listing prices with official state averages.
- OMI data is published quarterly as PDF/Excel, and OMI zones don't map 1:1 onto the zones portals use — the mapping is manual and fragile, breaking on every update.

### 2. LLM-Assisted Due Diligence Research
- On demand, for a specific property or neighborhood the user is seriously considering, have an LLM run a batch of web searches to collect: recent local news, user opinions/reviews of the building or street (forums, Google reviews of nearby businesses), comparable sale prices nearby, and anything else useful to judge whether it's a sound purchase.
- Summarize the findings into the property card as an optional, explicitly-triggered panel (not part of the automatic scan) — this is exploratory research to inform the user's own judgement, not a score or recommendation.
- Directly in tension with the project's "no cloud" principle (needs an LLM with web-search access, i.e. a paid external API), and result quality depends on whether anything about that specific street/building is online at all — often there's nothing to find.

### 3. Import Agency Emails That Never Mention a Portal
Agencies (Tecnocasa, and countless local ones) mail their own proposals, linking
their own website rather than an Immobiliare/Idealista ad. Today the inbox
import ignores those emails entirely: a listing is identified by its portal ID,
and there is none. Yet the emails often carry *more* than a portal alert does —
the Tecnocasa template states the full address, price, rooms and surface in
plain text, which the portals' alerts do not.

Making them importable means answering the question the portal ID answers for
free: **what makes two of these the same listing, across re-sends and across
agencies?** A candidate key is `(street + house number + city, price, surface)`,
i.e. the same "proof of location" the deduplicator already requires — but with
no ID, a price cut turns one listing into two. That, not the parsing, is the
hard part — an unresolved deduplication problem in the current design, not
just missing parsing code.
