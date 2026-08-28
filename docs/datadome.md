# Keeping Scans Unblocked (DataDome)

[← Back to README](../README.md)

Both portals sit behind **DataDome**, an anti-bot system that occasionally
answers a scan with a block instead of listings. This is expected, not a bug:
a blocked profile shows `Blocked (will retry)` and is retried on the next scan,
and you are alerted only if it fails several scans in a row (see
[Scraper health alerts](notifications.md#scraper-health-alerts)).

A search that finds **nothing** is not an error either: it reports 0 listings and
stays healthy. (Idealista answers such a search with an HTTP 404 — the same code
it gives a URL that does not exist — so the scan reads the page itself to tell
"no flats here today" from "no such zone". A genuine `Error` on a profile means
its URL is wrong or the portal changed its markup.)

The single most effective way to prevent blocks is to hand the scraper
a **`datadome` cookie** earned by a real browser on your own connection.

You can provide that cookie in three ways, from most to least automatic:

* **Automatic (recommended)** — in **Settings → Advanced Scraping**, press
  **"Grab a fresh cookie now"**. The app opens a local browser, earns the
  cookie, and saves it for you — no copy/paste. A window may briefly appear; if
  the portal shows a CAPTCHA, solve it once and it is remembered for next time.
  Not every block page has anything to solve, though — a hard "access
  restricted" wall just sits there — so a **⏹ Stop** button appears next to it
  while it runs, in case you'd rather give up than wait out the full timeout.
  You can also tick **"Refresh automatically before each scan"** so a scheduled
  scan always starts with a live cookie. With that option on, the app *also*
  grabs a fresh cookie **on the fly if the "Check if still online" button gets
  blocked** mid-run — it swaps in a new cookie and keeps going instead of
  stopping (bounded to a couple of attempts, so it never turns into hammering).
  This needs a one-time install of the
  browser engine, run **inside the backend's virtual environment** — not a
  system-wide `pip` — since that is the Python the app actually runs on:
  ```bash
  cd backend
  .venv\Scripts\python -m pip install playwright
  .venv\Scripts\python -m playwright install chromium
  ```
  Installing into a different Python (a global interpreter, another venv) will
  report success but leave the app unable to see it, and the Settings panel
  will keep showing the button as unavailable. After installing, restart the
  backend so it picks up the new package; until then the app runs exactly as
  before and simply hides the button.
* **Manual** — open a portal page in your browser, copy the `datadome` cookie
  from the developer tools, and paste it into the Cookie field. The panel has
  step-by-step instructions. The cookie expires after ~1 hour, so this is the
  gesture the automatic grab removes.
* **Proxy** — route scraper traffic through a proxy
  (Settings → Proxy URL). Note a *datacenter* proxy is blocked harder than your
  home IP; only a residential proxy helps. You can also list **several proxies**
  (Settings → *Proxy pool*, one URL per line): each scraping session sticks to
  one of them, and an address that gets blocked is rested for a while so the
  next attempt leaves through a different IP — one burned proxy no longer takes
  every scan down with it.
* **Scraping API** — for the sturdiest option, paste a key from a DataDome-solving
  scraping API (Settings → Advanced Scraping → *Scraping API*: Scrapfly,
  ScraperAPI or Zyte). Instead of fetching pages from your own IP, each scan
  hands the target URL to the provider, which returns the already-solved HTML —
  so blocks stop reaching your connection entirely, and detail data (like map
  coordinates) becomes fetchable. This is the one place the app can use a paid
  cloud service, and it stays **optional**: free tiers (~1,000 calls/month) can
  cover a small personal scanner, and with no key set the app runs exactly as
  before, fully local. Empty the key to go back to the local path.
  By default a saved key is used *only as a fallback*, so credits are spent
  only during an actual outage: scans start on the free local path and escalate
  to the provider when blocked (mid-scan, once the local retries are exhausted,
  or from the start when a search has already failed its last couple of scans).
  Switch **When to use it** to *"Always"* to route every fetch through the
  provider instead. The **Scraper health** panel on the dashboard shows which
  transport carried each day's scans.

* **Idealista's official API** — the only option on this page that is not a
  workaround, and the only one that removes the block rather than getting past
  it. Idealista runs a developer programme covering Italy: with a key and secret
  pasted into **Settings → Advanced Scraping → *Idealista official API***,
  searches on that portal ask Idealista for its own data instead of reading its
  pages. Nothing to block, no cookie, no browser. Keys are **not** self-service
  — you describe your project at
  [developers.idealista.com](https://developers.idealista.com/) and one is
  issued by hand, with a monthly request allowance agreed at the same time.
  That allowance is why the app spends **one request per search per scan** by
  default (it returns up to 50 listings); raise *Requests per search, per scan*
  once you know your own limit.

  It is a **complement to the scraper, never a replacement**, and it says so out
  loud: a search the API cannot express *exactly* — one narrowed to a
  neighbourhood, or to a room count, or to a feature like "with a lift" — keeps
  using the normal scraper, and so does any search the API refuses, runs out of
  quota on, or answers with nothing. The reason is that a room count means
  *locali* on the Italian site and *bedrooms* in the API, and quietly assuming
  they are the same number would return a plausible page of the wrong flats. The
  **Scraper health** panel names which engine served each day's scans.

Nothing here is required for the app to work — a home connection is trusted by
DataDome most of the time on its own. These are the levers for when it isn't.

---

## What DataDome actually measures

Everything above is a lever. This part is the map that tells you *which* lever a
given block calls for. It is written down because the detection changed in 2026
while nothing here was failing, and because the reasoning behind these levers is
not visible from looking at them.

### The handshake is fingerprinted with JA4+, not JA3

Before a page is even requested, a secure connection has to be opened, and the
first message the client sends — the *ClientHello* — announces which TLS version,
cipher suites and protocol extensions it supports. Every browser sends a slightly
different one. None of it is secret; the point is that it is hard to fake
*consistently*.

The old fingerprint, **JA3**, boiled that message down to a single hash. It
stopped working for an unglamorous reason: Chrome began shuffling the order of
its TLS extensions on every connection, so real Chrome produced a different JA3
each time and the hash identified nothing.

Its replacement, **JA4+**, is what fingerprints the scraper today. It is a family
rather than one hash — the handshake, the HTTP request that follows it, the
certificate and even the round-trip timing each get a component — and the TLS
part is built to survive shuffling: it sorts the lists before hashing, writes the
**number** of cipher suites and the **number** of extensions into the readable
front of the fingerprint, and keeps a raw variant that preserves the original
order.

The consequence is the only part worth remembering: **a handshake is either
exactly some real browser's, or it is nobody's.** Under JA3 an approximate
imitation produced an unknown hash that could pass as an unremarkable client.
Under JA4+ one extension too many lands the connection in a bucket no real
browser has ever occupied — which is a louder signal than merely being
unrecognised. That is why every profile in the rotation was *measured* against
the live portals rather than reasoned about ([invariant 8](invariants.md)):
"close enough" is not a category that exists here.

### A profile is changed as a unit, never piecemeal

The `safari184` in the rotation is not a User-Agent string. It is the entire
costume: the ClientHello, the HTTP/2 settings, the header names *and the order
they are sent in*, and the User-Agent last of all. `curl_cffi` supplies all of it
together — which is why the scraper sets a few `Accept-*` and `Sec-Fetch-*`
headers and deliberately **never sets a User-Agent** of its own. The profile owns
that line.

This avoids the mistake that is easiest to walk into. A User-Agent claiming
Safari 26 arriving over a Safari 18.4 handshake is a combination no real browser
can produce, and spotting it is a table lookup — caught on the first request,
not inferred slowly over many. So when the profiles start to look old, the fix is
to change the profile *name* to a newer one and measure it. Editing a header to
look newer while the handshake stays where it was is not a smaller version of
that fix; it is strictly worse than doing nothing.

The browser rungs work for the same reason in reverse: a cookie earned by a real
local browser comes from a session where every layer already agrees with itself.

### About a quarter of the verdict is the address you come from

The handshake is not the whole score. Where the request originates is estimated
to carry roughly a quarter of it, and it is judged separately: the address's
reputation, whether it belongs to a home internet provider or to a datacenter,
and what else has lately been seen coming from it.

This is the largest single reason the app is built to run **on your own
connection**. A residential address earns a reasonable score for free, with
nothing to buy or maintain. A datacenter address — every cheap VPS, every cheap
proxy, and the runners of any CI service — starts with a handicap that no
handshake, however perfect, cancels out. That is the whole story behind the
warning under *Proxy* above, and behind the rule that automated builds never
reach a portal.

Note which way the asymmetry runs: a good address will not rescue a bad
handshake, but a bad address will undo a good one.

### Telling a stale profile from a burnt address

When the free rung starts getting blocked, these are the same symptom and
opposite fixes, so establish which one you have before changing anything.

**First, rule out the boring cause.** The `datadome` cookie lasts about an hour.
Press **"Grab a fresh cookie now"** and scan again; most of the time that is the
end of it.

**Then run the one test that separates them:** open the same portal page in your
own browser, on the same connection, with no proxy.

* **The page loads normally** → your address is fine, and the scraper's disguise
  is what is being rejected. *The profile went stale.* Expect blocks on every
  profile in the rotation rather than one, on both portals at once, or appearing
  right after a `curl_cffi` upgrade. Check the log for `TLS impersonation:
  dropping …`: that is the self-healing filter reporting that an upgrade retired
  a profile name, leaving the rotation shorter than you configured it.
  **Fix:** update `curl_cffi`, then edit `tls_impersonations` in `settings.json`
  (in the data directory) — move a working profile to the front, drop a burnt
  one, add a current-generation name. It is a setting precisely so this needs no
  new release. Measure the result against a live page before trusting it.

* **Your own browser gets a CAPTCHA or a wall too** → the disguise is innocent.
  *The address went bad.* Expect this to have begun when a proxy was switched on
  or the network changed, or to affect one proxy in the pool and not the others,
  or to happen on a machine in a datacenter while the same code works from the
  laptop.
  **Fix:** stop routing through that proxy — no proxy beats a datacenter one —
  and give a residential address time, since its reputation recovers on its own.
  If the machine is permanently in a datacenter, the local rungs are the wrong
  tool for it: go up to the scraping API or Idealista's official API, both above.

**Where to look while diagnosing:** the **Scraper health** panel on the dashboard
names the transport that carried each day's scans — a day labelled
`local (curl_cffi)` with no blocks is the cheap rung doing its job. The **📜** log
viewer in the top bar carries the rotation lines (`switching impersonation ->`)
and the filter warnings above.
