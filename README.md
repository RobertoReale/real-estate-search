# Real Estate Search

Local PC/Raspberry Pi platform that aggregates real estate listings (sale and rental) from **Immobiliare.it** and **Idealista**, deduplicates multiple ads for the same property, filters out unwanted listings (e.g., bare ownership, ground floors, or court auctions), and sends real-time notifications on **Telegram and/or Email**.

---

## Why This Is Different

Real estate portals erase history and hide metrics to protect listing agencies. This platform stores everything in a local **SQLite database (`case.db`)**, acting as your personal **buyer decision engine and negotiation assistant**:

1. **Deal Radar & Congruity Engine (`Deal Score`):** Automatically compares every new listing against the localized €/sqm median of its specific micro-zone (`pricing_stats.py`). Combined with agency historical discounting behavior (`market_velocity.py`), it reveals undervalued opportunities within minutes of publication. [Import the Agenzia delle Entrate's OMI quotations](docs/using-the-app.md#refreshing-the-omi-benchmark) and each property also shows what the tax authority records **sales** at in its micro-zone — shown beside the listing median, never blended into it, because asking prices sit systematically above transacted ones, and flagged *out of date* once the imported semester falls behind.
2. **Ghost Price & Re-listing Memory (`Recycled Ad Tracker`):** When a house sits unsold for months at €420k, agencies often delete the ad and re-publish it weeks later as "New" at €389k with different photos. Our cross-portal deduplicator matches coordinates and sqm across old `gone` listings to alert you: `[RECYCLED PROPERTY] previously listed for 160 days at higher price (-9.5%)`.
3. **Red Flags Audit & Real TCO Calculator:** Extracts structural and legal red flags directly from ad text (e.g., active tenant lease, bare ownership, high condo fees > €250/mo, no elevator) and calculates your realistic monthly Total Cost of Ownership (Mortgage + Condo Fees + Renovation buffer).
4. **Zero Cloud, 100% Local Privacy:** Runs locally on your own PC or Raspberry Pi. No paid APIs, no subscriptions, no tracking.

---

## Quick Start

### Prerequisites

**Python 3.11 – 3.14**, and **Node.js 18+** to build the dashboard. The start
scripts check the Python version before creating the virtual environment and
stop with an explanation if it is out of range, rather than failing partway
through installing dependencies.

Node is only needed when there is something to build. `start.bat` compiles the
dashboard the first time and after any change to its sources, then serves the
compiled result — so running the app afterwards needs Python alone.

**3.12 is the recommended version**: it is the one with the widest wheel
availability for this dependency set, so nothing needs a compiler to install.
3.11 is the declared floor (`requires-python` in `backend/pyproject.toml`) and
the version the dependency locks are resolved against; the suite is also run on
3.14.

### Windows
Double-click on **`scripts\windows\start.bat`**:
- Installs all dependencies on first run.
- Builds the dashboard when it is missing or older than the code, then serves it and the API together on **http://localhost:8000**. One window, one port — close it to stop the app.
- Automatically opens the web interface in your default browser, once the server actually answers.
- If a setup step fails — no internet while installing, an unsupported Python — it stops there, says what went wrong and what to do about it, and starts nothing. The window stays open so you can read it.

Working on the code instead of using the app? **`scripts\windows\dev.bat`** is the
development flow: two windows, the backend on :8000 with auto-reload and Vite on
:5173 with hot module reload, so an edit is on screen before the editor loses
focus.

All Windows-only helpers (service install/uninstall, restart, stop, hidden
autostart) live in `scripts\windows\` — see [Remote Access & Running in the
Background](docs/remote-access.md).

### Windows, without installing anything
If you would rather not install Python and Node at all, use the packaged app:
download the `-windows-x64.zip` from the [Releases page](../../releases), unpack
it anywhere, and double-click **`RealEstateSearch.exe`**. It runs
in the notification area — right-click the icon for **Open dashboard**, **Open
data folder** and **Quit** — with no terminal window to keep open.

Your data does *not* live next to the program. It goes in
`%LOCALAPPDATA%\RealEstateSearch\` (the **Open data folder** menu item goes
straight there), because a program installed under `C:\Program Files` cannot
write to its own folder. **Moving an existing database across:** put your old
`case.db` — and `settings.json`, if you want your Telegram token and DataDome
cookie to come with it — in the same folder as `RealEstateSearch.exe` before
the first launch. It is copied into the data folder on startup, price history
included. Set `APP_DATA_DIR` if you want to choose the location yourself.

### Docker (NAS, Raspberry Pi)
```bash
docker compose -f packaging/docker-compose.yml up -d
```
Builds for x86-64 and ARM64 (a prebuilt image is published to `ghcr.io` with
each release), keeps `case.db` and `settings.json` on a volume
(`packaging/data/`), and restarts with the machine. The port is published to
**loopback only** — the API is unauthenticated by default (see
[Remote Access](docs/remote-access.md) before widening it).

### Linux / Raspberry Pi (from source)
Open a terminal inside the project directory and run:
```bash
chmod +x scripts/linux/start.sh
./scripts/linux/start.sh
```
- Installs dependencies and starts both services concurrently.
- Makes the dashboard accessible from any device on your local network at `http://<IP_OF_YOUR_PI>:5173`.
- Stops with an explanation if a setup step fails, exactly like the Windows script. It can be run from anywhere — it resolves the project directory from its own location.

---

## Access from Your Phone

The scraper stays on the PC — portals trust residential IPs and block cloud ones
— but the dashboard works from an Android or iOS browser, installable as an app
icon. Run **`scripts\windows\serve.bat`** instead of `start.bat`: it serves the
same single port (8000) but binds it to your Tailscale address instead of
loopback, so the phone can reach it and nothing else can. Reaching it from outside the house, the
security model of the open (unauthenticated) API, and the optional API token
are covered in [Remote Access & Running in the Background](docs/remote-access.md).

---

## How to Use

1. **Get the search URL** from Immobiliare.it or Idealista.it (or describe the
   search in plain Italian and let the built-in assistant build both URLs for
   you), and copy it from the address bar.
2. **Add Profile**: paste the URL into **"+ Add search profile"**, name it, save.
3. **Start Scanning**: click **"Start Scan Now"**, or let the scheduler run in
   the background.
4. **Browse Listings**: merged duplicates show a purple badge, and properties
   found since your last visit carry a **🆕 new** badge.
5. **Curate**: hide listings you don't want, mark ones as sold/rented, search
   and filter the grid, and clean up in bulk.

The full walkthrough — every portal filter, search-building shortcuts, the
search/filter bar, bulk cleanup, deleting a search (and what happens to the
listings it found), and silencing a search's notifications — is in
[Using the App](docs/using-the-app.md).

---

## Beyond the Listing Grid

The dashboard has a full toolbox beyond the grid itself: a bilingual interface,
a map view with drawable filter zones, price-fairness and Deal Score checks, a
Smart Match Score against your "dream home", commute times to the places you
actually travel to, an optional reading of a listing's own text (extra costs, a
sitting tenant, what is usable in a negotiation — off by default, and it can run
on a local model), price-trend and market-velocity
charts, a scraper-health panel, free-form tags, shortlist exports (HTML/MD/CSV,
plus a printable PDF report with a viewing checklist), and a mortgage calculator. See [Features](docs/features.md) for the full
rundown, and [Is This Ad Still Online?](docs/availability-check.md) for checking
a shortlist against the portals on demand.

---

## Background Operations & Caching
* **Data Persistence**: All settings, search profiles, listings, price history, and hidden statuses are saved locally in a database file. Running from source that is `backend/case.db`; in the packaged app it is `%LOCALAPPDATA%\RealEstateSearch\case.db`, and under Docker it is the `/data` volume — in every case outside the program's own folder, so updating or reinstalling never touches it. You can close the app or shut down your PC at any time without losing any progress or history.
* **Always-on Scanning**: background scans, price-trend snapshots, and alerts run only while the app is running. With `start.bat`/`serve.bat` that means keeping the terminal window open (minimized); the packaged app has no window to keep open — it sits in the notification area. To have it start at boot before you log in, see [Running it 24/7 on Windows](docs/remote-access.md#running-it-247-on-windows-no-window-to-keep-open).
* **Restart from the dashboard**: after updating the app, press **Settings → 🔄 Restart backend** instead of hunting for the terminal window. The dashboard goes offline for a few seconds and reloads itself. `start.bat` and `serve.bat` both serve a pre-built dashboard, so this applies a backend change — if the frontend itself changed, re-run the script and it rebuilds. With `dev.bat` the auto-reloader usually picks a code change up on its own.
* **Pause automatic scans**: **Settings → Automatic scan → Pause automatic scans** stops the scheduled scans from touching the portals — handy for resting the connection while you are away, without deactivating every search one by one. The top bar shows *⏸ Automatic scans paused* while it is on, and **Start Scan Now** still works on demand (an explicit request bypasses the pause). To silence a single search instead, untick it in the search list.
* **Catch-up Scan**: the scheduled scan normally fires one full interval after startup. If the PC was off and the last scan is already older than the configured interval, a catch-up scan runs ~2 minutes after startup instead — so switching the PC on is enough to bring the listings up to date.
* **Automatic Backups**: a copy of `case.db` is written to `backend/backups/` at most once per day (checked at startup; the 14 most recent copies are kept). The folder is local — point your cloud-sync or a second drive at it if you want off-machine safety. The copies are taken through SQLite's own backup API, so they are consistent even if a scan is writing at that moment. *If you ever copy the database by hand, take `case.db-wal` and `case.db-shm` with it*: the newest changes live in those two companion files until the database folds them in, and `case.db` on its own would be missing them.
* **Paged Loading**: the dashboard loads results a page at a time and fetches the next as you scroll, so a large collection opens quickly instead of downloading everything up front. The count beside the filters is always the full number of matches, and **Select all**, the map and the dossier export still work on the whole filtered set — not just the part on screen. While a scan is running the dashboard checks for changes with a lightweight request and only reloads the grid when something has actually changed.
* **In-App Log Viewer**: click **📜** in the top bar to see the backend's own log — scan progress, the availability check advancing line by line, DataDome blocks — without opening `backend/app.log` in a text editor. It filters by keyword and auto-refreshes every few seconds while open, so you can tell a slow-but-working check apart from a genuinely stuck one.
* **Data Management (start fresh)**: **Settings → Data management** has three irreversible resets, each behind a confirmation. *Clear dashboard* deletes all found properties and price history but keeps your search profiles — the next scan rebuilds the grid silently (no notification flood). *Clear price trends* drops only the trend-chart history. *Factory reset* wipes everything back to a fresh install (a backup of the database is saved first). Your notification and login settings are never touched.

---

## Notifications

Telegram and Email are both configured in **Settings**, with a step-by-step
guide next to each, and each search profile can route its own alerts to either
channel, both, or neither.

Telegram alerts about a property also carry **⭐ Favourite · 👁️ Seen · 🚫 Hide ·
🗺️ Map** buttons, so you can triage a listing from the phone and see the change
in the dashboard. They need no open port and no public address — the backend
collects the taps over its own outgoing connection.

See [Notifications](docs/notifications.md) for the setup details, the buttons,
using Gmail's app password, and scraper-health alerts.

---

## Notes on First Scan

The **first** scan of any search profile retrieves all existing listings and saves them to build the baseline database. **No notifications are sent during the first scan** to avoid flooding your Telegram account. You will only receive alerts for new listings and price drops starting from the **second** scan onward.

---

## Keeping Scans Unblocked (DataDome)

Both portals sit behind **DataDome**, an anti-bot system that occasionally
blocks a scan instead of returning listings — expected, not a bug: a blocked
profile is retried on the next scan, and you're alerted only after several
failures in a row. The most effective fix is handing the scraper a real
browser's `datadome` cookie, which the app can grab for you automatically; a
proxy pool or a paid scraping API are further options for a stubborn block. For
Idealista there is also an **official API** — if you are granted a key, searches
on that portal ask the portal for its own data instead of reading its pages, so
there is nothing left to block (searches it cannot express exactly keep using
the scraper). See [Keeping Scans Unblocked](docs/datadome.md) for all the
levers, from most to least automatic, for what the portals actually fingerprint,
and for how to tell a stale TLS profile from an address that has gone bad.

## Technical Architecture

* **Backend**: Python 3.11–3.14 / FastAPI / SQLite / APScheduler.
* **Resilient Scrapers**: Built on 4 fallback strategies (JSON-LD Schema → Embedded `__NEXT_DATA__` state → Heuristic class-free HTML parsing → Internal API fallback). 
* **Residential IP Scraping**: Designed to run locally or on home networks. Cloud server IPs are heavily blocked by DataDome, whereas your home internet IP is trusted, ensuring reliable scans.
* **Deduplication Engine**: Listings are merged only if they contain geographical proof (coordinates within 60 meters **OR** exact same street and house number) plus compatible price, rooms, floor, and square meters.
* **Frontend**: React / Vite / TypeScript / Tailwind CSS, bilingual (English /
  Italian) through a small dependency-free dictionary — no i18n library, and a
  key present in one language but missing in the other fails the build.

### Documentation for contributors

If you are changing the code rather than using the app, five documents carry
everything that is not obvious from reading it:

* **[Architecture](docs/architecture.md)** — where to act for each kind of change,
  the data schema, the property lifecycle, the migration strategy, and the known
  fragilities with the symptom each one produces.
* **[Invariants](docs/invariants.md)** — twenty-two rules that must not break, each
  with the regression that put it there. Read the relevant one *before* editing,
  not after.
* **[Conventions](docs/conventions.md)** — how code is written and tested here.
* **[Development cycle](docs/development-cycle.md)** — how a change gets made: the
  unit of work, the gates that run before every commit, when new behaviour earns
  an invariant, and how a release is cut from a tag.
* **[Audit playbook](docs/audit.md)** — the repeatable full-project health check:
  the green baseline, the module review order, the invariant→test cross-check.

---

## Testing & Verification

Automated tests cover all parser strategies, price formatting edge cases, deduplication rules, price history changes, and scanner routines — all offline (no network calls), so they always pass or fail for a real reason. The frontend has its own unit tests for the pure logic (filter querystring codec, floor labels, the English/Italian dictionaries — key and placeholder parity — and the settings dialog's save, so a field cannot quietly stop persisting).

Run the backend tests using the local Python virtual environment:
```bash
cd backend
& .venv/Scripts/python.exe -m pytest
```

Run the frontend tests:
```bash
cd frontend
npm test
```
*(All tests must pass before committing changes).*

### Dependency locking

`backend/requirements.txt`, `requirements-dev.txt` and `requirements-package.txt`
are **generated** lockfiles: every package pinned to the exact version, with
hashes, so the same checkout installs the same application on any machine and at
any point in the future. Edit the `.in` file beside them and recompile with
[uv](https://docs.astral.sh/uv/):

```bash
cd backend
uv pip compile requirements.in --universal --python-version 3.11 --generate-hashes -o requirements.txt
uv pip compile requirements-dev.in --universal --python-version 3.11 --generate-hashes -o requirements-dev.txt
uv pip compile requirements-package.in --universal --python-version 3.11 --generate-hashes -o requirements-package.txt
```

Recompile **all three** after touching `requirements.in`: the other two `.in`
files start with `-r requirements.in`, so a runtime pin that moves in one and not
the others leaves the packaged Windows build installing a different version from
the one the gates ran against.

The frontend is locked the same way by `frontend/package-lock.json`. Install it
with **`npm ci`, never `npm install`**: `ci` installs exactly what the lock pins
and fails loudly if the lock and `package.json` disagree, where `install`
quietly rewrites the lock and gives that machine a different toolchain. The
start scripts and CI both use `npm ci`, so the only time `npm install` is right
is when you are deliberately adding or upgrading a dependency — and then the
rewritten lock is part of the change and gets committed with it.

```bash
cd frontend
npm ci
```

Regenerating that lock is the one step with a trap in it: delete `node_modules`
**and** `package-lock.json`, then run a plain `npm install`. Never
`npm install --package-lock-only` — with no materialised tree npm resolves a
thinner one and writes a lock that `npm ci` afterwards rejects as out of sync,
and the failure names a transitive package nothing depends on directly
(`@emnapi/core`, reached through Tailwind's optional wasm fallback), so it reads
like a registry outage rather than a malformed lock. For the same reason CI pins
the same Node major as the development machine: npm 10 and npm 11 disagree about
what a valid lock is, and one written by the other fails `npm ci` on a checkout
that is otherwise perfectly fine.

Neither lock has to be watched by hand: `.github/dependabot.yml` opens one
grouped pull request per ecosystem per month. The frontend one is ordinary — it
carries the `package-lock.json` rewrite with it, so merge it once CI is green.
The backend one is a **notice, not a diff**: it edits a generated lock without
touching the `.in` file the lock is compiled from. Take the version it names,
move the pin in the `.in`, recompile all three as above, and push that over the
branch.

### Optional developer tooling

Beyond the runtime dependencies, an optional dev toolchain (linting, coverage,
property-based tests, dependency CVE scanning, and a pre-commit hook) lives in
`backend/requirements-dev.txt`. It is **never** installed on the target device —
only in a development checkout (it includes the runtime set, so it is the only
file a developer needs to install):
```bash
cd backend
& .venv/Scripts/python.exe -m pip install -r requirements-dev.txt
& .venv/Scripts/ruff.exe check app tests      # lint
& .venv/Scripts/ruff.exe format app tests     # format
& .venv/Scripts/python.exe -m pip_audit -r requirements.txt   # CVE scan
```
