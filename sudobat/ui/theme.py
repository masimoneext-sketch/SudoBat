"""Tema grafico di SudoBat: palette neon synthwave, font, sfondo e logo.

Stile coerente con l'ecosistema (RGSX/RomsOrganizer) ma identita' propria: accento
verde "terminale/sudo" + ciano, secondario magenta. Lo sfondo e' disegnato in modo
PROCEDURALE (griglia in prospettiva + scanline) e messo in cache: scala a qualsiasi
risoluzione dello schermo Batocera e non dipende da file binari. Il logo prova a
caricare assets/logo.png, con fallback vettoriale se manca.
"""
from __future__ import annotations

from pathlib import Path

import pygame

_ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
_logo_img: pygame.Surface | None = None
_logo_loaded = False

# Palette neon synthwave (base NERA).
BG = (7, 10, 12)
BG_GLOW = (10, 34, 28)
NEON_GREEN = (57, 255, 120)
NEON_TEAL = (29, 233, 182)
NEON_CYAN = (0, 229, 255)
NEON_PINK = (255, 43, 214)
NEON_AMBER = (255, 190, 60)
WHITE = (235, 240, 240)
DIM = (120, 140, 140)
SELECT_BG = (14, 60, 48)
PANEL_FILL = (10, 20, 20)
DANGER = (255, 96, 96)


def make_font(size: int, bold: bool = True) -> pygame.font.Font:
    """Font monospace (vibe terminale); fallback al default di pygame."""
    try:
        return pygame.font.SysFont("couriernew,dejavusansmono,monospace", size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)


_bg_cache: pygame.Surface | None = None


def draw_background(surf: pygame.Surface) -> None:
    """Sfondo neon in cache: ogni frame e' solo un blit."""
    global _bg_cache
    w, h = surf.get_size()
    if _bg_cache is None or _bg_cache.get_size() != (w, h):
        _bg_cache = _build_background(w, h)
    surf.blit(_bg_cache, (0, 0))


def _build_background(w: int, h: int) -> pygame.Surface:
    bg = pygame.Surface((w, h))
    bg.fill(BG)

    glow = pygame.Surface((w, h), pygame.SRCALPHA)
    cx, cy = w // 2, int(h * 0.16)
    for r in range(int(h * 0.5), 0, -8):
        a = max(0, 26 - r * 26 // int(h * 0.5))
        pygame.draw.circle(glow, (*BG_GLOW, a), (cx, cy), r)
    bg.blit(glow, (0, 0))

    grid = pygame.Surface((w, h), pygame.SRCALPHA)
    horizon = int(h * 0.58)
    vp = (w // 2, horizon)
    for i in range(-12, 13):
        x_bottom = w // 2 + i * (w // 12)
        pygame.draw.line(grid, (*NEON_GREEN, 40), (x_bottom, h), vp, 1)
    t = 0.0
    while t < 1.0:
        y = horizon + int((h - horizon) * (t * t))
        a = int(24 + 60 * t)
        pygame.draw.line(grid, (*NEON_CYAN, a), (0, y), (w, y), 1)
        t += 0.06
    pygame.draw.line(grid, (*NEON_TEAL, 110), (0, horizon), (w, horizon), 2)
    bg.blit(grid, (0, 0))

    scan = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(0, h, 3):
        pygame.draw.line(scan, (0, 0, 0, 40), (0, y), (w, y))
    bg.blit(scan, (0, 0))
    return bg


def fit_text(font: pygame.font.Font, text: str, max_w: int) -> str:
    """Tronca con '...' se il testo supera max_w pixel."""
    if font.size(text)[0] <= max_w:
        return text
    ell = "..."
    s = text
    while s and font.size(s + ell)[0] > max_w:
        s = s[:-1]
    return (s + ell) if s else ell


def wrap_text(font: pygame.font.Font, text: str, max_w: int) -> list[str]:
    """Manda a capo il testo su piu' righe entro max_w pixel."""
    words = text.split()
    lines: list[str] = []
    cur = ""
    for wd in words:
        trial = f"{cur} {wd}".strip()
        if font.size(trial)[0] <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def draw_panel(surf: pygame.Surface, rect, border=NEON_TEAL) -> None:
    """Pannello scuro semi-trasparente con bordo neon arrotondato."""
    rect = pygame.Rect(rect)
    fill = pygame.Surface(rect.size, pygame.SRCALPHA)
    fill.fill((*PANEL_FILL, 210))
    surf.blit(fill, rect.topleft)
    pygame.draw.rect(surf, border, rect, 2, border_radius=10)


def neon_text(surf: pygame.Surface, font: pygame.font.Font, text: str,
              center=None, topleft=None, color=NEON_GREEN, glow=True):
    """Testo con alone neon."""
    if glow:
        halo = font.render(text, True, tuple(c // 3 for c in color))
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            r = halo.get_rect()
            if center:
                r.center = (center[0] + dx, center[1] + dy)
            else:
                r.topleft = (topleft[0] + dx, topleft[1] + dy)
            surf.blit(halo, r)
    img = font.render(text, True, color)
    r = img.get_rect()
    if center:
        r.center = center
    else:
        r.topleft = topleft
    surf.blit(img, r)
    return r


def _load_logo() -> pygame.Surface | None:
    global _logo_img, _logo_loaded
    if _logo_loaded:
        return _logo_img
    _logo_loaded = True
    png = _ASSETS / "logo.png"
    if png.is_file():
        try:
            _logo_img = pygame.image.load(str(png)).convert_alpha()
        except pygame.error:
            _logo_img = None
    return _logo_img


def draw_logo(surf: pygame.Surface, cx: int, cy: int, scale: float = 1.0) -> None:
    """Logo ufficiale (PNG) incorniciato come un monitor neon; fallback vettoriale."""
    img = _load_logo()
    if img is not None:
        target_w = int(300 * scale)
        ratio = img.get_height() / img.get_width()
        scaled = pygame.transform.smoothscale(img, (target_w, int(target_w * ratio)))
        rect = scaled.get_rect(center=(cx, cy))
        frame = rect.inflate(int(14 * scale), int(14 * scale))
        pygame.draw.rect(surf, (5, 8, 8), frame, 0, border_radius=int(16 * scale))
        surf.blit(scaled, rect)
        pygame.draw.rect(surf, NEON_TEAL, frame, max(2, int(3 * scale)),
                         border_radius=int(16 * scale))
        pygame.draw.rect(surf, NEON_CYAN, frame, 1, border_radius=int(16 * scale))
        return
    _draw_logo_vector(surf, cx, cy, scale)


def _draw_logo_vector(surf: pygame.Surface, cx: int, cy: int, scale: float = 1.0) -> None:
    """Fallback: prompt da terminale 'sudo' neon disegnato a runtime."""
    w = int(300 * scale)
    h = int(140 * scale)
    x = cx - w // 2
    y = cy - h // 2
    body = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surf, NEON_TEAL, body, max(2, int(3 * scale)), border_radius=int(12 * scale))
    pygame.draw.rect(surf, NEON_GREEN, pygame.Rect(x, y, w, int(22 * scale)),
                     0, border_radius=int(8 * scale))
    f1 = make_font(int(34 * scale))
    f2 = make_font(int(18 * scale))
    neon_text(surf, f1, "SudoBat", center=(cx, cy), color=NEON_GREEN)
    neon_text(surf, f2, "> auto-tuning", center=(cx, y + h - int(20 * scale)), color=NEON_CYAN)
