"""2011X grab charge: sprint, grab survivor, DPS, mash minigame, stun killer on escape."""

from __future__ import annotations

import math

from outcome_game.constants import (
    METAL_CHARGE_DAMAGE_REDUCTION_FLAT,
    KNUCKLES_PUNCH_CHARGE_DAMAGE_MULT,
    X2011_GRAB_BOT_ESCAPE_PER_SECOND,
    X2011_GRAB_BREAK_STUN_SECONDS,
    X2011_GRAB_CHARGE_SECONDS,
    X2011_GRAB_DPS,
)
from outcome_game.entities import Combatant, clamp_to_arena
from outcome_game.survivor_death_revive import resolve_survivor_zero_hp
from outcome_game.hit_reaction import apply_survivor_hit_speed_boost
from outcome_game.last_man_standing import last_man_incoming_damage_multiplier
from outcome_game.x2011_rage import apply_executioner_stun_from_now, rage_damage_multiplier


def _flat_dist(a: Combatant, b: Combatant) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def try_start_grab_charge(killer: Combatant, now: float) -> bool:
    if killer.char_id != "X2011" or not killer.alive():
        return False
    if killer.x2011_grab_victim is not None:
        return False
    if killer.x2011_grab_charge_until > now:
        return False
    killer.x2011_grab_charge_until = now + X2011_GRAB_CHARGE_SECONDS
    killer.x2011_charge_trail = []
    killer.x2011_charge_warn_count = 0
    return True


def _release_grab(
    killer: Combatant,
    victim: Combatant,
    *,
    stun_killer_seconds: float,
    now: float,
    combatants: list[Combatant] | None = None,
) -> None:
    victim.grabbed_by = None
    victim.grab_break_progress = 0.0
    killer.x2011_grab_victim = None
    killer.x2011_grab_until = 0.0
    if stun_killer_seconds > 0:
        apply_executioner_stun_from_now(killer, now, stun_killer_seconds, combatants)


def _try_begin_grab_from_charge(killer: Combatant, combatants: list[Combatant], now: float) -> None:
    if killer.x2011_grab_victim is not None:
        return
    if killer.x2011_grab_charge_until <= now:
        return
    best: Combatant | None = None
    best_d = 1e18
    for s in combatants:
        if s.team != "Survivors" or not s.alive() or s.escaped:
            continue
        if s.char_id == "Knuckles" and s.knuckles_block_until > now:
            continue
        if s.grabbed_by is not None:
            continue
        d = _flat_dist(killer, s)
        touch = killer.radius + s.radius + 10.0
        if d <= touch and d < best_d:
            best_d = d
            best = s
    if not best:
        return
    killer.x2011_grab_victim = best
    killer.x2011_grab_until = now + X2011_GRAB_CHARGE_SECONDS
    killer.x2011_grab_charge_until = now
    killer.x2011_charge_trail = []
    killer.x2011_charge_warn_count = 0
    best.grabbed_by = killer
    best.grab_break_progress = 0.0


def _tick_charge_fx(killer: Combatant, combatants: list[Combatant], now: float) -> None:
    """Charge-only FX: trail, three release warning flashes, and proximity flash."""
    ttl = 0.3
    killer.x2011_charge_trail = [(x, y, t) for (x, y, t) in killer.x2011_charge_trail if now - t <= ttl]
    if killer.x2011_grab_charge_until <= now or killer.x2011_grab_victim is not None:
        killer.x2011_charge_warn_count = 0
        return
    if (
        not killer.x2011_charge_trail
        or (killer.x - killer.x2011_charge_trail[-1][0]) ** 2 + (killer.y - killer.x2011_charge_trail[-1][1]) ** 2 >= 16.0 * 16.0
    ):
        killer.x2011_charge_trail.append((killer.x, killer.y, now))

    remaining = killer.x2011_grab_charge_until - now
    warn_times = (0.9, 0.6, 0.3)
    while killer.x2011_charge_warn_count < 3 and remaining <= warn_times[killer.x2011_charge_warn_count]:
        killer.ability_flash_until = max(killer.ability_flash_until, now + 0.14)
        killer.x2011_charge_warn_count += 1

    best = 1e18
    touch_pad = 76.0
    for s in combatants:
        if s.team != "Survivors" or not s.alive() or s.escaped:
            continue
        d = _flat_dist(killer, s) - (killer.radius + s.radius)
        if d < best:
            best = d
    if best <= touch_pad:
        killer.ability_flash_until = max(killer.ability_flash_until, now + 0.1)


def tick_x2011_grab(
    combatants: list[Combatant],
    killer: Combatant,
    arena_w: float,
    arena_h: float,
    now: float,
    dt: float,
) -> None:
    if killer.char_id != "X2011" or not killer.alive():
        return

    _tick_charge_fx(killer, combatants, now)

    if killer.x2011_grab_victim is None:
        _try_begin_grab_from_charge(killer, combatants, now)

    victim = killer.x2011_grab_victim
    if victim is None:
        return

    if not victim.alive() or victim.escaped:
        _release_grab(killer, victim, stun_killer_seconds=0.0, now=now, combatants=combatants)
        return

    if now >= killer.x2011_grab_until:
        _release_grab(killer, victim, stun_killer_seconds=0.0, now=now, combatants=combatants)
        return

    dps = X2011_GRAB_DPS * rage_damage_multiplier(killer, now, combatants)
    dps *= last_man_incoming_damage_multiplier(victim, combatants)
    if victim.char_id == "Knuckles" and now < victim.knuckles_block_until:
        dps = 0.0
    if now < victim.invulnerable_until:
        dps = 0.0
    if victim.char_id == "Knuckles" and victim.knuckles_punch_armed:
        dps *= KNUCKLES_PUNCH_CHARGE_DAMAGE_MULT
    if victim.char_id == "MetalSonic" and victim.metal_charge_until > now:
        dps = max(0.0, dps - METAL_CHARGE_DAMAGE_REDUCTION_FLAT)
    victim.health -= dps * dt
    apply_survivor_hit_speed_boost(victim, now)
    if victim.health <= 0:
        victim.health = 0.0
        resolve_survivor_zero_hp(victim, now, combatants)
        _release_grab(killer, victim, stun_killer_seconds=0.0, now=now, combatants=combatants)
        return

    if victim.is_bot:
        victim.grab_break_progress += X2011_GRAB_BOT_ESCAPE_PER_SECOND * dt

    if victim.grab_break_progress >= 100.0:
        _release_grab(
            killer,
            victim,
            stun_killer_seconds=X2011_GRAB_BREAK_STUN_SECONDS,
            now=now,
            combatants=combatants,
        )
        return

    off = killer.radius + victim.radius + 6.0
    victim.x = killer.x + killer.facing_x * off
    victim.y = killer.y + killer.facing_y * off
    clamp_to_arena(victim, arena_w, arena_h)
