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
  "common.optional": "optional",
  "common.of": "of",
  "common.dismissError": "Dismiss error",
  "common.actionFailed": "Action failed",
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
  "card.matchBadge": "🎯 {score}% match",
  "card.matchBadgeTitle": "Compatibility with your dream-home settings",
  "card.dealScore": "Deal Score",
  "card.dealBelowMarket": "🎯 {pct}% below market",
  "card.dealAboveMarket": "🎯 {pct}% above market",
  "card.new": "🆕 new",
  "card.newTitle": "First appeared since your last visit to the dashboard",
  "card.rent": "🔑 rent",
  "card.mergedListings": "{count} merged listings",
  "card.email": "✉️ email",
  "card.emailTitle": "Imported from your email inbox (not from a monitored search)",
  "card.deselect": "Deselect",
  "card.selectForBatch": "Select for batch check",
  "card.removeFavorite": "Remove from favorites",
  "card.addFavorite": "Add to favorites",
  "card.hideTitle": "Hide this property (it will never come back on its own)",
  "card.hideAria": "Hide this property",
  "card.filteredReason": "🚫 Filtered: {reason}",
  "card.noLongerAvailable": "💨 No longer available",
  "card.sold": "🔑 Sold",
  "card.rentedOut": "🔑 Rented out",
  "card.untitled": "Untitled",
  "card.locationUnknown": "Location N/A",
  "card.notes": "📝 notes",
  "card.notOnMap": "🗺️✗ not on map",
  "card.notOnMapTitle":
    "No map coordinates yet — this listing won't appear on the map or inside a drawn zone until located (open it and use 'View on map', or run 'Find coordinates').",

  // ── property modal ──────────────────────────────────────────────────────
  "modal.locateFailed":
    "Could not place this property — the portal's location is too vague to find coordinates for it.",
  "modal.locateError": "Could not locate this property",
  "modal.checkGone": "🔴 Removed / Gone (404)",
  "modal.checkOnline": "🟢 Online (just verified)",
  "modal.checkUnknown": "⚠️ Could not verify (blocked by the portal or timeout)",
  "modal.checkError": "Error during the online check",
  "modal.notesError": "Could not save notes",
  "modal.dealScoreTitle": "🎯 Deal Score:",
  "modal.dealBelowLocal": "below the local market",
  "modal.dealAboveLocal": "above the local market",
  "modal.suggestedProposal": "💬 Suggested proposal:",
  "modal.dealDisclaimer":
    "An estimate from the area's median €/sqm, the listing's condition cues, and the agency's usual discount — a starting point for your own judgement, not an appraisal.",
  "modal.foundListings": "Found listings ({count})",
  "modal.open": "Open ↗",
  "modal.priceHistory": "Price history",
  "modal.foundBySearch": "🔍 Found by search",
  "modal.foundBySearches": "🔍 Found by {count} searches",
  "modal.notLinked": "🔍 Not linked to any monitored search — imported from your inbox.",
  "modal.tags": "🏷️ Tags",
  "modal.notes": "📝 Personal notes",
  "modal.notesPlaceholder":
    'e.g. "called agent on Monday — viewing scheduled for Friday", "needs 15k renovation"',
  "modal.saveNotes": "Save notes",
  "modal.description": "Description",
  "modal.checkOnlineButton": "🔎 Check if still online",
  "modal.checkOnlineTitle":
    "Probes the portal URL right now to verify if this listing is still online or removed (404)",
  "modal.viewOnMap": "🗺️ View on map",
  "modal.viewOnMapTitle": "Open this property on the map",
  "modal.locateAndViewTitle": "Find this property's coordinates and open it on the map",
  "modal.restore": "👁 Restore property",
  "modal.restoreGone":
    'Restore this property? Use this if the availability check marked it "no longer available" by mistake.',
  "modal.restoreSold":
    "Restore this property? Use this if you marked it sold by mistake — it goes back to active lists.",
  "modal.restoreHidden": "Restore this property? It will appear in active lists again.",
  "modal.restoreFailed": "Restore failed",
  "modal.markSold": "🔑 Mark sold",
  "modal.markRented": "🔑 Mark rented",
  "modal.confirmSold":
    "Mark this property as sold? It leaves the active lists but is kept as a confirmed sale for market statistics.",
  "modal.confirmRented":
    "Mark this property as rented out? It leaves the active lists but is kept as a confirmed close for market statistics.",
  "modal.markSoldFailed": "Mark sold failed",
  "modal.hide": "🙈 Hide property",
  "modal.hideFailed": "Hide failed",

  // ── tag picker ──────────────────────────────────────────────────────────
  "tags.removeTag": 'Remove tag "{name}"',
  "tags.addTag": "Add tag",
  "tags.addTagButton": "+ tag",
  "tags.namePlaceholder": "Tag name…",
  "tags.create": '+ create "{name}"',

  // ── navbar ──────────────────────────────────────────────────────────────
  "nav.title": "Real Estate Search",
  "nav.subtitle": "Immobiliare.it + Idealista, without duplicates",
  "nav.scanning": "⏳ Scan in progress…",
  "nav.paused": "⏸ Automatic scans paused",
  "nav.nextScan": "Next automatic scan: {time}",
  "nav.scanNowShort": "▶ Scan",
  "nav.scanNow": "▶ Start Scan Now",
  "nav.scanNowAria": "Start scan now",
  "nav.running": "Running…",
  "nav.toLight": "Switch to light theme",
  "nav.toDark": "Switch to dark theme",
  "nav.viewLog": "View backend log",
  "nav.settings": "Settings",
  "nav.language": "Language",
  "nav.languageSwitchTo": "Switch to {language}",

  // ── dashboard shell ─────────────────────────────────────────────────────
  "app.backendUnreachable":
    "Backend unreachable on http://localhost:8000 — start it with start.bat",
  "app.noMatches": "No properties match the current filters.",
  "app.noMatchesHint": "Try switching the Buy/Rent toggle or relaxing the filters.",
  "app.welcome": "Welcome! Three steps to get started:",
  "app.step1":
    'Add a search above — describe it in words with "💬 Just describe it", build one with "🧭 Build a search", or paste a results URL from Immobiliare.it / Idealista.',
  "app.step1Tip": "Tip:",
  "app.step1TipBody":
    'to use every portal filter (bathrooms, floor, elevator, energy class, exclude auctions…), set them on the portal and use "🔗 Paste a URL" — the app monitors exactly that search.',
  "app.step2":
    'Press "▶ Start Scan Now" — the first scan builds your baseline (no notification flood).',
  "app.step3":
    "Optional: open ⚙️ Settings to enable Telegram or Email alerts for new listings and price drops.",
  "app.showMoreCount": "Show more ({count} more)",

  // ── bulk selection bar ──────────────────────────────────────────────────
  "app.selectMultiple": "☐ Select multiple properties",
  "app.closeMultiSelect": "✕ Close multi-select",
  "app.selectAll": "Select all ({selected} of {total})",
  "app.hideSelected": "🙈 Hide selected ({count})",
  "app.hideSelectedTitle":
    "Hidden properties leave the dashboard for good and never come back on their own, even if a scan finds them again. Use Restore to bring one back.",
  "app.markSold": "🔑 Mark sold ({count})",
  "app.addFavorites": "⭐ Add to favorites",
  "app.removeFavorites": "❌ Remove from favorites",
  "app.checkAvailability": "🔎 Check online availability ({count})",
  "app.checking": "⏳ Checking…",
  "app.stopping": "⏳ Stopping…",
  "app.stop": "⏹ Stop",
  "app.confirmHideOne":
    "Hide this property? It will never appear in lists or notifications again.",
  "app.confirmHideMany":
    "Hide {count} properties? They will disappear from lists and notifications (recoverable from 🙈 Discarded → Restore).",
  "app.confirmSoldMany":
    "Mark {count} properties as sold/rented out? They leave the active lists but are kept as confirmed sales for the market statistics (recoverable from 🔑 Sold → Restore).",
  "app.batchCheckFailed": "Batch check failed",

  // ── availability batch progress / summary ───────────────────────────────
  "app.checkProgress":
    "Checking listing {done} of {total} — {online} online, {gone} removed/sold",
  "app.checkProgressUnknown": ", {count} not verifiable",
  "app.checkStarting": "Starting check…",
  "app.checkPacingNote":
    "A safety pause runs between requests to protect the IP from DataDome blocks.",
  "app.checkTransport": "Transport: {transport}",
  "app.checkLastIssue": "Last issue from the portal: {error}",
  "app.summaryChecked": "🔎 Checked:",
  "app.summaryGone": "{count} removed or sold (moved to Gone)",
  "app.summaryOnline": "{count} still online",
  "app.summaryUnknown": " ({count} not verifiable from the portal)",
  "app.summaryCancelled":
    "⏹ Stopped — the rest of the selection was left unchecked. Select it again to resume.",
  "app.summaryAborted":
    "⚠️ The portal blocked the requests: check stopped to protect the IP. Try again later.",
  "app.summaryAbortedService":
    "Ran via {transport}. The browser window setting is on, but a background Windows service has no desktop to show a window on. To solve a CAPTCHA yourself, stop the service and run the app normally (start.bat / serve.bat) for this check.",
  "app.summaryAbortedNoWindow":
    'Ran via {transport}. To solve a CAPTCHA yourself, enable both "Run the check through the browser" and "Show the browser window" in Settings (needs the browser engine installed).',
  "app.summaryCapped":
    "Per-run request limit reached: run the check again to continue with the rest.",

  // ── filters bar ─────────────────────────────────────────────────────────
  "filters.search": "Search",
  "filters.searchPlaceholder": "Search by zone, address, title, floor or ad text…",
  "filters.clearSearch": "Clear search",
  "filters.market": "Market",
  "filters.buy": "🏠 Buy",
  "filters.rent": "🔑 Rent",
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
  "filters.sortMatch": "🎯 Best match",
  "filters.status": "Status",
  "filters.statusForSale": "For sale",
  "filters.statusForRent": "For rent",
  "filters.statusFiltered": "🚫 Filtered",
  "filters.statusGone": "💨 Gone",
  "filters.statusSold": "🔑 Sold",
  "filters.statusRentedOut": "🔑 Rented out",
  "filters.statusHidden": "🙈 Discarded",
  "filters.statusAll": "All",
  "filters.origin": "Origin",
  "filters.originAll": "All sources",
  "filters.originScan": "🔎 Monitored search",
  "filters.originEmail": "✉️ Email import",
  "filters.tag": "Tag",
  "filters.allTags": "All tags",
  "filters.limitToSearch": "Limit to a search",
  "filters.limitToSearchTitle":
    "Show only the properties this saved search found (its 'Found by' provenance). Email imports, which no search found, drop out. This narrows the list — it does not reorder it.",
  "filters.allSearches": "All searches",
  "filters.priceDrops": "📉 Price drops",
  "filters.favorites": "⭐ Favorites",
  "filters.more": "⚙️ More filters",
  "filters.moreTitle": "More filters",
  "filters.moreHint": "· narrow the grid by portal, agency, deal quality or €/sqm",
  "filters.portal": "Portal",
  "filters.anyPortal": "Any portal",
  "filters.agency": "Agency",
  "filters.agencyPlaceholder": "e.g. Tecnocasa",
  "filters.deal": "Deal",
  "filters.anyDeal": "Any deal",
  "filters.dealUndervalued": "💎 Undervalued only",
  "filters.dealFairPlus": "👍 Fair or better",
  "filters.minSqmPrice": "Min €/sqm",
  "filters.maxSqmPrice": "Max €/sqm",
  "filters.mergedOnly": "🔗 Merged only (same home on several portals/agencies)",
  "filters.countProperties": "{count} properties",
  "filters.reset": "↺ Reset filters",
  "filters.resetTitle": "Clear every filter and go back to the default view",
  "filters.view": "View",
  "filters.viewGrid": "▦ Grid",
  "filters.viewMap": "🗺 Map",
  "filters.export": "Export",
  "filters.exportTitle": "Download the {count} filtered properties as {format}",
  "filters.exportFavorites": "Favorites",
  "filters.exportRentals": "Rentals",
  "filters.exportProperties": "Properties",
  "filters.exportIn": "{what} in {city}",

  // ── maintenance actions ─────────────────────────────────────────────────
  "filters.maintenance": "Maintenance",
  "filters.repair": "🛠️ Repair data",
  "filters.repairing": "⏳ Repairing…",
  "filters.repairTitle":
    "Instantly repair missing titles, zones and photos on previously imported listings",
  "filters.findCoords": "📍 Find coordinates",
  "filters.locating": "⏳ Locating…",
  "filters.findCoordsTitle":
    "Find map coordinates for listings that have an address or zone but no pin (uses OpenStreetMap; can take a while)",
  "filters.retryFailed": "🧹 Retry failed lookups",
  "filters.clearing": "⏳ Clearing…",
  "filters.retryFailedTitle":
    "Forget failed geocoding lookups so 'Find coordinates' retries addresses a temporary OpenStreetMap outage froze as 'not found'. Never moves existing pins.",
  "filters.backendTooOld":
    "The backend doesn't have this feature yet — restart it (close and re-run start.bat / serve.bat) and try again.",

  // ── maintenance result banners ──────────────────────────────────────────
  "filters.repairDone": "Repair completed successfully!",
  "filters.repairSummary":
    "Updated {properties} properties, {listings} listings and recovered {images} photos.",
  "filters.repairMerged":
    "Merged {merged} duplicate cards and removed {removed} duplicate listings pointing at the same ad.",
  "filters.repairNothing": "Everything is in order and fully in sync!",
  "filters.repairNothingBody":
    "The check scanned the database: no property or listing with missing data, city (`Location N/A`), photos, or duplicate ad links was found to repair. Every listing is already complete and aligned.",
  "filters.geocodeRunning": "Locating coordinates in background…",
  "filters.geocodeProgress":
    "Locating listing {done} of {total} — {geocoded} located, {cached} from cache",
  "filters.geocodeProgressNotFound": ", {count} not found",
  "filters.geocodeStarting": "Starting coordinate lookup…",
  "filters.geocodePacing":
    "(Paced at 1 request/sec to respect OpenStreetMap Nominatim usage policy)",
  "filters.geocodeLastIssue": "Last issue from Nominatim: {error}",
  "filters.geocodeDone": "Coordinate lookup finished",
  "filters.geocodeNothing":
    "Nothing to locate: every property either already has a pin or has no address/zone to look one up from. (A bare city is skipped on purpose — it would drop every such listing on one downtown pin.)",
  "filters.geocodeLocated": "Located {geocoded} of {scanned} listings without a pin",
  "filters.geocodeNotFound": " · {count} could not be resolved",
  "filters.geocodeCancelled":
    '⏹ Stopped — remaining properties were left without pins. Click "Find coordinates" again to resume.',
  "filters.geocodeRemaining": "{count} left — run it again to continue.",
  "filters.cacheClearedNone":
    "No stuck lookups to clear — every failed address had already been forgotten or never cached.",
  "filters.cacheCleared":
    "🧹 Cleared {count} failed lookups. Click 📍 Find coordinates to retry them.",
  "filters.cacheClearedOne":
    "🧹 Cleared {count} failed lookup. Click 📍 Find coordinates to retry it.",

  // ── settings: shell & secrets ───────────────────────────────────────────
  "settings.title": "⚙️ Settings",
  "settings.testNote":
    "Each test button saves your changes first, so what it tests is exactly what you typed.",
  "settings.secretDirty": "✎ Unsaved change — will replace the stored value",
  "settings.secretSaved": "✓ Saved",
  "settings.secretSavedOn": "✓ Saved · {date}",
  "settings.secretSavedTitle": "A value is currently stored",
  "settings.secretLastSaved": "Last saved: {date}",
  "settings.secretNotSet": "○ Not set",
  "settings.saved": "Settings saved.",
  "settings.saveFailed": "Could not save settings: {error}",
  "settings.save": "Save settings",
  "settings.errCredentials":
    "{error} — the credentials were refused. With Gmail you must use a 16-character App password, not your normal password.",
  "settings.errNetwork": "{error} — could not reach the server. Check the host name and port.",

  // ── settings: telegram ──────────────────────────────────────────────────
  "settings.telegramTitle": "📨 Telegram notifications",
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
  "settings.sending": "Sending…",
  "settings.saveAndTest": "Save & send test",
  "settings.telegramTestSent": "Test message sent — check your Telegram chat.",

  // ── settings: email ─────────────────────────────────────────────────────
  "settings.emailTitle": "✉️ Email notifications",
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

  // ── settings: IMAP ──────────────────────────────────────────────────────
  "settings.imapTitle": "📥 Email inbox import (IMAP)",
  "settings.imapHelp": "What is this? How do I set it up? (works with Gmail)",
  "settings.imStep1":
    "Lets the dashboard mine your own inbox for old Immobiliare.it / Idealista alert emails and import those listings for review.",
  "settings.imStep2":
    "Strictly read-only: the app never modifies, marks or deletes your emails, and nothing appears in the dashboard until you accept it.",
  "settings.imStep3": "For Gmail: host imap.gmail.com, port 993, username = your Gmail address.",
  "settings.imStep4": "Password: the same 16-character App password as the email section above.",
  "settings.imStep5":
    'Press "Save & test connection", then use the "📥 Import from email" panel in the dashboard.',
  "settings.imapHost": "IMAP host (e.g. imap.gmail.com)",
  "settings.imapPortTitle": "Port (993 SSL)",
  "settings.imapUser": "IMAP username (email address)",
  "settings.readOnlyNote": "Read-only access: your mailbox is never modified.",
  "settings.connecting": "Connecting…",
  "settings.saveAndTestConnection": "Save & test connection",
  "settings.autoImport": "Re-scan the inbox automatically for new listing emails",
  "settings.rescanFrequency": "Re-scan frequency",
  "settings.every6h": "Every 6 hours",
  "settings.every12h": "Every 12 hours",
  "settings.onceADay": "Once a day",
  "settings.every3d": "Every 3 days",
  "settings.onceAWeek": "Once a week",
  "settings.autoImportNote":
    'New listings are staged silently in the "📥 Import from email" review queue — you are not notified, and nothing appears in the dashboard until you accept it.',

  // ── settings: scanning ──────────────────────────────────────────────────
  "settings.scanTitle": "🔄 Automatic scan",
  "settings.frequency": "Frequency",
  "settings.every30m": "Every 30 minutes",
  "settings.everyHour": "Every hour",
  "settings.every2h": "Every 2 hours",
  "settings.every4h": "Every 4 hours",
  "settings.every8h": "Every 8 hours",
  "settings.pauseScans": "Pause automatic scans",
  "settings.pauseScansNote":
    'Stops scheduled scans from touching the portals — useful for resting the connection while you are away. "Scan now" still works on demand.',
  "settings.healthTitle": "🚨 Scraper health alerts",
  "settings.healthNote":
    "A broken scraper is silent: no listings looks exactly like a quiet market. Get notified when a search fails this many scans in a row. Portals block scrapers occasionally, so a value of 1 will cry wolf.",
  "settings.alertAfter": "Alert after",
  "settings.neverDisabled": "Never (disabled)",
  "settings.nFailures": "{count} consecutive failures",

  // ── settings: keywords & match score ────────────────────────────────────
  "settings.keywordsTitle": "🚫 Excluded keywords (global)",
  "settings.keywordsNote":
    "Listings containing these words are automatically discarded (whole words only, accents ignored). Separate with commas. Each search profile can add its own extra keywords on top of these.",
  "settings.matchTitle": "🎯 Smart Match Score (dream home)",
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

  // ── settings: assistant backend ─────────────────────────────────────────
  "settings.assistantTitle": "🧠 Search assistant backend",
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

  // ── settings: scraping & bypass ─────────────────────────────────────────
  "settings.scrapingTitle": "🛡️ Advanced Scraping & Bypass",
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
  "settings.scrapeApiTitle": "🌐 Scraping API (solves DataDome for you)",
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
  "settings.harvestTitle": "🤖 Grab the cookie automatically",
  "settings.harvestNote":
    "Opens a local browser, earns a fresh cookie, and saves it — no copy/paste. A window may open: if the portal shows a CAPTCHA, solve it once and it is remembered next time.",
  "settings.grabCookie": "🔄 Grab a fresh cookie now",
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
  "settings.camoufoxInstalled": "Installed ✓",
  "settings.camoufoxMissing": "Not installed — one-click adds it (~150 MB, one time):",
  "settings.installCamoufox": "⚡ One-Click Install Camoufox",
  "settings.installingCamoufox": "⚡ Installing Camoufox (~1-3 min)…",
  "settings.camoufoxInstalledMsg": "Camoufox installed successfully!",
  "settings.harvesterMissing":
    "Not installed yet in this Python environment. You can install Playwright and Chromium automatically with one click:",
  "settings.installHarvester": "⚡ One-Click Install Playwright & Chromium",
  "settings.installingHarvester": "⚡ Installing Playwright & Chromium (~1-2 min)…",
  "settings.harvesterInstalledMsg": "Playwright & Chromium installed successfully!",
  "settings.manualInstall":
    "Or install manually from terminal using `install-playwright.bat` inside the project folder, or run: ",

  // ── settings: API token & backend restart ───────────────────────────────
  "settings.apiTokenTitle": "🔒 API access token",
  "settings.apiTokenNote":
    "By default the dashboard is reachable by anyone who can reach its address (that is why it binds to localhost). Set a token to require it on every request — then it is safe to expose the app on your LAN or Tailscale. Leave empty to keep it open. You stay logged in on this device; other devices are asked for the token once.",
  "settings.apiTokenPlaceholder": "No token (open access)",
  "settings.backendTitle": "🔄 Backend",
  "settings.backendNote":
    "Restart the backend process — use this after updating the app so new features take effect, instead of closing and re-opening the terminal window. The dashboard goes offline for a few seconds and then reloads on its own.",
  "settings.restart": "🔄 Restart backend",
  "settings.restarting": "⏳ Restarting… (waiting for the backend)",
  "settings.restartConfirm":
    "Restart the backend now? The dashboard is unavailable for a few seconds, then reloads itself.",
  "settings.restartTooOld":
    "This running backend is too old to restart itself — close its terminal window and re-run start.bat / serve.bat once. After that this button (and the newest features) will work.",
  "settings.restartNoReturn":
    "The backend did not come back on its own — check its terminal window (or re-run start.bat / serve.bat).",

  // ── settings: data management ───────────────────────────────────────────
  "settings.dataTitle": "🧹 Data management",
  "settings.dataNote": "Irreversible. Your notification and login settings are always kept.",
  "settings.resetImportsName": "Reset email imports",
  "settings.resetImportsBody":
    " — clear every listing found in your inbox so you can import again from scratch (also forgets discarded ones).",
  "settings.resetImportsButton": "Reset imports",
  "settings.resetImportsConfirm":
    "Delete ALL imported email listings? You can re-run the inbox import afterwards.",
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

  // ── monitored searches: shell & modes ───────────────────────────────────
  "profiles.title": "🔍 Monitored searches",
  "profiles.statusOk": "OK",
  "profiles.statusBlocked": "Blocked (will retry)",
  "profiles.statusError": "Error",
  "profiles.modeAssistant": "💬 Just describe it",
  "profiles.modeBuilder": "🧭 Build a search",
  "profiles.modeUrl": "🔗 Paste a URL",
  "profiles.empty":
    "No search profiles configured. Build a search with your criteria or paste a results URL from Immobiliare.it / Idealista to get started.",
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
  "profiles.chAll": "🔔 All channels",
  "profiles.chAllWarn":
    "No notification channel is set up yet — this search won't send alerts. Configure Telegram or Email in ⚙️ Settings.",
  "profiles.chTelegram": "📨 Telegram only",
  "profiles.chTelegramOff": "📨 Telegram only (not set up)",
  "profiles.chTelegramWarn":
    "Telegram is not set up — this search won't send alerts. Add the bot token and chat ID in ⚙️ Settings.",
  "profiles.chEmail": "✉️ Email only",
  "profiles.chEmailOff": "✉️ Email only (not set up)",
  "profiles.chEmailWarn":
    "Email is not set up — this search won't send alerts. Configure SMTP in ⚙️ Settings.",
  "profiles.chNone": "🔕 No notifications",

  // ── monitored searches: assistant ───────────────────────────────────────
  "profiles.assistantIntro":
    'Describe what you are looking for in plain Italian or English — even several alternatives at once ("bilocale in zona X o trilocale in zona Y"). The text is parsed on your PC — nothing is sent to any AI service — and you review every search before it is saved.',
  "profiles.assistantPlaceholder":
    "e.g. trilocale in affitto a Milano sotto i 1.200 € al mese",
  "profiles.assistantReading": "Reading…",
  "profiles.assistantSubmit": "Understand it →",
  "profiles.assistantTry": "Try:",
  "profiles.multiIntro":
    "I read {count} alternative searches in your sentence. Check each one (open the links to verify the results), then create all the profiles at once.",
  "profiles.reword": "✏️ Reword",
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
    "💡 This is how you use every portal filter — bathrooms, floor, elevator, terrace, energy class, property type, exclude auctions, and so on. Set them on the portal, then paste the URL: the app monitors exactly that search. The two helpers above (\"Just describe it\" / \"Build a search\") only cover city, price, rooms and surface.",
  "profiles.namePlaceholder": "Name (e.g. 3 rooms South Milan)",
  "profiles.keywordsPlaceholder": "Extra excluded keywords (optional, comma-separated)",
  "profiles.urlPlaceholder":
    "https://www.immobiliare.it/vendita-case/milano/?prezzoMassimo=300000…",
  "profiles.extractParams": "🪄 Extract parameters",
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
    "💡 Need bathrooms, terrace, energy class, property type or another filter? Set it on the portal and ",
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
  "profiles.activate": "▶️ Activate",
  "profiles.pause": "⏸️ Pause",
  "profiles.notificationsAction": "Notifications →",
  "profiles.deleteAction": "🗑 Delete",
  "profiles.mergeSelected": "🔗 Merge selected",
  "profiles.mergeSelectedTitle": "Merge the selected portals into a single search box",
  "profiles.mergePrompt":
    "Enter the single name to merge the selected searches under one box:",
  "profiles.clearSelection": "Clear",
  "profiles.merged": "Merged ({count} portals)",
  "profiles.mergedTitle": "Searches across several portals merged into one box",
  "profiles.separateConfirm": 'Separate the portals of "{name}" into distinct search boxes?',
  "profiles.excludesTitle":
    "Listings mentioning any of these words are discarded (Settings + this search's own extras)",
  "profiles.excludes": "🚫 Excludes: {words}",
  "profiles.globalKeywords": "🌐 Always excluded for every search (from Settings): {words}",
  "profiles.notifyTitle": "Where to send notifications for this search",
  "profiles.active": "Active",
  "profiles.editBox": "Edit this search box",
  "profiles.separateBox": "Separate the portals into independent boxes",
  "profiles.deleteBox": "Delete this search box (all its portals)",
  "profiles.chipRent": "🔑 Rent",
  "profiles.chipBuy": "🏠 Buy",
  "profiles.chipRooms": "🛏️ {range} rooms",
  "profiles.chipMinSqm": "📐 ≥ {value} sqm",

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

  // ── email import: panel shell ───────────────────────────────────────────
  "email.title": "📥 Import from email",
  "email.toReview": "({count} to review)",
  "email.hide": "Hide",
  "email.open": "Open",
  "email.intro":
    'Mine your own inbox for listing emails and review them here: accept what interests you, discard the rest. Your mailbox is accessed strictly read-only, and duplicates of listings already tracked are skipped automatically. Alert emails can be months old, so an ad may already be sold or withdrawn — "Open ↗" is the only way to find out, since this panel never visits the portals.',
  "email.portalsOnlyPrefix": "Only ads ",
  "email.portalsOnlyBold": "hosted on Immobiliare.it or Idealista.it",
  "email.portalsOnlySuffix":
    " can be imported: the whole app is built around their listing IDs. An agency's own email counts only if it links to a portal ad — one that links to the agency's website instead brings back nothing, whatever sender you search for.",
  "email.imapMissing":
    '⚠️ IMAP is not configured yet — open ⚙️ Settings → "Email inbox import" and add host, username and app password first.',
  "email.unknownError": "Unknown error",
  "email.nothingToCheck":
    "No listings to check. Scan the emails or select a specific listing to force the recompute.",
  "email.confirmDiscardAll":
    "Discard all {count} listings shown here? They won't come back on future scans.",
  "email.confirmDiscardAllOne":
    "Discard the {count} listing shown here? It won't come back on future scans.",
  "email.cookieSaveFailed": "Failed to save cookie: {error}",
  "email.nothingToReview": "Nothing to review.",
  "email.nothingToReviewYet": "Nothing to review — run a scan above.",

  // ── email import: scan form ─────────────────────────────────────────────
  "email.lookFor": "Look for",
  "email.modePortals": "Portal alert emails",
  "email.modeAddress": "Specific sender(s)",
  "email.modeAny": "Any email linking a portal ad",
  "email.senders": "Senders (comma-separated addresses or domains)",
  "email.sendersTitle":
    "Their emails must link an Immobiliare.it or Idealista.it ad: a link to the agency's own site cannot be imported",
  "email.sendersPlaceholder": "e.g. agenzia@example.com, immobiliare.it",
  "email.period": "Period",
  "email.lastMonth": "Last month",
  "email.last6Months": "Last 6 months",
  "email.lastYear": "Last year",
  "email.last5Years": "Last 5 years",
  "email.maxEmails": "Max emails",
  "email.maxEmailsTitle":
    "Newest messages first; re-run the scan to go deeper (already imported listings are skipped)",
  "email.scan": "Scan inbox",
  "email.scanning": "Scanning inbox…",
  "email.phaseConnecting": "Connecting to your mailbox…",
  "email.phaseSearching": "Searching the inbox…",
  "email.phaseReading": "Reading email {done} of {total} — {staged} new listings staged",
  "email.phaseReadingOne": "Reading email {done} of {total} — {staged} new listing staged",
  "email.phaseStarting": "Starting…",
  "email.scanNote":
    "Large mailboxes take a few minutes; you can keep using the dashboard meanwhile.",
  "email.scanSummary":
    "✅ Scanned {emails} emails ({withListings} with listings) — {imported} new listings staged, {tracked} already tracked by your searches, {seen} seen in a previous scan.",
  "email.blankLinks":
    " {count} links were skipped: the email gave no price, size or name to review them by.",
  "email.blankLinksOne":
    " {count} link was skipped: the email gave no price, size or name to review it by.",
  "email.blankRemoved": " {count} such rows left by earlier scans were cleaned up.",
  "email.blankRemovedOne": " {count} such row left by earlier scans was cleaned up.",

  // ── email import: review filters ────────────────────────────────────────
  "email.statusTitle": "Choose whether to show pending, discarded or already accepted listings",
  "email.statusPending": "⏳ Pending",
  "email.statusDiscarded": "🗑️ Discarded",
  "email.statusAccepted": "✅ Accepted",
  "email.statusAll": "📋 All",
  "email.filterLikeSearch": "Filter like search",
  "email.filterLikeSearchTitle":
    "Reuse the contract, city and excluded keywords of a search you already monitor",
  "email.adHocFilters": "— ad-hoc filters —",
  "email.contract": "Contract",
  "email.any": "Any",
  "email.textSearch": "Text search",
  "email.textSearchPlaceholder": "in title/subject",

  // ── email import: actions bar ───────────────────────────────────────────
  "email.selectAll": "Select all ({count})",
  "email.acceptSelected": "✓ Accept selected",
  "email.discardSelected": "✕ Discard selected",
  "email.discardAll": "🗑 Discard all ({count})",
  "email.discardAllTitle":
    "Discard all currently shown listings (the filters above stay applied).",
  "email.cookieSaved": "DataDome cookie saved",
  "email.cookiePaste": "Paste DataDome cookie…",
  "email.cookieTitle":
    "Paste the 'datadome' cookie from your browser here to get past the portals' blocks",
  "email.checkTitle":
    "Probe the portal pages to see which are still online and refresh their photos and data. If nothing is selected, it checks the not-yet-verified ones.",
  "email.checkSelected": "🔎 Check selected ({count})",
  "email.checkAll": "🔎 Check online availability",
  "email.discardGone": "🚫 Discard the {count} removed",
  "email.discardGoneTitle":
    "Discard in one go all listings the portal confirmed as removed/non-existent",
  "email.sortBy": "Sort by:",
  "email.sortDate": "Most recent email",
  "email.sortSqmPrice": "€/m² (cheapest)",
  "email.sortPrice": "Price (lowest)",
  "email.checkProgress": "Checking listing {done} of {total} — {gone} already removed…",
  "email.checkPacing": "(One page every 6 seconds to avoid the portals blocking the IP)",
  "email.checkResult": "🔎 Check result for {count} listings:",
  "email.checkGone": "{count} no longer online (removed)",
  "email.checkOnline": "{count} still online and refreshed",
  "email.checkUnknown": " ({count} inconclusive due to a block or network error)",
  "email.cookieRefreshedOnce":
    "🔄 DataDome cookie auto-refreshed once during the check to get past the anti-bot controls.",
  "email.cookieRefreshed":
    "🔄 DataDome cookie auto-refreshed {count} times during the check to get past the anti-bot controls.",
  "email.lastErrorDetail": "❌ Last error detail: {error}",
  "email.checkAborted":
    "⚠️ The portal started blocking the requests, so the check was stopped to protect the network IP. Paste a fresh DataDome cookie or try again later.",

  // ── email import: listing card ──────────────────────────────────────────
  "email.openOriginal": "Open the original listing on the portal",
  "email.listingPhoto": "Listing photo",
  "email.listingNumber": "Listing #{id}",
  "email.badgeAccepted": "✅ Accepted",
  "email.badgeDiscarded": "🗑️ Discarded",
  "email.badgeOnline": "🟢 Online on the portal",
  "email.badgeOnlineTitle":
    "The portal confirmed the listing page is still online and reachable",
  "email.badgeRemoved": "🔴 Removed / Unavailable",
  "email.badgeRemovedTitle": "The portal answered 'page not found' (404/removed)",
  "email.badgeUnchecked": "⚪ Not checked",
  "email.badgeUncheckedTitle":
    "Availability not checked on the portal yet. Use 'Check if online'",
  "email.sqmUnit": "{value} m²",
  "email.roomsUnit": "{count} rooms",
  "email.contractRent": "rent",
  "email.contractSale": "sale",
  "email.emailOf": "email of {date}",
  "email.sqmPriceMonth": "{value} €/m² per month",
  "email.sqmPriceUnit": "{value} €/m²",
  "email.sqmPriceTitle": "Price per square meter computed from the email",
  "email.openPage": "Open ↗",
  "email.openPageTitle": "Open the original page on the portal",
  "email.accept": "✓ Accept",
  "email.recoverAccept": "✓ Recover / Accept",
  "email.acceptTitle": "Add to the main dashboard (automatically deduplicated)",
  "email.discard": "✕ Discard",
  "email.discardTitle": "Discard listing (it will not be re-loaded on future scans)",

  // ── map view ────────────────────────────────────────────────────────────
  "map.pinDrop": "📉 Price drop",
  "map.pinFavorite": "★ Favorite",
  "map.pinFiltered": "🚫 Filtered",
  "map.pinGone": "💨 No longer available",
  "map.pinSold": "🔑 Sold / rented out",
  "map.pinActive": "Active listing",
  "map.onMap": "{shown} of {total} properties on the map",
  "map.missing": "{count} without coordinates",
  "map.missingTitle":
    "Portals do not publish coordinates for every listing; those properties are still in the grid view.",
  "map.drawRadius": "◯ Draw radius",
  "map.drawingRadius": "◯ Click centre, drag handle…",
  "map.drawRadiusTitle":
    "Click the map to set the centre, then drag the handle to size the radius.",
  "map.drawArea": "⬠ Draw area",
  "map.finishArea": "⬠ Finish area",
  "map.drawAreaTitle":
    "Click to add each corner; double-click or press Finish to close the area.",
  "map.polyHint": "{count} point(s) — need ≥ 3, then double-click to close",
  "map.clearZone": "✕ Clear zone",
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

  // ── market velocity ─────────────────────────────────────────────────────
  "velocity.title": "📊 Market velocity",
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
  "trends.title": "📈 Price trends",
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
  "trends.changeSince": "{arrow} {pct}% since {date}",
  "trends.caveat":
    "Median asking price per square meter among the listings this app was tracking each day — your own sample, not the whole market. It moves with what you monitor as much as with prices.",
  "trends.oneDayOnly":
    "Only one day recorded for this area so far — the line appears once there are at least two.",
  "trends.showComparables": "🔍 Show the listings behind this median ▼",
  "trends.hideComparables": "Hide the listings behind this median ▲",
  "trends.comparablesEmpty": "No priced listings in this area right now.",
  "trends.comparablesNote":
    "The {count} listings currently priced in this area — the live set today's median is computed from. Earlier points on the chart kept only their count, so their exact listings can no longer be shown. Click one to open its details.",
  "trends.comparablesNoteOne":
    "The {count} listing currently priced in this area — the live set today's median is computed from. Earlier points on the chart kept only their count, so their exact listings can no longer be shown. Click it to open its details.",
  "trends.vsMedian": " ({sign}{pct}% vs median)",

  // ── backend log viewer ──────────────────────────────────────────────────
  "logs.title": "📜 Backend log",
  "logs.filterPlaceholder": "Filter (e.g. availability_check, blocked, error)",
  "logs.autoRefresh": "Auto-refresh (3s)",
  "logs.lineCount": "{visible} / {total} lines",
  "logs.loadFailed": "Failed to load logs",
  "logs.empty": "No log lines yet — this fills up once a scan or check runs.",
  "logs.noMatch": "No lines match this filter.",
  "logs.source": "Source: {path}",

  // ── scraper health ──────────────────────────────────────────────────────
  "health.title": "🩺 Scraper health",
  "health.subtitle": "is the anti-bot pipeline still getting through?",
  "health.hide": "Hide ▲",
  "health.show": "Show ▼",
  "health.loadFailed": "Could not load scraper health",
  "health.window":
    "Last {days} days of scan outcomes per portal. Next scan starts on: {transport}.",
  "health.empty": "No scans recorded yet — this fills in as scans run.",
  "health.colPortal": "Portal",
  "health.colDays": "Days (oldest → today)",
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
  "health.failingTitle": "Searches currently failing",
  "health.failingRow": "({portal}) — {count} consecutive {status} scans",
  "health.failingStatusFallback": "failed",
  "health.failingHint":
    "A short streak is routine (transient anti-bot blocks). A long one means the free path is down: consider a proxy pool or a scrape-API key in Settings.",

  // ── calculators (property modal) ────────────────────────────────────────
  "calc.mortgageTitle": "🧮 Mortgage estimator",
  "calc.downPayment": "Down payment",
  "calc.interestRate": "Interest rate",
  "calc.perYear": "%/yr",
  "calc.duration": "Duration",
  "calc.years": "years",
  "calc.loanAmount": "Loan amount",
  "calc.monthlyPayment": "Monthly payment",
  "calc.yieldTitle": "📈 Rental yield (investment)",
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
  "auth.title": "🔒 Authentication required",
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
