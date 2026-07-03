"""Registra SudoBat nel menu PORTS di EmulationStation, con logo e video animato.

ES mostra l'artwork dei port leggendo /userdata/roms/ports/gamelist.xml. Questo
script:
  1. copia il launcher SudoBat.sh in /userdata/roms/ports/
  2. copia il logo in ports/images/sudobat.png
  3. genera (se possibile) il video animato ports/videos/sudobat.mp4
  4. aggiunge o AGGIORNA solo la voce di SudoBat nel gamelist, preservando gli
     altri port gia' presenti (RGSX, RomsOrganizer, ...).

Idempotente, nessuna dipendenza esterna oltre a quanto gia' su Batocera.
Uso: python3 -m tools.register_port  (dalla radice del repo).
"""
from __future__ import annotations

import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PORTS = Path(os.environ.get("SUDOBAT_PORTS_DIR", "/userdata/roms/ports"))
LAUNCHER_SRC = REPO / "scripts" / "SudoBat.sh"
LAUNCHER_PATH = "./SudoBat.sh"
IMG_REL = "./images/sudobat.png"
VIDEO_REL = "./videos/sudobat.mp4"
SRC_IMG = REPO / "assets" / "logo.png"
DESC = ("Tuning grafico per-gioco consapevole dell'hardware: profila la macchina, "
        "identifica il gioco, diagnostica crash/scatti dell'ultimo lancio e applica "
        "i preset migliori in batocera.conf, con backup automatico.")


def _set(elem: ET.Element, tag: str, text: str) -> None:
    child = elem.find(tag)
    if child is None:
        child = ET.SubElement(elem, tag)
    child.text = text


def main() -> int:
    PORTS.mkdir(parents=True, exist_ok=True)

    # 1) launcher
    if LAUNCHER_SRC.is_file():
        dest = PORTS / "SudoBat.sh"
        shutil.copy2(LAUNCHER_SRC, dest)
        dest.chmod(0o755)

    # 2) immagine
    if SRC_IMG.is_file():
        (PORTS / "images").mkdir(parents=True, exist_ok=True)
        shutil.copy2(SRC_IMG, PORTS / "images" / "sudobat.png")

    # 3) video animato (best-effort)
    try:
        from . import make_preview
        make_preview.main()
    except Exception as e:
        print("[register_port] video saltato:", e)

    # 4) gamelist
    gl = PORTS / "gamelist.xml"
    if gl.is_file():
        try:
            tree = ET.parse(gl)
            root = tree.getroot()
        except ET.ParseError:
            root = ET.Element("gameList")
            tree = ET.ElementTree(root)
    else:
        root = ET.Element("gameList")
        tree = ET.ElementTree(root)

    game = None
    for g in root.findall("game"):
        p = (g.findtext("path") or "").strip()
        if p in (LAUNCHER_PATH, "SudoBat.sh", "./SudoBat.sh"):
            game = g
            break
    if game is None:
        game = ET.SubElement(root, "game")

    _set(game, "path", LAUNCHER_PATH)
    _set(game, "name", "SudoBat")
    _set(game, "desc", DESC)
    if SRC_IMG.is_file():
        _set(game, "image", IMG_REL)
        _set(game, "thumbnail", IMG_REL)
        _set(game, "marquee", IMG_REL)
    if (PORTS / "videos" / "sudobat.mp4").is_file():
        _set(game, "video", VIDEO_REL)

    tree.write(gl, encoding="utf-8", xml_declaration=True)
    print("[register_port] gamelist aggiornato:", gl)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
