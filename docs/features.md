# Beyond the Listing Grid

[← Back to README](../README.md)

* **Four places, not one long page**: the app opens on the **Listings**, which
  is the product — the first property is on screen without scrolling. The rest
  is one click away in the navigation: **Insights** (price trends, market
  velocity, scraper health), **Searches** (everything you monitor, and the three
  ways to add one) and **Settings**. Each has its own address, so any of them
  can be bookmarked or sent to someone, and moving between them keeps whatever
  you had filtered the listings down to. On a phone the navigation is a bar
  along the bottom, where a thumb reaches it; on a laptop it is in the top bar.
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
  the property. Many Immobiliare listings arrive without coordinates, so **a scan
  fills the map in as it goes**, without being asked: it takes whatever the ad
  itself carried, then places the rest from what your dashboard already knows —
  an address looked up once answers every other listing on that street for free —
  and finally asks OpenStreetMap about what is left, for the listings that scan
  collected only. That last step is the only one that costs a request, is capped
  per scan and paced at OpenStreetMap's one request a second; set
  `geocode_after_scan` to `false` in `settings.json` if you would rather your
  scans stay entirely local. The two free steps always run.
* **A pin that is not an address says so**: when a listing's own address cannot
  be placed, it is drawn at the centre of its district instead — as a **hollow,
  dashed pin**, counted in the legend, and labelled "approximate: centre of the
  area, not the address" when you hover it. A rough location is useful; a rough
  location that looks exact is not, and it is the kind of mistake you would have
  no way of spotting. Nothing else in the app treats those pins differently, so a
  zone you draw around a district will include them.
* The **📍 Find coordinates** button under *Maintenance*, on the **Searches**
  screen, runs the same
  OpenStreetMap lookup over the *whole* dashboard rather than one scan's
  listings — the remedy for what is still missing after a scan, or after
  importing older data (cached, and it never invents a wrong pin: a lookup it
  cannot resolve is simply left off the map). It works in batches, so on a large
  dashboard press it again to continue. You can also jump to a single property: open its card and
  press **🗺️ View on map** — it opens the map centered on that pin, and if the
  property has no coordinates yet it finds them first (same OpenStreetMap lookup),
  telling you if the address was too vague to place. Failed lookups are
  remembered so the same address isn't asked twice, which means a temporary
  OpenStreetMap outage can leave a perfectly good address stuck as "not found";
  the **🧹 Retry failed lookups** button (next to *Find coordinates*) forgets
  those failed lookups so the next *Find coordinates* tries them again — it only
  clears the lookup memory and never moves a pin you already have. The lookup's
  sanity check works for **every Italian comune** (a bundled offline index of
  all ~7,900 municipalities), not just a shortlist of big cities — a
  wrong-looking pin is judged against its own town's actual location.
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
* **What the tax authority records** (only once you have imported the OMI data):
  the fairness check above compares asking prices with asking prices, so a zone
  where everyone asks too much reads as normal. The Agenzia delle Entrate
  publishes min/max €/mq per micro-zone taken from **recorded sales**, and a
  property's detail view shows that band next to the listing median, each
  labelled with what it is and the OMI one dated with its semester. They are
  deliberately never averaged: what sellers ask sits systematically above what
  deeds say, so a single blended number would mean nothing while looking
  official. A property with no OMI data behind it simply shows the median alone.
  Because the Agenzia publishes twice a year and the file is imported by hand, a
  band whose semester ended more than 18 months ago is flagged **out of date**
  rather than left to look current — it is still shown, since recorded prices two
  years old still beat asking prices alone, but you can see its age before you
  lean on it. The source is credited wherever the figures appear, on screen and
  in the printed dossier, as the licence on the data requires.
  [Refreshing it](using-the-app.md#refreshing-the-omi-benchmark) explains where
  the file comes from and how to load a new one.
* **Deal Score**: builds on the fairness check to flag genuine opportunities. It
  combines the €/sqm gap to the local median with condition cues read from the
  listing text (*da ristrutturare* lowers it, *ristrutturato / classe A* raises
  it) into a single score — positive means priced below the market. An
  undervalued listing shows a **🎯 below market** badge, and its detail modal
  adds a suggested proposal range drawn from the agency's own usual discount. If
  Telegram or email alerts are on, an undervalued new listing carries the flag
  into the notification. It is a starting point for your judgement, not an
  appraisal, and appears only where there are enough comparables to mean it.
* **What the listing says** (optional, off by default): an agency description is
  written to sell, and the things that decide whether a viewing is worth the
  trip are buried in its prose — building fees the price does not include, a
  flat sold *locato* with a tenant in place until 2028, a *da ristrutturare*
  three paragraphs down, the sentence that becomes your first argument on
  price. Turn it on under **Settings → 🧠 Read listing texts**, and a property's
  detail view gains a **🧠 Read the listing** button: the model reads that ad's
  own text and reports the condition, whether a tenant comes with it, what the
  asking price does not cover, what is worth checking, and what is usable when
  negotiating. Four things to know. Nothing is ever read automatically — one
  press reads one listing, so no scan and no scrolling costs you anything. It
  uses the **same** language model as the search assistant above (a local
  **Ollama** keeps it free and fully offline; a cloud endpoint works too), set
  up once in the same panel. Answers are remembered, so re-opening the card is
  free, and if the ad has been rewritten since, the panel says so and offers to
  read it again. And it is a re-reading of the ad's own words, not an appraisal:
  it reports what the text states and stays quiet where the text is silent —
  anything that matters is still a question for the agency.
* **Smart Match Score**: define your "dream home" once in **Settings** — a budget,
  minimum rooms, surface or floor, must-have features (e.g. *balcone, ascensore*),
  and preferred zones — and every card shows a **compatibility %** scored against
  it. Only the wishes you fill in count, numbers you leave at 0 are ignored, and
  the scoring is entirely local. Sort the grid by **🎯 Best match** to bring your
  closest fits to the top.
* **Commute times**: a price only answers half the question — "how far is it from
  work?" is the other half, and no portal filter asks it. Under **Settings → 🚏
  Commute times**, save the places you actually travel to (work, the university,
  the nearest metro stop), each with an address and how you would get there (car,
  on foot, bike). Press **Compute commute times now** and every card gains a line
  like *🚗 Work 18 min*, with the distance alongside it in the property's detail
  view. Three things are worth knowing. It only covers listings that already have
  map coordinates, so run **📍 Find coordinates** first if the map looks sparse.
  Times are computed once and remembered, so opening the dashboard never waits on
  the routing server — which also means a newly-found listing shows no commute
  until you press the button again (it tells you how many are left). And by
  default the routing goes to OpenStreetMap's free demo server, which only knows
  the **road** network: "on foot" and "bike" are routed there as if driving, so
  set your own OSRM server in the same panel if you need true walking times.
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
* **Scraper health**: a panel in two halves, labelled so neither can be read as
  the other. *History* is portal by portal, how the last month of scans actually
  went — one colored cell per day (green = every scan ok, amber = some failed,
  red = all failed), the failure rate over the window, and which transport
  carried the last scan. *Right now* is the searches still on a failure streak,
  which clears the moment a scan gets through. A blocked scraper is otherwise
  silent (no listings looks exactly like a quiet market), so this is the place
  that says *the pipeline is degrading, add a proxy pool or a scraping-API key*
  before scans quietly stop delivering.
* **"Nothing found" is not "something went wrong"**: a search that comes back
  empty says which of the two it was. **No matches** means the portal answered
  and its answer was that nothing fits your criteria today; **Blocked** means it
  did not really answer at all. The distinction is taken from the portal's own
  words — an empty result set it counted, versus an empty one it did not — and
  a "no matches" run is treated as a working scan, so a search over a quiet
  market never builds up towards a false outage alert.
* **Tags**: create your own free-form categories — "senza ascensore", "con
  giardino", "mi piace ma…" — and attach as many as you like to a property,
  right from its card or the detail modal. Typing a name that already exists
  reuses it instead of creating a near-duplicate. Filter the grid down to a
  single tag from the filter rail, same as filtering by city or zone.
* **Which search found it**: a property's detail modal shows **🔍 Found by** —
  the monitored searches that turned it up. Overlapping searches both appear, so
  you can tell at a glance whether a listing came from your "Milano trilocali" or
  your "Navigli" search (or both). A property that predates the provenance links
  says so instead.
* **Mortgage calculator**: inside a property's detail modal, estimate the monthly
  payment (French amortization) for a given down payment, rate, and term.
* **Share a shortlist**: the **Export** buttons at the foot of the filter rail download the
  properties currently on screen — apply the filters or tick *Favorites* first —
  as a self-contained **HTML dossier**, a clean **Markdown** report, or a **CSV**
  spreadsheet. Each includes prices, price-drop history, and the Deal/Match
  scores. It is a single offline file you can send to a partner, family member,
  or agent over chat or email, without giving anyone access to your dashboard or
  database. (The HTML dossier's thumbnails load from the portals, so those need
  a connection; everything else works fully offline.)
* **A printable report for the bank or the viewing**: the fourth Export button,
  **PDF**, opens a paginated report — one property per page — and raises your
  browser's print dialog straight away. Choose *Save as PDF* as the destination
  (tick *Background graphics* to keep the coloured badges) and you have a file
  to email to a broker or print for a visit. Each page carries a photo gallery,
  the key facts, the full asking-price history with the drop percentages, the
  area median and Deal/Match scores when they are known, your own notes, the ad
  links, and a **viewing checklist** with tick boxes and blank lines to fill in
  on site — building fees, heating, damp, noise, what the land registry plan
  says. A merged property shows one photo per agency ad, so a listing published
  three times gives you three pictures rather than one. There is no PDF engine
  on the backend and none is needed: your browser already renders the page and
  writes the PDF, which also means the photos come from the portals exactly as
  they do in the HTML dossier, so that step needs a connection.
* **Is this ad still online?**: see [Is This Ad Still Online?](availability-check.md)
  for the full walkthrough — checking a selection against the portals on demand,
  why it is paced the way it is, and dealing with DataDome blocks during a check.
