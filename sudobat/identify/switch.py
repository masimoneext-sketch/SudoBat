"""Identificazione gioco Switch: si osservano le cartelle Title ID che gli emulatori
stessi creano dopo il primo lancio (shader cache/salvataggi), invece di decifrare
il container XCI (NCA/HFS0) da soli -- lavoro non banale, evitato riusando quello
che l'emulatore ha gia' fatto.

Nessuna tabella per-emulatore: i fork cambiano nome (yuzu/citron/eden/...), le
convenzioni restano. Si scandisce QUALUNQUE cartella configs/*/shader e
configs/*/games in cerca di sottocartelle con nome Title ID (16 cifre esadecimali).
"""
import re
from pathlib import Path

_TITLEID_RE = re.compile(r"^[0-9A-Fa-f]{16}$")

_CONFIGS = Path("/userdata/system/configs")
# convenzioni note per le cartelle per-titolo (famiglia yuzu: shader/, Ryujinx: games/)
_SUBDIRS = ("shader", "games")


def _last_activity(d: Path) -> float:
    """Attivita' piu' recente: mtime della cartella O dei file direttamente dentro.
    Serve guardare dentro perche' l'emulatore RISCRIVE i file della cache
    (vulkan_pipelines.bin ecc.) senza ricreare la cartella: per un gioco gia'
    giocato in passato il mtime della sola directory resta quello vecchio."""
    ts = d.stat().st_mtime
    try:
        for f in d.iterdir():
            m = f.stat().st_mtime
            if m > ts:
                ts = m
    except OSError:
        pass
    return ts


def guess_title_id(emulator: str, since_ts: float) -> str | None:
    """Ritorna il Title ID la cui cartella mostra attivita' dopo since_ts, tra
    quelle di qualunque emulatore presente in configs/. Se piu' cartelle risultano
    toccate nella finestra, si prende la piu' recente. None se non trova nulla.
    ('emulator' non serve piu' alla scansione: tenuto per compatibilita' di firma.)"""
    candidates = []
    seen_bases = set()
    for sub in _SUBDIRS:
        for base in _CONFIGS.glob(f"*/{sub}"):
            real = base.resolve()  # eden/citron sono spesso symlink a yuzu
            if real in seen_bases or not base.is_dir():
                continue
            seen_bases.add(real)
            for entry in base.iterdir():
                if not entry.is_dir() or not _TITLEID_RE.match(entry.name):
                    continue
                mtime = _last_activity(entry)
                if mtime >= since_ts:
                    candidates.append((mtime, entry.name.lower()))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]
