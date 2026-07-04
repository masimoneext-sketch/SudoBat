# SudoBat — Copyright © 2026 Marco Simone. PolyForm Noncommercial License 1.0.0.
# Uso personale/non commerciale libero; uso commerciale solo con licenza separata. Vedi LICENSE.md.
"""Self-test del MOTORE (stile RomsOrganizer): `python3 -m sudobat.selftest`.

Copre i pezzi che toccano il sistema (config, hook, distillazione) e la logica
di apprendimento (esiti, escalation, verifica LLM), con FIXTURE in directory
temporanee: non legge ne' scrive MAI su /userdata o sui file veri del repo.
Non richiede pygame (il selftest della UI e' a parte: python3 -m sudobat.ui
--selftest) ne' rete: gira identico sul Batocera e su qualunque Linux.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import traceback
from pathlib import Path

import yaml

from . import brain, catalog, config, diagnose, distill, escalate, outcomes, tuning
from .ui import i18n

_REPO = Path(__file__).parent.parent
_HOOK = _REPO / "scripts" / "sudobat-hook.sh"

_CONF_FIXTURE = """## batocera.conf di prova (fixture)
# commento da preservare

wifi.enabled=0
global.videomode=auto
ps2["Grand Theft Auto - San Andreas (Europe).iso"].pcsx2_resolution=2
"""

_TESTS = []


def test(fn):
    _TESTS.append(fn)
    return fn


def _write_conf(tmp: Path) -> Path:
    conf = tmp / "batocera.conf"
    conf.write_text(_CONF_FIXTURE)
    return conf


# ------------------------------------------------------------------ config
@test
def config_parse_e_override():
    with tempfile.TemporaryDirectory() as td:
        conf = _write_conf(Path(td))
        values = config.parse(conf)
        assert values["wifi.enabled"] == "0"
        assert values["global.videomode"] == "auto"
        assert "# commento da preservare" not in values
        romfile = "Grand Theft Auto - San Andreas (Europe).iso"
        assert config.get_game_override(values, "ps2", romfile, "pcsx2_resolution") == "2"
        key = config.game_override_key("ps2", romfile, "pcsx2_gfxbackend")
        assert key == f'ps2["{romfile}"].pcsx2_gfxbackend'


@test
def config_plan_changes():
    with tempfile.TemporaryDirectory() as td:
        conf = _write_conf(Path(td))
        plan = config.plan_changes({"wifi.enabled": "0",       # unchanged
                                    "global.videomode": "max", # update
                                    "nuova.chiave": "x"}, conf)  # add
        actions = {c["key"]: c["action"] for c in plan}
        assert actions == {"wifi.enabled": "unchanged",
                           "global.videomode": "update",
                           "nuova.chiave": "add"}


@test
def config_set_values_dry_run_non_scrive():
    with tempfile.TemporaryDirectory() as td:
        conf = _write_conf(Path(td))
        before = conf.read_text()
        res = config.set_values({"global.videomode": "max"}, conf)  # dry_run default
        assert res["applied"] is False and res["backup"] is None
        assert conf.read_text() == before
        assert config.list_backups(conf) == []


@test
def config_set_values_scrittura_chirurgica():
    with tempfile.TemporaryDirectory() as td:
        conf = _write_conf(Path(td))
        before = conf.read_text()
        res = config.set_values({"global.videomode": "max", "nuova.chiave": "x"},
                                conf, dry_run=False)
        assert res["applied"] is True
        text = conf.read_text()
        assert text.endswith("\n")
        lines = text.splitlines()
        # commenti e ordine preservati, update in-place, add in fondo
        assert lines[0] == "## batocera.conf di prova (fixture)"
        assert "# commento da preservare" in lines
        assert lines.index("wifi.enabled=0") < lines.index("global.videomode=max")
        assert lines[-1] == "nuova.chiave=x"
        # backup: esiste e contiene il contenuto PRE-scrittura
        assert res["backup"] and Path(res["backup"]).read_text() == before


@test
def config_backup_stesso_secondo_non_si_sovrascrive():
    with tempfile.TemporaryDirectory() as td:
        conf = _write_conf(Path(td))
        b1 = config.backup(conf)
        b2 = config.backup(conf)  # stesso secondo: deve prendere il suffisso -1
        assert b1 != b2 and b1.exists() and b2.exists()


@test
def config_list_backups_ordine():
    with tempfile.TemporaryDirectory() as td:
        conf = _write_conf(Path(td))
        names = ["batocera.conf.sudobat-bak-20260702-101010",
                 "batocera.conf.sudobat-bak-20260703-101010",
                 "batocera.conf.sudobat-bak-20260703-101010-2",
                 "batocera.conf.sudobat-bak-20260703-101010-10"]
        for n in names:
            (Path(td) / n).write_text("x")
        got = [p.name for p in config.list_backups(conf)]
        # ordine per (timestamp, contatore NUMERICO): -10 e' piu' recente di -2
        assert got == [names[3], names[2], names[1], names[0]], got


@test
def config_rotate_backups():
    with tempfile.TemporaryDirectory() as td:
        conf = _write_conf(Path(td))
        for i in range(1, 6):
            (Path(td) / f"batocera.conf.sudobat-bak-2026070{i}-101010").write_text("x")
        removed = config.rotate_backups(conf, keep=3)
        assert len(removed) == 2
        rest = [p.name for p in config.list_backups(conf)]
        assert rest == ["batocera.conf.sudobat-bak-20260705-101010",
                        "batocera.conf.sudobat-bak-20260704-101010",
                        "batocera.conf.sudobat-bak-20260703-101010"]


@test
def config_restore_annulla_ultima_modifica():
    with tempfile.TemporaryDirectory() as td:
        conf = _write_conf(Path(td))
        original = conf.read_text()
        config.set_values({"global.videomode": "max"}, conf, dry_run=False)
        modified = conf.read_text()
        assert modified != original

        # dry-run: indica il backup ma non tocca nulla
        res = config.restore_latest_backup(conf)
        assert res["restored"] is False and res["restored_from"]
        assert conf.read_text() == modified

        # restore vero: torna all'originale, con safety backup del modificato
        res = config.restore_latest_backup(conf, dry_run=False)
        assert res["restored"] is True
        assert conf.read_text() == original
        assert Path(res["safety_backup"]).read_text() == modified

        # undo dell'undo: un secondo restore torna allo stato modificato
        res2 = config.restore_latest_backup(conf, dry_run=False)
        assert res2["restored"] is True and conf.read_text() == modified


# -------------------------------------------------------------------- hook
def _run_hook(state_dir: str, *args) -> None:
    env = dict(os.environ, SUDOBAT_STATE_DIR=state_dir)
    subprocess.run(["bash", str(_HOOK), *args], env=env, check=True, timeout=10)


@test
def hook_json_valido_con_nome_rom_ostile():
    with tempfile.TemporaryDirectory() as td:
        # virgolette e backslash nel filename: senza escape il JSON esplode
        rom = '/userdata/roms/ps2/Gioco "Speciale" \\ Test (Europe).iso'
        _run_hook(td, "gameStart", "ps2", "pcsx2", "pcsx2", rom)
        data = json.loads((Path(td) / "last_launch.json").read_text())
        assert data["event"] == "gameStart"
        assert data["rom"] == rom          # roundtrip fedele, nessuna perdita
        assert data["system"] == "ps2" and isinstance(data["timestamp"], int)


@test
def hook_gamestop_append_senza_toccare_lo_start():
    with tempfile.TemporaryDirectory() as td:
        rom = "/userdata/roms/ps2/Gioco.iso"
        _run_hook(td, "gameStart", "ps2", "pcsx2", "pcsx2", rom)
        start = (Path(td) / "last_launch.json").read_text()
        _run_hook(td, "gameStop", "ps2", "pcsx2", "pcsx2", rom)
        _run_hook(td, "gameStop", "ps2", "pcsx2", "pcsx2", rom)
        assert (Path(td) / "last_launch.json").read_text() == start
        stops = (Path(td) / "last_launch.json.stop_log").read_text().splitlines()
        assert len(stops) == 2 and all(json.loads(s)["event"] == "gameStop" for s in stops)


@test
def hook_ignora_il_lancio_di_sudobat_stesso():
    with tempfile.TemporaryDirectory() as td:
        _run_hook(td, "gameStart", "ports", "ports", "", "/userdata/roms/ports/SudoBat.sh")
        assert not (Path(td) / "last_launch.json").exists()


# ----------------------------------------------------------------- outcomes
class _PatchStore:
    """Reindirizza outcomes.json su un file temporaneo per la durata del test."""

    def __enter__(self):
        self._td = tempfile.TemporaryDirectory()
        self._orig = outcomes._STORE
        outcomes._STORE = Path(self._td.name) / "outcomes.json"
        return self

    def __exit__(self, *exc):
        outcomes._STORE = self._orig
        self._td.cleanup()


@test
def outcomes_flusso_pending_flag_storico():
    with _PatchStore():
        st = {"pcsx2_resolution": "2"}
        outcomes.note_applied("ps2", "SLUS-205.60", st, source="test", game_title="GTA SA")
        pend = outcomes.pending_for("ps2", "SLUS-205.60")
        assert pend and pend["result"] == "pending" and pend["settings"] == st

        good = {"fluido": True, "fps_ok": True, "scatti_concitate": False, "glitch": False}
        assert outcomes.is_good_experience(good)
        rec = outcomes.resolve_flags("ps2", "SLUS-205.60", good)
        assert rec and rec["result"] == "good"
        assert outcomes.pending_for("ps2", "SLUS-205.60") is None

        tr = outcomes.track_record("ps2", "SLUS-205.60", st)
        assert tr == {"ok": 1, "crash": 0}
        assert "OK" in outcomes.verdict("ps2", "SLUS-205.60", st)


@test
def outcomes_sessione_osservata_e_guardia_lancio():
    """Questionario universale: una sessione SENZA apply diventa storico coi flag
    (record 'osservato'), e la guardia anti-molestia chiede una volta per lancio."""
    with _PatchStore():
        orig_judged = outcomes._JUDGED_FILE
        outcomes._JUDGED_FILE = outcomes._STORE.parent / "judged_launch.json"
        try:
            outcomes.note_observed("switch", "01006b601380e000", {}, game_title="Kirby RtDL")
            pend = outcomes.pending_for("switch", "01006b601380e000")
            assert pend and pend["source"] == "osservato" and pend["settings"] == {}
            good = {"fluido": True, "fps_ok": True, "scatti_concitate": False, "glitch": False}
            rec = outcomes.resolve_flags("switch", "01006b601380e000", good)
            assert rec and rec["result"] == "good"
            tr = outcomes.track_record("switch", "01006b601380e000", {})
            assert tr == {"ok": 1, "crash": 0}

            assert not outcomes.already_judged(1234567)
            outcomes.mark_judged(1234567)
            assert outcomes.already_judged(1234567)
            assert not outcomes.already_judged(7654321)  # un lancio nuovo si giudica
        finally:
            outcomes._JUDGED_FILE = orig_judged


@test
def diagnose_verdetto_sessione():
    """Classificatore a 3 esiti sui SOLI segnali universali (durata, regole log):
    crash -> diagnosi; clean/short -> questionario; unknown -> non si giudica."""
    sv = diagnose.session_verdict
    assert sv(None, None, []) == "unknown"          # nessuno stop registrato
    assert sv(8, True, []) == "crash"               # morto subito
    assert sv(1200, False, [{"cause": "x"}]) == "crash"  # fatal riconosciuto nel log
    assert sv(1200, False, []) == "clean"           # 20 min finiti puliti
    assert sv(30, False, []) == "short"             # uscito subito: chiedi comunque


@test
def outcomes_rerank_promuove_gli_esiti_reali():
    with _PatchStore():
        s_eur = {"pcsx2_resolution": "4"}   # euristica, ma sul campo crasha
        s_alt = {"pcsx2_resolution": "2"}   # alternativa, sul campo funziona
        outcomes.note_applied("ps2", "SLUS-205.60", s_eur)
        outcomes.resolve("ps2", "SLUS-205.60", "crash")
        outcomes.note_applied("ps2", "SLUS-205.60", s_alt)
        outcomes.resolve("ps2", "SLUS-205.60", "ok")

        sets = [{"name": "Qualita'", "recommended": True, "settings": s_eur},
                {"name": "Fluidita'", "recommended": False, "settings": s_alt}]
        ranked = outcomes.rerank(sets, "ps2", "SLUS-205.60")
        chosen = next(s for s in ranked if s["recommended"])
        assert chosen["settings"] == s_alt
        assert chosen["reco_reason_key"] == "reco_field_ok"


# ------------------------------------------------------------------ distill
class _PatchDataDir:
    """Reindirizza sudobat/data (catalogo + diagnostics) su una dir temporanea."""

    def __enter__(self):
        self._td = tempfile.TemporaryDirectory()
        self._orig = catalog._DATA_DIR
        catalog._DATA_DIR = Path(self._td.name)
        (catalog._DATA_DIR / "diagnostics").mkdir()
        (catalog._DATA_DIR / "systems").mkdir()
        return self

    def __exit__(self, *exc):
        catalog._DATA_DIR = self._orig
        self._td.cleanup()


@test
def distill_pulizia_firma():
    sig = "[  212.626521] VK_ERROR_DEVICE_LOST in scheda video"
    clean = distill._clean_signature(sig)
    assert clean.startswith("VK_ERROR_DEVICE_LOST")
    assert len(distill._clean_signature("x" * 500)) <= 120


@test
def distill_candidato_ancorato_al_log():
    log = "riga uno\n[  212.6] VK_ERROR_DEVICE_LOST while drawing\nriga tre"
    base = {"source": "groq:test", "cause": "driver", "explanation": "spiegazione",
            "settings": {"pcsx2_gfxbackend": 12}, "recommend_emulator": None,
            "confidence": 0.8}
    with _PatchDataDir():
        # firma inventata (non nel log) -> rifiutato
        cand, why = distill.build_candidate(dict(base, log_signature="INVENTATA"), log, "pcsx2")
        assert cand is None and "NON" in why
        # confidenza bassa -> rifiutato
        cand, _ = distill.build_candidate(
            dict(base, log_signature="VK_ERROR_DEVICE_LOST while drawing", confidence=0.2),
            log, "pcsx2")
        assert cand is None
        # firma vera nel log -> accettato, pattern che rimatcha il log
        cand, why = distill.build_candidate(
            dict(base, log_signature="VK_ERROR_DEVICE_LOST while drawing"), log, "pcsx2")
        assert why == "ok" and cand["source"] == "distilled"
        assert re.search(cand["match_log_pattern"], log)


@test
def distill_append_rule_yaml_valido():
    rule = {"match_log_pattern": re.escape(r"errore 'strano' con \ backslash"),
            "cause": "causa con 'apici' dentro",
            "source": "distilled", "learned": "test",
            "fix_suggestions": [{"description": "desc", "settings": {"k": 1}}]}
    with _PatchDataDir():
        res = distill.append_rule("pcsx2", rule)
        loaded = catalog.load_diagnostics("pcsx2")
        rules = loaded.get("rules") or []
        assert len(rules) == 1
        # il pattern sopravvive al roundtrip YAML e rimatcha la riga originale
        assert re.search(rules[0]["match_log_pattern"], r"errore 'strano' con \ backslash")
        assert res["path"].endswith("pcsx2.yaml")


# -------------------------------------------------------------------- brain
@test
def brain_estrazione_json():
    assert brain._extract_json('{"a": 1}') == {"a": 1}
    assert brain._extract_json('bla {"a": 1} bla') == {"a": 1}
    assert brain._extract_json("niente json") is None


@test
def brain_verify_confine_di_sicurezza():
    orig_keys, orig_vals = tuning.known_keys, tuning.known_values
    tuning.known_keys = lambda emu, core="": {"pcsx2_gfxbackend", "pcsx2_resolution"}
    tuning.known_values = lambda emu, core="": {"pcsx2_gfxbackend": {"12", "14"}}
    try:
        raw = {"cause": "c", "explanation": "e", "log_signature": "sig",
               "confidence": 0.9, "recommend_emulator": None,
               "proposed_settings": {"pcsx2_gfxbackend": 12,     # ok (valore vagliato)
                                     "pcsx2_gfxbackend_typo": 1,  # chiave sconosciuta
                                     "pcsx2_resolution": 3}}      # ok (nessun vincolo valori)
        out = brain.verify(raw, "ps2", "pcsx2")
        assert out["settings"] == {"pcsx2_gfxbackend": 12, "pcsx2_resolution": 3}
        assert len(out["rejected_keys"]) == 1 and "typo" in out["rejected_keys"][0]
        # valore fuori dai vagliati -> scartato
        raw["proposed_settings"] = {"pcsx2_gfxbackend": 99}
        assert brain.verify(raw, "ps2", "pcsx2")["settings"] == {}
    finally:
        tuning.known_keys, tuning.known_values = orig_keys, orig_vals


@test
def brain_gestione_chiave_personale():
    orig_file = brain._KEY_FILE
    orig_env = os.environ.pop("GROQ_API_KEY", None)
    try:
        with tempfile.TemporaryDirectory() as td:
            brain._KEY_FILE = Path(td) / "state" / "groq_key.txt"
            assert brain.key_status()["configured"] is False
            # chiavi malformate rifiutate PRIMA di scrivere
            for bad in ("", "  ", "gsk_corta", "gsk_con spazi dentro_abcdefghijk",
                        "sk-formato-openai-non-groq-12345"):
                try:
                    brain.save_key(bad)
                    assert False, f"chiave accettata ma invalida: {bad!r}"
                except ValueError:
                    pass
            # chiave ben formata: salvata con permessi 600, mascherata nello stato
            key = "gsk_" + "a" * 40 + "WXYZ"
            path = brain.save_key(f'  "{key}"  ')  # sopravvive a spazi/virgolette incollati
            assert path.read_text().strip() == key
            assert (path.stat().st_mode & 0o777) == 0o600
            st = brain.key_status()
            assert st["configured"] and st["masked"] == "···WXYZ"
            assert key not in st["masked"]          # mai la chiave in chiaro
            assert brain.api_key() == key
            # rimozione
            assert brain.remove_key() is True
            assert brain.key_status()["configured"] is False
            assert brain.remove_key() is False
    finally:
        brain._KEY_FILE = orig_file
        if orig_env is not None:
            os.environ["GROQ_API_KEY"] = orig_env


@test
def share_consenso_e_coda():
    from . import share
    orig_p, orig_q = share._PREFS, share._QUEUE
    try:
        with tempfile.TemporaryDirectory() as td:
            share._PREFS = Path(td) / "share_prefs.json"
            share._QUEUE = Path(td) / "share_queue.json"
            assert share.consent() is None            # mai chiesto
            entry = share.build_entry(system="ps2", game_id="SLUS-205.60",
                                      game_title="GTA SA", tier="igpu-weak",
                                      emulator="pcsx2", core="pcsx2",
                                      settings={"pcsx2_resolution": 2},
                                      flags={"fluido": True, "fps_ok": True,
                                             "scatti_concitate": False, "glitch": False})
            share.enqueue(entry)
            assert share.queue_length() == 1
            # senza consenso NON invia nulla (nemmeno con la coda piena)
            assert share.flush() == 0 and share.queue_length() == 1
            share.set_consent(False)
            assert share.consent() == "no" and share.flush() == 0
            share.set_consent(True)
            assert share.consent() == "yes"
            iid = share.install_id()
            assert iid and len(iid) == 36              # uuid4 casuale
            share.set_consent(True)
            assert share.install_id() == iid           # stabile, non rigenerato
    finally:
        share._PREFS, share._QUEUE = orig_p, orig_q


@test
def share_flush_invia_al_collettore():
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading
    from . import share

    received = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            received.append(json.loads(body))
            self.send_response(204)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    orig_p, orig_q = share._PREFS, share._QUEUE
    os.environ["SUDOBAT_KNOWLEDGE_ENDPOINT"] = f"http://127.0.0.1:{srv.server_port}/api/v1/sets"
    try:
        with tempfile.TemporaryDirectory() as td:
            share._PREFS = Path(td) / "p.json"
            share._QUEUE = Path(td) / "q.json"
            share.set_consent(True)
            share.enqueue(share.build_entry(system="ps2", game_id="X", game_title="",
                                            tier="igpu-weak", emulator="pcsx2", core="",
                                            settings={"pcsx2_resolution": 2},
                                            flags={"fluido": True}))
            assert share.flush() == 1 and share.queue_length() == 0
            assert received and received[0]["schema"] == share.SCHEMA
            assert received[0]["install_id"] == share.install_id()
            assert received[0]["settings"] == {"pcsx2_resolution": 2}
    finally:
        os.environ.pop("SUDOBAT_KNOWLEDGE_ENDPOINT", None)
        share._PREFS, share._QUEUE = orig_p, orig_q
        srv.shutdown()


@test
def knowledge_valida_e_installa_community():
    from . import knowledge
    good = """
games:
  SLUS-205.60:
    title: "GTA San Andreas"
    tiers:
      igpu-weak:
        - settings: {pcsx2_gfxbackend: 12, pcsx2_resolution: 2}
          confirmations: 4
          emulator: pcsx2
"""
    evil = """
games:
  EVIL-01:
    tiers:
      igpu-weak:
        - settings: {"chiave con spazi e simboli!!": "x"}
        - settings: {pcsx2_ok: "valore_lunghissimo_oltre_il_cap_di_trentadue_caratteri_bloccato"}
"""
    with _PatchDataDir():
        res = knowledge.install_from_files({"ps2.yaml": good, "evil.yaml": evil,
                                            "../hax.yaml": good, "NO Valido!.yaml": good,
                                            "rotto.yaml": "x: ["})
        # passano ps2.yaml e ../hax.yaml (il path traversal viene NEUTRALIZZATO:
        # basename dentro community/); evil (entry invalide), nome sporco e yaml
        # rotto vengono scartati.
        assert res == {"files": 2, "games": 2}, res
        written = sorted(p.name for p in knowledge.community_dir().glob("*"))
        assert written == ["hax.yaml", "ps2.yaml"], written
        sets = catalog.community_sets("ps2", "SLUS-205.60", "igpu-weak")
        assert len(sets) == 1 and sets[0]["confirmations"] == 4
        assert sets[0]["settings"] == {"pcsx2_gfxbackend": 12, "pcsx2_resolution": 2}
        assert catalog.community_sets("ps2", "SLUS-205.60", "dgpu-mid") == []
        assert catalog.community_sets("evil", "EVIL-01", "igpu-weak") == []


# ----------------------------------------------------------------- escalate
@test
def escalate_scala_delle_mosse():
    orig = tuning.lighter_set
    flags_bad_perf = {"fluido": False, "fps_ok": True,
                      "scatti_concitate": False, "glitch": False}
    try:
        # esperienza buona -> good
        good = {"fluido": True, "fps_ok": True, "scatti_concitate": False, "glitch": False}
        assert escalate.next_move("ps2", "pcsx2", "igpu-weak", {}, good)["kind"] == "good"
        # problema di prestazioni con un set piu' leggero disponibile -> lighter
        tuning.lighter_set = lambda emu, st, core="": {"name": "Piu' leggero", "settings": {}}
        mv = escalate.next_move("ps2", "pcsx2", "igpu-weak", {}, flags_bad_perf)
        assert mv["kind"] == "lighter" and mv["why_key"] == "why_notfluid"
        # gia' al minimo -> palla a core/emulatore (manuale)
        tuning.lighter_set = lambda emu, st, core="": None
        mv = escalate.next_move("ps2", "pcsx2", "igpu-weak", {}, flags_bad_perf)
        assert mv["kind"] == "manual_emulator" and mv["reason_key"] == "manual_lightest"
        # solo glitch (fluido) -> manuale, motivo glitch
        gl = {"fluido": True, "fps_ok": True, "scatti_concitate": False, "glitch": True}
        mv = escalate.next_move("ps2", "pcsx2", "igpu-weak", {}, gl)
        assert mv["kind"] == "manual_emulator" and mv["reason_key"] == "manual_glitch"
    finally:
        tuning.lighter_set = orig


# ----------------------------------------------------------------- diagnose
@test
def diagnose_collect_fixes():
    result = {
        "game": {"known_issues": [
            {"symptom": "crash con Vulkan", "fix": {"pcsx2_gfxbackend": 12}},
            {"symptom": "solo consiglio manuale", "manual_fix": {"recommended": "x"}},
        ]},
        "matched_diagnostic_rules": [
            {"cause": "out of memory", "fix_suggestions": [
                {"description": "abbassa la risoluzione", "settings": {"pcsx2_resolution": 1}},
            ]},
        ],
    }
    fixes = diagnose.collect_fixes(result)
    assert len(fixes) == 2  # il manual_fix senza settings NON diventa applicabile
    assert fixes[0]["settings"] == {"pcsx2_gfxbackend": 12}
    assert fixes[1]["source"].startswith("regola log")


# --------------------------------------------------------------- dati + i18n
@test
def dati_yaml_tutti_validi():
    data_dir = Path(__file__).parent / "data"
    files = sorted(data_dir.rglob("*.yaml"))
    assert files, "nessun file YAML in sudobat/data"
    for f in files:
        loaded = yaml.safe_load(f.read_text()) or {}
        assert isinstance(loaded, dict), f"{f.name}: non e' un dict"
        for rule in (loaded.get("rules") or []):
            assert rule.get("match_log_pattern"), f"{f.name}: regola senza pattern"
            re.compile(rule["match_log_pattern"])  # il pattern deve compilare
        games = loaded.get("games")
        assert games is None or isinstance(games, dict), f"{f.name}: games non e' un dict"


@test
def i18n_parita_it_en():
    it, en = set(i18n.STRINGS["it"]), set(i18n.STRINGS["en"])
    assert it == en, f"chiavi disallineate: solo IT={it - en}, solo EN={en - it}"
    for key in ("set_restore", "restore_q", "restore_done", "restore_none"):
        assert key in it  # le chiavi del ripristino esistono in entrambe


# ------------------------------------------------------------------- runner
def main() -> int:
    passed, failed = 0, []
    for fn in _TESTS:
        name = fn.__name__
        try:
            fn()
            passed += 1
            print(f"  [ok]   {name}")
        except Exception:
            failed.append(name)
            print(f"  [FAIL] {name}")
            traceback.print_exc()
    total = len(_TESTS)
    if failed:
        print(f"\n[selftest motore] {passed}/{total} OK — FALLITI: {', '.join(failed)}")
        return 1
    print(f"\n[selftest motore] {passed}/{total} OK: config, hook, esiti, distillazione,"
          " verifica LLM, escalation, dati, i18n.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
