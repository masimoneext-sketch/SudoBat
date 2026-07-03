"""Caricamento del database di preset/diagnostica (file YAML in sudobat/data/).

Il catalogo NON e' scritto a mano: parte vuoto e si popola da solo quando un set
da' all'utente un'esperienza validata come buona (record_validated). Ogni voce porta
la provenienza (chi/quando) e la fascia hardware per cui vale."""
import time
from pathlib import Path

import yaml

_DATA_DIR = Path(__file__).parent / "data"


def load_system_catalog(system: str) -> dict:
    """Carica sudobat/data/systems/<system>.yaml. {} se il sistema non ha catalogo."""
    path = _DATA_DIR / "systems" / f"{system}.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def diagnostics_path(emulator: str) -> Path:
    """Percorso del file diagnostics per una chiave (esista o no). Serve al loop di
    distillazione per aggiungere regole imparate."""
    return _DATA_DIR / "diagnostics" / f"{emulator}.yaml"


def load_diagnostics(emulator: str) -> dict:
    """Carica sudobat/data/diagnostics/<emulator>.yaml. {} se non esistono regole."""
    path = diagnostics_path(emulator)
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def find_game(system: str, game_id: str) -> dict | None:
    catalog = load_system_catalog(system)
    return (catalog.get("games") or {}).get(game_id)


def find_game_id_by_filename(system: str, filename: str) -> str | None:
    """Trova il game_id nel catalogo dal nome-file della ROM, via aliases_filename.
    Robusto e indipendente dall'emulatore (non dipende da cartelle create a runtime)."""
    games = (load_system_catalog(system).get("games") or {})
    for gid, info in games.items():
        if filename in (info.get("aliases_filename") or []):
            return gid
    return None


def get_profiles(system: str, game_id: str, tier: str) -> list:
    """Profili grafici selezionabili per un gioco+fascia hardware. Lista di dict
    {name, desc, recommended, settings}. SudoBat li propone TUTTI e lascia scegliere
    all'utente, marcando il consigliato. [] se il gioco non ha profili per la fascia."""
    game = find_game(system, game_id)
    if not game:
        return []
    return (game.get("profiles") or {}).get(tier) or []


def community_sets(system: str, game_id: str, tier: str) -> list:
    """Set validati dalla COMMUNITY (scaricati da sudobat-knowledge in
    data/community/) per gioco+fascia. Lista di {settings, confirmations,
    emulator, core}. [] se non c'e' nulla. Separati dal catalogo locale:
    nel rerank gli esiti dell'utente vincono sempre."""
    path = _DATA_DIR / "community" / f"{system}.yaml"
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return []
    game = (data.get("games") or {}).get(game_id) or {}
    return list((game.get("tiers") or {}).get(tier) or [])


def validated_set(system: str, game_id: str, tier: str) -> dict | None:
    """Il set che l'utente ha confermato dare una BUONA esperienza per questo
    gioco su questa fascia hardware. None se non c'e' ancora (catalogo si popola
    solo dall'esperienza reale). E' conoscenza guadagnata, non congettura."""
    game = find_game(system, game_id)
    if not game:
        return None
    entry = (game.get("validated") or {}).get(tier)
    return (entry or {}).get("settings")


def record_validated(system: str, game_id: str, game_title: str, tier: str,
                     settings: dict, flags: dict) -> Path:
    """Chiude il cerchio: SudoBat scrive DA SOLO in catalogo che questo set ha dato
    una buona esperienza a questo gioco su questa fascia hardware. Con provenienza
    (utente + data) e i flag che l'hanno confermata. Cosi' la prossima volta il gioco
    parte gia' col set che ha funzionato davvero. Ritorna il path del catalogo scritto."""
    path = _DATA_DIR / "systems" / f"{system}.yaml"
    data = load_system_catalog(system) or {}
    games = data.get("games") or {}
    entry = games.get(game_id) or {}
    if game_title:
        entry["title"] = game_title
    validated = entry.get("validated") or {}
    validated[tier] = {
        "settings": settings,
        "by": "user",
        "when": time.strftime("%Y-%m-%d %H:%M:%S"),
        "flags": flags,
    }
    entry["validated"] = validated
    games[game_id] = entry
    data["games"] = games

    header = (
        f"# Catalogo giochi {system.upper()}. Schema in PRESET_SCHEMA.md.\n"
        f"# POPOLATO DA SUDOBAT, non a mano: ogni voce 'validated' e' un set che ha\n"
        f"# dato una BUONA esperienza all'utente su quella fascia hardware (provenienza\n"
        f"# + data + flag). Conoscenza guadagnata sul campo, non congettura.\n"
    )
    path.write_text(header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    return path
