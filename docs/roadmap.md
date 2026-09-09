# Roadmap

What is known and not done, and where this product goes after 2.0.0.

Every entry here was found by somebody who had the evidence in front of them and decided,
deliberately, not to act — so each one carries the evidence and the reason, not just the
intention. An item with neither is a wish, and belongs in an issue rather than in this file.

Two rules keep it honest:

- **A row states its blocker as plainly as its ambition.** A roadmap that lists only what
  would be nice is a wish list; the value is in what has to be solved first. The corollary
  is about order: the hard entries come first on this page, because a list that hides them
  behind the easy ones reads as progress and is not.
- **A row is removed when it is done or when it is withdrawn**, and a withdrawn row says
  why. Nothing accumulates here silently.

---

## 1. Every limit still standing

[`limits.md`](limits.md) is the inventory of everything this software cannot do, and its
second table — [*What it would take to lift each one*](limits.md#what-it-would-take-to-lift-each-one)
— says, per limit, the method and the price. **The standing goal is to lift all of them**,
and every row that survives is a roadmap item by definition. What follows carries each one
by its `data-limit` id with the method compressed to a line; the row in `limits.md` is the
copy that is maintained, and this page links to it rather than restating it.

The verdicts are the ones `limits.md` defines: **open** (nobody has a good answer),
**liftable but it costs something** (a key, a server, a machine kept running), and
**liftable now** (this repository already has what it needs).

### Open — no method exists yet

Five, and they are the honest part of this page. Two of them are not defects at all, which
is stated rather than hidden: for those, "lifting" would mean discarding a correct answer,
and the goal above does not apply.

| `data-limit` | Why nobody has a method |
|---|---|
| `scan.portalBlocked` | Idealista's half costs a key — its own API has no DataDome in front of it. Immobiliare publishes no developer API at all, and the third-party "Immobiliare APIs" resell the same scraping and carry the same 403. A portal refusing a scraper is the portal working as intended. |
| `profiles.zoneIdsUnnamed` | The geography autocomplete resolves text to ids, never ids back to text, and nothing published maps an Immobiliare zone id to a name. Caching the pairing when a name *is* resolved helps only ids this installation has already met. |
| `handoff.<criterion>` | A deal score, a tag, a status: the criteria that drop are the ones no portal has a concept for. Any mapping would be an invention presented as a filter, so exact/widened/dropped-and-why is the whole of what is available. |
| `map.zoneCentroid` | There is no source of exact coordinates for a listing whose address nobody publishes. Withholding it is the portals' product decision, not a gap here. **Not a defect.** |
| `benchmark.omiIsNotTheMedian` | OMI publishes a band derived from recorded transactions; the median is what is being asked today. The two measure different things correctly, and the only way to make them agree is to throw one away — which [invariant 22](invariants.md) exists to prevent. **Not a defect, and not wanted.** |

### Liftable, but it costs something

Seven. Four of them are the same purchase: **an Idealista API key**, issued by hand with
[no self-service signup](https://developers.idealista.com/access-request). That single key
is the highest-leverage item on this page, and it has a first cost that is not the money —
the key must exist before anyone can check whether the endpoints behind it have the shape
these rows need. Two more are one machine: a self-hosted Nominatim.

| `data-limit` | What lifting it needs | What it costs |
|---|---|---|
| `profiles.zoneCarry` | Idealista's internal `locationId`, which is not derivable offline; its location lookup sits behind the key, and so does its documentation. | An Idealista key, whose first purchase is the ability to check the endpoint at all. |
| `profiles.zonePreferred` | Nothing of its own — this line exists only to name the trustworthy side while the two sides differ, and disappears with `profiles.zoneCarry`. | The same key. Not separately purchasable. |
| `profiles.reviewApprox` | Each widening is a specific filter token, and this project measures portal tokens against real result totals rather than inferring them. Measuring an Idealista token means running the search against Idealista. | The same key, which buys the measurement. Guessing the token is the failure mode the rule exists to prevent. |
| `profiles.reviewDropped` | Same method. The concrete casualty is named: this codebase counts Italian *locali* where the API filters `bedrooms`, and "locali − 1" is the plausible guess that silently returns the wrong set. | The same key. Until then declining is visible and guessing is not. |
| `settings.idealistaReach` | Raise `idealista_api_max_pages`; each extra page is 50 more listings and one more request. | Quota on that key, against a ceiling agreed privately when it is issued and published nowhere. |
| `geocode.pace` | Run Nominatim yourself and point `nominatim_url` at it — the setting already exists for this. The public instance restricts scheduled scripts to 4 requests a minute, which is exactly what a scheduled scan is. | A machine kept running: 2 GB RAM floor, plus a 2.07 GB Italy extract to import. It buys unmetered geocoding. |
| `scan.outsideArea`, `card.outsideArea` | The polygon test already flags the strays; *dropping* them needs a coordinate for every listing, and the unplaced ones are precisely those the paced geocoder has not reached. | The same self-hosted geocoder — this row is `geocode.pace`'s cost, spent inside a scan rather than after it. |

### Liftable now — the work is here and nothing must be obtained

Eight. These are the ones with no excuse, which is why they are last: they are the cheapest
and therefore the least interesting thing on this page.

Four of the eight have since been lifted, and are marked **done** below rather than
deleted: each was lifted by *offering* something, so the limit still stands on a default
install and the inventory still states it. That is the shape a lift takes here — the app
must keep working with nothing added, so the deliverable is a setting the owner may leave
alone, never a new requirement.

The two zone rows are the ones deliberately left. Their method is a call to Immobiliare's
geography autocomplete, which means saving a search would put one more request on the
portal; the whole anti-blocking posture is built on making fewer of those, so lifting these
two waits for a method that does not spend requests, or for the judgement that the spend is
worth it. That is a decision, not an oversight.

| `data-limit` | What lifting it takes |
|---|---|
| `profiles.zoneBestEffort` | Call the geography autocomplete the scraper already calls, from the search builder, and keep the ids. Everything needed exists; only the builder does not reach for it. It does make saving a search perform a network call, which it never does today — and that request lands on a portal, which is the reason this one is still here. |
| `profiles.zoneFirstNameOnly` | The same call: with names resolved to ids, all of them travel as repeated query params instead of only the first. One method closes both rows, and the same request cost stops both. |
| `profiles.areaNeedsUrl` | The builder already parses `vrt` and `centro`+`raggio` out of a pasted URL, and the dashboard already draws polygons in the format the geo filter reads. Emitting those params from the drawn shape closes the loop. Immobiliare only — Idealista's URL grammar has no equivalent, so a drawn search stays one-portal. |
| `commute.carRouting` | **Done.** `osrm_url_foot` and `osrm_url_bike` sit beside `osrm_url`: a mode with one set is measured on that host's own graph and drops the "measured on the road network" badge, per mode. Blank is the default and routes exactly as before, so the limit still stands until someone fills one in. |
| `scan.pageCap` | Already mostly done: an over-cap search is re-run as several non-overlapping narrower ones and merged. Raising `max_pages_per_search` covers the remainder, at one more request per page. The cap is a dial the owner can already turn. |
| `card.goneAfter` | **Done.** `gone_after_days` is in Settings, 2 to 30 days, still 7 by default — the dial was the deliverable, not a smaller default, because shortening it trades directly against the block tolerance it was chosen for. A zero is refused rather than obeyed. |
| Notifications capped at 15 | **Done.** `max_notifications_per_scan` is in Settings, still 15 by default. Nothing was lost silently before either — the overflow message already named the count it suppressed — so this was always a preference about volume. |
| A quick scan is a partial reading | **Done**, in both directions and neither of them new: `stop_when_nothing_new` turns the shortcut off and every scan reads to the cap, and left on it is bounded anyway — a search's first scan is a full sweep, and so is one every `full_sweep_every_days`. What is deliberately not lifted is the label on the journal row: a quick scan is worth having, and worth saying it was one. |

---

## 2. After 2.0.0: the hosted, multi-account version

Recorded because it was asked for, and because knowing the blockers changes what is worth
building now. **This is a direction, not a commitment.**

Today the product is one person, one machine, one database, and its entire security model is
that the API answers only on loopback ([invariant 14](invariants.md)). "Available on the web,
with accounts" is not a feature added to that — it is a different product built on the same
engine. Four things stand between here and there, in descending order of how likely each is
to kill it.

**1. The scrapers would run from a datacenter IP, and that is the hard one.** The whole
anti-blocking ladder — `curl_cffi` TLS impersonation with rotating profiles, the Camoufox
browser, the harvested DataDome cookie ([`scan-returns-nothing.md`](scan-returns-nothing.md)) — is tuned for a
residential connection scanning a handful of searches a day. From AWS or Hetzner the same
requests meet a much harder wall, much sooner, and the cookie a real browser earned on a home
connection does not transfer. The realistic answer is to stop scraping directly and pay per
request through the Idealista official API or a scraping provider — which converts a free
local tool into a per-user variable cost, and makes pricing a product decision before it is
an engineering one. Every other item here is work; this one is a question that has to be
answered before the work is worth starting.

**2. Invariant 14's premise disappears.** "The bind address is the access control" cannot
survive a public host. That means real authentication — sessions, password reset, email
verification — and multi-tenancy: an owner column on every table, and every query in the
application filtered by it. That is not a feature, it is a change to the shape of every read
in the codebase, and the one place a mistake shows another person's shortlist.

**3. Legal posture changes with the money.** Collecting listings for yourself and operating a
service that collects them for paying customers are different things in front of a portal's
terms, and holding accounts brings GDPR obligations the local app has never had: a data
controller, a retention policy, deletion on request. Worth an actual opinion before the first
paying user, not after.

**4. Cost and operations.** Scans are long-running and bursty, so per-user scheduling, a job
queue, per-tenant rate limits and a database that is not SQLite-on-one-disk all arrive
together, along with backups and monitoring that are somebody's job rather than a folder.

**What 2.0.0 buys either way.** Nothing in it is wasted on that path and most of it is a
prerequisite: the URL and routing are what make a shareable link possible at all; the
generated API client is what lets a second frontend exist; the event stream is how a browser
learns about a scan it did not start; the design system and the information architecture are
the difference between a tool and something a stranger will pay for; and the browser suite is
the only way any of it stays true once more than one person depends on it.

---

## 3. Found by the backend review, not done

The review is [`audit.md`](audit.md) §2–§3 (correctness), §6 (security) and §7
(efficiency). It ran after the scan was rewritten and before the interface was built on it,
under a standing rule that it was a review and not a rewrite: anything that would change
behaviour a test asserts stops and becomes a row here.

### Idealista's own delay floor is overwritten by the scanner

`IdealistaScraper.__init__` raises whatever delay it is given to at least 8 seconds, with a
comment saying why ("DataDome is sensitive to request frequency"), and the availability
check applies the same idea properly — `max(request_delay_seconds, MIN_PROBE_DELAY[portal])`
in `services/availability_check.py`. The scan does not: `scanner._fetch_search` assigns
`scraper.delay_seconds = request_delay_seconds` *after* construction, so the floor is
silently discarded and Idealista is paged at the global 6-second default. `scanner`'s own
docstring for `_fetch_searches` states the floor as a fact, which makes this a place where
the code says one thing and does another.

**Why it was not fixed in the review.** Applying the floor changes what
`test_the_two_portals_are_read_at_once_and_neither_is_asked_faster` measures: Idealista
would then pace at 8 s against Immobiliare's test delay, the concurrency assertion
(`whole < serial * 0.75`) no longer holds arithmetically, and the suite grows by roughly
half a minute of real sleeping. That is a behaviour change with a test in front of it, which
is exactly the line the review was told not to cross.

**What doing it looks like.** A `min_delay_seconds` class attribute (0 on `BaseScraper`,
8 on `IdealistaScraper`), applied where the scanner sets the delay, plus a decision about
whether a configured `0` means "no pacing at all" — the offline sandbox relies on it, and
the availability check today does not honour it. The concurrency test then needs its two
delays chosen per host rather than globally.

### A scraped URL's scheme is checked where it is exported, and nowhere else

Both dossiers now refuse to link anything that is not `http(s)` (`exporter._safe_url`,
`audit.md` §6.1), and so does the one anchor the interface builds from a listing URL
(`services/api.ts` `safeHref`, applied in `routes/property/Provenance.tsx`). One consumer of
the same field is still deliberately left alone:

- **ingestion** — `scrapers/immobiliare.py` and `idealista.py` store whatever the portal's
  `href` or `seo.url` field held. Filtering there would protect every consumer at once, but
  the URL is also the identity two sightings of an ad are matched on (`listing_key`,
  `merge_scrapes`, `_already_seen`), so dropping or blanking one is a change to
  deduplication, not to rendering.

**What doing it looks like.** A scheme check at the point a listing is built, with a rejected
URL keeping the row out of the merge rather than blanking the field — which means deciding
what a listing with no usable URL even is, and that is a data-model question, not a
rendering one.

### `settings.json` is written with whatever permissions the platform defaults to

Nothing narrows the file's mode. On the single-user Windows install this is built for that
buys nothing; on the Docker path, where the file sits in a volume on a host that may have
other accounts, `0600` would be a one-line change with a POSIX-only test behind it. It is
written down rather than done because the review that found it had no failing test to point
at — the file is exactly as readable as the database beside it, and neither is a regression.

### `_mark_vanished_properties` walks every active property in Python

`services/scanner.py` loads every `active`/`filtered` property and compares `last_seen_at`
row by row, where a single `UPDATE … WHERE last_seen_at < ?` would do it. It is a candidate
and not a change, because §7's rule applies: it runs **once per clean full scan**, not per
request, and no measurement shows it costs anything at the sizes this app holds. It is
recorded so that whoever does measure it at 100 000 properties finds it already named.

### The dashboard ships as one chunk, and a fifth of it is for one route or one language

Measured 2026-09-09 with `scripts/measure_frontend.mjs` ([`audit.md`](audit.md) §7.2): 922 kB
of JavaScript in a single chunk, of which **leaflet is 145 kB (16 %)** and the **two locale
catalogues are 78 + 72 kB**. The map is one route out of nine, and the user reads one of the
two languages, so roughly a fifth of what loads before anything renders is for something this
visit will not do. The Lighthouse budget is 950 kB and the build is at 922.

**What doing it looks like.** A `React.lazy` around the map route and a dynamic `import()`
per locale, with a loading state each. Both change when a module is evaluated, and the
browser suite asserts against a rendered map and against Italian strings being there on first
paint — so this is a change with tests in front of it, which is the line a review does not
cross. Its own task, with the before and after from the same instrument.

### The grid is sent 45 % more than it reads

`GET /api/properties?limit=0` is 189 kB for the 80-property demo corpus, and 85 kB of that is
read by nothing on the page (`measure_backend.py --only payloads`). 66 kB is inside the
nested listings: the card reads their `portal` name and counts them — 895 bytes' worth — and
is sent every field of every listing, descriptions included. The rest is `deal_reasons`,
`found_by`, `price_history` and two timestamps.

**What doing it looks like.** A narrower response model for the list route, which is not free:
`routes/property/*` reads the full listing objects, and today they can come from the grid's
cache rather than from a second request. Either the property route stops sharing that cache,
or the grid's rows carry a summary and the detail route keeps the full shape — a decision
about the query cache, not about bytes. Nothing here is slow at the sizes this app holds,
which is why it is a candidate.

### Nothing measures the grid rendering in a browser

The grid is not virtualised: it renders every row the API returns. That is fine at the sizes
seen so far — the browser suite paints the whole 80-property corpus on every run, well inside
its navigation budget — but there is no way to answer "and at 500?" without booting the built
app against a corpus of a chosen size and measuring inside the page. `measure_frontend.mjs`
deliberately does not: it needs no browser and no backend, and keeping it that way is worth
more than the one number it cannot produce. Whoever needs that number builds the harness
first, and [`audit.md`](audit.md) §7.4 says so.

---

## 4. The dependency queue

An open pull request on a finished product is a question nobody answered, and there are
only two honest answers: it is taken, or it is closed with the reason written down.
"Still open" is neither.

**The queue was cleared on 2026-09-09.** Three were open — the actions group (7 updates),
the backend group (pydantic, ruff) and the frontend group (three dev packages). All three
were taken, each as its own commit so that one bad version can be reverted without losing
the other two, and the eight gates of [`audit.md` §0](audit.md) are green on the result.
Nothing was held: no version failed a gate, so no held row follows this paragraph. Two
earlier ones had already been closed by the bot itself as superseded by the three above.

Neither lock was taken as the bot wrote it, and the reason is per-ecosystem. The backend
one edits the compiled `requirements*.txt` without touching the `.in` file they come from,
and it recompiles without `--universal`: its diff dropped `colorama`, `tzdata`, `pefile`
and `macholib` along with the `sys_platform` markers that select them, which would have
shipped a Windows build with no `tzdata` for `tzlocal` to find. The frontend one writes a
`package-lock.json` without the six packages `@tailwindcss/oxide-wasm32-wasi` declares in
`bundleDependencies`, which is the shape `npm ci` refuses on the runner's npm. Both were
treated as a notice — take the versions, regenerate the lock by the commands
[dependencies.md](dependencies.md) documents.

**It does not stay cleared.** The bot opens more every week, and the release procedure is
where that is caught: check `gh pr list --state open` before tagging, so a release is never
cut over an unanswered question.

### One release-workflow action pin does not run until a tag

`release.yml` triggers on `push: tags: ["v*"]` and `workflow_dispatch` alone. Six of the
seven pins bumped on 2026-09-09 live only there — `softprops/action-gh-release` and the
five `docker/*` actions — so no push to a branch exercises them, and the first thing that
does is the release they are needed for. The five docker ones are covered by a
`workflow_dispatch` on a branch, which is safe because both the image push and the release
creation are gated on `github.ref_type == 'tag'`, and since 2026-09-09 that dispatch is part
of cutting a release rather than something available in principle —
[`manual-tests.md` § 9](manual-tests.md#9-the-pull-request-queue-at-the-tag) owns the step.
What is left standing is `action-gh-release`, which cannot be
exercised without cutting a real release. That one is recorded rather than fixed because the
cost of the failure is one red release run and one re-tag, and the alternative — a second
workflow that exists only to prove a single action's pin resolves — is more machinery than
the risk is worth.
