/** Italian dictionary.
 *
 *  Typed as `Dict` (= `typeof en`): a key missing here, or one that no longer
 *  exists in `en.ts`, is a `tsc -b` failure. That type annotation is the whole
 *  guarantee that the two languages cannot drift apart — do not replace it with
 *  `Record<string, string>`.
 */
import type { Dict } from "./index";

export const it: Dict = {
  // ── vocabolario condiviso ───────────────────────────────────────────────
  "common.save": "Salva",
  "common.saving": "Salvataggio…",
  "common.cancel": "Annulla",
  "common.close": "Chiudi",
  "common.delete": "Elimina",
  "common.edit": "Modifica",
  "common.restore": "Ripristina",
  "common.loading": "Caricamento…",
  "common.refresh": "Aggiorna",
  "common.retry": "Riprova",
  "common.yes": "Sì",
  "common.no": "No",
  "common.all": "Tutti",
  "common.none": "Nessuno",
  "common.optional": "facoltativo",
  "common.of": "di",
  "common.dismissError": "Chiudi l'errore",
  "common.actionFailed": "Operazione non riuscita",
  "common.copy": "Copia",
  "common.copied": "Copiato",
  "common.showMore": "Mostra altro",
  "common.showLess": "Mostra meno",
  "common.sale": "Vendita",
  "common.rent": "Affitto",
  "common.buy": "Compra",
  "common.unknown": "Sconosciuto",
  "common.notAvailable": "N/D",
  "common.perMonthSuffix": "/mese",
  "common.sqmPrice": "{value} €/mq",
  "common.rooms": "{count} locali",
  "common.sqm": "{value} mq",

  // ── scheda immobile ─────────────────────────────────────────────────────
  "card.medianIn": "Mediana in questa {scope}: {value} €/mq",
  "card.scopeZone": "zona",
  "card.scopeCity": "città",
  "card.belowAverage": "{pct}% sotto la media della {scope}",
  "card.aboveAverage": "{pct}% sopra la media della {scope}",
  "card.matchBadge": "🎯 {score}% di corrispondenza",
  "card.matchBadgeTitle": "Compatibilità con le impostazioni della casa dei sogni",
  "card.dealScore": "Punteggio affare",
  "card.dealBelowMarket": "🎯 {pct}% sotto mercato",
  "card.dealAboveMarket": "🎯 {pct}% sopra mercato",
  "card.new": "🆕 nuovo",
  "card.newTitle": "Comparso dopo la tua ultima visita alla dashboard",
  "card.rent": "🔑 affitto",
  "card.mergedListings": "{count} annunci unificati",
  "card.email": "✉️ email",
  "card.emailTitle": "Importato dalla tua casella email (non da una ricerca monitorata)",
  "card.deselect": "Deseleziona",
  "card.selectForBatch": "Seleziona per la verifica in blocco",
  "card.removeFavorite": "Togli dai preferiti",
  "card.addFavorite": "Aggiungi ai preferiti",
  "card.hideTitle": "Nascondi questo immobile (non tornerà mai da solo)",
  "card.hideAria": "Nascondi questo immobile",
  "card.filteredReason": "🚫 Filtrato: {reason}",
  "card.noLongerAvailable": "💨 Non più disponibile",
  "card.sold": "🔑 Venduto",
  "card.rentedOut": "🔑 Affittato",
  "card.untitled": "Senza titolo",
  "card.locationUnknown": "Posizione N/D",
  "card.notes": "📝 note",
  "card.notOnMap": "🗺️✗ non sulla mappa",
  "card.notOnMapTitle":
    "Nessuna coordinata sulla mappa — questo annuncio non comparirà sulla mappa né dentro una zona disegnata finché non viene localizzato (aprilo e usa \"Mostra sulla mappa\", oppure lancia \"Trova le coordinate\").",

  // ── scheda dettaglio ────────────────────────────────────────────────────
  "modal.locateFailed":
    "Impossibile posizionare questo immobile — la località indicata dal portale è troppo vaga per ricavarne le coordinate.",
  "modal.locateError": "Impossibile localizzare questo immobile",
  "modal.checkGone": "🔴 Rimosso / Sparito (404)",
  "modal.checkOnline": "🟢 Online (appena verificato)",
  "modal.checkUnknown": "⚠️ Impossibile verificare (bloccato dal portale o timeout)",
  "modal.checkError": "Errore durante la verifica online",
  "modal.notesError": "Impossibile salvare le note",
  "modal.dealScoreTitle": "🎯 Punteggio affare:",
  "modal.dealBelowLocal": "sotto il mercato locale",
  "modal.dealAboveLocal": "sopra il mercato locale",
  "modal.suggestedProposal": "💬 Proposta suggerita:",
  "modal.dealDisclaimer":
    "Una stima ricavata dalla mediana €/mq della zona, dagli indizi sullo stato dell'immobile e dallo sconto abituale dell'agenzia — un punto di partenza per il tuo giudizio, non una perizia.",
  "modal.foundListings": "Annunci trovati ({count})",
  "modal.open": "Apri ↗",
  "modal.priceHistory": "Storico dei prezzi",
  "modal.foundBySearch": "🔍 Trovato da una ricerca",
  "modal.foundBySearches": "🔍 Trovato da {count} ricerche",
  "modal.notLinked":
    "🔍 Non collegato a nessuna ricerca monitorata — importato dalla tua casella email.",
  "modal.tags": "🏷️ Etichette",
  "modal.notes": "📝 Note personali",
  "modal.notesPlaceholder":
    'es. "chiamata l\'agenzia lunedì — visita fissata per venerdì", "servono 15k di ristrutturazione"',
  "modal.saveNotes": "Salva le note",
  "modal.description": "Descrizione",
  "modal.checkOnlineButton": "🔎 Verifica se è ancora online",
  "modal.checkOnlineTitle":
    "Interroga subito l'URL del portale per verificare se questo annuncio è ancora online o è stato rimosso (404)",
  "modal.viewOnMap": "🗺️ Mostra sulla mappa",
  "modal.viewOnMapTitle": "Apri questo immobile sulla mappa",
  "modal.locateAndViewTitle": "Trova le coordinate di questo immobile e aprilo sulla mappa",
  "modal.restore": "👁 Ripristina l'immobile",
  "modal.restoreGone":
    'Ripristinare questo immobile? Usalo se la verifica di disponibilità lo ha segnato "non più disponibile" per sbaglio.',
  "modal.restoreSold":
    "Ripristinare questo immobile? Usalo se lo hai segnato come venduto per sbaglio — torna negli elenchi attivi.",
  "modal.restoreHidden": "Ripristinare questo immobile? Tornerà negli elenchi attivi.",
  "modal.restoreFailed": "Ripristino non riuscito",
  "modal.markSold": "🔑 Segna come venduto",
  "modal.markRented": "🔑 Segna come affittato",
  "modal.confirmSold":
    "Segnare questo immobile come venduto? Esce dagli elenchi attivi ma resta come vendita confermata per le statistiche di mercato.",
  "modal.confirmRented":
    "Segnare questo immobile come affittato? Esce dagli elenchi attivi ma resta come contratto confermato per le statistiche di mercato.",
  "modal.markSoldFailed": "Impossibile segnarlo come venduto",
  "modal.hide": "🙈 Nascondi l'immobile",
  "modal.hideFailed": "Impossibile nasconderlo",

  // ── etichette ───────────────────────────────────────────────────────────
  "tags.removeTag": 'Rimuovi l\'etichetta "{name}"',
  "tags.addTag": "Aggiungi un'etichetta",
  "tags.addTagButton": "+ etichetta",
  "tags.namePlaceholder": "Nome dell'etichetta…",
  "tags.create": '+ crea "{name}"',

  // ── barra di navigazione ────────────────────────────────────────────────
  "nav.title": "Ricerca Immobili",
  "nav.subtitle": "Immobiliare.it + Idealista, senza duplicati",
  "nav.scanning": "⏳ Scansione in corso…",
  "nav.paused": "⏸ Scansioni automatiche in pausa",
  "nav.nextScan": "Prossima scansione automatica: {time}",
  "nav.scanNowShort": "▶ Scansiona",
  "nav.scanNow": "▶ Avvia scansione",
  "nav.scanNowAria": "Avvia subito la scansione",
  "nav.running": "In corso…",
  "nav.toLight": "Passa al tema chiaro",
  "nav.toDark": "Passa al tema scuro",
  "nav.viewLog": "Mostra il log del backend",
  "nav.settings": "Impostazioni",
  "nav.language": "Lingua",
  "nav.languageSwitchTo": "Passa a {language}",

  // ── struttura della dashboard ───────────────────────────────────────────
  "app.backendUnreachable":
    "Backend non raggiungibile su http://localhost:8000 — avvialo con start.bat",
  "app.noMatches": "Nessun immobile corrisponde ai filtri attuali.",
  "app.noMatchesHint":
    "Prova a cambiare Compra/Affitto o ad allentare i filtri.",
  "app.welcome": "Benvenuto! Tre passi per iniziare:",
  "app.step1":
    'Aggiungi una ricerca qui sopra — descrivila a parole con "💬 Descrivila e basta", costruiscila con "🧭 Costruisci una ricerca", oppure incolla l\'URL dei risultati da Immobiliare.it / Idealista.',
  "app.step1Tip": "Suggerimento:",
  "app.step1TipBody":
    'per usare tutti i filtri del portale (bagni, piano, ascensore, classe energetica, escludi aste…), impostali sul portale e usa "🔗 Incolla un URL" — l\'app monitora esattamente quella ricerca.',
  "app.step2":
    'Premi "▶ Avvia scansione" — la prima scansione crea la tua base di partenza (nessuna raffica di notifiche).',
  "app.step3":
    "Facoltativo: apri ⚙️ Impostazioni per attivare gli avvisi Telegram o Email su nuovi annunci e cali di prezzo.",
  "app.showMoreCount": "Mostra altri ({count} rimanenti)",

  // ── barra di selezione multipla ─────────────────────────────────────────
  "app.selectMultiple": "☐ Seleziona più immobili",
  "app.closeMultiSelect": "✕ Chiudi selezione multipla",
  "app.selectAll": "Seleziona tutti ({selected} di {total})",
  "app.hideSelected": "🙈 Nascondi selezionati ({count})",
  "app.hideSelectedTitle":
    "Gli immobili nascosti lasciano la dashboard definitivamente e non tornano da soli, nemmeno se una scansione li ritrova. Usa Ripristina per riportarne indietro uno.",
  "app.markSold": "🔑 Segna come venduto ({count})",
  "app.addFavorites": "⭐ Aggiungi ai preferiti",
  "app.removeFavorites": "❌ Togli dai preferiti",
  "app.checkAvailability": "🔎 Verifica disponibilità online ({count})",
  "app.checking": "⏳ Verifica in corso…",
  "app.stopping": "⏳ Interruzione…",
  "app.stop": "⏹ Ferma",
  "app.confirmHideOne":
    "Nascondere questo immobile? Non comparirà mai più negli elenchi né nelle notifiche.",
  "app.confirmHideMany":
    "Nascondere {count} immobili? Spariranno dagli elenchi e dalle notifiche (recuperabili da 🙈 Scartati → Ripristina).",
  "app.confirmSoldMany":
    "Segnare {count} immobili come venduti/affittati? Escono dagli elenchi attivi ma restano come vendite confermate per le statistiche di mercato (recuperabili da 🔑 Venduti → Ripristina).",
  "app.batchCheckFailed": "Verifica in blocco non riuscita",

  // ── avanzamento e riepilogo della verifica ──────────────────────────────
  "app.checkProgress":
    "Verifica annuncio {done} di {total} — {online} online, {gone} rimossi/venduti",
  "app.checkProgressUnknown": ", {count} non verificabili",
  "app.checkStarting": "Avvio della verifica…",
  "app.checkPacingNote":
    "Tra una richiesta e l'altra c'è una pausa di sicurezza per proteggere l'IP dai blocchi DataDome.",
  "app.checkTransport": "Trasporto: {transport}",
  "app.checkLastIssue": "Ultimo problema segnalato dal portale: {error}",
  "app.summaryChecked": "🔎 Verificati:",
  "app.summaryGone": "{count} rimossi o venduti (spostati in Spariti)",
  "app.summaryOnline": "{count} ancora online",
  "app.summaryUnknown": " ({count} non verificabili dal portale)",
  "app.summaryCancelled":
    "⏹ Interrotta — il resto della selezione non è stato verificato. Riselezionalo per riprendere.",
  "app.summaryAborted":
    "⚠️ Il portale ha bloccato le richieste: verifica interrotta per proteggere l'IP. Riprova più tardi.",
  "app.summaryAbortedService":
    "Eseguita tramite {transport}. L'opzione della finestra del browser è attiva, ma un servizio Windows in background non ha un desktop su cui mostrarla. Per risolvere un CAPTCHA a mano, ferma il servizio e avvia l'app normalmente (start.bat / serve.bat) per questa verifica.",
  "app.summaryAbortedNoWindow":
    'Eseguita tramite {transport}. Per risolvere un CAPTCHA a mano, attiva sia "Esegui la verifica tramite browser" sia "Mostra la finestra del browser" nelle Impostazioni (serve il motore browser installato).',
  "app.summaryCapped":
    "Raggiunto il limite di richieste per esecuzione: rilancia la verifica per continuare con i restanti.",

  // ── barra dei filtri ────────────────────────────────────────────────────
  "filters.search": "Cerca",
  "filters.searchPlaceholder": "Cerca per zona, indirizzo, titolo, piano o testo dell'annuncio…",
  "filters.clearSearch": "Cancella la ricerca",
  "filters.market": "Mercato",
  "filters.buy": "🏠 Compra",
  "filters.rent": "🔑 Affitta",
  "filters.city": "Città",
  "filters.cityPlaceholder": "es. Milano",
  "filters.zone": "Zona",
  "filters.zonePlaceholder": "es. Navigli",
  "filters.minPrice": "Prezzo min €",
  "filters.maxPrice": "Prezzo max €",
  "filters.perMonth": "/mese",
  "filters.minSqm": "Mq min",
  "filters.maxSqm": "Mq max",
  "filters.rooms": "Locali",
  "filters.floor": "Piano",
  "filters.anyFloor": "Qualsiasi piano",
  "filters.floorGround": "Piano terra",
  "filters.floorLow": "Basso (1–2)",
  "filters.floorMid": "Intermedio (3–5)",
  "filters.floorHigh": "Alto (6+)",
  "filters.floorTop": "Ultimo piano (attico/ultimo)",
  "filters.sortBy": "Ordina per",
  "filters.sortNewest": "Più recenti",
  "filters.sortPriceAsc": "Prezzo crescente",
  "filters.sortPriceDesc": "Prezzo decrescente",
  "filters.sortSqmPrice": "€/mq più basso",
  "filters.sortMatch": "🎯 Corrispondenza migliore",
  "filters.status": "Stato",
  "filters.statusForSale": "In vendita",
  "filters.statusForRent": "In affitto",
  "filters.statusFiltered": "🚫 Filtrati",
  "filters.statusGone": "💨 Spariti",
  "filters.statusSold": "🔑 Venduti",
  "filters.statusRentedOut": "🔑 Affittati",
  "filters.statusHidden": "🙈 Scartati",
  "filters.statusAll": "Tutti",
  "filters.origin": "Provenienza",
  "filters.originAll": "Tutte le provenienze",
  "filters.originScan": "🔎 Ricerca monitorata",
  "filters.originEmail": "✉️ Import da email",
  "filters.tag": "Etichetta",
  "filters.allTags": "Tutte le etichette",
  "filters.limitToSearch": "Limita a una ricerca",
  "filters.limitToSearchTitle":
    "Mostra solo gli immobili trovati da questa ricerca salvata (la sua provenienza 'Trovato da'). Gli import da email, che nessuna ricerca ha trovato, escono. Questo restringe l'elenco — non lo riordina.",
  "filters.allSearches": "Tutte le ricerche",
  "filters.priceDrops": "📉 Cali di prezzo",
  "filters.favorites": "⭐ Preferiti",
  "filters.more": "⚙️ Altri filtri",
  "filters.moreTitle": "Altri filtri",
  "filters.moreHint": "· restringi per portale, agenzia, qualità dell'affare o €/mq",
  "filters.portal": "Portale",
  "filters.anyPortal": "Qualsiasi portale",
  "filters.agency": "Agenzia",
  "filters.agencyPlaceholder": "es. Tecnocasa",
  "filters.deal": "Affare",
  "filters.anyDeal": "Qualsiasi affare",
  "filters.dealUndervalued": "💎 Solo sottovalutati",
  "filters.dealFairPlus": "👍 Equo o migliore",
  "filters.minSqmPrice": "€/mq min",
  "filters.maxSqmPrice": "€/mq max",
  "filters.mergedOnly": "🔗 Solo unificati (stessa casa su più portali/agenzie)",
  "filters.countProperties": "{count} immobili",
  "filters.reset": "↺ Azzera i filtri",
  "filters.resetTitle": "Cancella tutti i filtri e torna alla vista predefinita",
  "filters.view": "Vista",
  "filters.viewGrid": "▦ Griglia",
  "filters.viewMap": "🗺 Mappa",
  "filters.export": "Esporta",
  "filters.exportTitle": "Scarica i {count} immobili filtrati in {format}",
  "filters.exportFavorites": "Preferiti",
  "filters.exportRentals": "Affitti",
  "filters.exportProperties": "Immobili",
  "filters.exportIn": "{what} a {city}",

  // ── azioni di manutenzione ──────────────────────────────────────────────
  "filters.maintenance": "Manutenzione",
  "filters.repair": "🛠️ Ripara i dati",
  "filters.repairing": "⏳ Riparazione…",
  "filters.repairTitle":
    "Ripara subito titoli, zone e foto mancanti sugli annunci importati in precedenza",
  "filters.findCoords": "📍 Trova le coordinate",
  "filters.locating": "⏳ Localizzazione…",
  "filters.findCoordsTitle":
    "Trova le coordinate sulla mappa per gli annunci che hanno un indirizzo o una zona ma nessun segnaposto (usa OpenStreetMap; può richiedere tempo)",
  "filters.retryFailed": "🧹 Riprova le ricerche fallite",
  "filters.clearing": "⏳ Pulizia…",
  "filters.retryFailedTitle":
    "Dimentica le geocodifiche fallite così \"Trova le coordinate\" riprova gli indirizzi che un disservizio temporaneo di OpenStreetMap ha congelato come \"non trovati\". Non sposta mai i segnaposti esistenti.",
  "filters.backendTooOld":
    "Il backend non ha ancora questa funzione — riavvialo (chiudi e rilancia start.bat / serve.bat) e riprova.",

  // ── esiti della manutenzione ────────────────────────────────────────────
  "filters.repairDone": "Riparazione completata!",
  "filters.repairSummary":
    "Aggiornati {properties} immobili, {listings} annunci e recuperate {images} foto.",
  "filters.repairMerged":
    "Unificate {merged} schede duplicate e rimossi {removed} annunci duplicati che puntavano allo stesso inserimento.",
  "filters.repairNothing": "È tutto in ordine e perfettamente allineato!",
  "filters.repairNothingBody":
    "Il controllo ha analizzato il database: nessun immobile o annuncio con dati mancanti, città (`Location N/A`), foto o link duplicati da riparare. Ogni annuncio è già completo e allineato.",
  "filters.geocodeRunning": "Ricerca delle coordinate in background…",
  "filters.geocodeProgress":
    "Localizzazione annuncio {done} di {total} — {geocoded} localizzati, {cached} dalla cache",
  "filters.geocodeProgressNotFound": ", {count} non trovati",
  "filters.geocodeStarting": "Avvio della ricerca delle coordinate…",
  "filters.geocodePacing":
    "(Ritmo di 1 richiesta al secondo, per rispettare le regole d'uso di OpenStreetMap Nominatim)",
  "filters.geocodeLastIssue": "Ultimo problema segnalato da Nominatim: {error}",
  "filters.geocodeDone": "Ricerca delle coordinate terminata",
  "filters.geocodeNothing":
    "Niente da localizzare: ogni immobile ha già un segnaposto oppure non ha indirizzo/zona da cui ricavarlo. (La sola città viene saltata di proposito — porterebbe tutti quegli annunci sullo stesso punto in centro.)",
  "filters.geocodeLocated": "Localizzati {geocoded} di {scanned} annunci senza segnaposto",
  "filters.geocodeNotFound": " · {count} non risolti",
  "filters.geocodeCancelled":
    '⏹ Interrotta — gli immobili rimanenti sono rimasti senza segnaposto. Premi di nuovo "Trova le coordinate" per riprendere.',
  "filters.geocodeRemaining": "Ne restano {count} — rilanciala per continuare.",
  "filters.cacheClearedNone":
    "Nessuna ricerca bloccata da cancellare — ogni indirizzo fallito era già stato dimenticato o non era mai stato messo in cache.",
  "filters.cacheCleared":
    "🧹 Cancellate {count} ricerche fallite. Premi 📍 Trova le coordinate per riprovarle.",
  "filters.cacheClearedOne":
    "🧹 Cancellata {count} ricerca fallita. Premi 📍 Trova le coordinate per riprovarla.",

  // ── impostazioni: struttura e segreti ───────────────────────────────────
  "settings.title": "⚙️ Impostazioni",
  "settings.testNote":
    "Ogni pulsante di test salva prima le tue modifiche, così ciò che verifica è esattamente ciò che hai scritto.",
  "settings.secretDirty": "✎ Modifica non salvata — sostituirà il valore memorizzato",
  "settings.secretSaved": "✓ Salvato",
  "settings.secretSavedOn": "✓ Salvato · {date}",
  "settings.secretSavedTitle": "Un valore è attualmente memorizzato",
  "settings.secretLastSaved": "Ultimo salvataggio: {date}",
  "settings.secretNotSet": "○ Non impostato",
  "settings.saved": "Impostazioni salvate.",
  "settings.saveFailed": "Impossibile salvare le impostazioni: {error}",
  "settings.save": "Salva le impostazioni",
  "settings.errCredentials":
    "{error} — le credenziali sono state rifiutate. Con Gmail devi usare una password per app di 16 caratteri, non la tua password normale.",
  "settings.errNetwork":
    "{error} — impossibile raggiungere il server. Controlla nome host e porta.",

  // ── impostazioni: telegram ──────────────────────────────────────────────
  "settings.telegramTitle": "📨 Notifiche Telegram",
  "settings.telegramHelp": "Come configuro Telegram? (passo per passo)",
  "settings.tgStep1": "Apri Telegram e cerca @BotFather.",
  "settings.tgStep2": 'Invia "/newbot" e segui le istruzioni; copia il token che ti dà.',
  "settings.tgStep3": "Incolla il token qui sotto.",
  "settings.tgStep4":
    "Cerca il tuo nuovo bot per nome e inviagli un messaggio qualsiasi (così lo autorizzi a scriverti).",
  "settings.tgStep5":
    "Ricava il tuo Chat ID: scrivi a @userinfobot e copia il numero che risponde.",
  "settings.tgStep6":
    'Incolla il Chat ID qui sotto, spunta "Attiva", poi premi "Salva e invia test".',
  "settings.tokenSaved": "Token già salvato (lascia vuoto per mantenerlo)",
  "settings.tokenPlaceholder": "Token del bot (da @BotFather)",
  "settings.chatIdPlaceholder": "Chat ID (es. 123456789)",
  "settings.enableTelegram": "Attiva le notifiche Telegram",
  "settings.sending": "Invio…",
  "settings.saveAndTest": "Salva e invia test",
  "settings.telegramTestSent": "Messaggio di test inviato — controlla la chat Telegram.",

  // ── impostazioni: email ─────────────────────────────────────────────────
  "settings.emailTitle": "✉️ Notifiche email",
  "settings.emailHelp": "Come configuro gli avvisi via email? (funziona con Gmail)",
  "settings.emStep1":
    "Per Gmail: host smtp.gmail.com, porta 587, utente = il tuo indirizzo Gmail.",
  "settings.emStep2a":
    "Gmail richiede una password per app, non la tua password normale. Esiste solo con la verifica in due passaggi attiva, quindi ",
  "settings.emStep2Link": "attivala prima",
  "settings.emStep2b":
    " — finché non lo fai, la pagina delle password per app dirà che non è disponibile per il tuo account.",
  "settings.emStep3a": "Poi creane una su ",
  "settings.emStep3b": " e incolla qui sotto i 16 caratteri (gli spazi vengono ignorati).",
  "settings.emStep4":
    "Destinatario: l'indirizzo dove vuoi ricevere gli avvisi (può essere lo stesso).",
  "settings.emStep5": 'Spunta "Attiva", poi premi "Salva e invia test".',
  "settings.smtpHost": "Host SMTP (es. smtp.gmail.com)",
  "settings.smtpPortTitle": "Porta (587 STARTTLS, 465 SSL)",
  "settings.smtpUser": "Utente SMTP (indirizzo email)",
  "settings.passwordSaved": "Password salvata (lascia vuoto per mantenerla)",
  "settings.appPassword": "Password per app (16 caratteri)",
  "settings.emailFrom": "Mittente (facoltativo, per impostazione predefinita l'utente)",
  "settings.emailTo": "Destinatario (tu@example.com)",
  "settings.enableEmail": "Attiva le notifiche email",
  "settings.emailTestSent":
    "Email di test inviata a {to} — controlla la posta in arrivo (e lo spam).",
  "settings.theRecipient": "il destinatario",

  // ── impostazioni: IMAP ──────────────────────────────────────────────────
  "settings.imapTitle": "📥 Import dalla casella email (IMAP)",
  "settings.imapHelp": "Cos'è? Come si configura? (funziona con Gmail)",
  "settings.imStep1":
    "Permette alla dashboard di setacciare la tua casella alla ricerca di vecchie email di avviso Immobiliare.it / Idealista e importarne gli annunci per la revisione.",
  "settings.imStep2":
    "Rigorosamente in sola lettura: l'app non modifica, non marca e non elimina mai le tue email, e nulla compare nella dashboard finché non lo accetti.",
  "settings.imStep3": "Per Gmail: host imap.gmail.com, porta 993, utente = il tuo indirizzo Gmail.",
  "settings.imStep4":
    "Password: la stessa password per app di 16 caratteri della sezione email qui sopra.",
  "settings.imStep5":
    'Premi "Salva e prova la connessione", poi usa il pannello "📥 Importa dalle email" nella dashboard.',
  "settings.imapHost": "Host IMAP (es. imap.gmail.com)",
  "settings.imapPortTitle": "Porta (993 SSL)",
  "settings.imapUser": "Utente IMAP (indirizzo email)",
  "settings.readOnlyNote": "Accesso in sola lettura: la casella non viene mai modificata.",
  "settings.connecting": "Connessione…",
  "settings.saveAndTestConnection": "Salva e prova la connessione",
  "settings.autoImport":
    "Ripeti automaticamente la scansione della casella per nuove email di annunci",
  "settings.rescanFrequency": "Frequenza di ri-scansione",
  "settings.every6h": "Ogni 6 ore",
  "settings.every12h": "Ogni 12 ore",
  "settings.onceADay": "Una volta al giorno",
  "settings.every3d": "Ogni 3 giorni",
  "settings.onceAWeek": "Una volta a settimana",
  "settings.autoImportNote":
    'I nuovi annunci vengono messi in attesa silenziosamente nella coda di revisione "📥 Importa dalle email" — non ricevi notifiche e nulla compare nella dashboard finché non lo accetti.',

  // ── impostazioni: scansioni ─────────────────────────────────────────────
  "settings.scanTitle": "🔄 Scansione automatica",
  "settings.frequency": "Frequenza",
  "settings.every30m": "Ogni 30 minuti",
  "settings.everyHour": "Ogni ora",
  "settings.every2h": "Ogni 2 ore",
  "settings.every4h": "Ogni 4 ore",
  "settings.every8h": "Ogni 8 ore",
  "settings.pauseScans": "Metti in pausa le scansioni automatiche",
  "settings.pauseScansNote":
    'Impedisce alle scansioni programmate di contattare i portali — utile per far riposare la connessione quando sei via. "Scansiona ora" continua a funzionare su richiesta.',
  "settings.healthTitle": "🚨 Avvisi sulla salute degli scraper",
  "settings.healthNote":
    "Uno scraper rotto è silenzioso: nessun annuncio somiglia in tutto e per tutto a un mercato fermo. Ricevi un avviso quando una ricerca fallisce questo numero di scansioni di fila. I portali bloccano gli scraper ogni tanto, quindi il valore 1 grida al lupo.",
  "settings.alertAfter": "Avvisa dopo",
  "settings.neverDisabled": "Mai (disattivato)",
  "settings.nFailures": "{count} fallimenti consecutivi",

  // ── impostazioni: parole chiave e punteggio ─────────────────────────────
  "settings.keywordsTitle": "🚫 Parole chiave escluse (globali)",
  "settings.keywordsNote":
    "Gli annunci che contengono queste parole vengono scartati automaticamente (solo parole intere, accenti ignorati). Separale con virgole. Ogni ricerca può aggiungere le proprie parole extra oltre a queste.",
  "settings.matchTitle": "🎯 Smart Match Score (casa dei sogni)",
  "settings.matchEnable":
    "Mostra una percentuale di compatibilità su ogni scheda, calcolata sui desideri qui sotto",
  "settings.matchNote":
    "Ogni campo è facoltativo — lascia un numero a 0 per ignorarlo. Solo i desideri che compili contano per il punteggio. Nulla lascia il tuo PC.",
  "settings.dreamMaxPrice": "Prezzo max (€)",
  "settings.dreamMinRooms": "Locali min",
  "settings.dreamMinSqm": "Mq min",
  "settings.dreamMinFloor": "Piano min",
  "settings.dreamFeatures":
    "Caratteristiche desiderate (separate da virgola, es. balcone, ascensore, terrazzo)",
  "settings.dreamZones": "Zone o città preferite (separate da virgola)",

  // ── impostazioni: motore dell'assistente ────────────────────────────────
  "settings.assistantTitle": "🧠 Motore dell'assistente di ricerca",
  "settings.assistantNote":
    'Come il campo "descrivi la ricerca a parole" trasforma il testo in una ricerca. L\'interprete predefinito è offline e istantaneo. Un LLM capisce formulazioni più libere; in caso di errore ricade sull\'interprete offline, e nient\'altro lascia mai il tuo PC.',
  "settings.backendBuiltin": "Interprete integrato (offline, predefinito)",
  "settings.backendLlm": "LLM (compatibile OpenAI / Ollama locale)",
  "settings.llmHintA": "Per un modello gratuito e completamente offline installa ",
  "settings.llmHintB": " e usa come base URL ",
  "settings.llmHintC": " con un modello tipo ",
  "settings.llmHintD": " (nessuna chiave necessaria).",
  "settings.llmBaseUrl": "Base URL (es. http://localhost:11434/v1)",
  "settings.llmModel": "Modello (es. llama3.1)",
  "settings.llmKeySaved": "Chiave API salvata (lascia vuoto per mantenerla)",
  "settings.llmKeyPlaceholder": "Chiave API (vuota per Ollama locale)",

  // ── impostazioni: scraping e aggiramento blocchi ────────────────────────
  "settings.scrapingTitle": "🛡️ Scraping avanzato e aggiramento blocchi",
  "settings.scrapingHelp": "Come risolvere i blocchi DataDome? (istruzioni)",
  "settings.ddStep1":
    "DataDome blocca le richieste HTTP dirette alle singole pagine degli annunci dal tuo IP di casa.",
  "settings.ddStep2":
    "Opzione A: imposta qui sotto un URL proxy (es. socks5://127.0.0.1:9050 per Tor, oppure un proxy HTTP/HTTPS) per instradare il traffico dello scraper.",
  "settings.ddStep3Intro": "Opzione B: copia il valore del cookie datadome dal tuo browser:",
  "settings.ddStep3a":
    "Apri la pagina di un annuncio (es. Immobiliare.it) in Chrome/Firefox.",
  "settings.ddStep3b":
    "Premi F12 e vai alla scheda Applicazione (Chrome) o Archiviazione (Firefox).",
  "settings.ddStep3c":
    "Sotto Cookie, seleziona il dominio del portale, trova datadome e copiane il valore.",
  "settings.ddStep3d":
    "Incollalo nel campo Cookie qui sotto. Nota: scade dopo qualche ora.",
  "settings.proxyUrl": "URL del proxy (HTTP/HTTPS/SOCKS5)",
  "settings.proxyUrlPlaceholder": "es. socks5://127.0.0.1:9050",
  "settings.proxyPool": "Pool di proxy (facoltativo, un URL per riga)",
  "settings.proxyPoolNote":
    "Con più di un proxy, un IP di uscita bloccato riposa per un po' e il tentativo successivo esce da un altro — un indirizzo bruciato non manda più giù tutte le scansioni.",
  "settings.scrapeApiTitle": "🌐 API di scraping (risolve DataDome per te)",
  "settings.scrapeApiNote":
    "Facoltativa. Con una chiave del provider impostata, le scansioni instradano ogni pagina del portale attraverso il provider — che restituisce l'HTML già risolto — così i blocchi smettono di colpire il tuo IP di casa. I piani gratuiti (~1.000 chiamate al mese) bastano per uno scanner personale. Lascia vuoto per mantenere il percorso locale (gratuito, offline).",
  "settings.scrapeKeySaved": "Chiave già salvata (lascia vuoto per mantenerla)",
  "settings.scrapeKeyPlaceholder": "Chiave API del provider",
  "settings.whenToUse": "Quando usarla",
  "settings.modeFallback": "Solo come ripiego quando il percorso gratuito è bloccato",
  "settings.modeAlways": "Sempre (ogni richiesta passa dal provider)",
  "settings.modeNote":
    '"Ripiego" (l\'impostazione predefinita) consuma i crediti API solo durante un vero disservizio: le scansioni partono dal percorso locale gratuito e passano al provider quando vengono bloccate.',
  "settings.cookieLabel": "Cookie DataDome",
  "settings.cookieSaved": "Cookie già salvato (lascia vuoto per mantenerlo)",
  "settings.cookiePlaceholder": "Incolla il valore del cookie datadome",

  // ── impostazioni: raccolta cookie e browser ─────────────────────────────
  "settings.harvestTitle": "🤖 Ottieni il cookie automaticamente",
  "settings.harvestNote":
    "Apre un browser locale, ottiene un cookie fresco e lo salva — senza copia/incolla. Potrebbe aprirsi una finestra: se il portale mostra un CAPTCHA, risolvilo una volta e verrà ricordato.",
  "settings.grabCookie": "🔄 Ottieni subito un cookie fresco",
  "settings.openingBrowser": "Apertura del browser…",
  "settings.cookieGrabbed": "Nuovo cookie DataDome salvato ({preview}).",
  "settings.autoRefreshCookie":
    "Rinnova il cookie automaticamente prima di ogni scansione (headless)",
  "settings.browserFirst":
    'Esegui la verifica "è ancora online?" tramite browser invece che con richieste rapide — più lento per annuncio, ma mantiene un cookie reale così DataDome non lo interrompe con blocchi 403.',
  "settings.browserHeadful":
    "Mostra la finestra del browser durante la verifica così puoi risolvere a mano un eventuale CAPTCHA — una sola soluzione sblocca l'intera esecuzione. Funziona meglio insieme all'opzione qui sopra. Ignorata quando l'app gira come servizio Windows in background.",
  "settings.browserHumanize":
    "Muovi il mouse e scorri come una persona su ogni pagina aperta dal browser — i sistemi anti-bot valutano anche il comportamento, e una pagina visitata senza alcun evento del puntatore sembra robotica. Aggiunge circa un secondo per pagina.",
  "settings.browserEngine": "Motore browser:",
  "settings.engineAuto": "Auto (Camoufox se installato, altrimenti Chromium)",
  "settings.engineCamoufox": "Camoufox (Firefox stealth)",
  "settings.engineChromium": "Chromium",
  "settings.camoufoxNote":
    "Camoufox è un Firefox stealth che nasconde i segnali di automazione che DataDome cerca, così la verifica viene sfidata molto meno spesso.",
  "settings.camoufoxInstalled": "Installato ✓",
  "settings.camoufoxMissing":
    "Non installato — un clic lo aggiunge (~150 MB, una tantum):",
  "settings.installCamoufox": "⚡ Installa Camoufox con un clic",
  "settings.installingCamoufox": "⚡ Installazione di Camoufox (~1-3 min)…",
  "settings.camoufoxInstalledMsg": "Camoufox installato con successo!",
  "settings.harvesterMissing":
    "Non ancora installato in questo ambiente Python. Puoi installare Playwright e Chromium automaticamente con un clic:",
  "settings.installHarvester": "⚡ Installa Playwright e Chromium con un clic",
  "settings.installingHarvester": "⚡ Installazione di Playwright e Chromium (~1-2 min)…",
  "settings.harvesterInstalledMsg": "Playwright e Chromium installati con successo!",
  "settings.manualInstall":
    "Oppure installali a mano da terminale con `install-playwright.bat` nella cartella del progetto, o esegui: ",

  // ── impostazioni: token API e riavvio ───────────────────────────────────
  "settings.apiTokenTitle": "🔒 Token di accesso all'API",
  "settings.apiTokenNote":
    "Per impostazione predefinita la dashboard è raggiungibile da chiunque arrivi al suo indirizzo (per questo si lega a localhost). Imposta un token per richiederlo a ogni richiesta — così è sicuro esporre l'app sulla tua LAN o su Tailscale. Lascia vuoto per tenerla aperta. Su questo dispositivo resti autenticato; agli altri il token viene chiesto una volta.",
  "settings.apiTokenPlaceholder": "Nessun token (accesso libero)",
  "settings.backendTitle": "🔄 Backend",
  "settings.backendNote":
    "Riavvia il processo del backend — usalo dopo aver aggiornato l'app perché le novità abbiano effetto, invece di chiudere e riaprire la finestra del terminale. La dashboard va offline per qualche secondo e poi si ricarica da sola.",
  "settings.restart": "🔄 Riavvia il backend",
  "settings.restarting": "⏳ Riavvio… (in attesa del backend)",
  "settings.restartConfirm":
    "Riavviare ora il backend? La dashboard resta non disponibile per qualche secondo, poi si ricarica da sola.",
  "settings.restartTooOld":
    "Questo backend in esecuzione è troppo vecchio per riavviarsi da solo — chiudi la sua finestra del terminale e rilancia start.bat / serve.bat una volta. Dopodiché questo pulsante (e le funzioni più recenti) funzionerà.",
  "settings.restartNoReturn":
    "Il backend non è tornato da solo — controlla la finestra del terminale (o rilancia start.bat / serve.bat).",

  // ── impostazioni: gestione dei dati ─────────────────────────────────────
  "settings.dataTitle": "🧹 Gestione dei dati",
  "settings.dataNote":
    "Irreversibile. Le impostazioni di notifica e di accesso vengono sempre mantenute.",
  "settings.resetImportsName": "Azzera gli import da email",
  "settings.resetImportsBody":
    " — cancella ogni annuncio trovato nella casella così puoi reimportare da zero (dimentica anche quelli scartati).",
  "settings.resetImportsButton": "Azzera gli import",
  "settings.resetImportsConfirm":
    "Eliminare TUTTI gli annunci importati dalle email? Potrai rilanciare l'import dalla casella in seguito.",
  "settings.clearDashboardName": "Svuota la dashboard",
  "settings.clearDashboardBody":
    " — elimina tutti gli immobili trovati e lo storico dei prezzi. Le tue ricerche restano; la prossima scansione ricostruisce la griglia in silenzio.",
  "settings.clearDashboardButton": "Svuota la dashboard",
  "settings.clearDashboardConfirm":
    "Eliminare TUTTI gli immobili e il loro storico prezzi? Le ricerche vengono mantenute e la prossima scansione ricostruirà la dashboard.",
  "settings.clearTrendsName": "Azzera gli andamenti dei prezzi",
  "settings.clearTrendsBody":
    " — rimuove lo storico delle mediane giornaliere dietro ai grafici, senza toccare nessun annuncio.",
  "settings.clearTrendsButton": "Azzera gli andamenti",
  "settings.clearTrendsConfirm":
    "Eliminare lo storico degli andamenti dei prezzi? I grafici ripartiranno dalla prossima scansione.",
  "settings.factoryName": "Ripristino di fabbrica",
  "settings.factoryBody":
    " — cancella tutto (dashboard, ricerche, import, andamenti) tornando a un'installazione nuova. Viene salvato prima un backup del database.",
  "settings.factoryButton": "Ripristino di fabbrica",
  "settings.factoryConfirm":
    "Ripristino di fabbrica: elimina la dashboard, TUTTE le ricerche, gli import e gli andamenti. Viene salvato prima un backup. Continuare?",
  "settings.lastChance":
    "Ultima possibilità: questo cancella tutto e non si può annullare. Continuare?",
  "settings.resetDone": "Fatto — rimossi {removed}. Ricaricamento…",
  "settings.resetDoneBackup":
    "Fatto — rimossi {removed} · backup salvato: {backup}. Ricaricamento…",
  "settings.resetNothing": "nulla",

  // ── ricerche monitorate: struttura e modalità ───────────────────────────
  "profiles.title": "🔍 Ricerche monitorate",
  "profiles.statusOk": "OK",
  "profiles.statusBlocked": "Bloccata (riproverà)",
  "profiles.statusError": "Errore",
  "profiles.modeAssistant": "💬 Descrivila e basta",
  "profiles.modeBuilder": "🧭 Costruisci una ricerca",
  "profiles.modeUrl": "🔗 Incolla un URL",
  "profiles.empty":
    "Nessuna ricerca configurata. Costruiscine una con i tuoi criteri oppure incolla l'URL dei risultati da Immobiliare.it / Idealista per iniziare.",
  "profiles.untitled": "Ricerca senza nome",
  "profiles.defaultName": "Ricerca monitorata",
  "profiles.labelRent": "Affitto",
  "profiles.labelBuy": "Acquisto",
  "profiles.labelRooms": "{count}+ locali",

  // ── ricerche monitorate: caratteristiche, piani, stato ──────────────────
  "profiles.featBalcony": "Balcone",
  "profiles.featGarden": "Giardino",
  "profiles.featParking": "Box / posto auto",
  "profiles.featElevator": "Ascensore",
  "profiles.featExcludeAuctions": "Escludi le aste",
  "profiles.featPool": "Piscina",
  "profiles.floorAny": "Qualsiasi piano",
  "profiles.floorGround": "Piano terra",
  "profiles.floorMiddle": "Piani intermedi",
  "profiles.floorTop": "Ultimo piano",
  "profiles.condAny": "Qualsiasi stato",
  "profiles.condNew": "Nuova costruzione",
  "profiles.condGood": "Buono / abitabile",
  "profiles.condExcellent": "Ottimo / ristrutturato",
  "profiles.condToRenovate": "Da ristrutturare",
  "profiles.unsupportedFloor": "questa fascia di piano",
  "profiles.unsupportedCondition": "questo stato",
  "profiles.unsupportedMaxRooms":
    "un tetto di 5 o più locali (la sua fascia più alta è “5 o più”)",

  // ── ricerche monitorate: canali di notifica ─────────────────────────────
  "profiles.chAll": "🔔 Tutti i canali",
  "profiles.chAllWarn":
    "Nessun canale di notifica è ancora configurato — questa ricerca non invierà avvisi. Configura Telegram o Email in ⚙️ Impostazioni.",
  "profiles.chTelegram": "📨 Solo Telegram",
  "profiles.chTelegramOff": "📨 Solo Telegram (non configurato)",
  "profiles.chTelegramWarn":
    "Telegram non è configurato — questa ricerca non invierà avvisi. Aggiungi il token del bot e il chat ID in ⚙️ Impostazioni.",
  "profiles.chEmail": "✉️ Solo Email",
  "profiles.chEmailOff": "✉️ Solo Email (non configurata)",
  "profiles.chEmailWarn":
    "L'email non è configurata — questa ricerca non invierà avvisi. Configura l'SMTP in ⚙️ Impostazioni.",
  "profiles.chNone": "🔕 Nessuna notifica",

  // ── ricerche monitorate: assistente ─────────────────────────────────────
  "profiles.assistantIntro":
    'Descrivi ciò che cerchi in italiano o in inglese — anche più alternative insieme ("bilocale in zona X o trilocale in zona Y"). Il testo viene interpretato sul tuo PC — nulla viene inviato a servizi di IA — e rivedi ogni ricerca prima che venga salvata.',
  "profiles.assistantPlaceholder":
    "es. trilocale in affitto a Milano sotto i 1.200 € al mese",
  "profiles.assistantReading": "Lettura…",
  "profiles.assistantSubmit": "Interpretala →",
  "profiles.assistantTry": "Prova:",
  "profiles.multiIntro":
    "Ho letto {count} ricerche alternative nella tua frase. Controllale una per una (apri i link per verificare i risultati), poi crea tutti i profili in un colpo solo.",
  "profiles.reword": "✏️ Riformula",
  "profiles.searchNumber": "Ricerca {n}",
  "profiles.editInBuilder": "Modifica questa ricerca nel modulo guidato",
  "profiles.dropAlternative": "Elimina questa alternativa",
  "profiles.createProfiles": "Crea {count} profili",
  "profiles.allAlreadyPresent": "Tutte le ricerche selezionate sono già presenti e monitorate.",
  "profiles.duplicateExists":
    "Esiste già una ricerca monitorata identica ('{name}') con lo stesso URL e le stesse parole chiave escluse.",
  "profiles.duplicateParams":
    "Esiste già una ricerca monitorata identica per i parametri selezionati.",

  // ── ricerche monitorate: modulo URL ─────────────────────────────────────
  "profiles.urlIntro":
    "Vai su Immobiliare.it o Idealista, imposta zona e filtri sulla mappa, poi copia qui l'URL della pagina dei risultati.",
  "profiles.urlTip":
    '💡 È così che usi tutti i filtri del portale — bagni, piano, ascensore, terrazzo, classe energetica, tipologia, escludi aste e così via. Impostali sul portale, poi incolla l\'URL: l\'app monitora esattamente quella ricerca. I due strumenti qui sopra ("Descrivila e basta" / "Costruisci una ricerca") coprono solo città, prezzo, locali e superficie.',
  "profiles.namePlaceholder": "Nome (es. Trilocali Milano Sud)",
  "profiles.keywordsPlaceholder":
    "Parole chiave escluse aggiuntive (facoltative, separate da virgola)",
  "profiles.urlPlaceholder":
    "https://www.immobiliare.it/vendita-case/milano/?prezzoMassimo=300000…",
  "profiles.extractParams": "🪄 Estrai i parametri",
  "profiles.extractParamsTitle": "Estrai città e filtri nel modulo guidato",
  "profiles.saveChanges": "Salva le modifiche",
  "profiles.saveProfile": "Salva la ricerca",

  // ── ricerche monitorate: modulo guidato ─────────────────────────────────
  "profiles.understood": "Ho capito:",
  "profiles.checkFields":
    "Controlla i campi qui sotto — correggi tutto ciò che l'interprete ha sbagliato.",
  "profiles.builderIntroPrefix":
    "Scegli i criteri e gli URL di ricerca corretti dei portali vengono generati per te — nessun copia/incolla dal browser. Copre le basi (città, prezzo, locali, superficie); per bagni, piano, caratteristiche o classe energetica impostali sul portale e usa ",
  "profiles.builderIntroSuffix": ".",
  "profiles.cityRequired": "Città *",
  "profiles.province": "Provincia",
  "profiles.provinceTitle":
    "Idealista ha bisogno della provincia; lasciala vuota se la città è capoluogo",
  "profiles.optional": "(facoltativo)",
  "profiles.zoneTitle":
    "Quartiere, al meglio possibile: apri gli URL generati per verificare che il portale lo riconosca",
  "profiles.minRooms": "Locali min",
  "profiles.moreCriteria": "Altri criteri",
  "profiles.moreCriteriaHint": "· applicati a entrambi i portali",
  "profiles.condition": "Stato",
  "profiles.builderTipPrefix":
    "💡 Ti servono bagni, terrazzo, classe energetica, tipologia o un altro filtro? Impostalo sul portale e ",
  "profiles.builderTipLink": "incolla l'URL dei risultati",
  "profiles.builderTipSuffix": " — così catturi tutti i filtri offerti dal portale.",
  "profiles.profileNamePlaceholder": "Nome della ricerca (facoltativo)",
  "profiles.generate": "Genera gli URL di ricerca",
  "profiles.generating": "Verifica della zona su Idealista…",
  "profiles.checkGenerated":
    "Controlla le ricerche generate (aprile per verificare i risultati), poi crea i profili:",
  "profiles.zoneKnown": "Idealista conosce la zona “{zone}”: userò la sua pagina esatta.",
  "profiles.zoneUnknown":
    "Idealista non ha una pagina di zona per “{zone}”, quindi ne cerca il nome come testo — aspettati qualche annuncio fuori zona che la cita soltanto.",
  "profiles.idealistaUnsupported":
    "Idealista non ha un filtro di ricerca per {filters}, quindi la sua metà di questa coppia è la ricerca più ampia — aspettati lì annunci che Immobiliare esclude.",
  "profiles.createProfilesButton": "Crea le ricerche",

  // ── ricerche monitorate: azioni in blocco e righe ───────────────────────
  "profiles.selectAll": "Seleziona tutte",
  "profiles.selectRow": "Seleziona {name}",
  "profiles.selectedCount": "{count} selezionate",
  "profiles.activate": "▶️ Attiva",
  "profiles.pause": "⏸️ Metti in pausa",
  "profiles.notificationsAction": "Notifiche →",
  "profiles.deleteAction": "🗑 Elimina",
  "profiles.mergeSelected": "🔗 Accorpa i selezionati",
  "profiles.mergeSelectedTitle": "Accorpa i portali selezionati in un unico box di ricerca",
  "profiles.mergePrompt":
    "Inserisci il nome univoco per accorpare le ricerche selezionate in un solo box:",
  "profiles.clearSelection": "Deseleziona",
  "profiles.merged": "Accorpata ({count} portali)",
  "profiles.mergedTitle": "Ricerche su più portali accorpate in un solo box",
  "profiles.separateConfirm":
    'Vuoi separare i portali di "{name}" in box di ricerca distinti?',
  "profiles.excludesTitle":
    "Gli annunci che citano una di queste parole vengono scartati (Impostazioni + gli extra di questa ricerca)",
  "profiles.excludes": "🚫 Esclude: {words}",
  "profiles.globalKeywords":
    "🌐 Sempre escluse per ogni ricerca (dalle Impostazioni): {words}",
  "profiles.notifyTitle": "Dove inviare le notifiche di questa ricerca",
  "profiles.active": "Attiva",
  "profiles.editBox": "Modifica questo box di ricerca",
  "profiles.separateBox": "Separa i portali in box singoli indipendenti",
  "profiles.deleteBox": "Elimina questo box di ricerca (tutti i portali associati)",
  "profiles.chipRent": "🔑 Affitto",
  "profiles.chipBuy": "🏠 Acquisto",
  "profiles.chipRooms": "🛏️ {range} locali",
  "profiles.chipMinSqm": "📐 ≥ {value} mq",

  // ── ricerche monitorate: dialogo di eliminazione ────────────────────────
  "profiles.deleteOne": "Eliminare “{name}”?",
  "profiles.deleteGroup": "Eliminare “{name}” ({count} portali)?",
  "profiles.deleteBodyOne":
    "La ricerca smette di essere monitorata. I suoi risultati sono già nella dashboard — scegli tu se eliminarli.",
  "profiles.deleteBodyMany":
    "Le ricerche smettono di essere monitorate. I loro risultati sono già nella dashboard — scegli tu se eliminarli.",
  "profiles.countingResults": "Conteggio dei risultati…",
  "profiles.noneAttributableOne":
    "Nessun immobile nella dashboard è attribuibile a questa ricerca, quindi “elimina anche i risultati” non ha nulla da eliminare. I risultati vengono attribuiti dalle scansioni che li hanno trovati: una ricerca eliminata prima di girare non lascia traccia.",
  "profiles.noneAttributableMany":
    "Nessun immobile nella dashboard è attribuibile a queste ricerche, quindi “elimina anche i risultati” non ha nulla da eliminare. I risultati vengono attribuiti dalle scansioni che li hanno trovati: una ricerca eliminata prima di girare non lascia traccia.",
  "profiles.foundOne": "Ha trovato {tracked} immobili; ne verrebbero eliminati {deletable}.",
  "profiles.foundMany": "Hanno trovato {tracked} immobili; ne verrebbero eliminati {deletable}.",
  "profiles.keptShared": "· {count} mantenuti: trovati anche da una ricerca che conservi",
  "profiles.keptCurated": "· {count} mantenuti: messi tra i preferiti o annotati da te",
  "profiles.deleteIrreversible":
    "L'eliminazione è irreversibile: storico dei prezzi compreso.",
  "profiles.keepResults": "Mantieni i risultati",
  "profiles.deleting": "Eliminazione…",
  "profiles.deleteWith": "Elimina con {count} immobili",

  // ── import da email: struttura del pannello ─────────────────────────────
  "email.title": "📥 Importa dalle email",
  "email.toReview": "({count} da rivedere)",
  "email.hide": "Nascondi",
  "email.open": "Apri",
  "email.intro":
    'Setaccia la tua casella alla ricerca di email con annunci e rivedili qui: accetta quelli che ti interessano, scarta il resto. La casella viene letta in sola lettura e i duplicati di annunci già monitorati vengono saltati automaticamente. Le email di avviso possono avere mesi, quindi un annuncio potrebbe essere già venduto o ritirato — "Apri ↗" è l\'unico modo per scoprirlo, perché questo pannello non visita mai i portali.',
  "email.portalsOnlyPrefix": "Si possono importare solo gli annunci ",
  "email.portalsOnlyBold": "ospitati su Immobiliare.it o Idealista.it",
  "email.portalsOnlySuffix":
    ": tutta l'app è costruita attorno ai loro ID annuncio. L'email di un'agenzia vale solo se rimanda a un annuncio su un portale — una che rimanda al sito dell'agenzia non porta nulla, qualunque mittente tu cerchi.",
  "email.imapMissing":
    '⚠️ IMAP non è ancora configurato — apri ⚙️ Impostazioni → "Import dalla casella email" e inserisci host, utente e password per app.',
  "email.unknownError": "Errore sconosciuto",
  "email.nothingToCheck":
    "Nessun annuncio da verificare. Scansiona le email o seleziona un annuncio specifico per forzare il ricalcolo.",
  "email.confirmDiscardAll":
    "Scartare tutti i {count} annunci mostrati qui? Non torneranno nelle prossime scansioni.",
  "email.confirmDiscardAllOne":
    "Scartare l'annuncio ({count}) mostrato qui? Non tornerà nelle prossime scansioni.",
  "email.cookieSaveFailed": "Impossibile salvare il cookie: {error}",
  "email.nothingToReview": "Niente da rivedere.",
  "email.nothingToReviewYet": "Niente da rivedere — lancia una scansione qui sopra.",

  // ── import da email: modulo di scansione ────────────────────────────────
  "email.lookFor": "Cerca",
  "email.modePortals": "Email di avviso dei portali",
  "email.modeAddress": "Mittenti specifici",
  "email.modeAny": "Qualsiasi email con un link a un annuncio",
  "email.senders": "Mittenti (indirizzi o domini separati da virgola)",
  "email.sendersTitle":
    "Le loro email devono rimandare a un annuncio Immobiliare.it o Idealista.it: un link al sito dell'agenzia non è importabile",
  "email.sendersPlaceholder": "es. agenzia@example.com, immobiliare.it",
  "email.period": "Periodo",
  "email.lastMonth": "Ultimo mese",
  "email.last6Months": "Ultimi 6 mesi",
  "email.lastYear": "Ultimo anno",
  "email.last5Years": "Ultimi 5 anni",
  "email.maxEmails": "Email max",
  "email.maxEmailsTitle":
    "Prima i messaggi più recenti; rilancia la scansione per andare più a fondo (gli annunci già importati vengono saltati)",
  "email.scan": "Scansiona la casella",
  "email.scanning": "Scansione della casella…",
  "email.phaseConnecting": "Connessione alla casella…",
  "email.phaseSearching": "Ricerca nella casella…",
  "email.phaseReading": "Lettura email {done} di {total} — {staged} nuovi annunci in attesa",
  "email.phaseReadingOne": "Lettura email {done} di {total} — {staged} nuovo annuncio in attesa",
  "email.phaseStarting": "Avvio…",
  "email.scanNote":
    "Le caselle grandi richiedono qualche minuto; nel frattempo puoi continuare a usare la dashboard.",
  "email.scanSummary":
    "✅ Analizzate {emails} email ({withListings} con annunci) — {imported} nuovi annunci in attesa, {tracked} già monitorati dalle tue ricerche, {seen} già visti in una scansione precedente.",
  "email.blankLinks":
    " {count} link sono stati saltati: l'email non dava prezzo, superficie o nome per poterli valutare.",
  "email.blankLinksOne":
    " {count} link è stato saltato: l'email non dava prezzo, superficie o nome per poterlo valutare.",
  "email.blankRemoved":
    " {count} righe di questo tipo lasciate da scansioni precedenti sono state ripulite.",
  "email.blankRemovedOne":
    " {count} riga di questo tipo lasciata da scansioni precedenti è stata ripulita.",

  // ── import da email: filtri di revisione ────────────────────────────────
  "email.statusTitle":
    "Scegli se mostrare gli annunci in attesa, scartati o già accettati",
  "email.statusPending": "⏳ In attesa",
  "email.statusDiscarded": "🗑️ Scartati",
  "email.statusAccepted": "✅ Accettati",
  "email.statusAll": "📋 Tutti",
  "email.filterLikeSearch": "Filtra come una ricerca",
  "email.filterLikeSearchTitle":
    "Riusa contratto, città e parole escluse di una ricerca che già monitori",
  "email.adHocFilters": "— filtri ad hoc —",
  "email.contract": "Contratto",
  "email.any": "Qualsiasi",
  "email.textSearch": "Ricerca testuale",
  "email.textSearchPlaceholder": "nel titolo/oggetto",

  // ── import da email: barra delle azioni ─────────────────────────────────
  "email.selectAll": "Seleziona tutti ({count})",
  "email.acceptSelected": "✓ Accetta i selezionati",
  "email.discardSelected": "✕ Scarta i selezionati",
  "email.discardAll": "🗑 Scarta tutti ({count})",
  "email.discardAllTitle":
    "Scarta tutti gli annunci attualmente mostrati (i filtri qui sopra restano applicati).",
  "email.cookieSaved": "Cookie DataDome salvato",
  "email.cookiePaste": "Incolla il cookie DataDome…",
  "email.cookieTitle":
    "Incolla qui il cookie 'datadome' del tuo browser per superare i blocchi dei portali",
  "email.checkTitle":
    "Interroga le pagine dei portali per vedere quali sono ancora online e aggiornarne foto e dati. Se non selezioni nulla, verifica quelli non ancora controllati.",
  "email.checkSelected": "🔎 Verifica i selezionati ({count})",
  "email.checkAll": "🔎 Verifica la disponibilità online",
  "email.discardGone": "🚫 Scarta i {count} rimossi",
  "email.discardGoneTitle":
    "Scarta in un colpo solo tutti gli annunci che il portale ha confermato come rimossi/inesistenti",
  "email.sortBy": "Ordina per:",
  "email.sortDate": "Email più recente",
  "email.sortSqmPrice": "€/m² (più economici)",
  "email.sortPrice": "Prezzo (più basso)",
  "email.checkProgress": "Verifica annuncio {done} di {total} — {gone} già rimossi…",
  "email.checkPacing":
    "(Una pagina ogni 6 secondi per evitare che i portali blocchino l'IP)",
  "email.checkResult": "🔎 Esito della verifica su {count} annunci:",
  "email.checkGone": "{count} non più online (rimossi)",
  "email.checkOnline": "{count} ancora online e aggiornati",
  "email.checkUnknown": " ({count} non conclusivi per un blocco o un errore di rete)",
  "email.cookieRefreshedOnce":
    "🔄 Cookie DataDome rinnovato automaticamente una volta durante la verifica per superare i controlli anti-bot.",
  "email.cookieRefreshed":
    "🔄 Cookie DataDome rinnovato automaticamente {count} volte durante la verifica per superare i controlli anti-bot.",
  "email.lastErrorDetail": "❌ Dettaglio dell'ultimo errore: {error}",
  "email.checkAborted":
    "⚠️ Il portale ha iniziato a bloccare le richieste, quindi la verifica è stata interrotta per proteggere l'IP della rete. Incolla un cookie DataDome fresco o riprova più tardi.",

  // ── import da email: scheda annuncio ────────────────────────────────────
  "email.openOriginal": "Apri l'annuncio originale sul portale",
  "email.listingPhoto": "Foto dell'annuncio",
  "email.listingNumber": "Annuncio #{id}",
  "email.badgeAccepted": "✅ Accettato",
  "email.badgeDiscarded": "🗑️ Scartato",
  "email.badgeOnline": "🟢 Online sul portale",
  "email.badgeOnlineTitle":
    "Il portale ha confermato che la pagina dell'annuncio è ancora online e raggiungibile",
  "email.badgeRemoved": "🔴 Rimosso / Non disponibile",
  "email.badgeRemovedTitle": "Il portale ha risposto 'pagina non trovata' (404/rimosso)",
  "email.badgeUnchecked": "⚪ Non verificato",
  "email.badgeUncheckedTitle":
    "Disponibilità non ancora verificata sul portale. Usa 'Verifica se è online'",
  "email.sqmUnit": "{value} m²",
  "email.roomsUnit": "{count} locali",
  "email.contractRent": "affitto",
  "email.contractSale": "vendita",
  "email.emailOf": "email del {date}",
  "email.sqmPriceMonth": "{value} €/m² al mese",
  "email.sqmPriceUnit": "{value} €/m²",
  "email.sqmPriceTitle": "Prezzo al metro quadro calcolato dall'email",
  "email.openPage": "Apri ↗",
  "email.openPageTitle": "Apri la pagina originale sul portale",
  "email.accept": "✓ Accetta",
  "email.recoverAccept": "✓ Recupera / Accetta",
  "email.acceptTitle": "Aggiungi alla dashboard principale (con deduplica automatica)",
  "email.discard": "✕ Scarta",
  "email.discardTitle":
    "Scarta l'annuncio (non verrà ricaricato nelle prossime scansioni)",

  // ── mappa ───────────────────────────────────────────────────────────────
  "map.pinDrop": "📉 Calo di prezzo",
  "map.pinFavorite": "★ Preferito",
  "map.pinFiltered": "🚫 Filtrato",
  "map.pinGone": "💨 Non più disponibile",
  "map.pinSold": "🔑 Venduto / affittato",
  "map.pinActive": "Annuncio attivo",
  "map.onMap": "{shown} di {total} immobili sulla mappa",
  "map.missing": "{count} senza coordinate",
  "map.missingTitle":
    "I portali non pubblicano le coordinate per ogni annuncio; quegli immobili restano comunque nella vista a griglia.",
  "map.drawRadius": "◯ Disegna un raggio",
  "map.drawingRadius": "◯ Clicca il centro, trascina la maniglia…",
  "map.drawRadiusTitle":
    "Clicca sulla mappa per fissare il centro, poi trascina la maniglia per dimensionare il raggio.",
  "map.drawArea": "⬠ Disegna un'area",
  "map.finishArea": "⬠ Chiudi l'area",
  "map.drawAreaTitle":
    "Clicca per aggiungere ogni vertice; fai doppio clic o premi Chiudi per chiudere l'area.",
  "map.polyHint": "{count} punti — ne servono ≥ 3, poi doppio clic per chiudere",
  "map.clearZone": "✕ Rimuovi la zona",
  "map.radiusActive": "Raggio di {km} km attivo",
  "map.areaActive": "Filtro per area attivo",
  "map.zoneWarning":
    "Filtro per zona attivo — {count} immobili senza coordinate non possono essere posizionati e restano esclusi.",
  "map.zoneWarningOne":
    "Filtro per zona attivo — {count} immobile senza coordinate non può essere posizionato e resta escluso.",
  "map.findCoordinates": "Trova le coordinate",
  "map.findingCoordinates": "Ricerca delle coordinate…",
  "map.noneGeolocated":
    "Nessuno degli immobili attuali ha coordinate — lancia una scansione o torna alla vista a griglia.",
  "map.attribution":
    "Clicca un segnaposto per aprire l'immobile. Dati della mappa © contributori OpenStreetMap (le tile sono scaricate online).",

  // ── velocità del mercato ────────────────────────────────────────────────
  "velocity.title": "📊 Velocità del mercato",
  "velocity.subtitleSale":
    "quanto in fretta gli annunci lasciano il mercato, e come li prezzano le agenzie",
  "velocity.subtitleRent":
    "quanto in fretta gli affitti lasciano il mercato, e come li prezzano le agenzie",
  "velocity.loadFailed": "Impossibile caricare le statistiche",
  "velocity.tracked": "{count} immobili monitorati",
  "velocity.inCity": " a “{city}”",
  "velocity.left": ", {count} hanno lasciato il mercato",
  "velocity.confirmedSold": " ({count} venduti confermati)",
  "velocity.observedSince": " · osservati dal {date}",
  "velocity.minSample":
    ". Zone e agenzie con meno di {count} osservazioni non vengono mostrate.",
  "velocity.empty":
    "Storico ancora insufficiente. Questi segnali richiedono almeno {count} immobili per zona e qualche settimana di scansioni prima di dire qualcosa — il database si sta ancora riempiendo.",
  "velocity.areasTitle": "Zone",
  "velocity.areasHint": "(prima le più veloci)",
  "velocity.colArea": "Zona",
  "velocity.colTracked": "Monitorati",
  "velocity.colDaysToExit": "Giorni all'uscita",
  "velocity.colDaysToExitTitle":
    "Giorni mediani tra la prima volta che una scansione ha visto l'annuncio e il giorno in cui è sparito",
  "velocity.colStillListed": "Ancora online",
  "velocity.colStillListedTitle":
    "Giorni mediani da cui gli annunci ancora online sono lì",
  "velocity.colLeftMarket": "Usciti dal mercato",
  "velocity.colLeftMarketTitle": "Quota di immobili monitorati che ha lasciato il mercato",
  "velocity.colCutPrice": "Prezzo ridotto",
  "velocity.colCutPriceTitle":
    "Quota di immobili monitorati il cui prezzo è calato almeno una volta",
  "velocity.wholeCity": "tutta la città",
  "velocity.agenciesTitle": "Agenzie",
  "velocity.agenciesHint": "(chi chiede sopra la mediana locale, e chi sconta)",
  "velocity.colAgency": "Agenzia",
  "velocity.colListings": "Annunci",
  "velocity.colVsArea": "vs €/mq della zona",
  "velocity.colVsAreaTitle":
    "Mediana €/mq confrontata con la mediana della stessa zona. Positivo = chiede più della zona.",
  "velocity.colAgencyCutTitle":
    "Quota di annunci di questa agenzia il cui prezzo è calato almeno una volta",
  "velocity.colTypicalCut": "Sconto tipico",
  "velocity.colTypicalCutTitle":
    "Sconto mediano tra gli annunci effettivamente ribassati",
  "velocity.caveat":
    "“Usciti dal mercato” significa che nessuna scansione vede l'annuncio da una settimana: venduto, affittato, ritirato o ripubblicato con un nuovo id — non è la prova di una vendita. I giorni sul mercato si contano dal giorno in cui questa app ha visto l'annuncio per la prima volta, quindi gli immobili già online quando hai aggiunto la ricerca sembrano più giovani di quanto siano. Entrambe le distorsioni si attenuano col tempo.",

  // ── andamento dei prezzi ────────────────────────────────────────────────
  "trends.title": "📈 Andamento dei prezzi",
  "trends.subtitle": "come si è mosso nel tempo il €/mq mediano nelle zone che segui",
  "trends.wholeCity": "{city} · tutta la città",
  "trends.areaOption": "{label} ({days} giorni)",
  "trends.chartAria": "Prezzo mediano al metro quadro nel tempo",
  "trends.pointTooltip": "{date}: {value} €/mq",
  "trends.areasFailed": "Impossibile caricare gli andamenti",
  "trends.trendFailed": "Impossibile caricare l'andamento",
  "trends.listingsFailed": "Impossibile caricare gli annunci",
  "trends.empty":
    "Nessuno storico da rappresentare. L'app registra una mediana per zona al giorno; una linea di tendenza ha bisogno di almeno due giorni di scansioni prima di dire qualcosa — ripassa tra un paio di giorni.",
  "trends.changeSince": "{arrow} {pct}% dal {date}",
  "trends.caveat":
    "Prezzo richiesto mediano al metro quadro tra gli annunci che l'app stava monitorando ogni giorno — il tuo campione, non tutto il mercato. Si muove con ciò che monitori tanto quanto con i prezzi.",
  "trends.oneDayOnly":
    "Per questa zona è registrato un solo giorno — la linea compare quando ce ne sono almeno due.",
  "trends.showComparables": "🔍 Mostra gli annunci dietro questa mediana ▼",
  "trends.hideComparables": "Nascondi gli annunci dietro questa mediana ▲",
  "trends.comparablesEmpty": "In questa zona non c'è al momento nessun annuncio con prezzo.",
  "trends.comparablesNote":
    "I {count} annunci attualmente prezzati in questa zona — l'insieme attuale da cui si calcola la mediana di oggi. I punti precedenti del grafico hanno conservato solo il conteggio, quindi i loro annunci esatti non sono più mostrabili. Cliccane uno per aprirne i dettagli.",
  "trends.comparablesNoteOne":
    "L'unico annuncio ({count}) attualmente prezzato in questa zona — l'insieme attuale da cui si calcola la mediana di oggi. I punti precedenti del grafico hanno conservato solo il conteggio, quindi i loro annunci esatti non sono più mostrabili. Cliccalo per aprirne i dettagli.",
  "trends.vsMedian": " ({sign}{pct}% rispetto alla mediana)",

  // ── log del backend ─────────────────────────────────────────────────────
  "logs.title": "📜 Log del backend",
  "logs.filterPlaceholder": "Filtra (es. availability_check, blocked, error)",
  "logs.autoRefresh": "Aggiornamento automatico (3s)",
  "logs.lineCount": "{visible} / {total} righe",
  "logs.loadFailed": "Impossibile caricare il log",
  "logs.empty": "Nessuna riga di log — si riempie appena parte una scansione o una verifica.",
  "logs.noMatch": "Nessuna riga corrisponde a questo filtro.",
  "logs.source": "Origine: {path}",

  // ── salute degli scraper ────────────────────────────────────────────────
  "health.title": "🩺 Salute degli scraper",
  "health.subtitle": "la pipeline anti-bot riesce ancora a passare?",
  "health.hide": "Nascondi ▲",
  "health.show": "Mostra ▼",
  "health.loadFailed": "Impossibile caricare la salute degli scraper",
  "health.window":
    "Ultimi {days} giorni di esiti delle scansioni per portale. La prossima scansione parte da: {transport}.",
  "health.empty": "Nessuna scansione registrata — si riempie man mano che le scansioni girano.",
  "health.colPortal": "Portale",
  "health.colDays": "Giorni (dal più vecchio a oggi)",
  "health.colScans": "Scansioni",
  "health.colFailureRate": "Tasso di fallimento",
  "health.colFailureRateTitle":
    "Quota di scansioni tornate bloccate o in errore nel periodo",
  "health.colTransport": "Ultimo trasporto",
  "health.legend":
    "Giorno verde = tutte le scansioni ok · ambra = alcune fallite · rosso = tutte fallite. Passa sopra un giorno per i conteggi esatti.",
  "health.dayAllOk": "tutte le scansioni ok",
  "health.dayNone": "nessuna scansione",
  "health.dayAllFailed": "tutte le scansioni fallite",
  "health.daySomeFailed": "alcune scansioni fallite",
  "health.dayLabel":
    "{date}: {state} — {attempts} scansioni, {blocked} bloccate, {errors} errori",
  "health.failingTitle": "Ricerche attualmente in errore",
  "health.failingRow": "({portal}) — {count} scansioni {status} consecutive",
  "health.failingStatusFallback": "fallite",
  "health.failingHint":
    "Una serie breve è normale (blocchi anti-bot transitori). Una lunga significa che la via gratuita è caduta: valuta un pool di proxy o una chiave scrape-API nelle Impostazioni.",

  // ── calcolatori (scheda dettaglio) ──────────────────────────────────────
  "calc.mortgageTitle": "🧮 Stima del mutuo",
  "calc.downPayment": "Anticipo",
  "calc.interestRate": "Tasso d'interesse",
  "calc.perYear": "%/anno",
  "calc.duration": "Durata",
  "calc.years": "anni",
  "calc.loanAmount": "Importo del mutuo",
  "calc.monthlyPayment": "Rata mensile",
  "calc.yieldTitle": "📈 Rendimento da affitto (investimento)",
  "calc.expectedRent": "Affitto previsto",
  "calc.perMonthUnit": "€/mese",
  "calc.costsVacancy": "Spese e sfitto",
  "calc.percentOfRent": "% dell'affitto",
  "calc.grossYield": "Rendimento lordo",
  "calc.netYield": "Rendimento netto",
  "calc.cashFlow": "Flusso di cassa vs mutuo",
  "calc.enterRent":
    "Inserisci l'affitto che pensi di chiedere per vedere il rendimento lordo/netto e il flusso di cassa mensile (affitto meno la rata del mutuo qui sopra).",

  // ── errori e accesso ────────────────────────────────────────────────────
  "error.title": "Qualcosa è andato storto nel mostrare la pagina.",
  "error.dataSafe": "I tuoi dati sono al sicuro nel backend — basta ricaricare.",
  "error.reload": "⟳ Ricarica",
  "auth.title": "🔒 Autenticazione richiesta",
  "auth.hint": "Questa dashboard è protetta da un token API. Inseriscilo per continuare.",
  "auth.placeholder": "Token API",
  "auth.rejected": "Il token non è stato accettato. Controllalo e riprova.",
  "auth.checking": "Verifica…",
  "auth.unlock": "Sblocca",

  // ── etichette dei piani (utils/format) ──────────────────────────────────
  "floor.ground": "piano terra",
  "floor.raised": "piano rialzato",
  "floor.basement": "seminterrato",
  "floor.numbered": "piano {floor}",
};
