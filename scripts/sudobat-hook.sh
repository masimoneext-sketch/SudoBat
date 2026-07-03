#!/bin/bash
# SudoBat — Copyright © 2026 Marco Simone. PolyForm Noncommercial License 1.0.0.
# Uso personale/non commerciale libero; uso commerciale solo con licenza separata. Vedi LICENSE.md.
# Hook gameStart/gameStop di Batocera (vedi configgen/emulatorlauncher.py e
# /usr/share/batocera/datainit/system/scripts/template-game-start-stop.txt).
#
# Installato via symlink in /userdata/system/scripts/ (cartella USER_SCRIPTS
# letta da Batocera a ogni lancio/stop di un gioco).
#
# Si limita a loggare in modo append-only lo stato dell'ultimo lancio in
# state/last_launch.json (dentro il repo SudoBat) -- nessuna altra azione,
# nessuna scrittura su file di sistema.
#
# SUDOBAT_STATE_DIR: override per i test (il selftest scrive in una dir
# temporanea invece che in /userdata).

STATE_DIR="${SUDOBAT_STATE_DIR:-/userdata/system/SudoBat/state}"
STATE_FILE="$STATE_DIR/last_launch.json"

mkdir -p "$STATE_DIR"

event="$1"
system_name="$2"
emulator="$3"
core="$4"
rom="$5"
timestamp=$(date +%s)

# SudoBat e' a sua volta un Port: Batocera fa scattare questo hook anche per il
# suo stesso avvio. Se lo registrassimo, last_launch.json punterebbe a SudoBat
# invece che al gioco che l'utente vuole regolare -> SudoBat sarebbe cieco su
# se stesso. Quindi il SUO lancio NON deve mai sovrascrivere l'ultimo gioco.
case "$(basename "$rom")" in
    SudoBat.sh) exit 0 ;;
esac

# I nomi delle rom possono contenere " o \: interpolati grezzi nel JSON lo
# rendono invalido e la diagnosi muore alla lettura. Per il JSON bastano questi
# due escape (prima il backslash, poi le virgolette).
json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    printf '%s' "$s"
}

system_name="$(json_escape "$system_name")"
emulator="$(json_escape "$emulator")"
core="$(json_escape "$core")"
rom="$(json_escape "$rom")"

case "$event" in
    gameStart)
        printf '{"event":"gameStart","system":"%s","emulator":"%s","core":"%s","rom":"%s","timestamp":%s}\n' \
            "$system_name" "$emulator" "$core" "$rom" "$timestamp" > "$STATE_FILE"
        ;;
    gameStop)
        # Aggiunge lo stop accanto, senza toccare i dati del gameStart appena scritti.
        printf '{"event":"gameStop","system":"%s","emulator":"%s","core":"%s","rom":"%s","timestamp":%s}\n' \
            "$system_name" "$emulator" "$core" "$rom" "$timestamp" >> "$STATE_FILE.stop_log"
        ;;
esac

exit 0
