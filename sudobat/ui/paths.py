"""Percorsi dei file di stato della UI (config controller, impostazioni).

Come RGSX/RomsOrganizer, i salvataggi della UI stanno fuori dal repo, in
/userdata/saves, cosi' sopravvivono a un aggiornamento dell'app e non sporcano
il git. Sovrascrivibili via env per i test in locale.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_SAVES_DIR = "/userdata/saves/ports/sudobat"


def saves_dir() -> Path:
    d = Path(os.environ.get("SUDOBAT_SAVES_DIR", DEFAULT_SAVES_DIR))
    d.mkdir(parents=True, exist_ok=True)
    return d


def controls_path() -> Path:
    return saves_dir() / "controls.json"


def settings_path() -> Path:
    return saves_dir() / "settings.json"


def load_settings() -> dict:
    p = settings_path()
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {"lang": "it"}


def save_settings(data: dict) -> None:
    settings_path().write_text(json.dumps(data, indent=2, ensure_ascii=False),
                               encoding="utf-8")
