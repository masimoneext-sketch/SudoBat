"""Input astratto: tastiera + controller.

Il resto della UI non sa nulla di tasti fisici: chiede solo azioni astratte
(UP, DOWN, LEFT, RIGHT, CONFIRM, BACK, SELECT, QUIT). Il mapping del joystick si
salva in /userdata/saves/ports/sudobat/controls.json.
"""
from __future__ import annotations

import json

import pygame

from . import paths

UP, DOWN, LEFT, RIGHT = "up", "down", "left", "right"
CONFIRM, BACK, SELECT, QUIT = "confirm", "back", "select", "quit"

# Tastiera: mappa fissa, sempre disponibile come rete di sicurezza.
_KEYS = {
    pygame.K_UP: UP, pygame.K_DOWN: DOWN, pygame.K_LEFT: LEFT, pygame.K_RIGHT: RIGHT,
    pygame.K_w: UP, pygame.K_s: DOWN, pygame.K_a: LEFT, pygame.K_d: RIGHT,
    pygame.K_RETURN: CONFIRM, pygame.K_KP_ENTER: CONFIRM,
    pygame.K_ESCAPE: BACK, pygame.K_BACKSPACE: BACK,
    pygame.K_SPACE: SELECT,
}

_AXIS_THRESHOLD = 0.6


class InputManager:
    def __init__(self) -> None:
        self.joy: pygame.joystick.Joystick | None = None
        self.mapping = {"confirm": 0, "back": 1, "select": 2}  # default tipo Xbox
        self._axis_state = {0: 0, 1: 0}
        self._init_joystick()
        self._load_mapping()

    def _init_joystick(self) -> None:
        try:
            pygame.joystick.init()
            if pygame.joystick.get_count() > 0:
                self.joy = pygame.joystick.Joystick(0)
                self.joy.init()
        except pygame.error:
            self.joy = None

    def has_joystick(self) -> bool:
        return self.joy is not None

    def joystick_name(self) -> str:
        return self.joy.get_name() if self.joy else ""

    def mapping_exists(self) -> bool:
        return paths.controls_path().is_file()

    def _load_mapping(self) -> None:
        p = paths.controls_path()
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                self.mapping.update(data.get("buttons", {}))
            except (ValueError, OSError):
                pass

    def save_mapping(self) -> None:
        paths.controls_path().write_text(
            json.dumps({"name": self.joystick_name(), "buttons": self.mapping},
                       indent=2, ensure_ascii=False), encoding="utf-8")

    def translate(self, event: pygame.event.Event) -> str | None:
        if event.type == pygame.QUIT:
            return QUIT
        if event.type == pygame.KEYDOWN:
            return _KEYS.get(event.key)
        if event.type == pygame.JOYBUTTONDOWN:
            for action, btn in self.mapping.items():
                if event.button == btn:
                    return action
            return None
        if event.type == pygame.JOYHATMOTION:
            x, y = event.value
            if y == 1:
                return UP
            if y == -1:
                return DOWN
            if x == -1:
                return LEFT
            if x == 1:
                return RIGHT
            return None
        if event.type == pygame.JOYAXISMOTION and event.axis in (0, 1):
            v = event.value
            direction = 0
            if v <= -_AXIS_THRESHOLD:
                direction = -1
            elif v >= _AXIS_THRESHOLD:
                direction = 1
            if direction == self._axis_state[event.axis]:
                return None
            self._axis_state[event.axis] = direction
            if direction == 0:
                return None
            if event.axis == 1:
                return UP if direction < 0 else DOWN
            return LEFT if direction < 0 else RIGHT
        return None
