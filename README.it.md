# SudoBat

🇬🇧 **[English version](README.md)**

> **Tuning grafico per-gioco su Batocera, consapevole dell'hardware.** Un gioco crasha o scatta? SudoBat lo riconosce, capisce il perché e ti propone i settaggi giusti per la tua macchina — li applichi con un tasto, dal gamepad.

---

## 🎮 Cosa fa

SudoBat è un'app che gira **dentro Batocera** (come Port in EmulationStation) ed elimina il tuning manuale dei settaggi grafici per-gioco:

- **Traccia ogni lancio** in automatico: gioco, sistema, emulatore, core, durata della sessione
- **Diagnostica i crash**: legge i log dell'emulatore, riconosce i problemi noti (es. driver Vulkan instabile su iGPU Intel) e ti dice la causa probabile in linguaggio umano
- **Propone set grafici su misura** (Massima fluidità / Bilanciato / Qualità), calcolati per il TUO hardware e la pesantezza del gioco — i valori sono quelli veri esposti da Batocera, non numeri inventati
- **Applica con un tasto**: scrive gli override per-gioco in `batocera.conf`, con backup automatico e ripristino sempre disponibile
- **Impara dai risultati reali**: a fine partita ti chiede com'è andata (fluido? scatti? glitch?). I set che funzionano vengono promossi, quelli che ricrashano sconsigliati, e le esperienze buone finiscono in un catalogo che cresce con l'uso
- **Turbo AI opzionale**: per i crash che non riconosce, può interrogare un LLM (Groq, chiave gratuita) e — dopo la tua conferma — trasformare la diagnosi in una regola offline permanente: quel crash non richiederà mai più la rete

Quello che SudoBat **non fa**, detto onestamente:

- **Non misura gli FPS**: si basa su durata della sessione, log di crash e sul tuo giudizio a fine partita. È una scelta: la misura automatica degli FPS è fragile e diversa per ogni emulatore
- **Non cambia emulatore o core**: quello lo decide EmulationStation. Quando è la mossa giusta, te lo consiglia con istruzioni precise, ma il passo lo fai tu
- **Il catalogo parte leggero e migliora giocando**: non c'è un database di migliaia di giochi pre-compilato; la conoscenza si costruisce con le tue partite validate
- **I sistemi 2D leggeri** (NES, SNES, GB/GBA, arcade classico…) non hanno tuning dedicato: girano bene su qualsiasi x86 moderno, non c'è nulla da ottimizzare

---

## 📋 Requisiti

| Cosa | Requisito |
|---|---|
| OS | **Batocera.linux su x86_64** (mini-PC / desktop). Sviluppato e testato su Batocera 43.1 |
| Hardware | CPU Intel/AMD, iGPU o GPU dedicata (la fascia viene rilevata da sola) |
| Dipendenze | **Nessuna da installare**: Python 3, pygame e PyYAML sono già a bordo di Batocera |
| Rete | **Non necessaria** per il funzionamento normale. Serve solo per il turbo AI opzionale |

Testato a fondo su i5-8500 + Intel UHD 630 (lo scenario "iGPU debole", il più delicato). Su altri setup x86 deve funzionare per costruzione — la fascia hardware e i valori dei settaggi vengono letti dalla macchina, non da liste precotte — ma non è stato provato su tutto.

---

## 🚀 Installazione — un solo comando

Dal Batocera (collegati in SSH con `ssh root@batocera.local`, password predefinita `linux`, oppure usa il terminale integrato) lancia:

```bash
curl -L https://raw.githubusercontent.com/masimoneext-sketch/SudoBat/master/install.sh | bash
```

Poi un ultimo passo a mano, una volta sola: in EmulationStation → **Menu → Impostazioni giochi → Aggiorna gamelist** (o riavvia il box). SudoBat compare nel menu **PORTS**.

**Cosa fa lo script** (trasparenza totale — è [`install.sh`](install.sh), leggibile prima di eseguirlo):
1. controlla che sia davvero un Batocera x86_64
2. scarica SudoBat in `/userdata/system/SudoBat` (con git se c'è, altrimenti come archivio)
3. attiva il tracciamento dei lanci (un symlink all'hook ufficiale Batocera — reversibile)
4. esegue il selftest da 23 test per verificare l'installazione (nessuna scrittura sul sistema)
5. registra SudoBat nel menu PORTS, con logo e anteprima animata

**Rilanciare lo stesso comando aggiorna SudoBat** all'ultima versione. E dalla 1.2 non serve nemmeno ricordarselo: SudoBat controlla una volta al giorno se c'e' una release nuova e propone l'aggiornamento in **Impostazioni** — mai automatico, sempre dietro tua conferma.

<details>
<summary>Preferisci fare a mano? I 3 passi equivalenti</summary>

```bash
cd /userdata/system
git clone https://github.com/masimoneext-sketch/SudoBat.git
ln -s /userdata/system/SudoBat/scripts/sudobat-hook.sh /userdata/system/scripts/sudobat-hook.sh
cd /userdata/system/SudoBat && python3 -m tools.register_port
# poi aggiorna la gamelist da ES
```
</details>

Per disinstallare: rimuovi il symlink dell'hook, la voce dal menu PORTS e la cartella — SudoBat non tocca nient'altro del sistema:

```bash
rm /userdata/system/scripts/sudobat-hook.sh /userdata/roms/ports/SudoBat.sh
rm -r /userdata/system/SudoBat
```

---

## 🕹️ Come si usa (il ciclo completo)

1. **Gioca** normalmente da EmulationStation. Se va tutto bene, SudoBat non lo apri nemmeno.
2. Il gioco **crasha o scatta**? Esci e apri **SudoBat** dal menu PORTS.
3. **Diagnosi ultimo lancio**: SudoBat riconosce il gioco (dal serial del disco, non dal nome del file), mostra cosa è successo e i set grafici applicabili — col consigliato marcato ★.
4. **Applica** il set scelto (ti mostra prima esattamente cosa cambia, poi fa backup e scrive).
5. **Rigioca**. Alla riapertura SudoBat ti chiede com'è andata con 4 domande secche (fluido? FPS ok? scatti? glitch?).
6. In base alla risposta: esperienza buona → **salvata in catalogo** (la prossima volta parte già così); ancora problemi → propone il gradino successivo (set più leggero, o cambio core/emulatore con istruzioni).

Tutto si naviga col **gamepad** (o tastiera). Interfaccia in **italiano e inglese** (si cambia in Impostazioni).

### Da terminale (opzionale)

Tutte le funzioni esistono anche come CLI, comoda via SSH:

```bash
cd /userdata/system/SudoBat
python3 -m sudobat.cli profile        # profilo hardware rilevato + fascia
python3 -m sudobat.cli diagnose       # diagnosi dell'ultimo lancio
python3 -m sudobat.cli apply          # fix proposti (dry-run); apply --write N per applicare
python3 -m sudobat.cli restore        # annulla l'ultima modifica (dry-run); --write per farlo
python3 -m sudobat.cli sets ps2 SLUS-205.60   # set generati per un gioco
python3 -m sudobat.cli brain          # turbo AI su un crash sconosciuto (se configurato)
python3 -m sudobat.cli learn          # trasforma la diagnosi AI in regola offline
python3 -m sudobat.cli history ps2 SLUS-205.60  # storico esiti di un gioco
```

### Turbo AI (opzionale) — con la TUA chiave

Il turbo richiede una **chiave API Groq personale**: gratuita, senza carta di credito, ~5 minuti per ottenerla. Deve essere *tua* perché i limiti di utilizzo sono legati al proprietario della chiave — una chiave condivisa si esaurirebbe subito, la tua è più che abbondante per l'uso che ne fa SudoBat (una chiamata per ogni crash sconosciuto).

**📖 Guida passo-passo per utenti non tecnici: [docs/GROQ_SETUP.it.md](docs/GROQ_SETUP.it.md)** — spiega come creare l'account gratuito, generare la chiave e portarla sul box anche senza toccare un terminale (via condivisione di rete di Batocera).

Versione rapida, se hai dimestichezza con SSH:

```bash
cd /userdata/system/SudoBat
python3 -m sudobat.cli key set gsk_LA_TUA_CHIAVE  # valida e salva (permessi 600, gitignorata)
python3 -m sudobat.cli key test                   # chiamata di prova vera: "OK" = turbo pronto
```

La schermata Impostazioni mostra a colpo d'occhio lo stato del turbo (attivo / non configurato). Si accende **solo** per i crash che il motore offline non riconosce. **Trasparenza totale su cosa esce dalla macchina**: la coda del log di crash (~40 righe), il modello di CPU/GPU e il titolo del gioco vengono inviati a Groq. Niente chiave = niente traffico, e l'app funziona identica col solo motore offline. L'AI non applica mai nulla da sola: propone, tu confermi.

---

## 🌍 Conoscenza community (opt-in)

Le installazioni di SudoBat possono aiutarsi a vicenda: quando un set che hai validato come buona esperienza viene condiviso (col tuo consenso) e **almeno 3 installazioni indipendenti** confermano lo stesso set, finisce nel repo pubblico [sudobat-knowledge](https://github.com/masimoneext-sketch/sudobat-knowledge) e ogni SudoBat può scaricarlo — così i nuovi utenti partono con set provati sul campo.

Come funziona il consenso, in totale trasparenza:

- La **prima volta** che validi un set buono, SudoBat chiede una volta sola: condividere anonimamente, sì o no. La scelta viene ricordata ed è cambiabile quando vuoi in Impostazioni (`share on|off` da CLI)
- **Cosa viene inviato** (tutto qui, non c'è altro): id/titolo del gioco, fascia hardware, emulatore/core, i settaggi, i flag esperienza, e un identificativo casuale dell'installazione (uuid, non derivato dal tuo hardware). Mai dati personali, mai percorsi file, mai IP conservati
- **Niente consenso = zero traffico.** L'invio è silenzioso e best-effort; un invio fallito non ti disturba mai
- **Scaricare** la conoscenza community non richiede consenso (sono dati pubblici): `python3 -m sudobat.cli knowledge update` — aggiornata anche dall'installer
- I set community compaiono come opzioni in più marcate "Community (N conferme)"; i tuoi esiti locali le battono sempre

Documento di progetto completo: [KNOWLEDGE_SHARING.md](KNOWLEDGE_SHARING.md).

## 🛡️ Reti di sicurezza

Su un retro-box la config è sacra. Ogni scrittura di SudoBat è blindata:

- **Scrive in un solo file**: `batocera.conf`, e solo override per-gioco (`sistema["rom"].chiave=valore`) — mai le config globali, mai gli ini nativi degli emulatori
- **Chirurgica**: modifica solo le righe interessate; commenti, ordine e il resto del file restano intatti
- **Backup automatico** timestampato prima di ogni scrittura, con rotazione (ultimi 10)
- **Ripristino a un tasto**: Impostazioni → "Ripristina ultimo backup" (e il ripristino stesso è annullabile)
- **Scrittura atomica**: il file non può rimanere a metà nemmeno togliendo la corrente nel momento sbagliato
- **Dry-run di default**: ogni "applica" mostra prima il piano esatto delle modifiche
- Un valore fuori range in `batocera.conf` viene comunque **ignorato da Batocera** (fallback al default): anche il caso peggiore non rompe il sistema

---

## ⚙️ Specifiche tecniche

- **Stack**: Python 3 + pygame (UI) + PyYAML (dati) — tutto stock su Batocera, zero `pip install`
- **Identificazione giochi** robusta ai rinomini: PS2 dal serial in `SYSTEM.CNF` (lettura ISO9660 via `bsdtar`), PSX dal serial dentro i `.chd` (`chdman` + de-interleave settori), Switch dal Title ID osservato nelle cartelle degli emulatori
- **Profiling hardware** dai dati reali del sistema (`batocera-info`, `vulkaninfo`, `batocera-vulkan`): fascia `igpu-weak` / `igpu-strong` / `dgpu-entry` / `dgpu-mid` / `dgpu-high`
- **Set grafici generati**, non hardcodati: le "manopole" e i loro valori vengono letti da `es_features` di Batocera, quindi seguono l'installazione reale (inclusi sistemi add-on come Switch)
- **Diagnosi**: hook ufficiale `gameStart`/`gameStop` + log di lancio ES + log nativi degli emulatori (PCSX2, DuckStation, Ryujinx, famiglia yuzu/eden/citron) + regole YAML per-emulatore
- **Copertura tuning**: PS2, PSX, Switch (diagnosi dedicata); qualunque emulatore con asse di risoluzione in `es_features` ottiene comunque i set generati
- **Apprendimento**: memoria esiti per gioco+set (promozione/bocciatura sul campo) e distillazione AI→regola offline, sempre con conferma umana
- **Footprint**: ~5.000 righe di Python, nessun demone in background (l'hook è uno script di poche righe che scatta solo al lancio/stop di un gioco), stato in `state/` dentro la cartella dell'app

### Verifica dell'installazione

```bash
python3 -m sudobat.selftest       # 26 test del motore (config, hook, apprendimento, condivisione) — nessuna scrittura sul sistema
python3 -m sudobat.ui --selftest  # test dell'interfaccia, headless
```

---

## 📄 Licenza

SudoBat è rilasciato sotto **[PolyForm Noncommercial License 1.0.0](LICENSE.md)**:

- ✅ **Libero per uso personale e ogni altro uso non commerciale** — il tuo retro-box di casa, sperimentazione, condivisione con gli amici
- ❌ **L'uso commerciale è riservato all'autore**: includere SudoBat in dispositivi in vendita, distribuzioni a pagamento o qualunque uso che generi ricavi richiede una licenza commerciale separata — contatta l'autore via GitHub

I contributi sono benvenuti secondo i termini in [CONTRIBUTING.md](CONTRIBUTING.md) (firma DCO + concessione di rilicenza).

`Required Notice: Copyright © 2026 Marco Simone (https://github.com/masimoneext-sketch/SudoBat)`
