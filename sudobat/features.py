"""Legge da es_features.cfg (Batocera) le OPZIONI GRAFICHE di ogni emulatore/core.

E' la fonte che rende SudoBat portabile: invece di conoscere a mano 4 emulatori,
scopre da Batocera stessa, per QUALUNQUE emulatore, quali manopole grafiche esistono,
la loro chiave in batocera.conf e i valori ammessi gia' ordinati leggero->pesante.

Nessuna conoscenza per-emulatore scritta da Claude: solo un'euristica generale su
quali opzioni contano per le prestazioni (risoluzione/scala/filtri/blending/AA).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

# EmulationStation fonde TUTTI gli es_features*.cfg (l'ufficiale + quelli degli
# add-on, es. es_features_switch.cfg installato dal pacchetto Switch): quindi
# anche noi. Prima userdata (override dell'utente), poi il sistema.
_DIRS = [
    Path("/userdata/system/configs/emulationstation"),
    Path("/usr/share/emulationstation"),
]

# opzioni che incidono sul CARICO grafico (match su chiave o nome, case-insensitive)
_PERF_KW = ("resolution", "scale", "upscal", "supersampl", "internal", "render",
            "anisotrop", "blend", "bilinear", "antialias", "msaa", "ssaa", "fxaa", "smaa")
# l'asse DOMINANTE: la risoluzione/scala interna
_PRIMARY_KW = ("resolution", "scale", "upscal", "supersampl", "internal")

_roots_cache: list[ET.Element] | None = None

# '&' nudo non seguito da un'entita' XML valida: va escapato per il parser strict
_BARE_AMP = re.compile(r"&(?!amp;|lt;|gt;|quot;|apos;|#)")


def _parse_lenient(path: Path) -> ET.Element | None:
    """Parse XML; se fallisce riprova escapando gli '&' nudi. I cfg degli add-on
    sono spesso scritti a mano e ES li tollera: meglio leggerli che scartarli.
    Il file su disco NON viene mai modificato."""
    try:
        return ET.parse(path).getroot()
    except ET.ParseError:
        pass
    except OSError:
        return None
    try:
        return ET.fromstring(_BARE_AMP.sub("&amp;", path.read_text(errors="replace")))
    except (ET.ParseError, OSError):
        return None


def _roots() -> list[ET.Element]:
    global _roots_cache
    if _roots_cache is None:
        _roots_cache = []
        for d in _DIRS:
            for p in sorted(d.glob("es_features*.cfg")):
                root = _parse_lenient(p)
                if root is not None:
                    _roots_cache.append(root)
    return _roots_cache


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


def _numeric_choices(feat: ET.Element) -> list[tuple[str, str]] | None:
    """[(label, value_str), ...] ordinati per valore numerico crescente
    (= leggero->pesante). None se meno di 2 scelte numeriche."""
    num = [(c.get("name", ""), c.get("value", ""))
           for c in feat.findall("choice") if _is_number(c.get("value", ""))]
    if len(num) < 2:
        return None
    num.sort(key=lambda lv: float(lv[1]))
    return num


def _find_emulator(name: str) -> ET.Element | None:
    """Cerca l'emulatore in tutti i file caricati (vince il primo trovato:
    l'ordine e' userdata prima del sistema, come fa EmulationStation)."""
    for root in _roots():
        node = next((e for e in root.findall("emulator") if e.get("name") == name), None)
        if node is not None:
            return node
    return None


def _emulator_features(emulator: str, core: str = "") -> list[ET.Element]:
    """Tutti i <feature> validi per questo emulatore (+ core specifico se dato)."""
    node = _find_emulator(emulator)
    # fallback: a volte il 'core' e' registrato come emulatore top-level (standalone)
    if node is None and core:
        node = _find_emulator(core)
    if node is None:
        return []
    feats = list(node.findall("feature"))          # feature dirette dell'emulatore
    cores = node.find("cores")
    if cores is not None:
        match = next((c for c in cores.findall("core") if c.get("name") == core), None)
        # core specifico se lo troviamo, altrimenti unione di tutti i core
        feats += (match.findall(".//feature") if match is not None
                  else cores.findall(".//feature"))
    systems = node.find("systems")
    if systems is not None:
        feats += systems.findall(".//feature")
    return feats


def graphics_axes(emulator: str, core: str = "") -> dict:
    """{chiave_batocera: {"name": label, "choices": [(label,val)...ordinati],
                          "primary": bool}} per le opzioni grafiche di carico.
    {} se l'emulatore non ha opzioni note (es. molti emulatori 2D)."""
    axes: dict = {}
    for feat in _emulator_features(emulator, core):
        key = feat.get("value")
        if not key:
            continue
        name = feat.get("name", key)
        haystack = f"{key} {name}".lower()
        if not any(kw in haystack for kw in _PERF_KW):
            continue
        choices = _numeric_choices(feat)
        if not choices:
            continue
        if key in axes:
            continue
        axes[key] = {
            "name": name,
            "choices": choices,
            "primary": any(kw in haystack for kw in _PRIMARY_KW),
        }
    return axes
