# Real Estate Search (Piattaforma Locale per l'Acquisto e Affitto Casa)

[Read the documentation in English](README.md)

Piattaforma software locale (PC Windows / Linux / Raspberry Pi) che monitora e aggrega annunci immobiliari (vendita e affitto) da **Immobiliare.it** e **Idealista**, deduplica gli annunci identici pubblicati da agenzie diverse, scarta gli immobili indesiderati (es. nuda proprietà, piani terra, aste giudiziarie) e invia notifiche in tempo reale via **Telegram e/o Email**.

A differenza dei portali tradizionali, che cancellano lo storico o nascondono i dati per proteggere i venditori, questo software salva tutto in un **database SQLite locale** (`case.db`), fungendo da **macchina del tempo e assistente di negoziazione per l'acquirente**.

---

## Perché questo software è diverso

I portali immobiliari vivono delle provvigioni delle agenzie. Questo software lavora al 100% dalla parte di chi compra o cerca casa:

1. **Radar del "Vero Affare" & Indice di Congruità:** Ogni annuncio viene confrontato con il prezzo/m² mediano del micro-quartiere specifico per la stessa tipologia e piano (`pricing_stats.py`). Se un immobile è prezzato al di sotto della media locale o se l'agenzia ha uno storico di forti sconti nel tempo (`market_velocity.py`), il sistema calcola e mostra il target reale di negoziazione.
2. **Memoria Storica Fantasma (`Ghost Price Tracking`):** Se una casa non si vende per mesi a €420.000, l'agenzia cancella l'annuncio e lo ripubblica come "Nuovo" a €389.000 cambiando le foto. I portali azzerano il contatore dei giorni. Il nostro motore (`deduplicator.py`) incrocia le coordinate, la metratura e i locali con lo storico locale e ti avvisa: `[IMMOBILE RICICLATO] precedentemente sul mercato per 160 giorni a un prezzo superiore (-9.5%)`. Un'arma negoziale imbattibile durante le visite.
3. **Analisi Criticità & Costo Reale (`TCO Audit`):** Estrazione automatica di criticità legali o strutturali dal testo dell'annuncio (nuda proprietà, immobile locato, spese condominiali elevate, assenza di ascensore ai piani alti) e calcolo del costo mensile totale effettivo (Rata Mutuo + Spese Condominiali + Fondo Ristrutturazione).
4. **Zero Cloud, 100% Privacy:** Tutti i dati, le ricerche e le preferenze restano sul tuo computer locale. Nessuna abbonamento o API esterna a pagamento richiesta.

---

## Avvio Rapido (Quick Start)

### Windows
Fai doppio clic su **`start.bat`**:
- Al primo avvio installa automaticamente tutte le dipendenze (richiede Python 3.11+ e Node.js 18+).
- Avvia il server backend (`http://localhost:8000`) e la dashboard frontend (`http://localhost:5173`).
- Apre automaticamente l'interfaccia nel browser predefinito.

### Linux / Raspberry Pi
Apri il terminale nella cartella del progetto ed esegui:
```bash
chmod +x start.sh
./start.sh
```
- Installa le dipendenze e avvia entrambi i servizi in parallelo.
- Rende la dashboard accessibile da qualsiasi dispositivo connesso alla rete locale all'indirizzo `http://<IP_DEL_RASPBERRY>:5173`.

---

## Accesso da Smartphone e Controllo da Remoto

Lo scraper deve girare sul PC locale (i portali si fidano degli IP residenziali di casa mentre bloccano i server cloud), ma la dashboard è perfettamente ottimizzata per essere consultata e controllata comodamente dallo smartphone (Android o iOS).

Esegui **`serve.bat`** al posto di `start.bat`. Questo comando compila l'interfaccia React ed eroga dashboard e API su una singola porta (`8000`), permettendo di aprire l'indirizzo dal telefono e selezionare **"Aggiungi a schermata Home"** per avere un'applicazione a tutti gli effetti sul cellulare.

**Accesso da fuori casa (senza esporre il PC su Internet):** installa [Tailscale](https://tailscale.com) gratis sia sul PC che sul telefono ed effettua l'accesso allo stesso account. `serve.bat` rileverà automaticamente l'IP Tailscale privato (`100.x.y.z`) e si collegherà solo a quello: la dashboard sarà accessibile ovunque dal tuo smartphone in totale sicurezza senza configurare porte sul router.

> **Nota di Sicurezza:** L'API non possiede password di autenticazione. Per questo motivo il bind predefinito di `serve.bat` ascolta esclusivamente sul tuo indirizzo privato Tailscale. Non esporre mai la porta 8000 direttamente su Internet.

---

## Esecuzione 24/7 su Windows (senza finestra aperta)

Le scansioni automatiche, gli snapshot per i grafici dei prezzi e le notifiche
funzionano **solo mentre l'app è in esecuzione**. Con `start.bat`/`serve.bat`
questo significa tenere aperta (minimizzata) la finestra del terminale. Se non
hai ancora un Raspberry Pi, puoi far girare l'app in background sul PC Windows,
**senza alcuna finestra**.

Qualunque opzione scegli, **compila prima la dashboard una volta** così il
backend la serve su un'unica porta: esegui `serve.bat` una volta (Ctrl+C dopo
"Building the frontend"), oppure `cd frontend && npm run build`. Poi apri
**http://localhost:8000** e aggiungilo ai preferiti. Tutto resta su `127.0.0.1`:
l'API non ha password, quindi non va esposta.

Tre opzioni, dalla più semplice alla più robusta:

| Opzione | Cosa fa | Compromesso |
|---|---|---|
| **A — Avvio all'accesso (nascosto)** | Un collegamento a `run-hidden.vbs` nella cartella Esecuzione automatica avvia il backend, nascosto, a ogni login. | La più semplice. Parte solo dopo il login; nessun riavvio automatico in caso di crash. |
| **B — Utilità di pianificazione (nascosto)** | Un'attività pianificata esegue `run-hidden.vbs` "All'accesso", con più controllo (ritardo, esecuzione a batteria, ecc.). | Sempre legata al login, ma più configurabile della A. |
| **C — Servizio Windows (NSSM)** ⭐ | `install-service.bat` registra il backend come vero servizio: parte all'**accensione** (prima del login), **si riavvia da solo se crasha**, log in `backend/service.log`. | La più simile a un dispositivo sempre acceso. Setup una tantum, richiede un piccolo download. |

**Opzione A — Avvio all'accesso.** Premi `Win+R`, scrivi `shell:startup`,
Invio. Nella cartella che si apre: tasto destro → *Nuovo → Collegamento* e
puntalo a `run-hidden.vbs` nella cartella del progetto. Fatto: parte in
silenzio a ogni accesso. (Per fermarlo: elimina il collegamento e chiudi
`pythonw.exe` da Gestione attività.)

**Opzione B — Utilità di pianificazione.** Apri *Utilità di pianificazione* →
*Crea attività* → attivazione *All'accesso*, azione *Avvio programma* →
`wscript.exe` con argomento il percorso completo di `run-hidden.vbs`.

**Opzione C — Servizio Windows (consigliata).**
1. Scarica **NSSM** da <https://nssm.cc/download> e copia `win64\nssm.exe` nella
   cartella del progetto (accanto a `install-service.bat`).
2. Tasto destro su **`install-service.bat`** → *Esegui come amministratore*.
   Compila il frontend se serve, registra il servizio `RealEstateSearch`
   (avvio e riavvio automatici) e lo avvia.
3. Apri **http://localhost:8000**.

Gestione da terminale amministratore: `nssm restart RealEstateSearch` (dopo aver
aggiornato il codice), `nssm stop RealEstateSearch`, `nssm edit RealEstateSearch`
(interfaccia grafica). Per rimuoverlo: **`uninstall-service.bat`** da
amministratore — database e impostazioni restano intatti.

> Note per tutte e tre: non lanciare `start.bat` in contemporanea (userebbe la
> stessa porta 8000 — ferma prima l'avvio automatico). Dopo aver cambiato il
> codice, ricompila il frontend e riavvia. Il grab automatico del cookie
> DataDome col browser è interattivo, quindi da servizio non funziona: incolla
> il cookie a mano (le scansioni normali non ne risentono).

---

## Come Utilizzarlo

1. **Crea l'URL di Ricerca:** Vai su Immobiliare.it o Idealista.it dal tuo browser. Seleziona la città o disegna un'area sulla mappa (`poligoni disegnati a mano`), imposta fasce di prezzo, numero locali, presenza balconi/ascensore e qualsiasi altra opzione del portale, quindi **copia l'URL dalla barra degli indirizzi**.
   - *Nota:* Qualsiasi filtro tu imposti sul portale viene compreso e monitorato automaticamente dall'applicazione, perché lo scraper utilizza direttamente quell'URL come sorgente.
   - *Assistente in Lingua Naturale:* Se preferisci, puoi descrivere ciò che cerchi in italiano direttamente nell'interfaccia (*"trilocale a Milano sotto i 300k, zona Navigli o Isola"*) e l'assistente integrato genererà automaticamente gli URL per entrambi i portali.
2. **Aggiungi il Profilo:** Nella dashboard clicca su **"+ Add search profile"** (Aggiungi profilo di ricerca), assegna un nome, incolla l'URL copiato e clicca **"Save profile"**.
3. **Avvia la Scansione:** Clicca su **"Start Scan Now"** per avviare una ricerca immediata, oppure lascia che lo scheduler automatico controlli i portali in background (ogni 30/60/120 minuti).
4. **Analizza gli Annunci Unified:** Le schede unificate mostreranno un badge viola (es. *"2 merged listings"*) quando lo stesso immobile pubblicato da agenzie o portali diversi viene accorpato con successo.
5. **Cura del Database (Nascondi o Ripristina):** Cliccando su un immobile puoi nasconderlo (`Hide property`) per escluderlo definitivamente da future notifiche. Se cambi idea, puoi sempre ripristinarlo filtrando gli immobili con stato `Discarded` nella barra superiore.

---

## Funzionalità Avanzate

* **Mappa Interattiva (`Map View`):** Visualizza tutti gli immobili su mappa OpenStreetMap ad alta precisione per valutare la vicinanza ai mezzi pubblici o ai servizi.
* **Analisi Prezzo al m² (`pricing_stats`):** Calcolo statistico della mediana al metro quadro del quartiere specifico.
* **Andamento Storico dei Prezzi (`Price Trends`):** Grafico di come la mediana €/m² si è mossa nel tempo nelle zone che monitori. L'app registra una mediana per zona al giorno, quindi la linea compare dopo qualche giorno di scansioni e riflette il *tuo* campione (gli annunci osservati), non l'intero mercato.
* **Deal Score (Congruità del Prezzo):** Combina lo scarto €/m² rispetto alla mediana di zona con gli indizi sullo stato dell'immobile letti dal testo (*da ristrutturare* abbassa il punteggio, *ristrutturato / classe A* lo alza) in un unico valore — positivo = sotto mercato. Gli annunci sotto-mercato mostrano un badge **🎯 below market**, il dettaglio propone un range di offerta basato sullo sconto tipico dell'agenzia, e il flag arriva anche nelle notifiche Telegram/email. È un punto di partenza per il tuo giudizio, non una perizia.
* **Dossier Condivisibili (Export Offline):** I pulsanti **Export** nella barra dei filtri scaricano gli immobili attualmente visualizzati (applica i filtri o spunta *Preferiti* prima) come **dossier HTML** autonomo, report **Markdown** o foglio **CSV**, completi di prezzi, storico dei ribassi e Deal/Match Score. Un unico file offline da inviare via chat o email a partner, familiari o agenti, senza dare a nessuno accesso alla dashboard o al database.
* **Punteggio di Compatibilità (`Smart Match Score`):** Definisci una volta la tua "casa ideale" nelle Impostazioni (budget, locali/superficie/piano minimi, caratteristiche desiderate come *balcone* o *ascensore*, zone preferite) e ogni scheda mostra una **percentuale di compatibilità**. Contano solo i criteri che imposti, tutto in locale; puoi ordinare la griglia per **🎯 Miglior corrispondenza**.
* **Velocità di Mercato e Agenzie (`market_velocity`):** Monitoraggio dei tempi medi di permanenza sul mercato degli immobili in una zona e del tasso di sconti applicato dalle singole agenzie.
* **Importazione Storica Email (`IMAP Import`):** Ti permette di collegare in sola lettura la tua casella di posta per importare anni di vecchi alert email e ricostruire lo storico dei prezzi prima di iniziare a usare l'applicazione. Puoi anche attivare una **ri-scansione automatica** della casella (opzionale, dalle Impostazioni): i nuovi annunci ricevuti via email vengono aggiunti in silenzio alla lista di revisione, senza notifiche e senza entrare nella dashboard finché non li accetti.
* **Cookie DataDome automatico:** In Impostazioni puoi far sì che l'app apra un browser locale e recuperi da sola il cookie `datadome` (niente copia/incolla). Spuntando *"Refresh automatically before each scan"* il cookie viene rinfrescato prima di ogni scansione **e** al volo se il pulsante *"Check if still online"* dell'import email viene bloccato a metà: l'app inserisce un cookie fresco e prosegue invece di fermarsi (con un limite di un paio di tentativi, così non insiste mai). Richiede l'installazione una tantum di Playwright nella venv del backend.
