"""App pygame di SudoBat: macchina a stati (stile RomsOrganizer).

Ogni stato `X` ha un handler `on_X(action)` (naviga/agisce) e un `draw_X()`
(disegna). `dispatch` instrada l'azione astratta allo stato attivo. Tutta la
logica pesante vive nei moduli `sudobat.*`; qui c'e' solo presentazione.

La scrittura in batocera.conf avviene SOLO dalla schermata Diagnosi, dietro una
conferma esplicita, e passa da `config.set_game_override` (backup automatico).
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

import pygame

from .. import catalog, config, diagnose as diag_mod, escalate, hardware, outcomes, roms, tuning
from . import controls, paths, theme
from .i18n import t
from . import i18n

# --- debug live: traccia cosa fa davvero la UI mentre l'utente la prova.
# Scrive solo su cambi schermata/diagnosi (non per-frame), dentro il repo
# (state/debug.log), mai su file di sistema. Attivo sempre: e' economico e serve
# da "occhi" per chi non vede lo schermo.
import time as _time
_DEBUG_LOG = Path(__file__).parent.parent.parent / "state" / "debug.log"


def _dbg(msg: str) -> None:
    try:
        _DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(_DEBUG_LOG, "a") as fh:
            fh.write(f"{_time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass  # il debug non deve MAI far crashare la UI

# (chiave_i18n, stato). L'etichetta si risolve a runtime -> cambia con la lingua.
MAIN_ITEMS = [
    ("menu_diagnose", "diagnose"),
    ("menu_hardware", "hardware"),
    ("menu_catalog", "catalog_sys"),
    ("menu_howto", "howto"),
    ("menu_settings", "settings"),
    ("menu_quit", "__quit__"),
]

# NIENTE lista hardcoded: i sistemi si leggono dal disco a runtime (roms.list_systems()).

# Flag di fine partita: la voce dell'utente sull'esperienza VERA.
# (chiave_dato, chiave_i18n_domanda). La domanda si traduce a runtime.
FLAG_DEFS = [
    ("fluido", "flag_fluido"),
    ("fps_ok", "flag_fps_ok"),
    ("scatti_concitate", "flag_scatti_concitate"),
    ("glitch", "flag_glitch"),
]


class App:
    def __init__(self, headless: bool = False) -> None:
        self.headless = headless or bool(os.environ.get("SUDOBAT_UI_HEADLESS"))
        if self.headless:
            # Nessun display in questa modalita': si disegna su una Surface
            # offscreen (come make_preview.py). Serve solo il sottosistema font.
            pygame.font.init()
            pygame.joystick.init()
            self.has_display = False
            self.screen = pygame.Surface((1024, 640))
        else:
            pygame.init()
            try:
                self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            except pygame.error:
                self.screen = pygame.display.set_mode((1024, 640))
            pygame.display.set_caption("SudoBat")
            try:
                pygame.mouse.set_visible(False)
            except pygame.error:
                pass
            self.has_display = True
        self.clock = pygame.time.Clock()
        self.inp = controls.InputManager()
        self.running = True

        self.state = "splash"
        self.menu_index = 0
        self._fonts()

        # dati caricati pigramente
        self.diag: dict | None = None
        self.fixes: list = []
        self.tuning: list = []       # profili grafici + fix, opzioni selezionabili
        self.manual_notes: list = []  # fix che SudoBat non puo' applicare (es. cambio emulatore)
        self.hw = None
        self.cur_system = ""
        self.games: list = []
        self.systems: list = roms.list_systems()   # sistemi VERI presenti sul disco

        # turbo Groq (diagnosi assistita) — stato della schermata brain
        self.brain_applicable = False
        self.brain_loading = False
        self.brain_sug: dict | None = None
        self.brain_candidate: dict | None = None
        self.brain_reason = ""

        # dialog di conferma / messaggi
        self.confirm_lines: list[str] = []
        self.confirm_index = 1  # default su "Annulla" per sicurezza
        self.pending_action = None
        self.pending_back = "main"
        self.msg_lines: list[str] = []
        self.msg_next = "main"

        # questionario flag di fine partita (giudizio utente sull'esperienza)
        self._pending_flags: dict | None = None
        self.flags_ctx: dict = {}
        self.flag_answers: dict = {}

    def _fonts(self) -> None:
        h = self.screen.get_height()
        self.f_title = theme.make_font(max(24, h // 13))
        self.f_item = theme.make_font(max(16, h // 24))
        self.f_small = theme.make_font(max(13, h // 32))
        self.f_tiny = theme.make_font(max(11, h // 42))

    # ------------------------------------------------------------------ loop
    def run(self) -> None:
        _dbg(f"=== AVVIO UI (display={getattr(self,'has_display',None)}, "
             f"size={self.screen.get_size()}) ===")
        while self.running:
            self.handle_events()
            self.draw()
            self.clock.tick(30)
        pygame.quit()

    def handle_events(self) -> None:
        for event in pygame.event.get():
            action = self.inp.translate(event)
            if action == controls.QUIT:
                self.running = False
                return
            if action:
                self.dispatch(action)

    def dispatch(self, action: str) -> None:
        handler = getattr(self, f"on_{self.state}", None)
        if handler:
            handler(action)

    def move(self, n_items: int, action: str) -> None:
        if n_items <= 0:
            return
        if action == controls.UP:
            self.menu_index = (self.menu_index - 1) % n_items
        elif action == controls.DOWN:
            self.menu_index = (self.menu_index + 1) % n_items

    def enter(self, state: str) -> None:
        _dbg(f"-> schermata '{state}'")
        self.menu_index = 0
        if state == "diagnose":
            self._load_diagnose()
            # se hai rigiocato dopo un apply, prima chiedo com'e' andata (flag),
            # poi mostro la diagnosi. Il giudizio guida la mossa successiva.
            if self._pending_flags:
                self._start_flags(self._pending_flags)
                self._pending_flags = None
                return
        elif state == "hardware":
            self._load_hardware()
        self.state = state

    # ----------------------------------------------------------- caricamenti
    def _load_diagnose(self, resolve_outcome: bool = True) -> None:
        try:
            self.diag = diag_mod.diagnose()
        except Exception as e:  # difensivo: la UI non deve mai crashare
            self.diag = {"error": f"errore diagnosi: {e}"}
        self.tuning = []
        self.manual_notes = []
        self.brain_applicable = False
        if "error" in self.diag:
            _dbg(f"   DIAGNOSI: errore -> {self.diag['error']}")
            return
        _dbg("   DIAGNOSI: gioco={g!r} sys={s} emu={e} game_id={gid} "
             "durata={dur}s crash_sospetto={cr} crash_log={cl}".format(
                 g=(self.diag.get("game") or {}).get("title")
                   or Path(self.diag.get("launch", {}).get("rom", "")).name,
                 s=self.diag.get("launch", {}).get("system"),
                 e=self.diag.get("launch", {}).get("emulator"),
                 gid=self.diag.get("game_id"),
                 dur=self.diag.get("duration_seconds"),
                 cr=self.diag.get("suspected_crash"),
                 cl=len(self.diag.get("emulator_crashes") or [])))
        gid = self.diag.get("game_id")
        tier = self.diag.get("hardware_tier")
        system = self.diag.get("launch", {}).get("system", "")
        emu = self.diag.get("launch", {}).get("emulator", "")
        core = self.diag.get("launch", {}).get("core", "")
        rid = gid or Path(self.diag.get("launch", {}).get("rom", "")).name

        # memoria esiti: com'e' andata la sessione col set applicato?
        # (NON dopo un apply immediato: li' resolve_outcome=False, la sessione col
        #  nuovo set deve ancora avvenire.)
        if resolve_outcome and rid:
            pending = outcomes.pending_for(system, rid)
            if pending:
                if self.diag.get("suspected_crash") or self.diag.get("emulator_crashes"):
                    # crash: esito ovvio, non ti chiedo se "girava fluido".
                    outcomes.resolve(system, rid, "crash")
                    _dbg(f"   ESITO: crash auto-risolto per {rid}")
                else:
                    # hai rigiocato DOPO l'apply? allora chiedo il giudizio (flag).
                    launch_ts = self.diag.get("launch", {}).get("timestamp", 0) or 0
                    if launch_ts and launch_ts > (pending.get("ts") or 0):
                        self._pending_flags = pending
                        _dbg(f"   ESITO: giudizio in sospeso per {rid} -> chiedo i flag")

        # set grafici: GENERATI dal motore (o override dal catalogo), con ★ e verdetti
        # gia' ri-ordinati dagli esiti reali (tuning.profiles_for -> outcomes.rerank).
        for p in tuning.profiles_for(system, gid, tier, emu, core):
            self.tuning.append({"label": p.get("name", "?"), "desc": p.get("desc", ""),
                                "recommended": bool(p.get("recommended")),
                                "reco_reason": p.get("reco_reason", ""),
                                "verdict": p.get("verdict", ""),
                                "settings": p.get("settings", {}), "kind": "profilo"})
        # fix di crash applicabili (known_issues con settings)
        for fx in diag_mod.collect_fixes(self.diag):
            self.tuning.append({"label": fx["description"], "desc": fx.get("source", ""),
                                "recommended": False, "settings": fx["settings"], "kind": "fix"})
        # consigli che SudoBat NON puo' applicare (es. cambio emulatore, solo da ES),
        # mostrati SOLO se non sei gia' sull'emulatore consigliato (niente assillo).
        game = self.diag.get("game") or {}
        cur_emu = self.diag.get("launch", {}).get("emulator", "")
        for iss in game.get("known_issues", []):
            mf = iss.get("manual_fix")
            if mf and mf.get("recommended", "\0") not in cur_emu:
                self.manual_notes.append(mf)
        # selezione di default sul profilo consigliato
        self.menu_index = next((i for i, o in enumerate(self.tuning) if o["recommended"]), 0)

        # turbo applicabile SOLO se: crash sospetto, il motore offline NON l'ha
        # riconosciuto, e c'e' una chiave Groq. (Se offline gia' sa, niente turbo.)
        try:
            from .. import brain
            self.brain_applicable = bool(
                self.diag.get("suspected_crash")
                and not self.diag.get("emulator_crashes")
                and brain.available()
            )
        except Exception:
            self.brain_applicable = False

        _dbg(f"   DIAGNOSI: {len(self.tuning)} set grafici, "
             f"{len(self.manual_notes)} note manuali, "
             f"AI_applicabile={self.brain_applicable}")

    def _load_hardware(self) -> None:
        try:
            self.hw = hardware.profile()
        except Exception as e:
            self.hw = None
            self._hw_error = str(e)

    def _load_games(self, system: str) -> None:
        self.cur_system = system
        cat = catalog.load_system_catalog(system)
        games = (cat.get("games") or {})
        self.games = sorted(((gid, info) for gid, info in games.items()),
                            key=lambda kv: (kv[1].get("title") or kv[0]).lower())

    # --------------------------------------------------------------- splash
    def on_splash(self, action: str) -> None:
        if action in (controls.CONFIRM, controls.BACK, controls.SELECT):
            self.state = "main"
            self.menu_index = 0

    def draw_splash(self) -> None:
        w, h = self.screen.get_size()
        theme.draw_background(self.screen)
        theme.draw_logo(self.screen, w // 2, int(h * 0.40), scale=h / 640)
        theme.neon_text(self.screen, self.f_small, t("app_subtitle"),
                        center=(w // 2, int(h * 0.60)), color=theme.NEON_CYAN, glow=False)
        theme.neon_text(self.screen, self.f_item, t("press_key"),
                        center=(w // 2, int(h * 0.78)), color=theme.NEON_GREEN)

    # ----------------------------------------------------------------- main
    def on_main(self, action: str) -> None:
        n = len(MAIN_ITEMS)
        if action in (controls.UP, controls.DOWN):
            self.move(n, action)
        elif action == controls.CONFIRM:
            _, target = MAIN_ITEMS[self.menu_index]
            if target == "__quit__":
                self.running = False
            else:
                self.enter(target)
        elif action == controls.BACK:
            self.running = False

    def draw_main(self) -> None:
        w, h = self.screen.get_size()
        theme.draw_background(self.screen)
        self._title_bar("SudoBat")
        labels = [t(k) for k, _ in MAIN_ITEMS]
        self._draw_menu(labels, self.menu_index, top=int(h * 0.30))
        self._footer(t("footer_main"))

    # -------------------------------------------------------------- howto
    def on_howto(self, action: str) -> None:
        if action in (controls.BACK, controls.CONFIRM):
            self.enter("main")

    def draw_howto(self) -> None:
        w, h = self.screen.get_size()
        theme.draw_background(self.screen)
        self._title_bar(t("howto_title"))
        x = int(w * 0.07)
        y = int(h * 0.20)
        inner = int(w * 0.86)
        steps = [t("howto_1"), t("howto_2"), t("howto_3"), t("howto_4"), t("howto_5"),
                 t("howto_6")]
        for step in steps:
            for ln in theme.wrap_text(self.f_small, step, inner):
                self.screen.blit(self.f_small.render(ln, True, theme.WHITE), (x, y))
                y += self.f_small.get_height() + 4
            y += 8
        y += 6
        for ln in theme.wrap_text(self.f_small, t("howto_note"), inner):
            self.screen.blit(self.f_small.render(ln, True, theme.NEON_AMBER), (x, y))
            y += self.f_small.get_height() + 4
        self._footer(t("footer_back"))

    # ------------------------------------------------------------- diagnose
    def on_diagnose(self, action: str) -> None:
        if action == controls.BACK:
            self.enter("main")
            return
        # I set grafici sono SEMPRE selezionabili/applicabili (anche se c'e' un
        # consiglio manuale accanto: SudoBat applica cio' che puo', l'utente sceglie).
        if not self.tuning:
            return
        if action == controls.SELECT and self.brain_applicable:
            self._ask_brain()
            return
        if action in (controls.UP, controls.DOWN):
            self.move(len(self.tuning), action)
        elif action == controls.CONFIRM:
            self._ask_apply(self.tuning[self.menu_index])

    def draw_diagnose(self) -> None:
        w, h = self.screen.get_size()
        theme.draw_background(self.screen)
        self._title_bar(t("diag_title"))
        d = self.diag or {}
        w2 = int(w * 0.88)
        x = int(w * 0.06)
        y = int(h * 0.19)
        line_h = self.f_small.get_height() + 5

        if "error" in d:
            theme.neon_text(self.screen, self.f_item, d["error"],
                            topleft=(x, y), color=theme.NEON_AMBER, glow=False)
            self._footer(t("footer_back"))
            return

        launch = d.get("launch", {})
        rom = Path(launch.get("rom", "")).name or "?"
        dur = d.get("duration_seconds")
        crash = d.get("suspected_crash")
        if dur is not None:
            sess = f"{dur}s" + (f"  ⚠ {t('crash_suspected')}" if crash else f"  {t('session_ok')}")
        else:
            sess = t("session_running")
        # info compatta (3 righe, per lasciare spazio a avviso + profili)
        sess_label = t("lbl_session")
        info = [
            (t("lbl_game"), d.get("game", {}).get("title") if d.get("game") else rom),
            (t("lbl_sysemu"), f"{launch.get('system','?')} / {launch.get('emulator','?')}   ·   {t('tier_label')} {d.get('hardware_tier','?')}"),
            (sess_label, sess),
        ]
        for label, val in info:
            theme.neon_text(self.screen, self.f_small, f"{label}: ",
                            topleft=(x, y), color=theme.NEON_TEAL, glow=False)
            off = self.f_small.size(f"{label}: ")[0]
            col = theme.DANGER if (label == sess_label and crash) else theme.WHITE
            self.screen.blit(self.f_small.render(theme.fit_text(self.f_small, str(val), w2 - off), True, col), (x + off, y))
            y += line_h

        y += 8
        # 0) Crash riconosciuto dal log dell'emulatore (motore offline).
        for c in (d.get("emulator_crashes") or [])[:1]:
            for ln in theme.wrap_text(self.f_tiny, t("diag_crash_recognized") + c.get("cause", ""), w2):
                self.screen.blit(self.f_tiny.render(ln, True, theme.DANGER), (x, y))
                y += self.f_tiny.get_height() + 2
            y += 6

        # 1) Avviso "cosa devi fare TU a mano" (se sei sull'emulatore sbagliato).
        if self.manual_notes:
            y = self._draw_manual_advice(self.manual_notes[0], x, y, w2)
            y += 10

        # 2) Set grafici che SudoBat PUO' applicare (sempre, a prescindere dall'avviso).
        if not self.tuning:
            theme.neon_text(self.screen, self.f_small, t("no_sets"),
                            topleft=(x, y), color=theme.DIM, glow=False)
            self._footer(t("footer_back"))
            return
        theme.neon_text(self.screen, self.f_small, t("diag_sets_header"),
                        topleft=(x, y), color=theme.NEON_GREEN, glow=False)
        y += line_h + 2
        row_h = self.f_small.get_height() + self.f_tiny.get_height() + 10
        for i, opt in enumerate(self.tuning):
            sel = (i == self.menu_index)
            row = pygame.Rect(x - 8, y - 3, w2, row_h)
            if sel:
                theme.draw_panel(self.screen, row, border=theme.NEON_GREEN)
            name_col = theme.NEON_GREEN if sel else theme.WHITE
            r = theme.neon_text(self.screen, self.f_small, opt["label"], topleft=(x + 6, y),
                                color=name_col, glow=False)
            if opt.get("recommended"):
                theme.neon_text(self.screen, self.f_tiny, t("star_recommended"),
                                topleft=(r.right + 12, y + 3), color=theme.NEON_AMBER, glow=False)
            # verdetto storico (esiti reali) costruito da ok/crash -> localizzato
            ok, crash = opt.get("ok", 0), opt.get("crash", 0)
            vd, vcol = "", theme.DIM
            if ok and not crash:
                vd, vcol = t("verdict_ok", n=ok), theme.NEON_GREEN
            elif crash and not ok:
                vd, vcol = t("verdict_bad", n=crash), theme.DANGER
            elif ok or crash:
                vd = t("verdict_mixed", ok=ok, crash=crash)
            if vd:
                vs = self.f_tiny.render(theme.fit_text(self.f_tiny, vd, int(w2 * 0.5)), True, vcol)
                self.screen.blit(vs, (x + w2 - vs.get_width() - 12, y + 3))
            desc_txt = opt.get("desc", "")
            if opt.get("reco_reason_key"):
                desc_txt = f"{desc_txt}  —  {t(opt['reco_reason_key'])}"
            desc = theme.fit_text(self.f_tiny, desc_txt, row.width - 24)
            self.screen.blit(self.f_tiny.render(desc, True, theme.DIM),
                             (x + 10, y + self.f_small.get_height() + 1))
            y += row_h + 3
        if self.brain_applicable:
            self._footer(t("footer_diag_brain"))
        else:
            self._footer(t("footer_diag"))

    def _ask_apply(self, option: dict) -> None:
        launch = self.diag.get("launch", {})
        system = launch.get("system", "")
        romfile = Path(launch.get("rom", "")).name
        plan = config.set_game_override(system, romfile, option["settings"], dry_run=True)
        lines = [t("apply_q", label=option["label"]), romfile + "?", ""]
        changed = [c for c in plan["changes"] if c["action"] != "unchanged"]
        if not changed:
            lines.append(t("apply_nochange"))
        for c in changed:
            opt = c["key"].split(".")[-1]
            lines.append(f"{opt}: {c['old']} → {c['new']}")
        lines.append("")
        lines.append(t("apply_backup_note"))
        self._ask(lines, lambda: self._do_apply(option), "diagnose")

    def _do_apply(self, option: dict) -> None:
        launch = self.diag.get("launch", {})
        system = launch.get("system", "")
        romfile = Path(launch.get("rom", "")).name
        try:
            res = config.set_game_override(system, romfile, option["settings"], dry_run=False)
        except Exception as e:
            self._flash([t("apply_write_error"), str(e)], "diagnose")
            return
        # Registra SEMPRE la scelta: l'utente giochera' con questo set a prescindere dal
        # fatto che il file sia cambiato (poteva gia' avere quei valori). E' la scelta,
        # non la scrittura, che vogliamo giudicare alla prossima partita.
        rid = self.diag.get("game_id") or romfile
        gtitle = (self.diag.get("game") or {}).get("title", "")
        outcomes.note_applied(system, rid, option["settings"],
                              source=f"ui:{option['label']}", game_title=gtitle)
        self._load_diagnose(resolve_outcome=False)  # non risolvere subito il pending
        lines = [t("apply_done", label=option["label"])]
        if res["applied"]:
            lines.append(t("apply_backup", name=Path(res['backup']).name))
        lines.append(t("apply_replay_hint"))
        self._flash(lines, "diagnose")

    # ------------------------------------------------- flag di fine partita
    def _start_flags(self, record: dict) -> None:
        """Prepara il questionario 'com'e' andata?' per il set applicato di cui
        aspettiamo il giudizio. Il contesto (gioco/fascia/emulatore/set) viene dal
        record pending + dalla diagnosi corrente."""
        launch = self.diag.get("launch", {})
        self.flags_ctx = {
            "system": record["system"],
            "game_id": record["game_id"],
            "game_title": record.get("game") or (self.diag.get("game") or {}).get("title")
            or Path(launch.get("rom", "")).name,
            "tier": self.diag.get("hardware_tier", ""),
            "settings": record.get("settings", {}),
            "emulator": launch.get("emulator", ""),
            "core": launch.get("core", ""),
        }
        # default sul percorso 'buono': l'utente cambia solo cio' che e' andato storto.
        self.flag_answers = {"fluido": True, "fps_ok": True,
                             "scatti_concitate": False, "glitch": False}
        self.menu_index = 0
        self.state = "flags"
        _dbg(f"-> schermata 'flags' per {self.flags_ctx['game_id']} "
             f"set={self.flags_ctx['settings']}")

    def on_flags(self, action: str) -> None:
        n = len(FLAG_DEFS) + 1  # +1 = riga "Conferma"
        if action == controls.BACK:
            self.enter("main")   # rimanda il giudizio: il record resta pending
            return
        if action in (controls.UP, controls.DOWN):
            self.move(n, action)
            return
        if self.menu_index < len(FLAG_DEFS):
            key = FLAG_DEFS[self.menu_index][0]
            if action == controls.LEFT:
                self.flag_answers[key] = False
            elif action == controls.RIGHT:
                self.flag_answers[key] = True
            elif action == controls.CONFIRM:
                self.flag_answers[key] = not self.flag_answers[key]
        elif action == controls.CONFIRM:
            self._submit_flags()

    def draw_flags(self) -> None:
        w, h = self.screen.get_size()
        theme.draw_background(self.screen)
        self._title_bar(t("flags_title"))
        theme.neon_text(self.screen, self.f_small,
                        theme.fit_text(self.f_small, self.flags_ctx.get("game_title", ""),
                                       int(w * 0.88)),
                        topleft=(int(w * 0.06), int(h * 0.17)),
                        color=theme.NEON_CYAN, glow=False)
        y = int(h * 0.28)
        line_h = self.f_item.get_height() + 26
        for i, (key, qkey) in enumerate(FLAG_DEFS):
            sel = (self.menu_index == i)
            rect = pygame.Rect(int(w * 0.07), y - 6, int(w * 0.86), line_h - 10)
            if sel:
                theme.draw_panel(self.screen, rect, border=theme.NEON_GREEN)
            cy = y + self.f_item.get_height() // 2
            self.screen.blit(self.f_item.render(t(qkey), True,
                             theme.NEON_GREEN if sel else theme.WHITE), (int(w * 0.10), y))
            ans = self.flag_answers.get(key, False)
            for j, (lbl, val) in enumerate([(t("ans_no"), False), (t("ans_yes"), True)]):
                bx = int(w * 0.64) + j * int(w * 0.12)
                on = (ans == val)
                col = ((theme.NEON_GREEN if val else theme.DANGER) if on else theme.DIM)
                theme.neon_text(self.screen, self.f_item, lbl, center=(bx, cy),
                                color=col, glow=(on and sel))
            y += line_h
        sel = (self.menu_index == len(FLAG_DEFS))
        rect = pygame.Rect(int(w * 0.07), y - 6, int(w * 0.86), line_h - 10)
        if sel:
            theme.draw_panel(self.screen, rect, border=theme.NEON_GREEN)
        theme.neon_text(self.screen, self.f_item, t("flags_confirm"),
                        center=(w // 2, y + self.f_item.get_height() // 2),
                        color=theme.NEON_GREEN if sel else theme.DIM, glow=sel)
        self._footer(t("footer_flags"))

    def _submit_flags(self) -> None:
        ctx = self.flags_ctx
        flags = {k: bool(self.flag_answers.get(k)) for k in outcomes.FLAG_KEYS}
        outcomes.resolve_flags(ctx["system"], ctx["game_id"], flags)
        mv = escalate.next_move(ctx["system"], ctx["emulator"], ctx["tier"],
                                ctx["settings"], flags, core=ctx.get("core", ""))
        _dbg(f"   FLAGS: {flags} -> mossa={mv['kind']}")
        if mv["kind"] == "good":
            # chiude il cerchio: SudoBat scrive DA SOLO in catalogo l'esperienza buona.
            try:
                catalog.record_validated(ctx["system"], ctx["game_id"], ctx["game_title"],
                                         ctx["tier"], ctx["settings"], flags)
                _dbg(f"   CATALOGO: {ctx['game_id']} validato per fascia {ctx['tier']}")
                self._load_diagnose(resolve_outcome=False)  # rilegge col validato in catalogo
                self._flash([t("flash_good_title"),
                             ctx["game_title"],
                             t("flash_saved_catalog", tier=ctx["tier"]),
                             t("flash_next_time")], "diagnose")
            except Exception as e:
                self._load_diagnose(resolve_outcome=False)
                self._flash(["catalog write failed:", str(e)], "diagnose")
            return
        self._load_diagnose(resolve_outcome=False)  # ricarica set (esito gia' risolto)
        if mv["kind"] == "lighter":
            s = mv["set"]
            self._flash([t("flash_lighter_intro", why=t(mv["why_key"])),
                         t("flash_lighter_propose"),
                         s["desc"],
                         t("flash_apply_here")], "diagnose")
        else:  # manual_emulator
            reason = t(mv["reason_key"])
            self.manual_notes = [{"problem": reason, "why_manual": t("manual_why"),
                                  "steps": t("manual_steps"), "recommended": ""}] + list(self.manual_notes)
            self._flash([reason,
                         t("manual_notenough"),
                         t("manual_change_emu")], "diagnose")

    def _draw_manual_advice(self, mf: dict, x: int, y: int, width: int) -> int:
        """Riquadro ambra: cosa non puo' fare SudoBat, PERCHE', e cosa deve fare
        l'utente. Chiaro anche per l'utente medio. Ritorna la y sotto il riquadro."""
        inner = width - 28
        rendered = [(self.f_small, t("manual_header"), theme.NEON_AMBER)]
        blocks = [
            (t("manual_lbl_problem"), mf.get("problem", ""), theme.WHITE),
            (t("manual_lbl_why"), mf.get("why_manual", ""), theme.DIM),
            (t("manual_lbl_do"), mf.get("steps", ""), theme.NEON_GREEN),
        ]
        for label, text, col in blocks:
            for ln in theme.wrap_text(self.f_tiny, f"{label}: {text}", inner):
                rendered.append((self.f_tiny, ln, col))
        total_h = sum(f.get_height() + 4 for f, _, _ in rendered) + 14
        panel = pygame.Rect(x - 10, y - 6, width, total_h)
        theme.draw_panel(self.screen, panel, border=theme.NEON_AMBER)
        yy = y + 3
        for f, text, col in rendered:
            self.screen.blit(f.render(text, True, col), (x + 6, yy))
            yy += f.get_height() + 4
        return yy + 8

    # ---------------------------------------------------------------- brain
    def _ask_brain(self) -> None:
        """Avvia l'interrogazione del turbo Groq in un thread separato, cosi' la UI
        resta reattiva (mostra 'Interrogo...' invece di freezare)."""
        self.brain_loading = True
        self.brain_sug = None
        self.brain_candidate = None
        self.brain_reason = ""
        self.state = "brain"
        threading.Thread(target=self._brain_worker, daemon=True).start()

    def _brain_worker(self) -> None:
        try:
            from .. import brain, distill, logscan
            launch = self.diag.get("launch", {})
            system = launch.get("system", "")
            emulator = launch.get("emulator", "")
            log_path = logscan.emulator_log_path(emulator)
            tail = ""
            if log_path:
                try:
                    tail = "\n".join(Path(log_path).read_text(errors="replace").splitlines()[-40:])
                except OSError:
                    tail = ""
            prof = hardware.profile()
            ctx = {
                "hardware": {"gpu": prof.gpu_name, "tier": prof.tier},
                "system": system, "emulator": emulator,
                "game": (self.diag.get("game") or {}).get("title") or self.diag.get("game_id"),
                "symptom": f"crash sospetto dopo {self.diag.get('duration_seconds')}s",
                "crash_log_tail": tail,
            }
            sug = brain.ask_about_crash(ctx, system, emulator)
            self.brain_sug = sug
            if sug:
                cand, reason = distill.build_candidate(sug, tail, emulator)
                self.brain_candidate = cand
                self.brain_reason = reason
        except Exception as e:  # la UI non deve mai crashare per il turbo
            self.brain_reason = f"errore: {e}"
        finally:
            self.brain_loading = False

    def on_brain(self, action: str) -> None:
        if self.brain_loading:
            return
        if action == controls.BACK:
            self.enter("diagnose")
        elif action == controls.CONFIRM and self.brain_candidate:
            self._do_learn()

    def _do_learn(self) -> None:
        from .. import distill
        launch = self.diag.get("launch", {})
        diag_key = distill.diag_key_for(launch.get("emulator", ""))
        rule = self.brain_candidate
        try:
            for r in catalog.load_diagnostics(diag_key).get("rules", []):
                if r.get("match_log_pattern") == rule["match_log_pattern"]:
                    self._flash([t("learn_present"), t("learn_present2")], "diagnose")
                    return
            distill.append_rule(diag_key, rule)
        except Exception as e:
            self._flash([t("learn_error"), str(e)], "diagnose")
            return
        self._flash([t("learn_done"), t("learn_done2"), t("learn_done3")], "diagnose")

    def draw_brain(self) -> None:
        w, h = self.screen.get_size()
        theme.draw_background(self.screen)
        self._title_bar(t("brain_title"))
        x = int(w * 0.06)
        y = int(h * 0.22)
        w2 = int(w * 0.88)
        line_h = self.f_small.get_height() + 6

        if self.brain_loading:
            dots = "." * (1 + (pygame.time.get_ticks() // 400) % 3)
            theme.neon_text(self.screen, self.f_item, t("brain_querying") + dots,
                            topleft=(x, y), color=theme.NEON_CYAN, glow=False)
            theme.neon_text(self.screen, self.f_tiny, t("brain_querying_sub"),
                            topleft=(x, y + line_h + 6), color=theme.DIM, glow=False)
            self._footer(t("brain_wait"))
            return

        sug = self.brain_sug
        if not sug:
            theme.neon_text(self.screen, self.f_item, t("brain_noresp"),
                            topleft=(x, y), color=theme.NEON_AMBER, glow=False)
            theme.neon_text(self.screen, self.f_small, t("brain_offline_valid"),
                            topleft=(x, y + line_h + 6), color=theme.DIM, glow=False)
            self._footer(t("footer_back"))
            return

        theme.neon_text(self.screen, self.f_tiny,
                        f"{t('brain_lowconf')} · {sug.get('source', '')} · conf {sug.get('confidence')}",
                        topleft=(x, y), color=theme.DIM, glow=False)
        y += self.f_tiny.get_height() + 8
        blocks = [
            (t("brain_lbl_cause"), sug.get("cause", ""), theme.WHITE),
            (t("brain_lbl_expl"), sug.get("explanation", ""), theme.DIM),
        ]
        if sug.get("recommend_emulator"):
            blocks.append((t("brain_lbl_recemu"), sug["recommend_emulator"], theme.NEON_AMBER))
        if sug.get("settings"):
            blocks.append((t("brain_lbl_settings"), str(sug["settings"]), theme.NEON_GREEN))
        elif sug.get("rejected_keys"):
            blocks.append((t("brain_lbl_rejected"), ", ".join(sug["rejected_keys"]), theme.DANGER))
        for label, text, col in blocks:
            for j, ln in enumerate(theme.wrap_text(self.f_small, f"{label}: {text}", w2)):
                self.screen.blit(self.f_small.render(ln, True, col if j == 0 else theme.DIM), (x, y))
                y += line_h
            y += 4

        y += 6
        if self.brain_candidate:
            theme.neon_text(self.screen, self.f_small, t("brain_learn"),
                            topleft=(x, y), color=theme.NEON_GREEN, glow=False)
            self._footer(t("footer_brain_learn"))
        else:
            theme.neon_text(self.screen, self.f_small,
                            theme.fit_text(self.f_small, t("brain_notlearnable", reason=self.brain_reason), w2),
                            topleft=(x, y), color=theme.DIM, glow=False)
            self._footer(t("footer_back"))

    # ------------------------------------------------------------- hardware
    def on_hardware(self, action: str) -> None:
        if action == controls.BACK:
            self.enter("main")

    def draw_hardware(self) -> None:
        w, h = self.screen.get_size()
        theme.draw_background(self.screen)
        self._title_bar(t("hw_title"))
        x = int(w * 0.10)
        y = int(h * 0.28)
        line_h = self.f_item.get_height() + 10
        if self.hw is None:
            theme.neon_text(self.screen, self.f_item, t("hw_unavailable"),
                            topleft=(x, y), color=theme.NEON_AMBER, glow=False)
            self._footer(t("footer_back"))
            return
        rows = [
            ("CPU", f"{self.hw.cpu_model}  ({self.hw.cpu_cores} core)"),
            ("RAM", f"{self.hw.ram_mb} MB"),
            ("GPU", self.hw.gpu_name),
            (t("hw_gpu_dedicated"), t("hw_yes") if self.hw.has_discrete_gpu else t("hw_no_integrated")),
            (t("hw_tier"), self.hw.tier),
        ]
        for label, val in rows:
            theme.neon_text(self.screen, self.f_item, f"{label}",
                            topleft=(x, y), color=theme.NEON_TEAL, glow=False)
            self.screen.blit(self.f_item.render(
                theme.fit_text(self.f_item, str(val), int(w * 0.55)), True, theme.WHITE),
                (int(w * 0.36), y))
            y += line_h
        self._footer(t("footer_back"))

    # -------------------------------------------------------------- catalog
    def on_catalog_sys(self, action: str) -> None:
        if action == controls.BACK:
            self.enter("main")
        elif not self.systems:
            return
        elif action in (controls.UP, controls.DOWN):
            self.move(len(self.systems), action)
        elif action == controls.CONFIRM:
            self._load_games(self.systems[self.menu_index][0])
            self.menu_index = 0
            self.state = "catalog_games"

    def draw_catalog_sys(self) -> None:
        w, h = self.screen.get_size()
        theme.draw_background(self.screen)
        self._title_bar(t("cat_choose_system"))
        if not self.systems:
            theme.neon_text(self.screen, self.f_item, t("cat_empty"),
                            topleft=(int(w * 0.10), int(h * 0.30)), color=theme.DIM, glow=False)
            self._footer(t("footer_back"))
            return
        labels = []
        for sid, name in self.systems:
            n = len((catalog.load_system_catalog(sid).get("games") or {}))
            labels.append(f"{name}  ({t('cat_games_count', n=n)})")
        self._draw_menu(labels, self.menu_index, top=int(h * 0.26))
        self._footer(t("footer_cat_open"))

    def on_catalog_games(self, action: str) -> None:
        if action == controls.BACK:
            self.state = "catalog_sys"
            self.menu_index = 0
        elif action in (controls.UP, controls.DOWN):
            self.move(max(1, len(self.games)), action)

    def draw_catalog_games(self) -> None:
        w, h = self.screen.get_size()
        theme.draw_background(self.screen)
        sys_name = dict(self.systems).get(self.cur_system, self.cur_system)
        self._title_bar(t("cat_title", sys=sys_name))
        if not self.games:
            theme.neon_text(self.screen, self.f_item, t("cat_empty"),
                            topleft=(int(w * 0.10), int(h * 0.30)), color=theme.DIM, glow=False)
            self._footer(t("footer_back"))
            return
        # lista a sinistra, dettaglio a destra
        list_x = int(w * 0.06)
        list_w = int(w * 0.44)
        top = int(h * 0.24)
        line_h = self.f_small.get_height() + 8
        visible = max(1, (int(h * 0.66)) // line_h)
        start = max(0, min(self.menu_index - visible // 2, max(0, len(self.games) - visible)))
        for row, (gid, info) in enumerate(self.games[start:start + visible]):
            i = start + row
            y = top + row * line_h
            sel = (i == self.menu_index)
            rect = pygame.Rect(list_x - 6, y - 3, list_w, line_h)
            if sel:
                theme.draw_panel(self.screen, rect, border=theme.NEON_GREEN)
            title = info.get("title") or gid
            self.screen.blit(self.f_small.render(theme.fit_text(self.f_small, title, list_w - 16),
                             True, theme.WHITE if sel else theme.DIM), (list_x + 4, y))
        # dettaglio del gioco selezionato
        gid, info = self.games[self.menu_index]
        self._draw_game_detail(gid, info, int(w * 0.53), top, int(w * 0.41))
        self._footer(t("footer_scroll"))

    def _draw_game_detail(self, gid: str, info: dict, x: int, y: int, width: int) -> None:
        line_h = self.f_small.get_height() + 6
        theme.neon_text(self.screen, self.f_item, theme.fit_text(self.f_item, info.get("title") or gid, width),
                        topleft=(x, y), color=theme.NEON_CYAN, glow=False)
        y += self.f_item.get_height() + 8
        rows = [("ID", gid), (t("cat_heaviness"), info.get("heaviness", "?"))]
        tier = self.hw.tier if self.hw else None
        if tier and (info.get("presets") or {}).get(tier):
            preset = ", ".join(f"{k}={v}" for k, v in info["presets"][tier].items())
            rows.append((t("cat_preset", tier=tier), preset))
        for label, val in rows:
            for j, ln in enumerate(theme.wrap_text(self.f_small, f"{label}: {val}", width)):
                self.screen.blit(self.f_small.render(ln, True, theme.WHITE if j == 0 else theme.DIM), (x, y))
                y += line_h
        issues = info.get("known_issues") or []
        if issues:
            y += line_h // 2
            theme.neon_text(self.screen, self.f_small, t("cat_known_issues"), topleft=(x, y),
                            color=theme.NEON_AMBER, glow=False)
            y += line_h
            for iss in issues:
                for ln in theme.wrap_text(self.f_tiny, f"• {iss.get('symptom','')}", width):
                    self.screen.blit(self.f_tiny.render(ln, True, theme.DIM), (x, y))
                    y += self.f_tiny.get_height() + 3

    # -------------------------------------------------------------- settings
    def on_settings(self, action: str) -> None:
        # righe attive: 0 = Lingua (A/Sx/Dx cambia), 1 = Ripristina ultimo backup
        # (A apre la conferma). Le altre righe sono solo informative.
        if action == controls.BACK:
            self.enter("main")
            return
        if action in (controls.UP, controls.DOWN):
            self.move(2, action)
            return
        if self.menu_index == 0 and action in (controls.CONFIRM, controls.LEFT, controls.RIGHT):
            i18n.toggle()
            self._fonts()  # nel caso cambi metrica testo
        elif self.menu_index == 1 and action == controls.CONFIRM:
            self._ask_restore()

    def _ask_restore(self) -> None:
        """"Annulla ultima modifica" a portata di gamepad: propone il ripristino di
        batocera.conf dall'ultimo backup, dietro la solita conferma esplicita."""
        latest = config.latest_backup()
        if latest is None:
            self._flash([t("restore_none")], "settings")
            return
        lines = [t("restore_q"), latest.name, "", t("restore_note")]
        self._ask(lines, self._do_restore, "settings")

    def _do_restore(self) -> None:
        try:
            res = config.restore_latest_backup(dry_run=False)
        except Exception as e:
            self._flash([t("restore_error"), str(e)], "settings")
            return
        if not res.get("restored"):
            self._flash([t("restore_none")], "settings")
            return
        _dbg(f"   RESTORE: batocera.conf <- {res['restored_from']}")
        self._flash([t("restore_done"),
                     Path(res["restored_from"]).name,
                     t("restore_undo_hint")], "settings")

    def draw_settings(self) -> None:
        w, h = self.screen.get_size()
        theme.draw_background(self.screen)
        self._title_bar(t("settings_title"))
        hook_installed = Path("/userdata/system/scripts/sudobat-hook.sh").exists()
        latest = config.latest_backup()
        # stato del turbo AI: ognuno usa la PROPRIA chiave Groq (limiti personali);
        # qui si vede se e' configurata, l'inserimento si fa da CLI/file (guida in docs/)
        try:
            from .. import brain
            ks = brain.key_status()
            turbo_val = t("turbo_on", tail=ks["masked"]) if ks["configured"] else t("turbo_off")
        except Exception:
            turbo_val = "?"
        # terzo campo: indice della riga ATTIVA (None = riga solo informativa)
        rows = [
            (t("set_language"), i18n.t("lang_name"), 0),
            (t("set_restore"), latest.name if latest else t("set_nobackup"), 1),
            (t("set_turbo"), turbo_val, None),
            (t("set_hook"), t("set_installed") if hook_installed else t("set_notinstalled"), None),
            (t("set_conf"), str(config.BATOCERA_CONF_PATH), None),
            (t("set_saves"), str(paths.saves_dir()), None),
            (t("set_controller"), self.inp.joystick_name() or t("set_keyboard"), None),
        ]
        x = int(w * 0.10)
        y = int(h * 0.28)
        line_h = self.f_small.get_height() + 14
        for label, val, active_idx in rows:
            active = active_idx is not None
            sel = active and active_idx == self.menu_index
            if sel:
                rect = pygame.Rect(int(w * 0.07), y - 4, int(w * 0.86), line_h - 6)
                theme.draw_panel(self.screen, rect, border=theme.NEON_GREEN)
            theme.neon_text(self.screen, self.f_small, f"{label}", topleft=(x, y),
                            color=theme.NEON_GREEN if sel else theme.NEON_TEAL, glow=False)
            self.screen.blit(self.f_small.render(
                theme.fit_text(self.f_small, str(val), int(w * 0.55)), True,
                theme.WHITE if active else theme.DIM),
                (int(w * 0.36), y))
            y += line_h
        self._footer(t("footer_settings"))

    # -------------------------------------------------------------- confirm
    def _ask(self, lines: list[str], action_callable, back_state: str) -> None:
        self.confirm_lines = lines
        self.pending_action = action_callable
        self.pending_back = back_state
        self.confirm_index = 1  # default "Annulla"
        self.state = "confirm"

    def on_confirm(self, action: str) -> None:
        if action in (controls.LEFT, controls.RIGHT, controls.UP, controls.DOWN):
            self.confirm_index = 1 - self.confirm_index
        elif action == controls.BACK:
            self.state = self.pending_back
        elif action == controls.CONFIRM:
            if self.confirm_index == 0 and self.pending_action:
                self.pending_action()
            else:
                self.state = self.pending_back

    def draw_confirm(self) -> None:
        w, h = self.screen.get_size()
        theme.draw_background(self.screen)
        panel = pygame.Rect(int(w * 0.15), int(h * 0.22), int(w * 0.70), int(h * 0.56))
        theme.draw_panel(self.screen, panel, border=theme.NEON_AMBER)
        y = panel.top + 24
        for ln in self.confirm_lines:
            color = theme.WHITE if ln else theme.DIM
            self.screen.blit(self.f_small.render(theme.fit_text(self.f_small, ln, panel.width - 40),
                             True, color), (panel.left + 24, y))
            y += self.f_small.get_height() + 6
        # bottoni
        opts = [t("confirm_apply"), t("confirm_cancel")]
        by = panel.bottom - 54
        for i, opt in enumerate(opts):
            bx = panel.left + 60 + i * int(panel.width * 0.45)
            rect = pygame.Rect(bx, by, int(panel.width * 0.32), 40)
            sel = (i == self.confirm_index)
            border = theme.NEON_GREEN if (i == 0) else theme.DANGER
            if sel:
                theme.draw_panel(self.screen, rect, border=border)
            theme.neon_text(self.screen, self.f_small, opt, center=rect.center,
                            color=border if sel else theme.DIM, glow=False)
        self._footer(t("footer_confirm"))

    # -------------------------------------------------------------- message
    def _flash(self, lines: list[str], next_state: str) -> None:
        self.msg_lines = lines
        self.msg_next = next_state
        self.state = "message"

    def on_message(self, action: str) -> None:
        if action in (controls.CONFIRM, controls.BACK, controls.SELECT):
            self.state = self.msg_next
            self.menu_index = 0

    def draw_message(self) -> None:
        w, h = self.screen.get_size()
        theme.draw_background(self.screen)
        panel = pygame.Rect(int(w * 0.18), int(h * 0.32), int(w * 0.64), int(h * 0.36))
        theme.draw_panel(self.screen, panel, border=theme.NEON_GREEN)
        y = panel.top + 30
        for ln in self.msg_lines:
            theme.neon_text(self.screen, self.f_small, theme.fit_text(self.f_small, ln, panel.width - 40),
                            center=(panel.centerx, y), color=theme.WHITE, glow=False)
            y += self.f_small.get_height() + 10
        theme.neon_text(self.screen, self.f_tiny, t("press_key"),
                        center=(panel.centerx, panel.bottom - 26), color=theme.NEON_GREEN, glow=False)

    # -------------------------------------------------------------- helpers
    def _title_bar(self, title: str) -> None:
        w, _ = self.screen.get_size()
        theme.neon_text(self.screen, self.f_title, title, topleft=(int(w * 0.06), int(w * 0.02)),
                        color=theme.NEON_GREEN)

    def _footer(self, hint: str) -> None:
        w, h = self.screen.get_size()
        theme.neon_text(self.screen, self.f_tiny, hint,
                        center=(w // 2, int(h * 0.955)), color=theme.NEON_CYAN, glow=False)

    def _draw_menu(self, labels: list[str], index: int, top: int) -> None:
        w, _ = self.screen.get_size()
        line_h = self.f_item.get_height() + 22
        for i, label in enumerate(labels):
            y = top + i * line_h
            sel = (i == index)
            rect = pygame.Rect(int(w * 0.22), y - 6, int(w * 0.56), line_h - 8)
            if sel:
                theme.draw_panel(self.screen, rect, border=theme.NEON_GREEN)
            theme.neon_text(self.screen, self.f_item, label, center=(w // 2, y + (line_h - 8) // 2 - 6),
                            color=theme.NEON_GREEN if sel else theme.DIM, glow=sel)

    def draw(self) -> None:
        drawer = getattr(self, f"draw_{self.state}", None)
        if drawer:
            drawer()
        if self.has_display:
            pygame.display.flip()


def run() -> None:
    App().run()
