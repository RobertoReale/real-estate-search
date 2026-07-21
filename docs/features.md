# Beyond the Listing Grid

[← Back to README](../README.md)

* **Interface language (English / Italian)**: the 🌐 button in the top bar
  switches the whole dashboard between English and Italian — every label,
  button, tooltip and confirmation dialog, plus number and date formats
  (`€350,000` / `350.000 €`). The first visit follows your browser's language
  (Italian if it can't tell); after that your choice is remembered **per
  device**, exactly like the light / dark theme next to it, so the phone and
  the desktop can differ. Two things stay in English on purpose: text the
  *backend* produces (scan summaries, the availability check's transport line,
  error messages coming from a portal or from Gmail) — it is rendered before
  it reaches the browser and the server does not know which language you
  picked — and the listing text itself, which is whatever the Italian portals
  published.
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
  clears the lookup memory and never moves a pin you already have. Both the
  lookup's sanity check and the *Repair data* city detection work for **every
  Italian comune** (a bundled offline index of all ~7,900 municipalities), not
  just a shortlist of big cities — a wrong-looking pin is judged against its own
  town's actual location, and city names anywhere in Italy are recognized.
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
* **Scraper health**: a panel showing, portal by portal, how the last month of
  scans actually went — one colored cell per day (green = every scan ok, amber =
  some failed, red = all failed), the failure rate over the window, which
  transport carried the last scan, and which searches are currently on a failure
  streak. A blocked scraper is otherwise silent (no listings looks exactly like
  a quiet market), so this is the place that says *the pipeline is degrading,
  add a proxy pool or a scraping-API key* before scans quietly stop delivering.
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
* **Email inbox import**: see [Email Inbox Import](email-import.md) for the full
  walkthrough — importing listing links from your own mailbox, checking whether
  they're still online, and dealing with DataDome blocks during that check.
