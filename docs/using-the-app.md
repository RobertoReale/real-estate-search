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
     a small **✉️ email** badge. *Limit to a search* narrows the grid down to the
     properties one of your saved monitored searches actually found — the same
     searches listed under each card's **🔍 Found by**. Email imports, which no
     search found, drop out. (It is a filter, not a ranking — it shrinks the
     list, it does not reorder it.)
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
