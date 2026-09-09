# Real Estate Search

Raccoglie gli annunci immobiliari di **Immobiliare.it** e **Idealista** (vendita
e affitto), riconosce quando due annunci descrivono la stessa casa, scarta
quelli che non ti interessano e ti avvisa su **Telegram o via email** appena
compare qualcosa. Gira sul tuo PC o sul tuo Raspberry Pi: niente cloud, niente
abbonamenti.

> Questo file è per chi usa il programma. I documenti di dettaglio linkati qui
> sotto stanno in [`docs/`](docs/) e sono in inglese.

---

## Perché non è solo un altro aggregatore

I portali cancellano lo storico e nascondono i numeri. Qui resta tutto in un
database SQLite sul tuo disco (`case.db`), e da quel momento diventa materiale
per trattare.

**Sai se il prezzo è fuori mercato.** Ogni annuncio nuovo viene confrontato con
la mediana €/mq della sua micro-zona e con gli sconti che quell'agenzia ha
praticato in passato. Se importi le
[quotazioni OMI dell'Agenzia delle Entrate](docs/using-the-app.md#refreshing-the-omi-benchmark),
vedi anche a quanto il fisco registra le compravendite vere della zona:
affiancata alla mediana degli annunci, non mescolata, perché chi vende chiede
sempre più di quanto poi incassa.

**Riconosci gli annunci riciclati.** Una casa ferma da mesi a 420.000 € sparisce
e ricompare settimane dopo come "nuova" a 389.000 €, con altre foto. Il
programma la ritrova confrontando coordinate e metratura anche con gli annunci
già scomparsi, e te lo scrive: `[IMMOBILE RICICLATO] già online per 160 giorni a
un prezzo più alto (-9,5%)`.

**Vedi cosa costa davvero.** Dal testo dell'annuncio tira fuori i problemi che di
solito emergono troppo tardi (inquilino con contratto in corso, nuda proprietà,
spese condominiali sopra i 250 € al mese, niente ascensore) e calcola la spesa
mensile reale: rata, condominio e un margine per i lavori.

**Resta tutto in casa tua.** Nessun servizio esterno a pagamento, nessun
tracciamento, nessun dato che esce dalla tua rete.

---

## Installazione

Serve **Python 3.11–3.14** e, solo per compilare la dashboard, **Node.js 18+**.
La versione consigliata è la **3.12**, quella con più pacchetti già compilati
disponibili: con le altre potrebbe servirti un compilatore. Gli script di avvio
controllano la versione prima di creare l'ambiente virtuale, così se qualcosa
non va te lo dicono subito invece di piantarsi a metà installazione.

Dopo la prima volta Node non serve più: `start.bat` ricompila la dashboard solo
quando i suoi sorgenti sono cambiati.

### Windows

Doppio clic su **`scripts\windows\start.bat`**. Installa le dipendenze, compila
la dashboard se serve, e la pubblica insieme all'API su
**http://localhost:8000**. Una finestra sola, una porta sola: quando la chiudi,
il programma si ferma. Il browser si apre da solo appena il server risponde
davvero.

Se un passaggio non riesce, lo script si ferma lì, spiega cosa è successo e non
avvia niente. La finestra resta aperta per darti il tempo di leggere.

Per lavorare sul codice usa invece **`scripts\windows\dev.bat`**: apre due
finestre, backend sulla 8000 con ricarica automatica e Vite sulla 5173 con hot
reload. Gli altri script per Windows (servizio, riavvio, arresto, avvio
automatico) stanno in `scripts\windows\` e sono spiegati in
[accesso da remoto](docs/remote-access.md).

### Windows, senza installare niente

Scarica lo zip `-windows-x64` dalla [pagina delle release](../../releases),
estrailo dove vuoi e apri **`RealEstateSearch.exe`**. Vive nell'area di
notifica, senza finestre di terminale: clic destro per aprire la dashboard, la
cartella dei dati, o per uscire.

I dati **non** stanno accanto al programma ma in
`%LOCALAPPDATA%\RealEstateSearch\`, perché un programma installato sotto
`C:\Program Files` non può scrivere nella propria cartella. Se hai già un
`case.db` e vuoi portartelo dietro, mettilo accanto a `RealEstateSearch.exe`
prima del primo avvio (con `settings.json`, se vuoi anche il token Telegram e il
cookie DataDome): al primo avvio viene copiato al posto giusto, storico dei
prezzi compreso. Per scegliere tu dove tenerli, imposta `APP_DATA_DIR`.

### Docker (NAS, Raspberry Pi)

```bash
docker compose -f packaging/docker-compose.yml up -d
```

Immagini già pronte per x86-64 e ARM64 su `ghcr.io`, pubblicate a ogni release.
`case.db` e `settings.json` restano su un volume (`packaging/data/`) e il
container riparte con la macchina. La porta è esposta **solo su loopback**:
l'API non è autenticata, quindi leggi
[accesso da remoto](docs/remote-access.md) prima di aprirla verso l'esterno.

### Linux e Raspberry Pi, dai sorgenti

```bash
chmod +x scripts/linux/start.sh
./scripts/linux/start.sh
```

Installa le dipendenze, avvia i due servizi e rende la dashboard raggiungibile
da tutta la rete locale su `http://<IP-del-Pi>:5173`. Puoi lanciarlo da
qualsiasi cartella: la posizione del progetto se la ricava da solo.

---

## Dal telefono

La dashboard funziona bene dal browser di Android e iOS, e puoi installarla come
icona sulla schermata iniziale. Lo scraper invece resta sul PC, perché i portali
si fidano degli indirizzi IP domestici e bloccano quelli dei server in cloud.

Al posto di `start.bat` lancia **`scripts\windows\serve.bat`**: pubblica la
stessa porta 8000, ma legata al tuo indirizzo Tailscale invece che a loopback.
Il telefono la raggiunge, il resto del mondo no. Come arrivarci da fuori casa e
il token API facoltativo sono in [accesso da remoto](docs/remote-access.md).

---

## Come si usa

Al primo avvio parte una guida breve che ti porta fino a una ricerca funzionante
senza bisogno di leggere altro. Ti propone i tre modi per crearla, uno accanto
all'altro: descrivere in italiano quello che cerchi, compilare un modulo, oppure
incollare l'indirizzo di una pagina di risultati del portale. Puoi saltarla
quando vuoi e non ricompare.

Poi il giro è questo:

1. **Guarda cosa è arrivato.** Gli annunci unificati hanno un contrassegno
   viola; quelli comparsi dalla tua ultima visita sono segnati **🆕 nuovo**.
2. **Fai selezione.** Nascondi quello che non ti interessa, segna cosa è stato
   venduto o affittato, filtra la griglia, ripulisci in blocco.
3. **Aggiungi ricerche.** La sezione **Ricerche** contiene gli stessi tre modi,
   più lo stato di quelle che hai già.
4. **Scansiona quando vuoi.** C'è **Avvia scansione** per farlo subito, oppure
   lasci lavorare lo scheduler.

Tutto il resto — filtri dei portali, scorciatoie, pulizia in blocco, cosa
succede agli annunci quando elimini una ricerca — è in
[guida all'uso](docs/using-the-app.md).

---

## Cosa c'è oltre la griglia

Una mappa con zone di filtro che disegni tu, il punteggio affare e i riferimenti
di prezzo, il confronto con la tua "casa dei sogni", i tempi di viaggio verso i
posti dove vai davvero, i grafici dell'andamento dei prezzi, un pannello sulla
salute degli scraper, le etichette libere, la stima del mutuo e l'esportazione
della rosa dei candidati (HTML, Markdown, CSV, più un dossier PDF con la lista
di controllo per la visita). L'interfaccia è in italiano e in inglese, si cambia
con un clic.

C'è anche una lettura automatica del testo dell'annuncio, che ne ricava costi
nascosti e appigli per la trattativa. È **spenta di serie** e può girare su un
modello in locale.

Il quadro completo è in [funzionalità](docs/features.md). Per ricontrollare la
tua rosa contro i portali quando vuoi, c'è
[l'annuncio è ancora online?](docs/availability-check.md).

---

## Come lavora mentre non lo guardi

**I dati restano dove sono.** Impostazioni, ricerche, annunci, storico dei
prezzi e cosa hai nascosto stanno in un file di database, sempre fuori dalla
cartella del programma: `backend/case.db` dai sorgenti,
`%LOCALAPPDATA%\RealEstateSearch\case.db` nell'app pacchettizzata, il volume
`/data` sotto Docker. Un aggiornamento o una reinstallazione non lo toccano, e
puoi spegnere il PC quando vuoi.

**Le scansioni girano solo mentre il programma è acceso.** Con `start.bat` o
`serve.bat` vuol dire tenere aperta la finestra del terminale, anche ridotta a
icona; l'app pacchettizzata non ha finestre da tenere aperte. Per farla partire
all'accensione, prima ancora del login, vedi
[come tenerlo attivo 24 ore su 24](docs/remote-access.md#running-it-247-on-windows-no-window-to-keep-open).

**Se il PC era spento, recupera da solo.** La scansione programmata parte normalmente un
intervallo dopo l'avvio. Ma se l'ultima è più vecchia dell'intervallo
configurato, ne parte una di recupero dopo circa due minuti: accendi il PC e gli
annunci tornano al presente.

**Puoi metterle in pausa tutte insieme.** **Impostazioni → Scansione automatica →
Metti in pausa** ferma le scansioni programmate senza doverle disattivare una per
una: utile per far riposare la connessione mentre sei via. La barra in alto lo
ricorda, e **Avvia scansione** continua a funzionare, perché una richiesta
esplicita scavalca la pausa. Per silenziare una sola ricerca, togli invece la
spunta nel suo elenco.

**Puoi riavviare il backend dalla dashboard.** **Impostazioni → 🔄 Riavvia il
backend**, invece di andare a cercare la finestra del terminale. La dashboard va
giù per qualche secondo e si ricarica da sola. Vale per le modifiche al backend:
se è cambiato il frontend, rilancia lo script, che lo ricompila.

**Vedi la scansione mentre succede.** Il pulsante dell'attività nella barra in
alto racconta cosa sta facendo: quale ricerca, quale portale, quante pagine ha
letto, quanti annunci sono arrivati. Le pause tra una pagina e l'altra sono
scritte come pause, perché è lì che se ne va la maggior parte del tempo e uno
schermo fermo sembrerebbe un blocco. La barra di avanzamento compare **solo se è
il portale a dire quante pagine ci sono**, altrimenti trovi un contatore che
sale: una barra ferma al 90% non informa nessuno. Sotto c'è il diario, una riga
per ricerca, che resta lì anche dopo aver ricaricato la pagina.

**Il log è a schermo.** *Diagnostica → Apri il log* mostra quello che sta
facendo il backend riga per riga — la verifica di disponibilità, i blocchi
DataDome, gli errori completi — senza aprire `backend/app.log` in un editor. Si
filtra per parola e si aggiorna da solo.

**La griglia si carica a pagine.** Prende la pagina successiva mentre scorri,
così una raccolta grande si apre subito. Il numero accanto ai filtri è sempre il
totale, e **Seleziona tutto**, la mappa e l'esportazione lavorano su tutto
l'insieme filtrato, non solo su quello che vedi.

**Aggiornare non ti fa perdere niente.** Un database scritto da una versione
precedente si riapre come l'avevi lasciato: immobili, preferiti, note,
etichette, storico dei prezzi, ricerche. Non è un auspicio, è una prova: un
database nella forma in cui lo scriveva la 1.0.0 fa parte della suite di test, e
ogni build lo aggiorna e lo confronta riga per riga con quello che conteneva
prima. **Tornare indietro non è supportato**: una versione vecchia che apre un
database già aggiornato lo segnala nel log e prosegue lo stesso, cosa che di
solito funziona ma su cui non conviene contare. Se devi tornare indietro,
ripristina la copia `case-pre-<versione>.db`.

### Copie di sicurezza

Una copia di `case.db` finisce in `backend/backups/` al massimo una volta al
giorno, e vengono tenute le 14 più recenti. **Prima che un aggiornamento cambi la
struttura del database** ne viene salvata una a parte, `case-pre-<versione>.db`,
che la rotazione giornaliera non cancella mai: lo stato da cui sei partito resta
lì per tutto il tempo che ti serve ad accorgerti che qualcosa non va.

Le copie sono fatte con l'API di backup di SQLite, quindi sono valide anche se
in quel momento una scansione sta scrivendo. La cartella è locale: se vuoi una
copia fuori dalla macchina, puntaci il tuo servizio di sincronizzazione o un
secondo disco.

Si usano da **Impostazioni → Gestione dei dati → Copie di sicurezza**, senza
fermare il programma e senza spostare file a mano. Ogni copia è elencata con
data, dimensione e versione dello schema:

* **Salva una copia adesso**, prima di fare qualcosa di cui non sei sicuro.
* **Scarica**: arriva nei download come un normale file SQLite, apribile con
  qualsiasi strumento. Qui niente è chiuso a chiave.
* **Ripristina questa**: sostituisce il database attuale. Ti fa scrivere una
  parola di conferma e salva comunque una copia dello stato attuale prima di
  toccare qualcosa, così anche sbagliare copia è recuperabile.
* **Portane una qui**: carica un `case.db` arrivato da un'altra macchina. Viene
  controllato che sia davvero un database di questo programma *prima* di
  sostituire qualsiasi cosa, e comunque si limita a entrare nell'elenco:
  passarci sopra è il passo separato **Ripristina**.

Se invece copi il database a mano, porta con te anche `case.db-wal` e
`case.db-shm`: le modifiche più recenti vivono lì finché il database non le
assorbe, e `case.db` da solo ne sarebbe privo. I pulsanti qui sopra esistono
perché tu non debba ricordartelo.

### Ripartire da zero

**Impostazioni → Gestione dei dati** ha tre azzeramenti, ognuno con la sua
conferma. *Svuota la dashboard* cancella immobili e storico ma tiene le
ricerche, e la scansione successiva ricostruisce tutto senza sommergerti di
notifiche. *Azzera gli andamenti* cancella solo lo storico dei grafici.
*Ripristino di fabbrica* riporta tutto a un'installazione nuova. Le impostazioni
di notifica e di accesso non vengono mai toccate, e tutti e tre sono
recuperabili dalla copia salvata subito prima.

---

## Notifiche

Telegram ed email si configurano in **Impostazioni**, con una guida passo passo
accanto a ciascuno. Ogni ricerca sceglie dove mandare i propri avvisi: su uno dei
due, su entrambi o da nessuna parte.

Gli avvisi Telegram portano i pulsanti **⭐ Preferito · 👁️ Visto · 🚫 Nascondi ·
🗺️ Mappa**, così smisti un annuncio dal telefono e ritrovi il risultato nella
dashboard. Non servono porte aperte né un indirizzo pubblico: è il backend a
raccogliere i tocchi attraverso la propria connessione in uscita.

Configurazione, password per le app di Gmail e avvisi sulla salute degli scraper
sono in [notifiche](docs/notifications.md).

---

## La prima scansione è diversa

La prima scansione di una ricerca raccoglie tutto quello che c'è già e lo salva
come punto di partenza. **Non manda nessuna notifica**, altrimenti ti
inonderebbe la chat. Gli avvisi su annunci nuovi e cali di prezzo cominciano
dalla seconda.

---

## Quando una scansione non trova niente

"Non è arrivato niente" ha tre cause, e ognuna chiede una risposta diversa.

**`Nessun risultato`** è una risposta vera: il portale ha risposto e quel giorno
non aveva niente.

**`Non riuscita`** vuol dire che l'indirizzo della ricerca è sbagliato, oppure
che il portale ha cambiato il proprio codice.

**`Bloccata`** vuol dire che il portale ha rifiutato la richiesta invece di
risponderle. Entrambi i siti stanno dietro a un servizio anti-bot, quindi
succede: la ricerca viene ritentata alla scansione dopo e vieni avvisato solo
dopo diversi rifiuti di fila. Una ricerca bloccata lascia quello che vedi
**incompleto, non vuoto**, e il programma te lo scrive sulla riga a cui è
capitato.

Contro un blocco la prima cosa da provare è un cookie `datadome` fresco, che il
programma può prendere da un browser locale. Per Idealista esiste anche un'**API
ufficiale**: con una chiave, le ricerche su quel portale chiedono i dati invece
di leggere le pagine, e non c'è più niente da rifiutare (le ricerche troppo
particolari per l'API continuano a passare dallo scraper). Per Immobiliare non
esiste l'equivalente.

Come distinguere le tre cause, cosa puoi cambiare e quanto costa ogni
cambiamento sono in
[una scansione ha smesso di trovare annunci](docs/scan-returns-nothing.md).

---

## Com'è fatto

**Backend** in Python 3.11–3.14: FastAPI, SQLite, APScheduler.

**Frontend** in React, Vite, TypeScript e Tailwind, con TanStack Query come
strato dati: ogni lettura è una query con la sua chiave, ogni scrittura una
mutation. In pratica, la risposta lenta a un filtro che hai già cambiato non
arriva più a schermo, e una scansione che finisce non ti fa perdere il punto in
cui eri. Pulsanti, campi e finestre sono un unico insieme di primitive costruite
su Radix, quindi ogni dialogo trattiene il fuoco, ogni menu risponde a Esc e
tutto si raggiunge da tastiera. Il bilinguismo passa da un piccolo dizionario
senza dipendenze: una voce presente in una lingua e mancante nell'altra fa
fallire la compilazione.

**Scraper a quattro strategie in cascata**: schema JSON-LD, poi lo stato
`__NEXT_DATA__` incorporato nella pagina, poi una lettura euristica dell'HTML
che non si appoggia alle classi CSS, e come ultima risorsa l'API interna del
portale.

**Scansione da IP domestico**, per scelta. Gli indirizzi dei server in cloud
sono bloccati pesantemente, quello di casa no: è questo che rende le scansioni
possibili.

**Unificazione prudente**: due annunci diventano uno solo se c'è una prova
geografica — coordinate entro 60 metri, oppure stessa via e stesso civico — più
prezzo, locali, piano e metratura compatibili.

---

## Se metti le mani nel codice

I test automatici coprono le quattro strategie di lettura, i casi limite dei
prezzi, le regole di unificazione, lo storico e le routine dello scanner. Girano
tutti offline, senza toccare la rete, quindi passano o falliscono sempre per un
motivo vero.

```bash
# dalla cartella del progetto, una riga alla volta
(cd backend  && .venv/Scripts/python -m pytest)   # il backend
(cd frontend && npm test)                         # la logica del frontend
(cd frontend && npm run e2e)                      # la dashboard in un browser vero
```

La suite nel browser usa il build di produzione contro un backend reale su un
database usa-e-getta. Non apre mai il tuo `case.db`, non occupa la porta 8000 e
non raggiunge la rete. La prima volta serve `npm run e2e:browser` per scaricare
Chromium.

Una suite verde dice che la logica è giusta. Non dice che i portali si leggono
ancora: quello lo può verificare solo una persona, e i controlli da fare prima
di ogni release sono elencati in [manual-tests](docs/manual-tests.md).

Le dipendenze sono bloccate con dei lockfile e si installano con `npm ci` e con
`pip install -r`, mai con `npm install`: come si rigenerano, e le trappole che
nascondono, sono in [dependencies](docs/dependencies.md).

La documentazione tecnica, **in inglese**, è in [`docs/`](docs/):

| Documento | Cosa contiene |
|---|---|
| [architecture](docs/architecture.md) | dove intervenire per ogni tipo di modifica, schema dei dati, ciclo di vita di un immobile, migrazioni, fragilità note |
| [invariants](docs/invariants.md) | le ventinove regole che non devono rompersi, ognuna con la regressione che l'ha resa necessaria |
| [conventions](docs/conventions.md) | come si scrive e come si testa il codice qui |
| [ui](docs/ui.md) | design token, catalogo delle primitive, di cosa si occupa ogni schermata |
| [development-cycle](docs/development-cycle.md) | l'unità di lavoro, i controlli prima di ogni commit, come si taglia una release da un tag |
| [dependencies](docs/dependencies.md) | i lockfile del backend e del frontend, come si rigenerano, le trappole |
| [audit](docs/audit.md) | il controllo di salute dell'intero progetto, ripetibile |
| [manual-tests](docs/manual-tests.md) | i nove controlli che nessun test automatico può fare |
| [roadmap](docs/roadmap.md) | cosa si sa e non è fatto, con il costo di ogni limite ancora in piedi |

---

## Licenza

[MIT](LICENSE). Usalo, modificalo, distribuiscilo: tieni solo la nota di
copyright.

Gli annunci raccolti non sono coperti da quella licenza: appartengono ai portali
da cui arrivano. Le quotazioni OMI appartengono all'Agenzia delle Entrate, che
le fornisce gratuitamente ma non come open data. Nessuno dei due viene
ridistribuito qui, ed è per questo che i riferimenti OMI partono vuoti e sei tu a
importare il tuo download.
