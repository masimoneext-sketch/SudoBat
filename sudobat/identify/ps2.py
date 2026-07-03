"""Identificazione gioco PS2: legge il serial da SYSTEM.CNF dentro l'ISO9660.

Nessuna cifratura in mezzo: un .iso PS2 e' un filesystem ISO9660 semplice,
`bsdtar` lo legge direttamente senza bisogno di parser dedicati.
"""
import re
import subprocess

_BOOT_LINE_RE = re.compile(r"BOOT2?\s*=\s*cdrom0?:\\+([A-Z]{4}_\d{3}\.\d{2})")


def read_system_cnf(iso_path: str) -> str | None:
    try:
        result = subprocess.run(
            ["bsdtar", "-xf", iso_path, "-O", "SYSTEM.CNF"],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def extract_serial(iso_path: str) -> str | None:
    content = read_system_cnf(iso_path)
    if not content:
        return None
    match = _BOOT_LINE_RE.search(content)
    if not match:
        return None
    return match.group(1).replace("_", "-")
