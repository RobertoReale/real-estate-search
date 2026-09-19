# Live Checks

[← Back to README](../README.md)

Every gate in this repository runs offline. That is deliberate — CI must never
touch a real estate portal — but it means no gate can answer the one question
that matters after a portal changes something overnight: *does a search still
work?* A scan can answer it, but only in one word per portal, and that word
hides which of five transports produced it. The Bicocca search that started this
tool reported `Blocked` for the lot: `curl_cffi` was genuinely refused, the saved
cookie was genuinely refused, and the paid provider was not refused at all — it
had timed out on our side, after being paid for the page.

`python -m app.livecheck` asks each transport separately and reports what each
one got, parsed by the **real** parsers. It is the instrument to reach for
instead of asking the owner to try the app.

```bash
cd backend && .venv\Scripts\python -m app.livecheck "https://www.immobiliare.it/vendita-case/milano/bicocca/"
```

## What it does

One run takes a search URL, works out the portal, builds every rung this machine
could climb, and tries them in order — free first, cheapest evidence first, money
last. Nothing in `app/scrapers/` is modified or re-implemented: the scrapers are
driven from outside, so what the report measures is what a scan would get.

Four ways to say what to check:

| | |
|---|---|
| `python -m app.livecheck URL [URL …]` | the searches you name |
| `--profiles` | every active saved search, read out of `case.db` **read-only** (`file:…?mode=ro`) |
| `--suite` | the tracked reference searches: one per shape a search can have |
| `--replay DIR` | re-parse an earlier run's saved pages; makes no network call at all |

### The rungs

| Rung | What it proves |
|---|---|
| `curl:<profile>` | one TLS impersonation from `tls_impersonations`, with **no cookie**, one rung per profile. Answers "is the disguise burnt, or is it this address?" |
| `curl+cookie` | the same transport carrying the saved `datadome` cookie. Answers "is the cookie still worth anything?" |
| `browser` | the headless browser path. Opt-in by name only (invariant 18); never in the default selection |
| `api:<provider>` | the paid scrape API. Needs `--paid`, and answers to the credit cap and the account floor |
| `official` | Idealista's own API, where a key is configured. Not a scrape at all, and the control for everything above it |

`--rungs` selects a subset by family (`curl`, `api`) or by exact name
(`curl:safari184`, `curl+cookie`, `browser`, `official`). A rung this machine
cannot climb — no cookie saved, no browser installed, no key configured — is
reported as skipped **with the reason**, never quietly left out of the table.

### The targets

* **Immobiliare** — the api-next JSON of page 1, and the HTML search page 1. The
  api-next parameters are built by the scraper's own `_api_params`, so the run
  first resolves the geography and reports that as its own row: invariant 7 says
  api-next is never called without it, and a geography that does not resolve is
  the reason the JSON target cannot be asked for at all.
* **Idealista** — the HTML page, plus `official p1` where the API is configured.

### What each attempt records

Rung, target, HTTP status, bytes, elapsed milliseconds, the block signals
separately from the verdict they feed (a refusing status, a DataDome marker in a
200, a CAPTCHA), and then the outcome **through the real parsers**: how many
listings came out, which strategy produced them, the total the portal declared,
and three sample title/price pairs. Paid attempts carry the credits the provider
itself reported. The table ends in one plain-words verdict per portal:

```
immobiliare: works via api:scrapfly (api-next p1, 30 credits); every free rung tried was refused (403); the rest were not tried
```

A column is left empty where the attempt did not produce it. An empty
`DECLARED` means the portal published no total, which is not a total of nothing
(invariant 26) — the report never fills a gap with a plausible zero.

Immobiliare's run opens with a `prepare` row: resolving the search's geography,
which invariant 7 requires before api-next can be called at all. It is a request
and is reported as one, but it is **not** a rung and can never be the verdict —
it answers a lookup endpoint anti-bot rarely guards, so a run where every real
transport was refused must still read `no rung worked`.

**Exit code:** 0 when every portal checked had at least one rung that parsed
listings or *proved* the search matches nothing; 1 otherwise.

## The reference suite

One search is not every search. The shapes a user can create take different code
paths — `_api_params`, `_absorb_query`, `search_builder` — and each has broken
separately before, so a green run on a city search says nothing about the four
shapes below it.

```bash
cd backend && .venv\Scripts\python -m app.livecheck --suite
```

`--suite` checks a tracked list instead of a URL. The searches are public and
generic; none of them comes from `case.db`, because a report is a file that gets
pasted into an issue.

| Entry | Portal | Shape |
|---|---|---|
| `imm-city` | Immobiliare | a city |
| `imm-zone-path` | Immobiliare | a zone in the path, with price and room filters |
| `imm-zone-ids` | Immobiliare | zone ids in the query (`idMZona[]`) |
| `imm-polygon` | Immobiliare | a drawn polygon (`search-list` + `vrt`) |
| `imm-radius` | Immobiliare | a radius around a point (`centro` + `raggio`) |
| `ide-city` | Idealista | a city |
| `ide-zone` | Idealista | a zone with filters |
| `*-form` | both | the same criteria built by `search_builder`, as the form builds them |

The `-form` entries are **derived**, never typed out: each one is what
`build_search_urls` produces from the criteria of the pasted entry it restates.
A builder that started producing something else would fail the offline test
rather than quietly measure a different search.

The list is checked before a single request leaves. Every entry must still parse
as the shape it claims, name the portal it claims, survive `search_validator`
with no zone warning, and be a different search from every other entry. If any of
that stops being true the run refuses with exit code 2 and says which entry —
a suite that has drifted would report a green table for shapes it never checked.

**It climbs one rung, not the matrix.** Each search stops at the first rung that
parses, so a suite run costs a handful of requests rather than one per rung per
search. `--all-rungs` asks every rung of every search; it is the full matrix, and
it is the thing the budget exists to make you ask for on purpose. The request cap
scales with the list — three requests per search of the busiest portal — so the
second half of the suite is not refused by a cap sized for one URL.

**Exit code:** 0 only when **every** reference search had a rung that answered.
The per-portal verdict cannot say this: one working city search would cover for
four broken shapes.

### `--portal`

```bash
cd backend && .venv\Scripts\python -m app.livecheck --suite --portal idealista
```

Narrows the suite to one portal's entries, and narrows the request cap with them.
It exists for the case where one portal is under repair and the other is known
good: checking both would spend the working portal's address on a question
already answered, and invariant 8's whole point is that those requests are not
free. The narrowing is recorded in `report.json` rather than inferred from which
rows are present — "the other portal was not asked" and "the other portal
answered nothing" are different findings, and `--compare-form` leaves the
unasked portal's review out for the same reason. It only means anything beside
`--suite`, and says so rather than falling through to "nothing to check".

### `--compare-form`

```bash
cd backend && .venv\Scripts\python -m app.livecheck --compare-form
```

Implies `--suite`, and prints a second table: the pasted search's total and the
form-built total side by side, with `search_validator`'s review of what the
restatement approximated or dropped. It is the whole of the form-against-URL
check [`manual-tests.md`](manual-tests.md#what-a-tool-decides-now) used to ask a
person for — the gap between two totals is only a bug when the review did not
predict it, and the screen that has to show the review is driven by the browser
suite's control inventory.

The review is free; it is computed offline whether or not the run had a total to
put beside it. So a shape the form cannot express says so in words —
*the builder has no grammar for a search drawn on the map*, and `drawn_area
dropped` — instead of showing an empty cell that reads as "not checked".

Idealista's zones are the case the review has to be careful with, because the
form has **two** routes to one of them and they return different totals. Pressing
Generate in the dashboard spends one request confirming the zone page exists and
then saves that page; the suite spends no request, so its form entry is the
`/cerca/<filters>/<Zone>_<City>/` free-text fallback, which is wider. Where the
pasted URL *is* the zone page, its own answered row is the proof the probe would
succeed, so the review states the URL Generate would save and adds *"Generate
reaches the zone page and produces this very URL; the form total beside it is the
wider /cerca/ fallback"*. Without that sentence the row read as a gap between two
searches, when it is a gap between a live path of the product and a path the user
never gets — and an unpredicted gap is what item 2 calls a failure.

## The budgets are the rules

This tool leaves from the residential connection the owner's real scans leave
from, and a retry loop on it is what gets that address blocked for a day
(invariant 8). The budget is not advice — it refuses.

| | Default | Raise it with |
|---|---|---|
| requests per portal, per run | 12 | `--max-requests` |
| seconds between requests to one portal | `request_delay_seconds` from settings, plus jitter | `--delay` |
| consecutive blocked attempts before the portal is dropped | 3 | — |
| credits one run may spend | 25 (one page) | `--max-credits` |
| account balance below which the paid rung is refused | 500 | `--credit-floor` |

The paid rung is off unless `--paid` is passed, and `--paid` is not enough on its
own: the run asks the provider what the account has left before spending
anything, and refuses if the answer is below the floor or if there is no answer
at all. `--credit-floor 0` is the documented way past that, and it is meant to be
typed on purpose.

Scrapfly bills per page and reports the price of each call back in the response;
see [its billing documentation](https://scrapfly.io/docs/scrape-api/billing). The
price is **not** fixed — the same Bicocca search cost 25 credits on 2026-09-10 and
30 on 2026-09-11, because the anti-bot surcharge depends on what the portal put
in the way that day. The run therefore checks the cap against the estimate before
a call and charges what the receipt says afterwards: one page can overshoot
`--max-credits` by the difference, and the call after it is refused. Budget two
pages (`--max-credits 60`) when you want both of Immobiliare's targets paid for.

When a portal stops answering, the answer is **not** another run. Every body is
saved, so `--replay` re-runs the parsers over the pages already fetched, offline
and for free, as many times as the work needs.

## What it writes, and what it never writes

Each run creates `backend/live-checks/<timestamp>/` holding `report.json` and the
raw body of every attempt. The directory is git-ignored: a captured page is the
portal's, not ours.

The provider key travels in the query string of every paid request, so **every
URL is redacted** before it reaches the table, the JSON or a log line, and
**cookies are never recorded** — not the value, not a preview of it. Redaction
runs twice, once where an attempt is built and again at the write, because the
boundary that matters is `report.json`.

The tool opens nothing for writing under the data directory, binds no port, and
touches `case.db` read-only and only to read saved search URLs. It cannot
interfere with a running app.

## Measurements — 2026-09-12

The baseline every later investigation starts from, taken from the owner's
residential connection in the small hours of 2026-09-12. Four runs, all of them
kept under the per-portal cap in any fifteen-minute window: `20260912-032029`
(the free matrix), `20260912-032453` and `20260912-032527` (two targeted
follow-ups), `20260912-032600` (the paid rung), `20260912-034103` (the suite
through the rung that works, taken after the window had drained) and
`20260912-043617` (the suite again, once the app's own call to the provider had
been repaired). Ninety credits spent in total, on two entries; the account was
above the 500 floor throughout.

**Every reference search works today — through the saved cookie.** Run
`20260912-034103`, `--suite --rungs curl+cookie`, nine of nine:

| Search | Portal | Shape | Target | HTTP | Ads | Declared |
|---|---|---|---|---|---|---|
| `imm-city` | Immobiliare | city | api-next p1 | 200 | 25 | 18,172 |
| `imm-zone-path` | Immobiliare | zone in the path | api-next p1 | 200 | 25 | 258 |
| `imm-zone-ids` | Immobiliare | zone ids in the query | api-next p1 | 200 | 25 | 981 |
| `imm-polygon` | Immobiliare | drawn polygon | api-next p1 | 200 | 25 | 1,184 |
| `imm-radius` | Immobiliare | radius around a point | api-next p1 | 200 | 25 | 3,378 |
| `ide-city` | Idealista | city | html p1 | 200 | 30 | 14,751 |
| `ide-zone` | Idealista | zone with filters | html p1 | 200 | 30 | 65 |
| `imm-zone-path-form` | Immobiliare | form | api-next p1 | 200 | 25 | 258 |
| `ide-zone-form` | Idealista | form | html p1 | 200 | 30 | — |

`imm-zone-path-form` declared the same 258 as the pasted `imm-zone-path` it
restates: the builder and the typed URL reached the same search. `ide-zone-form`
parsed thirty listings and published no total, which is a blank and not a zero
(invariant 26).

**Without the cookie, the two portals behave differently.** Run
`20260912-032029`, `--suite --all-rungs`, plus the follow-up `20260912-032527`
that reached the profiles the run never got to:

| Rung | Immobiliare | Idealista |
|---|---|---|
| `curl:safari184` | 403 | 200, 30 ads |
| `curl:chrome131_android` | 403 | **403** |
| `curl:safari180` | 403 | 200, 30 ads |
| `curl:safari18_4_ios` | not attempted — the name is rejected before any request | same |
| `curl:firefox147` | 403 | 200, 30 ads |
| `curl:safari260` | not reached (breaker) | 200, 30 ads |
| `curl+cookie` | 200, 25 ads | 200, 30 ads |

Both refusals are DataDome: the body is the `geo.captcha-delivery.com`
interstitial (`rt:'i'`), served for both portals. On Immobiliare's **api-next**
target that interstitial arrives as **JSON** — a `{"url":"https://geo.captcha-delivery.com/interstitial/?…"}`
object rather than the HTML block page — so anything that looks for the block
page's markup alone will read a refusal as a malformed answer.

**The paid rung works, slowly.** Run `20260912-032600`, `--rungs api --paid
--max-credits 100`, on `imm-city`: api-next p1 answered 200 with 25 ads and the
same 18,172 total, and html p1 answered 200 with 25 ads. Thirty credits each,
sixty for the pair. What matters is the clock: **22,593 ms** and **30,549 ms**
end to end. The provider is not answering in three seconds when it has an
anti-bot challenge to solve, and a client timeout of thirty seconds sits on top
of that distribution rather than clear of it.

**And the app's own call to it received nothing.** The same page the harness got
in three seconds, asked for by `BaseScraper._fetch_via_scrape_api`, timed out at
thirty seconds with zero bytes — after the provider had charged for solving it.
The cause was that the call went out on the portal's own session: a DataDome
cookie pinned to `.immobiliare.it`, `Sec-Fetch-*` and `Referer` headers
describing a navigation inside the portal, the proxy pool, and that thirty-second
timeout, all aimed at an endpoint that is none of those things. The provider now
gets a plain session of its own and the read timeout
[its documentation asks for](https://scrapfly.io/docs/scrape-api/getting-started),
155 s, which is five times the tail measured above rather than inside it.

Re-measured after the repair — run `20260912-043617`, `--suite --paid
--max-credits 75`, thirty credits spent:

| Search | Rung | Target | HTTP | Bytes | ms | Ads | Declared |
|---|---|---|---|---|---|---|---|
| `imm-city` | `api:scrapfly` | api-next p1 | 200 | 248,204 | 21,859 | 25 | 18,173 |

Twenty-five parsed entries on page 1 against a declared 18,173, which is the
portal's own arithmetic for a page of twenty-five. The three Idealista searches
in the same run answered free on `curl:safari184`, so four of nine reference
searches came back and the other five never reached a rung — see below.

**And a real scan finishes.** A copy of the Bicocca search run through
`run_scan` in a throwaway data directory, page limit 1: journal row `ok`, 25
listings, strategy `api-next`, declared total 258, transport `local
(curl_cffi)`. The saved cookie answered, so no escalation happened and the run
cost nothing — which is the point of the ladder, and the reason the paid rung
above had to be measured separately.

**The residential breaker still drops a search before its paid rung.** The five
Immobiliare entries that did not answer in `20260912-043617` were "dropped after
3 blocked attempts in a row": the blocked-streak limit counts refusals of *this*
connection and skips the whole search, including the provider attempt, whose exit
is not this connection at all. Nothing in the run was wrong — the cap of 75
credits could not have paid for five entries at 30 each anyway — but the report
reads as five untried searches where one of them is a rung that would have
worked. [`roadmap.md`](roadmap.md) carries it as a known limit.

### What this rules in, and what it rules out

* **Ruled out: this address is blocked.** It is not. Every shape on both portals
  answered from it, and Idealista answered cookieless on four profiles.
* **Ruled in: cookieless impersonation is refused by Immobiliare**, uniformly —
  four different profiles, both targets, always the same DataDome interstitial.
  The saved cookie is the entire difference between a refusal and 25 listings.
* **Ruled in: `chrome131_android` is burnt on Idealista**, and the profile is the
  cause rather than the address: in the same run, in the same minute, from the
  same connection, it drew a 403 on all three Idealista searches while four other
  profiles drew 200s.
* **Ruled out: `safari18_4_ios` is a working profile.** curl_cffi 0.16.2 rejects
  the name with `ImpersonateError` before opening a connection, so it has never
  been one of six profiles here — it is five and a gap. The compact spelling
  `safari184_ios` is accepted by the same build; upstream
  [documents both spellings as supported](https://curl-cffi.readthedocs.io/en/latest/impersonate/targets.html),
  which this build does not honour.
* **Ruled out: the paid provider was silently failing.** It returns a complete,
  parseable page. What it does not do is return it quickly — and until
  2026-09-12 the app hung up on it before it could.

### The trap in reading `--all-rungs`

`--suite --all-rungs` reported `immobiliare: no rung worked` in run
`20260912-032029`, and that verdict was an artefact. The rungs are ordered
cheapest-evidence-first, so all six cookieless profiles are tried before
`curl+cookie`; the third consecutive 403 tripped the blocked-streak limit and
dropped the portal for the rest of the run — before the one rung that works was
ever asked, and before four of the five Immobiliare shapes were reached at all.
Twenty-five minutes later the same searches answered on the first attempt.

So an Immobiliare verdict from `--all-rungs` says *the free cookieless rungs were
refused*, never *the portal is dead*. The rows below the streak limit are
**untried**, and the report says so in the note column — read that column before
concluding anything from an empty one. The cheap confirmation is one targeted
run: `--rungs curl+cookie` against a single URL costs two requests.

## Measurements — 2026-09-12, why every free local rung is refused

The baseline above ends on a fact without an explanation: from this connection
Immobiliare refuses every cookieless local rung and answers the saved cookie.
Five hypotheses, one harness variation each, seven runs under
`backend/live-checks/`, sixteen requests, no credit spent. Times are local
(UTC+2) and the run directory name is the timestamp.

### 1. Stale fingerprints — ruled out

| Run | Rung | api-next p1 | html p1 |
|---|---|---|---|
| `20260912-142304` | `curl:chrome150` | 403, 674 B | 403, 777 B |
| `20260912-142325` | `curl:safari2601` | 403, 674 B | 403, 777 B |
| `20260912-142348` | `curl:safari260` | 403, 669 B | 403, 774 B |

`chrome150` and `safari2601` are the newest Chrome and the newest Safari the
installed `curl_cffi` 0.16.2 carries, and neither had ever been measured here;
`safari260` is configured but had never been reached past the blocked-streak
limit. The first two ran from a throwaway data directory (`APP_DATA_DIR`) whose
`settings.json` carried nothing but those two names, so no product setting was
touched to measure them. All three draw the same DataDome interstitial as the
four profiles measured this morning, within a handful of bytes of the same body.
Seven of this build's fifty-four targets have now been measured against this
portal, and there is one verdict between them.

Upstream is one release ahead:
[0.16.3](https://github.com/lexiforest/curl_cffi/releases) (2026-09-02) adds the
TLS `trust_anchors` extension for Chrome 152 — a detail of a family already
refused here — and since 0.16.0 the project points at the separate
`impersonate.pro` service for fingerprints fresher than the shipped targets. The
issue tracker carries no report of a target that gets past DataDome; what it
does carry is [#247](https://github.com/lexiforest/curl_cffi/issues/247), Chrome
profiles newer than 116 drawing challenges where Safari and Firefox do not,
which runs the opposite way from "newer is better".

**Verdict: the profile name is not the variable, and a `curl_cffi` upgrade is
not the free path.** [Invariant 8](invariants.md) is why this is a table and not
an opinion.

### 2. The missing warm-up — ruled out as the cause

Run `20260912-141559`, the profile that had just been refused, against the
homepage instead of a search:

| Rung | Target | HTTP | Bytes | ms |
|---|---|---|---|---|
| `curl:safari184` | `https://www.immobiliare.it/` | **200** | 485,281 | 227 |

That is the whole run: the geography lookup resolves nothing for a URL that is
not a search, so `prepare` is recorded as blocked and the api-next target is
never built. What is left is the point — **the cookieless handshake that is 403
on `/vendita-case/milano/` is 200 on `/`**, seventy seconds apart. The address
opens connections and the portal serves pages; what is defended is the search
endpoint.

Could a session warmed up on the homepage then carry a usable token into the
search? Two things say no. The weak form is already measured: inside one rung
both targets share one session, so in run `20260912-141448` the `Set-Cookie`
that came back with the first interstitial was in the jar for the second
request, and the second request was refused identically. The strong form cannot
work at all, because the token records the outcome of a client-side check, and
DataDome's own documentation describes that check as
[JavaScript collecting "hundreds of signals"](https://docs.datadome.co/docs/device-check)
— canvas rendering among them, execution times measured — none of which a
`curl_cffi` session can produce.

The limitation worth writing down: "homepage first, then the search, on one
session" is not expressible in the harness, because the driver rebuilds the
rungs per URL (`livecheck/rungs.py`). Building that warm-up row is work R.4
should not spend.

### 3. Cookie transfer — portable and long-lived, but revocable

Run `20260912-141448`. The cookie in `settings.json` was minted by a **headful**
browser on **2026-09-10T09:40:25Z** and nothing has touched it since
(`datadome_auto_refresh` is off), so this is that cookie replayed by `curl_cffi`:

| Rung | Target | HTTP | Bytes | ms | Ads | Declared |
|---|---|---|---|---|---|---|
| `curl:safari184` | api-next p1 | 403 | 674 | 229 | — | — |
| `curl:safari184` | html p1 | 403 | 777 | 89 | — | — |
| `curl+cookie` | api-next p1 | **200** | 246,462 | 606 | 25 | 18,210 |
| `curl+cookie` | html p1 | **200** | 921,280 | 161 | 25 | — |

Same process, same profile, same minute, one cookie of difference. So a cookie
earned in a Chrome session **survives replay from a different TLS fingerprint**
— it is not bound to the handshake that earned it. And it was **50.8 hours old**
when it did, sixty-one times the fifty-minute TTL this app assumes.

The portal's own `Set-Cookie` agrees about the lifetime: the `datadome` row
Chrome stored in `browser_profile/` during run `20260912-141707` expires
**2027-09-12**, a year out, and DataDome documents exactly that —
[the cookie is encrypted, carries no PII and expires after one year](https://docs.datadome.co/docs/cookie-session-storage),
its lifetime a customer setting that can be lowered
[no further than seven days](https://docs.datadome.co/docs/data-privacy). What
it stores is whether this visitor passed a CAPTCHA or Device Check, which is
both why it is worth so much and why it is the one asset here that deserves to
be kept rather than regenerated.

**It can be revoked, though, and it was — during this session.** See §4.

Not measurable from one address: whether the cookie is also bound to the IP that
earned it. One connection gives one answer. Of the two claims in
`cookie_harvester`'s module docstring — bound to the IP, lives about an hour —
the second is now measured false.

### 4. The address — not flagged; the cookie's own standing is what changed

The same rung at the start and at the end of the session, on the same URL:

| Time | Run | Rung | api-next p1 | html p1 | Body |
|---|---|---|---|---|---|
| 14:14 | `20260912-141448` | `curl:safari184` | 403, 674 B | 403, 777 B | `/interstitial/`, `rt:'i'` |
| 14:28 | `20260912-142845` | `curl:safari184` | 403, 674 B | 403, 777 B | `/interstitial/`, `rt:'i'` |
| 14:14 | `20260912-141448` | `curl+cookie` | **200**, 25 ads | **200**, 25 ads | — |
| 14:28 | `20260912-142845` | `curl+cookie` | **403**, 669 B | not tried (breaker) | `/captcha/`, `t=fe` |

**Ruled out: the address was flagged by this morning's refusals, or by this
session's.** Byte for byte, fourteen minutes and a dozen refusals apart, the
cookieless treatment is unchanged: the same interstitial at the same size, never
escalated. Nothing here is IP-level.

**Ruled in, and it is the finding of the day: the cookie was burned between
those two runs, and the headless browser run of §5 is what burned it.** The
refusal the cookie now draws is not the cookieless interstitial — it is a
`geo.captcha-delivery.com/captcha/` with `t=fe`, a client DataDome knows and has
stopped trusting. And its `initialCid` is
`AHrlqAAAAAMAhjQLJNDzZBAABVqIsA==`, *the same identifier the browser run's
CAPTCHA page carried at 14:17*, where both cookieless runs carry different ones.
The reading — an inference from that match, not a documented field — is that the
browser presented the very cookie `settings.json` holds (it was minted into that
persistent profile on 2026-09-10), failed Device Check as automation, and took
the shared DataDome session down with it. Fourteen minutes later the cookie
replayed by `curl_cffi` inherits that verdict.

The alternative reading is that the cookie simply reached the end of its life
between 14:14 and 14:28, unaided. It fits the clock far worse than the
`initialCid` does, and it does not explain a `t=fe` CAPTCHA instead of the
interstitial an unknown client gets.

Confirming it costs three requests — mint headful, run the headless rung, re-run
`curl+cookie` — and they were **not** spent today: the portal is now refusing
every rung from here, and the rule in the budgets above is that a portal which
stops answering gets `--replay`, not another attempt. Whoever picks this up does
it on a fresh cookie and a quiet day.

**Operationally, this leaves the app without a working free rung until someone
mints a new cookie** — *Settings → Advanced Scraping → "Grab a fresh cookie
now"*, which is headful and needs a person for the CAPTCHA.

### 5. A real browser, headless — refused harder than `curl_cffi`

Run `20260912-141707`, `--rungs browser`: Playwright driving the **real Chrome**
installed on this machine (`cookie_harvester._launch` prefers channel `chrome`,
then `msedge`, then bundled Chromium; Camoufox is not installed), on the
persistent `browser_profile/` directory, with
`--disable-blink-features=AutomationControlled` and `navigator.webdriver`
shimmed.

| Rung | Target | HTTP | Body |
|---|---|---|---|
| `browser` | api-next p1 | 403 | CAPTCHA page |
| `browser` | html p1 | 403 | CAPTCHA page |

The body is what matters. Cookieless `curl_cffi` gets `var dd={'rt':'i',…}` and
`i.js` — the *interstitial*, the challenge a real browser clears by running it.
The browser got `var dd={'rt':'c',…,'t':'bv',…}` with `c.js` and an iframe
whose query carries `&t=bv&dm=cd`: a CAPTCHA, `dm=cd` for Device Check, and the
`bv` variant, which presents nothing to solve. **The better-equipped client was
classified worse than the crude one.**

Three consequences, all for R.4:

* **A headless browser-primary scan rung is not the free path.** It measures
  below the rung it would replace.
* **A headless run does not fail quietly — it spends the cookie.** This is the
  §4 finding from the other end: the run presented the profile's DataDome
  session, was judged automation, and that session stopped working for
  `curl_cffi` too.
* **It also overwrites the profile.** The `datadome` row in `browser_profile/`
  now carries a value created `2026-09-12T12:17:22Z` — written by this refused
  run, over whatever the successful headful session of 2026-09-10 left there.
  [Invariant 18](invariants.md)'s fail-open protects `settings.json`, not the
  profile: the next mint starts out presenting a token earned while the client
  was being classified as a bot. Clear that row before minting, or mint in a
  profile of its own.

### The one recommendation this points at (R.4)

**Make cookie custody the product: mint headful, renew on refusal, and take the
headless refresh path out of service. Do not build a browser-primary rung.**

Everything above converges on it. The cookie is the only free rung that works
from this connection; it is portable across fingerprints and lives for days, not
minutes; and the thing that destroys it is the app's own unattended browser.

1. **Headful only.** Headless cannot mint — it draws `t=bv`, which has nothing
   to solve — and it burns the cookie already in hand on the way out. Today
   `datadome_auto_refresh` is off by default, which is the only reason this cost
   one cookie instead of every cookie; that default is now load-bearing and the
   flag should not arm a headless launch at all until it is headful.
2. **Stop expiring the cookie on a fifty-minute clock.**
   `maybe_auto_refresh()` is the only reader of `datadome_cookie_ttl_minutes`,
   and a cookie sixty-one times past that TTL returned 25 listings today. Renew
   when a request is *refused*, which is observable, instead of when a timer
   predicts death.
3. **Keep the paid rung as the escalation**, inside the monthly credit ceiling
   the metering already enforces, for the case where the cookie is refused and
   nobody is at the keyboard.

What R.4 should not spend a line on: a `curl_cffi` upgrade (§1), a homepage
warm-up row (§2), or a headless browser rung (§5).

### What was built from it — 2026-09-12

All three points, and nothing else.

`refresh_into_settings` now refuses `headless=True` before it launches anything,
so the only way to mint is the Settings button in a visible window. The TTL is
gone — `datadome_cookie_ttl_minutes`, `cookie_is_stale()`, `maybe_auto_refresh()`
and the scan's pre-flight call to it no longer exist, and neither does the
availability check's reactive re-mint. What replaced them is bookkeeping:
`note_cookie_refused` / `note_cookie_accepted` write `datadome_cookie_refused_at`
and a human-readable `_detail` on the transition, so Settings can say *which rung
was refused and when* instead of counting down to a death that does not happen on
a clock. `datadome_auto_refresh` survives, renamed on screen to what it actually
does — carry on through the persistent browser when the fast requests are blocked
— and no longer arms any mint. The paid rung stays the escalation for a refusal
nobody is present to answer, inside R.2's monthly ceiling.

The free path was re-measured afterwards, run `20260912-192930`,
`--suite --rungs curl+cookie`, no credits spent:

| | Answered | Rung | Target |
|---|---|---|---|
| Immobiliare | 6 of 6 | `curl+cookie` | api-next p1, 25 ads each |
| Idealista | 3 of 3 | `curl+cookie` | html p1, 30 ads each |

Nine of nine, on the cookie minted headful at `2026-09-10T09:40Z` — **fifty-six
hours old, and sixty-seven times the TTL that would have thrown it away.** That is the
§3 finding holding at a second sitting, which is the whole case for deleting the
timer.

## Measurements — 2026-09-13, Idealista through the same loop

Every live run to this point had been an Immobiliare run that happened to carry
Idealista's three entries along. Idealista had never been the subject of one, and
`3 of 3 · 30 ads` above is what that costs: the row was green and three of the
four findings below were sitting under it. **An answered row is not a correct
one** — the count comes from the card parser, and every field inside those cards
can be empty without the count moving.

Four runs, `--rungs curl+cookie` throughout: `20260913-015929` (the survey),
`20260913-020237` (the 404 probe, one URL), `20260913-022215` (after the first
two fixes) and `20260913-022623` (after all four). **Seven requests in total
against a 12-per-run cap, no credits spent, the paid rung never armed.**

### 1. Every rent parsed with no price at all

`ide-zone` and `ide-zone-form` reported 30 ads each and **30 of 30 had
`price=None`**. Two independent causes, either one sufficient:

* The per-square-metre guard in `parse_price` was written `€/m` with no unit
  after it, so it matched the `€/m` of `1.150 €/mese` and deleted the rent it was
  there to protect. It now requires the unit — `€/m²`, `€/mq`, `€/m2`.
* The instrument never told the scraper which contract it was reading. A scraper
  learns that inside `scrape()`, and a live check calls the parsers directly, so
  `self.contract` stayed at the constructor's `"sale"` and invariant 10's sale
  bounds threw away every monthly rent as implausible. `Target` now carries the
  contract for every kind, from `detect_contract` on the search URL, and
  `--replay` records it so a saved run re-parses the way it ran.

Both were live before this cycle and neither is visible in a count. After:
30 of 30 priced on all three entries — `1.150 €`, `1.350 €`, `1.200 €` on the
Forlanini zone, `219.000 €`, `250.000 €`, `490.000 €` on the Milan city search.

### 2. The free-text grammar states its total a second way

`ide-zone-form` published no total. Idealista's zone pages head themselves
*"66 case in affitto a Milano"*; the `/cerca/<filters>/<Zone>_<City>/` pages the
builder produces never write that phrase — they head *"Forlanini Milano: 114
annunci"* and link *"vedi 114 case"*, the noun without the contract.
`declared_result_total` now tries a second pattern requiring the `vedi`, which is
what keeps it as safe as the first: a footer's *"case in vendita a Roma"* or a
card's *"3 locali"* cannot reach it. On pages that publish both forms the two
agree, and invariant 26 is intact — this is still a number the portal stated.

### 3. The 404 that means "nothing matches" — confirmed live

`base.py` treats a 404 as an empty result set when the body says so, which is a
guess worth checking against the portal rather than against a fixture. A rent
search capped at €200 with a 250 m² floor
(`/affitto-case/milano/forlanini/con-prezzo_200,dimensione_250/`) answered
**HTTP 404 carrying a 218 KB no-results page**, and the check read it as
`no_results` — *"answers (nothing matches this search)"* — not as an error. The
other half is pinned synthetically: a 404 whose body says nothing of the kind
still raises.

### 4. The official rung vanished when there was no key

`_idealista_targets` built the official target only where a key **and** a plan
both existed. With neither, the rung had nothing of its kind to pair with and
produced no row — a run with no key read as though the official API had never
been on the ladder. The target is now always built, and the two reasons divide
cleanly: the rung owns *"this transport cannot be used from here at all"* (no
key), the target owns *"this search cannot be expressed for it"* (a filter in
`UNMAPPED_FILTERS`). The rung's reason wins when both apply.

### No key exists here, and the app now says so

There is no Idealista API key on this machine and none was obtained: keys are
issued by hand. The setup copy promised they were *"free and arrive in a couple
of days"* — [the access-request page](https://developers.idealista.com/access-request)
states neither, only *"To receive an API key get in touch and tell us a bit about
your project."* Both language files now say what is true: keys are issued by hand
after you describe your project, no turnaround is published, and **until you have
one, Idealista is read from the site and the API is never contacted.** Everything
else was already honest — `get_scraper` hands back the plain scraper,
`transport_used` names the official API only when it was actually used, and
Settings shows *set / not set* rather than a promise.

### Where Idealista stands

| Shape | Entry | Answered | Ads | Total the portal stated |
|---|---|---|---|---|
| a city | `ide-city` | `curl+cookie`, html p1 | 30, all priced | 14,771 |
| a zone with filters | `ide-zone` | `curl+cookie`, html p1 | 30, all priced | 66 |
| the form's grammar | `ide-zone-form` | `curl+cookie`, html p1 | 30, all priced | 114 |
| the official API | — | never asked | — | no key on this machine |

Three of three, on the same headful cookie, with the fields inside the cards
checked and not just counted. `idealista_unsupported` was not reached in any run
and no zone mapping failed, so neither is measured here.

## Measurements — 2026-09-13, the real scan path end to end

Everything above measures transports and parsers from the outside. This one ran
the product: a backend of its own on port 8138 with a throwaway data directory,
the seven reference shapes created **through the API the dashboard posts to**,
and one full scan. What it reads is the scan journal — the row the owner used to
read by hand, now the verdict of the real-scan check in
[`manual-tests.md`](manual-tests.md#what-a-tool-decides-now) — not the tool's own
summary.
**Zero credits of the 150 budgeted**: every search answered on the free local
rung, and the paid one was never armed.

| Entry | Outcome | Saved | The portal's own total | Pages | Why it stopped |
|---|---|---|---|---|---|
| `imm-city` | `ok` | 75 | 18,232 | 3 / 3 | the page limit of 3 pages |
| `imm-zone-path` | `ok` | 214 | 256 | 12 / 3 | the page limit, on each of 4 parts |
| `imm-zone-ids` | `ok` | 75 | 989 | 3 / 3 | the page limit of 3 pages |
| `imm-polygon` | `ok` | 75 | 1,193 | 3 / 3 | the page limit of 3 pages |
| `imm-radius` | `ok` | 75 | 3,388 | 3 / 3 | the page limit of 3 pages |
| `ide-city` | `ok` | 90 | 14,773 | 3 / 3 | the page limit of 3 pages |
| `ide-zone` | `ok` | 65 | 65 | 3 / 3 | nothing more to give |

Seven of seven `ok`, every count consistent with the total the portal declared,
and the one row that fetched more than the cap says so in its `detail`. Then the
fields inside: every Immobiliare row 100% on title, zone, city, surface and URL,
with price on 74–75 of each 75. Which is what made the Idealista column
impossible to miss.

### 1. Not one Idealista property had a zone

`with_zone` was **0 of 89** and **0 of 63** — a green row, a right count, and a
whole portal's worth of properties stored with an empty district. The zone is not
optional furniture: the zone median, the district centroid the geocoder falls
back on, and the zone filter all read that column, so all three were silently
dead for half the corpus.

Idealista never states the district in a field. It states it in the card title —
*"Trilocale in Via Volvinio, 26, Stadera, Milano"* — and `_address_from_title`
took the street and threw the rest away. `_place_from_title` now returns both,
peeling the municipality (already known from the search URL) and then the
district, each taken only where it cannot be anything else: a trailing *"26"* or
*"3 /1"* is a house number, not a place. The embedded-state parser asks the title
too, where the state itself has no `neighborhood`.

The second half of the same defect was in the deduplicator. A property seen first
on the portal that omitted the district and then on the portal that states it
kept the empty one for good — the merge filled a missing address and never a
missing zone. It fills both now, and still never overwrites a district already
stated.

### 2. "12 pages, the page limit of 3 pages"

`imm-zone-path` split into four parts, fetched three pages of each, and reported
both numbers in one row: `pages: 12` beside `page_limit: 3`. Read as arithmetic
it is an error, and the structured fields gave a reader no way to tell it was
not. `_stop_reason` now says *"the page limit of 3 pages on each of the 4
parts"* whenever the result carries parts, which is the only case where the two
numbers are allowed to disagree.

### 3. The review was reviewing a URL the product would not save

Both form-built searches were refused with **400 — an identical monitored search
already exists**, and that refusal is the finding. With `verify: true` the
builder confirmed the Idealista zone page and produced the pasted URL exactly;
`--compare-form`, which spends no request, had been comparing against the wider
`/cerca/` fallback and calling it *"the same criteria, in a grammar the pasted URL
did not use"*. So the check reported a totals gap the user's own press of Generate
never produces — the one thing item 2 defines as a failure. The restatement now
infers the probe's answer where it is already known (the pasted URL *is* that zone
page, and it answered), reports the URL Generate would save, and names the
fallback beside it. The suite still requests the `/cerca/` grammar on purpose: it
is a live path of the product and this is the only check that ever exercises one.

None of the three could be caught offline before it was seen live, and all three
are pinned offline now — the parser against saved cards, the stop reason against
a split result, the restatement against the reference suite. No network in any of
them.

## Measurements — 2026-09-14, the acceptance pass

The run above measured the scan path against the reference shapes. This one asked
the narrower question a release actually turns on: does the product work for
someone using it the way the owner does. Four searches — Immobiliare and
Idealista, sale and rent — created through the API, one scan, every journal row
and a sample of the stored properties read, *Prova questa ricerca* on each, and
the built dashboard walked in Chromium against the same backend. **Zero credits
of the 75 budgeted**; the paid rung was never armed.

**Use 8140, not 8138.** The run before this one took 8138 and said so, and 8138 is
`EMPTY_BACKEND_PORT` in `frontend/e2e/harness/ports.ts` — the browser suite's second
backend. A live backend left on it does not collide with anything until someone runs
`npm run e2e`, which then fails to start with *"already used"* and looks like a suite
defect. 8137, 8138 and 8139 all belong to harnesses; 8140 is the first free one.

| Search | Outcome | Listings | Pages | Why it stopped |
|---|---|---|---|---|
| IMM sale, Milano Bicocca | `ok` | 257 | 21, in 2 parts | the parts covered the whole result set |
| IMM rent, Milano Bicocca | `ok` | 250 of ~683 | 10 / 28 | the page limit of 10 pages |
| IDE sale, Milano Forlanini | `ok` | 248 | 10 / 10 | the page limit of 10 pages |
| IDE rent, Milano Forlanini | `ok` | 65 | 4 | nothing more to give |

Four of four `ok`, the stored fields present on the sample read back, one listing
per portal opened in a real browser and still live, and the dashboard walked over
nine screens — the grid in both contracts, the map, a detail panel, insights,
searches, activity, logs, settings — with **no console error, no page error, no
failed request and no response at or above 400**. Two defects came out of it
anyway, both invisible to a green journal row.

### 1. An Idealista macro-area flagged every district inside it

`outside_requested_area` fired on **224 of 248** Idealista sale listings and **52 of
65** rents. Not one was outside anything: the searches are Forlanini, and what came
back was Mecenate, Ponte Lambro and Parco Forlanini — the districts *inside*
Forlanini.

Idealista's search paths nest three levels — `/milano/fiera-de-angeli/fiera/` — and a
URL that stops at the second names a macro-area. No listing ever carries one:
`_place_from_title` reads the district off the end of the card title, which is always
the narrowest level. So the requested zone and the listing's zone are two levels of
one hierarchy, and nothing in the app can resolve either into the other — there is no
district gazetteer, only the comuni in `geo_reference`. The check was reading a
disagreement out of a difference in altitude.

`zone_is_macro_area` in the search builder now recognises the shape, and
`requested_area` drops the zones when it sees one, exactly as it already did for
Immobiliare's opaque `idMZona[]` ids: the comune still applies, the districts cannot.
Re-run over the same stored corpus, the two Idealista searches go **224 → 0** and
**52 → 0**, and the Immobiliare searches keep all of theirs — Istria, Precotto,
Maggiolina, Affori and Dergano really are other districts. That is the guard against
over-correcting, and it has a test of its own.

### 2. The header said what the scan did, in English, in an Italian app

`scan_state["last_summary"]` was an English sentence built in the scanner
(*"14 new, 2 updated, …"*) and printed verbatim in the nav header. The rule it broke is
one the same file already follows for `last_portals` and the cards follow for
`filtered_reason`: **the backend sends the facts, the dashboard writes the sentence.**
It is now `last_counts` — five integers and a `ScanCountsOut` schema — with
`nav.lastScan` and the two `nav.lastScanTruncated` forms owning every word in both
language files.

### What this pass could not close

* **Immobiliare refused this connection throughout.** *Prova questa ricerca* on both
  Immobiliare searches returned `blocked`: 403 on the first rungs, then the breaker
  after three in a row. `--suite` the same hour agreed — six Immobiliare entries, no
  rung worked, 403 on every free one tried — while Idealista answered 3 of 3 on
  `curl:safari184`. The refusal followed the scan's own 45 pages from this address, so
  it is the expected cost of having just run one, and it is not something this machine
  can decide: per the budgets, it gets no retries.
* **`deal_reasons` is still English** in the same Italian panel, for the same reason
  item 2 existed. It is a stored column rather than a line in flight, so it is a
  migration and not a rendering fix; it is written up in
  [`roadmap.md`](roadmap.md#deal_reasons-reaches-an-italian-screen-in-english) with
  what closing it costs.
* `curl:safari18_4_ios` raises `ImpersonateError: Impersonating safari18_4_ios is not
  supported` on both Idealista runs — a rung on the ladder that the installed
  `curl_cffi` cannot actually drive.

## Measurements — 2026-09-19, one request answers and the next is refused

For a week Immobiliare behaved as if it were rationing: a fresh cookie answered
once and then refused, a rested connection answered once and then refused. The
pattern was read as a rate limit and it was not one — **the app was throwing the
cookie away between requests.**

### The shape, run by run

| When | What happened |
|---|---|
| 2026-09-12 | 6 of 6 reference searches answered on a cookie 56 hours old (§ *Measurements — 2026-09-12*) |
| 2026-09-14 | a scan read 45 pages in one session; every session after it was refused |
| 2026-09-18 11:03 | 0 of 6, every free rung 403, on the same cookie |
| 2026-09-18 11:06 | cookie minted headful minutes earlier: first request 200 with 25 ads, **every later request 403** |
| 2026-09-18 11:10 | two requests, both 403 — and each 403 carried a `Set-Cookie: datadome=…` of its own |
| 2026-09-19 10:41 | after a day's rest: one request 200 with 25 ads, declared total 18,607 |

The three refusals of 11:06–11:10 went out on **three different sessions**, each
one freshly seeded with the same saved cookie. That is the whole tell.

**One correction, because it cost a day of reasoning.** The 10:41 run was read as
"answered once, then refused". It was not: after the one 200, every remaining
attempt is `skipped — request cap reached (3 per run)`. The budget stopped that
run, not the portal. A skipped attempt and a blocked one both read as *nothing
came back* in the summary table, so check the `OUTCOME` column before concluding
a portal refused you.

### What the portal is actually doing

DataDome reissues its token on an answered request and stops trusting the value
that token superseded once the binding context drifts; the cookie is not a bearer
credential that can be lifted from one client and replayed from another. The
published guidance is the opposite of what this app was doing: persist the cookie
the portal hands back, per session, pinned to the address it was earned from.

* [DataDome — cookie & session storage](https://docs.datadome.co/docs/cookie-session-storage)
  (the cookie is long-lived and used by both the server- and client-side checks;
  the refresh mechanics are not documented)
* [The DataDome cookie lifecycle](https://blog.crawlex.net/blog/datadome-cookie-lifecycle/)
* [403s with the same status and different causes](https://www.aethyn.io/blog/datadome-403-same-status-different-outcomes)
* [Handling DataDome blocks from Python](https://www.aethyn.io/solutions/handle-datadome-blocks-python)

Nothing in any of them documents a per-cookie or per-address request threshold,
which is the other hypothesis this measurement had to separate.

Against that, the code read as a machine for discarding rotations:
`BaseScraper._new_session` seeded the *saved* cookie onto every new session and
nothing ever wrote back what came in on a `Set-Cookie`; `run_checks` built a new
scraper per URL and `build_rungs` a new session per rung, so a six-search suite
was six to twelve first-time visitors in a row; and one `datadome_cookie` setting
fed both portals, so minting for one overwrote the other's working token with a
value that had never been valid there.

### The measurement

One run, 2026-09-19 11:22:17, about 40 minutes after the last request left this
address. `--suite --portal immobiliare --rungs curl+cookie --max-requests 8`,
**8 requests, zero credits, no `--paid`**: five geography lookups (three of which
went to the network) and five listing requests, all on **one session** carrying
whatever cookie the portal had last set.

| Search | Shape | HTTP | Ads | Declared total | ms |
|---|---|---|---|---|---|
| `imm-city` | city | 200 | 25 | 18,607 | 202 |
| `imm-zone-path` | zone in the path | 200 | 25 | 247 | 373 |
| `imm-zone-ids` | zone ids in the query | 200 | 25 | 1,003 | 424 |
| `imm-polygon` | drawn polygon | 200 | 25 | 1,226 | 637 |
| `imm-radius` | radius around a point | 200 | 25 | 3,470 | 475 |
| `imm-zone-path-form` | form | — | — | — | skipped at the 8-request cap |

**5 of 5, where the same ladder got 1 and then 403s.** Hypothesis (a) — rotation
with the superseded value distrusted — is confirmed; hypothesis (b), a rate or
behaviour threshold, is not what was stopping these runs. Five requests inside a
minute is the opposite of what a rate limit tolerates.

What this does **not** rule out is a threshold much higher up: the 45-page scan of
2026-09-14 was followed by real refusals, and nothing here measures where that
edge is. The scan's existing page caps and `request_delay_seconds` stay the answer
for volume; they were not tightened, because there is no measured number to tighten
them to.

### What was built from it

* **The cookie the portal hands back is kept.** `_CookieKeepingSession` wraps the
  scraper's session, reads the `datadome` cookie off the jar after an answered
  response and persists it. Only after an answered one: every 403 on 2026-09-18
  also set a cookie, and a token issued alongside a refusal is not worth keeping.
* **Per portal, not shared.** `datadome_session_cookies` holds one value per
  portal, keyed by the jar's domain; `datadome_cookie` stays the seed a first
  session starts from, and minting a new one drops the rotations it supersedes.
  A fresh cookie for Immobiliare no longer overwrites Idealista's.
* **One session per portal per run.** `run_checks` builds one scraper and one set
  of rungs per portal instead of per URL, and the `curl+cookie` rung goes out on
  the scraper's own jar — the one the geography lookup already used — rather than
  opening a second jar seeded from the same value.
* **It is a secret, and it is treated as one.** The rotated values are written by
  the scrapers and never by a person, so they are not in `SECRET_SETTINGS` (that
  list drives the settings form's mask/unmask round trip). `config.secret_values()`
  is what the two redactors read instead, and `GET /api/settings` drops the map
  outright: nothing in the UI reads it, so it never leaves the backend.
* **Still no retry loop.** A refusal ends the attempt exactly as before
  (invariant 8); what changed is what the *next* attempt carries.

## Where it fits

* A scan came back empty or blocked and you want to know why:
  [`scan-returns-nothing.md`](scan-returns-nothing.md) is the decision tree; this
  tool is how you get the evidence it asks you for without guessing.
* Before a release, this tool **is** the real-scan check: `--suite` for the
  transports and the parsers, and the end-to-end run above for the product — its
  own backend, the searches created through the API, one full scan, the journal
  row read. Both lines are in
  [`manual-tests.md`](manual-tests.md#what-a-tool-decides-now), which now lists
  only what a person is still asked for.
* A portal changed something overnight and you want to know how much of the
  product it took with it: `--suite` answers it shape by shape in one run.
* The parsing strategies themselves, and which portal quirk each one exists for,
  are in [`architecture.md`](architecture.md).
