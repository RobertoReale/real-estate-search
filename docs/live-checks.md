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

### `--compare-form`

```bash
cd backend && .venv\Scripts\python -m app.livecheck --compare-form
```

Implies `--suite`, and prints a second table: the pasted search's total and the
form-built total side by side, with `search_validator`'s review of what the
restatement approximated or dropped. It is the computed half of item 2 of
[`manual-tests.md`](manual-tests.md) — the gap between two totals is only a bug
when the review did not predict it.

The review is free; it is computed offline whether or not the run had a total to
put beside it. So a shape the form cannot express says so in words —
*the builder has no grammar for a search drawn on the map*, and `drawn_area
dropped` — instead of showing an empty cell that reads as "not checked". The
converse case is the one worth the run: Idealista's zone URL and the form's route
to the same zone carry identical criteria through different grammars, which is
exactly where two different totals are legitimate.

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

## Where it fits

* A scan came back empty or blocked and you want to know why:
  [`scan-returns-nothing.md`](scan-returns-nothing.md) is the decision tree; this
  tool is how you get the evidence it asks you for without guessing.
* Before a release, item 1 of [`manual-tests.md`](manual-tests.md) is still a
  real scan through the app — a live check proves the transports and the parsers,
  not the product. `--compare-form` computes the numbers item 2 asks for, but not
  the screen that has to show them.
* A portal changed something overnight and you want to know how much of the
  product it took with it: `--suite` answers it shape by shape in one run.
* The parsing strategies themselves, and which portal quirk each one exists for,
  are in [`architecture.md`](architecture.md).
