"""Enumera i sistemi VERI presenti su questa Batocera.

SudoBat li scopre DA SOLO, leggendo la realta' della macchina:
  - quali sistemi hai  -> le cartelle con giochi in /userdata/roms
  - come si chiamano    -> il <fullname> in es_systems.cfg (config di Batocera)

Niente lista ne' nomi scritti a mano da Claude. Se un sistema non e' in
es_systems.cfg, si usa l'id della cartella cosi' com'e'.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ROMS_DIR = Path("/userdata/roms")

# es_systems.cfg di Batocera: prima la versione utente (se personalizzata), poi
# quella di sistema. E' Batocera a dire nomi ed elenco, non io.
_ES_SYSTEMS_PATHS = [
    Path("/userdata/system/configs/emulationstation/es_systems.cfg"),
    Path("/usr/share/emulationstation/es_systems.cfg"),
]

# cartelle di metadati dentro roms/, non sistemi
_META_DIRS = {"images", "media", "manuals", "videos", "bios"}

_fullnames_cache: dict[str, str] | None = None


def _fullnames() -> dict[str, str]:
    """{id_sistema: nome_leggibile} letto da es_systems.cfg di Batocera."""
    global _fullnames_cache
    if _fullnames_cache is not None:
        return _fullnames_cache
    names: dict[str, str] = {}
    for path in _ES_SYSTEMS_PATHS:
        if not path.exists():
            continue
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        for s in root.findall(".//system"):
            name = s.findtext("name")
            full = s.findtext("fullname")
            if name and full and name not in names:
                names[name] = full
    _fullnames_cache = names
    return names


def _has_games(folder: Path) -> bool:
    """True se la cartella contiene almeno un file-gioco (esclusi metadati)."""
    try:
        for p in folder.iterdir():
            if p.is_file() and not p.name.startswith(".") \
               and p.name != "gamelist.xml" and not p.name.endswith(".txt"):
                return True
    except OSError:
        pass
    return False


def list_systems() -> list[tuple[str, str]]:
    """(id, nome_leggibile) per ogni sistema con giochi in /userdata/roms.
    Il nome viene da es_systems.cfg; se manca, si usa l'id. [] se roms non esiste."""
    if not ROMS_DIR.is_dir():
        return []
    names = _fullnames()
    out = []
    for d in sorted(ROMS_DIR.iterdir()):
        if d.is_dir() and d.name not in _META_DIRS and _has_games(d):
            out.append((d.name, names.get(d.name, d.name)))
    return out
