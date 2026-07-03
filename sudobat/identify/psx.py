"""Identificazione gioco PSX: estrae il CD grezzo dal .chd (chdman), ricostruisce
un'immagine ISO9660 leggibile de-interleaving i settori MODE2/2352 (offset dati 24,
2048 byte utili per settore), poi legge SYSTEM.CNF come per PS2.

Pipeline testata su "Crash Bandicoot (Europe).chd" -> serial reale SCES-00344.
"""
import re
import subprocess
import tempfile
from pathlib import Path

_SECTOR_SIZE = 2352
_MODE2_FORM1_DATA_OFFSET = 24
_MODE2_FORM1_DATA_LEN = 2048
_BOOT_LINE_RE = re.compile(r"BOOT2?\s*=\s*cdrom0?:\\+([A-Z]{4}_\d{3}\.\d{2})")


def _extract_cd(chd_path: str, out_dir: Path) -> Path | None:
    bin_path = out_dir / "track.bin"
    cue_path = out_dir / "track.cue"
    try:
        subprocess.run(
            ["chdman", "extractcd", "-i", chd_path, "-o", str(cue_path), "-ob", str(bin_path)],
            capture_output=True, text=True, timeout=120, check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    return bin_path if bin_path.exists() else None


def _deinterleave(bin_path: Path, iso_path: Path) -> None:
    with open(bin_path, "rb") as src, open(iso_path, "wb") as dst:
        while True:
            sector = src.read(_SECTOR_SIZE)
            if len(sector) < _SECTOR_SIZE:
                break
            start = _MODE2_FORM1_DATA_OFFSET
            dst.write(sector[start:start + _MODE2_FORM1_DATA_LEN])


def read_system_cnf(chd_path: str) -> str | None:
    with tempfile.TemporaryDirectory(prefix="sudobat-psx-") as tmp:
        tmp_dir = Path(tmp)
        bin_path = _extract_cd(chd_path, tmp_dir)
        if bin_path is None:
            return None
        iso_path = tmp_dir / "track.iso"
        _deinterleave(bin_path, iso_path)
        result = subprocess.run(
            ["bsdtar", "-xf", str(iso_path), "-O", "SYSTEM.CNF"],
            capture_output=True, text=True, timeout=30,
        )
    if result.returncode != 0:
        return None
    return result.stdout


def extract_serial(chd_path: str) -> str | None:
    content = read_system_cnf(chd_path)
    if not content:
        return None
    match = _BOOT_LINE_RE.search(content)
    if not match:
        return None
    return match.group(1).replace("_", "-")
