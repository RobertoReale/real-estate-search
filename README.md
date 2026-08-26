# Real Estate Search

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

### Prerequisites

**Python 3.11 – 3.14**, and **Node.js 18+**. The start scripts check the Python
version before creating the virtual environment and stop with an explanation if
it is out of range, rather than failing partway through installing dependencies.

**3.12 is the recommended version**: it is the one with the widest wheel
availability for this dependency set, so nothing needs a compiler to install.
3.11 is the declared floor (`requires-python` in `backend/pyproject.toml`) and
the version the dependency locks are resolved against; the suite is also run on
3.14.

### Windows
Double-click on **`scripts\windows\start.bat`**:
- Installs all dependencies on first run.
- Starts the backend server (http://localhost:8000) and the frontend dashboard (http://localhost:5173).
- Automatically opens the web interface in your default browser.

All Windows-only helpers (service install/uninstall, restart, stop, hidden
autostart) live in `scripts\windows\` — see [Remote Access & Running in the
Background](docs/remote-access.md).

### Linux / Raspberry Pi
Open a terminal inside the project directory and run:
```bash
chmod +x scripts/linux/start.sh
./scripts/linux/start.sh
```
- Installs dependencies and starts both services concurrently.
- Makes the dashboard accessible from any device on your local network at `http://<IP_OF_YOUR_PI>:5173`.

---

## Access from Your Phone

The scraper stays on the PC — portals trust residential IPs and block cloud ones
— but the dashboard works from an Android or iOS browser, installable as an app
icon. Run **`scripts\windows\serve.bat`** instead of `start.bat`: it builds the
frontend and serves the dashboard and API from a single port (8000), so there
is nothing to configure on the phone. Reaching it from outside the house, the
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
Smart Match Score against your "dream home", price-trend and market-velocity
charts, a scraper-health panel, free-form tags, shortlist exports (HTML/MD/CSV),
and a mortgage calculator. See [Features](docs/features.md) for the full
rundown, and [Is This Ad Still Online?](docs/availability-check.md) for checking
a shortlist against the portals on demand.

---

## Background Operations & Caching
* **Data Persistence**: All settings, search profiles, listings, price history, and hidden statuses are saved locally in a database file (`backend/case.db`). You can close the app or shut down your PC at any time without losing any progress or history.
* **Always-on Scanning**: background scans, price-trend snapshots, and alerts run only while the app is running. With `start.bat`/`serve.bat` that means keeping the terminal window open (minimized). To run it silently with no window, see [Running it 24/7 on Windows](docs/remote-access.md#running-it-247-on-windows-no-window-to-keep-open).
* **Restart from the dashboard**: after updating the app, press **Settings → 🔄 Restart backend** instead of hunting for the terminal window. The dashboard goes offline for a few seconds and reloads itself. With `start.bat` (which runs with auto-reload) a code update is usually picked up on its own; with `serve.bat` this button is the quick way to apply one. *(It restarts the backend only — with `serve.bat`, which serves a pre-built frontend, re-run the script if the frontend itself changed.)*
* **Pause automatic scans**: **Settings → Automatic scan → Pause automatic scans** stops the scheduled scans from touching the portals — handy for resting the connection while you are away, without deactivating every search one by one. The top bar shows *⏸ Automatic scans paused* while it is on, and **Start Scan Now** still works on demand (an explicit request bypasses the pause). To silence a single search instead, untick it in the search list.
* **Catch-up Scan**: the scheduled scan normally fires one full interval after startup. If the PC was off and the last scan is already older than the configured interval, a catch-up scan runs ~2 minutes after startup instead — so switching the PC on is enough to bring the listings up to date.
* **Automatic Backups**: a copy of `case.db` is written to `backend/backups/` at most once per day (checked at startup; the 14 most recent copies are kept). The folder is local — point your cloud-sync or a second drive at it if you want off-machine safety. The copies are taken through SQLite's own backup API, so they are consistent even if a scan is writing at that moment. *If you ever copy the database by hand, take `case.db-wal` and `case.db-shm` with it*: the newest changes live in those two companion files until the database folds them in, and `case.db` on its own would be missing them.
* **In-App Log Viewer**: click **📜** in the top bar to see the backend's own log — scan progress, the availability check advancing line by line, DataDome blocks — without opening `backend/app.log` in a text editor. It filters by keyword and auto-refreshes every few seconds while open, so you can tell a slow-but-working check apart from a genuinely stuck one.
* **Data Management (start fresh)**: **Settings → Data management** has three irreversible resets, each behind a confirmation. *Clear dashboard* deletes all found properties and price history but keeps your search profiles — the next scan rebuilds the grid silently (no notification flood). *Clear price trends* drops only the trend-chart history. *Factory reset* wipes everything back to a fresh install (a backup of the database is saved first). Your notification and login settings are never touched.

---

## Notifications

Telegram and Email are both configured in **Settings**, with a step-by-step
guide next to each, and each search profile can route its own alerts to either
channel, both, or neither. See [Notifications](docs/notifications.md) for the
setup details, using Gmail's app password, and scraper-health alerts.

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
proxy pool or a paid scraping API are further options for a stubborn block. See
[Keeping Scans Unblocked](docs/datadome.md) for all the levers, from most to
least automatic.

## Technical Architecture

* **Backend**: Python 3.11–3.14 / FastAPI / SQLite / APScheduler.
* **Resilient Scrapers**: Built on 4 fallback strategies (JSON-LD Schema → Embedded `__NEXT_DATA__` state → Heuristic class-free HTML parsing → Internal API fallback). 
* **Residential IP Scraping**: Designed to run locally or on home networks. Cloud server IPs are heavily blocked by DataDome, whereas your home internet IP is trusted, ensuring reliable scans.
* **Deduplication Engine**: Listings are merged only if they contain geographical proof (coordinates within 60 meters **OR** exact same street and house number) plus compatible price, rooms, floor, and square meters.
* **Frontend**: React / Vite / TypeScript / Tailwind CSS, bilingual (English /
  Italian) through a small dependency-free dictionary — no i18n library, and a
  key present in one language but missing in the other fails the build.

---

## Testing & Verification

Automated tests cover all parser strategies, price formatting edge cases, deduplication rules, price history changes, and scanner routines — all offline (no network calls), so they always pass or fail for a real reason. The frontend has its own unit tests for the pure logic (filter querystring codec, floor labels, and the English/Italian dictionaries — key and placeholder parity).

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

`backend/requirements.txt` and `requirements-dev.txt` are **generated**
lockfiles: every package pinned to the exact version, with hashes, so the same
checkout installs the same application on any machine and at any point in the
future. Edit the `.in` file beside them and recompile with
[uv](https://docs.astral.sh/uv/):

```bash
cd backend
uv pip compile requirements.in --universal --python-version 3.11 --generate-hashes -o requirements.txt
uv pip compile requirements-dev.in --universal --python-version 3.11 --generate-hashes -o requirements-dev.txt
```

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
