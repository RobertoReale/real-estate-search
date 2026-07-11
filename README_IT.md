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
* **Velocità di Mercato e Agenzie (`market_velocity`):** Monitoraggio dei tempi medi di permanenza sul mercato degli immobili in una zona e del tasso di sconti applicato dalle singole agenzie.
* **Importazione Storica Email (`IMAP Import`):** Ti permette di collegare in sola lettura la tua casella di posta per importare anni di vecchi alert email e ricostruire lo storico dei prezzi prima di iniziare a usare l'applicazione.
