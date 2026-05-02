from __future__ import annotations

import math

from outcome_game.constants import (
    KOLLOSIOS_CHARGE_SPEED_MULT,
    PEELOUT_SPEED,
    X2011_GRAB_CHARGE_SPEED_MULT,
)
from outcome_game.arena_navigation import resolve_combatant_walls
from outcome_game.entities import Combatant, clamp_to_arena, separate_circles
from outcome_game.last_man_standing import last_man_standing_speed_mult
from outcome_game.x2011_rage import rage_speed_multiplier


def apply_input_to_velocity(
    c: Combatant,
    input_x: float,
    input_y: float,
    dt: float,
    now: float,
    combatants: list[Combatant],
    *,
    sprint_mult: float = 1.0,
) -> None:
    """Planar top-down movement: desired direction from input, speed from definition + buffs."""
    if c.dead or c.escaped or c.downed:
        c.vx = c.vy = 0.0
        return

    if c.char_id == "Sonic" and c.drop_dash_finale_until > now:
        c.vx = c.vy = 0.0
        return

    if c.char_id == "MetalSonic" and c.metal_charge_windup_until > now:
        length = math.hypot(input_x, input_y)
        if length > 1e-6:
            c.facing_x = input_x / length
            c.facing_y = input_y / length
        c.vx = c.vy = 0.0
        return

    if c.grabbed_by is not None:
        c.vx = c.vy = 0.0
        return

    if c.held_by_metal_charge_carrier is not None:
        c.vx = c.vy = 0.0
        return

    if c.held_by_kollosios_charge:
        c.vx = c.vy = 0.0
        return

    if c.held_by_kollosios_basic_grab:
        c.vx = c.vy = 0.0
        return

    if c.char_id == "X2011" and c.x2011_grab_victim is not None:
        c.vx = c.vy = 0.0
        return

    if c.carried_by_peelout:
        c.vx = c.vy = 0.0
        return

    # Knockback / slam displacement (runs while stunned, but not while grabbed / carried).
    if now < c.dash_until:
        lm = last_man_standing_speed_mult(c, combatants) if c.team == "Survivors" else 1.0
        c.vx = c.dash_vx * lm
        c.vy = c.dash_vy * lm
        c.x += c.vx * dt
        c.y += c.vy * dt
        return
    if now < c.stunned_until:
        c.vx = c.vy = 0.0
        return

    if c.char_id == "Sonic" and c.peelout_phase == "windup" and now < c.peelout_phase_end:
        length = math.hypot(input_x, input_y)
        if length > 1e-6:
            c.facing_x = input_x / length
            c.facing_y = input_y / length
        c.vx = c.vy = 0.0
        return

    if c.char_id == "Sonic" and c.peelout_phase == "carry" and now < c.peelout_phase_end:
        lm = last_man_standing_speed_mult(c, combatants)
        length = math.hypot(input_x, input_y)
        if length > 1e-6:
            c.peelout_vx = input_x / length
            c.peelout_vy = input_y / length
        vx = c.peelout_vx * PEELOUT_SPEED * lm
        vy = c.peelout_vy * PEELOUT_SPEED * lm
        c.vx, c.vy = vx, vy
        c.x += vx * dt
        c.y += vy * dt
        c.facing_x, c.facing_y = c.peelout_vx, c.peelout_vy
        return

    if c.char_id == "Sonic" and c.drop_dash_end > now:
        sp = c.drop_dash_speed if c.drop_dash_speed > 0 else c.base_walk_speed * 1.1
        sp *= last_man_standing_speed_mult(c, combatants)
        length = math.hypot(input_x, input_y)
        if length > 1e-6:
            nx = input_x / length
            ny = input_y / length
            c.facing_x, c.facing_y = nx, ny
        nx, ny = c.facing_x, c.facing_y
        c.vx = nx * sp
        c.vy = ny * sp
        c.x += c.vx * dt
        c.y += c.vy * dt
        return

    if c.char_id == "Kollosios" and c.kollosios_charge_until > now:
        sp = c.base_walk_speed * KOLLOSIOS_CHARGE_SPEED_MULT
        if now < c.speed_mult_until:
            sp *= c.speed_mult
        if now < c.slowed_until:
            sp *= c.slow_mult
        length = math.hypot(input_x, input_y)
        if length > 1e-6:
            nx = input_x / length
            ny = input_y / length
            c.facing_x, c.facing_y = nx, ny
        nx, ny = c.facing_x, c.facing_y
        c.vx = nx * sp
        c.vy = ny * sp
        c.x += c.vx * dt
        c.y += c.vy * dt
        return

    if c.char_id == "X2011" and c.x2011_grab_charge_until > now and c.x2011_grab_victim is None:
        sp = c.base_walk_speed * X2011_GRAB_CHARGE_SPEED_MULT * rage_speed_multiplier(c, now, combatants)
        if now < c.speed_mult_until:
            sp *= c.speed_mult
        if now < c.slowed_until:
            sp *= c.slow_mult
        length = math.hypot(input_x, input_y)
        if length > 1e-6:
            nx = input_x / length
            ny = input_y / length
            # Heavy charge has slower turning than normal movement.
            alpha = min(1.0, dt * 3.0)
            tx = c.facing_x + (nx - c.facing_x) * alpha
            ty = c.facing_y + (ny - c.facing_y) * alpha
            td = math.hypot(tx, ty)
            if td > 1e-6:
                c.facing_x, c.facing_y = tx / td, ty / td
        nx, ny = c.facing_x, c.facing_y
        c.vx = nx * sp
        c.vy = ny * sp
        c.x += c.vx * dt
        c.y += c.vy * dt
        return

    if c.char_id == "MetalSonic" and c.metal_self_heal_until > now:
        c.vx = c.vy = 0.0
        return

    if c.char_id == "MetalSonic" and c.metal_charge_until > now:
        sp = PEELOUT_SPEED * last_man_standing_speed_mult(c, combatants)
        if now < c.speed_mult_until:
            sp *= c.speed_mult
        if now < c.slowed_until:
            sp *= c.slow_mult
        length = math.hypot(input_x, input_y)
        if length > 1e-6:
            nx = input_x / length
            ny = input_y / length
            c.facing_x, c.facing_y = nx, ny
        nx, ny = c.facing_x, c.facing_y
        c.vx = nx * sp
        c.vy = ny * sp
        c.x += c.vx * dt
        c.y += c.vy * dt
        return

    sp = c.base_walk_speed
    if c.char_id == "Knuckles" and c.knuckles_punch_armed:
        # Charging Lunge Punch should heavily reduce mobility.
        sp *= 0.28
    if now < c.speed_mult_until:
        sp *= c.speed_mult
    if now < c.slowed_until:
        sp *= c.slow_mult
    if c.char_id == "X2011":
        sp *= rage_speed_multiplier(c, now, combatants)
    if c.team == "Survivors":
        sp *= last_man_standing_speed_mult(c, combatants)

    if sprint_mult > 1.0:
        sp *= sprint_mult

    length = math.hypot(input_x, input_y)
    if length > 1e-6:
        nx = input_x / length
        ny = input_y / length
        c.facing_x, c.facing_y = nx, ny
        c.vx = nx * sp
        c.vy = ny * sp
        c.x += c.vx * dt
        c.y += c.vy * dt
    else:
        c.vx = c.vy = 0.0


def _kollosios_grab_pair(a: Combatant, b: Combatant) -> bool:
    if a.char_id == "Kollosios" and a.kollosios_charge_until > 0 and b in a.kollosios_grabbed_survivors:
        return True
    if b.char_id == "Kollosios" and b.kollosios_charge_until > 0 and a in b.kollosios_grabbed_survivors:
        return True
    return False


def _kollosios_basic_grab_pair(a: Combatant, b: Combatant) -> bool:
    if a.char_id == "Kollosios" and a.kollosios_basic_grab_victim is b:
        return True
    if b.char_id == "Kollosios" and b.kollosios_basic_grab_victim is a:
        return True
    return False


def _x2011_grab_pair(a: Combatant, b: Combatant) -> bool:
    if a.char_id == "X2011" and a.x2011_grab_victim is b:
        return True
    if b.char_id == "X2011" and b.x2011_grab_victim is a:
        return True
    return False


def _peelout_carry_pair(a: Combatant, b: Combatant) -> bool:
    if a.char_id == "Sonic" and a.peelout_phase == "carry" and a.peelout_partner is b:
        return True
    if b.char_id == "Sonic" and b.peelout_phase == "carry" and b.peelout_partner is a:
        return True
    return False


def _survivor_executioner_phase_pair(a: Combatant, b: Combatant) -> bool:
    """Survivors pass through the executioner (no circle separation)."""
    if a.team == "Survivors" and b.team == "Executioners":
        return True
    if b.team == "Survivors" and a.team == "Executioners":
        return True
    return False


def integrate_and_collide(
    combatants: list[Combatant],
    arena_w: float,
    arena_h: float,
    walls: list,
) -> None:
    for c in combatants:
        if c.alive() and not c.escaped:
            clamp_to_arena(c, arena_w, arena_h)
            for _ in range(6):
                resolve_combatant_walls(c, walls)
    # Dead survivors are skipped above; clamp corpses so draws/VFX stay on the floor.
    for c in combatants:
        if c.team == "Survivors" and c.dead and not c.escaped:
            clamp_to_arena(c, arena_w, arena_h)
    n = len(combatants)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = combatants[i], combatants[j]
            if not (a.alive() and b.alive()):
                continue
            if a.escaped or b.escaped:
                continue
            if _peelout_carry_pair(a, b):
                continue
            if _kollosios_grab_pair(a, b):
                continue
            if _kollosios_basic_grab_pair(a, b):
                continue
            if _x2011_grab_pair(a, b):
                continue
            if _survivor_executioner_phase_pair(a, b):
                continue
            separate_circles(a, b)
