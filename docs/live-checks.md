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
