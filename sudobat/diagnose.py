"""Motore di diagnosi: incrocia l'ultimo lancio tracciato dall'hook, il log
dell'ultimo avvio (/userdata/system/logs/es_launch_std{out,err}.log -- generico,
scritto da configgen per qualunque emulatore) e il database preset/diagnostica,
per proporre dei fix. Sola lettura: non scrive nulla, nessuna applicazione
automatica -- quella resta un passo separato ed esplicito.
"""
import json
import re
from pathlib import Path

from . import catalog, hardware, logscan
from .identify import ps2, psx, switch

_STATE_DIR = Path(__file__).parent.parent / "state"
_LAST_LAUNCH_FILE = _STATE_DIR / "last_launch.json"
_STOP_LOG_FILE = _STATE_DIR / "last_launch.json.stop_log"

_LAUNCH_LOG_PATHS = [
    Path("/userdata/system/logs/es_launch_stderr.log"),
    Path("/userdata/system/logs/es_launch_stdout.log"),
]

# Sotto questa durata (secondi) tra gameStart e gameStop si sospetta un crash
# piuttosto che uno stop volontario dell'utente.
_CRASH_THRESHOLD_SECONDS = 15

# Sotto questa durata una sessione finita pulita e' "corta": troppo poco gioco per
# un giudizio pieno, ma abbastanza perche' valga la pena chiedere (magari hai
# smesso presto proprio perche' era ingiocabile).
_SHORT_SESSION_SECONDS = 60

# Emulatore (come compare nell'hook/batocera.conf) -> file diagnostics/<...>.yaml da usare.
_EMULATOR_TO_DIAGNOSTICS_KEY = {
    "pcsx2": "pcsx2",
    "lr-pcsx2": "pcsx2",
    "duckstation": "duckstation",
    "ryujinx-emu": "switch",
    "citron-emu": "switch",
    "eden-emu": "switch",
    "eden-pgo": "switch",
    "eden-nightly": "switch",
}

_IDENTIFIERS = {
    "ps2": ps2.extract_serial,
    "psx": psx.extract_serial,
}


def read_last_launch() -> dict | None:
    if not _LAST_LAUNCH_FILE.exists():
        return None
    return json.loads(_LAST_LAUNCH_FILE.read_text())


def read_last_stop() -> dict | None:
    if not _STOP_LOG_FILE.exists():
        return None
    lines = [l for l in _STOP_LOG_FILE.read_text().splitlines() if l.strip()]
    return json.loads(lines[-1]) if lines else None


def read_launch_log_tail(max_lines: int = 300) -> str:
    for path in _LAUNCH_LOG_PATHS:
        if path.exists():
            lines = path.read_text(errors="replace").splitlines()
            return "\n".join(lines[-max_lines:])
    return ""


def identify_game_id(system: str, emulator: str, rom_path: str, launch_ts: float) -> str | None:
    if system in _IDENTIFIERS:  # ps2/psx: serial estratto dal disco (canonico)
        return _IDENTIFIERS[system](rom_path)
    if system == "switch":
        # 1) match per nome-file nel catalogo: robusto, funziona con QUALUNQUE
        #    emulatore (Ryujinx non "tocca" le sue cartelle a ogni lancio, quindi
        #    l'euristica sulle cartelle Title ID da sola falliva su Ryujinx).
        gid = catalog.find_game_id_by_filename("switch", Path(rom_path).name)
        if gid:
            return gid
        # 2) fallback: osserva le cartelle Title ID create dagli emulatori yuzu-family
        return switch.guess_title_id(emulator, since_ts=launch_ts)
    return None


def collect_fixes(result: dict) -> list:
    """Uniforma i fix proposti dalla diagnosi in una lista
    [{source, description, settings}], da problemi noti del gioco + regole log.
    Condivisa tra CLI e UI."""
    fixes = []
    game = result.get("game")
    if game:
        for issue in game.get("known_issues", []):
            if issue.get("fix"):
                fixes.append({"source": "problema noto",
                              "description": issue.get("symptom", ""),
                              "settings": issue["fix"]})
    for rule in result.get("matched_diagnostic_rules", []):
        for sug in rule.get("fix_suggestions", []):
            if sug.get("settings"):
                fixes.append({"source": f"regola log: {rule.get('cause', '')}",
                              "description": sug.get("description", ""),
                              "settings": sug["settings"]})
    return fixes


def diagnose(assume_crash: bool = False) -> dict:
    """assume_crash=True: l'UTENTE ha detto che il gioco si e' chiuso da solo.
    E' il segnale che la macchina non puo' vedere (un crash dopo 20 minuti sembra
    identico a un'uscita voluta): si forza la lettura dei log emulatore come per
    un crash sospetto. Generico per qualunque sistema/emulatore."""
    launch = read_last_launch()
    if not launch:
        return {"error": "nessun lancio tracciato (hook non installato o mai lanciato un gioco)"}

    stop = read_last_stop()
    duration = None
    suspected_crash = None
    if stop and stop.get("timestamp") is not None and launch.get("timestamp") is not None:
        delta = stop["timestamp"] - launch["timestamp"]
        # solo uno stop SUCCESSIVO al lancio e' valido: uno stop negativo viene da
        # una sessione precedente (stop_log e' append-only), non da questo lancio.
        if delta >= 0:
            duration = delta
            suspected_crash = duration < _CRASH_THRESHOLD_SECONDS
    if assume_crash:
        suspected_crash = True

    system = launch.get("system", "")
    emulator = launch.get("emulator", "")
    rom_path = launch.get("rom", "")

    game_id = identify_game_id(system, emulator, rom_path, launch.get("timestamp", 0))
    game = catalog.find_game(system, game_id) if game_id else None

    log_tail = read_launch_log_tail()
    diag_key = _EMULATOR_TO_DIAGNOSTICS_KEY.get(emulator)
    matched_rules = []
    if diag_key:
        for rule in catalog.load_diagnostics(diag_key).get("rules", []):
            if re.search(rule["match_log_pattern"], log_tail, re.IGNORECASE):
                matched_rules.append(rule)

    # Analisi dei log SPECIFICI dell'emulatore (+ kernel): SudoBat riconosce da solo
    # i crash noti leggendo citron_log.txt / eden_log / Ryujinx logs / emulog, come
    # farebbe un umano. Vedi sudobat.logscan. Si attiva SOLO se c'e' un sospetto
    # crash: una sessione lunga e finita pulita non ha nulla da spiegare (evita i
    # falsi positivi da righe stale nel log).
    emulator_crashes = logscan.scan(emulator, diag_key) if (diag_key and suspected_crash) else []

    tier = hardware.profile().tier
    baseline_preset = None
    if game:
        baseline_preset = (game.get("presets") or {}).get(tier)

    return {
        "launch": launch,
        "stop": stop,
        "duration_seconds": duration,
        "suspected_crash": suspected_crash,
        "session_verdict": session_verdict(duration, suspected_crash, emulator_crashes),
        "game_id": game_id,
        "game": game,
        "hardware_tier": tier,
        "baseline_preset": baseline_preset,
        "matched_diagnostic_rules": matched_rules,
        "emulator_crashes": emulator_crashes,
    }


def session_verdict(duration, suspected_crash, emulator_crashes) -> str:
    """Classifica l'ultima sessione con i SOLI segnali universali (durata dall'hook,
    regole log imparate): niente pattern per-emulatore.

      'crash'   -> se ne occupa la diagnosi, inutile chiedere com'e' andata
      'clean'   -> finita regolarmente e giocata abbastanza: si chiede il giudizio
      'short'   -> finita regolarmente ma subito: si chiede comunque (magari hai
                   smesso perche' era ingiocabile -- solo tu puoi dirlo)
      'unknown' -> nessuno stop registrato (forse ancora in corso): non si giudica

    Il caso che la macchina NON vede -- crash tardivo con log muto -- lo copre la
    domanda diretta all'utente nel questionario (vedi diagnose(assume_crash=True))."""
    if suspected_crash or emulator_crashes:
        return "crash"
    if duration is None:
        return "unknown"
    if duration >= _SHORT_SESSION_SECONDS:
        return "clean"
    return "short"
