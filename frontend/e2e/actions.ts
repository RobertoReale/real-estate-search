/** Every control in the dashboard, named once.
 *
 *  The journeys in the other specs cover what a user is *expected* to do. This
 *  covers what they *can* do: every element in `src/` carrying a click, change,
 *  submit or key handler declares a `data-action="<domain>.<verb>"`, and every
 *  one of those ids has a row here. Two gates in `coverage.spec.ts` hold the two
 *  halves together — a handler with no id (or an id with no row) fails the
 *  build, and a row nothing exercised fails the run. Between them, a button
 *  cannot ship untried, which is the whole point.
 *
 *  **What this guarantees is narrow, and worth stating plainly.** It is an
 *  inventory of *controls*, not of states. Nothing here claims every
 *  combination of filters is covered, or every value a field accepts. It claims
 *  that each control exists, is reachable, does the thing its row says, and
 *  does not take the app down when the backend refuses it.
 *
 *  **One row per control, not per rendering.** A control inside a `.map` — the
 *  portal checkboxes, the feature toggles, a backup's Download — is one control
 *  the user meets several times, so it has one row and one id. Splitting it per
 *  item would make the inventory grow with the data rather than with the app.
 *
 *  Three fields carry the rules:
 *
 *  - `does` is the assertion. It is what the spec has to prove, in the terms a
 *    user would use, and it is deliberately not "the request was sent".
 *  - `guard` marks an element whose handler exists only to stop an event
 *    reaching an ancestor — a dialog's panel, the card's quick-action corner.
 *    They are real behaviour (without them a click inside a dialog closes it),
 *    and the recorder credits them for every event that passes through, because
 *    that is exactly when their handler runs.
 *  - `blocked` is the escape hatch, and it costs a written reason. There is
 *    exactly one today. Where an action's *effect* would leave the harness —
 *    a scan, a portal probe, a browser launch — the transport is stubbed and
 *    the control is still driven for real; see `coverage.spec.ts`. Stubbing is
 *    not the same as skipping, and neither is described as the other.
 */

export interface Action {
  /** What the control is, in the words on the screen. */
  readonly what: string;
  /** What must be true after it is fired. This is the assertion. */
  readonly does: string;
  /** Its handler exists only to stop an event reaching an ancestor. */
  readonly guard?: true;
  /** Why the suite refuses to fire it at all. Empty means it is fired. */
  readonly blocked?: string;
}

export const ACTIONS = {
  // ── The shell ───────────────────────────────────────────────────────────
  "nav.listings": {
    what: "Listings, in the navigation",
    does: "goes to the property grid, keeping the filters that are applied",
  },
  "nav.insights": {
    what: "Insights, in the navigation",
    does: "goes to the screen with scraper health, market velocity and price trends",
  },
  "nav.searches": {
    what: "Searches, in the navigation",
    does: "goes to the monitored searches",
  },
  "nav.language": {
    what: "the language toggle in the shell header",
    does: "swaps the interface between English and Italian, and the grid follows",
  },
  "nav.theme": {
    what: "the light/dark toggle",
    does: "puts `dark` on the document element and remembers it across a reload",
  },
  "nav.logs": { what: "the log button in the header", does: "opens the log viewer" },
  "nav.settings": {
    what: "Settings, in the navigation",
    does: "opens the settings dialog over the grid",
  },
  "scan.now": {
    what: "Scan now",
    does: "asks the backend to start a scan and disables itself while one runs",
  },
  "toast.dismiss": {
    what: "the dismiss button on a message",
    does: "removes that message and leaves the screen it was about as it was",
  },
  "toast.action": {
    what: "Try again / Undo on a message",
    does: "re-runs what failed, or reverses what just happened, and closes the message",
  },
  "app.crash.reload": {
    what: "Reload on the last-resort error screen",
    does: "reloads the page after a rendering error, back to a working app",
  },

  // ── Filters ─────────────────────────────────────────────────────────────
  "filters.toggle": {
    what: "Filters — one control in two shapes",
    does: "collapses and reopens the rail on a wide screen, and opens the filter sheet on a narrow one",
  },
  "filters.chip.remove": {
    what: "the × on an active-filter chip",
    does: "takes that one clause off the query and leaves the rest of it alone",
  },
  "filters.query": { what: "the free-text search box", does: "narrows the grid to matching listings" },
  "filters.query.clear": { what: "the clear button inside the search box", does: "empties it and restores the full count" },
  "filters.contract.sale": { what: "Buy", does: "switches the grid to properties for sale" },
  "filters.contract.rent": { what: "Rent", does: "switches the grid to rentals, with rental prices" },
  "filters.city": { what: "the City field", does: "keeps only listings in that city" },
  "filters.zone": { what: "the Zone field", does: "keeps only listings in that zone" },
  "filters.minPrice": { what: "Min price", does: "drops everything cheaper" },
  "filters.maxPrice": { what: "Max price", does: "drops everything dearer" },
  "filters.minSqm": { what: "Min m²", does: "drops everything smaller" },
  "filters.maxSqm": { what: "Max m²", does: "drops everything larger" },
  "filters.rooms": { what: "the Rooms select", does: "keeps listings with that many rooms" },
  "filters.floor": { what: "the Floor band select", does: "keeps listings whose floor falls in the band" },
  "filters.sort": { what: "the Sort select", does: "reorders the grid" },
  "filters.status": { what: "the Status select", does: "switches which lifecycle state the grid shows" },
  "filters.source": { what: "the Origin select", does: "separates scan finds from inbox imports" },
  "filters.tag": { what: "the Tag select", does: "keeps only listings carrying that tag" },
  "filters.profile": { what: "the Limit to a search select", does: "keeps only what that saved search found" },
  "filters.priceDrops": { what: "the Price drops checkbox", does: "keeps only listings whose price has fallen" },
  "filters.favorites": { what: "the Favorites checkbox", does: "keeps only starred listings" },
  "filters.advanced.toggle": { what: "More filters", does: "reveals and hides the advanced panel" },
  "filters.portal": { what: "the Portal select", does: "keeps listings present on that portal" },
  "filters.agency": { what: "the Agency field", does: "keeps listings from a matching agency" },
  "filters.deal": { what: "the Deal quality select", does: "keeps listings by their deal score" },
  "filters.minSqmPrice": { what: "Min €/m²", does: "drops everything below that unit price" },
  "filters.maxSqmPrice": { what: "Max €/m²", does: "drops everything above that unit price" },
  "filters.mergedOnly": { what: "the merged-listings checkbox", does: "keeps only properties found on both portals" },
  "filters.reset": {
    what: "Reset filters",
    does: "puts every filter back to its default and restores the full count",
  },
  "view.grid": { what: "the Grid view button", does: "shows the cards" },
  "view.map": { what: "the Map view button", does: "shows the map instead of the cards" },
  "export.html": { what: "the HTML export button", does: "hands the browser an HTML file of the filtered set" },
  "export.markdown": { what: "the MD export button", does: "hands the browser a Markdown file of the filtered set" },
  "export.csv": { what: "the CSV export button", does: "hands the browser a CSV file of the filtered set" },
  "export.pdf": { what: "the PDF export button", does: "hands the browser a PDF of the filtered set" },

  // ── Maintenance ─────────────────────────────────────────────────────────
  "maintenance.geocode": {
    what: "Find coordinates",
    does: "runs the geocoding sweep and reports how many pins it placed",
  },
  "maintenance.geocode.stop": {
    what: "Stop, beside the geocoding progress bar",
    does: "asks the running sweep to stop after the address in flight",
  },
  "maintenance.clearGeocodeCache": {
    what: "Retry failed lookups",
    does: "clears the remembered failures and says how many it dropped",
  },
  "maintenance.result.dismiss": { what: "the dismiss button on the geocoding summary", does: "removes the summary" },
  "maintenance.cacheCleared.dismiss": { what: "the dismiss button on the cache-cleared notice", does: "removes the notice" },

  // ── The grid and its cards ──────────────────────────────────────────────
  "app.addSearch": {
    what: "Add a search, in the first-run steps",
    does: "goes to the searches, so step one is a click rather than an instruction",
  },
  "grid.loadMore": { what: "Show N more", does: "appends the next page of results to the grid" },
  "property.card": { what: "the card itself", does: "opens that property, or selects it while multi-select is on" },
  "property.open": { what: "the card's title button", does: "opens the property from the keyboard" },
  "property.favorite": { what: "the star on a card", does: "stars the property, and the star fills in" },
  "property.hide": { what: "the hide button on a card", does: "asks first, then takes the property out of the grid" },
  "property.select": { what: "the tick box on a card, while multi-select is on", does: "adds the property to the batch" },
  "property.quickActions": {
    what: "the corner holding the select, star and hide buttons",
    does: "keeps a click on any of them from opening the property underneath",
    guard: true,
  },

  // ── Tags, from the card and from the detail ─────────────────────────────
  "tags.picker": {
    what: "the tag strip",
    does: "keeps a click inside it from opening the property, and closes the input on blur",
    guard: true,
  },
  "tags.add": { what: "the + tag button", does: "opens the tag input" },
  "tags.name": { what: "the tag input", does: "filters the suggestions, and Enter creates the tag" },
  "tags.suggest": { what: "a suggested existing tag", does: "puts that tag on the property" },
  "tags.create": { what: "the create-this-tag row", does: "creates a new tag and puts it on the property" },
  "tags.remove": { what: "the × on a tag chip", does: "takes the tag off the property" },

  // ── The selection bar ───────────────────────────────────────────────────
  "selection.toggleMode": { what: "Select multiple", does: "turns multi-select on, and off again with the selection cleared" },
  "selection.selectAll": { what: "the select-all checkbox", does: "selects the whole filtered set, not just the loaded page" },
  "selection.hide": { what: "Hide N", does: "asks first, then hides every selected property" },
  "selection.markSold": { what: "Mark N sold", does: "asks first, then records the sale on every selected property" },
  "selection.favorite": { what: "Add to favorites", does: "stars every selected property" },
  "selection.unfavorite": { what: "Remove from favorites", does: "unstars every selected property" },
  "selection.checkAvailability": { what: "Check N are still online", does: "runs the availability batch and reports what it found" },
  "selection.stopCheck": { what: "Stop, while the batch runs", does: "asks the batch to stop after the listing in flight" },
  "selection.dismissSummary": { what: "the dismiss button on the batch summary", does: "removes the summary" },

  // ── The property detail ─────────────────────────────────────────────────
  "detail.close": { what: "the close button on the detail", does: "goes back to the grid" },
  "detail.prev": { what: "the back arrow in the detail's header", does: "opens the previous result without leaving the page" },
  "detail.next": { what: "the forward arrow in the detail's header", does: "opens the next result without leaving the page" },
  "detail.favorite": { what: "the star in the detail", does: "stars the property, and the star fills in" },
  "detail.notes": { what: "the notes box", does: "holds what is typed, and reveals the Save button" },
  "detail.notes.save": { what: "Save notes", does: "stores the note, and it is still there when the property is reopened" },
  "detail.checkOnline": { what: "Check if it is still online", does: "probes the listing and says what came back" },
  "detail.viewOnMap": { what: "View on the map", does: "leaves the detail and puts the map on that property" },
  "detail.audit.read": { what: "Read the listing", does: "asks the configured model to read the ad and shows what it found" },
  "detail.restore": { what: "Restore", does: "asks first, then puts a hidden, gone or sold property back in the grid" },
  "detail.markSold": { what: "Mark as sold", does: "asks first, then records the sale and leaves the grid" },
  "detail.hide": { what: "Hide", does: "asks first, then takes the property out of the grid" },

  // ── The mortgage and yield calculators ──────────────────────────────────
  "calc.mortgage.downPayment": { what: "the down-payment percentage", does: "changes the loan amount and the monthly payment" },
  "calc.mortgage.rate": { what: "the interest rate", does: "changes the monthly payment" },
  "calc.mortgage.years": { what: "the loan duration", does: "changes the monthly payment" },
  "calc.yield.rent": { what: "the expected rent", does: "reveals the gross and net yield and the cash flow" },
  "calc.yield.costs": { what: "the costs and vacancy percentage", does: "changes the net yield" },

  // ── The map ─────────────────────────────────────────────────────────────
  "map.drawRadius": { what: "Draw a radius", does: "arms radius drawing, and disarms it on a second press" },
  "map.drawArea": { what: "Draw an area", does: "arms polygon drawing, and finishes the polygon on a second press" },
  "map.clearZone": { what: "Clear the area", does: "drops the geographic filter and restores the full set" },
  "map.findCoordinates": {
    what: "Find coordinates, on the without-a-pin warning",
    does: "runs the geocoding sweep from the map",
    blocked:
      "the warning it sits on renders only while a geographic filter is active "
      + "AND the shown set still holds properties with no coordinates — and the "
      + "backend's geographic filter drops exactly those (routers/selection.py "
      + "keeps a property only when it has a latitude), so the moment the grid "
      + "refetches, the count is zero and the warning is gone. The state exists "
      + "for one frame and cannot be held still. The sweep behind the button is "
      + "the same one `maintenance.geocode` drives, and that one is exercised.",
  },

  // ── Insights ────────────────────────────────────────────────────────────
  "insights.toSearches": {
    what: "Add a search, on an Insights screen with nothing to analyse",
    does: "goes to the searches, which is the only thing that fills this screen in",
  },
  "trends.area": { what: "the area select", does: "redraws the chart for that area" },
  "trends.comparables": { what: "Show the listings behind it", does: "loads and hides the comparable listings" },
  "trends.openProperty": { what: "a comparable listing", does: "opens that property" },

  // ── Monitored searches ──────────────────────────────────────────────────
  "profiles.mode.assistant": { what: "Describe it", does: "opens the plain-language box, and closes it again" },
  "profiles.mode.builder": { what: "Build it", does: "opens the guided form, and closes it again" },
  "profiles.mode.url": { what: "Paste a URL", does: "opens the URL form, and closes it again" },

  "profiles.assistant.query": { what: "the plain-language box", does: "holds the query, and Enter submits it" },
  "profiles.assistant.ask": { what: "the assistant's submit button", does: "reads the query and opens the builder on what it understood" },
  "profiles.assistant.example": { what: "one of the example queries", does: "puts that example in the box" },

  "profiles.builder.reword": { what: "Reword", does: "goes back to the plain-language box" },
  "profiles.builder.toUrlIntro": { what: "the paste-a-URL link in the intro", does: "switches to the URL form" },
  "profiles.builder.toUrlTip": { what: "the paste-a-URL link in the tip", does: "switches to the URL form" },
  "profiles.builder.contract": { what: "the builder's Buy/Rent select", does: "sets which market the search covers" },
  "profiles.builder.city": { what: "the builder's City field", does: "sets the city, and enables Generate" },
  "profiles.builder.province": { what: "the builder's Province field", does: "narrows an ambiguous city name" },
  "profiles.builder.zone": { what: "the builder's Zone field", does: "sets the zone the search covers" },
  "profiles.builder.minPrice": { what: "the builder's Min price", does: "sets the lower bound of the search" },
  "profiles.builder.maxPrice": { what: "the builder's Max price", does: "sets the upper bound of the search" },
  "profiles.builder.minRooms": { what: "the builder's Min rooms", does: "sets the room floor of the search" },
  "profiles.builder.minSqm": { what: "the builder's Min m²", does: "sets the size floor of the search" },
  "profiles.builder.floor": { what: "the builder's Floor select", does: "restricts the search to a floor band" },
  "profiles.builder.condition": { what: "the builder's Condition select", does: "restricts the search by condition" },
  "profiles.builder.feature": { what: "one of the feature checkboxes", does: "adds that requirement to the search" },
  "profiles.builder.name": { what: "the builder's name field", does: "names the saved search" },
  "profiles.builder.keywords": { what: "the builder's exclusion keywords", does: "records the words that disqualify a listing" },
  "profiles.builder.generate": { what: "Generate the URLs", does: "shows the URL built for each portal" },
  "profiles.builder.usePortal": { what: "a portal checkbox on a generated URL", does: "decides whether that portal is searched" },
  "profiles.builder.openBuilt": {
    what: "Open, beside a generated URL",
    does: "opens the built search on the portal, in a new tab",
    blocked:
      "it navigates to the portal, in a second tab. The suite may reach nothing "
      + "beyond its own two servers (e2e/harness/offline.ts), and unlike the "
      + "actions whose transport is stubbed there is nothing here to stub: the "
      + "whole behaviour is the navigation.",
  },
  "profiles.builder.create": { what: "Create the searches", does: "saves the search and it appears in the list" },

  "profiles.url.name": { what: "the URL form's name field", does: "names the saved search" },
  "profiles.url.keywords": { what: "the URL form's exclusion keywords", does: "records the words that disqualify a listing" },
  "profiles.url.url": { what: "the pasted URL field", does: "holds the URL, and reveals Extract parameters" },
  "profiles.url.extract": { what: "Extract parameters", does: "reads the URL and fills the form from it" },
  "profiles.url.save": { what: "the URL form's save button", does: "saves the search and it appears in the list" },

  "profiles.multi.reword": { what: "Reword, above the alternatives", does: "goes back to the plain-language box" },
  "profiles.multi.edit": { what: "Edit, on one alternative", does: "opens that alternative in the builder" },
  "profiles.multi.drop": { what: "the remove button on one alternative", does: "removes it from the list before anything is created" },
  "profiles.multi.usePortal": { what: "a portal checkbox on the alternatives", does: "decides whether that portal is searched" },
  "profiles.multi.keywords": { what: "the alternatives' exclusion keywords", does: "records the words that disqualify a listing" },
  "profiles.multi.create": { what: "Create N searches", does: "saves every remaining alternative" },

  "profiles.row.select": { what: "a search's checkbox", does: "adds it to the bulk selection" },
  "profiles.row.notify": { what: "a search's notification select", does: "changes where that search's alerts go" },
  "profiles.row.active": { what: "a search's Active checkbox", does: "pauses the search without deleting it" },
  "profiles.row.edit": { what: "the edit button on a search", does: "opens it in the form it was created with" },
  "profiles.row.separate": { what: "the split button on a merged pair", does: "splits the two portals back into separate searches" },
  "profiles.row.delete": { what: "the delete button on a search", does: "opens the delete dialog for it" },

  "profiles.bulk.selectAll": { what: "the select-all checkbox above the searches", does: "selects every search, and clears them again" },
  "profiles.bulk.activate": { what: "Activate", does: "resumes every selected search" },
  "profiles.bulk.pause": { what: "Pause", does: "pauses every selected search" },
  "profiles.bulk.notify": { what: "the bulk notification select", does: "changes where the selected searches' alerts go" },
  "profiles.bulk.merge": { what: "Merge", does: "folds the selected searches into one row" },
  "profiles.bulk.delete": { what: "Delete", does: "opens the delete dialog for the selection" },
  "profiles.bulk.clear": { what: "Clear the selection", does: "unselects everything and hides the bulk bar" },

  "profiles.delete.panel": { what: "the delete dialog's panel", does: "keeps a click inside it from closing the dialog", guard: true },
  "profiles.delete.backdrop": { what: "the dimmed area around the delete dialog", does: "closes it without deleting anything" },
  "profiles.delete.cancel": { what: "Cancel", does: "closes the dialog and leaves the search alone" },
  "profiles.delete.keepResults": { what: "Delete but keep the results", does: "deletes the search and leaves its properties in the grid" },
  "profiles.delete.withResults": { what: "Delete with its N results", does: "deletes the search and the properties only it found" },

  // ── Settings: the dialog itself ─────────────────────────────────────────
  "settings.panel": { what: "the settings panel", does: "keeps a click inside the dialog from closing it", guard: true },
  "settings.close.backdrop": { what: "the dimmed area around the dialog", does: "closes settings" },
  "settings.close": { what: "the close button in settings", does: "closes settings" },
  "settings.footer.close": { what: "Close, at the foot of settings", does: "closes settings" },
  "settings.save": { what: "Save settings", does: "persists every section, and says so" },
  "settings.loadError.retry": { what: "Retry, when settings could not be loaded", does: "asks the backend again" },
  "settings.loadError.close": { what: "Close, when settings could not be loaded", does: "closes the dialog rather than trapping the user in it" },

  // ── Settings: Telegram ──────────────────────────────────────────────────
  "settings.telegram.token": { what: "the bot token field", does: "holds the token, and the badge says it is unsaved" },
  "settings.telegram.chatId": { what: "the chat id field", does: "holds the chat the alerts go to" },
  "settings.telegram.actions": { what: "the reply-buttons checkbox", does: "turns the notification's buttons on and off" },
  "settings.telegram.enable": { what: "the enable-Telegram checkbox", does: "turns Telegram notifications on and off" },
  "settings.telegram.test": { what: "Save and test, under Telegram", does: "saves, sends a test message and reports what happened" },

  // ── Settings: email ─────────────────────────────────────────────────────
  "settings.email.host": { what: "the SMTP host", does: "holds the server the mail goes through" },
  "settings.email.port": { what: "the SMTP port", does: "holds the port" },
  "settings.email.user": { what: "the SMTP user", does: "holds the account" },
  "settings.email.password": { what: "the SMTP password", does: "holds the password, and the badge says it is unsaved" },
  "settings.email.from": { what: "the From address", does: "holds the sender" },
  "settings.email.to": { what: "the To address", does: "holds the recipient" },
  "settings.email.enable": { what: "the enable-email checkbox", does: "turns email notifications on and off" },
  "settings.email.test": { what: "Save and test, under email", does: "saves, sends a test message and reports what happened" },

  // ── Settings: scanning ──────────────────────────────────────────────────
  "settings.scanning.interval": { what: "the scan frequency select", does: "sets how often the scheduler runs" },
  "settings.scanning.pause": { what: "the pause-scans checkbox", does: "stops the scheduler without deleting anything" },
  "settings.scanning.healthAfter": { what: "the health-alert threshold", does: "sets how many failures in a row raise an alert" },
  "settings.scanning.keywords": { what: "the global exclusion keywords", does: "records the words that disqualify a listing everywhere" },

  // ── Settings: smart match ───────────────────────────────────────────────
  "settings.match.enable": { what: "the match-score checkbox", does: "turns the score on, and reveals the dream-home fields" },
  "settings.match.maxPrice": { what: "the dream maximum price", does: "feeds the match score" },
  "settings.match.minRooms": { what: "the dream minimum rooms", does: "feeds the match score" },
  "settings.match.minSqm": { what: "the dream minimum m²", does: "feeds the match score" },
  "settings.match.minFloor": { what: "the dream minimum floor", does: "feeds the match score" },
  "settings.match.features": { what: "the dream features", does: "feeds the match score" },
  "settings.match.zones": { what: "the dream zones", does: "feeds the match score" },

  // ── Settings: commute ───────────────────────────────────────────────────
  "settings.commute.enable": { what: "the commute checkbox", does: "turns commute times on, and reveals the places list" },
  "settings.commute.addPoint": { what: "Add a place", does: "appends a blank place to type into" },
  "settings.commute.pointName": { what: "a place's name", does: "names the destination shown on the card" },
  "settings.commute.pointAddress": { what: "a place's address", does: "sets where the route ends" },
  "settings.commute.pointMode": { what: "a place's travel mode", does: "chooses car, foot or bike" },
  "settings.commute.removePoint": { what: "the delete button on a place", does: "removes that place" },
  "settings.commute.osrmUrl": { what: "the OSRM URL", does: "points the routing at a self-hosted server" },
  "settings.commute.compute": { what: "Compute the commutes", does: "saves, routes what it can and reports how many" },

  // ── Settings: assistant and the listing reader ──────────────────────────
  "settings.assistant.backend": { what: "the assistant backend select", does: "chooses the built-in parser or a model" },
  "settings.assistant.audit": { what: "the read-the-listing checkbox", does: "turns the optional listing reader on" },
  "settings.assistant.baseUrl": { what: "the model's base URL", does: "points the reader at an endpoint" },
  "settings.assistant.model": { what: "the model name", does: "names the model to ask" },
  "settings.assistant.apiKey": { what: "the model's API key", does: "holds the key, and the badge says it is unsaved" },

  // ── Settings: staying unblocked ─────────────────────────────────────────
  "settings.scraping.proxyUrl": { what: "the single proxy URL", does: "routes scraping through that proxy" },
  "settings.scraping.proxyPool": { what: "the proxy pool", does: "holds one proxy per line, rotated between requests" },
  "settings.scraping.idealistaKey": { what: "the Idealista API key", does: "holds the key, and the badge says it is unsaved" },
  "settings.scraping.idealistaSecret": { what: "the Idealista API secret", does: "holds the secret, and the badge says it is unsaved" },
  "settings.scraping.idealistaMaxPages": { what: "the Idealista page cap", does: "sets how many pages the official API is asked for" },
  "settings.scraping.apiProvider": { what: "the scraping-service select", does: "chooses which service the key belongs to" },
  "settings.scraping.apiKey": { what: "the scraping-service key", does: "holds the key, and the badge says it is unsaved" },
  "settings.scraping.apiMode": { what: "the when-to-use select", does: "chooses fallback-only or always" },
  "settings.scraping.cookie": { what: "the DataDome cookie", does: "holds the pasted cookie, and the badge says it is unsaved" },
  "settings.scraping.grabCookie": { what: "Grab the cookie", does: "opens a browser to harvest a fresh cookie, and says how it went" },
  "settings.scraping.stopGrab": { what: "Stop, while the browser is open", does: "closes the harvesting browser" },
  "settings.scraping.autoRefresh": { what: "the auto-refresh checkbox", does: "lets a scan harvest a cookie by itself" },
  "settings.scraping.browserFirst": { what: "the browser-first checkbox", does: "puts the browser at the top of the transport ladder" },
  "settings.scraping.browserHeadful": { what: "the visible-browser checkbox", does: "shows the harvesting browser rather than hiding it" },
  "settings.scraping.humanize": { what: "the humanize checkbox", does: "slows the harvesting browser's movements" },
  "settings.scraping.engine": { what: "the browser engine select", does: "chooses Camoufox, Chromium or whichever is available" },
  "settings.scraping.installCamoufox": { what: "Install Camoufox", does: "installs the stealth browser and reports the result" },
  "settings.scraping.installHarvester": { what: "Install the harvester", does: "installs Playwright and reports the result" },

  // ── Settings: the system, the backups and the resets ────────────────────
  "settings.system.apiToken": { what: "the API token field", does: "holds the token this browser will send" },
  "settings.system.restart": { what: "Restart the backend", does: "asks the backend to restart and says whether it will" },
  "settings.system.backupNow": { what: "Take one now", does: "adds a snapshot to the list" },
  "settings.system.backupDownload": { what: "Download, on a snapshot", does: "hands the browser that snapshot as a file" },
  "settings.system.backupImport": { what: "Bring one in", does: "opens the file picker" },
  "settings.system.backupFile": { what: "the hidden file input", does: "uploads the chosen database, and it joins the list" },
  "settings.system.backupRestore": { what: "Restore, on a snapshot", does: "asks for a typed word, then replaces the live database" },
  "settings.system.resetDashboard": { what: "Clear the dashboard", does: "asks first, then deletes the collected properties" },
  "settings.system.resetTrends": { what: "Clear the price history", does: "asks first, then deletes the pricing snapshots" },
  "settings.system.resetFactory": { what: "Factory reset", does: "asks twice, then empties everything" },

  // ── The log viewer ──────────────────────────────────────────────────────
  "logs.panel": { what: "the log viewer's panel", does: "keeps a click inside it from closing the viewer", guard: true },
  "logs.close.backdrop": { what: "the dimmed area around the log viewer", does: "closes it" },
  "logs.close": { what: "the close button in the log viewer", does: "closes it" },
  "logs.filter": { what: "the log filter box", does: "keeps only the lines containing the text" },
  "logs.autoRefresh": { what: "the auto-refresh checkbox", does: "stops and restarts the three-second reload" },

  // ── The token prompt ────────────────────────────────────────────────────
  "auth.token": { what: "the API token prompt's field", does: "holds the token, and enables Unlock" },
  "auth.submit": { what: "the token prompt itself", does: "checks the token, and says so when it is refused" },
} as const satisfies Record<string, Action>;

export type ActionId = keyof typeof ACTIONS;

/** The same table, widened: `as const` gives every row its own literal type,
 *  which is what makes `ActionId` exhaustive, but it also means a lookup
 *  through a variable key has no common shape to read `guard` off. */
export const INVENTORY: Record<ActionId, Action> = ACTIONS;

export const ACTION_IDS = Object.keys(ACTIONS) as ActionId[];

/** The guards, for the recorder: their handler runs for every event that passes
 *  through them, which is not true of an ordinary control's. */
export const GUARD_IDS = ACTION_IDS.filter((id) => INVENTORY[id].guard === true);
