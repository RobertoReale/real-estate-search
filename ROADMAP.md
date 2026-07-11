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

## Easy — existing infrastructure, no new unknowns

### 1. Shareable Dossiers & Shortlist Export (Offline HTML/Markdown/CSV Reports)
- Allow one-click export of curated shortlists (favorites), specific property cards with full price-drop history and TCO/Deal Score, or entire search profile results into a self-contained, interactive offline HTML dossier (or clean Markdown/CSV report).
- Can be sent easily via Telegram, WhatsApp, or email to partners, family members, or real estate advisors without exposing the local dashboard or SQLite database to the network.

---

## Medium — doable, but with real unknowns

### 1. Neighborhood Services & Safety
- Query OpenStreetMap/Overpass API to evaluate amenities (schools, transit, supermarkets, green spaces) within walking distance.
- Pull municipal safety indices or noise pollution data.
- The API is well-documented and free, but needs reliable geocoding and handling of a free external service's rate limits/timeouts.

### 2. Cloud Scraper Fallbacks
- Keep alternative browserless/Apify scraping fallbacks ready if the internal `api-next` JSON endpoints change or are shut down.
- Technically simple (these services expose ready-made APIs), but it introduces a recurring cost and a cloud dependency the project doesn't have today — an architectural choice more than a technical one.

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

### 4. Read-Only Guest Mode & Tokenized Share Links via Tailscale
- When sharing the live dashboard over LAN or Tailscale (`serve.bat lan` / `serve.bat tailscale`), today any connected device gets unauthenticated full read-write access (`CLAUDE.md` invariant 14), meaning guests can delete profiles, hide properties, or alter settings.
- Introduce an optional read-only guest scope (`/shared/dossier/{token}` or a read-only middleware switch): visitors with the link can explore interactive maps, view photos, and check price charts of specifically shared properties/shortlists, while all mutation endpoints (`POST/PATCH/DELETE` on properties, profiles, settings, and scans) return `403 Forbidden`.

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
