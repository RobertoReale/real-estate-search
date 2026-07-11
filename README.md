# Real Estate Search

[Documentation in Italian](README_IT.md)

Local PC/Raspberry Pi platform that aggregates real estate listings (sale and rental) from **Immobiliare.it** and **Idealista**, deduplicates multiple ads for the same property, filters out unwanted listings (e.g., bare ownership, ground floors, or court auctions), and sends real-time notifications on **Telegram and/or Email**.

---

## Why This Is Different

Real estate portals erase history and hide metrics to protect listing agencies. This platform stores everything in a local **SQLite database (`case.db`)**, acting as your personal **buyer decision engine and negotiation assistant**:

1. **Deal Radar & Congruity Engine (`Deal Score`):** Automatically compares every new listing against the localized €/sqm median of its specific micro-zone (`pricing_stats.py`). Combined with agency historical discounting behavior (`market_velocity.py`), it reveals undervalued opportunities within minutes of publication.
2. **Ghost Price & Re-listing Memory (`Recycled Ad Tracker`):** When a house sits unsold for months at €420k, agencies often delete the ad and re-publish it weeks later as "New" at €389k with different photos. Our cross-portal deduplicator matches coordinates and sqm across old `gone` listings to alert you: `[RECYCLED PROPERTY] previously listed for 160 days at higher price (-9.5%)`.
3. **Red Flags Audit & Real TCO Calculator:** Extracts structural and legal red flags directly from ad text (e.g., active tenant lease, bare ownership, high condo fees > €250/mo, no elevator) and calculates your realistic monthly Total Cost of Ownership (Mortgage + Condo Fees + Renovation buffer).
4. **Zero Cloud, 100% Local Privacy:** Runs locally on your own PC or Raspberry Pi. No paid APIs, no subscriptions, no tracking.

---

## Quick Start

### Windows
Double-click on **`start.bat`**: 
- Installs all dependencies on first run (requires Python 3.11+ and Node.js 18+).
- Starts the backend server (http://localhost:8000) and the frontend dashboard (http://localhost:5173).
- Automatically opens the web interface in your default browser.

### Linux / Raspberry Pi
Open a terminal inside the project directory and run:
```bash
chmod +x start.sh
./start.sh
```
- Installs dependencies and starts both services concurrently.
- Makes the dashboard accessible from any device on your local network at `http://<IP_OF_YOUR_PI>:5173`.

---

## Access from Your Phone

The scraper stays on the PC — portals trust residential IPs and block cloud ones
(see *Technical Architecture*) — but the dashboard can be used from an Android
or iOS browser, and installed as an app icon.

Run **`serve.bat`** instead of `start.bat`. It builds the frontend and serves the
dashboard *and* the API from a single port (8000), so there is nothing to
configure on the phone: open the URL the script prints, then use the browser's
**"Add to home screen"** to get a standalone app icon.

The layout adapts to the screen: filter bars and forms fold into two columns,
the property grid becomes a single column, and buttons grow to a thumb-sized
target. Wide tables (market velocity) scroll sideways on their own rather than
stretching the page.

**Reaching the PC from outside the house**: install [Tailscale](https://tailscale.com)
on both the PC and the phone and log into the same account. It is free, needs no
port forwarding, and no public IP. `serve.bat` detects the Tailscale address
automatically and binds only to it, so the dashboard is reachable from your own
devices anywhere and from nothing else.

> Note: **The API has no password.** Anything that can reach port 8000 can read your
> database and change your settings, so the address matters:
> - *(default)* Tailscale address — only your own logged-in devices.
> - `serve.bat lan` — **every device on your Wi-Fi**, guests included. Convenient
>   at home, but do not use it on a network you do not control.
> - Never forward port 8000 on your router.

Scans keep running only while the PC is on. Since listings stay online for days,
one scan a day is usually enough — and Telegram/Email alerts already reach your
phone without any of this. The dashboard is for browsing and triaging.

---

## How to Use

1. **Get the Search URL**: Go to Immobiliare.it or Idealista.it. Configure your target area (you can draw custom polygons on the map, choose cities, or filter by specific zones), price ranges, and portals' options, then **copy the URL** from your browser's address bar.
   - **This is how you use *every* portal filter.** Whatever you can set on
     Immobiliare or Idealista — bathrooms, floor, elevator, terrace/balcony,
     furnished, garden, garage, heating, property condition, property type
     (bare ownership, usufruct…), energy class, keywords, exclude auctions,
     virtual tour — is applied by the portal, and the app monitors exactly that
     filtered result. There is no search you can run on the portal that the app
     cannot follow, because it reads the URL as-is.
   - *Note*: Both portals' search options (standard lists and custom polygon `/search-list/` maps) are fully supported.
   - *Note*: Both sale (vendita) and rental (affitto) searches are supported.
   - *Shortcut*: instead of visiting the portals, describe the search in plain
     Italian ("trilocale a Milano sotto i 300k, zona Navigli o Isola") and the
     assistant builds both portal URLs for you. It runs offline with no AI
     service involved, and zone names are a best guess — use the **"Open ↗"**
     link to check the result on the portal before saving the profile. The
     assistant and the **"Build a search"** form only cover the basics (city,
     price, rooms, surface); for any of the advanced filters above, set them on
     the portal and paste the URL.
2. **Add Profile**: In the dashboard, click **"+ Add search profile"**, give it a name, paste the URL, and click **"Save profile"**.
3. **Start Scanning**: Click **"Start Scan Now"** (or let the automatic scheduler scan in the background).
4. **Browse Listings**: Merged listings will show a purple badge (e.g., *"2 merged listings"*), showing that duplicates across different portals or agencies have been successfully grouped together.
5. **Curation (Hide & Discard)**:
   - If you see a listing you do not want to track, click on the card to open its modal, then click **`Hide property`**.
   - Hidden listings are permanently excluded from searches and notifications. If you want to review or retrieve them, select the **`Discarded`** option in the **Status** filter at the top of the dashboard. Inside the detail modal of a discarded property, you can click **`Restore property`** to move it back to active status.

---

## Beyond the Listing Grid

* **Map view**: the same properties as pins on an OpenStreetMap background —
  useful to see how a shortlist is spread across the city. Clicking a pin opens
  the property.
* **Is this price fair?**: each card compares its €/sqm against the median of
  comparable properties in the same zone (falling back to the whole city), so an
  overpriced listing stands out. It needs at least 3 comparables to say anything,
  and sale and rental prices are never mixed — until your database has enough
  history, cards simply show nothing rather than a number invented from two
  samples.
* **Deal Score**: builds on the fairness check to flag genuine opportunities. It
  combines the €/sqm gap to the local median with condition cues read from the
  listing text (*da ristrutturare* lowers it, *ristrutturato / classe A* raises
  it) into a single score — positive means priced below the market. An
  undervalued listing shows a **🎯 below market** badge, and its detail modal
  adds a suggested proposal range drawn from the agency's own usual discount. If
  Telegram or email alerts are on, an undervalued new listing carries the flag
  into the notification. It is a starting point for your judgement, not an
  appraisal, and appears only where there are enough comparables to mean it.
* **Smart Match Score**: define your "dream home" once in **Settings** — a budget,
  minimum rooms, surface or floor, must-have features (e.g. *balcone, ascensore*),
  and preferred zones — and every card shows a **compatibility %** scored against
  it. Only the wishes you fill in count, numbers you leave at 0 are ignored, and
  the scoring is entirely local. Sort the grid by **🎯 Best match** to bring your
  closest fits to the top.
* **Price trends**: a chart of how the median €/sqm has moved over time in each
  area you track. The app records one median per area per day, so the line starts
  after a couple of days of scans and grows more useful the longer it runs. It
  reflects *your* sample — the listings this app was watching each day — not the
  whole market, which the panel states plainly.
* **Market velocity**: how long listings survive before disappearing, broken down
  by zone and agency. It is built from properties that have actually vanished, so
  it becomes meaningful after a few months of scanning.
* **Mortgage calculator**: inside a property's detail modal, estimate the monthly
  payment (French amortization) for a given down payment, rate, and term.
* **Share a shortlist**: the **Export** buttons on the filter bar download the
  properties currently on screen — apply the filters or tick *Favorites* first —
  as a self-contained **HTML dossier**, a clean **Markdown** report, or a **CSV**
  spreadsheet. Each includes prices, price-drop history, and the Deal/Match
  scores. It is a single offline file you can send to a partner, family member,
  or agent over chat or email, without giving anyone access to your dashboard or
  database. (The HTML dossier's thumbnails load from the portals, so those need
  a connection; everything else works fully offline.)
* **Email inbox import**: if the portals already mail you their alerts, point the
  app at your mailbox (IMAP) and it collects the listing links from those emails.
  Your mailbox is opened **strictly read-only** — nothing is deleted, and messages
  are not even marked as read. Imported listings are staged in a review list and
  enter the dashboard only when you accept them, going through the same
  deduplication as a normal scan. A scan of a large mailbox takes minutes, and a
  progress bar reports how many emails it has read so far. Once the first import
  is done, tick **"Re-scan the inbox automatically"** in **Settings** to have the
  app pick up newly arrived alert emails on a schedule (every few hours up to
  once a week). New listings are added to the review list silently — you are not
  notified and nothing enters the dashboard until you accept it, exactly like a
  manual scan.

  Review cards show only what the email itself contained: price, surface, rooms,
  the €/m² derived from them, and the alert's subject line (usually the name of
  the saved search, the one hint of *where* the property is). The panel never
  opens the ad pages — mass-visiting hundreds of old listings would be slow and
  a good way to get blocked — so anything else means clicking **Open ↗**. Sort by
  €/m² to rank them by value rather than by sticker price.

  Alert emails also link each ad several times: from its photo, from a "see the
  listing" button, and from the footer's *"if the link does not work, copy this
  address"*. Links the email describes with nothing at all are skipped rather
  than staged, since there would be nothing to review them by.

  Emails are often months old, so many of those ads are already sold. Select the
  ones you care about and press **Check if still online**: the app opens each
  ad page once and marks the removed ones, which you can then discard in one go.
  If the portal refuses to answer (a block, a timeout), the listing is left
  exactly as it was — a listing wrongly reported as gone would be discarded
  forever, so silence never counts as proof. Listings the dashboard already
  tracks as live are resolved from the local database without contacting the
  portal at all, and already-checked listings are skipped when checking in bulk
  (re-select a single one to force a fresh check). If the portal blocks the
  check anyway, you can paste the `datadome` cookie from your real browser into
  the field next to the button (it is stored with the other settings), or route
  the app's traffic through a proxy configured in **Settings**.

  The check is deliberately slow: it visits the portal's homepage first (as a
  browser would), then one ad page every 6–8 seconds, at most 50 per click. Same
  pace as a normal scan, and one tenth of its volume. If the portal starts
  refusing anyway, the check **stops after three refusals in a row** and says so:
  insisting would only deepen the block, and the block would land on the same
  home connection your scheduled scans need. In that case, wait and retry later.

  **Only ads hosted on Immobiliare.it or Idealista.it can be imported**, since
  the app identifies a listing by its portal ID. An agency that mails you its
  own proposals (Tecnocasa, a local agency, …) is imported only if the email
  links a portal ad; if it links the agency's own website, searching for that
  sender finds the email and imports nothing from it.

  The two buttons are not symmetric, so when in doubt accept: an accepted listing
  becomes a normal property you can still hide, while a discard is remembered
  forever — that memory is what stops a re-scan from resurfacing it.

---

## Background Operations & Caching
* **Data Persistence**: All settings, search profiles, listings, price history, and hidden statuses are saved locally in a database file (`backend/case.db`). You can close the app or shut down your PC at any time without losing any progress or history.
* **Always-on Scanning**: background scans, price-trend snapshots, and alerts run only while the app is running. With `start.bat`/`serve.bat` that means keeping the terminal window open (minimized). To run it silently with no window — the closest thing to a Raspberry Pi on a Windows PC — see *Running it 24/7 on Windows* below.
* **Catch-up Scan**: the scheduled scan normally fires one full interval after startup. If the PC was off and the last scan is already older than the configured interval, a catch-up scan runs ~2 minutes after startup instead — so switching the PC on is enough to bring the listings up to date.
* **Automatic Backups**: a copy of `case.db` is written to `backend/backups/` at most once per day (checked at startup; the 14 most recent copies are kept). The folder is local — point your cloud-sync or a second drive at it if you want off-machine safety.

### Running it 24/7 on Windows (no window to keep open)

Don't have a Raspberry Pi yet? You can make the app run in the background on
Windows, with no console window. Whichever option you pick, **build the
dashboard once first** so the backend serves it on a single port — run
`serve.bat` once (Ctrl+C after "Building the frontend"), or `cd frontend && npm
run build`. Then open **http://localhost:8000** and bookmark it. Everything
stays on `127.0.0.1` — the API has no password, so it must not be exposed.

Three options, from simplest to most robust:

| Option | What it does | Trade-off |
|---|---|---|
| **A — Start at login (hidden)** | A shortcut to `run-hidden.vbs` in your Startup folder launches the backend, hidden, every time you log in. | Simplest. Runs only after you log in; no auto-restart if it crashes. |
| **B — Task Scheduler (hidden)** | A scheduled task runs `run-hidden.vbs` "At log on", with more control (delay, run even on battery, etc.). | Still tied to login, but more configurable than A. |
| **C — Windows Service (NSSM)** ⭐ | `install-service.bat` registers the backend as a real service: starts at **boot** (before login), **auto-restarts on crash**, logs to `backend/service.log`. | The closest to an always-on appliance. One-time setup, needs a small download. |

**Option A — Start at login.** Press `Win+R`, type `shell:startup`, Enter. In
the folder that opens, right-click → *New → Shortcut*, and point it at
`run-hidden.vbs` in the project folder. Done — it launches silently at every
login. (To stop it, delete the shortcut and end `pythonw.exe` in Task Manager.)

**Option B — Task Scheduler.** Open *Task Scheduler* → *Create Task* → trigger
*At log on*, action *Start a program* → `wscript.exe` with argument the full path
to `run-hidden.vbs`. This gives you options A doesn't (delay after login, "run
whether logged on or not", stop if idle, …).

**Option C — Windows Service (recommended).**
1. Download **NSSM** from <https://nssm.cc/download>, and copy `win64\nssm.exe`
   into the project folder (next to `install-service.bat`).
2. Right-click **`install-service.bat`** → *Run as administrator*. It builds the
   frontend if needed, registers the `RealEstateSearch` service (auto-start,
   auto-restart), and starts it.
3. Open **http://localhost:8000**.

Manage it from an admin terminal: `nssm restart RealEstateSearch` (after
updating the code), `nssm stop RealEstateSearch`, `nssm edit RealEstateSearch`
(GUI). To remove it, run **`uninstall-service.bat`** as administrator — your
database and settings are left untouched.

> Notes for all three: don't run `start.bat` at the same time (both use port
> 8000 — stop the autostart first). After changing the code, rebuild the
> frontend and restart. The optional browser-based DataDome cookie grab is
> interactive, so it won't work headless from a service — paste the cookie by
> hand instead; normal scans are unaffected.

---

## Notifications

Both channels are configured in **Settings**, with a collapsible step-by-step
guide next to each one:

- **Telegram**: create a bot via **@BotFather**, get your Chat ID via
  **@userinfobot**, paste both, enable, and send a test message.
- **Email**: SMTP settings, enable, and send a test message.

Each test button saves the form before testing, so it always exercises the
values you just typed.

Each search profile can route its own alerts to Telegram only, Email only, or
both.

### Gmail: use an app password

Gmail rejects your normal password; both the email alerts and the inbox import
need a 16-character **app password** (`smtp.gmail.com:587`, `imap.gmail.com:993`,
username = your Gmail address). Google only offers app passwords once **2-Step
Verification is on** — until then
[the app passwords page](https://myaccount.google.com/apppasswords) answers *"the
setting you are looking for is not available for your account"*, which is
Google's way of saying "enable 2FA first", not a sign of a problem with this app.
Paste the password as Google shows it: the spaces are stripped on save.

### Scraper health alerts

A broken scraper is silent: it collects no listings, which looks exactly like a
quiet market. When a search profile fails several scans in a row (the portal
blocks the scraper, or its HTML changes), you get an alert on the profile's own
channels, and a matching message once it recovers.

The threshold lives in **Settings → Scraper health alerts** (default: 3
consecutive failures; set it to *Never* to disable). Alerting on a *streak*
rather than a single failure is deliberate — portals hand out occasional
anti-bot blocks that clear by themselves, and an alert that cries wolf gets
ignored. The dashboard also shows the current streak next to a failing
profile's status badge (e.g. `Blocked ×4`).

---

## Notes on First Scan

The **first** scan of any search profile retrieves all existing listings and saves them to build the baseline database. **No notifications are sent during the first scan** to avoid flooding your Telegram account. You will only receive alerts for new listings and price drops starting from the **second** scan onward.

---

## Keeping scans unblocked (DataDome)

Both portals sit behind **DataDome**, an anti-bot system that occasionally
answers a scan with a block instead of listings. This is expected, not a bug:
a blocked profile shows `Blocked (will retry)` and is retried on the next scan,
and you are alerted only if it fails several scans in a row (see *Scraper health
alerts*). The single most effective way to prevent blocks is to hand the scraper
a **`datadome` cookie** earned by a real browser on your own connection.

You can provide that cookie in three ways, from most to least automatic:

* **Automatic (recommended)** — in **Settings → Advanced Scraping**, press
  **"Grab a fresh cookie now"**. The app opens a local browser, earns the
  cookie, and saves it for you — no copy/paste. A window may briefly appear; if
  the portal shows a CAPTCHA, solve it once and it is remembered for next time.
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
* **Proxy** — as a last resort, route scraper traffic through a proxy
  (Settings → Proxy URL). Note a *datacenter* proxy is blocked harder than your
  home IP; only a residential proxy helps.

Nothing here is required for the app to work — a home connection is trusted by
DataDome most of the time on its own. These are the levers for when it isn't.

## Technical Architecture

* **Backend**: Python 3.11+ / FastAPI / SQLite / APScheduler.
* **Resilient Scrapers**: Built on 4 fallback strategies (JSON-LD Schema → Embedded `__NEXT_DATA__` state → Heuristic class-free HTML parsing → Internal API fallback). 
* **Residential IP Scraping**: Designed to run locally or on home networks. Cloud server IPs are heavily blocked by DataDome, whereas your home internet IP is trusted, ensuring reliable scans.
* **Deduplication Engine**: Listings are merged only if they contain geographical proof (coordinates within 60 meters **OR** exact same street and house number) plus compatible price, rooms, floor, and square meters.
* **Frontend**: React / Vite / TypeScript / Tailwind CSS.

---

## Testing & Verification

Automated tests cover all parser strategies, price formatting edge cases, deduplication rules, price history changes, and scanner routines — all offline (no network calls), so they always pass or fail for a real reason.

Run tests using the local Python virtual environment:
```bash
cd backend
& .venv/Scripts/python.exe -m pytest
```
*(All tests must pass before committing changes).*
