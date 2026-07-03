"""Lettura e scrittura di batocera.conf.

Formato flat chiave=valore (non un vero INI a sezioni: Batocera stesso lo tratta
cosi', vedi configgen/settings/unixSettings.py).

La scrittura (Fase 2) e' CHIRURGICA e con rete di sicurezza:
 - modifica solo le righe delle chiavi richieste, lasciando intatti commenti,
   righe vuote e ordine (a differenza di Batocera che riscrive tutto e perde i
   commenti) -- blast radius minimo su un file spesso curato a mano dall'utente;
 - fa sempre un BACKUP timestampato prima di scrivere;
 - scrittura ATOMICA (file temporaneo + os.replace) per non lasciare mai il file
   a meta';
 - supporta il DRY-RUN (preview): mostra il diff senza toccare nulla.
Il sistema live non va mai toccato senza backup + conferma.
"""
import os
import re
import shutil
import time
from pathlib import Path

BATOCERA_CONF_PATH = Path("/userdata/system/batocera.conf")

# La rotazione tiene gli ultimi N backup: abbastanza per tornare indietro,
# senza accumulare file all'infinito in /userdata/system/.
_BACKUP_KEEP = 10
_BAK_SUFFIX_RE = re.compile(r"\.sudobat-bak-(\d{8}-\d{6})(?:-(\d+))?$")


def read_raw_lines(path: Path = BATOCERA_CONF_PATH) -> list:
    return path.read_text().splitlines()


def parse(path: Path = BATOCERA_CONF_PATH) -> dict:
    """Ritorna un dict chiave->valore, ignorando righe vuote/commenti (# o ##)."""
    values = {}
    for line in read_raw_lines(path):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


def get_game_override(values: dict, system: str, romfile: str, option: str):
    """Legge un override per-gioco nel formato sistema["romfile"].opzione=valore."""
    key = f'{system}["{romfile}"].{option}'
    return values.get(key)


def game_override_key(system: str, romfile: str, option: str) -> str:
    """Costruisce la chiave override per-gioco nel formato di batocera.conf."""
    return f'{system}["{romfile}"].{option}'


def backup(path: Path = BATOCERA_CONF_PATH) -> Path:
    """Copia timestampata di batocera.conf accanto all'originale. copy2 preserva
    i metadati. Due backup nello stesso secondo NON si sovrascrivono (contatore
    progressivo): senza, un apply+ripristino ravvicinati corromperebbero la
    catena dei backup. Ritorna il percorso del backup."""
    ts = time.strftime("%Y%m%d-%H%M%S")
    dest = path.with_name(f"{path.name}.sudobat-bak-{ts}")
    n = 0
    while dest.exists():
        n += 1
        dest = path.with_name(f"{path.name}.sudobat-bak-{ts}-{n}")
    shutil.copy2(path, dest)
    return dest


def list_backups(path: Path = BATOCERA_CONF_PATH) -> list:
    """I backup di questo file, dal piu' recente al piu' vecchio. Ordinati per
    NOME (timestamp + contatore), non per mtime: copy2 preserva l'mtime
    dell'originale, quindi l'mtime del backup mente sulla data del backup."""
    if not path.parent.is_dir():
        return []
    found = []
    for p in path.parent.glob(f"{path.name}.sudobat-bak-*"):
        m = _BAK_SUFFIX_RE.search(p.name)
        if m:
            found.append(((m.group(1), int(m.group(2) or 0)), p))
    return [p for _key, p in sorted(found, reverse=True)]


def latest_backup(path: Path = BATOCERA_CONF_PATH) -> Path | None:
    baks = list_backups(path)
    return baks[0] if baks else None


def rotate_backups(path: Path = BATOCERA_CONF_PATH, keep: int = _BACKUP_KEEP) -> list:
    """Tiene i `keep` backup piu' recenti ed elimina gli altri. Ritorna i path
    rimossi. Chiamata dopo ogni nuovo backup, cosi' la cartella non cresce mai."""
    removed = []
    for p in list_backups(path)[keep:]:
        try:
            p.unlink()
            removed.append(p)
        except OSError:
            pass  # un backup non cancellabile non deve bloccare la scrittura
    return removed


def restore_latest_backup(path: Path = BATOCERA_CONF_PATH, *, dry_run: bool = True) -> dict:
    """"Annulla ultima modifica": ripristina la conf dall'ultimo backup.

    Prima salva la conf ATTUALE come nuovo backup (cosi' anche il ripristino e'
    annullabile: un secondo restore torna allo stato pre-ripristino), poi copia
    il backup scelto al posto della conf, in modo atomico.

    dry_run=True (default): non tocca nulla, dice solo da quale backup
    ripristinerebbe. Ritorna {restored, restored_from, safety_backup}.
    """
    target = latest_backup(path)
    result = {"restored": False,
              "restored_from": str(target) if target else None,
              "safety_backup": None}
    if target is None or dry_run:
        return result

    safety = backup(path)
    tmp = path.with_name(f"{path.name}.sudobat-tmp-{os.getpid()}")
    shutil.copyfile(target, tmp)
    os.replace(tmp, path)
    rotate_backups(path)

    result["restored"] = True
    result["safety_backup"] = str(safety)
    return result


def plan_changes(updates: dict, path: Path = BATOCERA_CONF_PATH) -> list:
    """Confronta gli update {chiave: valore} col file attuale e ritorna la lista
    delle modifiche come dict {key, old, new, action}. Nessuna scrittura.
    action = 'unchanged' | 'update' | 'add'. Serve al dry-run/preview."""
    current = parse(path) if path.exists() else {}
    changes = []
    for key, new_value in updates.items():
        new_value = str(new_value)
        old_value = current.get(key)
        if old_value is None:
            action = "add"
        elif old_value == new_value:
            action = "unchanged"
        else:
            action = "update"
        changes.append({"key": key, "old": old_value, "new": new_value, "action": action})
    return changes


def set_values(updates: dict, path: Path = BATOCERA_CONF_PATH, *, dry_run: bool = True,
               do_backup: bool = True) -> dict:
    """Applica {chiave: valore} a batocera.conf in modo chirurgico.

    dry_run=True (default): non scrive nulla, ritorna solo il piano. La scrittura
    va richiesta esplicitamente con dry_run=False -- rete di sicurezza contro
    modifiche accidentali al sistema live.

    Preserva commenti/righe vuote/ordine: aggiorna in-place la riga della chiave
    se esiste, altrimenti la accoda in fondo. Backup prima di scrivere, scrittura
    atomica. Ritorna {changes, applied, backup}.
    """
    changes = plan_changes(updates, path)
    effective = [c for c in changes if c["action"] != "unchanged"]

    result = {"changes": changes, "applied": False, "backup": None}
    if dry_run or not effective:
        return result

    backup_path = None
    if do_backup:
        backup_path = backup(path)
        rotate_backups(path)

    # riscrittura chirurgica: aggiorna solo le righe delle chiavi note.
    remaining = {c["key"]: c["new"] for c in effective}
    lines = path.read_text().splitlines()
    out_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.partition("=")[0].strip()
            if key in remaining:
                out_lines.append(f"{key}={remaining.pop(key)}")
                continue
        out_lines.append(line)
    # chiavi non trovate -> accodate in fondo
    for key, value in remaining.items():
        out_lines.append(f"{key}={value}")

    # scrittura atomica: tmp nella stessa dir + os.replace (rename atomico)
    tmp = path.with_name(f"{path.name}.sudobat-tmp-{os.getpid()}")
    tmp.write_text("\n".join(out_lines) + "\n")
    os.replace(tmp, path)

    result["applied"] = True
    result["backup"] = str(backup_path) if backup_path else None
    return result


def set_game_override(system: str, romfile: str, settings: dict,
                      path: Path = BATOCERA_CONF_PATH, *, dry_run: bool = True) -> dict:
    """Scrive uno o piu' override per-gioco (sistema["romfile"].opzione=valore).
    Wrapper attorno a set_values con le chiavi gia' formattate."""
    updates = {game_override_key(system, romfile, opt): val for opt, val in settings.items()}
    return set_values(updates, path, dry_run=dry_run)
