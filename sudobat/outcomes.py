"""Memoria degli ESITI: cosa e' stato applicato a un gioco e com'e' andata la
sessione DOPO. E' il pezzo che rende SudoBat capace di imparare dai risultati veri:

  - CONSIGLI MIGLIORI: un set che ha fatto ricrashare viene sconsigliato; uno che
    ha funzionato piu' volte viene preferito.
  - DISTILLAZIONE AUTO-CORRETTIVA: una regola distillata il cui fix continua a far
    crashare non e' da fidarsi -> qui si vede.

Come si collega al resto: quando si applica un set (cli apply / UI) si chiama
note_applied() -> record "pending". Alla diagnosi della sessione successiva si
chiama resolve() con l'esito (ok / crash), dedotto da durata + logscan. Nessuna
misura di FPS: solo "ha ricrashato?" e "ha girato a lungo pulito?".

Dati runtime in state/outcomes.json (gitignorato).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

_STORE = Path(__file__).parent.parent / "state" / "outcomes.json"


def _load() -> list:
    if _STORE.exists():
        try:
            return json.loads(_STORE.read_text())
        except (ValueError, OSError):
            return []
    return []


def _save(records: list) -> None:
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    _STORE.write_text(json.dumps(records, indent=2, ensure_ascii=False))


def _norm(settings: dict | None) -> str:
    """Chiave stabile di un set (ordine indipendente, valori come stringa)."""
    return json.dumps({k: str(v) for k, v in sorted((settings or {}).items())}, ensure_ascii=False)


def note_applied(system: str, game_id: str, settings: dict, *, source: str = "", game_title: str = "") -> None:
    """Registra che questo set e' stato applicato al gioco (esito 'pending', da
    risolvere alla sessione successiva)."""
    records = _load()
    records.append({
        "when": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ts": int(time.time()),   # per capire se la sessione dopo e' successiva all'apply
        "system": system, "game_id": game_id, "game": game_title,
        "settings": settings or {}, "settings_key": _norm(settings),
        "source": source, "result": "pending",
    })
    _save(records)


def resolve(system: str, game_id: str, outcome: str) -> dict | None:
    """Assegna l'esito ('ok'/'crash') all'ultimo record 'pending' del gioco.
    Ritorna il record risolto, o None se non c'era nulla in sospeso."""
    records = _load()
    for rec in reversed(records):
        if rec["system"] == system and rec["game_id"] == game_id and rec["result"] == "pending":
            rec["result"] = outcome
            rec["resolved_when"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _save(records)
            return rec
    return None


# I 4 flag che l'utente da' a fine partita: l'esperienza VERA, non solo "ha crashato".
# Sono la voce dell'utente -- il segnale di qualita' che SudoBat da solo non puo' misurare.
FLAG_KEYS = ["fluido", "fps_ok", "scatti_concitate", "glitch"]


def is_good_experience(flags: dict) -> bool:
    """Esperienza BUONA = girava fluido, fps buoni, niente scatti nelle fasi
    concitate, niente glitch grafici. Qualunque altra combinazione e' 'da migliorare'."""
    return bool(flags.get("fluido") and flags.get("fps_ok")
                and not flags.get("scatti_concitate") and not flags.get("glitch"))


def pending_for(system: str, game_id: str) -> dict | None:
    """L'ultimo set applicato a questo gioco ancora in attesa del giudizio utente.
    None se non c'e' nulla in sospeso."""
    for rec in reversed(_load()):
        if rec["system"] == system and rec["game_id"] == game_id and rec["result"] == "pending":
            return rec
    return None


def resolve_flags(system: str, game_id: str, flags: dict) -> dict | None:
    """Risolve l'ultimo record pending del gioco con i FLAG dati dall'utente.
    result = 'good' se l'esperienza e' buona, altrimenti 'bad'. Salva i flag grezzi
    (servono all'escalation per capire COSA non andava). None se non c'era pending."""
    records = _load()
    for rec in reversed(records):
        if rec["system"] == system and rec["game_id"] == game_id and rec["result"] == "pending":
            rec["flags"] = {k: bool(flags.get(k)) for k in FLAG_KEYS}
            rec["result"] = "good" if is_good_experience(rec["flags"]) else "bad"
            rec["resolved_when"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _save(records)
            return rec
    return None


def track_record(system: str, game_id: str, settings: dict | None = None) -> dict:
    """Conteggio {ok, crash} per un gioco; se settings e' dato, solo per quel set."""
    key = _norm(settings) if settings is not None else None
    ok = crash = 0
    for rec in _load():
        if rec["system"] != system or rec["game_id"] != game_id:
            continue
        if key is not None and rec.get("settings_key") != key:
            continue
        # 'good' (giudizio utente coi flag) conta come positivo, 'ok' (solo "non ha
        # crashato") pure; 'bad'/'crash' come negativo.
        if rec["result"] in ("ok", "good"):
            ok += 1
        elif rec["result"] in ("crash", "bad"):
            crash += 1
    return {"ok": ok, "crash": crash}


def verdict(system: str, game_id: str, settings: dict) -> str:
    """Etichetta breve sullo storico di un set, per annotarlo nei consigli."""
    tr = track_record(system, game_id, settings)
    if tr["ok"] and not tr["crash"]:
        return f"provato: {tr['ok']} volte OK"
    if tr["crash"] and not tr["ok"]:
        return f"SCONSIGLIATO: ha fatto ricrashare {tr['crash']} volte"
    if tr["ok"] or tr["crash"]:
        return f"misto: {tr['ok']} OK / {tr['crash']} crash"
    return ""


def history(system: str, game_id: str) -> list:
    return [r for r in _load() if r["system"] == system and r["game_id"] == game_id]


def rerank(sets: list, system: str, game_id: str) -> list:
    """Ri-ordina la raccomandazione (★) dei set in base agli ESITI reali, non solo
    all'euristica. Attacca a ogni set: ok, crash, verdict, reco_reason. Se non c'e'
    storico, lascia la scelta euristica invariata."""
    if not sets or not game_id:
        for s in sets:
            if s.get("recommended"):
                s.setdefault("reco_reason", "euristica")
                s.setdefault("reco_reason_key", "reco_heuristic")
            else:
                s.setdefault("reco_reason", "")
                s.setdefault("reco_reason_key", "")
        return sets

    for s in sets:
        tr = track_record(system, game_id, s.get("settings"))
        s["ok"], s["crash"] = tr["ok"], tr["crash"]
        s["verdict"] = verdict(system, game_id, s.get("settings", {}))

    heuristic = next((s for s in sets if s.get("recommended")), None)
    proven_good = [s for s in sets if s["ok"] > 0 and s["crash"] == 0]
    proven_bad = [s for s in sets if s["crash"] > 0 and s["ok"] == 0]

    # (testo italiano per la CLI, chiave i18n per la UI)
    chosen, reason, reason_key = heuristic, "euristica", "reco_heuristic"
    if proven_good:
        best = max(proven_good, key=lambda s: s["ok"])
        # se l'euristica e' gia' fra i promossi, non ribaltare per un pareggio
        chosen = heuristic if (heuristic in proven_good and heuristic["ok"] == best["ok"]) else best
        if chosen is not heuristic:
            reason, reason_key = "esiti: ha funzionato sul campo", "reco_field_ok"
        else:
            reason, reason_key = "euristica confermata dagli esiti", "reco_heuristic_confirmed"
    elif heuristic in proven_bad:
        alt = [s for s in sets if s not in proven_bad]
        if alt:
            chosen, reason, reason_key = alt[0], "esiti: l'euristica aveva fatto ricrashare", "reco_heuristic_crashed"

    for s in sets:
        s["recommended"] = (s is chosen)
        s["reco_reason"] = reason if s is chosen else ""
        s["reco_reason_key"] = reason_key if s is chosen else ""
    return sets
