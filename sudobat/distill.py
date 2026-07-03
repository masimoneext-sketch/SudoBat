"""Loop di DISTILLAZIONE: trasforma una diagnosi del turbo LLM in una REGOLA
offline salvata in data/diagnostics/<key>.yaml. Cosi' il crash, la prossima volta,
lo riconosce il motore offline veloce -- senza LLM. SudoBat impara e dipende sempre
meno dal cloud.

Guardrail (l'LLM puo' sbagliare, quindi niente automatismi ciechi):
  - ANCORAGGIO: la firma di log proposta dall'LLM deve comparire ALLA LETTERA nel
    log reale, altrimenti si rifiuta (niente pattern inventati).
  - GENERALIZZAZIONE: si toglie il timestamp iniziale ([ 212.6...]) che cambia a
    ogni run, se no la regola non matcherebbe mai i crash futuri.
  - CONFERMA UMANA: qui si costruisce solo il candidato; il salvataggio (append_rule)
    lo lancia l'utente con un comando separato. Backup prima di scrivere; reversibile.
  - TRASPARENZA: la regola e' marcata `source: distilled` con data/modello, cosi' e'
    chiaro che e' imparata (non verita' verificata a mano).
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

from . import catalog

_DIAG_KEY = {
    "pcsx2": "pcsx2", "lr-pcsx2": "pcsx2",
    "citron-emu": "switch", "eden-emu": "switch", "eden-pgo": "switch",
    "eden-nightly": "switch", "ryujinx-emu": "switch",
    "duckstation": "duckstation",
}
_MIN_CONFIDENCE = 0.5
_LEAD_TIMESTAMP = re.compile(r"^\s*\[\s*[\d.]+\s*\]\s*")  # es. "[ 212.626521] "


def diag_key_for(emulator: str) -> str | None:
    return _DIAG_KEY.get(emulator)


def _clean_signature(sig: str) -> str:
    """Toglie il timestamp iniziale e limita la lunghezza, per una firma stabile."""
    sig = _LEAD_TIMESTAMP.sub("", (sig or "").strip())
    return sig[:120].strip()


def _already_recognized(diag_key: str, log_text: str) -> bool:
    for rule in catalog.load_diagnostics(diag_key).get("rules", []):
        pat = rule.get("match_log_pattern", "")
        if pat and re.search(pat, log_text, re.IGNORECASE):
            return True
    return False


def build_candidate(sug: dict, log_text: str, emulator: str) -> tuple[dict | None, str]:
    """Da un suggerimento VERIFICATO del turbo + il log reale, costruisce (regola,
    'ok') oppure (None, motivo). Non salva niente."""
    diag_key = diag_key_for(emulator)
    if not diag_key:
        return None, f"nessun file diagnostics per l'emulatore {emulator}"

    conf = sug.get("confidence")
    if isinstance(conf, (int, float)) and conf < _MIN_CONFIDENCE:
        return None, f"confidenza troppo bassa ({conf}) per imparare una regola"

    sig = _clean_signature(sug.get("log_signature", ""))
    if not sig:
        return None, "l'LLM non ha fornito una firma di log"
    if sig.lower() not in log_text.lower():
        return None, "la firma proposta NON e' presente nel log (non ancorata alla realta')"

    if not sug.get("settings") and not sug.get("recommend_emulator"):
        return None, "nessuna azione concreta da salvare (ne' settings ne' cambio emulatore)"

    if _already_recognized(diag_key, log_text):
        return None, "questo crash e' gia' riconosciuto da una regola esistente"

    rule = {
        "match_log_pattern": re.escape(sig),
        "cause": sug.get("cause") or sug.get("explanation") or "causa proposta dall'LLM",
        "source": "distilled",
        "learned": f"{time.strftime('%Y-%m-%d')} via {sug.get('source', 'llm')} "
                   f"(confidence {conf}) -- da rivedere a mano",
    }
    if sug.get("recommend_emulator"):
        rule["recommend_emulator"] = sug["recommend_emulator"]
    if sug.get("settings"):
        rule["fix_suggestions"] = [{
            "description": (sug.get("explanation") or "impostazioni proposte")[:100],
            "settings": sug["settings"],
        }]
    return rule, "ok"


def _yq(s: str) -> str:
    """Scalare YAML single-quoted: i backslash del regex restano letterali (a
    differenza del double-quoted), si raddoppiano solo gli apici."""
    return str(s).replace("'", "''")


def _yaml_block(rule: dict) -> str:
    lines = [
        f"  # regola imparata automaticamente -- {rule.get('learned', '')}",
        f"  - match_log_pattern: '{_yq(rule['match_log_pattern'])}'",
        f"    cause: '{_yq(rule['cause'])}'",
        f"    source: distilled",
    ]
    if rule.get("recommend_emulator"):
        lines.append(f"    recommend_emulator: {rule['recommend_emulator']}")
    if rule.get("fix_suggestions"):
        lines.append("    fix_suggestions:")
        for fx in rule["fix_suggestions"]:
            lines.append(f"      - description: '{_yq(fx['description'])}'")
            lines.append(f"        settings: {json.dumps(fx['settings'])}")
    return "\n".join(lines) + "\n"


def append_rule(diag_key: str, rule: dict) -> dict:
    """Aggiunge la regola al file diagnostics, con backup. Ritorna {path, backup}.
    Verifica che il file resti YAML valido; se no, ripristina dal backup."""
    path = catalog.diagnostics_path(diag_key)
    backup = None
    if path.exists():
        backup = path.with_name(f"{path.name}.sudobat-bak-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(path, backup)
        text = path.read_text()
        if not text.endswith("\n"):
            text += "\n"
    else:
        text = ("# Regole diagnostiche (create dal loop di distillazione).\n"
                "rules:\n")

    new_text = text + _yaml_block(rule)
    path.write_text(new_text)

    # verifica: deve ricaricare come YAML valido, altrimenti rollback
    try:
        import yaml
        yaml.safe_load(new_text)
    except Exception as exc:
        if backup:
            shutil.copy2(backup, path)
        raise ValueError(f"append avrebbe rotto lo YAML, ripristinato il backup: {exc}")
    return {"path": str(path), "backup": str(backup) if backup else None}
