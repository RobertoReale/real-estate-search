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

Three ways to say what to check:

| | |
|---|---|
| `python -m app.livecheck URL [URL …]` | the searches you name |
| `--profiles` | every active saved search, read out of `case.db` **read-only** (`file:…?mode=ro`) |
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

## Where it fits

* A scan came back empty or blocked and you want to know why:
  [`scan-returns-nothing.md`](scan-returns-nothing.md) is the decision tree; this
  tool is how you get the evidence it asks you for without guessing.
* Before a release, item 1 of [`manual-tests.md`](manual-tests.md) is still a
  real scan through the app — a live check proves the transports and the parsers,
  not the product.
* The parsing strategies themselves, and which portal quirk each one exists for,
  are in [`architecture.md`](architecture.md).
