"""Livello LLM OPZIONALE (Groq) -- il "turbo" che si accende solo per i crash che
il motore offline NON riconosce. Il cuore di SudoBat resta offline: se manca la
chiave, manca internet o Groq risponde male, qui si ritorna None e il resto del
programma continua col motore a regole.

Due regole non negoziabili, incastonate nel codice:
  1. VERIFICA: l'LLM puo' proporre solo chiavi che SudoBat gia' conosce
     (tuning.known_keys + chiavi delle regole diagnostiche). Le chiavi inventate
     si scartano PRIMA di mostrarle o applicarle.
  2. MAI da solo: la proposta esce come suggerimento, poi passa dal solito
     percorso (backup + scelta dell'utente). Qui dentro non si scrive niente.

Solo libreria standard (urllib): su Batocera non c'e' pip.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from . import tuning

# Store della chiave: file nascosto, messo a veto nella condivisione SMB da
# smbguard (i permessi 600 da soli NON bastano: Samba serve /userdata come
# root agli ospiti della LAN). Il groq_key.txt documentato in GROQ_SETUP e'
# solo un punto di consegna: appena visto viene importato qui e cancellato.
_KEY_FILE = Path(__file__).parent.parent / "state" / ".groq_key"
_DROP_FILE = Path(__file__).parent.parent / "state" / "groq_key.txt"
_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
# Il nome del modello Groq puo' cambiare nel tempo: sovrascrivibile con GROQ_MODEL.
_DEFAULT_MODEL = "llama-3.3-70b-versatile"

_SYSTEM_PROMPT = (
    "Sei il cervello diagnostico di SudoBat, uno strumento per Batocera.linux. "
    "Ragioni SOLO sull'emulazione in Batocera: emulatori, crash, impostazioni grafiche. "
    "Ti do hardware, emulatore, gioco, la coda del log di crash e la LISTA DELLE CHIAVI "
    "DI CONFIG PERMESSE. Devi:\n"
    "1) spiegare la causa probabile del crash in una frase;\n"
    "2) proporre modifiche SOLO usando le chiavi permesse (mai altre);\n"
    "3) se l'unica vera soluzione e' cambiare emulatore (SudoBat non puo' farlo), "
    "indicarlo in recommend_emulator;\n"
    "4) indicare in log_signature una BREVE stringa COPIATA ALLA LETTERA dal log "
    "che identifica questo crash (verra' usata per riconoscerlo in futuro): deve "
    "esistere davvero nel log, non inventarla.\n"
    "Rispondi SOLO con JSON valido, senza testo attorno, con questo schema:\n"
    '{"cause": str, "explanation": str, "proposed_settings": {chiave: valore}, '
    '"recommend_emulator": str|null, "log_signature": str, "confidence": number 0..1}'
)


def _normalize(key: str) -> str:
    """Pulizia + validazione di forma. Solleva ValueError se non sembra una
    chiave Groq: meglio rifiutare subito una chiave incollata male che fallire
    al primo crash."""
    key = (key or "").strip().strip('"').strip("'")
    if not key or any(c.isspace() for c in key) or len(key) < 20:
        raise ValueError("chiave non valida: attesa una chiave Groq intera, senza spazi")
    if not key.startswith("gsk_"):
        raise ValueError("chiave non valida: le chiavi API di Groq iniziano con 'gsk_'")
    return key


def ingest_plaintext(*, guard: bool = True) -> Path | None:
    """Se l'utente ha depositato state/groq_key.txt (la via facile via SMB,
    docs/GROQ_SETUP*), lo importa nello store nascosto e CANCELLA l'originale
    in chiaro: la finestra di esposizione sulla rete finisce qui. Ritorna lo
    store se ha importato, None altrimenti (file assente o malformato: un
    file malformato resta li', visibile, cosi' l'utente capisce e corregge).
    Con guard=True prova anche ad alzare subito il veto SMB (best-effort)."""
    if not _DROP_FILE.is_file():
        return None
    try:
        key = _normalize(_DROP_FILE.read_text())
    except (OSError, ValueError):
        return None
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _KEY_FILE.write_text(key + "\n")
    os.chmod(_KEY_FILE, 0o600)
    _DROP_FILE.unlink()
    if guard:
        from . import smbguard
        smbguard.ensure()
    return _KEY_FILE


def api_key() -> str | None:
    """Chiave Groq: variabile GROQ_API_KEY, altrimenti lo store state/.groq_key
    (importando al volo un eventuale groq_key.txt depositato dall'utente).
    None se assente (l'utente deve procurarsela gratis su console.groq.com)."""
    env = os.environ.get("GROQ_API_KEY", "").strip()
    if env:
        return env
    ingest_plaintext()
    if _KEY_FILE.is_file():
        val = _KEY_FILE.read_text().strip()
        if val:
            return val
    return None


def available() -> bool:
    return api_key() is not None


def _mask(key: str) -> str:
    """Ultimi 4 caratteri della chiave, per mostrarla senza esporla."""
    return f"···{key[-4:]}" if len(key) >= 8 else "···"


def key_status() -> dict:
    """Da dove viene la chiave (se c'e') e una versione mascherata mostrabile.
    {configured, source ('env'|path|None), masked}."""
    env = os.environ.get("GROQ_API_KEY", "").strip()
    if env:
        return {"configured": True, "source": "env", "masked": _mask(env)}
    ingest_plaintext()
    if _KEY_FILE.is_file():
        val = _KEY_FILE.read_text().strip()
        if val:
            return {"configured": True, "source": str(_KEY_FILE), "masked": _mask(val)}
    return {"configured": False, "source": None, "masked": ""}


def save_key(key: str) -> Path:
    """Salva la chiave PERSONALE dell'utente nello store nascosto
    state/.groq_key (gitignorato, permessi 600, messo a veto SMB da smbguard).
    Ripulisce anche un eventuale groq_key.txt in chiaro rimasto in giro."""
    key = _normalize(key)
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _KEY_FILE.write_text(key + "\n")
    os.chmod(_KEY_FILE, 0o600)
    if _DROP_FILE.is_file():
        _DROP_FILE.unlink()
    return _KEY_FILE


def remove_key() -> bool:
    """Elimina la chiave salvata (store nascosto e/o groq_key.txt in chiaro).
    True se c'era qualcosa. Non tocca l'eventuale env."""
    found = False
    for f in (_KEY_FILE, _DROP_FILE):
        if f.is_file():
            f.unlink()
            found = True
    return found


def test_key() -> tuple[bool, str]:
    """Chiamata minima a Groq per verificare che la chiave funzioni davvero
    (richiede rete). Ritorna (ok, messaggio per l'utente)."""
    if not available():
        return False, "nessuna chiave configurata (cli: key set <CHIAVE>)"
    content = _call_groq({"test": "rispondi solo con {\"cause\": \"ok\"}"}, timeout=15)
    if content is None:
        return False, ("chiamata fallita: chiave non valida, rete assente o "
                       "Groq irraggiungibile")
    return True, "chiave valida: il turbo e' pronto"


def allowed_keys(system: str, emulator: str) -> set:
    """Confine di sicurezza: SOLO le chiavi del modello di tuning DELL'EMULATORE
    indicato -- cosi' sono corrette per la famiglia (a un crash Citron/yuzu non si
    offrono chiavi ryu_* di Ryujinx, e viceversa)."""
    return set(tuning.known_keys(emulator))


def _call_groq(context: dict, *, timeout: float = 20.0) -> str | None:
    """Chiamata HTTP a Groq. None su qualsiasi problema (niente chiave/rete/errore)."""
    key = api_key()
    if not key:
        return None
    user_msg = json.dumps(context, ensure_ascii=False, indent=2)
    body = json.dumps({
        "model": os.environ.get("GROQ_MODEL", _DEFAULT_MODEL),
        "temperature": 0.2,
        "max_tokens": 800,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    }).encode("utf-8")
    req = urllib.request.Request(
        _ENDPOINT, data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            # senza uno User-Agent "normale" Cloudflare davanti a Groq blocca (403/1010)
            "User-Agent": "SudoBat/0.1 (Batocera)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except (urllib.error.URLError, KeyError, IndexError, ValueError, TimeoutError, OSError):
        return None


def _extract_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    m = re.search(r"\{.*\}", text or "", re.DOTALL)  # primo blocco {...} come fallback
    if m:
        try:
            return json.loads(m.group(0))
        except ValueError:
            return None
    return None


def verify(raw: dict, system: str, emulator: str) -> dict:
    """Filtra la risposta dell'LLM contro il confine di sicurezza. Ritorna un
    suggerimento pulito: solo chiavi permesse in 'settings', le altre elencate in
    'rejected_keys' cosi' e' trasparente cosa e' stato scartato e perche'."""
    allowed = allowed_keys(system, emulator)
    valid_values = tuning.known_values(emulator)
    proposed = raw.get("proposed_settings") or {}
    settings, rejected = {}, []
    for k, v in proposed.items():
        if k not in allowed:
            rejected.append(f"{k} (chiave sconosciuta)")
        elif k in valid_values and str(v) not in valid_values[k]:
            rejected.append(f"{k}={v} (valore fuori da quelli vagliati: {sorted(valid_values[k])})")
        else:
            settings[k] = v
    return {
        "source": f"groq:{os.environ.get('GROQ_MODEL', _DEFAULT_MODEL)}",
        "cause": str(raw.get("cause", "")).strip(),
        "explanation": str(raw.get("explanation", "")).strip(),
        "settings": settings,
        "rejected_keys": rejected,
        "recommend_emulator": raw.get("recommend_emulator") or None,
        "log_signature": str(raw.get("log_signature", "")).strip(),
        "confidence": raw.get("confidence"),
    }


def ask_about_crash(context: dict, system: str, emulator: str) -> dict | None:
    """Interroga Groq su un crash sconosciuto e ritorna un suggerimento VERIFICATO,
    oppure None se il turbo non e' disponibile o la risposta e' inutilizzabile.
    NON applica nulla."""
    context = dict(context)
    context["allowed_config_keys"] = sorted(allowed_keys(system, emulator))
    content = _call_groq(context)
    if content is None:
        return None
    raw = _extract_json(content)
    if not raw:
        return None
    return verify(raw, system, emulator)
