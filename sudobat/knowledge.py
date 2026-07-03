# SudoBat — Copyright © 2026 Marco Simone. PolyForm Noncommercial License 1.0.0.
# Uso personale/non commerciale libero; uso commerciale solo con licenza separata. Vedi LICENSE.md.
"""Download della conoscenza COMMUNITY (repo pubblico sudobat-knowledge).

Il download e' innocuo e non richiede consenso (e' l'upload che sta dietro
l'opt-in, vedi share.py). I file scaricati vivono in sudobat/data/community/
(namespace separato: MAI mescolati col catalogo locale validato dall'utente).
Ogni YAML viene validato prima di essere scritto: un repo remoto corrotto o
malevolo non deve mai rompere il tool ne' iniettare chiavi strane.
"""
from __future__ import annotations

import io
import os
import re
import tarfile
import tempfile
import urllib.request
from pathlib import Path

import yaml

from . import catalog

_DEFAULT_TARBALL = ("https://codeload.github.com/masimoneext-sketch/"
                    "sudobat-knowledge/tar.gz/refs/heads/master")
_SYSTEM_RE = re.compile(r"^[a-z0-9_]{2,16}$")
_KEY_RE = re.compile(r"^[a-z0-9_]{2,48}$")
_MAX_YAML_BYTES = 512 * 1024  # un catalogo per-sistema non ha motivo di superarlo


def community_dir() -> Path:
    return catalog._DATA_DIR / "community"


def _tarball_url() -> str:
    return os.environ.get("SUDOBAT_KNOWLEDGE_TARBALL", _DEFAULT_TARBALL)


def _valid_settings(settings) -> bool:
    if not isinstance(settings, dict) or not 1 <= len(settings) <= 12:
        return False
    for k, v in settings.items():
        if not isinstance(k, str) or not _KEY_RE.match(k):
            return False
        if not isinstance(v, (str, int, float, bool)) or len(str(v)) > 32:
            return False
    return True


def _sanitize_system_yaml(text: str) -> dict | None:
    """Valida e ripulisce un YAML community. Ritorna il dict pulito o None.
    Struttura attesa: games -> <game_id> -> {title, tiers -> <tier> -> [entry]}
    dove entry = {settings, confirmations, emulator?, core?}."""
    if len(text.encode()) > _MAX_YAML_BYTES:
        return None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("games"), dict):
        return None
    clean_games = {}
    for gid, info in data["games"].items():
        if not isinstance(gid, str) or not (2 <= len(gid) <= 32) or not isinstance(info, dict):
            continue
        tiers = info.get("tiers")
        if not isinstance(tiers, dict):
            continue
        clean_tiers = {}
        for tier, entries in tiers.items():
            if not isinstance(tier, str) or not isinstance(entries, list):
                continue
            clean_entries = []
            for e in entries[:5]:  # difensivo: mai piu' di 5 set per fascia
                if not isinstance(e, dict) or not _valid_settings(e.get("settings")):
                    continue
                conf = e.get("confirmations")
                clean_entries.append({
                    "settings": e["settings"],
                    "confirmations": int(conf) if isinstance(conf, int) and conf > 0 else 1,
                    "emulator": str(e.get("emulator", ""))[:24],
                    "core": str(e.get("core", ""))[:24],
                })
            if clean_entries:
                clean_tiers[tier] = clean_entries
        if clean_tiers:
            clean_games[gid] = {"title": str(info.get("title", ""))[:120],
                                "tiers": clean_tiers}
    return {"games": clean_games} if clean_games else None


def install_from_files(named_texts: dict) -> dict:
    """{nomefile: testo_yaml} -> valida e scrive in data/community/. Ritorna
    {files, games}. Usata da update() e dal selftest (fixture locali)."""
    out_dir = community_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    files = games = 0
    for name, text in named_texts.items():
        stem = Path(name).stem
        if not _SYSTEM_RE.match(stem):
            continue
        clean = _sanitize_system_yaml(text)
        if not clean:
            continue
        (out_dir / f"{stem}.yaml").write_text(
            yaml.safe_dump(clean, allow_unicode=True, sort_keys=False))
        files += 1
        games += len(clean["games"])
    return {"files": files, "games": games}


def update(timeout: float = 30.0) -> dict:
    """Scarica il tarball del repo conoscenza e installa i cataloghi community.
    Nessun git richiesto. Ritorna {files, games}. Solleva su rete assente."""
    req = urllib.request.Request(_tarball_url(), headers={"User-Agent": "SudoBat"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        blob = resp.read(16 * 1024 * 1024)  # cap 16MB: un tarball di YAML non li supera
    texts = {}
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        for member in tar.getmembers():
            # solo file regolari systems/*.yaml, ignora tutto il resto (niente
            # symlink/path traversal: leggiamo il contenuto, mai estraiamo su disco)
            parts = Path(member.name).parts
            if (member.isfile() and len(parts) == 3 and parts[1] == "systems"
                    and parts[2].endswith(".yaml") and member.size < _MAX_YAML_BYTES):
                fh = tar.extractfile(member)
                if fh:
                    texts[parts[2]] = fh.read().decode("utf-8", errors="replace")
    return install_from_files(texts)
