# Real Estate Search

Piattaforma locale, per PC o Raspberry Pi, che raccoglie gli annunci immobiliari
(vendita e affitto) di **Immobiliare.it** e **Idealista**, unifica gli annunci
diversi che descrivono la stessa casa, scarta quelli che non ti interessano
(nuda proprietà, piani terra, aste giudiziarie) e ti avvisa su **Telegram e/o
via email** appena compare qualcosa.

> La documentazione tecnica in [`docs/`](docs/) è in inglese: la usa chi
> modifica il programma. Questo file è per chi lo usa.

---

## Perché è diverso

I portali cancellano lo storico e nascondono i numeri, per proteggere le agenzie
che pubblicano gli annunci. Questa piattaforma tiene tutto in un **database
SQLite locale (`case.db`)** e diventa il tuo strumento per decidere e per
trattare:

1. **Punteggio affare e riferimenti di prezzo (`Deal Score`):** ogni nuovo
   annuncio viene confrontato con la mediana €/mq della sua micro-zona
   (`pricing_stats.py`). Insieme allo storico degli sconti praticati
   dall'agenzia (`market_velocity.py`), questo fa emergere le occasioni
   sottovalutate entro pochi minuti dalla pubblicazione.
   [Importa le quotazioni OMI dell'Agenzia delle Entrate](docs/using-the-app.md#refreshing-the-omi-benchmark)
   e ogni immobile mostra anche a quanto il fisco registra le **compravendite**
   nella sua micro-zona — affiancata alla mediana degli annunci, mai fusa con
   essa, perché i prezzi richiesti stanno sistematicamente sopra quelli
   effettivi, e segnalata come *non aggiornata* quando il semestre importato
   resta indietro.
2. **Prezzi fantasma e annunci riciclati (`Recycled Ad Tracker`):** quando una
   casa resta invenduta per mesi a 420.000 €, spesso l'agenzia cancella
   l'annuncio e lo ripubblica settimane dopo come "nuovo" a 389.000 € con altre
   foto. L'unificatore confronta coordinate e metri quadri anche con gli annunci
   già scomparsi e te lo dice: `[IMMOBILE RICICLATO] già online per 160 giorni a
   un prezzo più alto (-9,5%)`.
3. **Campanelli d'allarme e costo reale di proprietà:** dal testo dell'annuncio
   estrae i problemi strutturali e legali (inquilino con contratto in corso,
   nuda proprietà, spese condominiali oltre 250 €/mese, assenza di ascensore) e
   calcola il costo mensile realistico della casa (rata del mutuo + spese
   condominiali + margine per i lavori).
4. **Nessun cloud, tutto in locale:** gira sul tuo PC o sul tuo Raspberry Pi.
   Nessuna API a pagamento, nessun abbonamento, nessun tracciamento.

---

## Come partire

### Cosa serve

**Python 3.11 – 3.14**, e **Node.js 18+** per compilare la dashboard. Gli script
di avvio controllano la versione di Python prima di creare l'ambiente virtuale e
si fermano spiegando il problema, invece di fallire a metà dell'installazione
delle dipendenze.

Node serve solo quando c'è qualcosa da compilare. `start.bat` compila la
dashboard la prima volta e dopo ogni modifica ai suoi sorgenti, poi serve il
risultato compilato — quindi per usare l'app dopo la prima volta basta Python.

**La versione consigliata è la 3.12**: è quella con la maggiore disponibilità di
pacchetti precompilati per queste dipendenze, quindi non serve alcun compilatore
per installarle. La 3.11 è il minimo dichiarato (`requires-python` in
`backend/pyproject.toml`) ed è la versione su cui sono risolti i lock delle
dipendenze; i test girano anche sulla 3.14.

### Windows

Doppio clic su **`scripts\windows\start.bat`**:

- Installa tutte le dipendenze al primo avvio.
- Compila la dashboard se manca o se è più vecchia del codice, poi la serve
  insieme all'API su **http://localhost:8000**. Una finestra, una porta: chiudila
  e l'applicazione si ferma.
- Apre l'interfaccia nel browser predefinito, appena il server risponde
  davvero.
- Se un passo dell'installazione non riesce — internet assente durante
  l'installazione, una versione di Python fuori intervallo — si ferma lì, dice
  cosa è andato storto e cosa fare, e non avvia niente. La finestra resta aperta
  per lasciarti leggere.

Stai lavorando sul codice invece di usare l'app? **`scripts\windows\dev.bat`** è
il flusso di sviluppo: due finestre, il backend sulla :8000 con ricarica
automatica e Vite sulla :5173 con hot module reload, così una modifica è già a
schermo prima che l'editor perda il fuoco.

Tutti gli script solo per Windows (installa/rimuovi servizio, riavvio, arresto,
avvio automatico nascosto) stanno in `scripts\windows\` — vedi
[Remote Access & Running in the Background](docs/remote-access.md).

### Windows, senza installare niente

Se preferisci non installare né Python né Node, usa l'app pacchettizzata: scarica
lo zip `-windows-x64` dalla [pagina delle release](../../releases), estrailo dove
vuoi e fai doppio clic su **`RealEstateSearch.exe`**. Sta nell'area di notifica —
clic destro sull'icona per **Apri la dashboard**, **Apri la cartella dei dati** e
**Esci** — e non lascia nessuna finestra di terminale da tenere aperta.

I tuoi dati **non** stanno accanto al programma. Vanno in
`%LOCALAPPDATA%\RealEstateSearch\` (la voce di menu **Apri la cartella dei dati**
porta esattamente lì), perché un programma installato sotto `C:\Program Files`
non può scrivere nella propria cartella. **Per portare con te un database che hai
già:** metti il vecchio `case.db` — e `settings.json`, se vuoi che vengano anche
il token di Telegram e il cookie DataDome — nella stessa cartella di
`RealEstateSearch.exe` prima del primo avvio. All'avvio viene copiato nella
cartella dei dati, storico dei prezzi compreso. Se vuoi scegliere tu la
posizione, imposta `APP_DATA_DIR`.

### Docker (NAS, Raspberry Pi)

```bash
docker compose -f packaging/docker-compose.yml up -d
```

Compila per x86-64 e ARM64 (a ogni release viene pubblicata un'immagine già
compilata su `ghcr.io`), tiene `case.db` e `settings.json` su un volume
(`packaging/data/`) e riparte con la macchina. La porta è pubblicata **solo su
loopback**: l'API non è autenticata per impostazione predefinita (leggi
[Remote Access](docs/remote-access.md) prima di aprirla).

### Linux / Raspberry Pi (dai sorgenti)

Apri un terminale nella cartella del progetto ed esegui:

```bash
chmod +x scripts/linux/start.sh
./scripts/linux/start.sh
```

- Installa le dipendenze e avvia i due servizi insieme.
- Rende la dashboard raggiungibile da qualsiasi dispositivo della tua rete
  locale, all'indirizzo `http://<IP_DEL_TUO_PI>:5173`.
- Si ferma spiegando il problema se un passo dell'installazione non riesce,
  esattamente come lo script per Windows. Puoi lanciarlo da qualsiasi cartella:
  ricava da sé la posizione del progetto.

---

## Dal telefono

Lo scraper resta sul PC — i portali si fidano degli indirizzi IP domestici e
bloccano quelli dei server in cloud — ma la dashboard funziona dal browser di
Android e iOS, e la puoi installare come icona di un'app. Al posto di
`start.bat` esegui **`scripts\windows\serve.bat`**: serve la stessa singola porta
(8000) ma la lega al tuo indirizzo Tailscale invece che a loopback, così il
telefono la raggiunge e nient'altro può farlo. Come raggiungerla da fuori casa,
il modello di sicurezza dell'API aperta (non autenticata) e il token API
facoltativo sono spiegati in
[Remote Access & Running in the Background](docs/remote-access.md).

---

## Come si usa

La prima volta che la apri, l'app parte con una breve guida — cosa fa, la tua
prima ricerca, la prima scansione — e ti porta fino a una ricerca funzionante
senza che ti serva niente di quello che c'è qui sotto. I tre modi per creare
quella ricerca sono offerti uno accanto all'altro: descriverla in italiano,
compilare un modulo, oppure incollare l'URL dei risultati preso dal portale
stesso. Puoi saltare la guida quando vuoi, e non tornerà.

Poi:

1. **Sfoglia gli annunci**: gli annunci unificati hanno un contrassegno viola, e
   gli immobili comparsi dalla tua ultima visita portano il contrassegno
   **🆕 nuovo**.
2. **Fai selezione**: nascondi quello che non vuoi, segna come venduto o
   affittato, cerca e filtra la griglia, e fai pulizia in blocco.
3. **Aggiungi altre ricerche**: **Ricerche**, nella navigazione, contiene gli
   stessi tre modi, più lo stato di ogni ricerca che hai già.
4. **Scansiona quando vuoi tu**: **"Avvia scansione"** in qualsiasi momento,
   oppure lascia che sia lo scheduler a farlo in background.

La guida completa — tutti i filtri dei portali, le scorciatoie per costruire una
ricerca, la colonna di ricerca e filtri, la pulizia in blocco, come si elimina
una ricerca (e cosa succede agli annunci che aveva trovato) e come si silenzia
una ricerca — è in [Using the App](docs/using-the-app.md).

---

## Oltre la griglia degli annunci

La dashboard ha molto altro oltre alla griglia: un'interfaccia bilingue, una
mappa con zone di filtro che puoi disegnare, i riferimenti di prezzo e il
punteggio affare, lo Smart Match Score rispetto alla tua "casa dei sogni", i
tempi di percorrenza verso i posti dove vai davvero, una lettura facoltativa del
testo dell'annuncio (costi aggiuntivi, inquilino in corso, cosa si può usare in
trattativa — spenta per impostazione predefinita, e può girare su un modello
locale), i grafici dell'andamento dei prezzi e della velocità del mercato, un
pannello sulla salute degli scraper, le etichette libere, l'esportazione della
rosa dei candidati (HTML/MD/CSV, più un dossier PDF stampabile con la lista di
controllo per la visita) e la stima del mutuo. Il quadro completo è in
[Features](docs/features.md), e per verificare la rosa dei candidati contro i
portali quando vuoi c'è [Is This Ad Still Online?](docs/availability-check.md).

---

## Cosa fa in background

* **I dati restano**: impostazioni, ricerche monitorate, annunci, storico dei
  prezzi e stato di quello che hai nascosto sono salvati in locale in un file di
  database. Dai sorgenti è `backend/case.db`; nell'app pacchettizzata è
  `%LOCALAPPDATA%\RealEstateSearch\case.db`, e sotto Docker è il volume `/data` —
  in ogni caso fuori dalla cartella del programma, così un aggiornamento o una
  reinstallazione non lo toccano. Puoi chiudere l'app o spegnere il PC quando
  vuoi senza perdere niente di quello che ha raccolto.
* **Scansioni sempre attive**: le scansioni in background, le istantanee
  dell'andamento dei prezzi e gli avvisi girano solo mentre l'app è in
  esecuzione. Con `start.bat`/`serve.bat` questo significa tenere aperta (anche
  ridotta a icona) la finestra del terminale; l'app pacchettizzata non ha
  nessuna finestra da tenere aperta — sta nell'area di notifica. Per farla
  partire all'accensione, prima che tu abbia fatto il login, vedi
  [Running it 24/7 on Windows](docs/remote-access.md#running-it-247-on-windows-no-window-to-keep-open).
* **Riavvio dalla dashboard**: dopo aver aggiornato l'app, premi **Impostazioni →
  🔄 Riavvia il backend** invece di andare a cercare la finestra del terminale.
  La dashboard va offline per qualche secondo e si ricarica da sola. `start.bat`
  e `serve.bat` servono entrambi una dashboard già compilata, quindi questo
  applica una modifica al backend — se è cambiato il frontend, rilancia lo script
  e la ricompila. Con `dev.bat` la ricarica automatica di solito prende da sé una
  modifica al codice.
* **Metti in pausa le scansioni automatiche**: **Impostazioni → Scansione
  automatica → Metti in pausa le scansioni automatiche** impedisce alle
  scansioni programmate di toccare i portali — utile per far riposare la
  connessione mentre sei via, senza disattivare una per una tutte le ricerche.
  Finché è attiva, la barra in alto mostra *⏸ Scansioni automatiche in pausa*, e
  **Avvia scansione** funziona ancora a richiesta (una richiesta esplicita
  scavalca la pausa). Per silenziare una sola ricerca, togli invece la spunta
  nell'elenco delle ricerche.
* **Scansione di recupero**: la scansione programmata parte normalmente un
  intervallo intero dopo l'avvio. Se il PC era spento e l'ultima scansione è già
  più vecchia dell'intervallo configurato, parte invece una scansione di recupero
  circa 2 minuti dopo l'avvio — così basta accendere il PC per riportare gli
  annunci al presente.
* **Aggiornare non ti fa perdere quello che hai raccolto**: un database scritto
  da una release precedente si apre come l'avevi lasciato — gli immobili, i
  preferiti, le note, le etichette, lo storico dei prezzi, le ricerche
  monitorate e tutto quello che hai nascosto o segnato come venduto — con lo
  schema portato al presente intorno a quei dati. E non è una speranza, è una
  verifica: un database nella forma in cui lo scriveva la release 1.0.0 fa parte
  della suite di test, e ogni build ne aggiorna una copia e la confronta riga per
  riga con quello che conteneva prima. **Tornare a una versione precedente non è
  supportato**: una volta che un aggiornamento ha cambiato la struttura del
  database, una release più vecchia che lo apre lo scrive nel log — una riga che
  nomina la discrepanza e la cartella delle copie — e poi va avanti comunque, il
  che di solito funziona ma non è una cosa su cui contare. Se devi tornare
  indietro, o reinstalli la versione più recente, o ripristini la copia
  `case-pre-<versione>.db` salvata subito prima dell'aggiornamento (vedi *Copie
  di sicurezza* qui sotto).
* **Copie di sicurezza, e la strada per tornare indietro**: una copia di
  `case.db` viene scritta in `backend/backups/` al massimo una volta al giorno
  (il controllo avviene all'avvio; vengono tenute le 14 copie più recenti).
  **Prima che un aggiornamento cambi la struttura del database, viene salvata una
  copia a parte**: si chiama `case-pre-<versione>.db`, è scritta prima che la
  modifica venga applicata e la rotazione giornaliera non la rimuove mai, così lo
  stato da cui sei partito resta disponibile per tutto il tempo che ti serve ad
  accorgerti che qualcosa non va. La cartella è locale: se vuoi una copia fuori
  dalla macchina, puntaci la tua sincronizzazione cloud o un secondo disco. Le
  copie sono fatte con l'API di backup di SQLite, quindi sono coerenti anche se
  in quel momento una scansione sta scrivendo.

  **Impostazioni → Gestione dei dati → Copie di sicurezza** è il posto dove le
  usi, senza fermare l'app e senza spostare file a mano. Ogni copia è elencata
  con la sua data, la sua dimensione e la versione di schema che contiene, e
  puoi:
  * **Salva una copia adesso** — prima di fare qualcosa di cui non sei sicuro.
  * **Scarica** — la copia arriva nella cartella dei download come un normale
    file SQLite. Tienila su un altro disco, oppure aprila con qualsiasi
    strumento per SQLite: qui niente è chiuso a chiave.
  * **Ripristina questa** — sostituisce tutto quello che c'è adesso nel database
    con quella copia. Ti chiede prima di scrivere una parola, e salva una copia
    dello stato *attuale* prima di toccare qualsiasi cosa, così anche
    ripristinare il file sbagliato è recuperabile. Dopo, la dashboard si ricarica
    da sé.
  * **Portane una qui** — carica un `case.db` arrivato da un'altra macchina.
    Viene controllato che sia davvero un database di questa app *prima* che
    qualcosa venga sostituito, e si limita a entrare nell'elenco: passare a
    quella copia è il passo separato **Ripristina**.

  *Se invece copi il database a mano, porta con te anche `case.db-wal` e
  `case.db-shm`*: le modifiche più recenti vivono in quei due file compagni
  finché il database non le assorbe, e `case.db` da solo ne sarebbe privo. I
  pulsanti qui sopra esistono perché tu non debba saperlo.
* **Caricamento a pagine**: la dashboard carica i risultati una pagina alla volta
  e prende la successiva mentre scorri, così una raccolta grande si apre subito
  invece di scaricare tutto in anticipo. Il numero accanto ai filtri è sempre il
  totale delle corrispondenze, e **Seleziona tutto**, la mappa e l'esportazione
  del dossier lavorano comunque sull'insieme filtrato per intero — non solo sulla
  parte a schermo. Mentre una scansione è in corso, la dashboard controlla se
  qualcosa è cambiato con una richiesta leggera e ricarica la griglia solo quando
  è cambiato davvero.
* **Guardare una scansione mentre avviene**: il pulsante dell'attività, nella
  barra in alto, apre il racconto di quello che sta facendo la scansione — su
  quale delle tue ricerche è e su quale portale, quante pagine ha letto, quanti
  annunci sono arrivati finora e quale trasporto sta usando quando la scala si
  alza a metà scansione. Le pause tra una pagina e l'altra sono chiamate pause,
  perché è lì che finisce la maggior parte del tempo di una scansione e uno
  schermo immobile sembra altrimenti un blocco. **Nessuna barra di avanzamento
  viene disegnata se non è il portale stesso a dire quante pagine ci sono** —
  altrove c'è un conteggio che sale, perché una barra che arriva al 90% e si
  ferma non dice niente. Sotto c'è il diario: una riga per ricerca per scansione,
  cosa ha letto, cosa ha trovato e come è finita, ancora lì dopo la fine della
  scansione e dopo una ricarica della pagina.
* **Log a schermo**: **Apri il log**, sotto *Diagnostica* nella schermata
  dell'attività, mostra il log del backend — la verifica di disponibilità che
  avanza riga per riga, i blocchi DataDome, gli errori con lo stack trace — senza
  aprire `backend/app.log` in un editor di testo. Filtra per parola chiave e si
  aggiorna da sé ogni pochi secondi mentre è aperto. È il resoconto riga per riga
  di quello che il processo ha fatto, e il posto giusto da guardare quando il
  racconto qui sopra non spiega qualcosa.
* **Gestione dei dati (ripartire da zero)**: **Impostazioni → Gestione dei dati**
  ha tre azzeramenti irreversibili, ognuno protetto da una conferma. *Svuota la
  dashboard* elimina tutti gli immobili trovati e lo storico dei prezzi ma tiene
  le tue ricerche — la scansione successiva ricostruisce la griglia in silenzio,
  senza una valanga di notifiche. *Azzera gli andamenti dei prezzi* cancella solo
  lo storico dei grafici. *Ripristino di fabbrica* riporta tutto a
  un'installazione appena fatta (prima viene salvata una copia del database). Le
  tue impostazioni di notifica e di accesso non vengono mai toccate — e ognuna di
  queste tre operazioni è recuperabile dalla copia salvata subito prima, elencata
  sotto *Copie di sicurezza* nello stesso pannello.

---

## Notifiche

Telegram ed email si configurano entrambi in **Impostazioni**, con una guida
passo per passo accanto a ciascuno, e ogni ricerca può mandare i propri avvisi a
uno dei due canali, a entrambi o a nessuno.

Gli avvisi Telegram su un immobile portano anche i pulsanti **⭐ Preferito ·
👁️ Visto · 🚫 Nascondi · 🗺️ Mappa**, così puoi smistare un annuncio dal telefono
e vedere il risultato nella dashboard. Non servono porte aperte né un indirizzo
pubblico: il backend raccoglie i tocchi attraverso la propria connessione in
uscita.

I dettagli della configurazione, i pulsanti, la password per le app di Gmail e
gli avvisi sulla salute degli scraper sono in
[Notifications](docs/notifications.md).

---

## Come va la prima scansione

La **prima** scansione di una ricerca raccoglie tutti gli annunci già presenti e
li salva per costruire la base di partenza. **Durante la prima scansione non
viene mandata nessuna notifica**, per non inondare la tua chat Telegram. Gli
avvisi per i nuovi annunci e per i cali di prezzo arrivano a partire dalla
**seconda** scansione.

---

## Quando una scansione non riporta più annunci

"Non è arrivato niente" ha tre cause diverse, e ognuna vuole da te una cosa
diversa. **`Nessun risultato`** è una risposta: il portale è stato interrogato e
quel giorno non aveva niente. **`Non riuscita`** significa che l'URL della
ricerca è sbagliato, oppure che il portale ha cambiato il proprio codice.
**`Bloccata`** significa che il portale ha rifiutato la richiesta invece di
risponderle — entrambi i siti stanno dietro a un servizio anti-bot — e questa è
una cosa prevista, non un difetto: la ricerca viene ritentata alla scansione
successiva, e vieni avvisato solo dopo diversi fallimenti di fila. Una ricerca
bloccata lascia la risposta che hai a schermo **incompleta, non vuota**, e l'app
lo dice sulla riga a cui è capitato.

Per un blocco, la prima cosa da provare è un cookie `datadome` fresco, che l'app
può prendere per te da un browser locale. Per Idealista esiste anche un'**API
ufficiale**: se ottieni una chiave, le ricerche su quel portale chiedono al
portale i suoi stessi dati invece di leggerne le pagine, quindi non c'è più
niente da rifiutare (le ricerche che l'API non sa esprimere con precisione
continuano a usare lo scraper); per Immobiliare non esiste l'equivalente. Per
distinguere le tre cause, per sapere cosa puoi cambiare e quanto costa ogni
cambiamento, e per capire cosa i portali guardano davvero, vedi
[A Scan Stopped Returning Listings](docs/scan-returns-nothing.md).

## Com'è fatto

* **Backend**: Python 3.11–3.14 / FastAPI / SQLite / APScheduler.
* **Scraper resistenti**: costruiti su 4 strategie in cascata (schema JSON-LD →
  stato `__NEXT_DATA__` incorporato nella pagina → lettura euristica dell'HTML
  senza usare le classi CSS → API interna come ultima risorsa).
* **Scansione da IP domestico**: pensato per girare in locale o su una rete
  casalinga. Gli IP dei server in cloud sono bloccati pesantemente da DataDome,
  mentre l'IP di casa è considerato affidabile: è quello che rende le scansioni
  utilizzabili.
* **Unificazione dei duplicati**: due annunci vengono unificati solo se c'è una
  prova geografica (coordinate entro 60 metri **oppure** stessa via e stesso
  numero civico) più prezzo, locali, piano e metri quadri compatibili.
* **Frontend**: React / Vite / TypeScript / Tailwind CSS, con TanStack Query
  come strato dati — ogni lettura è una query con la sua chiave e ogni scrittura
  una mutation, così la risposta lenta a un filtro che hai già lasciato non può
  arrivare a schermo, e una scansione che finisce non ti fa perdere il punto in
  cui eri nei risultati. Pulsanti, campi, finestre di dialogo e il resto sono un
  unico insieme di primitive costruite su Radix, quindi ogni finestra trattiene
  il fuoco, ogni menu risponde a Esc e ogni comando si raggiunge con la sola
  tastiera — verificato primitiva per primitiva, non lasciato alla revisione.
  L'interfaccia è bilingue (italiano / inglese) attraverso un piccolo dizionario
  senza dipendenze — nessuna libreria di i18n, e una voce presente in una lingua
  ma mancante nell'altra fa fallire la compilazione. Si apre in italiano; la
  lingua si cambia con un clic e la scelta viene ricordata.

### Documentazione per chi lavora sul codice

Se stai modificando il codice invece di usare l'app, otto documenti — **in
inglese**, come tutto quello che sta in [`docs/`](docs/) — contengono tutto
quello che non si capisce leggendo il codice:

* **[Architecture](docs/architecture.md)** — dove intervenire per ogni tipo di
  modifica, lo schema dei dati, il ciclo di vita di un immobile, la strategia
  delle migrazioni e le fragilità note con il sintomo che ciascuna produce.
* **[Invariants](docs/invariants.md)** — le ventinove regole che non devono
  rompersi, ognuna con la regressione che l'ha resa necessaria. Leggi quella che
  ti riguarda *prima* di modificare, non dopo.
* **[Conventions](docs/conventions.md)** — come si scrive e come si testa il
  codice qui.
* **[The interface](docs/ui.md)** — i design token, il catalogo delle primitive,
  di cosa si occupa ogni schermata e la regola per decidere dove va una nuova.
* **[Development cycle](docs/development-cycle.md)** — come si fa una modifica:
  l'unità di lavoro, i controlli che girano prima di ogni commit, quando un
  comportamento nuovo si merita un invariante e come si taglia una release da un
  tag.
* **[Audit playbook](docs/audit.md)** — il controllo di salute dell'intero
  progetto, ripetibile: la base verde, l'ordine in cui rivedere i moduli, il
  riscontro invariante→test.
* **[What only a person can test](docs/manual-tests.md)** — i nove controlli che
  nessun test automatico può raggiungere, nell'ordine in cui farli prima di una
  release: i portali veri, le credenziali, il pacchetto su una macchina pulita,
  il telefono. Ognuno dice perché l'automazione non può coprirlo e finisce con un
  esito, passato o non passato.
* **[Roadmap](docs/roadmap.md)** — cosa si sa e non è fatto, con l'ostacolo
  dichiarato in modo tanto chiaro quanto l'ambizione: ogni limite ancora in
  piedi e quanto costerebbe superarlo, i rilievi che una revisione ha
  deliberatamente deciso di non affrontare, e cosa manca per arrivare a una
  versione ospitata e multi-utente.

---

## Test e verifica

I test automatici coprono tutte le strategie di lettura delle pagine, i casi
limite nella formattazione dei prezzi, le regole di unificazione, le variazioni
nello storico dei prezzi e le routine dello scanner — tutti offline (nessuna
chiamata di rete), quindi passano o falliscono sempre per un motivo reale. Il
frontend ha i propri test per la logica pura (la codifica dei filtri nella
querystring, le etichette dei piani, i dizionari italiano/inglese — pareggio
delle chiavi e dei segnaposto — e il salvataggio della finestra delle
impostazioni, così un campo non può smettere di essere salvato in silenzio).

I test del backend girano con l'ambiente virtuale Python locale:

```bash
cd backend
& .venv/Scripts/python.exe -m pytest
```

I test del frontend:

```bash
cd frontend
npm test
```

*(Tutti i test devono passare prima di fare un commit.)*

C'è anche una suite nel browser, che usa la dashboard come la usi tu davvero: il
build di produzione, servito contro un backend reale su un database usa-e-getta
riempito con un insieme di dati dimostrativi. Non apre mai il tuo `case.db`, non
occupa mai la porta 8000 e non raggiunge mai la rete:

```bash
cd frontend
npm run e2e:browser   # una volta sola: scarica Chromium
npm run e2e
```

Niente di tutto questo tocca un portale immobiliare, ed è questo che la rende
affidabile ed è anche quello che non può dirti: una suite verde significa che la
logica è giusta, non che i portali si leggono ancora. I controlli che richiedono
una persona — una scansione vera da una connessione vera, le credenziali usate
per davvero, il pacchetto avviato su un PC che non ha mai avuto gli strumenti di
sviluppo, il telefono via Tailscale — sono elencati in
[What only a person can test](docs/manual-tests.md), con la risposta giusta
scritta per ognuno. Vanno fatti prima di taggare una release.

### Dipendenze bloccate

`backend/requirements.txt`, `requirements-dev.txt` e
`requirements-package.txt` sono lockfile **generati**: ogni pacchetto fissato
alla versione esatta, con gli hash, così lo stesso checkout installa la stessa
applicazione su qualsiasi macchina e in qualsiasi momento futuro. Si modifica il
file `.in` accanto a loro e si ricompila con
[uv](https://docs.astral.sh/uv/):

```bash
cd backend
uv pip compile requirements.in --universal --python-version 3.11 --generate-hashes -o requirements.txt
uv pip compile requirements-dev.in --universal --python-version 3.11 --generate-hashes -o requirements-dev.txt
uv pip compile requirements-package.in --universal --python-version 3.11 --generate-hashes -o requirements-package.txt
```

Dopo aver toccato `requirements.in` va ricompilato **tutti e tre**: gli altri due
file `.in` iniziano con `-r requirements.in`, quindi una versione fissata che si
muove in uno e non negli altri lascia il pacchetto Windows a installare una
versione diversa da quella su cui sono girati i controlli.

Il frontend è bloccato allo stesso modo da `frontend/package-lock.json`. Si
installa con **`npm ci`, mai `npm install`**: `ci` installa esattamente quello
che il lock fissa e si ferma rumorosamente se lock e `package.json` non vanno
d'accordo, mentre `install` riscrive il lock in silenzio e regala a quella
macchina strumenti diversi. Gli script di avvio e la CI usano entrambi `npm ci`,
quindi l'unica volta in cui `npm install` è la cosa giusta è quando stai
deliberatamente aggiungendo o aggiornando una dipendenza — e allora il lock
riscritto fa parte della modifica e va nel commit con essa.

```bash
cd frontend
npm ci
```

C'è un secondo progetto npm, molto più piccolo, in `scripts/apitypes/`, bloccato
e installato allo stesso modo. Non contiene niente di quello che l'applicazione
spedisce: solo `openapi-typescript`, che `scripts/gen_api_types.py` usa per
compilare il documento OpenAPI del backend in `frontend/src/types/api.ts`. Sta
separato perché quello strumento si lega alle API del compilatore TypeScript e lo
tiene ancora fissato alla 5.x, mentre l'app è compilata con TypeScript 7; npm
risolve una peer dependency alla radice dell'albero e si rifiuta di annidarla,
quindi installato accanto al frontend il generatore caricherebbe il compilatore
dell'app e non funzionerebbe. Un albero suo lascia a ciascuno esattamente la
versione che gli serve.

```bash
cd scripts/apitypes
npm ci
```

Rigenerare uno dei due lock npm è l'unico passo con una trappola dentro, e la
trappola ha due ganasce. Mai `npm install --package-lock-only`: senza un albero
materializzato npm ne risolve uno più magro e scrive un lock che poi `npm ci`
rifiuta come non allineato, e l'errore nomina un pacchetto transitivo da cui
niente dipende direttamente (`@emnapi/core`, raggiunto attraverso il ripiego wasm
facoltativo di Tailwind), quindi sembra un problema del registro npm e non un
lock malformato. E mai cancellare prima `package-lock.json`:
`@tailwindcss/oxide-wasm32-wasi` nomina quel pacchetto e altri cinque in
`bundleDependencies`, npm scrive le loro voci annidate solo quando sta
aggiornando un lock che le ha già, quindi un lock costruito da un `package.json`
nudo li omette tutti e sei — ed è esattamente su questo che
`test_generated_artifacts.py` fallisce.

Aggiorna sul posto, invece. Modifica `package.json`, lascia il lock esistente
dov'è, e passaci sopra `npm install`:

```bash
cd frontend
npm install
```

Fallo su Linux, con la versione di Node che `.github/workflows/ci.yml` fissa. Il
sottoalbero wasm viene saltato su Windows, quindi un'installazione fatta lì
perde in silenzio voci che poi `npm ci` sul runner rifiuta, e il build è rosso su
un lock che in locale sembrava a posto. La CI fissa quella versione esatta per la
stessa famiglia di motivi: npm 10 e npm 11 non sono d'accordo su cosa sia un lock
valido, e quello scritto da uno fa fallire `npm ci` su un checkout che per il
resto è perfettamente sano.

Nessuno dei due lock va guardato a mano: `.github/dependabot.yml` apre una pull
request raggruppata per ecosistema al mese. Entrambe sono un **avviso, non un
diff**: ognuna nomina versioni che vale la pena prendere e riscrive un file
generato su una macchina che non è configurata come questa. Quella del frontend
porta un `package-lock.json` scritto senza il sottoalbero wasm di cui sopra:
prendi le versioni che nomina, mettile in `package.json` e rigenera il lock come
descritto. Quella del backend modifica un lock generato senza toccare il file
`.in` da cui quel lock è compilato: prendi la versione che nomina, sposta il pin
nel `.in`, ricompila tutti e tre come sopra, e mandalo sul ramo sopra il resto.

### Strumenti di sviluppo facoltativi

Oltre alle dipendenze di esecuzione, in `backend/requirements-dev.txt` c'è una
dotazione di sviluppo facoltativa (lint, copertura, test basati su proprietà,
scansione delle CVE nelle dipendenze e un hook di pre-commit). Non viene **mai**
installata sul dispositivo di destinazione, solo in un checkout di sviluppo
(contiene anche le dipendenze di esecuzione, quindi è l'unico file che uno
sviluppatore deve installare):

```bash
cd backend
& .venv/Scripts/python.exe -m pip install -r requirements-dev.txt
& .venv/Scripts/ruff.exe check app tests      # lint
& .venv/Scripts/ruff.exe format app tests     # formattazione
& .venv/Scripts/python.exe -m pip_audit -r requirements.txt   # scansione CVE
```

## Licenza

[MIT](LICENSE). Usalo, modificalo, distribuiscilo — tieni la nota di copyright.

Gli annunci che questa app raccoglie non sono coperti da quella licenza:
appartengono ai portali da cui arrivano, e le quotazioni OMI appartengono
all'Agenzia delle Entrate, la cui fornitura è gratuita ma non è open data.
Nessuno dei due viene ridistribuito qui, ed è per questo che i riferimenti di
prezzo OMI partono vuoti e sei tu a importare il tuo download.
