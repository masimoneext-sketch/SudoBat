"""Profiling hardware: LEGGE i componenti che Batocera ha gia' rilevato al boot.

Niente lista di pattern-nome GPU, niente benchmark. I dati vengono da:
  - batocera-info   -> CPU (modello/core/freq), RAM
  - vulkaninfo      -> tipo GPU (INTEGRATED/DISCRETE) e VRAM del heap dedicato
  - batocera-vulkan -> nome GPU (+ fallback integrata/dedicata)

La fascia si deriva da segnali REALI: integrata vs dedicata, e per le dedicate la
VRAM vera. Le iGPU partono 'deboli' (un solo livello: non c'e' un segnale pulito per
distinguerle) e il loop dei flag corregge se un gioco gira meglio del previsto.
"""
import re
import subprocess
from dataclasses import dataclass


@dataclass
class HardwareProfile:
    cpu_model: str
    cpu_cores: int
    ram_mb: int
    gpu_name: str
    has_discrete_gpu: bool
    vram_mb: int
    tier: str


def _run(cmd: list) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=12).stdout
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return ""


def _batocera_info() -> dict:
    """{chiave: valore} da `batocera-info` (cio' che Batocera ha rilevato al boot)."""
    info = {}
    for line in _run(["batocera-info"]).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            info[k.strip()] = v.strip()
    return info


def _int(s: str, default: int = 0) -> int:
    m = re.search(r"\d+", s or "")
    return int(m.group()) if m else default


def _ram_mb(info: dict) -> int:
    # "Available Memory" = "13827/15834 MB" -> prendo il totale (dopo lo slash)
    val = info.get("Available Memory", "")
    if "/" in val:
        return _int(val.split("/", 1)[1])
    return _int(val)


def _gpu_name() -> str:
    n = _run(["batocera-vulkan", "defaultName"]).strip()
    return n or "unknown"


def _gpu_kind_and_vram() -> tuple[bool, int]:
    """(is_discrete, vram_mb) da segnali REALI. Per le iGPU la VRAM non e' indicativa
    (memoria condivisa) e non si usa; per le dGPU e' il heap dedicato vero."""
    out = _run(["vulkaninfo"])
    if "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU" in out:
        is_discrete = True
    elif "PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU" in out:
        is_discrete = False
    else:  # vulkaninfo non ha aiutato: fallback su batocera-vulkan
        is_discrete = _run(["batocera-vulkan", "hasDiscrete"]).strip().lower() == "true"
    # VRAM: solo per le dedicate ha senso (heap dedicato vero). Per le iGPU e'
    # memoria condivisa col sistema -> 0, per non spacciarla per VRAM.
    vram_mb = 0
    if is_discrete:
        sizes = [int(n) for n in re.findall(r"size\s*=\s*(\d{7,})", out)]
        vram_mb = max(sizes) // (1024 * 1024) if sizes else 0
    return is_discrete, vram_mb


def _classify_tier(is_discrete: bool, vram_mb: int) -> str:
    """Fascia da segnali reali. Soglie VRAM = regola generale (non pattern-nome),
    che il loop dei flag puo' comunque smentire per il singolo gioco."""
    if not is_discrete:
        return "igpu-weak"          # iGPU: un solo livello, start conservativo
    if not vram_mb:
        return "dgpu-mid"           # dedicata ma VRAM ignota: livello medio prudente
    if vram_mb < 4000:
        return "dgpu-entry"
    if vram_mb <= 8500:
        return "dgpu-mid"
    return "dgpu-high"


def profile() -> HardwareProfile:
    info = _batocera_info()
    is_discrete, vram_mb = _gpu_kind_and_vram()
    return HardwareProfile(
        cpu_model=info.get("CPU Model", "unknown"),
        cpu_cores=_int(info.get("CPU Cores", "")) or 1,
        ram_mb=_ram_mb(info),
        gpu_name=_gpu_name(),
        has_discrete_gpu=is_discrete,
        vram_mb=vram_mb,
        tier=_classify_tier(is_discrete, vram_mb),
    )
