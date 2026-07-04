"""Controllo aggiornamenti: confronta la VERSION locale con quella pubblicata
su GitHub e, se l'utente accetta, esegue l'installer ufficiale (install.sh,
lo stesso del README: idempotente, con selftest).

Filosofia, coerente col resto del tool:
  - MAI invadente: il controllo parte in un thread all'avvio della UI, al
    massimo UNA volta al giorno (cache in state/), con timeout corto; senza
    rete tace e la UI parte identica.
  - MAI automatico: l'aggiornamento si propone soltanto; l'esecuzione e' una
    scelta esplicita dell'utente, dietro conferma.
Si notifica per RELEASE (bump del file VERSION), non a ogni commit.
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_VERSION_FILE = _ROOT / "VERSION"
_CACHE = _ROOT / "state" / "update_check.json"
_REMOTE_URL = "https://raw.githubusercontent.com/masimoneext-sketch/SudoBat/master/VERSION"
_CHECK_EVERY_SECONDS = 24 * 3600  # una volta al giorno basta e avanza


def local_version() -> str:
    try:
        return _VERSION_FILE.read_text().strip()
    except OSError:
        return "0"


def _parse(v: str) -> tuple:
    """'1.10' > '1.2' deve valere: confronto numerico per componente."""
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except ValueError:
        return (0,)


def is_newer(remote: str | None, local: str) -> bool:
    if not remote:
        return False
    return _parse(remote) > _parse(local)


def _fetch_remote(timeout: float = 3.0) -> str | None:
    """La VERSION pubblicata, o None (niente rete / repo irraggiungibile)."""
    req = urllib.request.Request(
        _REMOTE_URL, headers={"User-Agent": f"SudoBat/{local_version()} (Batocera)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode(errors="replace").strip()
    except Exception:
        return None


def check(force: bool = False) -> dict:
    """{'local', 'remote', 'available'}. Usa la cache giornaliera salvo force=True.
    remote=None significa 'non ho potuto controllare' (mai un errore visibile)."""
    local = local_version()
    cached = None
    if not force:
        try:
            cached = json.loads(_CACHE.read_text())
        except (ValueError, OSError):
            cached = None
        if cached and time.time() - cached.get("ts", 0) < _CHECK_EVERY_SECONDS:
            remote = cached.get("remote")
            return {"local": local, "remote": remote, "available": is_newer(remote, local)}
    remote = _fetch_remote()
    try:
        _CACHE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE.write_text(json.dumps({"ts": int(time.time()), "remote": remote}))
    except OSError:
        pass
    return {"local": local, "remote": remote, "available": is_newer(remote, local)}


def check_async(on_done) -> None:
    """Controllo in background: la UI non aspetta mai la rete."""
    def _worker():
        try:
            on_done(check())
        except Exception:
            pass  # il controllo update non deve MAI disturbare la UI
    threading.Thread(target=_worker, daemon=True).start()


def run_installer(timeout: int = 600) -> dict:
    """Esegue l'installer ufficiale (aggiorna + selftest + registrazione PORTS).
    Ritorna {'ok': bool, 'output': ultime righe} — la UI mostra l'esito, onesto."""
    script = _ROOT / "install.sh"
    if not script.is_file():
        return {"ok": False, "output": "install.sh non trovato"}
    try:
        res = subprocess.run(["bash", str(script)], cwd=_ROOT,
                             capture_output=True, text=True, timeout=timeout)
        tail = "\n".join((res.stdout + res.stderr).splitlines()[-6:])
        return {"ok": res.returncode == 0, "output": tail}
    except (OSError, subprocess.SubprocessError) as e:
        return {"ok": False, "output": str(e)}
