# SudoBat — Schema del database di preset/regole (bozza decisa)

> Definisce come è strutturata la "conoscenza" che SudoBat usa per diagnosticare un crash/scatto e proporre un fix (file YAML in `sudobat/data/`). Primi sistemi coperti: **PS2**, **Switch** e **PSX**. Schema definito il 2026-07-02.

## Concetto

Due tipi di conoscenza, separati:

1. **Catalogo giochi per sistema** (`systems/ps2.yaml`, `systems/switch.yaml`): per ogni gioco conosciuto, quanto è pesante e quali impostazioni usare per fascia hardware.
2. **Regole diagnostiche per emulatore** (`diagnostics/pcsx2.yaml`, `diagnostics/switch.yaml`): pattern di sintomo/errore → causa probabile → fix, non legate a un gioco specifico (si applicano a qualsiasi gioco su quell'emulatore).

Alla diagnosi, SudoBat incrocia: ultimo gioco lanciato (dall'hook `gameStart`/`gameStop`, vedi CONVERSATION.md) → lo cerca nel catalogo (se conosciuto, propone il preset per la fascia hardware rilevata) → legge il log dell'emulatore → controlla le regole diagnostiche generiche di quell'emulatore → propone il fix più specifico disponibile.

## Identificazione del gioco

Non si usa il nome del file (fragile: cambia con dump/regione/versione). Si usa un ID canonico, con approccio diverso per sistema perché il formato del rom è diverso:

- **PS2**: il **serial** (es. `SLUS-205.60`), letto dal file `SYSTEM.CNF` dentro il filesystem ISO9660 dell'immagine (riga tipo `BOOT2 = cdrom0:\SLUS_205.60;1`). Nessuna cifratura, nessuna chiave necessaria — basta un lettore ISO9660 minimo.
- **Switch**: il **Title ID** (16 caratteri esadecimali). Non lo si estrae leggendo il file `.xci` grezzo (è dentro un container cifrato NCA/HFS0 — lavoro non banale). Si sfrutta invece il fatto che **gli emulatori stessi creano una cartella con quel nome** dopo il primo lancio, per la loro shader cache/salvataggi: `/userdata/system/configs/Ryujinx/games/<titleid>/`, `/userdata/system/configs/yuzu/shader/<titleid>/` (yuzu = cartella condivisa da eden/citron). Al primo `gameStart` di un gioco Switch mai visto, SudoBat osserva quale cartella titleid è stata appena creata/toccata nella config dell'emulatore usato e la associa al file rom lanciato.

## Fasce hardware (confermate)

```
igpu-weak     # iGPU integrata debole, nessuna GPU dedicata (es. questa macchina: Intel UHD 630)
igpu-strong   # iGPU integrata potente, nessuna GPU dedicata (es. Iris Xe, AMD 780M/880M)
dgpu-entry    # GPU dedicata fascia bassa (es. GTX 1050/1650, RX 560/6400)
dgpu-mid      # GPU dedicata fascia media
dgpu-high     # GPU dedicata fascia alta
```
Rilevate confrontando l'output di `batocera-info`/`batocera-vulkan` (modello GPU, presenza GPU discreta via `has_discrete()`) contro una piccola lista di modelli noti — criteri di match esatti da definire in fase di sviluppo, non bloccanti per lo schema.

## Classi di "heaviness" (confermate)

```
light       # es. GBC, MAME/arcade — tuning quasi ininfluente
medium
heavy       # es. la maggior parte dei PS2 3D installati (GTA, Tomb Raider, NFS)
very_heavy  # es. Switch open-world recenti (Zelda TOTK/BOTW, Mario Odyssey)
```

## Esempio — `systems/ps2.yaml`

```yaml
games:
  SLUS-205.60:   # serial reale da estrarre dall'ISO — qui segnaposto illustrativo
    title: "Grand Theft Auto: San Andreas"
    aliases_filename:
      - "Grand Theft Auto - San Andreas (Europe, Australia) (En,Fr,De,Es,It) (v2.01).iso"
    heaviness: heavy
    presets:
      igpu-weak:
        pcsx2_gfxbackend: 14        # Vulkan
        pcsx2_resolution: 2          # 2x nativa
        pcsx2_anisotropic_filtering: 0
      dgpu-mid:
        pcsx2_resolution: 4
        pcsx2_anisotropic_filtering: 8
    known_issues:
      - symptom: "crash nei primi 10s con Vulkan"
        cause: "driver iGPU Intel instabile con Vulkan su alcune scene GTA"
        fix: { pcsx2_gfxbackend: 12 }   # fallback OpenGL
```

## Esempio — `systems/psx.yaml`

Stesso pattern esatto di PS2 (identificazione via `SYSTEM.CNF` in chiaro nell'ISO9660, emulatore `duckstation`). Chiavi verificate in `es_features.cfg`: `duckstation_gfxbackend` (Vulkan/OpenGL/Software), `duckstation_resolution_scale` (1×–16×, da 320×240 nativa a 5120×3840), più `duckstation_texture_filtering`, `duckstation_antialiasing`, `duckstation_pgxp` (corregge il "wobble" dei poligoni, tipico artefatto PS1), `duckstation_widescreen_hack`.

```yaml
games:
  SCES-00344:   # Crash Bandicoot (Europe) — serial reale, letto da SYSTEM.CNF sull'ISO installata
    title: "Crash Bandicoot"
    aliases_filename:
      - "Crash Bandicoot (Europe).chd"
    heaviness: medium
    presets:
      igpu-weak:
        duckstation_gfxbackend: OpenGL
        duckstation_resolution_scale: "3"     # 720p, buon compromesso su iGPU debole
        duckstation_pgxp: true                 # corregge wobble poligoni, costo prestazionale basso
      igpu-strong:
        duckstation_resolution_scale: "5"      # 1080p
      dgpu-mid:
        duckstation_resolution_scale: "9"      # 4K
    known_issues:
      - symptom: "wobble/tremolio dei poligoni, texture che 'nuotano'"
        cause: "artefatto nativo PS1 (mancanza di correzione prospettica), non un problema hardware"
        fix: { duckstation_pgxp: true }

  BUST-A-GROOVE-SERIAL:   # placeholder — serial da estrarre da SYSTEM.CNF al primo scan
    title: "Bust-A-Groove"
    aliases_filename:
      - "Bust-A-Groove (Europe) (En,Fr,De,Es,It).chd"
    heaviness: light      # rhythm game, modelli semplici su sfondi statici
    presets:
      igpu-weak:
        duckstation_resolution_scale: "4"      # può permettersi di più: gioco leggero
      dgpu-mid:
        duckstation_resolution_scale: "9"
```

## Esempio — `systems/switch.yaml`

```yaml
games:
  "0100f2c0115b6000":   # Title ID reale di Tears of the Kingdom
    title: "The Legend of Zelda: Tears of the Kingdom"
    aliases_filename:
      - "Legend of Zelda, The - Tears of the Kingdom (...).xci"
    heaviness: very_heavy
    presets:
      igpu-weak:
        core: ryujinx-emu
        ryu_backend: vulkan
        ryu_resolution_scale: "0.75"
      igpu-strong:
        ryu_resolution_scale: "1.0"
    known_issues:
      - symptom: "scatta nei villaggi, nessun crash"
        cause: "risoluzione troppo alta per iGPU debole — gioco notoriamente pesante su CPU"
        fix: { ryu_resolution_scale: "0.5" }
```

## Esempio — `diagnostics/pcsx2.yaml` (regole generiche, non per-gioco)

```yaml
rules:
  - match_log_pattern: "VK_ERROR|vulkan.*lost|GPU hang"
    cause: "Backend Vulkan ha causato crash/hang del driver GPU"
    fix_suggestions:
      - description: "Passa a OpenGL (più stabile su iGPU Intel)"
        settings: { pcsx2_gfxbackend: 12 }
  - match_log_pattern: "bad_alloc|out of memory"
    cause: "Risoluzione/texture troppo alte per la memoria disponibile"
    fix_suggestions:
      - description: "Abbassa la risoluzione interna di un livello"
        settings: { pcsx2_resolution: "-1" }   # "-1" = decrementa rispetto all'attuale
```

## Scope — tutti i sistemi installati su questa macchina (ricognizione 2026-07-02)

Analisi completa di tutti i sistemi con rom reali per decidere dove ha senso costruire un catalogo/advisor e dove no.

### `advisor-utile` — hanno chiavi grafiche/performance rilevanti e beneficiano di un catalogo per-gioco

| Sistema | Emulatore | Identificazione gioco | Priorità |
|---|---|---|---|
| **PS2** | pcsx2 | serial da `SYSTEM.CNF` (ISO9660, in chiaro) | fatto — vedi sopra |
| **Switch** | ryujinx-emu / citron-emu / eden-emu(-pgo/-nightly) | Title ID osservato dalle cartelle create dagli emulatori dopo il primo lancio | fatto — vedi sopra |
| **PSX** | duckstation | stesso identico meccanismo di PS2: `SYSTEM.CNF` in chiaro nell'ISO9660 (verificato, es. `BOOT = cdrom:\SCES_003.44;1` = Crash Bandicoot). Chiavi verificate: `duckstation_resolution_scale` (1×–16×), `duckstation_gfxbackend` (Vulkan/OpenGL/Software) | **bozzato** — vedi esempio sopra |
| **Naomi / Atomiswave** | flycast | hardware 3D (derivato Dreamcast/PowerVR): `flycast_render_resolution`, `flycast_renderer` (OpenGL/Vulkan) — non è arcade 2D raw come si pensava | opportunistico: oggi solo bios installati, zero giochi reali. Da fare solo se arrivano rom pesanti |
| **MAME** | mame078plus/core mame | `mame_altres` esiste ma rilevante solo per i rari driver 3D/vector; la libreria 2D standard non ne beneficia | basso ROI vista la varietà di romset — al massimo regole diagnostiche generiche (es. overclock CPU per rallentamenti), niente catalogo per-gioco |

### `leggero-non-prioritario` — girano senza sforzo su qualsiasi x86 moderno, tuning ininfluente

fbneo, c64, nes, snes, gb, gba, gbc, megadrive, pcengine, mrboom, sdlpop, prboom, neogeocd. Nessuna feature di risoluzione/upscaling rilevante (verificato su fbneo in `es_features.cfg`: solo `frameskip`/overclock CPU). SudoBat li lascia passare senza diagnosi dedicata — non bloccanti, semplicemente non hanno un catalogo.

### `fuori-scope` — non sono emulatori con chiavi grafiche nel modello di SudoBat

`steam` (launcher Steam nativo), `windows` (Wine/Proton, tuning dipenderebbe dal gioco Windows sotto DXVK — modello completamente diverso), `moonlight` (game-streaming, il rendering avviene su un'altra macchina), `ports` (contenitore di script di lancio generici, non un emulatore), `odcommander` (file manager, non un gioco). L'hook `gameStart`/`gameStop` deve riconoscere questi sistemi ed **ignorarli esplicitamente**, senza tentare diagnosi.

## Stato

Schema PS2/Switch/PSX definito e implementato; scope completo su tutti i sistemi deciso il 2026-07-02. Naomi/Atomiswave restano opportunistici: si aggiungono solo se arrivano rom pesanti reali.
