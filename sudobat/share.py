# SudoBat — Copyright © 2026 Marco Simone. PolyForm Noncommercial License 1.0.0.
# Uso personale/non commerciale libero; uso commerciale solo con licenza separata. Vedi LICENSE.md.
"""Condivisione OPT-IN dei set validati buoni (vedi KNOWLEDGE_SHARING.md).

Regole incise nel codice:
  - NESSUN invio senza consenso esplicito ("yes" in state/share_prefs.json).
    La domanda viene fatta UNA volta, dalla UI, alla prima validazione buona.
  - Cosa parte (tutto qui, niente altro): sistema, id/titolo gioco, fascia hw,
    emulatore/core, settaggi, flag esperienza, e un install_id CASUALE (uuid4,
    non derivato dall'hardware) che serve al quorum lato server.
  - Invio best-effort e SILENZIOSO: coda locale, ritenta al prossimo avvio,
    un fallimento di rete non disturba mai l'utente e non blocca mai la UI.
Solo libreria standard (urllib): su Batocera non c'e' pip.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
import uuid
from pathlib import Path

_STATE_DIR = Path(__file__).parent.parent / "state"
_PREFS = _STATE_DIR / "share_prefs.json"
_QUEUE = _STATE_DIR / "share_queue.json"

_DEFAULT_ENDPOINT = "https://sudobat-knowledge.marcosimone.tech/api/v1/sets"
SCHEMA = 1
VERSION = "1.1"


def _endpoint() -> str:
    return os.environ.get("SUDOBAT_KNOWLEDGE_ENDPOINT", _DEFAULT_ENDPOINT)


def _load(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1))


def consent() -> str | None:
    """"yes" / "no" / None (mai chiesto). None = la UI deve chiedere."""
    return _load(_PREFS, {}).get("consent")


def install_id() -> str | None:
    return _load(_PREFS, {}).get("install_id")


def set_consent(yes: bool) -> None:
    prefs = _load(_PREFS, {})
    prefs["consent"] = "yes" if yes else "no"
    prefs.setdefault("install_id", str(uuid.uuid4()))
    prefs["asked_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save(_PREFS, prefs)


def build_entry(*, system: str, game_id: str, game_title: str, tier: str,
                emulator: str, core: str, settings: dict, flags: dict) -> dict:
    return {
        "system": system, "game_id": game_id, "game_title": game_title,
        "tier": tier, "emulator": emulator, "core": core,
        "settings": {k: v for k, v in (settings or {}).items()},
        "flags": {k: bool(v) for k, v in (flags or {}).items()},
    }


def enqueue(entry: dict) -> None:
    """Accoda un set validato. Chi chiama ha gia' verificato il consenso."""
    queue = _load(_QUEUE, [])
    queue.append(entry)
    _save(_QUEUE, queue[-50:])  # cap difensivo: mai una coda infinita


def flush(timeout: float = 6.0) -> int:
    """Invia la coda al collettore. Ritorna quanti inviati. Silenzioso: al primo
    errore si ferma e riprova alla prossima occasione. Consenso ricontrollato
    qui (l'utente puo' averlo revocato dalle Impostazioni a coda piena)."""
    if consent() != "yes":
        return 0
    queue = _load(_QUEUE, [])
    if not queue:
        return 0
    iid = install_id()
    sent = 0
    remaining = list(queue)
    for entry in queue:
        body = dict(entry)
        body["schema"] = SCHEMA
        body["install_id"] = iid
        body["sudobat_version"] = VERSION
        req = urllib.request.Request(
            _endpoint(), data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "User-Agent": f"SudoBat/{VERSION}"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status not in (200, 204):
                    break
        except Exception:
            break  # rete giu'/endpoint assente: la coda resta, si riprova poi
        remaining.pop(0)
        sent += 1
    _save(_QUEUE, remaining)
    return sent


def queue_length() -> int:
    return len(_load(_QUEUE, []))


def share_async(entry: dict | None = None) -> None:
    """Accoda (se dato) e invia in un thread: la UI non aspetta mai la rete."""
    def _worker():
        try:
            if entry is not None:
                enqueue(entry)
            flush()
        except Exception:
            pass  # la condivisione non deve MAI far crashare nulla
    threading.Thread(target=_worker, daemon=True).start()
