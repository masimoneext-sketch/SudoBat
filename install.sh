#!/bin/bash
# SudoBat — Copyright © 2026 Marco Simone. PolyForm Noncommercial License 1.0.0.
# Uso personale/non commerciale libero; uso commerciale solo con licenza separata. Vedi LICENSE.md.
# Installer one-shot di SudoBat per Batocera.
#
#   curl -L https://raw.githubusercontent.com/masimoneext-sketch/SudoBat/master/install.sh | bash
#
# Fa, in ordine: controlli ambiente -> scarica/aggiorna il repo in
# /userdata/system/SudoBat -> attiva l'hook dei lanci -> selftest ->
# registra SudoBat nel menu PORTS. Idempotente: rilanciarlo aggiorna.
#
# Non tocca nient'altro del sistema. Per disinstallare:
#   rm /userdata/system/scripts/sudobat-hook.sh
#   rm -r /userdata/system/SudoBat /userdata/roms/ports/SudoBat.sh
#
# Variabili opzionali (per test/situazioni particolari):
#   SUDOBAT_DEST         cartella di installazione (default /userdata/system/SudoBat)
#   SUDOBAT_SCRIPTS_DIR  cartella hook (default /userdata/system/scripts)
#   SUDOBAT_REPO_URL     sorgente git alternativa
#   SUDOBAT_REGISTER_PORT=0  salta la registrazione nel menu PORTS
#   SUDOBAT_SKIP_CHECKS=1    salta i controlli "sei su Batocera?"

set -u

OWNER="masimoneext-sketch"
REPO="SudoBat"
BRANCH="master"
DEST="${SUDOBAT_DEST:-/userdata/system/SudoBat}"
SCRIPTS_DIR="${SUDOBAT_SCRIPTS_DIR:-/userdata/system/scripts}"
REPO_URL="${SUDOBAT_REPO_URL:-https://github.com/$OWNER/$REPO.git}"

say() { printf '[SudoBat] %s\n' "$*"; }
die() { printf '[SudoBat] ERRORE: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- controlli
if [ "${SUDOBAT_SKIP_CHECKS:-0}" != "1" ]; then
    [ -d /userdata/system ] || die "questo non sembra un Batocera (/userdata/system mancante)"
    arch="$(uname -m)"
    [ "$arch" = "x86_64" ] || say "ATTENZIONE: architettura $arch — SudoBat e' sviluppato e testato su x86_64"
fi
command -v python3 >/dev/null 2>&1 || die "python3 non trovato (su Batocera e' preinstallato)"

# ------------------------------------------------------- scarica / aggiorna
if [ -d "$DEST/.git" ] && command -v git >/dev/null 2>&1; then
    say "installazione esistente trovata: aggiorno ($DEST)..."
    git -C "$DEST" pull --ff-only || die "aggiornamento fallito (modifiche locali? rete?)"
elif command -v git >/dev/null 2>&1; then
    say "scarico SudoBat con git in $DEST..."
    git clone --depth 1 "$REPO_URL" "$DEST" || die "clone fallito (rete ok? repo raggiungibile?)"
else
    say "git non presente: scarico l'archivio del repo..."
    TMP="$(mktemp -d)" || die "mktemp fallito"
    trap 'rm -rf "$TMP"' EXIT
    curl -fsSL "https://codeload.github.com/$OWNER/$REPO/tar.gz/refs/heads/$BRANCH" \
        -o "$TMP/sudobat.tar.gz" || die "download fallito (rete ok? repo raggiungibile?)"
    tar -xzf "$TMP/sudobat.tar.gz" -C "$TMP" || die "estrazione fallita"
    mkdir -p "$DEST"
    cp -a "$TMP/$REPO-$BRANCH/." "$DEST/" || die "copia in $DEST fallita"
fi

# ------------------------------------------------------------------- hook
chmod +x "$DEST/scripts/sudobat-hook.sh" "$DEST/scripts/SudoBat.sh" 2>/dev/null
mkdir -p "$SCRIPTS_DIR"
ln -sf "$DEST/scripts/sudobat-hook.sh" "$SCRIPTS_DIR/sudobat-hook.sh"
say "hook dei lanci attivato: $SCRIPTS_DIR/sudobat-hook.sh"

# ---------------------------------------------------------------- selftest
say "verifico l'installazione (selftest del motore, nessuna scrittura sul sistema)..."
if (cd "$DEST" && python3 -m sudobat.selftest >/dev/null 2>&1); then
    say "selftest: OK"
else
    say "ATTENZIONE: selftest fallito. Dettagli: cd $DEST && python3 -m sudobat.selftest"
fi

# -------------------------------------------------------------- menu PORTS
if [ "${SUDOBAT_REGISTER_PORT:-1}" = "1" ]; then
    if (cd "$DEST" && python3 -m tools.register_port); then
        say "registrato nel menu PORTS di EmulationStation"
    else
        say "ATTENZIONE: registrazione nel menu PORTS fallita."
        say "  Riprova a mano: cd $DEST && python3 -m tools.register_port"
    fi
fi

# ------------------------------------------------------------------ chiusura
say ""
say "FATTO! Ultimo passo (a mano, una volta sola):"
say "  in EmulationStation: Menu -> Impostazioni giochi -> Aggiorna gamelist"
say "  (oppure riavvia il box). SudoBat comparira' nel menu PORTS."
say ""
say "Turbo AI opzionale (serve la TUA chiave Groq gratuita):"
say "  guida: $DEST/docs/GROQ_SETUP.it.md  (english: GROQ_SETUP.md)"
