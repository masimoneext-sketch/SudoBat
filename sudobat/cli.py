# SudoBat — Copyright © 2026 Marco Simone. PolyForm Noncommercial License 1.0.0.
# Uso personale/non commerciale libero; uso commerciale solo con licenza separata. Vedi LICENSE.md.
"""CLI di test manuale. Quasi tutti i comandi sono in sola lettura; l'unico che
puo' scrivere e' `apply --write N` (in batocera.conf, con backup automatico).
Uso: python3 -m sudobat.cli <comando> [argomenti]

Comandi:
  profile                          stampa il profilo hardware rilevato
  identify-ps2 <path.iso>          estrae il serial da un'ISO PS2
  identify-psx <path.chd>          estrae il serial da un CHD PSX
  lookup <system> <game_id>        cerca un gioco nel catalogo e mostra il preset
                                    per la fascia hardware rilevata su questa macchina
  last-launch                      mostra l'ultimo lancio tracciato dall'hook (se presente)
  diagnose                         diagnostica l'ultimo lancio (crash/problemi noti + fix)
  apply [--write N]                elenca i fix proposti (dry-run); con --write N applica
                                    il fix N a batocera.conf (backup automatico prima)
  restore [--write]                annulla l'ultima modifica: ripristina batocera.conf
                                    dall'ultimo backup (dry-run senza --write)
  sets <system> <game_id> [emu]    mostra i set grafici che il motore GENERA per il gioco
  brain                            turbo LLM opzionale (Groq): solo per crash che il motore
                                    offline non riconosce; propone e prepara una regola nuova
  key [set <CHIAVE>|test|remove]   gestisce la TUA chiave API Groq personale (gratuita):
                                    senza argomenti mostra lo stato; guida: docs/GROQ_SETUP.it.md
  share [on|off|flush]             condivisione opt-in dei set validati (stato/attiva/
                                    disattiva; flush ritenta l'invio della coda)
  knowledge update                 scarica la conoscenza community (set validati dagli
                                    altri utenti) — il download non richiede consenso
  learn                            conferma e salva offline la regola preparata da `brain`
                                    (loop di distillazione: da qui in poi la riconosce da solo)
  history <system> <game_id>       storico esiti: quali set applicati e com'e' andata dopo
"""
import json
import sys
import time
from pathlib import Path

from . import catalog, config, diagnose as diagnose_mod, hardware, outcomes, tuning
from .identify import ps2, psx

_STATE_FILE = Path(__file__).parent.parent / "state" / "last_launch.json"
_PENDING_RULE = Path(__file__).parent.parent / "state" / "pending_rule.json"


def cmd_profile():
    p = hardware.profile()
    print(f"CPU: {p.cpu_model} ({p.cpu_cores} core)")
    print(f"RAM: {p.ram_mb} MB")
    print(f"GPU: {p.gpu_name} (dedicata: {p.has_discrete_gpu})")
    print(f"Fascia hardware: {p.tier}")


def cmd_identify_ps2(iso_path):
    serial = ps2.extract_serial(iso_path)
    print(f"Serial: {serial}" if serial else "Serial non trovato")


def cmd_identify_psx(chd_path):
    serial = psx.extract_serial(chd_path)
    print(f"Serial: {serial}" if serial else "Serial non trovato")


def cmd_lookup(system, game_id):
    game = catalog.find_game(system, game_id)
    if not game:
        print(f"Gioco '{game_id}' non presente nel catalogo {system}.yaml")
        return
    tier = hardware.profile().tier
    print(f"Titolo: {game['title']} (heaviness: {game.get('heaviness', '?')})")
    preset = (game.get("presets") or {}).get(tier)
    if preset:
        print(f"Preset per fascia '{tier}': {preset}")
    else:
        print(f"Nessun preset specifico per la fascia '{tier}' — servirebbe un default generico")
    for issue in game.get("known_issues", []):
        fix = issue.get("fix") or issue.get("manual_fix") or {}
        print(f"Problema noto: {issue.get('symptom', '')} -> {issue.get('cause', '')} -> fix: {fix}")


def cmd_diagnose():
    result = diagnose_mod.diagnose()
    if "error" in result:
        print(result["error"])
        return
    launch = result["launch"]
    system = launch.get("system", "")
    gid = result.get("game_id") or Path(launch.get("rom", "")).name
    print(f"Ultimo lancio: {launch.get('system')} / {launch.get('emulator')} / {Path(launch.get('rom', '')).name}")
    if result["duration_seconds"] is not None:
        print(f"Durata sessione: {result['duration_seconds']}s (sospetto crash: {result['suspected_crash']})")
    else:
        print("Nessuno stop registrato ancora (gioco forse ancora in corso, o hook non ha visto lo stop)")
    if result["game"]:
        print(f"Gioco riconosciuto: {result['game']['title']} (id: {result['game_id']})")
        print(f"Preset base per fascia '{result['hardware_tier']}': {result['baseline_preset']}")
        for issue in result["game"].get("known_issues", []):
            fix = issue.get("fix") or issue.get("manual_fix") or {}
            print(f"  Problema noto: {issue.get('symptom', '')} -> fix: {fix}")
    else:
        print(f"Gioco non riconosciuto nel catalogo (id estratto: {result['game_id']})")
    if result["matched_diagnostic_rules"]:
        print("Regole diagnostiche generiche che matchano il log:")
        for rule in result["matched_diagnostic_rules"]:
            print(f"  Causa: {rule['cause']}")
            for fix in rule["fix_suggestions"]:
                print(f"    Fix: {fix['description']} -> {fix['settings']}")
    else:
        print("Nessuna regola diagnostica generica matcha il log dell'ultimo lancio.")

    # crash riconosciuti dal log dell'emulatore (offline), annotati col loro storico:
    # un fix distillato che continua a far ricrashare si vede qui (auto-correzione).
    for c in result.get("emulator_crashes", []):
        print(f"Crash riconosciuto (dal log): {c['cause']}")
        if c.get("recommend_emulator"):
            print(f"    -> cambia emulatore in: {c['recommend_emulator']} (lo fai tu)")
        for fx in c.get("fix_suggestions", []):
            vr = outcomes.verdict(system, gid, fx["settings"]) if gid else ""
            print(f"    Fix: {fx['description']} -> {fx['settings']}" + (f"  [storico: {vr}]" if vr else ""))

    # --- memoria degli esiti: risolvi come e' andata la sessione appena finita ---
    if result.get("suspected_crash") or result.get("emulator_crashes"):
        outcome = "crash"
    elif result.get("duration_seconds") is not None and result["duration_seconds"] >= 60:
        outcome = "ok"
    else:
        outcome = None
    if gid and outcome:
        resolved = outcomes.resolve(system, gid, outcome)
        if resolved:
            print(f"\nEsito registrato per il set applicato ({resolved.get('source', '?')}): {outcome.upper()}")
        tr = outcomes.track_record(system, gid)
        if tr["ok"] or tr["crash"]:
            print(f"Storico di questo gioco: {tr['ok']} OK / {tr['crash']} crash")


def cmd_apply(args):
    """Mostra i fix proposti dalla diagnosi e (solo con --write N) li applica al
    gioco dell'ultimo lancio, scrivendo in batocera.conf con backup automatico.
    Senza --write e' un dry-run: non tocca nulla."""
    write_index = None
    if "--write" in args:
        i = args.index("--write")
        try:
            write_index = int(args[i + 1])
        except (IndexError, ValueError):
            print("Uso: apply --write <N>  (N = numero del fix elencato)")
            return

    result = diagnose_mod.diagnose()
    if "error" in result:
        print(result["error"])
        return
    launch = result["launch"]
    system = launch.get("system", "")
    rom = launch.get("rom", "")
    romfile = Path(rom).name
    fixes = diagnose_mod.collect_fixes(result)
    if not fixes:
        print("Nessun fix proposto per l'ultimo lancio (nessun problema noto o regola che matcha).")
        return

    print(f"Gioco: {romfile} ({system}) — fix proposti:")
    for n, fx in enumerate(fixes, 1):
        print(f"\n[{n}] ({fx['source']}) {fx['description']}")
        plan = config.set_game_override(system, romfile, fx["settings"], dry_run=True)
        for c in plan["changes"]:
            print(f"      {c['action']}: {c['key']} : {c['old']} -> {c['new']}")

    if write_index is None:
        print("\nDry-run: nulla e' stato scritto. Per applicare: apply --write <N>")
        return

    if not (1 <= write_index <= len(fixes)):
        print(f"Indice non valido: {write_index} (disponibili 1..{len(fixes)})")
        return
    chosen = fixes[write_index - 1]
    res = config.set_game_override(system, romfile, chosen["settings"], dry_run=False)
    if res["applied"]:
        print(f"\nApplicato fix [{write_index}] a {romfile}.")
        print(f"Backup: {res['backup']}")
        # memoria esiti: registra il set applicato, in attesa di come andra' la prossima sessione
        gid = result.get("game_id") or romfile
        gtitle = (result.get("game") or {}).get("title", "")
        outcomes.note_applied(system, gid, chosen["settings"], source=chosen["source"], game_title=gtitle)
        print("Registrato negli esiti: alla prossima diagnosi vedremo se ha funzionato.")
    else:
        print(f"\nNessuna modifica necessaria (i valori erano gia' quelli del fix).")


def cmd_restore(args):
    """Annulla l'ultima modifica a batocera.conf ripristinando l'ultimo backup.
    Senza --write e' un dry-run. La conf attuale viene salvata come backup prima
    del ripristino, quindi anche il restore e' annullabile (restore di nuovo)."""
    baks = config.list_backups()
    if not baks:
        print("Nessun backup di batocera.conf trovato: niente da ripristinare.")
        return
    print("Backup disponibili (dal piu' recente):")
    for p in baks:
        print(f"  {p.name}")
    if "--write" not in args:
        print(f"\nDry-run: ripristinerei {baks[0].name}. Per farlo davvero: restore --write")
        return
    res = config.restore_latest_backup(dry_run=False)
    print(f"\nRipristinato batocera.conf da: {Path(res['restored_from']).name}")
    print(f"La conf pre-ripristino e' salvata come: {Path(res['safety_backup']).name}")
    print("(per annullare il ripristino: restore --write di nuovo)")


def cmd_sets(system, game_id, emulator=None):
    """Mostra i set grafici che SudoBat GENERA per un gioco, sulla base della
    fascia hardware rilevata e della pesantezza del gioco. Sola lettura."""
    prof = hardware.profile()
    game = catalog.find_game(system, game_id)
    title = game.get("title") if game else game_id
    heaviness = game.get("heaviness", "medium") if game else "medium"
    if emulator is None:
        emulator = {"ps2": "pcsx2", "psx": "duckstation"}.get(system, "")
    print(f"Gioco: {title}  ({system}/{emulator}, pesantezza: {heaviness})")
    print(f"Hardware rilevato: {prof.gpu_name} -> fascia {prof.tier}")
    sets = tuning.profiles_for(system, game_id, prof.tier, emulator)
    if not sets:
        print("Nessun set generabile per questo emulatore (sistema leggero o non modellato).")
        return
    src = "override dal catalogo" if sets and not sets[0].get("generated") else "generati dal motore"
    print(f"\nSet proposti ({src}) — SudoBat consiglia quello con ★:")
    for s in sets:
        star = ""
        if s.get("recommended"):
            star = " ★ CONSIGLIATO" + (f" ({s['reco_reason']})" if s.get("reco_reason") else "")
        print(f"\n  [{s['name']}]{star}")
        print(f"    {s.get('desc','')}")
        print(f"    settaggi: " + ", ".join(f"{k}={v}" for k, v in s["settings"].items()))
        if s.get("verdict"):
            print(f"    storico: {s['verdict']}")


def cmd_brain():
    """Turbo OPZIONALE: solo se l'ultimo lancio ha un crash che il motore offline
    NON riconosce, interroga Groq. Non applica nulla; mostra un suggerimento
    verificato e a bassa fiducia. Il cuore resta offline."""
    from . import brain, logscan
    result = diagnose_mod.diagnose()
    if "error" in result:
        print(result["error"])
        return
    launch = result["launch"]
    if not result.get("suspected_crash"):
        print("Nessun crash sospetto sull'ultimo lancio: niente da spiegare.")
        return
    if result.get("emulator_crashes"):
        print("Il motore OFFLINE ha gia' riconosciuto il crash (turbo non necessario):")
        for c in result["emulator_crashes"]:
            print(f"  - {c['cause']}")
            if c.get("recommend_emulator"):
                print(f"    -> cambia emulatore in: {c['recommend_emulator']}")
        return

    system = launch.get("system", "")
    emulator = launch.get("emulator", "")
    if not brain.available():
        print("Crash NON riconosciuto dal motore offline, e nessuna chiave Groq configurata.")
        print("Serve la TUA chiave gratuita (guida: docs/GROQ_SETUP.it.md), poi:")
        print("  python3 -m sudobat.cli key set gsk_LA_TUA_CHIAVE")
        return

    log_path = logscan.emulator_log_path(emulator)
    tail = ""
    if log_path:
        tail = "\n".join(Path(log_path).read_text(errors="replace").splitlines()[-40:])
    prof = hardware.profile()
    context = {
        "hardware": {"gpu": prof.gpu_name, "cpu": prof.cpu_model, "ram_mb": prof.ram_mb, "tier": prof.tier},
        "system": system, "emulator": emulator,
        "game": (result.get("game") or {}).get("title") or result.get("game_id"),
        "symptom": f"crash sospetto dopo {result.get('duration_seconds')}s dall'avvio",
        "crash_log_tail": tail,
    }
    print("Crash non riconosciuto offline -> interrogo il turbo Groq (bassa fiducia, verra' verificato)...\n")
    sug = brain.ask_about_crash(context, system, emulator)
    if not sug:
        print("Il turbo non ha dato una risposta usabile. Resta valido il motore offline.")
        return
    print(f"[SUGGERIMENTO LLM — {sug['source']} — fiducia {sug['confidence']}, VERIFICATO, non applicato]")
    print(f"  Causa (ipotesi): {sug['cause']}")
    print(f"  Spiegazione: {sug['explanation']}")
    if sug.get("recommend_emulator"):
        print(f"  Consiglia di cambiare emulatore in: {sug['recommend_emulator']} (lo fai tu)")
    if sug["settings"]:
        print(f"  Impostazioni proposte (chiavi/valori vagliati): {sug['settings']}")
        print("  Per applicarle serve la tua conferma (percorso apply, con backup).")
    else:
        print("  Nessuna impostazione sicura proposta (scartate quelle non valide).")
    if sug["rejected_keys"]:
        print(f"  Scartate dal verificatore: {sug['rejected_keys']}")

    # --- distillazione: proporre di trasformare la diagnosi in regola OFFLINE ---
    from . import distill
    cand, reason = distill.build_candidate(sug, tail, emulator)
    if not cand:
        print(f"\n[distillazione] non imparo una regola: {reason}")
        return
    pending = {
        "diag_key": distill.diag_key_for(emulator), "rule": cand,
        "game": context["game"], "when": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _PENDING_RULE.write_text(json.dumps(pending, indent=2, ensure_ascii=False))
    print("\n[distillazione] candidato regola OFFLINE pronto (ancorato al log):")
    print(f"    riconoscera': {cand['match_log_pattern'][:80]}")
    print(f"    causa: {cand['cause']}")
    if cand.get("recommend_emulator"):
        print(f"    -> emulatore: {cand['recommend_emulator']}")
    if cand.get("fix_suggestions"):
        print(f"    -> settings: {cand['fix_suggestions'][0]['settings']}")
    print("    Per INSEGNARLA a SudoBat (offline d'ora in poi): python3 -m sudobat.cli learn")


def cmd_key(args):
    """Gestione della chiave API Groq PERSONALE dell'utente (il turbo e' opzionale
    e ognuno usa la propria chiave gratuita: i limiti di utilizzo sono i suoi, non
    condivisi). La chiave vive solo in state/groq_key.txt (gitignorata, permessi
    600) e non lascia mai il box se non verso Groq."""
    from . import brain
    if not args:
        st = brain.key_status()
        if st["configured"]:
            src = "variabile d'ambiente GROQ_API_KEY" if st["source"] == "env" else st["source"]
            print(f"Turbo AI: CONFIGURATO — chiave {st['masked']} (da: {src})")
            print("Per verificarla davvero (serve rete): key test")
        else:
            print("Turbo AI: NON configurato (l'app funziona comunque, solo motore offline).")
            print("Serve la TUA chiave gratuita di Groq — guida passo-passo per ottenerla:")
            print("  docs/GROQ_SETUP.it.md (italiano) / docs/GROQ_SETUP.md (english)")
            print("Poi: python3 -m sudobat.cli key set gsk_LA_TUA_CHIAVE")
        return
    action = args[0]
    if action == "set":
        if len(args) < 2:
            print("Uso: key set <CHIAVE>   (la chiave inizia con gsk_)")
            return
        try:
            path = brain.save_key(args[1])
        except ValueError as e:
            print(f"Chiave rifiutata: {e}")
            return
        print(f"Chiave salvata in {path} (solo su questo box, permessi 600).")
        print("Verifica con: key test")
    elif action == "test":
        ok, msg = brain.test_key()
        print(("OK: " if ok else "ERRORE: ") + msg)
    elif action == "remove":
        removed = brain.remove_key()
        print("Chiave rimossa." if removed else "Nessuna chiave salvata da rimuovere.")
        if brain.key_status()["configured"]:
            print("Attenzione: resta attiva una chiave dalla variabile d'ambiente GROQ_API_KEY.")
    else:
        print("Uso: key [set <CHIAVE> | test | remove]")


def cmd_share(args):
    """Stato e controllo della condivisione opt-in (vedi KNOWLEDGE_SHARING.md).
    Nessun invio avviene mai senza consenso; qui si puo' dare/revocare."""
    from . import share
    if not args:
        c = share.consent()
        stato = {"yes": "ATTIVA", "no": "disattivata"}.get(c, "mai decisa (la UI chiede alla prima validazione)")
        print(f"Condivisione set validati: {stato}")
        if c == "yes":
            print(f"Install id (casuale, per il quorum): {share.install_id()}")
        q = share.queue_length()
        if q:
            print(f"In coda da inviare: {q} (share flush per ritentare)")
        return
    if args[0] == "on":
        share.set_consent(True)
        print("Condivisione ATTIVATA. Grazie: i tuoi set buoni aiuteranno gli altri.")
    elif args[0] == "off":
        share.set_consent(False)
        print("Condivisione disattivata. Nessun dato verra' piu' inviato.")
    elif args[0] == "flush":
        sent = share.flush()
        print(f"Inviati {sent} set (in coda restano {share.queue_length()}).")
    else:
        print("Uso: share [on|off|flush]")


def cmd_knowledge(args):
    """Scarica/aggiorna la conoscenza community dal repo pubblico sudobat-knowledge."""
    from . import knowledge
    if not args or args[0] != "update":
        print("Uso: knowledge update")
        return
    try:
        res = knowledge.update()
    except Exception as e:
        print(f"Aggiornamento fallito (rete? repo?): {e}")
        return
    if res["files"]:
        print(f"Conoscenza community aggiornata: {res['games']} giochi in {res['files']} sistemi.")
        print(f"Cartella: {knowledge.community_dir()}")
    else:
        print("Nessuna conoscenza community disponibile ancora (repo vuoto): riprova piu' avanti.")


def cmd_learn():
    """Conferma umana del loop di distillazione: salva la regola candidata prodotta
    da `brain` nel file diagnostics, con backup. Da quel momento il crash e'
    riconosciuto OFFLINE."""
    from . import distill
    if not _PENDING_RULE.exists():
        print("Nessuna regola in attesa. Prima lancia `brain` su un crash che il")
        print("motore offline non riconosce.")
        return
    pending = json.loads(_PENDING_RULE.read_text())
    diag_key, rule = pending["diag_key"], pending["rule"]
    for r in catalog.load_diagnostics(diag_key).get("rules", []):
        if r.get("match_log_pattern") == rule["match_log_pattern"]:
            print("Regola gia' presente: non la riaggiungo.")
            _PENDING_RULE.unlink()
            return
    res = distill.append_rule(diag_key, rule)
    _PENDING_RULE.unlink()
    print(f"Imparata. Scritta in: {res['path']}")
    if res["backup"]:
        print(f"Backup: {res['backup']}")
    print("Da ora SudoBat riconosce questo crash OFFLINE (niente piu' LLM).")
    print(f"Per annullare: git checkout {res['path']}")


def cmd_history(system, game_id):
    """Storico degli esiti registrati per un gioco: quali set sono stati applicati
    e com'e' andata la sessione dopo."""
    recs = outcomes.history(system, game_id)
    if not recs:
        print(f"Nessun esito registrato per {system}/{game_id}.")
        return
    print(f"Storico esiti per {system}/{game_id}:")
    for r in recs:
        res = r.get("result", "?")
        mark = {"ok": "OK   ", "crash": "CRASH", "pending": "in attesa"}.get(res, res)
        print(f"  [{mark}] {r.get('when','')} ({r.get('source','')}) -> {r.get('settings')}")


def cmd_last_launch():
    if not _STATE_FILE.exists():
        print("Nessun lancio tracciato ancora (hook non installato o mai lanciato un gioco).")
        return
    print(json.dumps(json.loads(_STATE_FILE.read_text()), indent=2, ensure_ascii=False))


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    cmd, *rest = argv
    if cmd == "profile":
        cmd_profile()
    elif cmd == "identify-ps2":
        cmd_identify_ps2(rest[0])
    elif cmd == "identify-psx":
        cmd_identify_psx(rest[0])
    elif cmd == "lookup":
        cmd_lookup(rest[0], rest[1])
    elif cmd == "last-launch":
        cmd_last_launch()
    elif cmd == "diagnose":
        cmd_diagnose()
    elif cmd == "apply":
        cmd_apply(rest)
    elif cmd == "restore":
        cmd_restore(rest)
    elif cmd == "sets":
        cmd_sets(*rest[:3])
    elif cmd == "brain":
        cmd_brain()
    elif cmd == "key":
        cmd_key(rest)
    elif cmd == "share":
        cmd_share(rest)
    elif cmd == "knowledge":
        cmd_knowledge(rest)
    elif cmd == "learn":
        cmd_learn()
    elif cmd == "history":
        cmd_history(rest[0], rest[1])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
