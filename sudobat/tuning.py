"""Motore di tuning GENERICO e PORTABILE: genera i set grafici (Massima fluidita'
/ Bilanciato / Qualita') per QUALUNQUE gioco su QUALUNQUE emulatore.

Non conosce piu' gli emulatori a mano: legge da Batocera (es_features.cfg, via
sudobat.features) le manopole grafiche dell'emulatore in uso e i loro valori gia'
ordinati leggero->pesante. La fascia hardware sceglie una finestra di 3 set;
il consigliato e' centrato sulla fascia/pesantezza. Gli esiti reali (outcomes) e i
flag dell'utente lo affinano. Nessun preset scritto a mano da Claude.
"""
from . import catalog, features, outcomes

_NAMES = ["Massima fluidita'", "Bilanciato", "Qualita'"]

# fascia hardware -> posizione centrale come FRAZIONE della scala (0=piu' leggero,
# 1=piu' pesante). Regola generale, indipendente dall'emulatore.
_TIER_FRAC = {"igpu-weak": 0.25, "igpu-strong": 0.45, "dgpu-entry": 0.45,
              "dgpu-mid": 0.65, "dgpu-high": 0.85}
# pesantezza del gioco: sposta il centro (piu' pesante -> set piu' leggeri)
_HEAVINESS_SHIFT = {"light": 0.10, "medium": 0.0, "heavy": -0.05, "very_heavy": -0.15}

# assi secondari che accompagnano la risoluzione (set piu' ricchi, ma sobri)
_SECONDARY_KW = ("anisotrop", "blend")


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(v, hi))


def _primary_axis(axes: dict):
    """(chiave, choices) dell'asse dominante (risoluzione/scala): il primary con
    piu' scelte. None se l'emulatore non ha un asse di risoluzione numerico."""
    prim = [(k, a["choices"]) for k, a in axes.items() if a.get("primary")]
    return max(prim, key=lambda kc: len(kc[1])) if prim else None


def _secondary_axes(axes: dict, primary_key: str) -> list:
    """Fino a un asse per famiglia in _SECONDARY_KW (es. anisotropico, blending)."""
    out = []
    for kw in _SECONDARY_KW:
        for k, a in axes.items():
            if k != primary_key and kw in f"{k} {a['name']}".lower():
                out.append((k, a["choices"]))
                break
    return out


def _build_set(idx: int, res_key: str, res_choices: list, secondary: list, n: int) -> dict:
    """Un set al gradino idx della scala risoluzione, con gli assi secondari alla
    stessa posizione proporzionale. Etichette e valori vengono da es_features."""
    settings = {res_key: res_choices[idx][1]}
    parts = [res_choices[idx][0]]
    for sk, sch in secondary:
        j = round(idx / (n - 1) * (len(sch) - 1)) if n > 1 else 0
        settings[sk] = sch[j][1]
        parts.append(sch[j][0])
    return {"settings": settings, "desc": " · ".join(parts)}


def generate_profiles(emulator: str, tier: str, heaviness: str = "medium", core: str = "") -> list:
    """I 3 set per emulatore+fascia+pesantezza, costruiti dai valori VERI letti da
    Batocera. [] se l'emulatore non ha un asse grafico numerico (molti sistemi 2D)."""
    axes = features.graphics_axes(emulator, core)
    primary = _primary_axis(axes)
    if not primary:
        return []
    res_key, res_choices = primary
    n = len(res_choices)
    secondary = _secondary_axes(axes, res_key)

    frac = _TIER_FRAC.get(tier, 0.30) + _HEAVINESS_SHIFT.get(heaviness, 0.0)
    center = _clamp(round(frac * (n - 1)), 0, n - 1)
    lo = _clamp(center - 1, 0, max(0, n - 3))
    window = [i for i in (lo, lo + 1, lo + 2) if i < n]

    out = []
    for pos, idx in enumerate(window):
        s = _build_set(idx, res_key, res_choices, secondary, n)
        out.append({
            "name": _NAMES[pos] if pos < len(_NAMES) else f"Set {pos + 1}",
            "recommended": (idx == center),
            "desc": s["desc"],
            "settings": s["settings"],
            "generated": True,
        })
    return out


def step_index_of(emulator: str, settings: dict, core: str = "") -> int:
    """Indice sull'asse risoluzione corrispondente a questi settings. -1 se n/d."""
    axes = features.graphics_axes(emulator, core)
    primary = _primary_axis(axes)
    if not primary:
        return -1
    res_key, res_choices = primary
    cur = settings.get(res_key)
    if cur is None:
        return -1
    for i, (_lbl, val) in enumerate(res_choices):
        if str(val) == str(cur):
            return i
    return -1


def lighter_set(emulator: str, settings: dict, core: str = "") -> dict | None:
    """Il set uno step piu' LEGGERO di quello dato. None se e' gia' il piu' leggero
    o l'emulatore non ha un asse risoluzione. Primo gradino dell'escalation."""
    axes = features.graphics_axes(emulator, core)
    primary = _primary_axis(axes)
    if not primary:
        return None
    res_key, res_choices = primary
    n = len(res_choices)
    idx = step_index_of(emulator, settings, core)
    if idx < 0:
        idx = n - 1                      # settings ignoti: parti dal piu' pesante
    if idx <= 0:
        return None                      # gia' al minimo: escalation -> core/emu
    s = _build_set(idx - 1, res_key, res_choices, _secondary_axes(axes, res_key), n)
    return {"name": "Piu' leggero", "recommended": True, "generated": True,
            "desc": s["desc"], "settings": s["settings"]}


def _same_settings(a: dict, b: dict) -> bool:
    """True se b e' contenuto in a con gli stessi valori (confronto come stringhe)."""
    return all(str(a.get(k)) == str(v) for k, v in (b or {}).items())


def known_keys(emulator: str, core: str = "") -> set:
    """Chiavi grafiche che SudoBat conosce per un emulatore (da es_features). E' il
    confine di sicurezza: cio' che un LLM esterno puo' proporre di toccare."""
    return set(features.graphics_axes(emulator, core).keys())


def known_values(emulator: str, core: str = "") -> dict:
    """Per ogni chiave, i valori ammessi (come stringhe). Serve a rifiutare i valori
    fuori range proposti da un LLM esterno."""
    return {k: {str(v) for _lbl, v in a["choices"]}
            for k, a in features.graphics_axes(emulator, core).items()}


def profiles_for(system: str, game_id: str, tier: str, emulator: str, core: str = "") -> list:
    """Set grafici per un lancio. Sempre GENERATI dal motore (dai valori veri di
    Batocera). Se SudoBat ha gia' VALIDATO sul campo un set per questo gioco+fascia,
    quel set entra nella lista ed e' il consigliato. E' la funzione che usa la UI."""
    game = catalog.find_game(system, game_id) if game_id else None
    heaviness = game.get("heaviness", "medium") if game else "medium"
    profs = generate_profiles(emulator, tier, heaviness, core)

    validated = catalog.validated_set(system, game_id, tier) if game_id else None
    if validated and not any(_same_settings(p["settings"], validated) for p in profs):
        profs.insert(0, {"name": "Validato sul campo", "recommended": True,
                         "generated": False, "desc": "esperienza confermata buona da te",
                         "settings": validated})

    # set della COMMUNITY (da sudobat-knowledge): proposte in piu', mai imposte.
    # Entrano in coda alla lista e il rerank sugli esiti LOCALI resta l'autorita'.
    if game_id:
        for c in catalog.community_sets(system, game_id, tier):
            if any(_same_settings(p["settings"], c["settings"]) for p in profs):
                continue
            n = c.get("confirmations", 1)
            profs.append({"name": "Community", "recommended": False,
                          "generated": False,
                          "desc": f"convalidato da {n} installazioni",
                          "settings": c["settings"]})

    return outcomes.rerank(profs, system, game_id)
