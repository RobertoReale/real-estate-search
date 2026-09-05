# Using the App

[← Back to README](../README.md)

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
2. **Add Profile**: Open **Searches** in the navigation, click **"+ Add search profile"**, give it a name, paste the URL, and click **"Save profile"**. To change one later (name, URL, or excluded keywords), click the **✏️** icon next to it in the list. To remove one, click **🗑** — see *Deleting a search* below, since you get to decide what happens to the listings it found.
   - *No accidental duplicates*: a search that resolves to the same portal URL and the same excluded keywords as one you already monitor is refused (the comparison ignores irrelevant differences like trailing slashes, tracking parameters, or keyword order/case), so the same listings aren't scanned and notified twice. Any pre-existing duplicates are merged into the oldest copy at startup, preserving which searches found what.
   - Each search also shows the **excluded keywords** actually in effect for it — the global ones set in Settings plus its own extras — so what gets discarded is visible without opening anything.
3. **Start Scanning**: Click **"Start Scan Now"** (or let the automatic scheduler scan in the background).
4. **Browse Listings**: Merged listings will show a purple badge (e.g., *"2 merged listings"*), showing that duplicates across different portals or agencies have been successfully grouped together. Properties that appeared since your last visit carry a **🆕 new** badge, so a scan's findings are obvious at a glance; it clears itself the next time you reload the dashboard on that device (it is remembered per-browser, like the theme and the optional auth token — the same device shows it once).
5. **Curation (Hide, Discard & Mark sold)**:
   - If you see a listing you do not want to track, click on the card to open it, then click **`Hide property`**.
   - Hidden listings are permanently excluded from searches and notifications. If you want to review or retrieve them, select the **`Discarded`** option in the **Status** filter at the top of the dashboard. On the detail page of a discarded property, you can click **`Restore property`** to move it back to active status.
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
     monitored searches found (**🔎 Monitored search**) from ones an older
     version pulled in from your mailbox (**✉️ Email import**), which still
     carry a small **✉️ email** badge — the inbox import itself is gone, so
     nothing new arrives that way. *Limit to a search* narrows the grid down to
     the properties one of your saved monitored searches actually found — the
     same searches listed under each card's **🔍 Found by**. Cards no search
     found drop out. (It is a filter, not a ranking — it shrinks the list, it
     does not reorder it.)
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

## Sharing what you are looking at

The address bar holds the dashboard's state, so anything on screen can be sent
to somebody else or kept for later:

- **A property has its own address** (`/listings/123`). Copy it out of the
  address bar and it opens on that property in any browser on the machine —
  including one where the filters would otherwise have hidden it.
- **The filters travel with it.** Whatever you narrowed to is on the link, so
  the person opening it lands on the grid you were reading rather than on the
  default one. Only what you actually changed is written down, which is why a
  clean dashboard is just `/listings`.
- **Back and Forward work.** Each filter you set is one step back, and typing a
  price counts as one step rather than one per digit.
- **One property at a time, without losing your place.** On a laptop a
  property takes the whole screen; `j` and `k` — or the arrow keys — move to
  the next and previous result without going back to the grid in between, and
  the address follows as you go. Back returns you to the grid at the row you
  left rather than at the top. On a phone the same thing arrives as a sheet
  over the grid.
- **A reload lands where you left.** The filters, the sort and the grid/map
  choice all survive it, and survive being bookmarked.

## Deleting a search: what happens to its listings

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

## Acting on several searches at once

With more than one search in the list, each row gets a checkbox and a **Select
all** appears above them. Tick a few and a toolbar offers, for the whole
selection: **Activate**, **Pause**, a **Notifications →** menu, and **Delete**
(same dialog as above, with the totals for the selection). Handy for pausing
every search before a holiday, or silencing a noisy batch, without clicking
through them one at a time.

## Silencing one search

The **Notifications** menu on a search row (or on a selection) chooses where its
alerts go: *All channels*, *Telegram only*, *Email only*, or **🔕 No
notifications**. The last one keeps the search running — its listings keep
arriving in the dashboard — but you are never pinged for it: no new-listing
message, no price-drop message, not even the scraper-health alert. It is the
answer to "I want to watch this search, just not in real time"; *Pause*, by
contrast, stops scanning it altogether.

## Refreshing the OMI benchmark

The detail view of a property can show a second price reference beside the
listing median: min/max €/m² the Agenzia delle Entrate records **actual sales**
at, for that property's micro-zone. The app never fetches this itself — the data
sits behind an authenticated SPID session — so you download it and import it,
about once every six months. Until you do, nothing here applies and cards simply
show the listing median alone.

The figures on screen are always labelled with the semester they cover, and a
band whose semester ended more than **18 months** ago is flagged *out of date*
rather than quietly trusted. That flag is your cue to repeat this procedure.

### Getting the file

The supply comes from the Agenzia delle Entrate's OMI service, reached with
SPID/CIE through Fisconline/Entratel. Three things about that site are worth
knowing in advance, because each one costs a week when it is discovered by
accident:

* **You issue a *request*, not a download.** The request appears as *Inserita*
  and stays that way until the Agenzia processes it, at which point it becomes
  *Disponibile*. There is nothing to do in between but wait and check back.
* **Each processed request may be downloaded once.** A download that is
  interrupted, or a file saved somewhere you then lose it, means issuing the
  request again and waiting again. Save it somewhere permanent on the first try.
* **A processed request expires after 7 days.** Past that it is gone and has to
  be requested afresh.

**Ask for the national supply, not a single comune.** Only the national one ships
the *zone perimeters*; a municipal extract carries the prices and no geometry at
all, and without perimeters the app has no way to work out which micro-zone a
property falls in — so every listing would end up with no benchmark. It is a
larger download for the same amount of work afterwards.

### Importing it

Unzip the delivery into a folder of its own and point the `omi_input_dir`
setting at that folder. A folder rather than a file: a delivery is two documents
(the quotations and the zone descriptions), and the app identifies which is
which by reading their first line — never by their filenames, which contain the
codice fiscale of whoever requested the supply.

Then call the three maintenance endpoints, **in this order**:

```bash
curl -X POST http://localhost:8000/api/maintenance/omi-import
curl -X POST http://localhost:8000/api/maintenance/omi-zones-import
curl -X POST http://localhost:8000/api/maintenance/omi-zones-resolve
```

1. `omi-import` loads the quotations. It answers with how many landed **and** how
   many source rows it skipped — a partial import that reported only its
   successes would look exactly like a complete one.
2. `omi-zones-import` loads the perimeters. It runs second on purpose: it keeps
   only the zones the quotations actually cover, because the national supply
   holds around 28 000 of them and a perimeter with no price behind it can
   produce no benchmark.
3. `omi-zones-resolve` places your existing properties inside their zones. Like
   *Find coordinates*, this is a batch you trigger rather than something a page
   does while you scroll. Run it again after a scan brings in new listings.

Re-importing the same semester replaces it rather than adding to it, so running
these twice is harmless. A newer semester simply wins: the app reads the most
recent one it holds and never blends two together, since a band mixed from two
dates carries no date at all.

Anything that cannot be placed is left alone rather than guessed at — a property
with no coordinates, or one whose pin falls outside every zone, keeps the
listing median and shows no OMI figures. That is not an error condition.
