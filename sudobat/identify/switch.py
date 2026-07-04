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

# Basi dove gli emulatori tengono dati/log: configs/ (redirezione Batocera) e i
# path XDG standard (gli AppImage non agganciati alla redirezione usano quelli).
_BASES = (
    Path("/userdata/system/configs"),
    Path("/userdata/system/.local/share"),
    Path("/userdata/system/.config"),
)
# convenzioni note per le cartelle per-titolo (famiglia yuzu: shader/, Ryujinx: games/)
_SUBDIRS = ("shader", "games")
# e per i file di log (yuzu-family: log/*.txt, Ryujinx: Logs/*.log)
_LOG_GLOBS = ("*/log/*.txt", "*/log/*.log", "*/Logs/*.log")

# Il Title ID come lo DICHIARANO i log degli emulatori stessi, es.
#   "PatchExeFS: Patching ExeFS for title_id=01006B601380E000"
#   "Loading Kirby's Return to Dream Land Deluxe (01006B601380E000) ..."
_TITLE_IN_LOG_RE = re.compile(
    r"title[_ -]?id[=: ]+\(?([0-9A-Fa-f]{16})\)?|\(([0-9A-Fa-f]{16})\)")


def _title_from_logs(since_ts: float) -> str | None:
    """Title ID dichiarato nel log emulatore piu' recente scritto dopo since_ts.
    E' la fonte piu' affidabile: c'e' SEMPRE, anche per una sessione corta in cui
    l'emulatore non riscrive nessun file di cache (dove l'euristica delle cartelle
    e' cieca). Si prende l'ULTIMA occorrenza = il gioco avviato per ultimo."""
    best = None
    seen = set()
    for base in _BASES:
        for pattern in _LOG_GLOBS:
            for f in base.glob(pattern):
                try:
                    real = f.resolve()
                    if real in seen:
                        continue
                    seen.add(real)
                    mtime = f.stat().st_mtime
                except OSError:
                    continue
                if mtime >= since_ts and (best is None or mtime > best[0]):
                    best = (mtime, f)
    if best is None:
        return None
    try:
        text = best[1].read_text(errors="replace")
    except OSError:
        return None
    last = None
    for m in _TITLE_IN_LOG_RE.finditer(text):
        last = m.group(1) or m.group(2)
    return last.lower() if last else None


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
    """Ritorna il Title ID dell'ultimo gioco avviato dopo since_ts. Prima fonte:
    il log dell'emulatore (lo dichiara sempre); fallback: la cartella per-titolo
    con attivita' nella finestra (se piu' d'una, la piu' recente). None se nulla.
    ('emulator' non serve piu' alla scansione: tenuto per compatibilita' di firma.)"""
    from_log = _title_from_logs(since_ts)
    if from_log:
        return from_log
    candidates = []
    seen_bases = set()
    for root in _BASES:
        for sub in _SUBDIRS:
            for base in root.glob(f"*/{sub}"):
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
