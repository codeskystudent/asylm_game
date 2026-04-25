"""Match phase, exit zone, win / loss, reset helpers."""

from __future__ import annotations

import random
from enum import Enum, auto

import pygame

from outcome_game.constants import ARENA_H, ARENA_W, ESCAPE_OPENS_AT_ROUND_FRACTION
from outcome_game.entities import Combatant


class Phase(Enum):
    LOBBY = auto()
    IN_ROUND = auto()
    ENDED = auto()


_exit_rects: list[pygame.Rect] = []


def reset_exit_rects() -> None:
    """Pick 2–3 exit gates (max 3) at match start — spread around the arena."""
    global _exit_rects
    candidates = [
        pygame.Rect(int(ARENA_W // 2 - 100), 22, 200, 128),  # top center
        pygame.Rect(22, int(ARENA_H // 2 - 90), 128, 180),  # left
        pygame.Rect(int(ARENA_W - 150), int(ARENA_H // 2 - 90), 128, 180),  # right
    ]
    n = random.randint(2, 3)
    _exit_rects = random.sample(candidates, n)


def get_exit_rects() -> list[pygame.Rect]:
    return list(_exit_rects)


def is_escape_window_open(now: float, round_start_unix: float, round_duration_initial: float) -> bool:
    """Exits unlock after ESCAPE_OPENS_AT_ROUND_FRACTION of the *initial* round (e.g. 75% → last 25%)."""
    d = max(round_duration_initial, 1e-6)
    return now >= round_start_unix + ESCAPE_OPENS_AT_ROUND_FRACTION * d


def exits_available_for_escape(
    now: float,
    round_start_unix: float,
    round_duration_initial: float,
    killer: Combatant,
    combatants: list[Combatant],
) -> bool:
    """
    Survivors can only use exits when the escape window is open and exits are not suppressed.
    While 2011X is in rage after exits have opened, exits vanish until rage ends (rage off in LMS).
    """
    from outcome_game.x2011_rage import rage_active

    if not is_escape_window_open(now, round_start_unix, round_duration_initial):
        return False
    if killer.char_id == "X2011" and rage_active(killer, now, combatants):
        return False
    return True


def update_exit_zone(
    combatants: list[Combatant],
    dt: float,
    now: float,
    round_start_unix: float,
    round_duration_initial: float,
    killer: Combatant,
) -> None:
    """Track time in exit rects only while escapes are available (open and not rage-sealed)."""
    escape_open = exits_available_for_escape(now, round_start_unix, round_duration_initial, killer, combatants)
    rects = _exit_rects
    for c in combatants:
        if c.team != "Survivors" or not c.alive() or c.escaped:
            continue
        if not escape_open:
            c.exit_zone_time = 0.0
            continue
        px, py = c.x, c.y
        inside = any(
            r.left <= px <= r.right and r.top <= py <= r.bottom for r in rects
        )
        if inside:
            c.exit_zone_time += dt
            if c.exit_zone_time >= 3.0:
                c.escaped = True
                c.exit_zone_time = 0.0
        else:
            c.exit_zone_time = 0.0


def check_winner(combatants: list[Combatant], round_end_unix: float, now: float) -> str | None:
    """
    Survivors win if every survivor is either escaped or downed, with at least one escape.

    Executioners win if every survivor is downed, or time runs out before all escape.
    """
    survivors = [c for c in combatants if c.team == "Survivors"]
    if not survivors:
        return None

    if any([s.escaped for s in survivors]) and all([s.escaped or s.dead for s in survivors]):
        return "Survivors"

    if all([s.dead for s in survivors]):
        return "Executioners"

    if now >= round_end_unix:
        return "Executioners"

    return None
