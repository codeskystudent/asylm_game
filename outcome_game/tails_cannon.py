"""Tails hand cannon: charge, beam, +1s killer stun per full second in beam."""

from __future__ import annotations

import math

from outcome_game.constants import (
    TAILS_CANNON_BEAM_HALF_WIDTH,
    TAILS_CANNON_BEAM_LENGTH,
    TAILS_CANNON_BEAM_SECONDS,
    TAILS_CANNON_CHARGE_SECONDS,
)
from outcome_game.entities import Combatant
from outcome_game.x2011_rage import extend_executioner_stun


def _is_tails(c: Combatant) -> bool:
    return c.char_id == "Tails"


def _killer_in_beam(tails: Combatant, killer: Combatant) -> bool:
    fx = tails.tails_cannon_beam_dx
    fy = tails.tails_cannon_beam_dy
    dx = killer.x - tails.x
    dy = killer.y - tails.y
    t_along = dx * fx + dy * fy
    if t_along < -killer.radius or t_along > TAILS_CANNON_BEAM_LENGTH + killer.radius:
        return False
    perp = abs(dx * (-fy) + dy * fx)
    return perp <= TAILS_CANNON_BEAM_HALF_WIDTH + killer.radius


def try_start_hand_cannon(tails: Combatant, now: float) -> bool:
    if not _is_tails(tails) or not tails.alive() or tails.escaped:
        return False
    if tails.tails_cannon_phase != "none":
        return False
    tails.tails_cannon_phase = "charging"
    tails.tails_cannon_end = now + TAILS_CANNON_CHARGE_SECONDS
    return True


def tick_tails_hand_cannon(
    combatants: list[Combatant],
    killer: Combatant,
    now: float,
    dt: float,
) -> None:
    for c in combatants:
        if not _is_tails(c) or not c.alive() or c.escaped:
            continue

        if c.tails_cannon_phase == "charging" and now >= c.tails_cannon_end:
            c.tails_cannon_phase = "beaming"
            c.tails_cannon_end = now + TAILS_CANNON_BEAM_SECONDS
            c.tails_cannon_contact_bank = 0.0
            if killer.alive() and not killer.escaped:
                dx = killer.x - c.x
                dy = killer.y - c.y
                dist = math.hypot(dx, dy) or 1.0
                c.tails_cannon_beam_dx = dx / dist
                c.tails_cannon_beam_dy = dy / dist
            else:
                c.tails_cannon_beam_dx = c.facing_x
                c.tails_cannon_beam_dy = c.facing_y
            d = math.hypot(c.tails_cannon_beam_dx, c.tails_cannon_beam_dy) or 1.0
            c.tails_cannon_beam_dx /= d
            c.tails_cannon_beam_dy /= d

        elif c.tails_cannon_phase == "beaming" and now >= c.tails_cannon_end:
            c.tails_cannon_phase = "none"
            c.tails_cannon_contact_bank = 0.0
            continue

        if c.tails_cannon_phase != "beaming":
            continue
        if not killer.alive() or killer.escaped:
            continue
        if not _killer_in_beam(c, killer):
            continue
        c.tails_cannon_contact_bank += dt
        while c.tails_cannon_contact_bank >= 1.0:
            c.tails_cannon_contact_bank -= 1.0
            extend_executioner_stun(killer, now, 1.0, combatants)
