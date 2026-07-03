"""Identificazione gioco Switch: si osservano le cartelle Title ID che gli emulatori
stessi creano dopo il primo lancio (shader cache/salvataggi), invece di decifrare
il container XCI (NCA/HFS0) da soli -- lavoro non banale, evitato riusando quello
che l'emulatore ha gia' fatto.
"""
import re
from pathlib import Path

_TITLEID_RE = re.compile(r"^[0-9A-Fa-f]{16}$")

_EMULATOR_SCAN_DIRS = {
    "ryujinx-emu": [Path("/userdata/system/configs/Ryujinx/games")],
    "citron-emu": [Path("/userdata/system/configs/yuzu/shader")],
    "eden-emu": [Path("/userdata/system/configs/yuzu/shader")],
    "eden-pgo": [Path("/userdata/system/configs/yuzu/shader")],
    "eden-nightly": [Path("/userdata/system/configs/yuzu/shader")],
}


def guess_title_id(emulator: str, since_ts: float) -> str | None:
    """Ritorna il Title ID la cui cartella e' stata creata/toccata dopo since_ts,
    tra quelle note per l'emulatore indicato. Se piu' cartelle risultano toccate
    nella finestra, si prende la piu' recente. None se non trova nulla."""
    scan_dirs = _EMULATOR_SCAN_DIRS.get(emulator, [])
    candidates = []
    for base in scan_dirs:
        if not base.is_dir():
            continue
        for entry in base.iterdir():
            if not entry.is_dir() or not _TITLEID_RE.match(entry.name):
                continue
            mtime = entry.stat().st_mtime
            if mtime >= since_ts:
                candidates.append((mtime, entry.name.lower()))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]
