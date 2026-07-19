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

### 1b. Additional stealth browser engines (Nodriver / SeleniumBase-CDP)
The behavioral ghost-cursor step and the `BrowserEngine` adapter seam are
shipped (`scrapers/humanize.py`, `scrapers/browser_engine.py`); what remains is
registering Nodriver and/or SeleniumBase-CDP as extra `browser_engine` options
behind that seam. Mostly redundant with Camoufox (diversification, not a new
capability, at +150–300 MB per optional browser) — worth doing only if the
Scraper Health panel shows the Camoufox rung getting challenged regularly.
See `docs/plan-browser-humanization.md` §2.

### 2. Detail-page fetching for the fields cards omit
With a clean transport (the shipped scraping-API path, or a proxy), fetching each
ad's **detail page** becomes feasible — the search cards leave out the lat/lng
missing on ~70% of Immobiliare listings, the full address, and the energy class.
The scraping-API adapter at `_fetch_once` already returns solved HTML for any
URL, so the remaining work is a per-listing enrichment pass (opt-in, batched, off
the hot scan path) and parsers for the detail-page shape. Geocoding (now shipped)
covers the coordinates gap from the other side; this recovers the rest.

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

(The *core* free-text parse already has an optional LLM backend — shipped, off
by default, offline-capable via Ollama; this item is only the qualitative
"category-based proximity" extension on top of it.)

### 4. Read-Only Guest Mode & Tokenized Share Links via Tailscale
- The optional bearer token (`api_auth_token`) that gates all `/api` routes is
  **shipped** (invariant 14), so a wider bind is already safe. What is still
  ahead is a **read-only guest scope**: today the token is all-or-nothing —
  anyone who has it gets full read-write access.
- Introduce a read-only guest scope (`/shared/dossier/{token}` or a read-only
  middleware switch): visitors with the link can explore interactive maps, view
  photos, and check price charts of specifically shared properties/shortlists,
  while all mutation endpoints (`POST/PATCH/DELETE` on properties, profiles,
  settings, and scans) return `403 Forbidden`. Entirely free (code only).

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
