# What This Software Cannot Do

Every limit this app has, and the screen that states it.

The rule the list exists to enforce: **a limit is stated where it bites, not on a page
nobody opens.** A page cap the user meets as "why are there only 250 listings" is a bug;
the same cap printed beside the count is a fact. So this file is not the place the
limits are announced — it is the checklist that keeps the announcements honest. Each row
names the limit, where the number comes from, and the surface that says it out loud.

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
| Listings come back from outside the area asked for | `ScanJournalEntryOut.outside_area` | the journal row for the count; the card itself for which ones | `scan.outsideArea`, `card.outsideArea` |
| Zone names are matched best-effort; ids are exact | — (a statement, not a figure) | under the zone field in the search builder, as the field's hint | `profiles.zoneBestEffort` |
| The same zones are exact on one portal and approximate on the other | `BuiltSearch.zone_warnings` (Immobiliare) and `.idealista_zone_page` (Idealista) | the search review, one label per portal, side by side | `profiles.zoneCarry` |
| …and when they disagree, one of them is the one to trust | the same two fields | a line under the pair, naming the portal whose half is faithful | `profiles.zonePreferred` |
| Zones a pasted URL carried only as portal ids have no name to show | `SearchBuilderParamsOut.zone_ids`, its length | under the zone field, the moment the ids are in it | `profiles.zoneIdsUnnamed` |
| Rebuilding a multi-zone search from names keeps only the first | `SearchBuilderParams.zones`, its length — mirroring `search_validator.zone_coverage_warnings` | under the zone field, as soon as a second name is in the list | `profiles.zoneFirstNameOnly` |
| A drawn area or a radius cannot be expressed as city + zone | — | the builder, next to the URL paste that *can* carry it | `profiles.areaNeedsUrl` |
| Handing filters to a saved search drops or widens some of them | `handoff.ts`, per criterion | the review list, one tagged item per criterion | `handoff.<criterion>` |
| `idealista_api_max_pages` is worth ~50 listings a request | the field's current value × `SettingsOut.idealista_api_page_size` (published from `idealista_api.MAX_ITEMS_PER_PAGE`) | under the field, in Settings and in the setup wizard | `settings.idealistaReach` |
| Public Nominatim allows one request a second | `GeocodeProgressOut.pace_seconds` (from `geocoder.PACE_SECONDS`) | on the geocoding progress line, as the reason it is slow | `geocode.pace` |
| A zone centroid is not an address | `Property.coordinate_source == "zone"` | the map: the pin's own popup, and the count in the legend | `map.zoneCentroid` |
| The public OSRM demo routes "on foot" as a car | `CommuteOut.car_routing` (true only against the public host) | on the commute badge, beside the number that would otherwise be believed | `commute.carRouting` |
| The OMI band is not the listing median | — ([invariant 22](invariants.md)) | under the two figures, whenever both are on screen | `benchmark.omiIsNotTheMedian` |
| A listing is only called gone after 7 days unseen | `ScraperStatusOut.gone_after_days` (from `scanner.GONE_AFTER_DAYS`) | the card's "no longer available" marker | `card.goneAfter` |
| Notifications are capped at 15 per scan | `scanner.MAX_NOTIFICATIONS_PER_SCAN` | the overflow message the scan itself sends ("… and *N* more"), so the count that was suppressed is named | — (a message, not a screen) |
| The demo corpus is synthetic | `demo_data.py` | **not stated yet** — owned by task F.2, which introduces the mode and the banner | — |

## Deliberately not on this list

Things that look like limits and are not, so nobody adds a sentence for them:

- **A filtered-out listing.** `filtered_reason` already says which rule removed it, on the
  listing, and that is a decision the user configured rather than something the app
  cannot do.
- **A portal that answered nothing.** "Zero results" is an answer. It reads as a limit
  only when the portal *refused*, which is the `scan.portalBlocked` row above.
- **A stale OMI semester.** Already a chip on the figure it qualifies, with the semester
  printed beside it — a limit of the supply, not of the software.

## Adding one

A new limit is three things, in this order: the API field that owns the number, the
`Limit` (or `LimitInline`) on the surface where the user meets it, and a row here. Skip
the first and the copy will drift from the setting; skip the second and the limit becomes
a bug report; skip the third and the next sweep will not know to check it.

Two neighbouring documents are usually not affected: reach for
[`invariants.md`](invariants.md) only if the limit is a rule that must not break, and for
[`features.md`](features.md) only if it changes what the feature is understood to do.
