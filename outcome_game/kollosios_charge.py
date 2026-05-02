"""Kollosios: charge and grab multiple survivors; on end, damage or heal low-HP survivors."""

from __future__ import annotations

import math

from outcome_game.constants import (
    METAL_CHARGE_DAMAGE_REDUCTION_FLAT,
    KNUCKLES_PUNCH_CHARGE_DAMAGE_MULT,
    KOLLOSIOS_CHARGE_DAMAGE,
    KOLLOSIOS_CHARGE_LOW_HP_HEAL,
    KOLLOSIOS_CHARGE_LOW_HP_THRESHOLD,
    KOLLOSIOS_CHARGE_SECONDS,
)
from outcome_game.entities import Combatant, clamp_to_arena, heal_ceiling_for
from outcome_game.hit_reaction import apply_survivor_hit_speed_boost
from outcome_game.last_man_standing import last_man_incoming_damage_multiplier
from outcome_game.survivor_death_revive import resolve_survivor_zero_hp


def _flat_dist(a: Combatant, b: Combatant) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def try_start_kollosios_charge(killer: Combatant, now: float) -> bool:
    if killer.char_id != "Kollosios" or not killer.alive():
        return False
    if killer.kollosios_basic_grab_victim is not None:
        return False
    if killer.kollosios_charge_until > now:
        return False
    killer.kollosios_charge_until = now + KOLLOSIOS_CHARGE_SECONDS
    killer.kollosios_grabbed_survivors = []
    return True


def _collect_grabs(killer: Combatant, combatants: list[Combatant], now: float) -> None:
    for s in combatants:
        if s.team != "Survivors" or not s.alive() or s.escaped:
            continue
        if s.char_id == "Knuckles" and s.knuckles_block_until > now:
            continue
        if s.grabbed_by is not None:
            continue
        if s.held_by_kollosios_basic_grab:
            continue
        if s.held_by_kollosios_charge:
            continue
        touch = killer.radius + s.radius + 12.0
        if _flat_dist(killer, s) <= touch:
            s.held_by_kollosios_charge = True
            killer.kollosios_grabbed_survivors.append(s)


def _release_all(
    killer: Combatant,
    now: float,
    combatants: list[Combatant],
) -> None:
    grabbed = list(killer.kollosios_grabbed_survivors)
    for s in grabbed:
        s.held_by_kollosios_charge = False
        if not s.alive():
            continue
        if s.health < KOLLOSIOS_CHARGE_LOW_HP_THRESHOLD:
            cap = heal_ceiling_for(s)
            if s.health < cap:
                s.health = min(cap, s.health + KOLLOSIOS_CHARGE_LOW_HP_HEAL)
        else:
            dmg = KOLLOSIOS_CHARGE_DAMAGE * last_man_incoming_damage_multiplier(s, combatants)
            if s.char_id == "Knuckles" and now < s.knuckles_block_until:
                dmg = 0.0
            if now < s.invulnerable_until:
                dmg = 0.0
            if s.char_id == "Knuckles" and s.knuckles_punch_armed:
                dmg *= KNUCKLES_PUNCH_CHARGE_DAMAGE_MULT
            if s.char_id == "MetalSonic" and s.metal_charge_until > now:
                dmg = max(0.0, dmg - METAL_CHARGE_DAMAGE_REDUCTION_FLAT)
            s.health -= dmg
            apply_survivor_hit_speed_boost(s, now)
            if s.health <= 0:
                s.health = 0.0
                resolve_survivor_zero_hp(s, now, combatants)
    killer.kollosios_grabbed_survivors = []


def _snap_survivors_to_killer(killer: Combatant, arena_w: float, arena_h: float) -> None:
    grabbed = killer.kollosios_grabbed_survivors
    n = len(grabbed)
    if n == 0:
        return
    fx, fy = killer.facing_x, killer.facing_y
    base_ang = math.atan2(fy, fx)
    for i, s in enumerate(grabbed):
        if not s.alive():
            continue
        ang = base_ang + (2.0 * math.pi * i) / max(n, 1) - math.pi * 0.5
        dist = killer.radius + s.radius + 18.0
        s.x = killer.x + math.cos(ang) * dist
        s.y = killer.y + math.sin(ang) * dist
        clamp_to_arena(s, arena_w, arena_h)


def tick_kollosios_charge(
    combatants: list[Combatant],
    killer: Combatant,
    arena_w: float,
    arena_h: float,
    now: float,
) -> None:
    if killer.char_id != "Kollosios" or not killer.alive():
        return

    if killer.kollosios_charge_until <= 0:
        return

    if now >= killer.kollosios_charge_until:
        _release_all(killer, now, combatants)
        killer.kollosios_charge_until = 0.0
        return

    _collect_grabs(killer, combatants, now)
    alive_grabbed = [s for s in killer.kollosios_grabbed_survivors if s.alive()]
    for s in killer.kollosios_grabbed_survivors:
        if not s.alive():
            s.held_by_kollosios_charge = False
    killer.kollosios_grabbed_survivors = alive_grabbed
    _snap_survivors_to_killer(killer, arena_w, arena_h)
