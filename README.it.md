# Ricerca Immobili

Applicazione locale (PC/Raspberry Pi) che monitora annunci immobiliari — vendita
e affitto — su **Immobiliare.it** e **Idealista**, elimina i duplicati dello
stesso immobile pubblicato da più agenzie, filtra per parole chiave e avvisa su
**Telegram e/o Email** quando compare qualcosa di nuovo o cambia prezzo.

Tutto gira in locale: nessun servizio cloud obbligatorio, nessun abbonamento,
dati salvati in un semplice file SQLite sul tuo PC.

## Avvio rapido

**Windows**: doppio clic su `scripts\windows\start.bat`. Installa le dipendenze
al primo avvio, apre backend e frontend e mostra la dashboard nel browser.

**Linux / Raspberry Pi**:
```bash
chmod +x scripts/linux/start.sh
./scripts/linux/start.sh
```

Per usare la dashboard anche da telefono, o per farla girare in background
senza tenere una finestra aperta, vedi le sezioni dedicate in `README.md`
(in inglese, più dettagliato e aggiornato ad ogni funzionalità).

## Come si usa, in breve

1. Su Immobiliare o Idealista imposta la ricerca che vuoi (città, zona, prezzo,
   filtri) e copia l'URL dalla barra degli indirizzi.
2. Nella dashboard, **"+ Add search profile"**: incolla l'URL, dai un nome,
   salva.
3. Avvia una scansione (manuale o automatica) e gli annunci trovati compaiono
   nella griglia, con i duplicati già uniti.
4. Da ogni scheda puoi nascondere un annuncio, segnarlo come venduto/affittato,
   aggiungere tag, vedere la posizione sulla mappa e altro.

La prima scansione di una ricerca non invia notifiche (serve solo a costruire
la base dati): gli avvisi arrivano dalla seconda scansione in poi.

## Perché un secondo file

Questo file è una guida rapida in italiano, pensata per restare valida a lungo
e non richiedere aggiornamenti ad ogni nuova funzione. La documentazione
completa e sempre aggiornata — ogni funzione, ogni impostazione — resta in
`README.md` (inglese).
