#!/bin/bash
# SudoBat — Copyright © 2026 Marco Simone. PolyForm Noncommercial License 1.0.0.
# Uso personale/non commerciale libero; uso commerciale solo con licenza separata. Vedi LICENSE.md.
# Launcher di SudoBat per il menu PORTS di EmulationStation.
#
# Il codice vive nel repo /userdata/system/SudoBat (sorgente unica di verita');
# questo script viene copiato in /userdata/roms/ports/SudoBat.sh in fase di
# installazione (vedi tools/register_port.py) e avvia la UI pygame.
export PYGAME_HIDE_SUPPORT_PROMPT=1
export PYTHONWARNINGS="ignore::UserWarning:pygame.pkgdata"
cd /userdata/system/SudoBat || exit 1
# Sessione di debug: cattura tutto l'output grezzo (anche un crash precoce, prima
# dell'acchiappa-crash Python) in state/ui_stderr.log. Sola scrittura nel repo.
echo "=== launch $(date '+%Y-%m-%d %H:%M:%S') ===" >> state/ui_stderr.log
exec python3 -m sudobat.ui >> state/ui_stderr.log 2>&1
