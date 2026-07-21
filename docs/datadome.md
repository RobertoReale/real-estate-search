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

Nothing here is required for the app to work — a home connection is trusted by
DataDome most of the time on its own. These are the levers for when it isn't.
