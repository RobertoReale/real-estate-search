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

### Windows
Double-click on **`scripts\windows\start.bat`**:
- Installs all dependencies on first run (requires Python 3.11+ and Node.js 18+).
- Starts the backend server (http://localhost:8000) and the frontend dashboard (http://localhost:5173).
- Automatically opens the web interface in your default browser.

All Windows-only helpers (service install/uninstall, restart, stop, hidden
autostart) live in `scripts\windows\` — see *Running it 24/7 on Windows* below.

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
(see *Technical Architecture*) — but the dashboard can be used from an Android
or iOS browser, and installed as an app icon.

Run **`scripts\windows\serve.bat`** instead of `start.bat`. It builds the frontend and serves the
dashboard *and* the API from a single port (8000), so there is nothing to
configure on the phone: open the URL the script prints, then use the browser's
**"Add to home screen"** to get a standalone app icon.

The layout adapts to the screen: filter bars and forms fold into two columns,
the property grid becomes a single column, and buttons grow to a thumb-sized
target. Wide tables (market velocity) scroll sideways on their own rather than
stretching the page.

**Reaching the PC from outside the house**: install [Tailscale](https://tailscale.com)
on both the PC and the phone and log into the same account. It is free, needs no
port forwarding, and no public IP. `serve.bat` (in `scripts\windows\`) detects the Tailscale address
automatically and binds only to it, so the dashboard is reachable from your own
devices anywhere and from nothing else.

> Note: **By default the API has no password**, so the address is the access
> control:
> - *(default)* Tailscale address — only your own logged-in devices.
> - `scripts\windows\serve.bat lan` — **every device on your Wi-Fi**, guests included. Convenient
>   at home, but do not use it on a network you do not control.
> - Never forward port 8000 on your router.
>
> If you want a wider bind to be safe, set an **API token** (Settings → *API
> access token*). With one set, every device is asked for it once before it can
> see anything; your own browser stays logged in. Empty = the open,
> address-only behavior above.

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
     service involved. Zone names are still a best guess on Immobiliare, so use
     the **"Open ↗"** link to check the result before saving the profile.
   - *Optional AI parser*: if the built-in parser trips on unusual phrasing, you
     can point it at a language model instead (Settings → *Search assistant
     backend* → LLM). It understands freer wording and produces the same result;
     on any hiccup it falls back to the offline parser. Use a **local Ollama**
     model to keep this free and fully offline (nothing leaves your PC), or a
     cloud API key. Off by default.
   - *Note on Idealista zones*: pressing **"Generate search URLs"** asks
     Idealista once whether it knows the zone you typed. It has a page for some
     zone names (Forlanini) but not others (Bovisa, Udine/Lambrate), and there
     is no way to tell offline. When it does, you get that exact zone page; when
     it does not, the search falls back to matching the zone's *name as text*,
     which also returns listings outside the zone that merely mention it. The
     form tells you which of the two you got. If Idealista is blocking or
     unreachable at that moment, it uses the text search — a check that fails
     costs precision, never a working search.
   - The **"Build a search"** form covers city, price, rooms, surface, plus
     balcony, garden, garage, lift, swimming pool, excluding auctions, floor
     band (ground / middle / top) and condition (new / good / excellent / needs
     renovation) — all applied on **both** portals. Two exceptions, and the form
     names them when you pick one, because the Idealista half of the pair is then
     the wider search: the *"Excellent / renovated"* condition, which only
     Immobiliare offers, and a **maximum of 5 or more rooms**, since Idealista's
     largest bucket is "5 or more" and cannot be capped (a maximum of 4 or fewer
     is exact on both). For anything beyond this
     (hand-drawn map polygons, multi-zone selections, bathrooms, heating,
     energy class), set it on the portal and paste the URL.
2. **Add Profile**: In the dashboard, click **"+ Add search profile"**, give it a name, paste the URL, and click **"Save profile"**. To change one later (name, URL, or excluded keywords), click the **✏️** icon next to it in the list. To remove one, click **🗑** — see *Deleting a search* below, since you get to decide what happens to the listings it found.
   - *No accidental duplicates*: a search that resolves to the same portal URL and the same excluded keywords as one you already monitor is refused (the comparison ignores irrelevant differences like trailing slashes, tracking parameters, or keyword order/case), so the same listings aren't scanned and notified twice. Any pre-existing duplicates are merged into the oldest copy at startup, preserving which searches found what.
   - Each search also shows the **excluded keywords** actually in effect for it — the global ones set in Settings plus its own extras — so what gets discarded is visible without opening a modal.
3. **Start Scanning**: Click **"Start Scan Now"** (or let the automatic scheduler scan in the background).
4. **Browse Listings**: Merged listings will show a purple badge (e.g., *"2 merged listings"*), showing that duplicates across different portals or agencies have been successfully grouped together. Properties that appeared since your last visit carry a **🆕 new** badge, so a scan's findings are obvious at a glance; it clears itself the next time you reload the dashboard on that device (it is remembered per-browser, like the theme and the optional auth token — the same device shows it once).
5. **Curation (Hide, Discard & Mark sold)**:
   - If you see a listing you do not want to track, click on the card to open its modal, then click **`Hide property`**.
   - Hidden listings are permanently excluded from searches and notifications. If you want to review or retrieve them, select the **`Discarded`** option in the **Status** filter at the top of the dashboard. Inside the detail modal of a discarded property, you can click **`Restore property`** to move it back to active status.
   - **Mark as sold**: agencies often keep an ad online for weeks after the deal
     closes — reusing the photo with a big *"VENDUTO"* / *"VENDUTO IN 30 GIORNI"*
     overlay as advertising. Since the ad is still live, no scan will ever remove
     it. Open the card and click **`🔑 Mark sold`** (for rentals, *Mark rented*)
     to take it out of your active lists. Unlike *Hide*, a sold property is
     **kept as a confirmed sale**: it feeds the **Market velocity** statistics
     with a real close date (a much stronger signal than the *gone* guess), and
     you can review these under the **`🔑 Sold`** option in the **Status** filter.
     Marked one by mistake? *Restore property* puts it right back.
   - **Search & filter the grid**: the **Search** bar at the top of the filter
     bar matches any word across a listing's zone, address, title, floor and ad
     text (type *San Siro* or *nuova costruzione* to isolate them; to search by
     floor type either the Italian *4 piano* or the English *floor 4*). Beyond
     the search box there are dedicated **City**, **Zone**, price, **Min/Max
     sqm**, **Rooms**, **Floor** (Ground / Low / Middle / High / Top) and
     **Origin** filters, plus a one-click **↺ Reset filters** to clear them all.
     A collapsible **⚙️ More filters** panel adds the rest: **Portal** (only
     ads on Immobiliare or only on Idealista), **Agency**, **Deal** quality
     (💎 undervalued / 👍 fair or better, from the Deal Score), a **€/sqm**
     range, and **Merged only** (cards the app grouped from the same home on
     several portals/agencies). A small badge shows how many of these are active
     while the panel is collapsed.
     *Origin* separates listings your
     monitored searches found (**🔎 Monitored search**) from ones you pulled in
     from your inbox (**✉️ Email import**) — an email-imported card also carries
     a small **✉️ email** badge. *Limit to a search* narrows the whole grid,
     imports included, down to what one of your saved monitored searches would
     keep: it applies that search's city, contract and excluded keywords, so the
     rules that keep your scans clean can prune old email imports too. (It is a
     filter, not a ranking — it shrinks the list, it does not reorder it.)
   - **Bulk cleanup**: click **`Selezione multipla annunci`**, tick the cards
     (or *Seleziona tutti*), and **hide**, **mark sold** or **star** the whole
     selection at once — the fast way to clear a batch (e.g. every *nuova
     costruzione*, or a whole cluster of *VENDUTO* re-posts) without opening
     cards one by one.
   - **Retroactively excluding a whole category** (e.g. you decide *seminterrato*
     should never show up again): adding the word to your excluded keywords in
     Settings only affects *future* scans, since keyword filtering runs once,
     when a listing is first found. To clear out what is already in the
     dashboard, add the word there **and** use the Search bar to find the
     matching cards (they match the same word in title/zone/address/text), then
     select and hide them in bulk. There is no "delete forever" for a single
     property on purpose: it always hides rather than erases the row, so a scan
     that finds the same ad again recognizes it and leaves it hidden instead of
     re-adding it as new (which would re-notify you). Hiding is not a
     compromise — hidden listings never come back on their own, and it is fully
     reversible from the **Discarded** status filter if you change your mind.

### Deleting a search: what happens to its listings

Clicking **🗑** on a monitored search asks whether its results should go with
it, and shows the numbers before you choose:

* **Keep the results** — the search stops running; every property it found stays
  in the dashboard, price history and all. They are simply no longer refreshed
  by that search (after 7 unseen days they turn *gone*, as usual).
* **Delete with N properties** — the properties that search alone produced are
  deleted from the database. This is irreversible (unlike *Hide*, which is not),
  and it is safe precisely because the search that would re-find them is going
  away in the same breath.

Two kinds of listing are never deleted this way, and the dialog says how many it
is sparing:

* those **a search you are keeping also found** — that search still covers them;
* those you **starred or annotated** — hand-curated work a re-scan cannot rebuild.

A property counts as "found by this search" only if a scan actually recorded it
as such. Listings that predate this tracking (and that the search has not
re-found since) are not attributable to anyone, so they are left alone — a
search deleted before it has ever run therefore reports nothing to delete.

Deleting several searches at once (see below) asks the same question once for
the whole selection: a property found by two of the searches you are deleting is
not "covered by another search", so it *is* deleted.

### Acting on several searches at once

With more than one search in the list, each row gets a checkbox and a **Select
all** appears above them. Tick a few and a toolbar offers, for the whole
selection: **Activate**, **Pause**, a **Notifications →** menu, and **Delete**
(same dialog as above, with the totals for the selection). Handy for pausing
every search before a holiday, or silencing a noisy batch, without clicking
through them one at a time.

### Silencing one search

The **Notifications** menu on a search row (or on a selection) chooses where its
alerts go: *All channels*, *Telegram only*, *Email only*, or **🔕 No
notifications**. The last one keeps the search running — its listings keep
arriving in the dashboard — but you are never pinged for it: no new-listing
message, no price-drop message, not even the scraper-health alert. It is the
answer to "I want to watch this search, just not in real time"; *Pause*, by
contrast, stops scanning it altogether.

---

## Beyond the Listing Grid

* **Map view**: the same properties as pins on an OpenStreetMap background —
  useful to see how a shortlist is spread across the city. Clicking a pin opens
  the property. Many Immobiliare listings arrive without coordinates, so the map
  can look sparse; the **📍 Find coordinates** button (next to *Repair data*)
  looks up the missing pins from each listing's address or zone via OpenStreetMap
  (opt-in, cached, and it never invents a wrong pin — a lookup it cannot resolve
  is simply left off the map). It works in batches, so on a large dashboard press
  it again to continue. You can also jump to a single property: open its card and
  press **🗺️ View on map** — it opens the map centered on that pin, and if the
  property has no coordinates yet it finds them first (same OpenStreetMap lookup),
  telling you if the address was too vague to place. Failed lookups are
  remembered so the same address isn't asked twice, which means a temporary
  OpenStreetMap outage can leave a perfectly good address stuck as "not found";
  the **🧹 Retry failed lookups** button (next to *Find coordinates*) forgets
  those failed lookups so the next *Find coordinates* tries them again — it only
  clears the lookup memory and never moves a pin you already have.
* **Draw a zone on the map**: filter the whole dashboard by area directly on the
  map. Press **◯ Draw radius**, click a centre and drag the handle to size the
  circle; or **⬠ Draw area**, click each corner and double-click to close a free
  shape. Only the properties inside the zone stay — in the grid *and* in the
  exported dossier, since it is a filter like any other — and **✕ Clear zone**
  removes it. One caveat, shown as a banner while a zone is active: a property
  with no coordinates can't be placed on the map, so it is excluded from the
  zone; press **Find coordinates** from the banner to locate more of them first.
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
  whole market, which the panel states plainly. Under the chart, **🔍 Show the
  listings behind this median** reveals the exact properties that make up the
  area's current number — sorted by €/sqm, each showing how far it sits from the
  median, and clickable to open its full detail. These are the *current*
  comparables (the daily history keeps only each past point's count, not its
  listings), so it answers "which ads is today's number actually built from?".
* **Market velocity**: how long listings survive before disappearing, broken down
  by zone and agency. It is built from properties that have actually left the
  market, so it becomes meaningful after a few months of scanning. Listings you
  *Mark sold* count as **confirmed** sales here — a real close date rather than
  the "not seen for a while" guess — and the panel reports how many of the
  closes are confirmed.
* **Tags**: create your own free-form categories — "senza ascensore", "con
  giardino", "mi piace ma…" — and attach as many as you like to a property,
  right from its card or the detail modal. Typing a name that already exists
  reuses it instead of creating a near-duplicate. Filter the grid down to a
  single tag from the filter bar, same as filtering by city or zone.
* **Which search found it**: a property's detail modal shows **🔍 Found by** —
  the monitored searches that turned it up. Overlapping searches both appear, so
  you can tell at a glance whether a listing came from your "Milano trilocali" or
  your "Navigli" search (or both). A listing imported only from your inbox, never
  yet matched by a scan, says so instead.
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
  browser would), then one ad page every 6–8 seconds, at most 50 live page
  visits per click — selecting hundreds is fine, the already-verified ones skip
  for free, so pressing the button again continues where the last run stopped.
  Same pace as a normal scan, and one tenth of its volume. If the portal starts
  refusing anyway, the check **stops after three refusals in a row** and says so:
  insisting would only deepen the block, and the block would land on the same
  home connection your scheduled scans need. In that case, wait and retry later.
  You can also stop a run yourself at any time with the **⏹ Stop** button next to
  the progress bar — it finishes whatever listing is already in flight (there is
  no way to interrupt a live request mid-flight) and leaves the rest of the
  selection unchecked; re-select it later to pick up where you left off.

  If DataDome keeps interrupting the check, turn on **"Run the check through the
  browser"** in **Settings** (under the automatic cookie section). The check then
  runs through a real local browser (headless) that earns a genuine cookie once
  and reuses it, instead of a fresh request per ad — so it does not collect 403
  blocks. It is slower per listing, but it does not stop mid-run. This needs the
  optional browser engine installed (same one as the automatic cookie grab).

  If DataDome still challenges even that browser with a CAPTCHA, tick **"Show the
  browser window during the check"** right below it. Because you start the check
  yourself and watch it run, the browser opens **visible**: when a CAPTCHA
  appears, solve it once in the window and the run continues on its own — that
  single solve earns a real cookie the rest of the batch reuses, so you are not
  asked again. The window waits a few minutes for you; if you ignore it, the
  check falls back to stopping rather than hanging.

  **This option shows nothing when the app runs as the NSSM Windows service**
  (see *Running it 24/7 on Windows* below): a Windows service has no desktop of its own
  (Session 0), so there is no screen to open a window on, and the check just
  runs headless regardless of the tick box. If a run under the service gets
  blocked, don't wait on a window that will never appear — instead click
  **"Grab a fresh cookie now"** (same Settings page, under *Automatic cookie
  grab*) first. That button *does* pop a real, visible window even with the
  service running, because it specifically relaunches the browser inside your
  own logged-in desktop session rather than the service's; solve the CAPTCHA
  there once. It shares the same on-disk browser profile as the availability
  check, so the fresh, unblocked session it earns carries over to the next
  "Check online availability" run automatically — you don't need to run
  anything interactively for this to work.

  To be challenged less in the first place, switch the **Browser engine** (same
  Settings section) to **Camoufox** — a stealth Firefox that hides the automation
  signals DataDome looks for, so it is flagged far less often than plain
  Chromium. It is a one-click install (~150 MB, one time); leave the engine on
  **Auto** and it is used automatically once installed, falling back to Chromium
  if anything goes wrong. While a check runs, a **Transport** line under the
  progress bar tells you exactly what it is using — "camoufox (visible window)",
  "fast requests (curl)", or "browser off: no option enabled" — so you can see at
  a glance why a run behaved the way it did instead of guessing.

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
* **Restart from the dashboard**: after updating the app, press **Settings → 🔄 Restart backend** instead of hunting for the terminal window. The dashboard goes offline for a few seconds and reloads itself. With `start.bat` (which runs with auto-reload) a code update is usually picked up on its own; with `serve.bat` this button is the quick way to apply one. *(It restarts the backend only — with `serve.bat`, which serves a pre-built frontend, re-run the script if the frontend itself changed.)*
* **Pause automatic scans**: **Settings → Automatic scan → Pause automatic scans** stops the scheduled scans from touching the portals — handy for resting the connection while you are away, without deactivating every search one by one. The top bar shows *⏸ Automatic scans paused* while it is on, and **Start Scan Now** still works on demand (an explicit request bypasses the pause). To silence a single search instead, untick it in the search list.
* **Catch-up Scan**: the scheduled scan normally fires one full interval after startup. If the PC was off and the last scan is already older than the configured interval, a catch-up scan runs ~2 minutes after startup instead — so switching the PC on is enough to bring the listings up to date.
* **Automatic Backups**: a copy of `case.db` is written to `backend/backups/` at most once per day (checked at startup; the 14 most recent copies are kept). The folder is local — point your cloud-sync or a second drive at it if you want off-machine safety.
* **In-App Log Viewer**: click **📜** in the top bar to see the backend's own log — scan progress, the availability check advancing line by line, DataDome blocks — without opening `backend/app.log` in a text editor. It filters by keyword and auto-refreshes every few seconds while open, so you can tell a slow-but-working check apart from a genuinely stuck one.
* **Data Management (start fresh)**: **Settings → Data management** has four irreversible resets, each behind a confirmation. *Reset email imports* clears everything the inbox import staged, so you can import again from scratch. *Clear dashboard* deletes all found properties and price history but keeps your search profiles — the next scan rebuilds the grid silently (no notification flood). *Clear price trends* drops only the trend-chart history. *Factory reset* wipes everything back to a fresh install (a backup of the database is saved first). Your notification and login settings are never touched.

### Running it 24/7 on Windows (no window to keep open)

Don't have a Raspberry Pi yet? You can make the app run in the background on
Windows, with no console window. Whichever option you pick, **build the
dashboard once first** so the backend serves it on a single port — run
`scripts\windows\serve.bat` once (Ctrl+C after "Building the frontend"), or `cd frontend && npm
run build`. Then open **http://localhost:8000** and bookmark it. Everything
stays on `127.0.0.1` — the API has no password, so it must not be exposed.

All the scripts below live in **`scripts\windows\`**.

Three options, from simplest to most robust:

| Option | What it does | Trade-off |
|---|---|---|
| **A — Start at login (hidden)** | A shortcut to `run-hidden.vbs` in your Startup folder launches the backend, hidden, every time you log in. | Simplest. Runs only after you log in; no auto-restart if it crashes. |
| **B — Task Scheduler (hidden)** | A scheduled task runs `run-hidden.vbs` "At log on", with more control (delay, run even on battery, etc.). | Still tied to login, but more configurable than A. |
| **C — Windows Service (NSSM)** ⭐ | `install-service.bat` registers the backend as a real service: starts at **boot** (before login), **auto-restarts on crash**, logs to `backend/service.log`. | The closest to an always-on appliance. One-time setup, needs a small download. |

**Option A — Start at login.** Press `Win+R`, type `shell:startup`, Enter. In
the folder that opens, right-click → *New → Shortcut*, and point it at
`scripts\windows\run-hidden.vbs`. Done — it launches silently at every
login. (To stop it, delete the shortcut and end `pythonw.exe` in Task Manager.)

**Option B — Task Scheduler.** Open *Task Scheduler* → *Create Task* → trigger
*At log on*, action *Start a program* → `wscript.exe` with argument the full path
to `scripts\windows\run-hidden.vbs`. This gives you options A doesn't (delay after login, "run
whether logged on or not", stop if idle, …).

**Option C — Windows Service (recommended).**
1. Download **NSSM** from <https://nssm.cc/download>, and copy `win64\nssm.exe`
   into `scripts\windows\` (next to `install-service.bat`).
2. Right-click **`scripts\windows\install-service.bat`** → *Run as administrator*. It builds the
   frontend if needed, registers the `RealEstateSearch` service (auto-start,
   auto-restart), and starts it.
3. Open **http://localhost:8000**.

**Using Playwright / Automatic Cookie Grab with NSSM Service:**
When running as a Windows Service at boot (`LocalSystem` account), the service automatically searches for your installed Chromium binaries across user profiles (`C:\Users\<YourUser>\AppData\Local\ms-playwright`) and inside `backend/browser_binaries`.
If Playwright or Chromium is not yet installed:
* Open **http://localhost:8000** → **Settings** and click **⚡ One-Click Install Playwright & Chromium**, *OR*
* Double-click **`scripts\windows\install-playwright.bat`**. It installs Playwright into `backend\.venv`, downloads Chromium, and automatically restarts the `RealEstateSearch` service so it finds Chromium immediately upon boot.

Manage it from an admin terminal: `nssm restart RealEstateSearch` (after
updating the code), `nssm stop RealEstateSearch`, `nssm edit RealEstateSearch`
(GUI). To remove it, run **`uninstall-service.bat`** as administrator — your
database and settings are left untouched.

Double-click helpers for the same actions: **`restart-services.bat`** (restart
after updating the code) and **`stop-service.bat`** (stop it so you can run
`start.bat`/`serve.bat` normally — e.g. to solve a CAPTCHA by hand during the
availability check, since a service has no desktop to show that window on).
Both self-elevate via UAC. Remember to start the service again afterwards
(`restart-services.bat`, or `nssm start RealEstateSearch`).

> Notes for all three: don't run `start.bat` at the same time (both use port
> 8000 — stop the autostart first). After changing the code, rebuild the
> frontend and restart. The automatic DataDome cookie grab runs headless
> (`maybe_auto_refresh`) cleanly in the background right when needed. Any
> **interactive** browser step (solving a CAPTCHA by hand) still works under
> the service: **"Grab a fresh cookie now"** in Settings relaunches the browser
> inside your own desktop session instead of the service's invisible one, so a
> real window opens for you to solve it in. The availability check's own
> **"Show the browser window during the check"** option cannot do this — it
> runs the browser in the service itself, so under the service it is always
> headless no matter the setting (see the *Checking if listings are still
> online* section above for the workaround: run "Grab a fresh cookie now" first).

---

## Notifications

Both channels are configured in **Settings**, with a collapsible step-by-step
guide next to each one:

- **Telegram**: create a bot via **@BotFather**, get your Chat ID via
  **@userinfobot**, paste both, enable, and send a test message.
- **Email**: SMTP settings, enable, and send a test message.

Each test button saves the form before testing, so it always exercises the
values you just typed.

Each search profile can route its own alerts to Telegram only, Email only, both,
or nowhere at all (see *Silencing one search* above).

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
alerts*).

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
* **Proxy** — as a last resort, route scraper traffic through a proxy
  (Settings → Proxy URL). Note a *datacenter* proxy is blocked harder than your
  home IP; only a residential proxy helps.
* **Scraping API** — for the sturdiest option, paste a key from a DataDome-solving
  scraping API (Settings → Advanced Scraping → *Scraping API*: Scrapfly,
  ScraperAPI or Zyte). Instead of fetching pages from your own IP, each scan
  hands the target URL to the provider, which returns the already-solved HTML —
  so blocks stop reaching your connection entirely, and detail data (like map
  coordinates) becomes fetchable. This is the one place the app can use a paid
  cloud service, and it stays **optional**: free tiers (~1,000 calls/month) can
  cover a small personal scanner, and with no key set the app runs exactly as
  before, fully local. Empty the key to go back to the local path.

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

Automated tests cover all parser strategies, price formatting edge cases, deduplication rules, price history changes, and scanner routines — all offline (no network calls), so they always pass or fail for a real reason. The frontend has its own unit tests for the pure logic (filter querystring codec).

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

### Optional developer tooling

Beyond the runtime dependencies, an optional dev toolchain (linting, coverage,
property-based tests, dependency CVE scanning, and a pre-commit hook) lives in
`backend/requirements-dev.txt`. It is **never** installed on the target device —
only in a development checkout:
```bash
cd backend
& .venv/Scripts/python.exe -m pip install -r requirements-dev.txt
& .venv/Scripts/ruff.exe check app tests      # lint
& .venv/Scripts/ruff.exe format app tests     # format
& .venv/Scripts/python.exe -m pip_audit -r requirements.txt   # CVE scan
```
