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
  "common.open": "Apri",
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
  "common.any": "Qualsiasi",
  "common.contract": "Contratto",
  "common.unknownError": "Errore sconosciuto",
  "common.optional": "facoltativo",
  "common.of": "di",
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
  "card.matchBadge": "{score}% di corrispondenza",
  "card.matchBadgeTitle": "Compatibilità con le impostazioni della casa dei sogni",
  "card.dealScore": "Punteggio affare",
  "card.dealBelowMarket": "{pct}% sotto mercato",
  "card.dealAboveMarket": "{pct}% sopra mercato",
  "card.new": "nuovo",
  "card.newTitle": "Comparso dopo la tua ultima visita alla dashboard",
  "card.rent": "affitto",
  "card.mergedListings": "{count} annunci unificati",
  "card.email": "email",
  "card.emailTitle": "Importato dalla tua casella email (non da una ricerca monitorata)",
  "card.deselect": "Deseleziona",
  "card.selectForBatch": "Seleziona per la verifica in blocco",
  "card.removeFavorite": "Togli dai preferiti",
  "card.addFavorite": "Aggiungi ai preferiti",
  "card.hideTitle": "Nascondi questo immobile (non tornerà mai da solo)",
  "card.hideAria": "Nascondi questo immobile",
  "card.filteredReason": "Filtrato: {reason}",
  "card.noLongerAvailable": "Non più disponibile",
  "card.sold": "Venduto",
  "card.rentedOut": "Affittato",
  "card.untitled": "Senza titolo",
  "card.locationUnknown": "Posizione N/D",
  "card.notes": "note",
  "card.notOnMap": "non sulla mappa",
  "card.commuteTitle": "Tempo di viaggio verso {name}",

  // ── riferimenti di prezzo (i due valori affiancati, mai fusi) ────────────
  "benchmark.title": "Riferimenti di prezzo",
  "benchmark.askingLabel": "Quanto chiedono annunci simili",
  "benchmark.askingScope": "mediana in questa {scope}",
  "benchmark.omiSaleLabel": "A quanto il fisco registra le compravendite",
  "benchmark.omiRentLabel": "A quanto il fisco registra le locazioni",
  "benchmark.range": "{min}–{max} €/mq",
  "benchmark.rangeMonthly": "{min}–{max} €/mq al mese",
  "benchmark.omiSource": "Zona OMI {zone} · {semester}",
  "benchmark.note":
    "I prezzi richiesti stanno sistematicamente sopra quelli registrati: i due si leggono affiancati, mai mediati.",
  "benchmark.semesterFirst": "1° semestre {year}",
  "benchmark.semesterSecond": "2° semestre {year}",
  "benchmark.stale": "non aggiornato",
  "benchmark.staleNote":
    "Questa fascia ha più di 18 mesi: l'Agenzia pubblica due volte l'anno, quindi esiste una fornitura più recente.",
  // La dicitura richiesta dalla licenza OMI: resta in italiano in entrambi i
  // dizionari, perché è un credito da riprodurre, non una didascalia.
  "benchmark.attribution": "Fonte: Agenzia Entrate – OMI",

  // ── unità dei tempi di percorrenza (scheda e dettaglio) ──────────────────
  "commute.minutes": "{count} min",
  "commute.hours": "{count} h",
  "commute.hoursMinutes": "{hours} h {minutes} min",
  "commute.metres": "{count} m",
  "commute.kilometres": "{count} km",

  "card.notOnMapTitle":
    "Nessuna coordinata sulla mappa — questo annuncio non comparirà sulla mappa né dentro una zona disegnata finché non viene localizzato (aprilo e usa \"Mostra sulla mappa\", oppure lancia \"Trova le coordinate\").",

  // ── scheda dettaglio ────────────────────────────────────────────────────
  "detail.previous": "Risultato precedente (k, o la freccia sinistra)",
  "detail.next": "Risultato successivo (j, o la freccia destra)",
  "detail.position": "{position} di {total}",
  "detail.locateFailed":
    "Impossibile posizionare questo immobile — la località indicata dal portale è troppo vaga per ricavarne le coordinate.",
  "detail.locateError": "Non è stato possibile cercare le coordinate — riprova tra un momento.",
  "detail.checkGone": "Rimosso / Sparito (404)",
  "detail.checkOnline": "Online (appena verificato)",
  "detail.checkUnknown": "Impossibile verificare (bloccato dal portale o timeout)",
  "detail.checkError": "La verifica online non è andata a buon fine — riprova tra un momento.",
  "detail.notesError": "Non è stato possibile salvare le note — sono ancora nel riquadro, riprova.",
  "detail.dealScoreTitle": "Punteggio affare:",
  "detail.dealBelowLocal": "sotto il mercato locale",
  "detail.dealAboveLocal": "sopra il mercato locale",
  "detail.suggestedProposal": "Proposta suggerita:",
  "detail.dealDisclaimer":
    "Una stima ricavata dalla mediana €/mq della zona, dagli indizi sullo stato dell'immobile e dallo sconto abituale dell'agenzia — un punto di partenza per il tuo giudizio, non una perizia.",
  "detail.foundListings": "Annunci trovati ({count})",
  "detail.priceHistory": "Storico dei prezzi",
  "detail.commute": "Percorrenza",
  "detail.foundBySearch": "Trovato da una ricerca",
  "detail.foundBySearches": "Trovato da {count} ricerche",
  "detail.notLinked":
    "Non collegato a nessuna ricerca monitorata — importato dalla tua casella email.",
  "detail.tags": "Etichette",
  "detail.notes": "Note personali",
  "detail.notesPlaceholder":
    'es. "chiamata l\'agenzia lunedì — visita fissata per venerdì", "servono 15k di ristrutturazione"',
  "detail.saveNotes": "Salva le note",
  "detail.description": "Descrizione",
  "detail.checkOnlineButton": "Verifica se è ancora online",
  "detail.checkOnlineTitle":
    "Interroga subito l'URL del portale per verificare se questo annuncio è ancora online o è stato rimosso (404)",
  "detail.viewOnMap": "Mostra sulla mappa",
  "detail.viewOnMapTitle": "Apri questo immobile sulla mappa",
  "detail.locateAndViewTitle": "Trova le coordinate di questo immobile e aprilo sulla mappa",
  "detail.restore": "Ripristina l'immobile",
  "detail.restoreGone":
    'Ripristinare questo immobile? Usalo se la verifica di disponibilità lo ha segnato "non più disponibile" per sbaglio.',
  "detail.restoreSold":
    "Ripristinare questo immobile? Usalo se lo hai segnato come venduto per sbaglio — torna negli elenchi attivi.",
  "detail.restoreHidden": "Ripristinare questo immobile? Tornerà negli elenchi attivi.",
  "detail.restoreFailed": "Non è stato possibile ripristinare questo immobile. Riprova.",
  "detail.markSold": "Segna come venduto",
  "detail.markRented": "Segna come affittato",
  "detail.confirmSold":
    "Segnare questo immobile come venduto? Esce dagli elenchi attivi ma resta come vendita confermata per le statistiche di mercato.",
  "detail.confirmRented":
    "Segnare questo immobile come affittato? Esce dagli elenchi attivi ma resta come contratto confermato per le statistiche di mercato.",
  "detail.markSoldFailed": "Non è stato possibile segnare questo immobile come venduto. Riprova.",
  "detail.hide": "Nascondi l'immobile",
  "detail.hideFailed": "Non è stato possibile nascondere questo immobile. Riprova.",

  // ── scheda dettaglio: lettura opzionale dell'annuncio ───────────────────
  "audit.title": "Cosa dice l'annuncio",
  "audit.button": "Leggi l'annuncio",
  "audit.reading": "Lettura in corso…",
  "audit.again": "Rileggi",
  "audit.buttonTitle":
    "Legge il testo dell'annuncio con il tuo modello linguistico: spese oltre il prezzo, immobile locato, stato, punti da usare in trattativa",
  "audit.failed":
    "Non è stato possibile leggere l'annuncio — riprova, oppure controlla il modello nelle Impostazioni.",
  "audit.condition": "Stato",
  "audit.conditionNew": "nuova costruzione",
  "audit.conditionRenovated": "ristrutturato",
  "audit.conditionGood": "buono",
  "audit.conditionToRenovate": "da ristrutturare",
  "audit.conditionUnknown": "non indicato",
  "audit.tenant": "Immobile locato",
  "audit.tenantYes": "sì — venduto con inquilino in essere",
  "audit.tenantNo": "no",
  "audit.tenantUnknown": "non indicato",
  "audit.costs": "Oltre al prezzo",
  "audit.concerns": "Da verificare",
  "audit.negotiation": "Utile in trattativa",
  "audit.footer": "Letto da {model} il {date}",
  "audit.stale": "L'annuncio è cambiato dopo questa lettura — rileggilo per il testo attuale.",
  "audit.disclaimer":
    "È una rilettura delle parole dell'annuncio fatta da un modello linguistico, non una valutazione né un parere legale — verifica con l'agenzia ciò che conta.",

  // ── etichette ───────────────────────────────────────────────────────────
  "tags.removeTag": 'Rimuovi l\'etichetta "{name}"',
  "tags.addTag": "Aggiungi un'etichetta",
  "tags.addTagButton": "+ etichetta",
  "tags.namePlaceholder": "Nome dell'etichetta…",
  "tags.create": '+ crea "{name}"',

  // ── la struttura: intestazione, le quattro destinazioni, stato scansione ─
  "nav.title": "Ricerca Immobili",
  "nav.subtitle": "Immobiliare.it + Idealista, senza duplicati",
  "nav.primary": "Navigazione principale",
  "nav.skipToContent": "Vai al contenuto",
  "nav.listings": "Immobili",
  "nav.insights": "Analisi",
  "nav.searches": "Ricerche",
  "nav.scanning": "Scansione in corso…",
  "nav.paused": "Scansioni automatiche in pausa",
  "nav.pausedShort": "Scansioni in pausa",
  "nav.nextScan": "Prossima scansione automatica: {time}",
  "nav.nextScanShort": "Prossima {time}",
  "nav.scanNowShort": "Scansiona",
  "nav.scanNow": "Avvia scansione",
  "nav.scanNowAria": "Avvia subito la scansione",
  "nav.running": "In corso…",
  "nav.toLight": "Passa al tema chiaro",
  "nav.toDark": "Passa al tema scuro",
  "nav.viewLog": "Mostra il log del backend",
  "nav.viewActivity": "Cosa sta facendo la scansione",
  "nav.settings": "Impostazioni",
  "nav.language": "Lingua",
  "nav.languageSwitchTo": "Passa a {language}",

  // ── attività: la scansione in corso e quelle appena concluse ────────────
  "activity.liveTitle": "Scansione in corso",
  "activity.idleTitle": "Nessuna scansione in corso",
  "activity.idleBody":
    "Al momento non si sta scaricando nulla. Qui sotto c'è cosa hanno fatto le ultime scansioni.",
  "activity.loading": "Lettura di cosa sta facendo la scansione…",
  "activity.start": "Scansiona ora",
  "activity.lastFinished": "Ultima scansione conclusa alle {time}.",
  "activity.nextScan": "Prossima scansione automatica: {time}",
  "activity.paused": "Le scansioni automatiche sono in pausa.",
  "activity.searchOf": "Ricerca {index} di {total}",
  "activity.phaseStarting": "Avvio della scansione",
  "activity.phaseLocating": "Posizionamento dei nuovi annunci sulla mappa",
  "activity.phaseFetching": "Lettura dei risultati, pagina {page}",
  "activity.phaseWaiting": "Pausa di {seconds}s prima della pagina successiva",
  "activity.phaseSaving": "Salvataggio di quello che è arrivato",
  "activity.phaseScanning": "Scansione in corso",
  "activity.waitingWhy":
    "La pausa è voluta: chiedere le pagine una dopo l'altra è ciò che porta il portale a smettere di rispondere. È qui che passa la maggior parte del tempo di una scansione.",
  "activity.pagesLabel": "Pagine lette",
  "activity.pageOf": "Pagina {done} di {total}",
  "activity.pageCount": "Pagina {page}",
  "activity.pagesUnknown": "il portale non ha detto quante sono",
  "activity.found": "{count} annunci raccolti finora",
  "activity.foundOf": "{count} annunci raccolti su {total}",
  "activity.transport": "Trasporto:",
  "activity.streamDown":
    "La connessione in tempo reale non è disponibile, quindi l'aggiornamento avviene a intervalli. I dati restano corretti, solo un po' meno immediati.",

  "activity.journalTitle": "Le ultime scansioni",
  "activity.journalEmpty": "Non è ancora stata fatta nessuna scansione",
  "activity.journalEmptyHint":
    "Ogni ricerca che viene eseguita lascia una riga qui: cosa ha letto, cosa ha trovato e com'è finita. Resta anche dopo la fine della scansione.",
  "activity.outcomeOk": "Conclusa",
  "activity.outcomeNoResults": "Nessun risultato",
  "activity.outcomeBlocked": "Bloccata",
  "activity.outcomeError": "Non riuscita",
  "activity.outcomeUnknown": "Terminata",
  "activity.entryCounts": "{pages} pagine, {listings} annunci",
  "activity.modeFull": "scansione completa",
  "activity.modeQuick": "scansione rapida",
  "activity.stoppedBecause": "Si è fermata perché: {reason}.",

  "activity.diagnostics": "Diagnostica",
  "activity.diagnosticsBody":
    "Il log del backend è il resoconto riga per riga di quello che ha fatto il programma. È il posto giusto in cui guardare quando il riepilogo qui sopra non spiega qualcosa.",
  "activity.openLog": "Apri il log",

  // ── avvisi: cosa non ha funzionato e cosa fare ──────────────────────────
  "toast.region": "Messaggi",
  "toast.dismiss": "Chiudi questo messaggio",
  "toast.undo": "Annulla",
  "toast.adviceUnreachable":
    "Il backend non risponde. Controlla che sia in esecuzione — start.bat — e riprova.",
  "toast.adviceServer":
    "Il backend ha avuto un problema. Riprova; se continua, il dettaglio è nel log.",
  "toast.adviceRefused":
    "Il backend ha rifiutato la richiesta. Cambia quello che hai chiesto e riprova.",
  "toast.adviceRetry": "Riprova.",
  "toast.gridFailed":
    "Non è stato possibile aggiornare gli annunci — a schermo c'è l'ultima risposta arrivata.",
  "toast.hidden": "Immobile nascosto.",
  "toast.hiddenMany": "{count} immobili nascosti.",
  "toast.sold": "Segnato come non più sul mercato.",
  "toast.soldMany": "{count} segnati come non più sul mercato.",
  "toast.favoritedMany": "{count} aggiunti ai preferiti.",
  "toast.unfavoritedMany": "{count} rimossi dai preferiti.",
  "toast.hideFailed": "Non è stato possibile nascondere l'immobile.",
  "toast.bulkFailed": "Non è stato possibile aggiornare gli immobili selezionati.",
  "toast.undoFailed": "Non è stato possibile annullare l'operazione.",
  "toast.favoriteFailed": "Non è stato possibile aggiornare i preferiti.",
  "toast.tagFailed": "Non è stato possibile aggiornare le etichette.",
  "toast.scanFailed": "Non è stato possibile avviare la scansione.",
  "toast.selectAllFailed": "Non è stato possibile selezionare tutti i risultati.",
  "toast.exportFailed": "Non è stato possibile creare il dossier.",
  "toast.geocodeFailed": "Non è stato possibile cercare le coordinate.",
  "toast.settingsLoadFailed": "Non è stato possibile caricare le impostazioni.",
  "toast.settingsSaveFailed": "Non è stato possibile salvare le impostazioni.",
  "toast.searchSaveFailed": "Non è stato possibile salvare la ricerca.",
  "toast.searchUpdateFailed": "Non è stato possibile aggiornare le ricerche.",
  "toast.searchDeleteFailed": "Non è stato possibile eliminare le ricerche.",

  // ── struttura della dashboard ───────────────────────────────────────────
  "app.noMatches": "Nessun immobile raccolto corrisponde a questi filtri.",
  "app.noMatchesHint":
    "Nessuno dei {count} annunci raccolti finora rientra nei criteri. Allenta i filtri, oppure mandali sui portali, dove possono trovare annunci che questo computer non ha mai visto.",
  "app.toPortals": "Cerca sui portali con questi criteri",
  "app.welcome": "Non è ancora stato raccolto nulla.",
  "app.welcomeHint":
    "È una ricerca monitorata a riempire questa pagina: la guida ne imposta una in un paio di minuti.",
  "app.collectedNoneHint":
    "Le ricerche sono impostate: sarà la prossima scansione a riempire questa pagina.",
  "app.addSearch": "Aggiungi una ricerca",
  "app.showMoreCount": "Mostra altri ({count} rimanenti)",
  "app.loadingResults": "Caricamento dei risultati…",
  "app.resultsFailed": "Non è stato possibile caricare i risultati",

  // ── la guida al primo avvio ─────────────────────────────────────────────
  "onboarding.title": "Come iniziare",
  "onboarding.intro":
    "Tre passi brevi. Puoi uscire quando vuoi e riprendere più tardi.",
  "onboarding.stepWhat": "Che cos'è",
  "onboarding.stepSearch": "La tua prima ricerca",
  "onboarding.stepScan": "La prima scansione",
  "onboarding.next": "Avanti",
  "onboarding.back": "Indietro",
  "onboarding.skip": "Salta per ora",
  "onboarding.done": "Vai agli immobili",
  "onboarding.whatTitle": "Controlla i portali al posto tuo",
  "onboarding.whatBody":
    "Dici una volta sola che cosa cerchi. L'app legge Immobiliare.it e Idealista a intervalli regolari, conserva ogni annuncio che trova e ti dice che cosa è nuovo e che cosa è calato di prezzo.",
  "onboarding.whatKeeps":
    "Tutto resta su questo computer: il database è un file accanto all'app, e non esce nulla oltre alle richieste ai portali stessi.",
  "onboarding.searchTitle": "Crea la tua prima ricerca",
  "onboarding.searchBody":
    "Tre modi per fare la stessa cosa: prendi quello che ti viene più comodo. Potrai aggiungere altre ricerche dopo, e modificarle tutte.",
  "onboarding.wayAssistant": "Descrivila e basta",
  "onboarding.wayAssistantBody":
    "Scrivi in una frase che cosa cerchi e lascia che sia l'app a trasformarla in una ricerca.",
  "onboarding.wayBuilder": "Costruisci una ricerca",
  "onboarding.wayBuilderBody": "Compila città, prezzo e dimensioni in un modulo.",
  "onboarding.wayUrl": "Incolla un URL",
  "onboarding.wayUrlBody":
    "Cerca sul portale e poi incolla l'indirizzo dei risultati.",
  "onboarding.wayBack": "Scegli un altro modo",
  "onboarding.urlTip": "Suggerimento:",
  "onboarding.urlTipBody":
    "per usare tutti i filtri del portale (bagni, piano, ascensore, classe energetica, escludi aste…), impostali sul portale e incolla l'URL — l'app monitora esattamente quella ricerca.",
  "onboarding.searchSaved": "La tua ricerca è salvata.",
  "onboarding.scanTitle": "Avvia la prima scansione",
  "onboarding.scanBody":
    "La prima esecuzione raccoglie tutto quello che i portali hanno adesso per la tua ricerca. È la tua base di partenza, quindi non manda avvisi; da lì in poi saprai solo che cosa cambia.",
  "onboarding.scanStart": "Avvia la prima scansione",
  "onboarding.scanRunning": "Scansione in corso…",
  "onboarding.scanIdle": "Non è ancora in corso nulla.",
  "onboarding.scanPatience":
    "Gran parte di una scansione è pausa tra una pagina e l'altra, di proposito: è quella pausa che tiene i portali disposti a rispondere. Puoi lasciare questa pagina, la scansione continua.",
  "onboarding.scanFound": "{count} raccolti finora",
  "onboarding.scanSearchOf": "Ricerca {index} di {total}",
  "onboarding.setupBody":
    "Tutto il resto è spento finché non lo accendi: farti avvisare di un nuovo annuncio, una seconda fonte, non farti bloccare. Cinque domande brevi, tutte saltabili.",
  "onboarding.setupOpen": "Configura il resto",
  "onboarding.phaseStarting": "Avvio della scansione",
  "onboarding.phaseLocating": "Posizionamento dei nuovi annunci sulla mappa",
  "onboarding.phaseFetching": "Lettura dei risultati, pagina {page}",
  "onboarding.phaseWaiting": "Pausa prima della pagina successiva",
  "onboarding.phaseSaving": "Salvataggio di quello che è arrivato",

  // ── configurazione guidata ──────────────────────────────────────────────
  "setup.title": "Configura quello che ti serve",
  "setup.intro":
    "Cinque domande, raggruppate per quello che ognuna ti fa ottenere. Niente è obbligatorio: salta quello che non ti interessa e torna a riprenderlo dalle Impostazioni quando vuoi.",
  "setup.optional":
    "Quello che lasci vuoto resta com'è. In questa schermata non c'è niente di obbligatorio.",
  "setup.back": "Indietro",
  "setup.skip": "Salta per ora",
  "setup.saveNext": "Salva e continua",
  "setup.finish": "Salva e concludi",

  "setup.group.unblocked": "Non farti bloccare",
  "setup.group.source": "Una seconda fonte",
  "setup.group.told": "Farti avvisare",
  "setup.group.pace": "Quanto raccoglie",
  "setup.group.engines": "Gli extra facoltativi",

  "setup.body.unblocked":
    "I portali si difendono dalla lettura automatica, e Immobiliare è quello severo: senza aiuto risponde con una pagina di blocco invece che con i risultati. Basta una qualsiasi di queste: un cookie preso dal tuo browser, un servizio di scraping o dei proxy.",
  "setup.body.source":
    "Idealista pubblica una API ufficiale. Con una chiave viene letto da lì invece che dal sito: è la via autorizzata ed è immune al blocco di cui sopra. Le chiavi sono gratuite e arrivano in un paio di giorni.",
  "setup.body.told":
    "Altrimenti l'app raccoglie in silenzio e te ne accorgi solo aprendola. Telegram è il più rapido dei due: scrivi a @BotFather, incolla il token e manda un messaggio al tuo bot perché possa trovare la tua chat.",
  "setup.body.pace":
    "Hanno già valori sensati. Alzali per coprire di più a ogni scansione, abbassali se un portale comincia a rifiutare: la pausa tra una richiesta e l'altra è quella che conta di più.",
  "setup.body.engines":
    "Niente di tutto questo serve al funzionamento dell'app. Geocodifica e tempi di percorrenza mettono gli annunci sulla mappa e misurano il tragitto; un modello linguistico scrive i riassunti e trasforma una descrizione in filtri.",

  "setup.field.datadome_cookie": "Cookie DataDome",
  "setup.hint.datadome_cookie":
    "Dal tuo browser su immobiliare.it: strumenti per sviluppatori, Application, Cookie, il valore che si chiama «datadome». Scade dopo qualche ora.",
  "setup.field.datadome_auto_refresh": "Prendi il cookie automaticamente",
  "setup.hint.datadome_auto_refresh":
    "Apre un browser vero in background quando il cookie salvato è vecchio e ne prende uno nuovo.",
  "setup.field.browser_engine": "Browser da usare",
  "setup.hint.browser_engine":
    "Camoufox è più difficile da riconoscere per un portale; Chromium si avvia più in fretta.",
  "setup.field.proxy_urls": "Proxy",
  "setup.hint.proxy_urls":
    "Uno per riga, oppure separati da virgole. Le richieste vengono distribuite tra loro.",
  "setup.field.scrape_api_key": "Chiave del servizio di scraping",
  "setup.hint.scrape_api_key":
    "Un servizio a pagamento che scarica la pagina al posto tuo. Funziona con ScraperAPI, ScrapingBee e Zyte.",
  "setup.field.scrape_api_mode": "Quando usarlo",
  "setup.hint.scrape_api_mode":
    "Solo dopo che una richiesta diretta è stata rifiutata, oppure a ogni richiesta.",

  "setup.field.idealista_api_key": "Chiave API Idealista",
  "setup.hint.idealista_api_key": "L'«apikey» che trovi nella email di conferma.",
  "setup.field.idealista_api_secret": "Secret API Idealista",
  "setup.hint.idealista_api_secret": "Il «secret» della stessa email.",

  "setup.field.telegram_bot_token": "Token del bot Telegram",
  "setup.hint.telegram_bot_token": "Quello che ti risponde @BotFather quando crei un bot.",
  "setup.field.telegram_chat_id": "Id della chat Telegram",
  "setup.hint.telegram_chat_id":
    "Manda prima un messaggio qualsiasi al tuo bot, altrimenti non ha il permesso di scriverti.",
  "setup.field.telegram_enabled": "Mandami gli avvisi su Telegram",
  "setup.hint.telegram_enabled": "Nuovi annunci e cali di prezzo, appena vengono trovati.",
  "setup.field.smtp_host": "Server di posta",
  "setup.hint.smtp_host": "Per esempio smtp.gmail.com.",
  "setup.field.smtp_port": "Porta",
  "setup.hint.smtp_port": "587 per STARTTLS, 465 per SSL.",
  "setup.field.smtp_user": "Utente della posta",
  "setup.hint.smtp_user": "Di solito l'indirizzo completo.",
  "setup.field.smtp_password": "Password della posta",
  "setup.hint.smtp_password":
    "Con Gmail è una password per le app, non la password del tuo account.",
  "setup.field.email_from": "Manda da",
  "setup.hint.email_from": "L'indirizzo da cui sembrano arrivare gli avvisi.",
  "setup.field.email_to": "Manda a",
  "setup.hint.email_to": "Puoi mettere più indirizzi separati da virgole.",
  "setup.field.email_enabled": "Mandami gli avvisi via email",
  "setup.hint.email_enabled": "Gli stessi avvisi di Telegram, nella tua casella.",

  "setup.field.max_pages_per_search": "Pagine per ricerca",
  "setup.hint.max_pages_per_search":
    "Quanto in profondità legge ogni scansione. Circa 25 annunci a pagina.",
  "setup.field.request_delay_seconds": "Secondi tra una richiesta e l'altra",
  "setup.hint.request_delay_seconds":
    "È la pausa che tiene i portali disposti a rispondere. Sotto i due secondi prima o poi vieni rifiutato.",
  "setup.field.idealista_api_max_pages": "Pagine per ricerca sull'API Idealista",
  "setup.hint.idealista_api_max_pages":
    "Il piano gratuito consente cento richieste al mese, quindi conviene tenerlo basso.",

  "setup.field.nominatim_url": "Server di geocodifica",
  "setup.hint.nominatim_url":
    "Trasforma un indirizzo in un punto sulla mappa. Lascia vuoto per usare quello pubblico di OpenStreetMap.",
  "setup.field.osrm_url": "Server di routing",
  "setup.hint.osrm_url": "Misura il tragitto in auto, a piedi o in bici.",
  "setup.field.llm_base_url": "Endpoint del modello linguistico",
  "setup.hint.llm_base_url":
    "Qualsiasi cosa parli l'API di OpenAI, anche in locale.",
  "setup.field.llm_api_key": "Chiave del modello linguistico",
  "setup.hint.llm_api_key": "Non serve a un modello che gira su questa macchina.",
  "setup.field.llm_model": "Modello",
  "setup.hint.llm_model": "Per esempio gpt-4o-mini.",

  "setup.option.auto": "Quello che c'è",
  "setup.option.chromium": "Chromium",
  "setup.option.camoufox": "Camoufox",
  "setup.option.fallback": "Solo quando è bloccato",
  "setup.option.always": "A ogni richiesta",

  "setup.detected.harvester": "L'automazione del browser è installata",
  "setup.detected.noHarvester": "L'automazione del browser non è installata",
  "setup.detected.camoufox": "Camoufox è installato",
  "setup.detected.cookie": "C'è un cookie salvato, buono per circa {minutes} minuti",
  "setup.detected.noCookie": "Nessun cookie salvato",

  "setup.section.title": "Configurazione guidata",
  "setup.section.pending": "Questi sono ancora spenti:",
  "setup.section.allOn": "Tutto quello che la configurazione guidata propone è acceso.",
  "setup.section.open": "Configura il resto",
  "setup.section.reopen": "Rifai la configurazione guidata",

  // ── barra di selezione multipla ─────────────────────────────────────────
  "app.selectMultiple": "Seleziona più immobili",
  "app.closeMultiSelect": "Chiudi selezione multipla",
  "app.selectAll": "Seleziona tutti ({selected} di {total})",
  "app.hideSelected": "Nascondi selezionati ({count})",
  "app.hideSelectedTitle":
    "Gli immobili nascosti lasciano la dashboard definitivamente e non tornano da soli, nemmeno se una scansione li ritrova. Usa Ripristina per riportarne indietro uno.",
  "app.markSold": "Segna come venduto ({count})",
  "app.addFavorites": "Aggiungi ai preferiti",
  "app.removeFavorites": "Togli dai preferiti",
  "app.checkAvailability": "Verifica disponibilità online ({count})",
  "app.checking": "Verifica in corso…",
  "app.stopping": "Interruzione…",
  "app.stop": "Ferma",
  "app.confirmHideOne":
    "Nascondere questo immobile? Non comparirà mai più negli elenchi né nelle notifiche.",
  "app.confirmHideMany":
    "Nascondere {count} immobili? Spariranno dagli elenchi e dalle notifiche (recuperabili da Scartati → Ripristina).",
  "app.confirmSoldMany":
    "Segnare {count} immobili come venduti/affittati? Escono dagli elenchi attivi ma restano come vendite confermate per le statistiche di mercato (recuperabili da Venduti → Ripristina).",
  "app.batchCheckFailed": "Non è stato possibile verificare gli immobili selezionati. Riprova.",

  // ── avanzamento e riepilogo della verifica ──────────────────────────────
  "app.checkProgressLabel": "Verifica disponibilità",
  "app.checkProgress":
    "Verifica annuncio {done} di {total} — {online} online, {gone} rimossi/venduti",
  "app.checkProgressUnknown": ", {count} non verificabili",
  "app.checkStarting": "Avvio della verifica…",
  "app.checkPacingNote":
    "Tra una richiesta e l'altra c'è una pausa di sicurezza per proteggere l'IP dai blocchi DataDome.",
  "app.checkTransport": "Trasporto: {transport}",
  "app.checkLastIssue": "Ultimo problema segnalato dal portale: {error}",
  "app.summaryChecked": "Verificati:",
  "app.summaryGone": "{count} rimossi o venduti (spostati in Spariti)",
  "app.summaryOnline": "{count} ancora online",
  "app.summaryUnknown": " ({count} non verificabili dal portale)",
  "app.summaryCancelled":
    "Interrotta — il resto della selezione non è stato verificato. Riselezionalo per riprendere.",
  "app.summaryAborted":
    "Il portale ha bloccato le richieste: verifica interrotta per proteggere l'IP. Riprova più tardi.",
  "app.summaryAbortedService":
    "Eseguita tramite {transport}. L'opzione della finestra del browser è attiva, ma un servizio Windows in background non ha un desktop su cui mostrarla. Per risolvere un CAPTCHA a mano, ferma il servizio e avvia l'app normalmente (start.bat / serve.bat) per questa verifica.",
  "app.summaryAbortedNoWindow":
    'Eseguita tramite {transport}. Per risolvere un CAPTCHA a mano, attiva sia "Esegui la verifica tramite browser" sia "Mostra la finestra del browser" nelle Impostazioni (serve il motore browser installato).',
  "app.summaryCapped":
    "Raggiunto il limite di richieste per esecuzione: rilancia la verifica per continuare con i restanti.",

  // ── pannello dei filtri ─────────────────────────────────────────────────
  "filters.title": "Filtri",
  "filters.show": "Mostra i filtri",
  "filters.hide": "Nascondi i filtri",
  "filters.railHint": "Tutto ciò che restringe la griglia",
  "filters.collected": "{count} annunci raccolti",
  "filters.active": "Filtri attivi",
  "filters.chipValue": "{label}: {value}",
  "filters.chipRemove": "Togli il filtro {label}",
  "filters.chipMerged": "Solo unificati",
  "filters.chipMapArea": "Area sulla mappa",
  // Mai "Cerca": questo campo guarda dentro ciò che è già qui, e un campo con
  // il verbo sopra è proprio ciò che fa leggere un filtro come una ricerca sui
  // portali mai partita.
  "filters.keyword": "Parola chiave",
  "filters.keywordPlaceholder": "Restringi per zona, indirizzo, titolo, piano o testo dell'annuncio…",
  "filters.clearKeyword": "Cancella la parola chiave",
  "filters.market": "Mercato",
  "filters.buy": "Compra",
  "filters.rent": "Affitta",
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
  "filters.sortMatch": "Corrispondenza migliore",
  "filters.status": "Stato",
  "filters.statusForSale": "In vendita",
  "filters.statusForRent": "In affitto",
  "filters.statusFiltered": "Filtrati",
  "filters.statusGone": "Spariti",
  "filters.statusSold": "Venduti",
  "filters.statusRentedOut": "Affittati",
  "filters.statusHidden": "Scartati",
  "filters.statusAll": "Tutti",
  "filters.origin": "Provenienza",
  "filters.originAll": "Tutte le provenienze",
  "filters.originScan": "Ricerca monitorata",
  "filters.originEmail": "Import da email",
  "filters.tag": "Etichetta",
  "filters.allTags": "Tutte le etichette",
  "filters.limitToSearch": "Limita a una ricerca",
  "filters.limitToSearchTitle":
    "Mostra solo gli immobili trovati da questa ricerca salvata (la sua provenienza 'Trovato da'). Gli import da email, che nessuna ricerca ha trovato, escono. Questo restringe l'elenco — non lo riordina.",
  "filters.allSearches": "Tutte le ricerche",
  "filters.priceDrops": "Cali di prezzo",
  "filters.favorites": "Preferiti",
  "filters.more": "Altri filtri",
  "filters.moreTitle": "Altri filtri",
  "filters.moreHint": "· restringi per portale, agenzia, qualità dell'affare o €/mq",
  "filters.portal": "Portale",
  "filters.anyPortal": "Qualsiasi portale",
  "filters.agency": "Agenzia",
  "filters.agencyPlaceholder": "es. Tecnocasa",
  "filters.deal": "Affare",
  "filters.anyDeal": "Qualsiasi affare",
  "filters.dealUndervalued": "Solo sottovalutati",
  "filters.dealFairPlus": "Equo o migliore",
  "filters.minSqmPrice": "€/mq min",
  "filters.maxSqmPrice": "€/mq max",
  "filters.mergedOnly": "Solo unificati (stessa casa su più portali/agenzie)",
  "filters.countProperties": "{count} immobili",
  "filters.reset": "↺ Azzera i filtri",
  "filters.resetTitle": "Cancella tutti i filtri e torna alla vista predefinita",
  "filters.view": "Vista",
  "filters.viewGrid": "▦ Griglia",
  "filters.viewMap": "Mappa",
  "filters.export": "Esporta",
  "filters.exportTitle": "Scarica i {count} immobili filtrati in {format}",
  "filters.exportPdfTitle":
    "Apri un report stampabile dei {count} immobili filtrati — salvalo in PDF dalla finestra di stampa",
  "filters.exportFavorites": "Preferiti",
  "filters.exportRentals": "Affitti",
  "filters.exportProperties": "Immobili",
  "filters.exportIn": "{what} a {city}",

  // ── azioni di manutenzione ──────────────────────────────────────────────
  "maintenance.title": "Manutenzione",
  "maintenance.hint":
    "Manutenzione dell'intero archivio, non di una singola ricerca. Nessuna delle due cambia ciò che una scansione cerca.",
  "maintenance.findCoords": "Trova le coordinate",
  "maintenance.locating": "Localizzazione…",
  "maintenance.findCoordsTitle":
    "Trova le coordinate sulla mappa per gli annunci che hanno un indirizzo o una zona ma nessun segnaposto (usa OpenStreetMap; può richiedere tempo)",
  "maintenance.retryFailed": "Riprova le ricerche fallite",
  "maintenance.clearing": "Pulizia…",
  "maintenance.retryFailedTitle":
    "Dimentica le geocodifiche fallite così \"Trova le coordinate\" riprova gli indirizzi che un disservizio temporaneo di OpenStreetMap ha congelato come \"non trovati\". Non sposta mai i segnaposti esistenti.",
  "maintenance.backendTooOld":
    "Il backend non ha ancora questa funzione — riavvialo (chiudi e rilancia start.bat / serve.bat) e riprova.",

  // ── esiti della manutenzione ────────────────────────────────────────────
  "maintenance.geocodeRunning": "Ricerca delle coordinate in background…",
  "maintenance.geocodeProgressLabel": "Ricerca delle coordinate",
  "maintenance.geocodeProgress":
    "Localizzazione annuncio {done} di {total} — {geocoded} localizzati, {cached} dalla cache",
  "maintenance.geocodeProgressNotFound": ", {count} non trovati",
  "maintenance.geocodeStarting": "Avvio della ricerca delle coordinate…",
  "maintenance.geocodePacing":
    "(Ritmo di 1 richiesta al secondo, per rispettare le regole d'uso di OpenStreetMap Nominatim)",
  "maintenance.geocodeLastIssue": "Ultimo problema segnalato da Nominatim: {error}",
  "maintenance.geocodeDone": "Ricerca delle coordinate terminata",
  "maintenance.geocodeNothing":
    "Niente da localizzare: ogni immobile ha già un segnaposto oppure non ha indirizzo/zona da cui ricavarlo. (La sola città viene saltata di proposito — porterebbe tutti quegli annunci sullo stesso punto in centro.)",
  "maintenance.geocodeLocated": "Localizzati {geocoded} di {scanned} annunci senza segnaposto",
  "maintenance.geocodeNotFound": " · {count} non risolti",
  "maintenance.geocodeCancelled":
    'Interrotta — gli immobili rimanenti sono rimasti senza segnaposto. Premi di nuovo "Trova le coordinate" per riprendere.',
  "maintenance.geocodeRemaining": "Ne restano {count} — rilanciala per continuare.",
  "maintenance.cacheClearedNone":
    "Nessuna ricerca bloccata da cancellare — ogni indirizzo fallito era già stato dimenticato o non era mai stato messo in cache.",
  "maintenance.cacheCleared":
    "Cancellate {count} ricerche fallite. Premi Trova le coordinate per riprovarle.",
  "maintenance.cacheClearedOne":
    "Cancellata {count} ricerca fallita. Premi Trova le coordinate per riprovarla.",

  // ── impostazioni: struttura e segreti ───────────────────────────────────
  "settings.title": "Impostazioni",
  "settings.testNote":
    "Ogni pulsante di test salva prima le tue modifiche, così ciò che verifica è esattamente ciò che hai scritto.",
  "settings.secretDirty": "Modifica non salvata — sostituirà il valore memorizzato",
  "settings.secretSaved": "Salvato",
  "settings.secretSavedOn": "Salvato · {date}",
  "settings.secretSavedTitle": "Un valore è attualmente memorizzato",
  "settings.secretLastSaved": "Ultimo salvataggio: {date}",
  "settings.secretNotSet": "○ Non impostato",
  "settings.saved": "Impostazioni salvate.",
  "settings.loadFailed": "Impossibile caricare le impostazioni: {error}",
  "settings.save": "Salva le impostazioni",
  "settings.errCredentials":
    "{error} — le credenziali sono state rifiutate. Con Gmail devi usare una password per app di 16 caratteri, non la tua password normale.",
  "settings.errNetwork":
    "{error} — impossibile raggiungere il server. Controlla nome host e porta.",

  // ── impostazioni: telegram ──────────────────────────────────────────────
  "settings.telegramTitle": "Notifiche Telegram",
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
  "settings.telegramActions": "Pulsanti di azione sulle notifiche",
  "settings.telegramActionsHelp":
    "Aggiunge i pulsanti Preferito, Visto, Nascondi e Mappa sotto ogni notifica di immobile, così puoi smistare un annuncio dal telefono. Preferito e Nascondi modificano la dashboard e si annullano premendoli di nuovo; Visto archivia solo il messaggio.",
  "settings.sending": "Invio…",
  "settings.saveAndTest": "Salva e invia test",
  "settings.telegramTestSent": "Messaggio di test inviato — controlla la chat Telegram.",

  // ── impostazioni: email ─────────────────────────────────────────────────
  "settings.emailTitle": "Notifiche email",
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


  // ── impostazioni: scansioni ─────────────────────────────────────────────
  "settings.scanTitle": "Scansione automatica",
  "settings.frequency": "Frequenza",
  "settings.every30m": "Ogni 30 minuti",
  "settings.everyHour": "Ogni ora",
  "settings.every2h": "Ogni 2 ore",
  "settings.every4h": "Ogni 4 ore",
  "settings.every8h": "Ogni 8 ore",
  "settings.pauseScans": "Metti in pausa le scansioni automatiche",
  "settings.pauseScansNote":
    'Impedisce alle scansioni programmate di contattare i portali — utile per far riposare la connessione quando sei via. "Scansiona ora" continua a funzionare su richiesta.',
  "settings.healthTitle": "Avvisi sulla salute degli scraper",
  "settings.healthNote":
    "Uno scraper rotto è silenzioso: nessun annuncio somiglia in tutto e per tutto a un mercato fermo. Ricevi un avviso quando una ricerca fallisce questo numero di scansioni di fila. I portali bloccano gli scraper ogni tanto, quindi il valore 1 grida al lupo.",
  "settings.alertAfter": "Avvisa dopo",
  "settings.neverDisabled": "Mai (disattivato)",
  "settings.nFailures": "{count} fallimenti consecutivi",

  // ── impostazioni: parole chiave e punteggio ─────────────────────────────
  "settings.keywordsTitle": "Parole chiave escluse (globali)",
  "settings.keywordsNote":
    "Gli annunci che contengono queste parole vengono scartati automaticamente (solo parole intere, accenti ignorati). Separale con virgole. Ogni ricerca può aggiungere le proprie parole extra oltre a queste.",
  "settings.matchTitle": "Smart Match Score (casa dei sogni)",
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

  // ── impostazioni: tempi di percorrenza ──────────────────────────────────
  "settings.commuteTitle": "Tempi di percorrenza",
  "settings.commuteEnable": "Mostra il tempo di viaggio da ogni immobile ai luoghi qui sotto",
  "settings.commuteNote":
    "Il lavoro, l'università, la fermata della metro — calcolati con OpenStreetMap. I tempi compaiono su una scheda solo dopo aver premuto Calcola qui sotto, e solo per gli annunci che hanno già le coordinate sulla mappa.",
  "settings.commutePointName": "Etichetta",
  "settings.commutePointNamePlaceholder": "Lavoro",
  "settings.commutePointAddress": "Indirizzo",
  "settings.commutePointAddressPlaceholder": "Via Dante 5, Milano",
  "settings.commutePointMode": "Con",
  "settings.commuteMode.car": "Auto",
  "settings.commuteMode.foot": "A piedi",
  "settings.commuteMode.bike": "Bici",
  "settings.commuteAddPoint": "Aggiungi un luogo",
  "settings.commuteRemovePoint": "Rimuovi questo luogo",
  "settings.commuteOsrmUrl": "Server di routing (OSRM)",
  "settings.commuteOsrmNote":
    "Lascia vuoto per il server dimostrativo pubblico. È costruito solo sulla rete stradale, quindi lì «a piedi» e «bici» vengono calcolati come in auto — indica il tuo OSRM per avere tempi reali a piedi e in bici.",
  "settings.commuteCompute": "Calcola ora i tempi di percorrenza",
  "settings.commuteComputing": "Calcolo in corso…",
  "settings.commuteComputeNote":
    "Una richiesta per immobile verso {url}, al ritmo di una al secondo e con cache, così una seconda esecuzione copre solo le novità.",
  "settings.commuteComputed": "Calcolate {routed} tratte su {scanned} immobili",
  "settings.commuteRemaining": " · ne restano {count}, rilancia per continuare",

  // ── impostazioni: motore dell'assistente ────────────────────────────────
  "settings.assistantTitle": "Motore dell'assistente di ricerca",
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
  "settings.auditTitle": "Lettura degli annunci (opzionale)",
  "settings.auditEnable": "Fai leggere un annuncio al modello quando lo chiedo",
  "settings.auditNote":
    "Aggiunge il pulsante “Leggi l'annuncio” nella scheda di un immobile: il modello riporta ciò che il testo dice su spese oltre il prezzo, immobile locato, stato e punti utili in trattativa. Nulla viene letto in automatico — un clic, un annuncio, con lo stesso modello configurato qui sopra. Le risposte restano salvate, quindi riaprire la scheda non costa nulla.",

  // ── impostazioni: scraping e aggiramento blocchi ────────────────────────
  "settings.scrapingTitle": "Superare i blocchi",
  "settings.scrapingHelp": "Come risolvere i blocchi DataDome? (istruzioni)",
  "settings.ddStep1":
    "Il guardiano di Immobiliare, DataDome, respinge le richieste semplici che arrivano da una connessione di casa.",
  "settings.ddStep2":
    "Opzione A: metti qui sotto l'indirizzo di un proxy (socks5://127.0.0.1:9050 per Tor, oppure un qualsiasi proxy HTTP/HTTPS) e le richieste usciranno da lì.",
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
  "settings.idealistaApiTitle": "API ufficiale di Idealista",
  "settings.idealistaApiNote":
    "Facoltativa, ed è l'unica opzione qui che non sia un aggiramento: con una chiave e un segreto, le ricerche su Idealista chiedono al portale i suoi stessi dati invece di leggerne le pagine, quindi nulla può bloccarle. Le chiavi vengono rilasciate a mano dopo aver descritto il proprio progetto su",
  "settings.idealistaKeySaved": "Chiave già salvata (lascia vuoto per mantenerla)",
  "settings.idealistaKeyPlaceholder": "Chiave API",
  "settings.idealistaSecretSaved": "Segreto già salvato (lascia vuoto per mantenerlo)",
  "settings.idealistaSecretPlaceholder": "Segreto API",
  "settings.idealistaMaxPages": "Richieste per ricerca, a ogni scansione",
  "settings.idealistaMaxPagesNote":
    "Ognuna restituisce fino a 50 annunci e consuma la quota mensile concordata per la tua chiave — perciò il valore predefinito è una sola richiesta. Alzalo quando conosci il tuo limite. Le ricerche che l'API non sa esprimere con esattezza (un quartiere, un numero di locali, un filtro sulle caratteristiche) continuano a usare il normale scraper, e così anche tutto ciò che l'API rifiuta.",
  "settings.scrapeApiTitle": "API di scraping (risolve DataDome per te)",
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
  "settings.harvestTitle": "Ottieni il cookie automaticamente",
  "settings.harvestNote":
    "Apre un browser locale, ottiene un cookie fresco e lo salva — senza copia/incolla. Potrebbe aprirsi una finestra: se il portale mostra un CAPTCHA, risolvilo una volta e verrà ricordato.",
  "settings.grabCookie": "Ottieni subito un cookie fresco",
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
  "settings.camoufoxInstalled": "Installato",
  "settings.camoufoxMissing":
    "Non installato — un clic lo aggiunge (~150 MB, una tantum):",
  "settings.installCamoufox": "Installa Camoufox",
  "settings.installingCamoufox": "Installazione di Camoufox (~1-3 min)…",
  "settings.camoufoxInstalledMsg": "Camoufox è installato.",
  "settings.harvesterMissing":
    "Non ancora installato — un clic aggiunge Playwright e Chromium (qualche centinaio di MB, una tantum):",
  "settings.installHarvester": "Installa Playwright e Chromium",
  "settings.installingHarvester": "Installazione di Playwright e Chromium (~1-2 min)…",
  "settings.harvesterInstalledMsg": "Playwright e Chromium sono installati.",
  "settings.manualInstall":
    "Oppure fallo a mano: esegui `install-playwright.bat` nella cartella dell'app, oppure: ",

  // ── impostazioni: token API e riavvio ───────────────────────────────────
  "settings.apiTokenTitle": "Token di accesso all'API",
  "settings.apiTokenNote":
    "Per impostazione predefinita la dashboard è raggiungibile da chiunque arrivi al suo indirizzo (per questo si lega a localhost). Imposta un token per richiederlo a ogni richiesta — così è sicuro esporre l'app sulla tua LAN o su Tailscale. Lascia vuoto per tenerla aperta. Su questo dispositivo resti autenticato; agli altri il token viene chiesto una volta.",
  "settings.apiTokenPlaceholder": "Nessun token (accesso libero)",
  "settings.backendTitle": "Backend",
  "settings.backendNote":
    "Riavvia il processo del backend — usalo dopo aver aggiornato l'app perché le novità abbiano effetto, invece di chiudere e riaprire la finestra del terminale. La dashboard va offline per qualche secondo e poi si ricarica da sola.",
  "settings.restart": "Riavvia il backend",
  "settings.restarting": "Riavvio… (in attesa del backend)",
  "settings.restartConfirm":
    "Riavviare ora il backend? La dashboard resta non disponibile per qualche secondo, poi si ricarica da sola.",
  "settings.restartTooOld":
    "Questo backend in esecuzione è troppo vecchio per riavviarsi da solo — chiudi la sua finestra del terminale e rilancia start.bat / serve.bat una volta. Dopodiché questo pulsante (e le funzioni più recenti) funzionerà.",
  "settings.restartNoReturn":
    "Il backend non è tornato da solo — controlla la finestra del terminale (o rilancia start.bat / serve.bat).",

  // ── impostazioni: copie di sicurezza ────────────────────────────────────
  "settings.backupsTitle": "Copie di sicurezza",
  "settings.backupsNote":
    "Una copia del database viene salvata una volta al giorno, e un'altra prima che un aggiornamento ne cambi la struttura. Scaricane una per conservarla altrove, oppure rimettine una: il ripristino sostituisce tutto quello che hai adesso, per questo lo stato attuale viene copiato prima.",
  "settings.backupsFolder": "Si trovano in {folder}",
  "settings.backupsEmpty":
    "Ancora nessuna copia — la prima viene salvata al prossimo avvio dell'app.",
  "settings.backupTakeNow": "Salva una copia adesso",
  "settings.backupImport": "Portane una qui",
  "settings.backupDownload": "Scarica",
  "settings.backupRestore": "Ripristina questa",
  "settings.backupKind.daily": "Copia giornaliera",
  "settings.backupKind.pre-upgrade": "Salvata prima di un aggiornamento",
  "settings.backupKind.imported": "Portata da un'altra installazione",
  "settings.backupSchema": "schema {revision}",
  "settings.backupSchemaUnknown": "schema illeggibile",
  "settings.backupTaken": "Copia salvata: {name}",
  "settings.backupImported":
    "Aggiunta come {name}. Non è ancora in uso: premi «Ripristina questa» per passare a lei.",
  "settings.restoreConfirmWord": "RIPRISTINA",
  "settings.restoreConfirm":
    "Ripristinare la copia del {date}? Tutto quello che c'è ora nel database viene sostituito (lo stato attuale viene copiato prima). Scrivi {word} per confermare.",
  "settings.restoreDone": "Ripristinata {name}. Ricaricamento…",
  "settings.restoreDoneBackup":
    "Ripristinata {name} · quello che ha sostituito è stato salvato come {backup}. Ricaricamento…",

  // ── impostazioni: gestione dei dati ─────────────────────────────────────
  "settings.dataTitle": "Gestione dei dati",
  "settings.dataNote":
    "Irreversibile. Le impostazioni di notifica e di accesso vengono sempre mantenute.",
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

  // ── ricerche monitorate: arrivando qui dai filtri della griglia ─────────
  "handoff.title": "Partita dai filtri che avevi sugli Immobili",
  "handoff.lead":
    "Una ricerca esce verso i portali, quindi non può chiedere tutto ciò che chiede un filtro. Ecco cosa è passato e cosa no.",
  "handoff.carried": "Passati",
  "handoff.approximated": "Passati, ma allargati",
  "handoff.dropped": "Non passati",
  "handoff.item": "{label} — {note}",
  "handoff.noteRooms": "i portali accettano un numero minimo di locali, non uno esatto",
  "handoff.noteMaxSqm": "una ricerca sui portali accetta solo una superficie minima",
  "handoff.noteText":
    "il testo libero legge gli annunci già raccolti; una ricerca sui portali si fa per luogo, prezzo e superficie",
  "handoff.notePortal": "nessuno dei due portali può cercarlo",
  "handoff.noteLocal":
    "descrive annunci già su questo computer, di cui i portali non sanno nulla",
  "handoff.noteArea":
    "un'area disegnata sulla mappa non ha un equivalente sui portali: indica invece città e zona",

  // ── ricerche monitorate: struttura e modalità ───────────────────────────
  "profiles.title": "Ricerche monitorate",

  // Lo stato di una ricerca, una parola sola. "In pausa" vince su tutto: una
  // ricerca spenta non sta funzionando e non sta fallendo, non sta girando.
  "profiles.healthWorking": "Funziona",
  "profiles.healthQuiet": "Nessun risultato",
  "profiles.healthBlocked": "Bloccata dal portale",
  "profiles.healthFailing": "Non funziona",
  "profiles.healthPaused": "In pausa",
  "profiles.healthUnrun": "Mai eseguita",
  "profiles.modeAssistant": "Descrivila e basta",
  "profiles.modeBuilder": "Costruisci una ricerca",
  "profiles.modeUrl": "Incolla un URL",
  "profiles.emptyTitle": "Nessuna ricerca configurata",
  "profiles.empty":
    "Costruiscine una con i tuoi criteri oppure incolla l'URL dei risultati da Immobiliare.it / Idealista per iniziare.",
  "profiles.loadFailed": "Non è stato possibile caricare le ricerche",
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
  "profiles.chAll": "Tutti i canali",
  "profiles.chTelegram": "Solo Telegram",
  "profiles.chTelegramOff": "Solo Telegram (non configurato)",
  "profiles.chEmail": "Solo Email",
  "profiles.chEmailOff": "Solo Email (non configurata)",
  "profiles.chNone": "Nessuna notifica",

  // Un solo avviso per l'account, in cima alla pagina: dice che cosa manca e
  // porta dove si sistema. Il rimedio è un link, non una frase.
  "profiles.channelsNone":
    "Nessun canale di notifica è configurato: le ricerche che ne chiedono uno continuano a raccogliere annunci, ma non ti avvisano.",
  "profiles.channelsTelegram":
    "Telegram non è configurato: le ricerche che notificano via Telegram continuano a raccogliere annunci, ma non ti avvisano.",
  "profiles.channelsEmail":
    "L'email non è configurata: le ricerche che notificano via email continuano a raccogliere annunci, ma non ti avvisano.",
  "profiles.channelsFix": "Configura le notifiche",

  // ── ricerche monitorate: assistente ─────────────────────────────────────
  "profiles.assistantIntro":
    'Descrivi ciò che cerchi in italiano o in inglese — anche più alternative insieme ("bilocale in zona X o trilocale in zona Y"). Il testo viene interpretato sul tuo PC — nulla viene inviato a servizi di IA — e rivedi ogni ricerca prima che venga salvata.',
  "profiles.assistantPlaceholder":
    "es. trilocale in affitto a Milano sotto i 1.200 € al mese",
  "profiles.assistantReading": "Lettura…",
  "profiles.assistantSubmit": "Interpretala →",
  "profiles.assistantTry": "Prova:",
  "profiles.assistantNothing":
    "Non c'era nulla da leggere. Descrivi che cosa cerchi — almeno una città.",
  "profiles.multiIntro":
    "Ho letto {count} ricerche alternative nella tua frase. Controllale una per una (apri i link per verificare i risultati), poi crea tutti i profili in un colpo solo.",
  "profiles.reword": "Riformula",
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
    'È così che usi tutti i filtri del portale — bagni, piano, ascensore, terrazzo, classe energetica, tipologia, escludi aste e così via. Impostali sul portale, poi incolla l\'URL: l\'app monitora esattamente quella ricerca. I due strumenti qui sopra ("Descrivila e basta" / "Costruisci una ricerca") coprono solo città, prezzo, locali e superficie.',
  "profiles.namePlaceholder": "Nome (es. Trilocali Milano Sud)",
  "profiles.keywordsPlaceholder":
    "Parole chiave escluse aggiuntive (facoltative, separate da virgola)",
  "profiles.urlPlaceholder":
    "https://www.immobiliare.it/vendita-case/milano/?prezzoMassimo=300000…",
  "profiles.extractParams": "Estrai i parametri",
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
    "Ti servono bagni, terrazzo, classe energetica, tipologia o un altro filtro? Impostalo sul portale e ",
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
  "profiles.activate": "Attiva",
  "profiles.pause": "Metti in pausa",
  "profiles.notificationsAction": "Notifiche →",
  "profiles.deleteAction": "Elimina",
  "profiles.mergeSelected": "Accorpa i selezionati",
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
  "profiles.excludes": "Esclude: {words}",
  "profiles.globalKeywords":
    "Sempre escluse per ogni ricerca (dalle Impostazioni): {words}",
  "profiles.notifyTitle": "Dove inviare le notifiche di questa ricerca",
  "profiles.notifyFor": "Notifiche di {name}",
  "profiles.active": "Attiva",
  "profiles.editBox": "Modifica questo box di ricerca",
  "profiles.separateBox": "Separa i portali in box singoli indipendenti",
  "profiles.deleteBox": "Elimina questo box di ricerca (tutti i portali associati)",
  "profiles.chipRent": "Affitto",
  "profiles.chipBuy": "Acquisto",
  "profiles.chipRooms": "{range} locali",
  "profiles.chipMinSqm": "≥ {value} mq",

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

  // ── mappa ───────────────────────────────────────────────────────────────
  "map.pinDrop": "Calo di prezzo",
  "map.pinFavorite": "Preferito",
  "map.pinFiltered": "Filtrato",
  "map.pinGone": "Non più disponibile",
  "map.pinSold": "Venduto / affittato",
  "map.pinActive": "Annuncio attivo",
  "map.pinApproximate": "{count} in posizione approssimata",
  "map.pinApproximateTitle":
    "L’annuncio non portava le coordinate e non è stato possibile risolverne l’indirizzo: il segnaposto è al centro della zona di appartenenza, non all’indirizzo.",
  "map.approximateZone": "Approssimato: centro della zona, non l’indirizzo",
  "map.onMap": "{shown} di {total} immobili sulla mappa",
  "map.missing": "{count} senza coordinate",
  "map.missingTitle":
    "I portali non pubblicano le coordinate per ogni annuncio; quegli immobili restano comunque nella vista a griglia.",
  "map.cluster": "{count} immobili qui — clicca per avvicinarti",
  "map.clustered": "Segnaposto sovrapposti raggruppati",
  "map.clusteredTitle":
    "I segnaposto sono più di quanti la mappa riesca a tenere distinti: quelli uno sopra l'altro sono disegnati come un unico cerchio numerato. Clicca un cerchio, o avvicinati, per separarli.",
  "map.drawHint": "Disegna un raggio o un'area per filtrare in base a dove si trovano.",
  "map.guideRadiusTitle": "Come si disegna un raggio",
  "map.guideRadiusStep1": "Clicca sulla mappa dove va il centro.",
  "map.guideRadiusStep2":
    "Trascina il quadratino azzurro fino alla distanza che vuoi: il filtro si applica quando lo rilasci.",
  "map.guideAreaTitle": "Come si disegna un'area",
  "map.guideAreaStep1": "Clicca ogni vertice dell'area, in ordine lungo il suo perimetro.",
  "map.guideAreaStep2":
    "Dal terzo vertice in poi, fai doppio clic sulla mappa — o premi «Chiudi l'area» — per chiuderla e filtrare.",
  "map.drawRadius": "◯ Disegna un raggio",
  "map.drawingRadius": "◯ Clicca il centro, trascina la maniglia…",
  "map.drawRadiusTitle":
    "Clicca sulla mappa per fissare il centro, poi trascina la maniglia per dimensionare il raggio.",
  "map.drawArea": "Disegna un'area",
  "map.finishArea": "Chiudi l'area",
  "map.drawAreaTitle":
    "Clicca per aggiungere ogni vertice; fai doppio clic o premi Chiudi per chiudere l'area.",
  "map.polyHint": "{count} punti — ne servono ≥ 3, poi doppio clic per chiudere",
  "map.clearZone": "Rimuovi la zona",
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

  // ── analisi (la schermata che unisce i tre pannelli) ────────────────────
  "insights.empty": "Non c'è ancora niente da analizzare",
  "insights.emptyHint":
    "Salute degli scraper, velocità del mercato e andamento dei prezzi si costruiscono tutti su ciò che le scansioni raccolgono. Salva prima una ricerca e questa schermata si riempirà da sola.",

  // ── velocità del mercato ────────────────────────────────────────────────
  "velocity.title": "Velocità del mercato",
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
  "trends.title": "Andamento dei prezzi",
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
  "trends.chartEmpty": "Nessun dato registrato per questa zona",
  "trends.chartEmptyHint":
    "Le mediane vengono scritte una volta al giorno, alla fine di una scansione. Il primo punto compare dopo la prossima.",
  "trends.changeSince": "{pct}% dal {date}",
  "trends.caveat":
    "Prezzo richiesto mediano al metro quadro tra gli annunci che l'app stava monitorando ogni giorno — il tuo campione, non tutto il mercato. Si muove con ciò che monitori tanto quanto con i prezzi.",
  "trends.oneDayOnly":
    "Per questa zona è registrato un solo giorno — la linea compare quando ce ne sono almeno due.",
  "trends.showComparables": "Mostra gli annunci dietro questa mediana",
  "trends.hideComparables": "Nascondi gli annunci dietro questa mediana",
  "trends.comparablesEmpty": "In questa zona non c'è al momento nessun annuncio con prezzo.",
  "trends.comparablesNote":
    "I {count} annunci attualmente prezzati in questa zona — l'insieme attuale da cui si calcola la mediana di oggi. I punti precedenti del grafico hanno conservato solo il conteggio, quindi i loro annunci esatti non sono più mostrabili. Cliccane uno per aprirne i dettagli.",
  "trends.comparablesNoteOne":
    "L'unico annuncio ({count}) attualmente prezzato in questa zona — l'insieme attuale da cui si calcola la mediana di oggi. I punti precedenti del grafico hanno conservato solo il conteggio, quindi i loro annunci esatti non sono più mostrabili. Cliccalo per aprirne i dettagli.",
  "trends.vsMedian": " ({sign}{pct}% rispetto alla mediana)",

  // ── log del backend ─────────────────────────────────────────────────────
  "logs.title": "Log del backend",
  "logs.filterPlaceholder": "Filtra (es. availability_check, blocked, error)",
  "logs.autoRefresh": "Aggiornamento automatico (3s)",
  "logs.lineCount": "{visible} / {total} righe",
  "logs.loadFailed": "Impossibile caricare il log",
  "logs.empty": "Nessuna riga di log — si riempie appena parte una scansione o una verifica.",
  "logs.noMatch": "Nessuna riga corrisponde a questo filtro.",
  "logs.source": "Origine: {path}",

  // ── salute degli scraper ────────────────────────────────────────────────
  "health.title": "Salute degli scraper",
  "health.subtitle": "la pipeline anti-bot riesce ancora a passare?",
  "health.loadFailed": "Impossibile caricare la salute degli scraper",
  "health.window":
    "Ultimi {days} giorni di esiti delle scansioni per portale. La prossima scansione parte da: {transport}.",
  "health.empty": "Nessuna scansione registrata — si riempie man mano che le scansioni girano.",
  "health.historyTitle": "Storico — com'è andata giorno per giorno",
  "health.colPortal": "Portale",
  "health.colDays": "Giorni (dal più vecchio a oggi)",
  "health.noDays": "nessun giorno registrato",
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
  "health.failingTitle": "Adesso — ricerche ancora in errore",
  "health.failingSubtitle":
    "La serie in corso, non un totale: si azzera alla prima scansione che passa.",
  "health.failingRow": "({portal}) — {count} scansioni {status} consecutive",
  "health.failingStatusFallback": "fallite",
  "health.failingHint":
    "Una serie breve è normale (blocchi anti-bot transitori). Una lunga significa che la via gratuita è caduta: valuta un pool di proxy o una chiave scrape-API nelle Impostazioni.",

  // ── calcolatori (scheda dettaglio) ──────────────────────────────────────
  "calc.mortgageTitle": "Stima del mutuo",
  "calc.downPayment": "Anticipo",
  "calc.interestRate": "Tasso d'interesse",
  "calc.perYear": "%/anno",
  "calc.duration": "Durata",
  "calc.years": "anni",
  "calc.loanAmount": "Importo del mutuo",
  "calc.monthlyPayment": "Rata mensile",
  "calc.yieldTitle": "Rendimento da affitto (investimento)",
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
  "auth.title": "Autenticazione richiesta",
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
