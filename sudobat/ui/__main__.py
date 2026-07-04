# SudoBat — Copyright © 2026 Marco Simone. PolyForm Noncommercial License 1.0.0.
# Uso personale/non commerciale libero; uso commerciale solo con licenza separata. Vedi LICENSE.md.
"""Entrypoint della UI: `python3 -m sudobat.ui`.

Tiene fuori pygame finche' non serve: se manca, messaggio chiaro invece di un
traceback. `--selftest` esegue un giro headless che entra in ogni schermata e la
disegna una volta (driver video 'dummy'), per verificare che nulla crashi senza
bisogno di un display e SENZA mai scrivere sul sistema.
"""
from __future__ import annotations

import sys


def _selftest() -> int:
    import os
    os.environ["SUDOBAT_UI_HEADLESS"] = "1"
    from . import app as app_mod
    from . import controls

    a = app_mod.App(headless=True)
    # visita ogni stato e disegna; naviga un po' dove ha senso.
    a.draw_splash()
    a.enter("main")
    a.draw_main()
    a.dispatch(controls.DOWN); a.draw_main()
    # banner "nuova versione" in home + valore in impostazioni (nessuna rete:
    # si simula l'esito del controllo, il check vero e' disattivato in headless)
    a.update_available = "9.9"
    a.draw_main()
    a.state = "settings"; a.menu_index = 3; a.draw_settings()
    a.update_available = None
    a.state = "main"; a.menu_index = 0

    # diagnosi SENZA risolvere gli esiti: il selftest non deve consumare il
    # giudizio (questionario) della sessione reale dell'utente.
    a._load_diagnose(resolve_outcome=False)
    a.state = "diagnose"; a.draw_diagnose()
    if a.tuning:                   # naviga i profili ma NON confermare (niente scrittura)
        a.dispatch(controls.DOWN); a.draw_diagnose()
        a._ask_apply(a.tuning[0]); a.draw_confirm()  # apre il dialog (dry-run) e lo disegna
        a.on_confirm(controls.BACK)                  # annulla: nessuna scrittura

    # schermata turbo Groq: disegna sia lo stato "in corso" sia quello "risposta"
    a.state = "brain"; a.brain_loading = True; a.draw_brain()
    a.brain_loading = False; a.brain_sug = None; a.draw_brain()
    a._load_diagnose(resolve_outcome=False)  # torna indietro come on_brain(BACK), senza consumare esiti
    a.state = "diagnose"

    a.enter("howto"); a.draw_howto()

    # toggle lingua in impostazioni: cambia IT<->EN e ridisegna in entrambe
    from . import i18n
    a.state = "settings"; a.draw_settings()
    a.on_settings(controls.CONFIRM); a.draw_settings()   # -> EN
    a.draw_main()                                        # menu in EN
    a.on_settings(controls.CONFIRM)                      # torna a IT
    i18n.set_lang("it")

    a.enter("hardware"); a.draw_hardware()

    a.state = "catalog_sys"; a.menu_index = 0; a.draw_catalog_sys()
    a._load_games("ps2"); a.state = "catalog_games"; a.draw_catalog_games()

    a.state = "settings"; a.menu_index = 0; a.draw_settings()
    # riga "Ripristina ultimo backup": naviga e apri (conferma se c'e' un backup,
    # messaggio "nessun backup" se non c'e') -- in entrambi i casi si annulla
    # subito: NESSUNA scrittura.
    a.dispatch(controls.DOWN); a.draw_settings()
    a.dispatch(controls.CONFIRM)
    getattr(a, f"draw_{a.state}")()
    if a.state == "confirm":
        a.on_confirm(controls.BACK)      # annulla il ripristino
    else:
        a.on_message(controls.CONFIRM)   # chiudi il messaggio
    a.state = "settings"; a.menu_index = 0

    # questionario flag di fine partita: prepara un contesto finto e disegna,
    # naviga e cambia una risposta, senza mai risolvere/scrivere davvero.
    a._start_flags({"system": "ps2", "game_id": "TEST-000.00", "game": "Gioco di prova",
                    "settings": {"pcsx2_resolution": 3}})
    a.draw_flags()
    a.dispatch(controls.DOWN); a.dispatch(controls.LEFT); a.draw_flags()  # una risposta -> No
    a.dispatch(controls.BACK)  # rimanda: torna al menu, niente scrittura

    # schermata consenso condivisione: disegna, naviga, ed esce con B
    # (nessuna decisione salvata, nessuna scrittura)
    a._share_after = (["Test"], "main")
    a.state = "share_consent"; a.menu_index = 0; a.draw_share_consent()
    a.dispatch(controls.RIGHT); a.draw_share_consent()
    a.dispatch(controls.BACK)   # decidi dopo: consenso resta non impostato

    a._flash(["Test messaggio"], "main"); a.draw_message()

    import pygame
    pygame.quit()
    print("[selftest] OK: tutte le schermate disegnate senza errori.")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    try:
        import pygame  # noqa: F401
    except ImportError:
        sys.stderr.write(
            "\n[SudoBat] pygame non e' installato.\n"
            "Su Batocera di solito e' gia' presente.\n\n")
        return 2
    from . import app
    try:
        app.run()
    except BaseException:
        # acchiappa-crash: se la UI muore e rimbalza a EmulationStation, qui
        # resta il perche' (state/debug.log nel repo, mai su file di sistema).
        import traceback
        from pathlib import Path
        log = Path(__file__).parent.parent.parent / "state" / "debug.log"
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            with open(log, "a") as fh:
                fh.write("=== CRASH UI ===\n")
                traceback.print_exc(file=fh)
        except Exception:
            pass
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
