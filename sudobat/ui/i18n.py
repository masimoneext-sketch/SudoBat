"""Traduzioni IT/EN della UI. Ogni stringa mostrata passa da t("chiave").

La lingua scelta dall'utente e' persistita in state/ui_prefs.json (sopravvive ai
riavvii). Default: italiano. Se manca una chiave in una lingua, si ricade sull'italiano
e poi sulla chiave stessa -- non si crasha mai per una traduzione mancante.
"""
from __future__ import annotations

import json
from pathlib import Path

_PREFS = Path(__file__).parent.parent.parent / "state" / "ui_prefs.json"
_lang: str | None = None

STRINGS = {
    "it": {
        "lang_name": "Italiano",
        "app_subtitle": "tuning grafico per-gioco, consapevole dell'hardware",
        "press_key": "Premi un tasto",
        # menu principale
        "menu_diagnose": "Diagnosi ultimo lancio",
        "menu_hardware": "Profilo hardware",
        "menu_catalog": "Sfoglia catalogo giochi",
        "menu_howto": "Come si usa",
        "menu_settings": "Impostazioni",
        "menu_quit": "Esci",
        # come si usa
        "howto_title": "Come si usa SudoBat",
        "howto_1": "1. Gioca a un gioco, poi ESCI (torna a EmulationStation).",
        "howto_2": "2. Apri SudoBat e vai su 'Diagnosi ultimo lancio'.",
        "howto_3": "3. SudoBat riconosce il gioco e propone dei set grafici: scegline uno e applica.",
        "howto_4": "4. Rigioca lo stesso gioco per provare il set.",
        "howto_5": "5. Riapri SudoBat: ti chiede com'e' andata (fluido? scatti?). Impara e migliora.",
        "howto_6": ("6. Turbo AI (opzionale): se un crash e' SCONOSCIUTO e hai configurato la tua "
                    "chiave Groq, in Diagnosi compare 'SELECT: chiedi al turbo'. Non parte mai da "
                    "solo: interroga solo se premi SELECT, propone, e applichi/impari tu con A."),
        "howto_note": "L'emulatore/core NON lo cambia SudoBat: se serve te lo dice, lo cambi tu in ES.",
        # diagnosi
        "diag_title": "Diagnosi ultimo lancio",
        "lbl_game": "Gioco",
        "lbl_sysemu": "Sistema/emu",
        "lbl_session": "Sessione",
        "tier_label": "fascia",
        "no_sets": "Nessun set grafico per questo gioco.",
        "session_running": "nessuno stop (gioco forse in corso)",
        "crash_suspected": "sospetto crash",
        "session_ok": "ok",
        # flag di fine partita
        "flags_title": "Com'e' andata?",
        "flag_fluido": "Girava fluido?",
        "flag_fps_ok": "FPS buoni per giocare bene?",
        "flag_scatti_concitate": "Scattava nelle fasi concitate?",
        "flag_glitch": "Glitch grafici (texture, sfarfallii)?",
        "flags_confirm": "Conferma e salva l'esito",
        "ans_yes": "Si'",
        "ans_no": "No",
        # esiti / escalation
        "flash_good_title": "Esperienza buona 👍",
        "flash_saved_catalog": "salvato in catalogo (validato per {tier}).",
        "flash_next_time": "La prossima volta parte gia' cosi'.",
        "why_scatti": "scattava",
        "why_notfluid": "non abbastanza fluido",
        "flash_lighter_intro": "Ok, {why}.",
        "flash_lighter_propose": "Ti propongo un set piu' leggero:",
        "flash_apply_here": "Applicalo qui in Diagnosi e rigioca.",
        "manual_lightest": "Anche col set piu' leggero non gira bene.",
        "manual_glitch": "Glitch grafici: non si risolvono con la sola risoluzione.",
        "manual_notenough": "Il set grafico da solo non basta piu'.",
        "manual_change_emu": "Cambia core/emulatore da ES (vedi Diagnosi).",
        "manual_header": "⚠ L'emulatore lo devi cambiare TU (SudoBat non puo')",
        "manual_lbl_problem": "Problema",
        "manual_lbl_why": "Perche' non lo faccio io",
        "manual_lbl_do": "Cosa fare",
        "manual_why": ("SudoBat regola le impostazioni grafiche, ma NON puo' cambiare "
                       "core o emulatore: quello lo decide EmulationStation."),
        "manual_steps": ("In EmulationStation seleziona il gioco, premi SELECT -> Emulatore "
                         "(o Core) -> provane uno diverso, poi rilancia. Torna qui e dimmi "
                         "com'e' andata."),
        # impostazioni
        "settings_title": "Impostazioni",
        "set_language": "Lingua",
        "set_hook": "Hook lanci",
        "set_installed": "installato ✓",
        "set_notinstalled": "NON installato",
        "set_conf": "batocera.conf",
        "set_saves": "Salvataggi UI",
        "set_controller": "Controller",
        "set_keyboard": "tastiera",
        # ripristino backup ("annulla ultima modifica")
        "set_restore": "Ripristina ultimo backup",
        "set_nobackup": "nessun backup",
        "restore_q": "Ripristinare batocera.conf da questo backup?",
        "restore_note": "La conf attuale viene salvata come backup prima (annullabile).",
        "restore_none": "Nessun backup da ripristinare.",
        "restore_error": "Errore durante il ripristino:",
        "restore_done": "Ripristinato batocera.conf da:",
        "restore_undo_hint": "Per annullare: ripristina di nuovo.",
        # turbo AI in impostazioni (chiave personale dell'utente)
        "set_turbo": "Turbo AI (Groq)",
        "turbo_on": "attivo — chiave {tail}",
        "turbo_off": "non configurato — guida: docs/GROQ_SETUP.it.md",
        # condivisione opt-in dei set validati (community knowledge)
        "share_title": "Aiuta gli altri giocatori?",
        "share_body": ("Vuoi condividere anonimamente i set che funzionano, per "
                       "aiutare gli altri utenti?"),
        "share_body2": ("Verranno inviati solo: gioco, fascia hardware, emulatore, "
                        "settaggi e un identificativo casuale dell'installazione. "
                        "Mai dati personali. Cambiabile quando vuoi in Impostazioni."),
        "share_yes": "Si', condividi",
        "share_no": "No",
        "footer_share": "Sx/Dx: scegli   A: conferma   B: decidi dopo",
        "set_share": "Condivisione set",
        "share_state_on": "attiva — grazie!",
        "share_state_off": "disattivata",
        "share_state_unset": "da decidere (te lo chiedo alla prima validazione)",
        # footer / dialoghi
        "footer_main": "Su/Giu: scegli   A: conferma   B: esci",
        "footer_back": "B: indietro",
        "footer_diag": "Su/Giu: scegli set   A: applica (con backup)   B: indietro",
        "footer_diag_brain": "A: applica   SELECT: chiedi al turbo   B: indietro",
        "footer_flags": "Su/Giu: scegli   Sx=No / Dx=Si'   A: cambia/conferma   B: rimanda",
        "footer_confirm": "Sx/Dx: scegli   A: conferma   B: annulla",
        "footer_settings": "Su/Giu: scegli   A: conferma   B: indietro",
        "confirm_apply": "Applica",
        "confirm_cancel": "Annulla",
        # dialog di apply
        "apply_q": "Applicare '{label}' a",
        "apply_nochange": "(nessuna modifica: valori gia' impostati)",
        "apply_backup_note": "Backup di batocera.conf prima di scrivere.",
        "apply_write_error": "Errore durante la scrittura:",
        "apply_done": "Set '{label}' applicato.",
        "apply_backup": "Backup: {name}",
        "apply_replay_hint": "Rigioca: alla prossima diagnosi vedro' se ha funzionato.",
        # righe dei set in diagnosi
        "diag_crash_recognized": "Crash riconosciuto dal log: ",
        "diag_sets_header": "Set grafici che posso applicare io (A):",
        "star_recommended": "★ consigliato",
        "verdict_ok": "provato: {n} volte OK",
        "verdict_bad": "SCONSIGLIATO: {n} crash",
        "verdict_mixed": "misto: {ok} OK / {crash} crash",
        "reco_heuristic": "euristica",
        "reco_field_ok": "esiti: ha funzionato sul campo",
        "reco_heuristic_confirmed": "euristica confermata dagli esiti",
        "reco_heuristic_crashed": "esiti: l'euristica aveva fatto ricrashare",
        # turbo / brain
        "brain_title": "Turbo Groq — diagnosi assistita",
        "brain_querying": "Interrogo il turbo Groq",
        "brain_querying_sub": "(solo per questo crash sconosciuto; il cuore resta offline)",
        "brain_wait": "attendi...",
        "brain_noresp": "Nessuna risposta dal turbo (rete/chiave/errore).",
        "brain_offline_valid": "Il motore offline resta valido.",
        "brain_lowconf": "suggerimento a bassa fiducia, verificato",
        "brain_lbl_cause": "Causa (ipotesi)",
        "brain_lbl_expl": "Spiegazione",
        "brain_lbl_recemu": "Consiglia emulatore (lo fai tu)",
        "brain_lbl_settings": "Impostazioni (vagliate)",
        "brain_lbl_rejected": "Scartate dal verificatore",
        "brain_learn": "A: insegna questa regola a SudoBat (offline d'ora in poi)",
        "footer_brain_learn": "A: impara   B: indietro",
        "brain_notlearnable": "Non imparabile: {reason}",
        "learn_present": "Regola gia' presente:",
        "learn_present2": "la riconoscevo gia'.",
        "learn_error": "Errore salvataggio regola:",
        "learn_done": "Imparata!",
        "learn_done2": "Ora riconosco questo crash",
        "learn_done3": "OFFLINE, senza turbo.",
        # hardware
        "hw_title": "Profilo hardware",
        "hw_unavailable": "Profilo non disponibile.",
        "hw_gpu_dedicated": "GPU dedicata",
        "hw_yes": "si",
        "hw_no_integrated": "no (integrata)",
        "hw_tier": "Fascia",
        # catalogo
        "cat_choose_system": "Catalogo — scegli il sistema",
        "cat_games_count": "{n} giochi",
        "footer_cat_open": "A: apri   B: indietro",
        "cat_title": "Catalogo — {sys}",
        "cat_empty": "Catalogo vuoto per questo sistema.",
        "footer_scroll": "Su/Giu: scorri   B: indietro",
        "cat_heaviness": "Pesantezza",
        "cat_preset": "Preset [{tier}]",
        "cat_known_issues": "Problemi noti:",
    },
    "en": {
        "lang_name": "English",
        "app_subtitle": "per-game graphics tuning, hardware-aware",
        "press_key": "Press any key",
        "menu_diagnose": "Diagnose last launch",
        "menu_hardware": "Hardware profile",
        "menu_catalog": "Browse game catalog",
        "menu_howto": "How to use",
        "menu_settings": "Settings",
        "menu_quit": "Quit",
        "howto_title": "How to use SudoBat",
        "howto_1": "1. Play a game, then QUIT (back to EmulationStation).",
        "howto_2": "2. Open SudoBat and go to 'Diagnose last launch'.",
        "howto_3": "3. SudoBat recognizes the game and proposes graphics sets: pick one and apply.",
        "howto_4": "4. Replay the same game to try the set.",
        "howto_5": "5. Reopen SudoBat: it asks how it went (smooth? stutter?). It learns and improves.",
        "howto_6": ("6. AI turbo (optional): if a crash is UNKNOWN and you set up your Groq key, "
                    "Diagnose shows 'SELECT: ask the turbo'. It never runs on its own: it queries "
                    "only when you press SELECT, proposes, and you apply/learn with A."),
        "howto_note": "SudoBat does NOT change the emulator/core: if needed it tells you, you change it in ES.",
        "diag_title": "Diagnose last launch",
        "lbl_game": "Game",
        "lbl_sysemu": "System/emu",
        "lbl_session": "Session",
        "tier_label": "tier",
        "no_sets": "No graphics set for this game.",
        "session_running": "no stop (game maybe still running)",
        "crash_suspected": "suspected crash",
        "session_ok": "ok",
        "flags_title": "How did it go?",
        "flag_fluido": "Did it run smooth?",
        "flag_fps_ok": "Good FPS for a nice experience?",
        "flag_scatti_concitate": "Did it stutter in intense scenes?",
        "flag_glitch": "Graphics glitches (textures, flicker)?",
        "flags_confirm": "Confirm and save the result",
        "ans_yes": "Yes",
        "ans_no": "No",
        "flash_good_title": "Good experience 👍",
        "flash_saved_catalog": "saved to catalog (validated for {tier}).",
        "flash_next_time": "Next time it starts like this already.",
        "why_scatti": "it stuttered",
        "why_notfluid": "not smooth enough",
        "flash_lighter_intro": "Ok, {why}.",
        "flash_lighter_propose": "Here's a lighter set to try:",
        "flash_apply_here": "Apply it here in Diagnose and replay.",
        "manual_lightest": "Even the lightest set doesn't run well.",
        "manual_glitch": "Graphics glitches aren't fixed by resolution alone.",
        "manual_notenough": "The graphics set alone isn't enough anymore.",
        "manual_change_emu": "Change core/emulator from ES (see Diagnose).",
        "manual_header": "⚠ YOU must change the emulator (SudoBat can't)",
        "manual_lbl_problem": "Problem",
        "manual_lbl_why": "Why I don't do it",
        "manual_lbl_do": "What to do",
        "manual_why": ("SudoBat tunes graphics settings, but can NOT change core or "
                       "emulator: that's decided by EmulationStation."),
        "manual_steps": ("In EmulationStation select the game, press SELECT -> Emulator "
                         "(or Core) -> try a different one, then relaunch. Come back and tell "
                         "me how it went."),
        "settings_title": "Settings",
        "set_language": "Language",
        "set_hook": "Launch hook",
        "set_installed": "installed ✓",
        "set_notinstalled": "NOT installed",
        "set_conf": "batocera.conf",
        "set_saves": "UI saves",
        "set_controller": "Controller",
        "set_keyboard": "keyboard",
        "set_restore": "Restore latest backup",
        "set_nobackup": "no backup",
        "restore_q": "Restore batocera.conf from this backup?",
        "restore_note": "Current conf is saved as a backup first (undoable).",
        "restore_none": "No backup to restore.",
        "restore_error": "Error while restoring:",
        "restore_done": "Restored batocera.conf from:",
        "restore_undo_hint": "To undo: restore again.",
        "set_turbo": "AI turbo (Groq)",
        "turbo_on": "active — key {tail}",
        "turbo_off": "not set up — guide: docs/GROQ_SETUP.md",
        "share_title": "Help other players?",
        "share_body": ("Would you like to anonymously share the sets that work, "
                       "to help other users?"),
        "share_body2": ("Only this gets sent: game, hardware tier, emulator, "
                        "settings and a random install identifier. Never personal "
                        "data. You can change this anytime in Settings."),
        "share_yes": "Yes, share",
        "share_no": "No",
        "footer_share": "Left/Right: choose   A: confirm   B: decide later",
        "set_share": "Set sharing",
        "share_state_on": "on — thank you!",
        "share_state_off": "off",
        "share_state_unset": "undecided (asked at your first validation)",
        "footer_main": "Up/Down: choose   A: confirm   B: quit",
        "footer_back": "B: back",
        "footer_diag": "Up/Down: choose set   A: apply (with backup)   B: back",
        "footer_diag_brain": "A: apply   SELECT: ask the turbo   B: back",
        "footer_flags": "Up/Down: choose   Left=No / Right=Yes   A: change/confirm   B: later",
        "footer_confirm": "Left/Right: choose   A: confirm   B: cancel",
        "footer_settings": "Up/Down: choose   A: confirm   B: back",
        "confirm_apply": "Apply",
        "confirm_cancel": "Cancel",
        "apply_q": "Apply '{label}' to",
        "apply_nochange": "(no change: values already set)",
        "apply_backup_note": "batocera.conf backup before writing.",
        "apply_write_error": "Error while writing:",
        "apply_done": "Set '{label}' applied.",
        "apply_backup": "Backup: {name}",
        "apply_replay_hint": "Replay: at the next diagnosis I'll see if it worked.",
        "diag_crash_recognized": "Crash recognized from log: ",
        "diag_sets_header": "Graphics sets I can apply (A):",
        "star_recommended": "★ recommended",
        "verdict_ok": "tried: {n} times OK",
        "verdict_bad": "NOT ADVISED: {n} crash",
        "verdict_mixed": "mixed: {ok} OK / {crash} crash",
        "reco_heuristic": "heuristic",
        "reco_field_ok": "results: worked in the field",
        "reco_heuristic_confirmed": "heuristic confirmed by results",
        "reco_heuristic_crashed": "results: the heuristic had crashed",
        "brain_title": "Turbo Groq — assisted diagnosis",
        "brain_querying": "Querying the Groq turbo",
        "brain_querying_sub": "(only for this unknown crash; the core stays offline)",
        "brain_wait": "please wait...",
        "brain_noresp": "No answer from the turbo (network/key/error).",
        "brain_offline_valid": "The offline engine is still valid.",
        "brain_lowconf": "low-confidence suggestion, verified",
        "brain_lbl_cause": "Cause (hypothesis)",
        "brain_lbl_expl": "Explanation",
        "brain_lbl_recemu": "Suggests emulator (you do it)",
        "brain_lbl_settings": "Settings (vetted)",
        "brain_lbl_rejected": "Rejected by the verifier",
        "brain_learn": "A: teach this rule to SudoBat (offline from now on)",
        "footer_brain_learn": "A: learn   B: back",
        "brain_notlearnable": "Not learnable: {reason}",
        "learn_present": "Rule already present:",
        "learn_present2": "I already recognized it.",
        "learn_error": "Error saving rule:",
        "learn_done": "Learned!",
        "learn_done2": "Now I recognize this crash",
        "learn_done3": "OFFLINE, no turbo.",
        "hw_title": "Hardware profile",
        "hw_unavailable": "Profile not available.",
        "hw_gpu_dedicated": "Dedicated GPU",
        "hw_yes": "yes",
        "hw_no_integrated": "no (integrated)",
        "hw_tier": "Tier",
        "cat_choose_system": "Catalog — choose the system",
        "cat_games_count": "{n} games",
        "footer_cat_open": "A: open   B: back",
        "cat_title": "Catalog — {sys}",
        "cat_empty": "Empty catalog for this system.",
        "footer_scroll": "Up/Down: scroll   B: back",
        "cat_heaviness": "Heaviness",
        "cat_preset": "Preset [{tier}]",
        "cat_known_issues": "Known issues:",
    },
}


def _load_lang() -> str:
    global _lang
    if _lang is None:
        try:
            _lang = json.loads(_PREFS.read_text()).get("lang", "it")
        except Exception:
            _lang = "it"
        if _lang not in STRINGS:
            _lang = "it"
    return _lang


def lang() -> str:
    return _load_lang()


def set_lang(new: str) -> None:
    global _lang
    _lang = new if new in STRINGS else "it"
    try:
        _PREFS.parent.mkdir(parents=True, exist_ok=True)
        _PREFS.write_text(json.dumps({"lang": _lang}))
    except Exception:
        pass


def toggle() -> None:
    set_lang("en" if _load_lang() == "it" else "it")


def t(key: str, **kw) -> str:
    cur = _load_lang()
    s = STRINGS.get(cur, {}).get(key)
    if s is None:
        s = STRINGS["it"].get(key, key)
    return s.format(**kw) if kw else s
