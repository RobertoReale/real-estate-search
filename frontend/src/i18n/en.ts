/** English dictionary — the source of truth for the key set.
 *
 *  Keys are flat and namespaced by area (`nav.`, `app.`, `filters.`, …).
 *  `it.ts` is typed as `typeof en`, so adding a key here and forgetting it
 *  there is a build error, not a half-translated screen.
 *
 *  Placeholders are `{name}` and are interpolated by `translate()`.
 */
export const en = {
  // ── shared vocabulary ───────────────────────────────────────────────────
  "common.save": "Save",
  "common.saving": "Saving…",
  "common.cancel": "Cancel",
  "common.close": "Close",
  "common.open": "Open",
  "common.delete": "Delete",
  "common.edit": "Edit",
  "common.restore": "Restore",
  "common.loading": "Loading…",
  "common.refresh": "Refresh",
  "common.retry": "Try again",
  "common.yes": "Yes",
  "common.no": "No",
  "common.all": "All",
  "common.none": "None",
  "common.any": "Any",
  "common.contract": "Contract",
  "common.unknownError": "Unknown error",
  "common.optional": "optional",
  "common.of": "of",
  "common.copy": "Copy",
  "common.copied": "Copied",
  "common.showMore": "Show more",
  "common.showLess": "Show less",
  "common.sale": "Sale",
  "common.rent": "Rent",
  "common.buy": "Buy",
  "common.unknown": "Unknown",
  "common.notAvailable": "N/A",
  "common.perMonthSuffix": "/month",
  "common.sqmPrice": "{value} €/sqm",
  "common.rooms": "{count} rooms",
  "common.sqm": "{value} sqm",

  // ── property card ───────────────────────────────────────────────────────
  "card.medianIn": "Median in this {scope}: {value} €/sqm",
  "card.scopeZone": "neighborhood",
  "card.scopeCity": "city",
  "card.belowAverage": "{pct}% below {scope} average",
  "card.aboveAverage": "{pct}% above {scope} average",
  "card.matchBadge": "{score}% match",
  "card.matchBadgeTitle": "Compatibility with your dream-home settings",
  "card.dealScore": "Deal Score",
  "card.dealBelowMarket": "{pct}% below market",
  "card.dealAboveMarket": "{pct}% above market",
  "card.new": "new",
  "card.newTitle": "First appeared since your last visit to the dashboard",
  "card.rent": "rent",
  "card.mergedListings": "{count} merged listings",
  "card.email": "email",
  "card.emailTitle": "Imported from your email inbox (not from a monitored search)",
  "card.deselect": "Deselect",
  "card.selectForBatch": "Select for batch check",
  "card.removeFavorite": "Remove from favorites",
  "card.addFavorite": "Add to favorites",
  "card.hideTitle": "Hide this property (it will never come back on its own)",
  "card.hideAria": "Hide this property",
  "card.filteredReason": "Filtered: {reason}",
  "card.noLongerAvailable": "No longer available",
  "card.sold": "Sold",
  "card.rentedOut": "Rented out",
  "card.untitled": "Untitled",
  "card.locationUnknown": "Location N/A",
  "card.notes": "notes",
  "card.notOnMap": "not on map",
  "card.notOnMapTitle":
    "No map coordinates yet — this listing won't appear on the map or inside a drawn zone until located (open it and use 'View on map', or run 'Find coordinates').",
  "card.commuteTitle": "Travel time to {name}",

  // ── price benchmarks (the two references, side by side, never merged) ────
  "benchmark.title": "Price benchmarks",
  "benchmark.askingLabel": "What similar listings ask",
  "benchmark.askingScope": "median in this {scope}",
  "benchmark.omiSaleLabel": "What the tax authority records sales at",
  "benchmark.omiRentLabel": "What the tax authority records rents at",
  "benchmark.range": "{min}–{max} €/sqm",
  "benchmark.rangeMonthly": "{min}–{max} €/sqm per month",
  "benchmark.omiSource": "OMI zone {zone} · {semester}",
  "benchmark.note":
    "Asking prices sit systematically above recorded ones: read the two side by side, never averaged.",
  "benchmark.semesterFirst": "1st half {year}",
  "benchmark.semesterSecond": "2nd half {year}",
  "benchmark.stale": "out of date",
  "benchmark.staleNote":
    "This band is more than 18 months old — the Agenzia publishes twice a year, so a newer supply is available.",
  // The wording the OMI licence asks for, so it stays in Italian in both
  // dictionaries: an attribution is a credit to reproduce, not a caption.
  "benchmark.attribution": "Fonte: Agenzia Entrate – OMI",

  // ── commute units (shared by the card and the detail) ───────────────────
  "commute.minutes": "{count} min",
  "commute.hours": "{count} h",
  "commute.hoursMinutes": "{hours} h {minutes} min",
  "commute.metres": "{count} m",
  "commute.kilometres": "{count} km",

  // ── the property detail ─────────────────────────────────────────────────
  "detail.previous": "Previous result (k, or the left arrow)",
  "detail.next": "Next result (j, or the right arrow)",
  "detail.position": "{position} of {total}",
  "detail.locateFailed":
    "Could not place this property — the portal's location is too vague to find coordinates for it.",
  "detail.locateError": "Could not locate this property",
  "detail.checkGone": "Removed / Gone (404)",
  "detail.checkOnline": "Online (just verified)",
  "detail.checkUnknown": "Could not verify (blocked by the portal or timeout)",
  "detail.checkError": "Error during the online check",
  "detail.notesError": "Could not save notes",
  "detail.dealScoreTitle": "Deal Score:",
  "detail.dealBelowLocal": "below the local market",
  "detail.dealAboveLocal": "above the local market",
  "detail.suggestedProposal": "Suggested proposal:",
  "detail.dealDisclaimer":
    "An estimate from the area's median €/sqm, the listing's condition cues, and the agency's usual discount — a starting point for your own judgement, not an appraisal.",
  "detail.foundListings": "Found listings ({count})",
  "detail.priceHistory": "Price history",
  "detail.commute": "Commute",
  "detail.foundBySearch": "Found by search",
  "detail.foundBySearches": "Found by {count} searches",
  "detail.notLinked": "Not linked to any monitored search — imported from your inbox.",
  "detail.tags": "Tags",
  "detail.notes": "Personal notes",
  "detail.notesPlaceholder":
    'e.g. "called agent on Monday — viewing scheduled for Friday", "needs 15k renovation"',
  "detail.saveNotes": "Save notes",
  "detail.description": "Description",
  "detail.checkOnlineButton": "Check if still online",
  "detail.checkOnlineTitle":
    "Probes the portal URL right now to verify if this listing is still online or removed (404)",
  "detail.viewOnMap": "View on map",
  "detail.viewOnMapTitle": "Open this property on the map",
  "detail.locateAndViewTitle": "Find this property's coordinates and open it on the map",
  "detail.restore": "Restore property",
  "detail.restoreGone":
    'Restore this property? Use this if the availability check marked it "no longer available" by mistake.',
  "detail.restoreSold":
    "Restore this property? Use this if you marked it sold by mistake — it goes back to active lists.",
  "detail.restoreHidden": "Restore this property? It will appear in active lists again.",
  "detail.restoreFailed": "Restore failed",
  "detail.markSold": "Mark sold",
  "detail.markRented": "Mark rented",
  "detail.confirmSold":
    "Mark this property as sold? It leaves the active lists but is kept as a confirmed sale for market statistics.",
  "detail.confirmRented":
    "Mark this property as rented out? It leaves the active lists but is kept as a confirmed close for market statistics.",
  "detail.markSoldFailed": "Mark sold failed",
  "detail.hide": "Hide property",
  "detail.hideFailed": "Hide failed",

  // ── the property detail: the optional listing audit ─────────────────────
  "audit.title": "What the listing says",
  "audit.button": "Read the listing",
  "audit.reading": "Reading…",
  "audit.again": "Ask again",
  "audit.buttonTitle":
    "Reads this ad's own text with your language model: extra costs, a sitting tenant, condition, points to raise when negotiating",
  "audit.failed": "The listing could not be read",
  "audit.condition": "Condition",
  "audit.conditionNew": "new build",
  "audit.conditionRenovated": "renovated",
  "audit.conditionGood": "good",
  "audit.conditionToRenovate": "needs renovation",
  "audit.conditionUnknown": "not stated",
  "audit.tenant": "Sitting tenant",
  "audit.tenantYes": "yes — sold with a tenant in place",
  "audit.tenantNo": "no",
  "audit.tenantUnknown": "not stated",
  "audit.costs": "Beyond the price",
  "audit.concerns": "Worth checking",
  "audit.negotiation": "Useful when negotiating",
  "audit.footer": "Read by {model} on {date}",
  "audit.stale": "The ad has changed since this reading — ask again for the current text.",
  "audit.disclaimer":
    "A re-reading of the ad's own words by a language model, not an appraisal or legal advice — check anything that matters with the agency.",

  // ── tag picker ──────────────────────────────────────────────────────────
  "tags.removeTag": 'Remove tag "{name}"',
  "tags.addTag": "Add tag",
  "tags.addTagButton": "+ tag",
  "tags.namePlaceholder": "Tag name…",
  "tags.create": '+ create "{name}"',

  // ── the shell: the header, the four destinations, the scan status ───────
  "nav.title": "Real Estate Search",
  "nav.subtitle": "Immobiliare.it + Idealista, without duplicates",
  "nav.primary": "Main navigation",
  "nav.skipToContent": "Skip to content",
  "nav.listings": "Listings",
  "nav.insights": "Insights",
  "nav.searches": "Searches",
  "nav.scanning": "Scan in progress…",
  "nav.paused": "Automatic scans paused",
  "nav.pausedShort": "Scans paused",
  "nav.nextScan": "Next automatic scan: {time}",
  "nav.nextScanShort": "Next scan {time}",
  "nav.scanNowShort": "Scan",
  "nav.scanNow": "Start Scan Now",
  "nav.scanNowAria": "Start scan now",
  "nav.running": "Running…",
  "nav.toLight": "Switch to light theme",
  "nav.toDark": "Switch to dark theme",
  "nav.viewLog": "View backend log",
  "nav.viewActivity": "What the scanner is doing",
  "nav.settings": "Settings",
  "nav.language": "Language",
  "nav.languageSwitchTo": "Switch to {language}",

  // ── the activity screen: the scan in flight, and the ones before it ─────
  "activity.liveTitle": "Scan in progress",
  "activity.idleTitle": "No scan running",
  "activity.idleBody":
    "Nothing is being fetched right now. What the last few scans did is below.",
  "activity.loading": "Reading what the scanner is doing…",
  "activity.start": "Scan now",
  "activity.lastFinished": "Last scan finished at {time}.",
  "activity.nextScan": "Next automatic scan: {time}",
  "activity.paused": "Automatic scans are paused.",
  "activity.searchOf": "Search {index} of {total}",
  // The phases. Anything a newer backend adds falls back to the vague one
  // rather than to the backend's own English.
  "activity.phaseStarting": "Starting the scan",
  "activity.phaseLocating": "Placing the new listings on the map",
  "activity.phaseFetching": "Reading the results, page {page}",
  "activity.phaseWaiting": "Pausing {seconds}s before the next page",
  "activity.phaseSaving": "Saving what came back",
  "activity.phaseScanning": "Scanning",
  "activity.waitingWhy":
    "The pause is deliberate: requesting pages back to back is what gets the portal to stop answering. Most of a scan is spent here.",
  "activity.pagesLabel": "Pages read",
  "activity.pageOf": "Page {done} of {total}",
  "activity.pageCount": "Page {page}",
  "activity.pagesUnknown": "the portal did not say how many there are",
  "activity.found": "{count} listings collected so far",
  "activity.foundOf": "{count} of {total} listings collected",
  "activity.transport": "Transport:",
  "activity.streamDown":
    "The live connection is unavailable, so this is being refreshed on a timer instead. It stays accurate, just less promptly.",

  "activity.journalTitle": "The last few scans",
  "activity.journalEmpty": "Nothing has been scanned yet",
  "activity.journalEmptyHint":
    "Every search that runs writes a line here: what it read, what it found and how it ended. It stays after the scan finishes.",
  "activity.outcomeOk": "Done",
  "activity.outcomeNoResults": "Nothing found",
  "activity.outcomeBlocked": "Blocked",
  "activity.outcomeError": "Failed",
  "activity.outcomeUnknown": "Finished",
  "activity.entryCounts": "{pages} pages, {listings} listings",
  "activity.modeFull": "full scan",
  "activity.modeQuick": "quick scan",
  "activity.stoppedBecause": "Stopped because {reason}.",

  "activity.diagnostics": "Diagnostics",
  "activity.diagnosticsBody":
    "The backend log is the line-by-line record of what the process did. It is the right place to look when the account above does not explain something.",
  "activity.openLog": "Open the log",

  // ── toasts: what failed, and what to do about it ────────────────────────
  "toast.region": "Messages",
  "toast.dismiss": "Dismiss this message",
  "toast.undo": "Undo",
  "toast.adviceUnreachable":
    "The backend is not answering. Check it is running — start.bat — and try again.",
  "toast.adviceServer":
    "The backend ran into a problem. Try again; if it keeps failing, the log has the detail.",
  "toast.adviceRefused":
    "The backend refused the request. Change what you asked for and try again.",
  "toast.adviceRetry": "Try again.",
  "toast.gridFailed":
    "The listings could not be refreshed — what is on screen is the last answer that arrived.",
  "toast.hidden": "Property hidden.",
  "toast.hiddenMany": "{count} properties hidden.",
  "toast.sold": "Marked as no longer on the market.",
  "toast.soldMany": "{count} marked as no longer on the market.",
  "toast.favoritedMany": "{count} added to favourites.",
  "toast.unfavoritedMany": "{count} removed from favourites.",
  "toast.hideFailed": "The property could not be hidden.",
  "toast.bulkFailed": "The selected properties could not be updated.",
  "toast.undoFailed": "That could not be undone.",
  "toast.favoriteFailed": "The favourite could not be updated.",
  "toast.tagFailed": "The tags could not be updated.",
  "toast.scanFailed": "The scan could not be started.",
  "toast.selectAllFailed": "The whole set of results could not be selected.",
  "toast.exportFailed": "The dossier could not be produced.",
  "toast.geocodeFailed": "The coordinate lookup could not be run.",
  "toast.settingsLoadFailed": "The settings could not be loaded.",
  "toast.settingsSaveFailed": "The settings could not be saved.",
  "toast.searchSaveFailed": "The search could not be saved.",
  "toast.searchUpdateFailed": "The searches could not be updated.",
  "toast.searchDeleteFailed": "The searches could not be deleted.",

  // ── dashboard shell ─────────────────────────────────────────────────────
  "app.noMatches": "Nothing collected matches these filters.",
  "app.noMatchesHint":
    "None of the {count} listings collected so far fit. Relax the filters — or send these criteria out to the portals, where they can find listings this machine has never seen.",
  "app.toPortals": "Search the portals for this",
  "app.welcome": "Nothing collected yet.",
  "app.welcomeHint":
    "A monitored search is what fills this page in — the guide sets the first one up in a couple of minutes.",
  "app.collectedNoneHint":
    "The searches are set up; the next scan is what fills this page in.",
  "app.addSearch": "Add a search",
  "app.showMoreCount": "Show more ({count} more)",
  "app.loadingResults": "Loading the results…",
  "app.resultsFailed": "The results could not be loaded",

  // ── the guided first run ────────────────────────────────────────────────
  "onboarding.title": "Getting started",
  "onboarding.intro":
    "Three short steps. You can leave at any point and pick it up again later.",
  "onboarding.stepWhat": "What this is",
  "onboarding.stepSearch": "Your first search",
  "onboarding.stepScan": "The first scan",
  "onboarding.next": "Next",
  "onboarding.back": "Back",
  "onboarding.skip": "Skip for now",
  "onboarding.done": "Go to the listings",
  "onboarding.whatTitle": "It watches the portals so you don't have to",
  "onboarding.whatBody":
    "Say once what you are looking for. The app reads Immobiliare.it and Idealista on a schedule, keeps every listing it finds, and tells you what is new and what has dropped in price.",
  "onboarding.whatKeeps":
    "Everything stays on this machine: the database is a file beside the app, and nothing leaves it apart from the requests to the portals themselves.",
  "onboarding.searchTitle": "Create your first search",
  "onboarding.searchBody":
    "Three ways to the same thing — take whichever suits you. You can add more searches afterwards, and change any of them.",
  "onboarding.wayAssistant": "Just describe it",
  "onboarding.wayAssistantBody":
    "Write what you want in a sentence and let the app turn it into a search.",
  "onboarding.wayBuilder": "Build a search",
  "onboarding.wayBuilderBody": "Fill in city, price and size on a form.",
  "onboarding.wayUrl": "Paste a URL",
  "onboarding.wayUrlBody":
    "Search on the portal itself, then paste the address of the results.",
  "onboarding.wayBack": "Choose a different way",
  "onboarding.urlTip": "Tip:",
  "onboarding.urlTipBody":
    "to use every portal filter (bathrooms, floor, elevator, energy class, exclude auctions…), set them on the portal and paste the URL — the app monitors exactly that search.",
  "onboarding.searchSaved": "Your search is saved.",
  "onboarding.scanTitle": "Run the first scan",
  "onboarding.scanBody":
    "The first run collects everything the portals have for your search right now. It is your baseline, so nothing is sent out for it; from then on you only hear about what changes.",
  "onboarding.scanStart": "Run the first scan",
  "onboarding.scanRunning": "Scanning…",
  "onboarding.scanIdle": "Nothing is running yet.",
  "onboarding.scanPatience":
    "Most of a scan is spent pausing between pages on purpose — that pause is what keeps the portals answering. You can leave this page; the scan carries on.",
  "onboarding.scanFound": "{count} collected so far",
  "onboarding.scanSearchOf": "Search {index} of {total}",
  "onboarding.setupBody":
    "Everything else is off until you switch it on: being told about a new listing, a second source, staying unblocked. Five short questions, all of them skippable.",
  "onboarding.setupOpen": "Set the rest up",
  "onboarding.phaseStarting": "Starting the scan",
  "onboarding.phaseLocating": "Placing the new listings on the map",
  "onboarding.phaseFetching": "Reading the results, page {page}",
  "onboarding.phaseWaiting": "Pausing before the next page",
  "onboarding.phaseSaving": "Saving what came back",

  // ── the capability setup ────────────────────────────────────────────────
  "setup.title": "Set up what you need",
  "setup.intro":
    "Five questions, grouped by what each one gets you. Nothing here is required — skip anything you don't want, and come back to it from Settings whenever you like.",
  "setup.optional": "Leave anything blank and it stays as it is. Nothing on this screen is required.",
  "setup.back": "Back",
  "setup.skip": "Skip for now",
  "setup.saveNext": "Save and continue",
  "setup.finish": "Save and finish",

  "setup.group.unblocked": "Staying unblocked",
  "setup.group.source": "A second source",
  "setup.group.told": "Being told",
  "setup.group.pace": "How much it fetches",
  "setup.group.engines": "The optional extras",

  "setup.body.unblocked":
    "The portals defend themselves against automated reading, and Immobiliare is the strict one: without help it answers with a block page instead of the results. Any one of these is enough — a cookie taken from your own browser, a scraping service, or proxies.",
  "setup.body.source":
    "Idealista publishes an official API. With a key it is read through that instead of through the site, which is both sanctioned and immune to the blocking above. Keys are free to request and take a couple of days to arrive.",
  "setup.body.told":
    "Otherwise the app collects quietly and you find out by opening it. Telegram is the quicker of the two to set up — talk to @BotFather, paste the token, and send your bot a message so it can find your chat id.",
  "setup.body.pace":
    "These already have sensible values. Raise them for more coverage per scan, lower them if a portal starts refusing — the delay between requests is the one that matters most.",
  "setup.body.engines":
    "None of this is needed for the app to work. Geocoding and travel times put listings on the map and measure the commute; a language model writes the summaries and reads a description into filters.",

  "setup.field.datadome_cookie": "DataDome cookie",
  "setup.hint.datadome_cookie":
    "From your browser on immobiliare.it: developer tools, Application, Cookies, the value named 'datadome'. It expires after a few hours.",
  "setup.field.datadome_auto_refresh": "Fetch that cookie automatically",
  "setup.hint.datadome_auto_refresh":
    "Opens a real browser in the background when the stored cookie is old, and takes a fresh one.",
  "setup.field.browser_engine": "Browser to use for it",
  "setup.hint.browser_engine":
    "Camoufox is harder for a portal to recognise; Chromium starts faster.",
  "setup.field.proxy_urls": "Proxies",
  "setup.hint.proxy_urls":
    "One per line, or separated by commas. Requests are spread across them.",
  "setup.field.scrape_api_key": "Scraping service key",
  "setup.hint.scrape_api_key":
    "A paid service that fetches the page for you. Works with ScraperAPI, ScrapingBee and Zyte.",
  "setup.field.scrape_api_mode": "When to use it",
  "setup.hint.scrape_api_mode":
    "Only after a direct request has been refused, or for every request.",

  "setup.field.idealista_api_key": "Idealista API key",
  "setup.hint.idealista_api_key": "The 'apikey' from the confirmation email.",
  "setup.field.idealista_api_secret": "Idealista API secret",
  "setup.hint.idealista_api_secret": "The 'secret' from the same email.",

  "setup.field.telegram_bot_token": "Telegram bot token",
  "setup.hint.telegram_bot_token": "What @BotFather answers with when you create a bot.",
  "setup.field.telegram_chat_id": "Telegram chat id",
  "setup.hint.telegram_chat_id":
    "Send your bot any message first, otherwise it is not allowed to write to you.",
  "setup.field.telegram_enabled": "Send me alerts on Telegram",
  "setup.hint.telegram_enabled": "New listings and price drops, as they are found.",
  "setup.field.smtp_host": "Mail server",
  "setup.hint.smtp_host": "For example smtp.gmail.com.",
  "setup.field.smtp_port": "Port",
  "setup.hint.smtp_port": "587 for STARTTLS, 465 for SSL.",
  "setup.field.smtp_user": "Mail username",
  "setup.hint.smtp_user": "Usually the full address.",
  "setup.field.smtp_password": "Mail password",
  "setup.hint.smtp_password":
    "With Gmail this is an app password, not your account password.",
  "setup.field.email_from": "Send from",
  "setup.hint.email_from": "The address the alerts appear to come from.",
  "setup.field.email_to": "Send to",
  "setup.hint.email_to": "Several addresses separated by commas are fine.",
  "setup.field.email_enabled": "Send me alerts by email",
  "setup.hint.email_enabled": "The same alerts as Telegram, in your inbox.",

  "setup.field.max_pages_per_search": "Pages per search",
  "setup.hint.max_pages_per_search":
    "How deep into the results each scan reads. Roughly 25 listings a page.",
  "setup.field.request_delay_seconds": "Seconds between requests",
  "setup.hint.request_delay_seconds":
    "The pause that keeps the portals answering. Below two seconds you will be refused sooner or later.",
  "setup.field.idealista_api_max_pages": "Pages per search on the Idealista API",
  "setup.hint.idealista_api_max_pages":
    "The free tier allows a hundred requests a month, so this is worth keeping low.",

  "setup.field.nominatim_url": "Geocoding server",
  "setup.hint.nominatim_url":
    "Turns an address into a point on the map. Leave blank to use the public OpenStreetMap one.",
  "setup.field.osrm_url": "Routing server",
  "setup.hint.osrm_url": "Measures the commute by car, on foot or by bike.",
  "setup.field.llm_base_url": "Language model endpoint",
  "setup.hint.llm_base_url":
    "Anything that speaks the OpenAI API, including a local one.",
  "setup.field.llm_api_key": "Language model key",
  "setup.hint.llm_api_key": "Not needed by a model running on this machine.",
  "setup.field.llm_model": "Model",
  "setup.hint.llm_model": "For example gpt-4o-mini.",

  "setup.option.auto": "Whichever is available",
  "setup.option.chromium": "Chromium",
  "setup.option.camoufox": "Camoufox",
  "setup.option.fallback": "Only when blocked",
  "setup.option.always": "Every request",

  "setup.detected.harvester": "Browser automation is installed",
  "setup.detected.noHarvester": "Browser automation is not installed",
  "setup.detected.camoufox": "Camoufox is installed",
  "setup.detected.cookie": "A cookie is stored, good for about {minutes} minutes",
  "setup.detected.noCookie": "No cookie stored yet",

  "setup.section.title": "Guided setup",
  "setup.section.pending": "These are still switched off:",
  "setup.section.allOn": "Everything the guided setup offers is switched on.",
  "setup.section.open": "Set the rest up",
  "setup.section.reopen": "Go through the setup again",

  // ── bulk selection bar ──────────────────────────────────────────────────
  "app.selectMultiple": "Select multiple properties",
  "app.closeMultiSelect": "Close multi-select",
  "app.selectAll": "Select all ({selected} of {total})",
  "app.hideSelected": "Hide selected ({count})",
  "app.hideSelectedTitle":
    "Hidden properties leave the dashboard for good and never come back on their own, even if a scan finds them again. Use Restore to bring one back.",
  "app.markSold": "Mark sold ({count})",
  "app.addFavorites": "Add to favorites",
  "app.removeFavorites": "Remove from favorites",
  "app.checkAvailability": "Check online availability ({count})",
  "app.checking": "Checking…",
  "app.stopping": "Stopping…",
  "app.stop": "Stop",
  "app.confirmHideOne":
    "Hide this property? It will never appear in lists or notifications again.",
  "app.confirmHideMany":
    "Hide {count} properties? They will disappear from lists and notifications (recoverable from Discarded → Restore).",
  "app.confirmSoldMany":
    "Mark {count} properties as sold/rented out? They leave the active lists but are kept as confirmed sales for the market statistics (recoverable from Sold → Restore).",
  "app.batchCheckFailed": "Batch check failed",

  // ── availability batch progress / summary ───────────────────────────────
  // The bar's own name, for a screen reader. Deliberately not the running
  // commentary beside it: that changes on every listing, and a bar renamed on
  // every tick is announced from the start on every tick.
  "app.checkProgressLabel": "Availability check",
  "app.checkProgress":
    "Checking listing {done} of {total} — {online} online, {gone} removed/sold",
  "app.checkProgressUnknown": ", {count} not verifiable",
  "app.checkStarting": "Starting check…",
  "app.checkPacingNote":
    "A safety pause runs between requests to protect the IP from DataDome blocks.",
  "app.checkTransport": "Transport: {transport}",
  "app.checkLastIssue": "Last issue from the portal: {error}",
  "app.summaryChecked": "Checked:",
  "app.summaryGone": "{count} removed or sold (moved to Gone)",
  "app.summaryOnline": "{count} still online",
  "app.summaryUnknown": " ({count} not verifiable from the portal)",
  "app.summaryCancelled":
    "Stopped — the rest of the selection was left unchecked. Select it again to resume.",
  "app.summaryAborted":
    "The portal blocked the requests: check stopped to protect the IP. Try again later.",
  "app.summaryAbortedService":
    "Ran via {transport}. The browser window setting is on, but a background Windows service has no desktop to show a window on. To solve a CAPTCHA yourself, stop the service and run the app normally (start.bat / serve.bat) for this check.",
  "app.summaryAbortedNoWindow":
    'Ran via {transport}. To solve a CAPTCHA yourself, enable both "Run the check through the browser" and "Show the browser window" in Settings (needs the browser engine installed).',
  "app.summaryCapped":
    "Per-run request limit reached: run the check again to continue with the rest.",

  // ── filter rail ─────────────────────────────────────────────────────────
  "filters.title": "Filters",
  "filters.show": "Show the filters",
  "filters.hide": "Hide the filters",
  "filters.railHint": "Everything that narrows the grid",
  "filters.collected": "{count} listings collected",
  "filters.active": "Active filters",
  "filters.chipValue": "{label}: {value}",
  "filters.chipRemove": "Remove the {label} filter",
  "filters.chipMerged": "Merged only",
  "filters.chipMapArea": "Map area",
  // Never "Search": this box looks inside what is already here, and a box
  // labelled with the verb is exactly what makes a filter read as a portal
  // search that never ran.
  "filters.keyword": "Keyword",
  "filters.keywordPlaceholder": "Narrow by zone, address, title, floor or ad text…",
  "filters.clearKeyword": "Clear the keyword",
  "filters.market": "Market",
  "filters.buy": "Buy",
  "filters.rent": "Rent",
  "filters.city": "City",
  "filters.cityPlaceholder": "e.g. Milan",
  "filters.zone": "Zone",
  "filters.zonePlaceholder": "e.g. Navigli",
  "filters.minPrice": "Min price €",
  "filters.maxPrice": "Max price €",
  "filters.perMonth": "/mo",
  "filters.minSqm": "Min sqm",
  "filters.maxSqm": "Max sqm",
  "filters.rooms": "Rooms",
  "filters.floor": "Floor",
  "filters.anyFloor": "Any floor",
  "filters.floorGround": "Ground floor",
  "filters.floorLow": "Low (1–2)",
  "filters.floorMid": "Middle (3–5)",
  "filters.floorHigh": "High (6+)",
  "filters.floorTop": "Top floor (attico/ultimo)",
  "filters.sortBy": "Sort by",
  "filters.sortNewest": "Newest",
  "filters.sortPriceAsc": "Price ascending",
  "filters.sortPriceDesc": "Price descending",
  "filters.sortSqmPrice": "Lowest €/sqm",
  "filters.sortMatch": "Best match",
  "filters.status": "Status",
  "filters.statusForSale": "For sale",
  "filters.statusForRent": "For rent",
  "filters.statusFiltered": "Filtered",
  "filters.statusGone": "Gone",
  "filters.statusSold": "Sold",
  "filters.statusRentedOut": "Rented out",
  "filters.statusHidden": "Discarded",
  "filters.statusAll": "All",
  "filters.origin": "Origin",
  "filters.originAll": "All sources",
  "filters.originScan": "Monitored search",
  "filters.originEmail": "Email import",
  "filters.tag": "Tag",
  "filters.allTags": "All tags",
  "filters.limitToSearch": "Limit to a search",
  "filters.limitToSearchTitle":
    "Show only the properties this saved search found (its 'Found by' provenance). Email imports, which no search found, drop out. This narrows the list — it does not reorder it.",
  "filters.allSearches": "All searches",
  "filters.priceDrops": "Price drops",
  "filters.favorites": "Favorites",
  "filters.more": "More filters",
  "filters.moreTitle": "More filters",
  "filters.moreHint": "· narrow the grid by portal, agency, deal quality or €/sqm",
  "filters.portal": "Portal",
  "filters.anyPortal": "Any portal",
  "filters.agency": "Agency",
  "filters.agencyPlaceholder": "e.g. Tecnocasa",
  "filters.deal": "Deal",
  "filters.anyDeal": "Any deal",
  "filters.dealUndervalued": "Undervalued only",
  "filters.dealFairPlus": "Fair or better",
  "filters.minSqmPrice": "Min €/sqm",
  "filters.maxSqmPrice": "Max €/sqm",
  "filters.mergedOnly": "Merged only (same home on several portals/agencies)",
  "filters.countProperties": "{count} properties",
  "filters.reset": "↺ Reset filters",
  "filters.resetTitle": "Clear every filter and go back to the default view",
  "filters.view": "View",
  "filters.viewGrid": "▦ Grid",
  "filters.viewMap": "Map",
  "filters.export": "Export",
  "filters.exportTitle": "Download the {count} filtered properties as {format}",
  "filters.exportPdfTitle":
    "Open a printable report of the {count} filtered properties — save it as PDF from the print dialog",
  "filters.exportFavorites": "Favorites",
  "filters.exportRentals": "Rentals",
  "filters.exportProperties": "Properties",
  "filters.exportIn": "{what} in {city}",

  // ── maintenance actions ─────────────────────────────────────────────────
  "maintenance.title": "Maintenance",
  "maintenance.hint":
    "Housekeeping for the whole database, not for one search. Neither of these changes what a scan looks for.",
  "maintenance.findCoords": "Find coordinates",
  "maintenance.locating": "Locating…",
  "maintenance.findCoordsTitle":
    "Find map coordinates for listings that have an address or zone but no pin (uses OpenStreetMap; can take a while)",
  "maintenance.retryFailed": "Retry failed lookups",
  "maintenance.clearing": "Clearing…",
  "maintenance.retryFailedTitle":
    "Forget failed geocoding lookups so 'Find coordinates' retries addresses a temporary OpenStreetMap outage froze as 'not found'. Never moves existing pins.",
  "maintenance.backendTooOld":
    "The backend doesn't have this feature yet — restart it (close and re-run start.bat / serve.bat) and try again.",

  // ── maintenance result banners ──────────────────────────────────────────
  "maintenance.geocodeRunning": "Locating coordinates in background…",
  "maintenance.geocodeProgressLabel": "Coordinate lookup",
  "maintenance.geocodeProgress":
    "Locating listing {done} of {total} — {geocoded} located, {cached} from cache",
  "maintenance.geocodeProgressNotFound": ", {count} not found",
  "maintenance.geocodeStarting": "Starting coordinate lookup…",
  "maintenance.geocodePacing":
    "(Paced at 1 request/sec to respect OpenStreetMap Nominatim usage policy)",
  "maintenance.geocodeLastIssue": "Last issue from Nominatim: {error}",
  "maintenance.geocodeDone": "Coordinate lookup finished",
  "maintenance.geocodeNothing":
    "Nothing to locate: every property either already has a pin or has no address/zone to look one up from. (A bare city is skipped on purpose — it would drop every such listing on one downtown pin.)",
  "maintenance.geocodeLocated": "Located {geocoded} of {scanned} listings without a pin",
  "maintenance.geocodeNotFound": " · {count} could not be resolved",
  "maintenance.geocodeCancelled":
    'Stopped — remaining properties were left without pins. Click "Find coordinates" again to resume.',
  "maintenance.geocodeRemaining": "{count} left — run it again to continue.",
  "maintenance.cacheClearedNone":
    "No stuck lookups to clear — every failed address had already been forgotten or never cached.",
  "maintenance.cacheCleared":
    "Cleared {count} failed lookups. Click Find coordinates to retry them.",
  "maintenance.cacheClearedOne":
    "Cleared {count} failed lookup. Click Find coordinates to retry it.",

  // ── settings: shell & secrets ───────────────────────────────────────────
  "settings.title": "Settings",
  "settings.testNote":
    "Each test button saves your changes first, so what it tests is exactly what you typed.",
  "settings.secretDirty": "Unsaved change — will replace the stored value",
  "settings.secretSaved": "Saved",
  "settings.secretSavedOn": "Saved · {date}",
  "settings.secretSavedTitle": "A value is currently stored",
  "settings.secretLastSaved": "Last saved: {date}",
  "settings.secretNotSet": "○ Not set",
  "settings.saved": "Settings saved.",
  "settings.loadFailed": "Could not load the settings: {error}",
  "settings.save": "Save settings",
  "settings.errCredentials":
    "{error} — the credentials were refused. With Gmail you must use a 16-character App password, not your normal password.",
  "settings.errNetwork": "{error} — could not reach the server. Check the host name and port.",

  // ── settings: telegram ──────────────────────────────────────────────────
  "settings.telegramTitle": "Telegram notifications",
  "settings.telegramHelp": "How do I set up Telegram? (step-by-step)",
  "settings.tgStep1": "Open Telegram and search for @BotFather.",
  "settings.tgStep2": 'Send "/newbot" and follow the prompts; copy the token it gives you.',
  "settings.tgStep3": "Paste the token below.",
  "settings.tgStep4":
    "Search for your new bot by name and send it any message (this authorizes it to write to you).",
  "settings.tgStep5":
    "Get your Chat ID: message @userinfobot and copy the number it replies with.",
  "settings.tgStep6": 'Paste the Chat ID below, tick "Enable", then press "Save & send test".',
  "settings.tokenSaved": "Token already saved (leave empty to keep)",
  "settings.tokenPlaceholder": "Bot token (from @BotFather)",
  "settings.chatIdPlaceholder": "Chat ID (e.g. 123456789)",
  "settings.enableTelegram": "Enable Telegram notifications",
  "settings.telegramActions": "Action buttons on notifications",
  "settings.telegramActionsHelp":
    "Adds Favourite, Seen, Hide and Map buttons under each property notification, so you can triage a listing from your phone. Favourite and Hide change the dashboard and can be tapped again to undo; Seen only dismisses the message.",
  "settings.sending": "Sending…",
  "settings.saveAndTest": "Save & send test",
  "settings.telegramTestSent": "Test message sent — check your Telegram chat.",

  // ── settings: email ─────────────────────────────────────────────────────
  "settings.emailTitle": "Email notifications",
  "settings.emailHelp": "How do I set up Email alerts? (works with Gmail)",
  "settings.emStep1":
    "For Gmail: host smtp.gmail.com, port 587, username = your Gmail address.",
  "settings.emStep2a": "Gmail needs an App password, not your normal password. It only exists once 2-Step Verification is on, so ",
  "settings.emStep2Link": "turn that on first",
  "settings.emStep2b":
    " — until you do, the App passwords page will say it is not available for your account.",
  "settings.emStep3a": "Then create one at ",
  "settings.emStep3b": " and paste the 16 characters below (spaces are ignored).",
  "settings.emStep4":
    "Recipient: the address where you want to receive alerts (it can be the same one).",
  "settings.emStep5": 'Tick "Enable", then press "Save & send test".',
  "settings.smtpHost": "SMTP host (e.g. smtp.gmail.com)",
  "settings.smtpPortTitle": "Port (587 STARTTLS, 465 SSL)",
  "settings.smtpUser": "SMTP username (email address)",
  "settings.passwordSaved": "Password saved (leave empty to keep)",
  "settings.appPassword": "App password (16 characters)",
  "settings.emailFrom": "Sender (optional, defaults to username)",
  "settings.emailTo": "Recipient (you@example.com)",
  "settings.enableEmail": "Enable email notifications",
  "settings.emailTestSent":
    "Test email sent to {to} — check your inbox (and the spam folder).",
  "settings.theRecipient": "the recipient",


  // ── settings: scanning ──────────────────────────────────────────────────
  "settings.scanTitle": "Automatic scan",
  "settings.frequency": "Frequency",
  "settings.every30m": "Every 30 minutes",
  "settings.everyHour": "Every hour",
  "settings.every2h": "Every 2 hours",
  "settings.every4h": "Every 4 hours",
  "settings.every8h": "Every 8 hours",
  "settings.pauseScans": "Pause automatic scans",
  "settings.pauseScansNote":
    'Stops scheduled scans from touching the portals — useful for resting the connection while you are away. "Scan now" still works on demand.',
  "settings.healthTitle": "Scraper health alerts",
  "settings.healthNote":
    "A broken scraper is silent: no listings looks exactly like a quiet market. Get notified when a search fails this many scans in a row. Portals block scrapers occasionally, so a value of 1 will cry wolf.",
  "settings.alertAfter": "Alert after",
  "settings.neverDisabled": "Never (disabled)",
  "settings.nFailures": "{count} consecutive failures",

  // ── settings: keywords & match score ────────────────────────────────────
  "settings.keywordsTitle": "Excluded keywords (global)",
  "settings.keywordsNote":
    "Listings containing these words are automatically discarded (whole words only, accents ignored). Separate with commas. Each search profile can add its own extra keywords on top of these.",
  "settings.matchTitle": "Smart Match Score (dream home)",
  "settings.matchEnable":
    "Show a compatibility % on each card, scored against the wishes below",
  "settings.matchNote":
    "Every field is optional — leave a number at 0 to ignore it. Only the wishes you fill in count towards the score. Nothing leaves your PC.",
  "settings.dreamMaxPrice": "Max price (€)",
  "settings.dreamMinRooms": "Min rooms",
  "settings.dreamMinSqm": "Min sqm",
  "settings.dreamMinFloor": "Min floor",
  "settings.dreamFeatures":
    "Desired features (comma-separated, e.g. balcone, ascensore, terrazzo)",
  "settings.dreamZones": "Preferred zones or cities (comma-separated)",

  // ── settings: commute times ─────────────────────────────────────────────
  "settings.commuteTitle": "Commute times",
  "settings.commuteEnable": "Show travel time from each property to the places below",
  "settings.commuteNote":
    "Work, the university, the nearest metro stop — routed offline-friendly through OpenStreetMap. Times appear on a card only after you press Compute below, and only for listings that already have map coordinates.",
  "settings.commutePointName": "Label",
  "settings.commutePointNamePlaceholder": "Work",
  "settings.commutePointAddress": "Address",
  "settings.commutePointAddressPlaceholder": "Via Dante 5, Milano",
  "settings.commutePointMode": "By",
  "settings.commuteMode.car": "Car",
  "settings.commuteMode.foot": "On foot",
  "settings.commuteMode.bike": "Bike",
  "settings.commuteAddPoint": "Add a place",
  "settings.commuteRemovePoint": "Remove this place",
  "settings.commuteOsrmUrl": "Routing server (OSRM)",
  "settings.commuteOsrmNote":
    "Leave blank for the public demo server. It is built on the driving network alone, so “on foot” and “bike” are routed as a car there — point this at your own OSRM for true walking and cycling times.",
  "settings.commuteCompute": "Compute commute times now",
  "settings.commuteComputing": "Computing…",
  "settings.commuteComputeNote":
    "One request per property to {url}, paced at one per second and cached, so a second run only covers what is new.",
  "settings.commuteComputed": "Routed {routed} legs across {scanned} properties",
  "settings.commuteRemaining": " · {count} left, run it again to continue",

  // ── settings: assistant backend ─────────────────────────────────────────
  "settings.assistantTitle": "Search assistant backend",
  "settings.assistantNote":
    'How the "describe your search in words" box turns text into a search. The default parser is offline and instant. An LLM understands freer phrasing; it falls back to the offline parser on any error, and nothing else on your PC ever leaves it.',
  "settings.backendBuiltin": "Built-in parser (offline, default)",
  "settings.backendLlm": "LLM (OpenAI-compatible / local Ollama)",
  "settings.llmHintA": "For a free, fully-offline model install ",
  "settings.llmHintB": " and use base URL ",
  "settings.llmHintC": " with a model like ",
  "settings.llmHintD": " (no key needed).",
  "settings.llmBaseUrl": "Base URL (e.g. http://localhost:11434/v1)",
  "settings.llmModel": "Model (e.g. llama3.1)",
  "settings.llmKeySaved": "API key saved (leave empty to keep)",
  "settings.llmKeyPlaceholder": "API key (blank for local Ollama)",
  "settings.auditTitle": "Read listing texts (optional)",
  "settings.auditEnable": "Let the model read a listing when I ask",
  "settings.auditNote":
    "Adds a “Read the listing” button to a property's detail view: the model reports what the ad's text says about extra costs, a sitting tenant, the condition, and what is usable when negotiating. Nothing is read automatically — one press, one listing, using the same model configured above. Answers are remembered, so opening the card again is free.",

  // ── settings: scraping & bypass ─────────────────────────────────────────
  "settings.scrapingTitle": "Advanced Scraping & Bypass",
  "settings.scrapingHelp": "How to resolve DataDome blocks? (instructions)",
  "settings.ddStep1": "DataDome blocks raw HTTP requests to individual ad pages on your home IP.",
  "settings.ddStep2":
    "Option A: Set a Proxy URL (e.g. socks5://127.0.0.1:9050 for Tor, or an HTTP/HTTPS proxy) below to route scraper traffic.",
  "settings.ddStep3Intro": "Option B: Copy the datadome cookie value from your web browser:",
  "settings.ddStep3a": "Open a portal ad page (e.g., Immobiliare.it) in Chrome/Firefox.",
  "settings.ddStep3b": "Press F12, go to the Application (Chrome) or Storage (Firefox) tab.",
  "settings.ddStep3c":
    "Under Cookies, select the portal domain, find datadome, and copy its value.",
  "settings.ddStep3d":
    "Paste it in the Cookie field below. Note: it will expire after a few hours.",
  "settings.proxyUrl": "Proxy URL (HTTP/HTTPS/SOCKS5)",
  "settings.proxyUrlPlaceholder": "e.g. socks5://127.0.0.1:9050",
  "settings.proxyPool": "Proxy pool (optional, one URL per line)",
  "settings.proxyPoolNote":
    "With more than one proxy, a blocked exit IP is rested for a while and the next attempt leaves through a different one — one burned address no longer takes every scan down with it.",
  "settings.idealistaApiTitle": "Idealista official API",
  "settings.idealistaApiNote":
    "Optional, and the only option here that is not a workaround: with a key and secret, Idealista searches ask the portal for its own data instead of reading its pages, so nothing can block them. Keys are issued by hand after you describe your project at",
  "settings.idealistaKeySaved": "Key already saved (leave empty to keep)",
  "settings.idealistaKeyPlaceholder": "API key",
  "settings.idealistaSecretSaved": "Secret already saved (leave empty to keep)",
  "settings.idealistaSecretPlaceholder": "API secret",
  "settings.idealistaMaxPages": "Requests per search, per scan",
  "settings.idealistaMaxPagesNote":
    "Each one returns up to 50 listings and counts against the monthly quota agreed for your key — so the default is a single request. Raise it once you know your own limit. Searches the API cannot express exactly (a neighbourhood, a room count, a feature filter) keep using the normal scraper, and so does anything the API refuses.",
  "settings.scrapeApiTitle": "Scraping API (solves DataDome for you)",
  "settings.scrapeApiNote":
    "Optional. With a provider key set, scans route each portal page through the provider — which returns the already-solved HTML — so blocks stop hitting your home IP. Free tiers (~1,000 calls/month) can cover a small personal scanner. Leave empty to keep the local (free, offline) path.",
  "settings.scrapeKeySaved": "Key already saved (leave empty to keep)",
  "settings.scrapeKeyPlaceholder": "Provider API key",
  "settings.whenToUse": "When to use it",
  "settings.modeFallback": "Only as a fallback when the free path is blocked",
  "settings.modeAlways": "Always (every fetch goes through the provider)",
  "settings.modeNote":
    '"Fallback" (the default) spends your API credits only during an actual outage: scans start on the free local path and escalate when blocked.',
  "settings.cookieLabel": "DataDome Cookie",
  "settings.cookieSaved": "Cookie already saved (leave empty to keep)",
  "settings.cookiePlaceholder": "Paste datadome cookie value",

  // ── settings: cookie harvester & browser ────────────────────────────────
  "settings.harvestTitle": "Grab the cookie automatically",
  "settings.harvestNote":
    "Opens a local browser, earns a fresh cookie, and saves it — no copy/paste. A window may open: if the portal shows a CAPTCHA, solve it once and it is remembered next time.",
  "settings.grabCookie": "Grab a fresh cookie now",
  "settings.openingBrowser": "Opening browser…",
  "settings.cookieGrabbed": "Fresh DataDome cookie saved ({preview}).",
  "settings.autoRefreshCookie": "Refresh the cookie automatically before each scan (headless)",
  "settings.browserFirst":
    'Run the "still online?" check through the browser instead of fast requests — slower per ad, but it holds a real cookie so DataDome does not interrupt it with 403 blocks.',
  "settings.browserHeadful":
    "Show the browser window during the check so you can solve a CAPTCHA by hand if one appears — one solve unblocks the whole run. Works best together with the option above. Ignored when the app runs as a background Windows service.",
  "settings.browserHumanize":
    "Move the mouse and scroll like a person on every browser page — anti-bot systems also score behavior, and a page visited with zero pointer events looks robotic. Adds about a second per page.",
  "settings.browserEngine": "Browser engine:",
  "settings.engineAuto": "Auto (Camoufox if installed, else Chromium)",
  "settings.engineCamoufox": "Camoufox (stealth Firefox)",
  "settings.engineChromium": "Chromium",
  "settings.camoufoxNote":
    "Camoufox is a stealth Firefox that hides the automation signals DataDome looks for, so the check is challenged far less often.",
  "settings.camoufoxInstalled": "Installed",
  "settings.camoufoxMissing": "Not installed — one-click adds it (~150 MB, one time):",
  "settings.installCamoufox": "One-Click Install Camoufox",
  "settings.installingCamoufox": "Installing Camoufox (~1-3 min)…",
  "settings.camoufoxInstalledMsg": "Camoufox installed successfully!",
  "settings.harvesterMissing":
    "Not installed yet in this Python environment. You can install Playwright and Chromium automatically with one click:",
  "settings.installHarvester": "One-Click Install Playwright & Chromium",
  "settings.installingHarvester": "Installing Playwright & Chromium (~1-2 min)…",
  "settings.harvesterInstalledMsg": "Playwright & Chromium installed successfully!",
  "settings.manualInstall":
    "Or install manually from terminal using `install-playwright.bat` inside the project folder, or run: ",

  // ── settings: API token & backend restart ───────────────────────────────
  "settings.apiTokenTitle": "API access token",
  "settings.apiTokenNote":
    "By default the dashboard is reachable by anyone who can reach its address (that is why it binds to localhost). Set a token to require it on every request — then it is safe to expose the app on your LAN or Tailscale. Leave empty to keep it open. You stay logged in on this device; other devices are asked for the token once.",
  "settings.apiTokenPlaceholder": "No token (open access)",
  "settings.backendTitle": "Backend",
  "settings.backendNote":
    "Restart the backend process — use this after updating the app so new features take effect, instead of closing and re-opening the terminal window. The dashboard goes offline for a few seconds and then reloads on its own.",
  "settings.restart": "Restart backend",
  "settings.restarting": "Restarting… (waiting for the backend)",
  "settings.restartConfirm":
    "Restart the backend now? The dashboard is unavailable for a few seconds, then reloads itself.",
  "settings.restartTooOld":
    "This running backend is too old to restart itself — close its terminal window and re-run start.bat / serve.bat once. After that this button (and the newest features) will work.",
  "settings.restartNoReturn":
    "The backend did not come back on its own — check its terminal window (or re-run start.bat / serve.bat).",

  // ── settings: backups ───────────────────────────────────────────────────
  "settings.backupsTitle": "Backups",
  "settings.backupsNote":
    "A copy of your database is taken once a day, and again before an update changes its structure. Download one to keep it somewhere else, or put one back — restoring replaces everything you have now, so a copy of the current state is saved first.",
  "settings.backupsFolder": "They are kept in {folder}",
  "settings.backupsEmpty": "No copies yet — the first one is taken the next time the app starts.",
  "settings.backupTakeNow": "Take a copy now",
  "settings.backupImport": "Bring one in",
  "settings.backupDownload": "Download",
  "settings.backupRestore": "Restore this one",
  "settings.backupKind.daily": "Daily copy",
  "settings.backupKind.pre-upgrade": "Taken before an update",
  "settings.backupKind.imported": "Brought in from another install",
  "settings.backupSchema": "schema {revision}",
  "settings.backupSchemaUnknown": "schema unreadable",
  "settings.backupTaken": "Copy saved: {name}",
  "settings.backupImported":
    "Added as {name}. It is not in use yet — press “Restore this one” on it to switch to it.",
  "settings.restoreConfirmWord": "RESTORE",
  "settings.restoreConfirm":
    "Restore the copy from {date}? Everything currently in the database is replaced by it (a copy of the current state is saved first). Type {word} to confirm.",
  "settings.restoreDone": "Restored {name}. Reloading…",
  "settings.restoreDoneBackup":
    "Restored {name} · what it replaced was saved as {backup}. Reloading…",

  // ── settings: data management ───────────────────────────────────────────
  "settings.dataTitle": "Data management",
  "settings.dataNote": "Irreversible. Your notification and login settings are always kept.",
  "settings.clearDashboardName": "Clear dashboard",
  "settings.clearDashboardBody":
    " — delete all found properties and price history. Your search profiles stay; the next scan rebuilds the grid silently.",
  "settings.clearDashboardButton": "Clear dashboard",
  "settings.clearDashboardConfirm":
    "Delete ALL properties and their price history? Search profiles are kept and the next scan will rebuild the dashboard.",
  "settings.clearTrendsName": "Clear price trends",
  "settings.clearTrendsBody":
    " — remove the daily median history behind the trend charts, without touching any listing.",
  "settings.clearTrendsButton": "Clear trends",
  "settings.clearTrendsConfirm":
    "Delete the stored price-trend history? The charts will start over from the next scan.",
  "settings.factoryName": "Factory reset",
  "settings.factoryBody":
    " — wipe everything (dashboard, profiles, imports, trends) back to a fresh install. A backup of the database is saved first.",
  "settings.factoryButton": "Factory reset",
  "settings.factoryConfirm":
    "Factory reset: this deletes the dashboard, ALL search profiles, imports and trends. A backup is saved first. Continue?",
  "settings.lastChance": "Last chance: this erases everything and cannot be undone. Continue?",
  "settings.resetDone": "Done — removed {removed}. Reloading…",
  "settings.resetDoneBackup": "Done — removed {removed} · backup saved: {backup}. Reloading…",
  "settings.resetNothing": "nothing",

  // ── monitored searches: arriving here from the grid's filters ───────────
  "handoff.title": "Started from the filters you had on Listings",
  "handoff.lead":
    "A search goes out to the portals, so it cannot ask for everything a filter can. This is what came across, and what did not.",
  "handoff.carried": "Carried over",
  "handoff.approximated": "Carried over, widened",
  "handoff.dropped": "Not carried over",
  "handoff.item": "{label} — {note}",
  "handoff.noteRooms": "the portals take a minimum number of rooms, not an exact one",
  "handoff.noteMaxSqm": "a portal search takes a minimum size only",
  "handoff.noteText":
    "free text reads listings already collected; a portal search asks by place, price and size",
  "handoff.notePortal": "neither portal can search on it",
  "handoff.noteLocal":
    "it describes listings already on this machine, which the portals know nothing about",
  "handoff.noteArea":
    "an area drawn on the map has no portal equivalent — name the city and the zone instead",

  // ── monitored searches: shell & modes ───────────────────────────────────
  "profiles.title": "Monitored searches",

  // A search's state, in one word. "Paused" wins over everything: a search that
  // is off is not working and not failing, it is not running.
  "profiles.healthWorking": "Running",
  "profiles.healthQuiet": "No matches",
  "profiles.healthBlocked": "Blocked by the portal",
  "profiles.healthFailing": "Not working",
  "profiles.healthPaused": "Paused",
  "profiles.healthUnrun": "Never run",
  "profiles.modeAssistant": "Just describe it",
  "profiles.modeBuilder": "Build a search",
  "profiles.modeUrl": "Paste a URL",
  "profiles.emptyTitle": "No searches configured",
  "profiles.empty":
    "Build a search with your criteria, or paste a results URL from Immobiliare.it / Idealista, to get started.",
  "profiles.loadFailed": "The searches could not be loaded",
  "profiles.untitled": "Untitled search",
  "profiles.defaultName": "Monitored search",
  "profiles.labelRent": "Rent",
  "profiles.labelBuy": "Buy",
  "profiles.labelRooms": "{count}+ rooms",

  // ── monitored searches: feature/floor/condition options ─────────────────
  "profiles.featBalcony": "Balcony",
  "profiles.featGarden": "Garden",
  "profiles.featParking": "Garage / parking",
  "profiles.featElevator": "Lift",
  "profiles.featExcludeAuctions": "Exclude auctions",
  "profiles.featPool": "Swimming pool",
  "profiles.floorAny": "Any floor",
  "profiles.floorGround": "Ground floor",
  "profiles.floorMiddle": "Middle floors",
  "profiles.floorTop": "Top floor",
  "profiles.condAny": "Any condition",
  "profiles.condNew": "New build",
  "profiles.condGood": "Good / habitable",
  "profiles.condExcellent": "Excellent / renovated",
  "profiles.condToRenovate": "Needs renovation",
  "profiles.unsupportedFloor": "this floor band",
  "profiles.unsupportedCondition": "this condition",
  "profiles.unsupportedMaxRooms":
    "a cap of 5 or more rooms (its largest bucket is “5 or more”)",

  // ── monitored searches: notification channels ───────────────────────────
  "profiles.chAll": "All channels",
  "profiles.chTelegram": "Telegram only",
  "profiles.chTelegramOff": "Telegram only (not set up)",
  "profiles.chEmail": "Email only",
  "profiles.chEmailOff": "Email only (not set up)",
  "profiles.chNone": "No notifications",

  // One banner for the account, at the top of the page: what is missing, and a
  // link to where it is fixed. The remedy is a link, not a sentence.
  "profiles.channelsNone":
    "No notification channel is set up: the searches that ask for one keep collecting listings, but they will not alert you.",
  "profiles.channelsTelegram":
    "Telegram is not set up: the searches that notify by Telegram keep collecting listings, but they will not alert you.",
  "profiles.channelsEmail":
    "Email is not set up: the searches that notify by email keep collecting listings, but they will not alert you.",
  "profiles.channelsFix": "Set up notifications",

  // ── monitored searches: assistant ───────────────────────────────────────
  "profiles.assistantIntro":
    'Describe what you are looking for in plain Italian or English — even several alternatives at once ("bilocale in zona X o trilocale in zona Y"). The text is parsed on your PC — nothing is sent to any AI service — and you review every search before it is saved.',
  "profiles.assistantPlaceholder":
    "e.g. trilocale in affitto a Milano sotto i 1.200 € al mese",
  "profiles.assistantReading": "Reading…",
  "profiles.assistantSubmit": "Understand it →",
  "profiles.assistantTry": "Try:",
  "profiles.assistantNothing":
    "There was nothing to read in that. Describe what you are looking for — a city at least.",
  "profiles.multiIntro":
    "I read {count} alternative searches in your sentence. Check each one (open the links to verify the results), then create all the profiles at once.",
  "profiles.reword": "Reword",
  "profiles.searchNumber": "Search {n}",
  "profiles.editInBuilder": "Adjust this search in the builder form",
  "profiles.dropAlternative": "Drop this alternative",
  "profiles.createProfiles": "Create {count} profiles",
  "profiles.allAlreadyPresent": "Every selected search is already monitored.",
  "profiles.duplicateExists":
    "An identical monitored search ('{name}') already exists with the same URL and excluded keywords.",
  "profiles.duplicateParams":
    "An identical monitored search already exists for the selected parameters.",

  // ── monitored searches: URL form ────────────────────────────────────────
  "profiles.urlIntro":
    "Go to Immobiliare.it or Idealista, set zone and filters on the map, then copy the results page URL here.",
  "profiles.urlTip":
    "This is how you use every portal filter — bathrooms, floor, elevator, terrace, energy class, property type, exclude auctions, and so on. Set them on the portal, then paste the URL: the app monitors exactly that search. The two helpers above (\"Just describe it\" / \"Build a search\") only cover city, price, rooms and surface.",
  "profiles.namePlaceholder": "Name (e.g. 3 rooms South Milan)",
  "profiles.keywordsPlaceholder": "Extra excluded keywords (optional, comma-separated)",
  "profiles.urlPlaceholder":
    "https://www.immobiliare.it/vendita-case/milano/?prezzoMassimo=300000…",
  "profiles.extractParams": "Extract parameters",
  "profiles.extractParamsTitle": "Extract city and filters into the Builder form",
  "profiles.saveChanges": "Save changes",
  "profiles.saveProfile": "Save profile",

  // ── monitored searches: builder form ────────────────────────────────────
  "profiles.understood": "I understood:",
  "profiles.checkFields": "Check the fields below — correct anything the parser got wrong.",
  "profiles.builderIntroPrefix":
    "Pick your criteria and the correct portal search URLs are generated for you — no copy/paste from the browser needed. This covers the basics (city, price, rooms, surface); for bathrooms, floor, features or energy class, set them on the portal and use ",
  "profiles.builderIntroSuffix": " instead.",
  "profiles.cityRequired": "City *",
  "profiles.province": "Province",
  "profiles.provinceTitle":
    "Idealista needs the province; leave empty if the city is a province capital",
  "profiles.optional": "(optional)",
  "profiles.zoneTitle":
    "Neighborhood, best-effort: open the generated URLs to check the portal recognises it",
  "profiles.minRooms": "Min rooms",
  "profiles.moreCriteria": "More criteria",
  "profiles.moreCriteriaHint": "· applied to both portals",
  "profiles.condition": "Condition",
  "profiles.builderTipPrefix":
    "Need bathrooms, terrace, energy class, property type or another filter? Set it on the portal and ",
  "profiles.builderTipLink": "paste the results URL",
  "profiles.builderTipSuffix": " instead — that captures every filter the portal offers.",
  "profiles.profileNamePlaceholder": "Profile name (optional)",
  "profiles.generate": "Generate search URLs",
  "profiles.generating": "Checking the zone on Idealista…",
  "profiles.checkGenerated":
    "Check the generated searches (open them to verify the results), then create the profiles:",
  "profiles.zoneKnown": "Idealista knows the “{zone}” zone: using its exact zone page.",
  "profiles.zoneUnknown":
    "Idealista has no zone page for “{zone}”, so this searches its name as text — expect some listings from outside the zone that merely mention it.",
  "profiles.idealistaUnsupported":
    "Idealista has no search filter for {filters}, so its half of this pair is the wider search — expect listings there that Immobiliare filters out.",
  "profiles.createProfilesButton": "Create profiles",

  // ── monitored searches: bulk bar & rows ─────────────────────────────────
  "profiles.selectAll": "Select all",
  "profiles.selectRow": "Select {name}",
  "profiles.selectedCount": "{count} selected",
  "profiles.activate": "Activate",
  "profiles.pause": "Pause",
  "profiles.notificationsAction": "Notifications →",
  "profiles.deleteAction": "Delete",
  "profiles.mergeSelected": "Merge selected",
  "profiles.mergeSelectedTitle": "Merge the selected portals into a single search box",
  "profiles.mergePrompt":
    "Enter the single name to merge the selected searches under one box:",
  "profiles.clearSelection": "Clear",
  "profiles.merged": "Merged ({count} portals)",
  "profiles.mergedTitle": "Searches across several portals merged into one box",
  "profiles.separateConfirm": 'Separate the portals of "{name}" into distinct search boxes?',
  "profiles.excludesTitle":
    "Listings mentioning any of these words are discarded (Settings + this search's own extras)",
  "profiles.excludes": "Excludes: {words}",
  "profiles.globalKeywords": "Always excluded for every search (from Settings): {words}",
  "profiles.notifyTitle": "Where to send notifications for this search",
  "profiles.notifyFor": "Notifications for {name}",
  "profiles.active": "Active",
  "profiles.editBox": "Edit this search box",
  "profiles.separateBox": "Separate the portals into independent boxes",
  "profiles.deleteBox": "Delete this search box (all its portals)",
  "profiles.chipRent": "Rent",
  "profiles.chipBuy": "Buy",
  "profiles.chipRooms": "{range} rooms",
  "profiles.chipMinSqm": "≥ {value} sqm",

  // ── monitored searches: delete dialog ───────────────────────────────────
  "profiles.deleteOne": "Delete “{name}”?",
  "profiles.deleteGroup": "Delete “{name}” ({count} portals)?",
  "profiles.deleteBodyOne":
    "The search stops being monitored. Its results are already in the dashboard — you choose whether they go too.",
  "profiles.deleteBodyMany":
    "The searches stop being monitored. Their results are already in the dashboard — you choose whether they go too.",
  "profiles.countingResults": "Counting the results…",
  "profiles.noneAttributableOne":
    "No property in the dashboard is attributable to this search, so “delete the results too” has nothing to delete. Results are attributed from the scans that found them: a search deleted before it has run keeps nothing on record.",
  "profiles.noneAttributableMany":
    "No property in the dashboard is attributable to these searches, so “delete the results too” has nothing to delete. Results are attributed from the scans that found them: a search deleted before it has run keeps nothing on record.",
  "profiles.foundOne": "It found {tracked} properties; {deletable} would be deleted.",
  "profiles.foundMany": "They found {tracked} properties; {deletable} would be deleted.",
  "profiles.keptShared": "· {count} kept: also found by a search you are keeping",
  "profiles.keptCurated": "· {count} kept: favorited or annotated by you",
  "profiles.deleteIrreversible": "Deleting them is irreversible: price history included.",
  "profiles.keepResults": "Keep the results",
  "profiles.deleting": "Deleting…",
  "profiles.deleteWith": "Delete with {count} properties",

  // ── map view ────────────────────────────────────────────────────────────
  "map.pinDrop": "Price drop",
  "map.pinFavorite": "Favorite",
  "map.pinFiltered": "Filtered",
  "map.pinGone": "No longer available",
  "map.pinSold": "Sold / rented out",
  "map.pinActive": "Active listing",
  "map.pinApproximate": "{count} placed approximately",
  "map.pinApproximateTitle":
    "The listing did not carry coordinates and its address could not be resolved, so it sits at the centre of the area it belongs to — not at its address.",
  "map.approximateZone": "Approximate: centre of the area, not the address",
  "map.onMap": "{shown} of {total} properties on the map",
  "map.missing": "{count} without coordinates",
  "map.missingTitle":
    "Portals do not publish coordinates for every listing; those properties are still in the grid view.",
  "map.cluster": "{count} properties here — click to zoom in",
  "map.clustered": "Overlapping pins grouped",
  "map.clusteredTitle":
    "There are more pins than the map can keep apart, so the ones on top of each other are drawn as one numbered circle. Click a circle, or zoom in, to break it up.",
  "map.drawHint": "Draw a radius or an area to filter by where they are.",
  "map.guideRadiusTitle": "Drawing a radius",
  "map.guideRadiusStep1": "Click the map where the centre goes.",
  "map.guideRadiusStep2":
    "Drag the blue square out to the distance you want — the filter applies when you let go.",
  "map.guideAreaTitle": "Drawing an area",
  "map.guideAreaStep1": "Click each corner of the area, in order round its edge.",
  "map.guideAreaStep2":
    "From the third corner on, double-click the map — or press “Finish area” — to close it and filter.",
  "map.drawRadius": "◯ Draw radius",
  "map.drawingRadius": "◯ Click centre, drag handle…",
  "map.drawRadiusTitle":
    "Click the map to set the centre, then drag the handle to size the radius.",
  "map.drawArea": "Draw area",
  "map.finishArea": "Finish area",
  "map.drawAreaTitle":
    "Click to add each corner; double-click or press Finish to close the area.",
  "map.polyHint": "{count} point(s) — need ≥ 3, then double-click to close",
  "map.clearZone": "Clear zone",
  "map.radiusActive": "Radius {km} km active",
  "map.areaActive": "Area filter active",
  "map.zoneWarning":
    "Zone filter active — {count} properties without coordinates can’t be placed and are excluded.",
  "map.zoneWarningOne":
    "Zone filter active — {count} property without coordinates can’t be placed and is excluded.",
  "map.findCoordinates": "Find coordinates",
  "map.findingCoordinates": "Finding coordinates…",
  "map.noneGeolocated":
    "None of the current properties has coordinates yet — run a scan, or switch back to the grid view.",
  "map.attribution":
    "Click a pin to open the property. Map data © OpenStreetMap contributors (tiles are fetched online).",

  // ── insights (the screen the three analysis panels share) ───────────────
  "insights.empty": "Nothing to analyse yet",
  "insights.emptyHint":
    "Scraper health, market velocity and price trends are all built from what the scans collect. Save a search first and this screen fills itself in.",

  // ── market velocity ─────────────────────────────────────────────────────
  "velocity.title": "Market velocity",
  "velocity.subtitleSale": "how fast listings leave the market, and how agencies price them",
  "velocity.subtitleRent": "how fast rentals leave the market, and how agencies price them",
  "velocity.loadFailed": "Could not load statistics",
  "velocity.tracked": "{count} properties tracked",
  "velocity.inCity": " in “{city}”",
  "velocity.left": ", {count} left the market",
  "velocity.confirmedSold": " ({count} confirmed sold)",
  "velocity.observedSince": " · observed since {date}",
  "velocity.minSample":
    ". Areas and agencies with fewer than {count} observations are not shown.",
  "velocity.empty":
    "Not enough history yet. These signals need at least {count} properties per area and a few weeks of scans before they mean anything — the database is still filling up.",
  "velocity.areasTitle": "Neighborhoods",
  "velocity.areasHint": "(fastest-moving first)",
  "velocity.colArea": "Area",
  "velocity.colTracked": "Tracked",
  "velocity.colDaysToExit": "Days to exit",
  "velocity.colDaysToExitTitle":
    "Median days between the first time a scan saw the listing and the day it disappeared",
  "velocity.colStillListed": "Still listed",
  "velocity.colStillListedTitle":
    "Median days the still-online listings have been sitting there",
  "velocity.colLeftMarket": "Left market",
  "velocity.colLeftMarketTitle": "Share of tracked properties that left the market",
  "velocity.colCutPrice": "Cut price",
  "velocity.colCutPriceTitle":
    "Share of tracked properties whose price dropped at least once",
  "velocity.wholeCity": "whole city",
  "velocity.agenciesTitle": "Agencies",
  "velocity.agenciesHint": "(who asks above the local median, and who discounts)",
  "velocity.colAgency": "Agency",
  "velocity.colListings": "Listings",
  "velocity.colVsArea": "vs area €/sqm",
  "velocity.colVsAreaTitle":
    "Median €/sqm compared to the median of the same neighborhood. Positive = asks more than the area.",
  "velocity.colAgencyCutTitle":
    "Share of this agency's listings whose price dropped at least once",
  "velocity.colTypicalCut": "Typical cut",
  "velocity.colTypicalCutTitle":
    "Median discount among the listings that were actually reduced",
  "velocity.caveat":
    "“Left market” means no scan has seen the listing for a week: sold, rented, withdrawn, or republished under a new id — not proof of a sale. Days-on-market are counted from the day this app first saw the listing, so properties that were already online when you added the search look younger than they are. Both distortions fade as the database ages.",

  // ── price trends ────────────────────────────────────────────────────────
  "trends.title": "Price trends",
  "trends.subtitle": "how the median €/sqm has moved over time in your tracked areas",
  "trends.wholeCity": "{city} · whole city",
  "trends.areaOption": "{label} ({days} days)",
  "trends.chartAria": "Median price per square meter over time",
  "trends.pointTooltip": "{date}: {value} €/sqm",
  "trends.areasFailed": "Could not load trends",
  "trends.trendFailed": "Could not load trend",
  "trends.listingsFailed": "Could not load the listings",
  "trends.empty":
    "No history to chart yet. The app records one median per area per day; a trend line needs at least two days of scans before it means anything — come back in a couple of days.",
  "trends.chartEmpty": "Nothing recorded for this area",
  "trends.chartEmptyHint":
    "The medians are written once a day, at the end of a scan. The first point appears after the next one runs.",
  "trends.changeSince": "{pct}% since {date}",
  "trends.caveat":
    "Median asking price per square meter among the listings this app was tracking each day — your own sample, not the whole market. It moves with what you monitor as much as with prices.",
  "trends.oneDayOnly":
    "Only one day recorded for this area so far — the line appears once there are at least two.",
  "trends.showComparables": "Show the listings behind this median",
  "trends.hideComparables": "Hide the listings behind this median",
  "trends.comparablesEmpty": "No priced listings in this area right now.",
  "trends.comparablesNote":
    "The {count} listings currently priced in this area — the live set today's median is computed from. Earlier points on the chart kept only their count, so their exact listings can no longer be shown. Click one to open its details.",
  "trends.comparablesNoteOne":
    "The {count} listing currently priced in this area — the live set today's median is computed from. Earlier points on the chart kept only their count, so their exact listings can no longer be shown. Click it to open its details.",
  "trends.vsMedian": " ({sign}{pct}% vs median)",

  // ── backend log viewer ──────────────────────────────────────────────────
  "logs.title": "Backend log",
  "logs.filterPlaceholder": "Filter (e.g. availability_check, blocked, error)",
  "logs.autoRefresh": "Auto-refresh (3s)",
  "logs.lineCount": "{visible} / {total} lines",
  "logs.loadFailed": "Failed to load logs",
  "logs.empty": "No log lines yet — this fills up once a scan or check runs.",
  "logs.noMatch": "No lines match this filter.",
  "logs.source": "Source: {path}",

  // ── scraper health ──────────────────────────────────────────────────────
  "health.title": "Scraper health",
  "health.subtitle": "is the anti-bot pipeline still getting through?",
  "health.loadFailed": "Could not load scraper health",
  "health.window":
    "Last {days} days of scan outcomes per portal. Next scan starts on: {transport}.",
  "health.empty": "No scans recorded yet — this fills in as scans run.",
  "health.historyTitle": "History — how past scans went, day by day",
  "health.colPortal": "Portal",
  "health.colDays": "Days (oldest → today)",
  "health.noDays": "no days recorded",
  "health.colScans": "Scans",
  "health.colFailureRate": "Failure rate",
  "health.colFailureRateTitle":
    "Share of scans that came back blocked or in error over the window",
  "health.colTransport": "Last transport",
  "health.legend":
    "Green day = every scan ok · amber = some failed · red = all failed. Hover a day for the exact counts.",
  "health.dayAllOk": "all scans ok",
  "health.dayNone": "no scans",
  "health.dayAllFailed": "every scan failed",
  "health.daySomeFailed": "some scans failed",
  "health.dayLabel": "{date}: {state} — {attempts} scans, {blocked} blocked, {errors} errors",
  "health.failingTitle": "Right now — searches still failing",
  "health.failingSubtitle":
    "The current unbroken streak, not a running total: it clears the moment a scan gets through.",
  "health.failingRow": "({portal}) — {count} consecutive {status} scans",
  "health.failingStatusFallback": "failed",
  "health.failingHint":
    "A short streak is routine (transient anti-bot blocks). A long one means the free path is down: consider a proxy pool or a scrape-API key in Settings.",

  // ── calculators (the property detail) ───────────────────────────────────
  "calc.mortgageTitle": "Mortgage estimator",
  "calc.downPayment": "Down payment",
  "calc.interestRate": "Interest rate",
  "calc.perYear": "%/yr",
  "calc.duration": "Duration",
  "calc.years": "years",
  "calc.loanAmount": "Loan amount",
  "calc.monthlyPayment": "Monthly payment",
  "calc.yieldTitle": "Rental yield (investment)",
  "calc.expectedRent": "Expected rent",
  "calc.perMonthUnit": "€/mo",
  "calc.costsVacancy": "Costs & vacancy",
  "calc.percentOfRent": "% of rent",
  "calc.grossYield": "Gross yield",
  "calc.netYield": "Net yield",
  "calc.cashFlow": "Cash flow vs mortgage",
  "calc.enterRent":
    "Enter the rent you expect to charge to see gross/net yield and monthly cash flow (rent minus the mortgage payment above).",

  // ── error boundary / auth gate ──────────────────────────────────────────
  "error.title": "Something went wrong displaying the page.",
  "error.dataSafe": "Your data is safe on the backend — reloading is enough.",
  "error.reload": "⟳ Reload",
  "auth.title": "Authentication required",
  "auth.hint": "This dashboard is protected by an API token. Enter it to continue.",
  "auth.placeholder": "API token",
  "auth.rejected": "That token was not accepted. Check it and try again.",
  "auth.checking": "Checking…",
  "auth.unlock": "Unlock",

  // ── floor labels (utils/format) ─────────────────────────────────────────
  "floor.ground": "ground floor",
  "floor.raised": "raised ground floor",
  "floor.basement": "basement",
  "floor.numbered": "floor {floor}",
  // `satisfies` (not `as const`): the keys stay literal so `t()` is typo-proof,
  // while the values widen to `string` — otherwise `it: typeof en` would demand
  // the Italian text be character-identical to the English.
} satisfies Record<string, string>;
