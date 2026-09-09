# What This Software Cannot Do

Every limit this app has, and the screen that states it.

The rule the list exists to enforce: **a limit is stated where it bites, not on a page
nobody opens.** A page cap the user meets as "why are there only 250 listings" is a bug;
the same cap printed beside the count is a fact. So this file is not the place the
limits are announced — it is the checklist that keeps the announcements honest. Each row
names the limit, where the number comes from, and the surface that says it out loud; the
second table then answers the question the first one provokes, which is what it would take
to make the limit go away.

Three rules hold across the whole list.

**A limit is not a warning.** Most of these are fine — a zone matched by name, a pin on
a district centre, a walk measured on the road network. They render quietly, in the same
weight as the small print around them (`Limit` with the default `note` tone). Alarm
colouring is reserved for the two that mean *the answer in front of you is not the whole
answer*: a portal that refused the request, and a search that stopped at the page cap.
Twelve caution-coloured lines would train the eye to skip past the one that matters.

**No number is written twice.** Every figure below arrives from the setting or the
response that owns it, and reaches the copy as a placeholder. A hardcoded "10 pages" in
a translation string is a lie the moment someone changes `max_pages_per_search`. The
"Number comes from" column is the load-bearing one — if a row's number could not be
traced to an API field, the row would not be honest.

**Where one path is more faithful than another, the app says which.** "Both portals were
searched" is true and useless when one of them was searched approximately. The two rows
about zone fidelity do not stop at describing each side; they name the side to trust, at
the moment of choosing.

Each limit carries a `data-limit` id naming the limit rather than the place, so the same
limit stated on two screens carries one id. `frontend/e2e/limits.spec.ts` asserts a
sample of them against numbers the harness backend would never produce on its own, which
is what proves the value came from the API rather than from the sentence.

---

## The inventory

| The limit | Number comes from | Where it is said | `data-limit` |
|---|---|---|---|
| A scan stops at `max_pages_per_search` pages | `ScanJournalEntryOut.page_limit`, and `.total_listings` for what the portal said was there | the scan journal row, in the `incomplete` tone — a truncated run finishes `ok`, so nothing else on that row says it | `scan.pageCap` |
| A portal can refuse, and then the scan is partial | `ScanJournalEntryOut.outcome == "blocked"` | the same row, per portal, in the `incomplete` tone | `scan.portalBlocked` |
| A quick scan stops at the first page holding nothing new, so it read part of the search | `ScanJournalEntryOut.mode` (`full` \| `quick`), with `.pages` for how far it got and `.stopped_because` for why it stopped there | the same row, as the label beside the counts — every entry says which of the two kinds it was, so neither is read as the other | — (a label on every row, not a caution: most scans are quick and that is the intent) |
| Listings come back from outside the area asked for | `ScanJournalEntryOut.outside_area` | the journal row for the count; the card itself for which ones | `scan.outsideArea`, `card.outsideArea` |
| Zone names are matched best-effort; ids are exact | — (a statement, not a figure) | under the zone field in the search builder, as the field's hint | `profiles.zoneBestEffort` |
| The same zones are exact on one portal and approximate on the other | `BuiltSearch.zone_warnings` (Immobiliare) and `.idealista_zone_page` (Idealista) | the search review, one label per portal, side by side | `profiles.zoneCarry` |
| …and when they disagree, one of them is the one to trust | the same two fields | a line under the pair, naming the portal whose half is faithful | `profiles.zonePreferred` |
| Zones a pasted URL carried only as portal ids have no name to show | `SearchBuilderParamsOut.zone_ids`, its length | under the zone field, the moment the ids are in it | `profiles.zoneIdsUnnamed` |
| Rebuilding a multi-zone search from names keeps only the first | `SearchBuilderParams.zones`, its length — mirroring `search_validator.zone_coverage_warnings` | under the zone field, as soon as a second name is in the list | `profiles.zoneFirstNameOnly` |
| A drawn area or a radius cannot be expressed as city + zone | — | the builder, next to the URL paste that *can* carry it | `profiles.areaNeedsUrl` |
| A parameter reaches a portal widened rather than as asked | `BuiltSearch.zone_warnings` and `.idealista_zone_page`, per row | the search review, in that portal's cell, with what the approximation is | `profiles.reviewApprox` |
| A parameter reaches a portal not at all | `BuiltSearch.idealista_unsupported`, per row | the search review, in that portal's cell, with why it was dropped | `profiles.reviewDropped` |
| Handing filters to a saved search drops or widens some of them | `handoff.ts`, per criterion | the review list, one tagged item per criterion | `handoff.<criterion>` |
| `idealista_api_max_pages` is worth ~50 listings a request | the field's current value × `SettingsOut.idealista_api_page_size` (published from `idealista_api.MAX_ITEMS_PER_PAGE`) | under the field, in Settings and in the setup wizard | `settings.idealistaReach` |
| Public Nominatim allows one request a second | `GeocodeProgressOut.pace_seconds` (from `geocoder.PACE_SECONDS`) | on the geocoding progress line, as the reason it is slow | `geocode.pace` |
| A zone centroid is not an address | `Property.coordinate_source == "zone"` | the map: the pin's own popup, and the count in the legend | `map.zoneCentroid` |
| The public OSRM demo routes "on foot" as a car | `CommuteOut.car_routing` (true only for a mode still answered by the public host — `osrm_url_foot` / `osrm_url_bike` take a mode off it) | on the commute badge, beside the number that would otherwise be believed | `commute.carRouting` |
| The OMI band is not the listing median | — ([invariant 22](invariants.md)) | under the two figures, whenever both are on screen | `benchmark.omiIsNotTheMedian` |
| A listing is only called gone after so many days unseen | `ScraperStatusOut.gone_after_days` (the `gone_after_days` setting, 7 by default, floored at 1 by `scanner.gone_after_days`) | the card's "no longer available" marker | `card.goneAfter` |
| Notifications are capped per scan and per category | `SettingsOut.max_notifications_per_scan` (15 by default, floored at 1) | the overflow message the scan itself sends ("… and *N* more"), so the count that was suppressed is named | — (a message, not a screen) |

## What it would take to lift each one

The inventory says where each limit bites. This says what removing it would cost —
because "we know about it" and "we could fix it" are different claims, and the table
above only makes the first one. Every row above has a row here, keyed by the same
`data-limit`, so a limit and the way out of it stay one fact in one file.

A verdict is one of exactly three, and it is a claim about *this* repository:

- **liftable now** — it can be done here, with what the repository already has, and
  nothing the owner must obtain, run or pay for.
- **liftable, but it costs something** — it works, and it needs a key, a server or a
  machine kept running. The cost is named, and so is what it buys.
- **open** — nobody has a good answer, the people who run the service included. What
  makes it hard is written down, so a later attempt starts further along.

A *done* after the verdict means the method in the middle column is no longer a plan: it
is in the product, and the column says which setting turns it on. The row does not
disappear when that happens, because the limit does not — a dial left at its default is
still the limit, which is why the inventory keeps stating it. Removing the row is for a
limit that can no longer occur at all.

A verdict is a claim and a claim needs a reason, so each method is concrete enough to
act on: naming a technology is not a method. Where the method is not already visible in
this repository the row links to where it came from — an entry that says "self-hosting
removes this" without a link is a rumour, and a year from now nobody can check it. The
links below were **checked on 2026-09-09**; third-party terms change without anyone here
being told, which is exactly why the source is recorded rather than the conclusion alone.

| The limit | What it would take | Verdict |
|---|---|---|
| `scan.pageCap` | Nothing new: `split_large_searches` is on by default and already re-runs an over-cap search as several non-overlapping narrower ones (at most `search_builder.MAX_SEARCH_PARTS`), merging the results. Raising `max_pages_per_search` covers whatever the split does not, at one more request per page. | **liftable now** — the mechanism is shipped; the cap is a dial the owner can already turn. |
| A quick scan is a partial reading | `stop_when_nothing_new` is the dial, on by default, and turning it off makes every scan read to the cap. The shortcut is also bounded rather than trusted: a search's first scan is always a full sweep, and so is one every `full_sweep_every_days` (7 by default) counted from the last sweep that got through, which is what keeps the pages a quick scan skips from going unread indefinitely. | **liftable now** — *done*, and both directions are already dials. What is deliberately not lifted is the label: a quick scan is worth having, and it is worth saying that it was one. |
| `scan.portalBlocked` | For Idealista the block is already bypassed: `scrapers/idealista_api.py` asks the portal for its own data over OAuth2 with no DataDome in the way, and needs a key issued by hand ([no self-service signup](https://developers.idealista.com/access-request)). For Immobiliare there is no equivalent — the portal publishes no developer API, and the third-party "Immobiliare APIs" on offer are resellers of the same scraping, carrying the same 403. | **open** — the Idealista half costs a key; the Immobiliare half has no answer, because refusing a scraper is the portal working as intended. |
| `scan.outsideArea`, `card.outsideArea` | The polygon test already exists (`geo_filter.point_in_any`) and already flags the strays. Dropping them instead of merely marking them needs a coordinate for *every* listing, and the ones still unplaced are exactly those the paced geocoder has not reached — so this row is the geocoder's cost, spent inside a scan rather than after it. | **liftable, but it costs something** — the same self-hosted geocoder as `geocode.pace`, which buys a scan that can place every listing before it reports a count. |
| `profiles.zoneBestEffort` | Call the geography autocomplete the scraper already calls — `scrapers/immobiliare.API_GEO`, via `_resolve_geography` — from the search builder, and keep the ids it returns. The endpoint, the parser and the id plumbing all exist; only the builder does not reach for them. | **liftable now** — everything needed is in this repository. It does make saving a search perform a network call, which the builder currently never does. |
| `profiles.zoneCarry` | Idealista's half needs the portal's internal `locationId`, which `idealista_api.UNMAPPED_FILTERS` records as not derivable offline. Its location lookup sits behind the same hand-issued key as the rest of the API, and so does its documentation. | **liftable, but it costs something** — an Idealista key, whose first purchase is the ability to check whether the location endpoint has the shape this needs. That cannot be verified from outside the gate. |
| `profiles.zonePreferred` | Nothing of its own: this line exists only to name the trustworthy side while the two sides differ. It disappears when `profiles.zoneCarry` does, by the same method and at the same price. | **liftable, but it costs something** — the same Idealista key, and not separately purchasable. |
| `profiles.zoneIdsUnnamed` | The autocomplete resolves text to ids, not ids back to text, and nothing published maps an Immobiliare zone id to its name. The reachable half is to remember the pairing whenever a name *is* resolved, which only ever helps an id this installation has met before. | **open** — an id the app has never resolved has no name to show, and no source outside the portal supplies one. |
| `profiles.zoneFirstNameOnly` | The same call as `profiles.zoneBestEffort`: with names resolved to ids, all of them travel as repeated query params instead of only the first. | **liftable now** — one method fixes both rows. |
| `profiles.areaNeedsUrl` | The builder already *parses* `vrt` and `centro`+`raggio` out of a pasted URL, and the dashboard already draws polygons in the very format `geo_filter.parse_polygon` reads. Emitting those params from the drawn shape closes the loop without a new format on either end. | **liftable now** for Immobiliare, entirely in this repository. Idealista's URL grammar has no equivalent, so a drawn search stays one-portal until it gains one. |
| `profiles.reviewApprox` | Each widening is a specific filter token, and this project's standing rule is that portal tokens are measured against real result totals rather than inferred (`services/search_builder.py`). Measuring an Idealista token means running the search against Idealista. | **liftable, but it costs something** — a key, which buys the measurement; guessing the token is the failure mode the rule exists to prevent. |
| `profiles.reviewDropped` | Same method, and `idealista_api.py` names the concrete casualty: this codebase counts Italian *locali* while the API filters `bedrooms`, and "locali − 1" is the plausible guess that silently returns the wrong set. Establishing the real correspondence needs measured totals. | **liftable, but it costs something** — the same key. Until then declining is visible and guessing is not, which is why the parameter is dropped rather than approximated. |
| `handoff.<criterion>` | A deal score, a tag, a status: the criteria that drop are the ones no portal has a concept for, as `handoff.ts` says at the top. A filter cannot be handed to a search that has no field to receive it, so the three-way answer it gives — exact, widened, or dropped and why — is the whole of what is available. | **open** — not for want of effort: the two sets of criteria are genuinely not the same set, and any mapping would be an invention presented as a filter. |
| `settings.idealistaReach` | Raise `idealista_api_max_pages`; each extra page is 50 more listings and one more request. The ceiling it spends against is agreed privately when the key is issued and [published nowhere](https://developers.idealista.com/access-request), which is why the default is 1 rather than reusing `max_pages_per_search`. | **liftable, but it costs something** — quota on a hand-issued key. What it buys is exactly 50 listings per extra page, against a budget that cannot be known until the key exists. |
| `geocode.pace` | Run Nominatim yourself and point `nominatim_url` at it — the setting is already there for this. [The policy](https://operations.osmfoundation.org/policies/nominatim/) is the reason to: the public instance's absolute maximum is 1 request/second, but "scripts that are run at regular intervals are restricted to 4 requests per minute", and a scheduled scan is precisely that. [Nominatim's own install docs](https://nominatim.org/release-docs/latest/admin/Installation/) put the floor at 2 GB RAM; the country extract this needs is [Geofabrik's Italy PBF](https://download.geofabrik.de/europe/italy.html), 2.07 GB before import. | **liftable, but it costs something** — a machine kept running. It buys unmetered geocoding, which is what makes `scan.outsideArea` and a fully-placed map affordable. |
| `map.zoneCentroid` | Nothing here is missing: where a portal publishes coordinates or a street address the app already places the pin, and the centroid is the fallback for listings where it publishes neither. Withholding the exact address is the portals' own product decision, not a gap on this side. | **open** — there is no source of exact coordinates for a listing whose address nobody publishes. |
| `commute.carRouting` | Point `osrm_url` at `https://routing.openstreetmap.de/routed-foot`, the FOSSGIS-sponsored OSRM host that serves a real pedestrian graph ([demo server wiki](https://github.com/Project-OSRM/osrm-backend/wiki/Demo-server), [terms](https://routing.openstreetmap.de/about.html): 1 request/second, non-commercial, attribution — the pace `PACE_SECONDS` already keeps). Verified on a Milan pair: that host answers 2626 m symmetric on an unnamed footway, where `router.project-osrm.org` answers 3279.6/3465.6 m asymmetric snapped to Via Guglielmo Marconi — a one-way road, on the driving graph. Because that service splits profiles across three path prefixes (`routed-car`, `routed-bike`, `routed-foot`) and `osrm_url` is a single URL, a mixed-mode setup needed the base URL to become per-mode: `osrm_url_foot` and `osrm_url_bike` are that, and a mode with one set is measured on its own graph and drops the badge. Blank is the default and changes nothing. | **liftable now** — *done*, and it cost no key, no account, no machine. The badge stays for whichever mode is still on the driving graph, which on a default install is both of them. A [self-hosted OSRM built with `foot.lua`](https://github.com/Project-OSRM/osrm-backend#quick-start) is the alternative, and that one costs a machine. |
| `benchmark.omiIsNotTheMedian` | No method, and none is wanted. OMI publishes a band for a zone and property type derived from recorded transactions; the median is what is being asked today for the listings on screen. The two measure different things correctly, and the only way to make them agree is to throw one away. | **open** — what makes it hard is that it is not a defect. [Invariant 22](invariants.md) exists to stop a later reader "fixing" it by conflating the two. |
| `card.goneAfter` | `gone_after_days` is the dial, offered in Settings from 2 to 30 days and defaulting to the 7 the constant always held. The comment at the constant says why it is days at all and not "absent from the latest scan": a 403 lasting a few hours must not make half the database vanish, so 0 is refused rather than obeyed. | **liftable now** — *done*: the dial was the deliverable, not a smaller default. Choosing a shorter one trades directly against the block tolerance it was chosen for, which is why the marker still says how many days of silence it took. |
| Notifications capped per scan | `max_notifications_per_scan` is the dial, 15 by default. Nothing was lost silently before it either — the overflow message already names the count it suppressed — so this is a preference about notification volume rather than a gap in what the app knows. | **liftable now** — *done*; raising it costs nothing but messages, 0 is refused, since suppressing every individual message and leaving only "… and *N* more" reads as a broken integration. |

## Deliberately not on this list

Things that look like limits and are not, so nobody adds a sentence for them:

- **A filtered-out listing.** `filtered_reason` already says which rule removed it, on the
  listing, and that is a decision the user configured rather than something the app
  cannot do.
- **A portal that answered nothing.** "Zero results" is an answer. It reads as a limit
  only when the portal *refused*, which is the `scan.portalBlocked` row above.
- **A stale OMI semester.** Already a chip on the figure it qualifies, with the semester
  printed beside it — a limit of the supply, not of the software.
- **The synthetic demo corpus.** `demo_data.py` is a test fixture: the browser suite seeds
  it into a throwaway database and nobody running the app ever meets it. It stays
  synthetic on purpose — real listings are the portals' content, and a fixture shipping
  them would put someone else's data in this repository — but a fixture has no surface to
  state a limit on, and inventing one would announce a limit the user does not have.

## Adding one

A new limit is four things, in this order: the API field that owns the number, the
`Limit` (or `LimitInline`) on the surface where the user meets it, a row in the inventory,
and a row in *What it would take* carrying a method, a verdict and — unless the method is
already visible in this repository — a link. Skip the first and the copy will drift from
the setting; skip the second and the limit becomes a bug report; skip the third and the
next sweep will not know to check it; skip the fourth and the limit reads as permanent
when it may only be unattended.

Two neighbouring documents are usually not affected: reach for
[`invariants.md`](invariants.md) only if the limit is a rule that must not break, and for
[`features.md`](features.md) only if it changes what the feature is understood to do.
