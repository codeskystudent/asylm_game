"""Kollosios: basic attack can randomly grab one survivor, punch rolls, then throw."""

from __future__ import annotations

import math
import random

from outcome_game.constants import (
    METAL_CHARGE_DAMAGE_REDUCTION_FLAT,
    KNUCKLES_PUNCH_CHARGE_DAMAGE_MULT,
    KOLLOSIOS_BASIC_GRAB_PUNCH_CHANCE,
    KOLLOSIOS_BASIC_GRAB_SECONDS,
    KOLLOSIOS_BASIC_GRAB_THROW_DASH_SECONDS,
    KOLLOSIOS_BASIC_GRAB_THROW_SPEED,
)
from outcome_game.entities import Combatant, clamp_to_arena
from outcome_game.survivor_death_revive import resolve_survivor_zero_hp
from outcome_game.hit_reaction import apply_survivor_hit_speed_boost
from outcome_game.last_man_standing import last_man_incoming_damage_multiplier


def _flat_dist(a: Combatant, b: Combatant) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _release_victim_state(victim: Combatant) -> None:
    victim.held_by_kollosios_basic_grab = False


def _throw_victim(killer: Combatant, victim: Combatant, now: float) -> None:
    dx = victim.x - killer.x
    dy = victim.y - killer.y
    dist = math.hypot(dx, dy)
    if dist < 1e-4:
        dx, dy = killer.facing_x, killer.facing_y
        dist = 1.0
    nx = dx / dist
    ny = dy / dist
    victim.dash_until = now + KOLLOSIOS_BASIC_GRAB_THROW_DASH_SECONDS
    victim.dash_vx = nx * KOLLOSIOS_BASIC_GRAB_THROW_SPEED
    victim.dash_vy = ny * KOLLOSIOS_BASIC_GRAB_THROW_SPEED


def try_begin_basic_grab(killer: Combatant, victim: Combatant, now: float) -> None:
    if victim.char_id == "Knuckles" and victim.knuckles_block_until > now:
        return
    killer.kollosios_basic_grab_victim = victim
    killer.kollosios_basic_grab_until = now + KOLLOSIOS_BASIC_GRAB_SECONDS
    killer.kollosios_basic_grab_start = now
    killer.kollosios_basic_grab_last_pulse_sec = 0
    victim.held_by_kollosios_basic_grab = True


def tick_kollosios_basic_grab(
    killer: Combatant,
    combatants: list[Combatant],
    arena_w: float,
    arena_h: float,
    now: float,
) -> None:
    if killer.char_id != "Kollosios" or not killer.alive():
        return

    victim = killer.kollosios_basic_grab_victim
    if victim is None:
        return

    if not victim.alive() or victim.escaped:
        killer.kollosios_basic_grab_victim = None
        killer.kollosios_basic_grab_until = 0.0
        _release_victim_state(victim)
        return

    if now >= killer.kollosios_basic_grab_until:
        _throw_victim(killer, victim, now)
        killer.kollosios_basic_grab_victim = None
        killer.kollosios_basic_grab_until = 0.0
        _release_victim_state(victim)
        return

    elapsed = now - killer.kollosios_basic_grab_start
    curr_sec = int(math.floor(elapsed))
    prev = killer.kollosios_basic_grab_last_pulse_sec
    if curr_sec > prev:
        for s in range(prev + 1, curr_sec + 1):
            if 1 <= s <= 5 and random.random() < KOLLOSIOS_BASIC_GRAB_PUNCH_CHANCE:
                dmg = 10.0 * float(s)
                if victim.char_id == "Knuckles" and now < victim.knuckles_block_until:
                    dmg = 0.0
                if now < victim.invulnerable_until:
                    dmg = 0.0
                if victim.char_id == "Knuckles" and victim.knuckles_punch_armed:
                    dmg *= KNUCKLES_PUNCH_CHARGE_DAMAGE_MULT
                if victim.char_id == "MetalSonic" and victim.metal_charge_until > now:
                    dmg = max(0.0, dmg - METAL_CHARGE_DAMAGE_REDUCTION_FLAT)
                armor = 0.65 if now < victim.armor_until else 1.0
                lms = last_man_incoming_damage_multiplier(victim, combatants)
                victim.health -= dmg * armor * lms
                apply_survivor_hit_speed_boost(victim, now)
                if victim.health <= 0:
                    victim.health = 0.0
                    resolve_survivor_zero_hp(victim, now, combatants)
                    killer.kollosios_basic_grab_victim = None
                    killer.kollosios_basic_grab_until = 0.0
                    _release_victim_state(victim)
                    return
        killer.kollosios_basic_grab_last_pulse_sec = curr_sec

    off = killer.radius + victim.radius + 6.0
    victim.x = killer.x + killer.facing_x * off
    victim.y = killer.y + killer.facing_y * off
    clamp_to_arena(victim, arena_w, arena_h)
