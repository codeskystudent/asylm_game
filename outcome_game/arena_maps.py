"""Arena layouts and color themes — one map is picked randomly each match."""

from __future__ import annotations

import random
from dataclasses import dataclass

import pygame


@dataclass(frozen=True)
class ArenaTheme:
    """Visual palette for floor, frame, walls, and exit labels."""

    bg_outside: tuple[int, int, int]
    floor_a: tuple[int, int, int]
    floor_b: tuple[int, int, int]
    border: tuple[int, int, int]
    border_accent: tuple[int, int, int]
    grid_line: tuple[int, int, int]
    wall_fill: tuple[int, int, int]
    wall_edge: tuple[int, int, int]
    wall_highlight: tuple[int, int, int]
    exit_locked_border: tuple[int, int, int]
    exit_locked_text: tuple[int, int, int]
    exit_open_border: tuple[int, int, int]
    exit_open_text: tuple[int, int, int]


@dataclass(frozen=True)
class ArenaMapDef:
    id: str
    display_name: str
    walls: tuple[pygame.Rect, ...]
    theme: ArenaTheme


def _r(x: float, y: float, w: float, h: float) -> pygame.Rect:
    return pygame.Rect(int(x), int(y), int(w), int(h))


# --- Layouts (coordinates match ARENA_W × ARENA_H) ---------------------------------------------

# Classic central corridors — scaled from the original 2700×1800 layout (× 4/3).
_HANGAR_WALLS: tuple[pygame.Rect, ...] = (
    _r(520, 880, 1360, 56),
    _r(2080, 880, 1000, 56),
    _r(520, 1440, 1360, 56),
    _r(2080, 1440, 1000, 56),
    _r(1760, 1000, 56, 440),
    _r(840, 1120, 56, 400),
    _r(2700, 1120, 56, 400),
)

# Corner brackets — open middle, fights funnel through gaps.
_SECTOR_WALLS: tuple[pygame.Rect, ...] = (
    _r(220, 220, 780, 52),
    _r(220, 220, 52, 780),
    _r(2600, 220, 780, 52),
    _r(3328, 220, 52, 780),
    _r(220, 2128, 780, 52),
    _r(220, 1550, 52, 780),
    _r(2600, 2128, 780, 52),
    _r(3328, 1550, 52, 780),
)

# Six pillars — strong sight-blockers, rotational symmetry.
_TWILIGHT_WALLS: tuple[pygame.Rect, ...] = tuple(
    _r(cx - 72, cy - 72, 144, 144)
    for cx, cy in (
        (920, 680),
        (1800, 680),
        (2680, 680),
        (920, 1200),
        (1800, 1200),
        (2680, 1200),
    )
)

# Staggered industrial spans — long diagonal-feeling lanes.
_RUSTWORKS_WALLS: tuple[pygame.Rect, ...] = (
    _r(380, 520, 2360, 54),
    _r(1240, 1020, 2360, 54),
    _r(380, 1520, 2360, 54),
    _r(880, 760, 54, 420),
    _r(2466, 1260, 54, 420),
    _r(1600, 320, 54, 380),
    _r(1946, 1700, 54, 380),
)


THEME_HANGAR = ArenaTheme(
    bg_outside=(10, 12, 18),
    floor_a=(22, 27, 36),
    floor_b=(28, 33, 42),
    border=(44, 54, 68),
    border_accent=(95, 155, 205),
    grid_line=(34, 40, 50),
    wall_fill=(46, 50, 60),
    wall_edge=(92, 98, 112),
    wall_highlight=(120, 128, 142),
    exit_locked_border=(120, 62, 62),
    exit_locked_text=(235, 190, 185),
    exit_open_border=(52, 165, 108),
    exit_open_text=(185, 245, 205),
)

THEME_SECTOR = ArenaTheme(
    bg_outside=(14, 10, 22),
    floor_a=(36, 28, 52),
    floor_b=(44, 34, 62),
    border=(72, 52, 108),
    border_accent=(190, 130, 255),
    grid_line=(52, 40, 72),
    wall_fill=(58, 46, 82),
    wall_edge=(130, 108, 168),
    wall_highlight=(160, 135, 205),
    exit_locked_border=(140, 70, 110),
    exit_locked_text=(245, 200, 225),
    exit_open_border=(70, 200, 160),
    exit_open_text=(200, 250, 235),
)

THEME_TWILIGHT = ArenaTheme(
    bg_outside=(8, 14, 24),
    floor_a=(18, 34, 48),
    floor_b=(24, 42, 58),
    border=(38, 72, 98),
    border_accent=(80, 190, 230),
    grid_line=(28, 48, 62),
    wall_fill=(36, 62, 82),
    wall_edge=(85, 130, 158),
    wall_highlight=(110, 165, 195),
    exit_locked_border=(100, 58, 72),
    exit_locked_text=(235, 205, 215),
    exit_open_border=(48, 150, 125),
    exit_open_text=(175, 245, 225),
)

THEME_RUSTWORKS = ArenaTheme(
    bg_outside=(18, 12, 8),
    floor_a=(42, 32, 24),
    floor_b=(50, 38, 28),
    border=(92, 62, 42),
    border_accent=(255, 170, 95),
    grid_line=(56, 42, 32),
    wall_fill=(72, 52, 38),
    wall_edge=(140, 105, 78),
    wall_highlight=(175, 130, 95),
    exit_locked_border=(130, 65, 48),
    exit_locked_text=(245, 200, 175),
    exit_open_border=(95, 155, 72),
    exit_open_text=(235, 245, 195),
)


MAPS: dict[str, ArenaMapDef] = {
    "hangar": ArenaMapDef(
        id="hangar",
        display_name="Hangar",
        walls=_HANGAR_WALLS,
        theme=THEME_HANGAR,
    ),
    "sector": ArenaMapDef(
        id="sector",
        display_name="Sector 7",
        walls=_SECTOR_WALLS,
        theme=THEME_SECTOR,
    ),
    "twilight": ArenaMapDef(
        id="twilight",
        display_name="Twilight Yard",
        walls=_TWILIGHT_WALLS,
        theme=THEME_TWILIGHT,
    ),
    "rustworks": ArenaMapDef(
        id="rustworks",
        display_name="Rustworks",
        walls=_RUSTWORKS_WALLS,
        theme=THEME_RUSTWORKS,
    ),
}

_MAP_ORDER: tuple[str, ...] = tuple(MAPS.keys())

_active: ArenaMapDef | None = None


def get_active_map() -> ArenaMapDef:
    return _active if _active is not None else MAPS["hangar"]


def get_active_theme() -> ArenaTheme:
    return get_active_map().theme


def get_active_map_display_name() -> str:
    return get_active_map().display_name


def activate_random_map() -> ArenaMapDef:
    """Pick a layout for the upcoming round and refresh pathfinding collision."""
    global _active
    mid = random.choice(_MAP_ORDER)
    _active = MAPS[mid]
    from outcome_game.arena_navigation import set_active_walls

    set_active_walls(list(_active.walls))
    return _active
