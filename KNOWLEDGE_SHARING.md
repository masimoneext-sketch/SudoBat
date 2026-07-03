# SudoBat — Conoscenza condivisa (spec approvata da Marco il 2026-07-03)

> **STATO: IMPLEMENTATA (v1+v2, 2026-07-03).** Client: `share.py` + `knowledge.py`,
> consenso in UI, riga Impostazioni, CLI `share`/`knowledge`, 3 selftest (26/26).
> Server: collettore blindato su VPS (staging LIVE su
> `sudobat-knowledge.staging.marcosimone.tech`, prod su porta 3031 in attesa del
> record DNS `sudobat-knowledge` → 72.62.156.86), publisher a quorum 3, repo
> pubblico `masimoneext-sketch/sudobat-knowledge` creato. Endpoint prod (default
> nel client): `https://sudobat-knowledge.marcosimone.tech/api/v1/sets`.

> Obiettivo: i set validati "buoni" dagli utenti (con consenso) popolano una knowledge
> base pubblica su GitHub; ogni SudoBat può scaricarla e partire già "esperto".
> Il cold start del catalogo diventa effetto rete. Design deciso con Marco:
> **opt-in esplicito una volta sola, poi tutto automatico**. MAI invio silenzioso.

## Princìpi non negoziabili

1. **Opt-in prima di qualunque invio.** Nessun byte parte prima del "Sì". Il "No" è
   permanente (ri-attivabile solo dall'utente in Impostazioni).
2. **Offline-first invariato**: senza rete o senza consenso il tool funziona identico.
3. **Local-first trust**: gli esiti LOCALI dell'utente battono sempre la community
   nel rerank. La community suggerisce, il campo dell'utente decide.
4. **Trasparenza totale**: payload documentato qui e nel README pubblico; il codice
   di invio è leggibile nel repo pubblico.

## 1. Opt-in UX (client)

- **Quando**: alla PRIMA validazione di un set buono (flusso flags → `mv.kind == "good"`),
  prima del flash di conferma. Una sola volta nella vita dell'installazione.
- **Copy IT** (EN speculare in i18n):
  > **Aiuta gli altri giocatori?**
  > Vuoi condividere anonimamente i set che funzionano, per aiutare gli altri utenti?
  > Verranno inviati solo: gioco, fascia hardware, emulatore, settaggi, e un
  > identificativo casuale dell'installazione. Mai dati personali.
  > [ Sì, condividi ]  [ No ]
- **Stato**: `state/share_prefs.json` → `{"consent": "yes"|"no", "asked_at": ..., "install_id": "<uuid4>"}`.
  `install_id` = UUID casuale generato alla prima risposta (serve al quorum server-side;
  NON derivato dall'hardware). Riga in Impostazioni: "Condivisione set: attiva/disattivata"
  (riga ATTIVA, toggle con conferma).
- Se consenso = yes: ogni futura validazione "good" accoda l'invio, **senza più chiedere**.

## 2. Payload (client → collettore)

`POST https://sudobat-knowledge.marcosimone.tech/api/v1/sets` — JSON, cap 4 KB:

```json
{
  "schema": 1,
  "install_id": "uuid4",
  "sudobat_version": "1.0",
  "system": "ps2",
  "game_id": "SLUS-205.60",
  "game_title": "Grand Theft Auto: San Andreas",
  "tier": "igpu-weak",
  "emulator": "pcsx2",
  "core": "pcsx2",
  "settings": {"pcsx2_gfxbackend": 12, "pcsx2_resolution": 2},
  "flags": {"fluido": true, "fps_ok": true, "scatti_concitate": false, "glitch": false}
}
```

Client: coda locale `state/share_queue.json` (append alla validazione, invio best-effort
con retry al prossimo avvio; fallimenti SILENZIOSI — mai disturbare l'utente per la
telemetria). Solo stdlib (urllib), timeout corto, mai bloccante per la UI.

## 3. Collettore (VPS — layer /srv, pattern portali standard)

- Node.js o Python minimale, porta dedicata, Traefik `sudobat-knowledge.marcosimone.tech`,
  ufw bridge, PM2. DB SQLite `submissions` (payload + received_at + ip_hash effimero
  SOLO per rate-limit, mai persistito oltre 24h → GDPR-friendly, niente IP a riposo).
- **Validazione all'ingresso** (rifiuto muto, HTTP 204 comunque — niente oracle per abusi):
  schema esatto, chiavi/valori settings contro whitelist `es_features` (dump statico
  aggiornato dal repo), stringhe cap length, rate-limit per IP e per install_id.
- **Quorum**: un (system, game_id, tier, emulator, settings normalizzati) diventa
  `community-validated` con ≥ **3 install_id distinti** con flags "good". Sotto quorum
  resta in attesa, invisibile al pubblico.
- **Publisher**: job che committa i promossi nel repo pubblico della conoscenza
  (bot dedicato, token SOLO sul VPS): `masimoneext-sketch/sudobat-knowledge`,
  YAML per sistema, stesso schema del catalogo + campo `confirmations: N` e
  `source: community`.

## 4. Distribuzione della conoscenza (repo pubblico → client)

- Repo pubblico `sudobat-knowledge` (licenza dati: CC BY-NC 4.0, coerente con PolyForm).
- Client: comando `python3 -m sudobat.cli knowledge update` (+ voce Impostazioni):
  scarica il tarball del repo (codeload, niente git richiesto), valida YAML, scrive in
  `sudobat/data/community/` (NAMESPACE SEPARATO dal catalogo locale — mai mescolare).
- UI: set community marcati "community (N conferme)"; `tuning.profiles_for` li inserisce
  DOPO l'eventuale validato locale; `outcomes.rerank` resta l'autorità finale.
- Anche `install.sh` aggiorna la conoscenza a ogni run (se opt-in... no: il DOWNLOAD è
  innocuo e non richiede consenso — solo l'UPLOAD è dietro opt-in).

## 5. Fasi di costruzione

- **v1 (client-only, subito possibile)**: opt-in UX + coda locale + comando `export`
  che genera il file YAML del contributo → PR manuale al repo knowledge. Zero infra.
  Serve a validare formato e interesse.
- **v2 (collettore VPS)**: endpoint + quorum + publisher bot + `knowledge update`.
  Da costruire quando i numeri del rilascio lo giustificano (≥ qualche decina di
  utenti attivi, altrimenti il quorum a 3 non scatta mai).
- **v3 (rifiniture)**: badge nel README ("community knowledge: N giochi"), notifica
  in UI "nuova conoscenza disponibile".

## 6. Note legali/privacy (già decise)

- Consenso esplicito, revocabile, documentato — GDPR ok (dati tecnici + uuid casuale,
  IP mai persistito).
- README pubblico: sezione "Community knowledge" con elenco esatto dei dati inviati
  (stessa lista della schermata di consenso).
- I contributi dati entrano nella knowledge base di proprietà di Marco (nota nel
  consenso implicita via licenza repo dati; per i DATI il copyright è debole, il
  valore sta nell'aggregato e nel quorum — che vive sul collettore).

## Divisione lavoro proposta

- **Fratello (Batocera)**: lato client — opt-in UX, share_prefs, coda, `export`,
  `knowledge update`, marcatura community in UI (ha la macchina vera per testare).
- **Neo (VPS)**: collettore, quorum, publisher bot, repo `sudobat-knowledge`, Traefik/PM2.
- Contratto tra i due = QUESTO documento (payload §2 e formato YAML §4 sono l'interfaccia).
