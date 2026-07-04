"""Protezione della chiave Groq dalla condivisione di rete di Batocera.

Il problema, detto senza giri: Batocera esporta TUTTO /userdata via Samba
(sezione [share] con "guest ok = Yes" e "force user = root"). Qualunque file
persistente e' quindi leggibile da chiunque sia sulla rete locale, senza
password, e i permessi Unix (600) non contano nulla perche' Samba serve i
file come root. Una chiave salvata in chiaro sotto /userdata e' esposta.

L'unico blocco reale offerto da Samba e' "veto files": il file diventa
invisibile E inaccessibile via rete (lettura, scrittura, creazione), pur
restando normalissimo in locale. Questo modulo aggiunge lo store della
chiave (state/.groq_key, vedi brain.py) alla riga "veto files" della sezione
[share] di /etc/samba/smb.conf e ricarica smbd.

Il rootfs di Batocera vive in RAM: la patch evapora a ogni riavvio, percio'
il servizio sudobat_smbguard (scripts/, installato da install.sh in
/userdata/system/services/) la riapplica al boot. Eseguire il modulo
(python3 -m sudobat.smbguard) fa entrambe le cose: importa un eventuale
groq_key.txt lasciato in chiaro e attiva il veto.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

# Nome (basename) messo a veto: e' lo store nascosto usato da brain.py.
# NON si mette a veto "groq_key.txt": quello e' il file che l'utente crea
# dalla condivisione (docs/GROQ_SETUP*), e il veto ne impedirebbe la creazione.
VETO_NAME = ".groq_key"

SMB_CONF = Path("/etc/samba/smb.conf")


def _veto_in(value: str) -> bool:
    """True se la lista veto ("/pat1/pat2/") contiene gia' VETO_NAME."""
    return f"/{VETO_NAME}/" in value


def patch_text(text: str) -> str | None:
    """Testo di smb.conf con VETO_NAME nella riga "veto files" di [share].

    Ritorna None se il veto c'e' gia' (niente da fare). Solleva LookupError
    se manca la sezione [share] (non e' lo smb.conf di Batocera: meglio non
    toccare nulla). Funzione pura: cosi' il selftest la esercita senza
    avvicinarsi al file vero.
    """
    lines = text.splitlines(keepends=True)
    section = None
    share_header_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip().lower()
            if section == "share":
                share_header_idx = i
            continue
        if section != "share" or stripped.startswith((";", "#")):
            continue
        key, _, value = stripped.partition("=")
        if key.strip().lower() == "veto files":
            if _veto_in(value):
                return None
            base = value.strip()
            if not base.startswith("/"):
                base = "/" + base
            if not base.endswith("/"):
                base += "/"
            indent = line[: len(line) - len(line.lstrip())]
            eol = "\n" if line.endswith("\n") else ""
            lines[i] = f"{indent}veto files = {base}{VETO_NAME}/{eol}"
            return "".join(lines)
    if share_header_idx is None:
        raise LookupError("sezione [share] non trovata in smb.conf")
    eol = "\n" if lines[share_header_idx].endswith("\n") else "\n"
    lines.insert(share_header_idx + 1, f"   veto files = /{VETO_NAME}/{eol}")
    return "".join(lines)


def active() -> bool:
    """True se il veto e' in vigore nello smb.conf attuale."""
    try:
        text = SMB_CONF.read_text()
    except OSError:
        return False
    in_share = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_share = stripped[1:-1].strip().lower() == "share"
            continue
        if in_share and stripped.lower().startswith("veto files") and _veto_in(stripped):
            return True
    return False


def _reload_smbd() -> str | None:
    """Fa rileggere la configurazione a smbd. Ritorna None se ok, altrimenti
    il motivo (il veto restera' comunque attivo dal prossimo riavvio di smbd)."""
    try:
        r = subprocess.run(["smbcontrol", "smbd", "reload-config"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return None
        return (r.stderr or r.stdout).strip() or f"smbcontrol exit {r.returncode}"
    except (OSError, subprocess.TimeoutExpired) as e:
        return str(e)


def ensure(reload: bool = True) -> dict:
    """Applica il veto se manca. {active, changed, error}.

    Non solleva mai: chi salva una chiave deve poterlo chiamare best-effort
    e riferire l'esito all'utente, non esplodere.
    """
    try:
        text = SMB_CONF.read_text()
    except OSError as e:
        return {"active": False, "changed": False, "error": f"smb.conf illeggibile: {e}"}
    try:
        patched = patch_text(text)
    except LookupError as e:
        return {"active": False, "changed": False, "error": str(e)}
    if patched is None:
        return {"active": True, "changed": False, "error": None}
    try:
        fd, tmp = tempfile.mkstemp(dir=str(SMB_CONF.parent), prefix=".smb.conf.")
        with os.fdopen(fd, "w") as f:
            f.write(patched)
        os.replace(tmp, SMB_CONF)
    except OSError as e:
        return {"active": False, "changed": False, "error": f"scrittura smb.conf fallita: {e}"}
    err = _reload_smbd() if reload else None
    return {"active": True, "changed": True, "error": err}


def main() -> None:
    # Prima si ritira l'eventuale groq_key.txt in chiaro, poi si alza il veto:
    # cosi' al boot un file appena depositato via rete viene subito nascosto.
    from . import brain
    ingested = brain.ingest_plaintext(guard=False)
    if ingested:
        print(f"[smbguard] chiave importata nello store nascosto: {ingested}")
    r = ensure()
    if r["active"] and not r["error"]:
        stato = "attivato ora" if r["changed"] else "gia' attivo"
        print(f"[smbguard] veto SMB su {VETO_NAME}: {stato}")
    elif r["active"]:
        print(f"[smbguard] veto scritto ma reload smbd non riuscito: {r['error']}")
    else:
        print(f"[smbguard] veto NON attivo: {r['error']}")


if __name__ == "__main__":
    main()
