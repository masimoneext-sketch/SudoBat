"""Dalla voce dell'utente (i flag di fine partita) alla MOSSA SUCCESSIVA.

La scala di escalation dell'app:
    set piu' leggero  ->  core diverso  ->  emulatore diverso

SudoBat esegue solo il primo gradino (cambia il set grafico, che sa fare). Il core
e l'emulatore NON li cambia lui: e' l'utente da EmulationStation -- qui li propone
soltanto, con istruzioni chiare. Nessuna conoscenza scritta a mano: il set piu'
leggero lo calcola il motore (tuning), il resto e' un consiglio onesto.
"""
from __future__ import annotations

from . import tuning


def next_move(system: str, emulator: str, tier: str,
              applied_settings: dict, flags: dict, core: str = "") -> dict:
    """Ritorna la mossa successiva dato com'e' andata. Neutro rispetto alla lingua:
    ritorna CHIAVI (why_key / reason_key), la UI le traduce con i18n.

      {"kind": "good"}                             -> esperienza buona: niente da fare
      {"kind": "lighter", "set": {...},            -> prova questo set piu' leggero
       "why_key": "why_scatti"|"why_notfluid"}
      {"kind": "manual_emulator",                  -> set esauriti (o solo glitch): la
       "reason_key": "manual_lightest"|"manual_glitch"}  palla passa a core/emulatore
    """
    from . import outcomes
    if outcomes.is_good_experience(flags):
        return {"kind": "good"}

    perf_problem = (not flags.get("fluido")) or (not flags.get("fps_ok")) \
        or flags.get("scatti_concitate")

    # 1) problema di prestazioni -> scendi di uno step (piu' fluidita')
    if perf_problem:
        lighter = tuning.lighter_set(emulator, applied_settings, core=core)
        if lighter:
            why_key = "why_scatti" if flags.get("scatti_concitate") else "why_notfluid"
            return {"kind": "lighter", "set": lighter, "why_key": why_key}
        # 2) gia' al set piu' leggero e ancora non basta -> core/emulatore (manuale)
        return {"kind": "manual_emulator", "reason_key": "manual_lightest"}

    # 3) solo glitch grafici (girava fluido): serve un core/emulatore diverso -- il
    #    fix vero e' fuori dalle manopole grafiche che SudoBat regola.
    if flags.get("glitch"):
        return {"kind": "manual_emulator", "reason_key": "manual_glitch"}

    return {"kind": "good"}
