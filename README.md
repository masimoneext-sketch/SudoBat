# SudoBat

🇮🇹 **[Versione italiana](README.it.md)**

> **Per-game, hardware-aware graphics tuning for Batocera.** A game crashes or stutters? SudoBat recognizes it, figures out why, and proposes the right settings for your machine — you apply them with one button, from the gamepad.

---

## 🎮 What it does

SudoBat is an app that runs **inside Batocera** (as a Port in EmulationStation) and eliminates manual per-game graphics tuning:

- **Tracks every launch** automatically: game, system, emulator, core, session duration
- **Diagnoses crashes**: reads the emulator logs, recognizes known issues (e.g. unstable Vulkan driver on Intel iGPUs) and tells you the probable cause in plain language
- **Proposes tailored graphics sets** (Max smoothness / Balanced / Quality), computed for YOUR hardware and the game's heaviness — the values are the real ones exposed by Batocera, not made-up numbers
- **Applies with one button**: writes per-game overrides to `batocera.conf`, with automatic backup and restore always available
- **Learns from real results**: after a session it asks how it went (smooth? stutter? glitches?). Sets that work get promoted, sets that crash again get flagged, and good experiences land in a catalog that grows with use
- **Optional AI turbo**: for crashes it doesn't recognize, it can query an LLM (Groq, free API key) and — after your confirmation — turn the diagnosis into a permanent offline rule: that crash will never need the network again

What SudoBat **does not** do, stated honestly:

- **It does not measure FPS**: it relies on session duration, crash logs and your end-of-session judgment. That's deliberate: automatic FPS measurement is fragile and different for every emulator
- **It does not switch emulator or core**: EmulationStation decides that. When it's the right move, SudoBat recommends it with precise instructions, but you take the step
- **The catalog starts light and improves as you play**: there is no pre-compiled database of thousands of games; knowledge is built from your validated sessions
- **Lightweight 2D systems** (NES, SNES, GB/GBA, classic arcade…) get no dedicated tuning: they run fine on any modern x86, there is nothing to optimize

---

## 📋 Requirements

| What | Requirement |
|---|---|
| OS | **Batocera.linux on x86_64** (mini-PC / desktop). Developed and tested on Batocera 43.1 |
| Hardware | Intel/AMD CPU, iGPU or dedicated GPU (the tier is detected automatically) |
| Dependencies | **Nothing to install**: Python 3, pygame and PyYAML ship with Batocera |
| Network | **Not required** for normal operation. Only needed for the optional AI turbo |

Thoroughly tested on an i5-8500 + Intel UHD 630 (the "weak iGPU" scenario, the trickiest one). Other x86 setups should work by construction — the hardware tier and setting values are read from the machine, not from hardcoded lists — but not everything has been tried.

---

## 🚀 Installation — one command

From the Batocera box (SSH in with `ssh root@batocera.local`, default password `linux`, or use the built-in terminal) run:

```bash
curl -L https://raw.githubusercontent.com/masimoneext-sketch/SudoBat/master/install.sh | bash
```

Then one last manual step, once: in EmulationStation → **Menu → Game settings → Update gamelist** (or just reboot). SudoBat appears in the **PORTS** menu.

**What the script does** (full transparency — it's [`install.sh`](install.sh), readable before running):
1. checks it's really a Batocera x86_64 box
2. downloads SudoBat into `/userdata/system/SudoBat` (git if available, plain archive otherwise)
3. enables launch tracking (a symlink to the official Batocera hook — reversible)
4. runs the 23-test selftest to verify the installation (no writes to the system)
5. registers SudoBat in the PORTS menu, with logo and animated preview

**Re-running the same command updates SudoBat** to the latest version.

<details>
<summary>Prefer doing it by hand? The 3 equivalent steps</summary>

```bash
cd /userdata/system
git clone https://github.com/masimoneext-sketch/SudoBat.git
ln -s /userdata/system/SudoBat/scripts/sudobat-hook.sh /userdata/system/scripts/sudobat-hook.sh
cd /userdata/system/SudoBat && python3 -m tools.register_port
# then refresh the gamelist from ES
```
</details>

To uninstall: remove the hook symlink, the PORTS menu entry and the folder — SudoBat touches nothing else on the system:

```bash
rm /userdata/system/scripts/sudobat-hook.sh /userdata/roms/ports/SudoBat.sh
rm -r /userdata/system/SudoBat
```

---

## 🕹️ How to use it (the full loop)

1. **Play** normally from EmulationStation. If everything's fine, you never even open SudoBat.
2. Game **crashes or stutters**? Quit and open **SudoBat** from the PORTS menu.
3. **Diagnose last launch**: SudoBat recognizes the game (from the disc serial, not the filename), shows what happened and the applicable graphics sets — with the recommended one starred ★.
4. **Apply** the chosen set (it shows exactly what will change first, then backs up and writes).
5. **Replay**. On the next open, SudoBat asks how it went with 4 quick questions (smooth? FPS ok? stutter? glitches?).
6. Based on your answers: good experience → **saved to the catalog** (next time it starts like that already); still trouble → it proposes the next step (a lighter set, or a core/emulator change with instructions).

Everything is navigable with the **gamepad** (or keyboard). Interface in **English and Italian** (switchable in Settings).

### From the terminal (optional)

Every feature also exists as a CLI, handy over SSH:

```bash
cd /userdata/system/SudoBat
python3 -m sudobat.cli profile        # detected hardware profile + tier
python3 -m sudobat.cli diagnose       # diagnosis of the last launch
python3 -m sudobat.cli apply          # proposed fixes (dry-run); apply --write N to apply
python3 -m sudobat.cli restore        # undo the last change (dry-run); --write to do it
python3 -m sudobat.cli sets ps2 SLUS-205.60   # generated sets for a game
python3 -m sudobat.cli brain          # AI turbo on an unknown crash (if configured)
python3 -m sudobat.cli learn          # turn the AI diagnosis into an offline rule
python3 -m sudobat.cli history ps2 SLUS-205.60  # outcome history for a game
```

### AI turbo (optional) — bring your own key

The turbo requires a **personal Groq API key**: free, no credit card, ~5 minutes to get. It must be *yours* because API rate limits are tied to the key's owner — a shared key would run dry immediately, your own is more than enough for SudoBat's usage (one call per unknown crash).

**📖 Step-by-step guide for non-technical users: [docs/GROQ_SETUP.md](docs/GROQ_SETUP.md)** — covers creating the free account, generating the key, and getting it onto the box even without touching a terminal (via the Batocera network share).

Quick version, if you're comfortable with SSH:

```bash
cd /userdata/system/SudoBat
python3 -m sudobat.cli key set gsk_YOUR_KEY   # validates and stores it (600 perms, gitignored)
python3 -m sudobat.cli key test               # real test call: "OK" = turbo ready
```

The Settings screen shows the turbo status at a glance (active / not set up). It kicks in **only** for crashes the offline engine doesn't recognize. **Full transparency about what leaves the machine**: the tail of the crash log (~40 lines), the CPU/GPU model and the game title are sent to Groq. No key = no traffic, and the app works identically on the offline engine alone. The AI never applies anything by itself: it proposes, you confirm.

---

## 🛡️ Safety nets

On a retro box the config is sacred. Every write SudoBat makes is guarded:

- **Writes to a single file**: `batocera.conf`, and only per-game overrides (`system["rom"].key=value`) — never global settings, never the emulators' native ini files
- **Surgical**: only the affected lines change; comments, ordering and the rest of the file stay intact
- **Automatic timestamped backup** before every write, with rotation (last 10 kept)
- **One-button restore**: Settings → "Restore latest backup" (and the restore itself is undoable)
- **Atomic writes**: the file can't be left half-written even if power dies at the wrong moment
- **Dry-run by default**: every "apply" shows the exact change plan first
- An out-of-range value in `batocera.conf` is **ignored by Batocera anyway** (falls back to the default): even the worst case doesn't break the system

---

## ⚙️ Technical specs

- **Stack**: Python 3 + pygame (UI) + PyYAML (data) — all stock on Batocera, zero `pip install`
- **Game identification** robust to renames: PS2 from the serial in `SYSTEM.CNF` (ISO9660 read via `bsdtar`), PSX from the serial inside `.chd` files (`chdman` + sector de-interleave), Switch from the Title ID observed in the emulators' folders
- **Hardware profiling** from real system data (`batocera-info`, `vulkaninfo`, `batocera-vulkan`): tiers `igpu-weak` / `igpu-strong` / `dgpu-entry` / `dgpu-mid` / `dgpu-high`
- **Generated graphics sets**, not hardcoded: the "knobs" and their values are read from Batocera's `es_features`, so they follow the actual installation (including add-on systems like Switch)
- **Diagnosis**: official `gameStart`/`gameStop` hook + ES launch logs + native emulator logs (PCSX2, DuckStation, Ryujinx, yuzu/eden/citron family) + per-emulator YAML rules
- **Tuning coverage**: PS2, PSX, Switch (dedicated diagnosis); any emulator with a resolution axis in `es_features` still gets generated sets
- **Learning**: per game+set outcome memory (field promotion/demotion) and AI→offline-rule distillation, always with human confirmation
- **Footprint**: ~5,000 lines of Python, no background daemon (the hook is a few-line script that fires only on game launch/stop), state kept in `state/` inside the app folder

### Verifying the installation

```bash
python3 -m sudobat.selftest       # 23 engine tests (config, hook, learning) — no writes to the system
python3 -m sudobat.ui --selftest  # UI test, headless
```

---

## 📄 License

SudoBat is released under the **[PolyForm Noncommercial License 1.0.0](LICENSE.md)**:

- ✅ **Free for personal and any other noncommercial use** — your retro box at home, tinkering, sharing with friends
- ❌ **Commercial use is reserved to the author**: bundling SudoBat with devices for sale, paid distributions, or any revenue-generating use requires a separate commercial license — contact the author via GitHub

Contributions are welcome under the terms in [CONTRIBUTING.md](CONTRIBUTING.md) (DCO sign-off + relicensing grant).

`Required Notice: Copyright © 2026 Marco Simone (https://github.com/masimoneext-sketch/SudoBat)`
