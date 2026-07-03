"""Lettura dei log SPECIFICI dell'emulatore + kernel, per diagnosticare i crash
noti come farebbe un umano che apre il log dopo un crash.

Questo e' cio' che prima veniva fatto a mano: ora e' codice che gira offline sulla
macchina dell'utente. Riconosce solo pattern NOTI (quelli codificati nei file
data/diagnostics/*.yaml); un crash mai visto non lo capira' da solo -- quello resta
il limite onesto di un motore di regole.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from . import catalog

# Dove logga ciascun emulatore (verificato su questa Batocera).
_YUZU_LOG_DIR = Path("/userdata/system/configs/yuzu/log")
_RYUJINX_LOG_DIR = Path("/userdata/system/configs/Ryujinx/Logs")
_PCSX2_LOGS = [
    Path("/userdata/system/configs/PCSX2/logs/emulog.txt"),
    Path("/userdata/system/logs/emulog.txt"),
]
_DUCKSTATION_LOGS = [
    Path("/userdata/system/configs/duckstation/duckstation.log"),
]

# Token del nome-processo con cui l'emulatore compare nel kernel (dmesg i915).
# Serve a NON attribuire a un emulatore un hang GPU causato da un altro: il buffer
# del kernel e' globale e conserva righe di sessioni precedenti.
_EMU_PROC = {
    "citron-emu": "citron",
    "eden-emu": "eden", "eden-pgo": "eden", "eden-nightly": "eden",
    "ryujinx-emu": "ryujinx",
    "pcsx2": "pcsx2", "lr-pcsx2": "pcsx2",
    "duckstation": "duckstation",
}


def _latest(paths: list[Path]) -> Path | None:
    existing = [p for p in paths if p.is_file()]
    if not existing:
        return None
    return max(existing, key=lambda p: p.stat().st_mtime)


def emulator_log_path(emulator: str) -> Path | None:
    """Percorso del log piu' recente per l'emulatore indicato, o None."""
    if emulator in ("citron-emu",):
        return _latest([_YUZU_LOG_DIR / "citron_log.txt"])
    if emulator in ("eden-emu", "eden-pgo", "eden-nightly"):
        return _latest([_YUZU_LOG_DIR / "eden_log.txt"])
    if emulator == "ryujinx-emu":
        return _latest(list(_RYUJINX_LOG_DIR.glob("*.log"))) if _RYUJINX_LOG_DIR.is_dir() else None
    if emulator in ("pcsx2", "lr-pcsx2"):
        return _latest(_PCSX2_LOGS)
    if emulator == "duckstation":
        return _latest(_DUCKSTATION_LOGS)
    return None


def _read_tail(path: Path, max_lines: int = 600) -> str:
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-max_lines:])


def dmesg_tail(max_lines: int = 400, proc_token: str | None = None) -> str:
    """Ultime righe del kernel (per gli hang GPU i915, che NON stanno nel log
    dell'emulatore ma solo nel kernel). Se proc_token e' dato, tiene SOLO le righe
    che nominano quel processo: il buffer del kernel e' globale e stale, quindi
    senza filtro un hang di un altro emulatore verrebbe attribuito a questo."""
    try:
        out = subprocess.run(["dmesg"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    lines = out.splitlines()[-max_lines:]
    if proc_token:
        lines = [ln for ln in lines if proc_token.lower() in ln.lower()]
    return "\n".join(lines)


def _evidence_line(text: str, pattern: str) -> str:
    """Prima riga del log che matcha il pattern (la 'prova' da mostrare)."""
    for line in text.splitlines():
        if re.search(pattern, line, re.IGNORECASE):
            return line.strip()[:160]
    return ""


def scan(emulator: str, diagnostics_key: str) -> list[dict]:
    """Legge il log dell'emulatore (+ kernel) e ritorna i crash noti riconosciuti,
    ognuno con causa, prova (riga di log) e cosa proporre. [] se non trova pattern
    noti o se il log non c'e'."""
    rules = catalog.load_diagnostics(diagnostics_key).get("rules", [])
    if not rules:
        return []

    log_path = emulator_log_path(emulator)
    text = _read_tail(log_path) if log_path else ""
    # gli hang GPU stanno solo nel kernel: prendo SOLO le righe di QUESTO emulatore
    kernel = dmesg_tail(proc_token=_EMU_PROC.get(emulator))
    haystack = text + "\n" + kernel

    hits = []
    for rule in rules:
        pattern = rule.get("match_log_pattern", "")
        if not pattern:
            continue
        if not re.search(pattern, haystack, re.IGNORECASE):
            continue
        hits.append({
            "cause": rule.get("cause", ""),
            "evidence": _evidence_line(haystack, pattern),
            "recommend_emulator": rule.get("recommend_emulator"),
            "fix_suggestions": rule.get("fix_suggestions", []),
            "log": str(log_path) if log_path else "(kernel/dmesg)",
        })
    return hits
