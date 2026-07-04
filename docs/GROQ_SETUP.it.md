# Come ottenere e installare la tua chiave API Groq (guida per tutti)

🇬🇧 **[English version](GROQ_SETUP.md)**

Il **Turbo AI** di SudoBat è opzionale: analizza i crash che il motore offline non riconosce ancora. Per usarlo serve una **chiave API personale di Groq** — è **gratuita**, si ottiene in 5 minuti e **non richiede carta di credito**.

> **Perché una chiave "personale"?** Le chiavi API hanno limiti di utilizzo legati a chi le possiede. Se tutti usassero la stessa chiave, i limiti finirebbero subito. Con la TUA chiave i limiti sono tutti tuoi — e per l'uso che ne fa SudoBat (una chiamata solo quando un gioco crasha in modo sconosciuto) il piano gratuito è più che abbondante.

---

## Parte 1 — Ottenere la chiave (dal PC o dal telefono)

1. Apri il browser e vai su **https://console.groq.com**
2. Clicca **Sign up** (registrati). Puoi usare il tuo account Google/GitHub oppure un'email qualsiasi — se usi l'email, riceverai un messaggio di conferma: aprilo e clicca il link.
3. Una volta dentro, nel menu cerca **API Keys** e aprilo.
4. Clicca **Create API Key**. Come nome scrivi quello che vuoi, ad esempio `SudoBat`.
5. Ti viene mostrata la chiave: una scritta lunga che **inizia con `gsk_`**.
   **⚠ Copiala SUBITO** (pulsante di copia accanto): per sicurezza Groq te la mostra **solo questa volta**. Se la perdi non è un dramma — ne crei un'altra allo stesso modo.
6. Incollala temporaneamente in un posto sicuro (una nota sul telefono, un file di testo). È come una password: **non pubblicarla e non condividerla**.

Fatto. Ora va portata sul Batocera.

---

## Parte 2 — Installare la chiave su Batocera (scegli la strada più comoda)

### Strada A — Dal PC, senza terminale (consigliata per chi è alle prime armi)

Batocera condivide le sue cartelle sulla rete di casa:

1. Accendi il Batocera. Dal PC (stessa rete Wi-Fi/cavo) apri Esplora File:
   - **Windows**: nella barra dell'indirizzo scrivi `\\BATOCERA\share` e premi Invio
   - **Mac**: Finder → Vai → Connetti al server → `smb://batocera.local/share`
2. Entra nella cartella **`system`** → **`SudoBat`** → **`state`** (se `state` non esiste, creala).
3. Crea lì dentro un file di testo chiamato esattamente **`groq_key.txt`**.
4. Aprilo, incolla **solo la chiave** (la riga che inizia con `gsk_`, niente spazi né altre righe) e salva.

Il file `groq_key.txt` è solo un punto di consegna: al primo avvio di SudoBat (o al primo riavvio del box) viene importato in uno store nascosto (`state/.groq_key`), cancellato, e lo store viene reso **invisibile e inaccessibile dalla rete** (veto Samba, riapplicato a ogni boot dal servizio `sudobat_smbguard`). Finché il file `groq_key.txt` esiste, chiunque sia sulla tua rete di casa può leggerlo: la condivisione di Batocera è aperta agli ospiti. Se vuoi chiudere subito la finestra, avvia SudoBat una volta o dai il comando della Strada B.

### Strada B — Con un comando (via SSH o dal terminale del Batocera)

Se sai collegarti in SSH (`ssh root@batocera.local`, password predefinita `linux`):

```bash
cd /userdata/system/SudoBat
python3 -m sudobat.cli key set gsk_LA_TUA_CHIAVE
```

Il comando controlla che la chiave sia scritta bene, la salva nello store nascosto e attiva subito il veto SMB.

### Strada C — Variabile d'ambiente (per chi lavora da terminale)

`GROQ_API_KEY` ha la precedenza su tutto e non scrive nulla su disco: utile per sessioni SSH o prove. Attenzione però: su Batocera qualunque file persistente in cui potresti metterla (`custom.sh`, profili, script) vive comunque sotto `/userdata`, cioè dentro la stessa condivisione di rete — non è più sicura dello store con veto, è solo un'alternativa.

---

## Parte 3 — Verificare che funzioni

Dal terminale (serve la rete):

```bash
python3 -m sudobat.cli key         # mostra lo stato: configurata o no
python3 -m sudobat.cli key test    # fa una chiamata di prova vera a Groq
```

Se `key test` risponde `OK: chiave valida`, il turbo è pronto. In alternativa, apri SudoBat → **Impostazioni**: la riga **Turbo AI (Groq)** deve dire *attivo*.

Da questo momento, quando un gioco crasha in un modo che SudoBat non conosce, nella schermata Diagnosi comparirà l'opzione per chiedere al turbo (tasto SELECT).

---

## Domande frequenti

**Quanto costa?** Nulla. Il piano gratuito di Groq ha limiti di richieste al minuto/giorno, ma SudoBat fa **una** chiamata solo quando c'è un crash sconosciuto — e grazie alla distillazione ogni crash si paga una volta sola, poi viene riconosciuto offline.

**Dove finisce la mia chiave?** Solo sul tuo Batocera, nello store nascosto `state/.groq_key` (escluso dal repository, permessi 600). Onestà dovuta: i permessi Unix da soli NON proteggono dalla condivisione di rete di Batocera, che è aperta agli ospiti e serve i file come root — per questo SudoBat mette il file a veto in Samba (servizio `sudobat_smbguard`, attivo a ogni boot), rendendolo invisibile e illeggibile dalla rete. La chiave non viene inviata a nessuno tranne che a Groq per autenticare le chiamate.

**Cosa viene inviato a Groq?** Solo quando usi il turbo: la coda del log di crash (~40 righe), il modello di CPU/GPU e il titolo del gioco. Niente chiave = niente traffico.

**Come la rimuovo?** `python3 -m sudobat.cli key remove`, oppure cancella il file `state/.groq_key`. SudoBat continua a funzionare col solo motore offline.

**Ho perso la chiave / l'ho pubblicata per errore.** Vai su console.groq.com → API Keys, elimina quella vecchia (Revoke) e creane una nuova. Poi ripeti la Parte 2.
