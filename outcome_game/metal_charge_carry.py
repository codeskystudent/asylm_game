"""Metal Sonic charge: carry X2011; wall slam beat-up + debris; drop when charge ends."""

from __future__ import annotations

import math
import random

import pygame

from outcome_game.constants import (
    METAL_CHARGE_BEATUP_ANIM_SECONDS,
    METAL_CHARGE_CARRY_HP_DRAIN_INTERVAL,
    METAL_CHARGE_CARRY_HP_DRAIN_PER_TICK,
    METAL_CHARGE_CARRY_HP_LOSS_END_CHARGE,
    METAL_CHARGE_DURATION_WITH_X2011_CARRY_SECONDS,
    METAL_CHARGE_DEBRIS_COUNT,
    METAL_CHARGE_DEBRIS_LIFETIME,
    METAL_CHARGE_DEBRIS_SPEED_MAX,
    METAL_CHARGE_DEBRIS_SPEED_MIN,
    METAL_CHARGE_HP_COST,
    METAL_CHARGE_KILLER_STUN_SECONDS,
    METAL_CHARGE_X2011_DROP_STUN_SECONDS,
    METAL_CHARGE_X2011_SLAM_STUN_SECONDS,
    METAL_CHARGE_SLAM_DAMAGE,
    METAL_CHARGE_SLAM_KNOCKBACK_MULT,
    METAL_CHARGE_SLAM_KNOCKBACK_SECONDS,
    METAL_CHARGE_WALL_SLAM_DEPTH,
)
from outcome_game.arena_navigation import resolve_combatant_walls
from outcome_game.entities import Combatant, clamp_to_arena
from outcome_game.survivor_death_revive import resolve_survivor_zero_hp
from outcome_game.hit_reaction import apply_survivor_hit_speed_boost
from outcome_game.last_man_standing import last_man_incoming_damage_multiplier
from outcome_game.x2011_rage import apply_executioner_stun_from_now


def _flat_dist(a: Combatant, b: Combatant) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _deepest_wall_penetration(
    x: float,
    y: float,
    r: float,
    walls: list[pygame.Rect],
) -> tuple[float, float, float] | None:
    """Deepest circle-vs-AABB penetration; returns outward normal (nx, ny) and depth."""
    best_depth = 0.0
    best_nx = 0.0
    best_ny = 1.0
    for w in walls:
        cx = max(float(w.left), min(x, float(w.right)))
        cy = max(float(w.top), min(y, float(w.bottom)))
        dx = x - cx
        dy = y - cy
        d = math.hypot(dx, dy)
        if d >= r - 1e-8:
            continue
        depth = r - d
        if depth <= best_depth:
            continue
        best_depth = depth
        if d > 1e-6:
            inv = 1.0 / d
            best_nx = dx * inv
            best_ny = dy * inv
        else:
            dl = x - w.left
            dr = w.right - x
            dt = y - w.top
            db = w.bottom - y
            m = min(dl, dr, dt, db)
            if m == dl:
                best_nx, best_ny = -1.0, 0.0
            elif m == dr:
                best_nx, best_ny = 1.0, 0.0
            elif m == dt:
                best_nx, best_ny = 0.0, -1.0
            else:
                best_nx, best_ny = 0.0, 1.0
    if best_depth <= 0.0:
        return None
    return best_nx, best_ny, best_depth


def _clear_carry_refs(metal: Combatant, killer: Combatant) -> None:
    metal.metal_charge_carry_target = None
    killer.held_by_metal_charge_carrier = None
    metal.metal_carry_hp_drain_bank = 0.0
    metal.metal_carry_hp_drained_total = 0.0


def _release_carry_soft(metal: Combatant, killer: Combatant, now: float) -> None:
    _clear_carry_refs(metal, killer)
    killer.stunned_until = max(killer.stunned_until, now + METAL_CHARGE_X2011_DROP_STUN_SECONDS)


def _spawn_debris(metal: Combatant, nx: float, ny: float, now: float) -> None:
    """Concrete/concrete dust chunks radiating from slam."""
    for _ in range(METAL_CHARGE_DEBRIS_COUNT):
        ang = random.uniform(0, math.tau)
        sp = random.uniform(METAL_CHARGE_DEBRIS_SPEED_MIN, METAL_CHARGE_DEBRIS_SPEED_MAX)
        # Bias outward from wall normal with scatter
        vx = nx * sp * 0.55 + math.cos(ang) * sp * 0.55
        vy = ny * sp * 0.55 + math.sin(ang) * sp * 0.55
        ox = random.uniform(-14.0, 14.0)
        oy = random.uniform(-14.0, 14.0)
        col = random.choice(
            (
                (190, 188, 195),
                (160, 158, 168),
                (220, 90, 70),
                (255, 200, 120),
                (120, 118, 130),
            )
        )
        metal.metal_charge_debris.append(
            (metal.x + ox, metal.y + oy, vx, vy, now + METAL_CHARGE_DEBRIS_LIFETIME, col)
        )


def _wall_slam_metal_into_killer(
    metal: Combatant,
    killer: Combatant,
    nx: float,
    ny: float,
    now: float,
    combatants: list[Combatant],
) -> None:
    """Beat-up: damage X2011, knockback, VFX; stops carry and ends Metal's killer charge."""
    metal.metal_charge_until = now
    _clear_carry_refs(metal, killer)
    metal.metal_beatup_anim_until = now + METAL_CHARGE_BEATUP_ANIM_SECONDS
    metal.ability_flash_until = max(metal.ability_flash_until, now + METAL_CHARGE_BEATUP_ANIM_SECONDS * 0.9)
    killer.ability_flash_until = max(killer.ability_flash_until, now + 0.35)

    dmg = METAL_CHARGE_SLAM_DAMAGE * last_man_incoming_damage_multiplier(killer, combatants)
    killer.health -= dmg
    if killer.health <= 0:
        killer.health = 0.0
        killer.dead = True
    apply_survivor_hit_speed_boost(metal, now)

    # Knock killer along outward normal (away from wall into arena)
    killer.dash_until = now + METAL_CHARGE_SLAM_KNOCKBACK_SECONDS
    killer.dash_vx = nx * METAL_CHARGE_SLAM_KNOCKBACK_MULT
    killer.dash_vy = ny * METAL_CHARGE_SLAM_KNOCKBACK_MULT

    apply_executioner_stun_from_now(
        killer, now, METAL_CHARGE_X2011_SLAM_STUN_SECONDS, combatants, apply_knockback=False
    )
    _spawn_debris(metal, nx, ny, now)


def try_pickup_x2011(metal: Combatant, killer: Combatant, now: float) -> None:
    metal.metal_charge_carry_target = killer
    killer.held_by_metal_charge_carrier = metal
    metal.metal_carry_hp_drain_bank = 0.0
    metal.metal_carry_hp_drained_total = 0.0
    # Longer charge window while dragging X2011 (solo charge is METAL_CHARGE_DURATION_SECONDS only).
    metal.metal_charge_until = now + METAL_CHARGE_DURATION_WITH_X2011_CARRY_SECONDS


def _tick_carry_hp_drain(
    metal: Combatant,
    killer: Combatant,
    combatants: list[Combatant],
    dt: float,
    now: float,
) -> None:
    """Lose 1 HP per 0.1s while dragging X2011; drop carry if Metal dies or total drain hits cap."""
    metal.metal_carry_hp_drain_bank += dt
    while metal.metal_carry_hp_drain_bank >= METAL_CHARGE_CARRY_HP_DRAIN_INTERVAL:
        metal.health -= METAL_CHARGE_CARRY_HP_DRAIN_PER_TICK
        metal.metal_carry_hp_drain_bank -= METAL_CHARGE_CARRY_HP_DRAIN_INTERVAL
        metal.metal_carry_hp_drained_total += METAL_CHARGE_CARRY_HP_DRAIN_PER_TICK

        if metal.metal_carry_hp_drained_total >= METAL_CHARGE_CARRY_HP_LOSS_END_CHARGE:
            metal.metal_charge_until = now
            _release_carry_soft(metal, killer, now)
            return

        if metal.health <= 0:
            metal.health = 0.0
            _release_carry_soft(metal, killer, now)
            resolve_survivor_zero_hp(metal, now, combatants)
            return


def sync_carried_killer(
    metal: Combatant,
    killer: Combatant,
    now: float,
    arena_w: float,
    arena_h: float,
    walls: list[pygame.Rect],
) -> None:
    fx = metal.facing_x
    fy = metal.facing_y
    fd = math.hypot(fx, fy) or 1.0
    fx /= fd
    fy /= fd
    gap = metal.radius + killer.radius + 5.0
    killer.x = metal.x + fx * gap
    killer.y = metal.y + fy * gap
    killer.facing_x = -fx
    killer.facing_y = -fy
    killer.vx = killer.vy = 0.0
    # Stay stunned for the rest of the charge while dragged; drop/slam set final stun length.
    killer.stunned_until = max(killer.stunned_until, metal.metal_charge_until + 0.2)
    clamp_to_arena(killer, arena_w, arena_h)
    for _ in range(5):
        resolve_combatant_walls(killer, walls)
    clamp_to_arena(killer, arena_w, arena_h)


def tick_metal_charge_pre_integrate(
    combatants: list[Combatant],
    killer: Combatant,
    walls: list[pygame.Rect],
    now: float,
) -> None:
    """Pickup X2011, legacy grab on other killers, wall slam before wall resolution."""
    if not killer.alive() or killer.escaped:
        for c in combatants:
            if c.char_id != "MetalSonic":
                continue
            if c.metal_charge_carry_target is killer:
                _release_carry_soft(c, killer, now)
        return

    # Wall slam (Metal already carrying X2011 this frame — uses pre-resolve penetration)
    for c in combatants:
        if c.char_id != "MetalSonic" or not c.alive() or c.escaped:
            continue
        tgt = c.metal_charge_carry_target
        if tgt is None or tgt is not killer:
            continue
        if killer.char_id != "X2011":
            continue
        if c.metal_charge_until <= now:
            continue
        pen = _deepest_wall_penetration(c.x, c.y, c.radius, walls)
        if pen is None:
            continue
        nx, ny, depth = pen
        if depth < METAL_CHARGE_WALL_SLAM_DEPTH:
            continue
        _wall_slam_metal_into_killer(c, killer, nx, ny, now, combatants)

    # First contact: pick up X2011
    for c in combatants:
        if c.char_id != "MetalSonic" or not c.alive() or c.escaped:
            continue
        if c.metal_charge_until <= now:
            continue
        if c.metal_charge_carry_target is not None:
            continue
        if killer.char_id != "X2011":
            continue
        if _flat_dist(c, killer) > c.radius + killer.radius + 12.0:
            continue
        try_pickup_x2011(c, killer, now)
        c.metal_charge_grab_used = True
        return

    # Other executioners: original one-shot stun + HP cost
    for c in combatants:
        if c.char_id != "MetalSonic" or not c.alive() or c.escaped:
            continue
        if c.metal_charge_until <= now or c.metal_charge_grab_used:
            continue
        if killer.char_id == "X2011":
            continue
        if _flat_dist(c, killer) > c.radius + killer.radius + 10.0:
            continue
        apply_executioner_stun_from_now(killer, now, METAL_CHARGE_KILLER_STUN_SECONDS, combatants)
        c.health -= METAL_CHARGE_HP_COST
        if c.health <= 0:
            c.health = 0.0
            resolve_survivor_zero_hp(c, now, combatants)
        c.metal_charge_grab_used = True
        return


def tick_metal_charge_post_integrate(
    combatants: list[Combatant],
    killer: Combatant,
    arena_w: float,
    arena_h: float,
    walls: list[pygame.Rect],
    now: float,
    dt: float,
) -> None:
    """Snap carried killer to Metal; drop when charge ends; advance debris."""
    for c in combatants:
        if c.char_id == "MetalSonic" and not c.alive() and c.metal_charge_carry_target is not None:
            tgt = c.metal_charge_carry_target
            if tgt is not None:
                tgt.held_by_metal_charge_carrier = None
            c.metal_charge_carry_target = None

    for c in combatants:
        if c.char_id != "MetalSonic" or not c.alive() or c.escaped:
            continue
        tgt = c.metal_charge_carry_target
        if tgt is None:
            continue
        if not tgt.alive() or tgt.escaped:
            _clear_carry_refs(c, tgt)
            continue
        if tgt is not killer or killer.char_id != "X2011":
            _clear_carry_refs(c, tgt)
            continue

        # Charge expired — drop without slam
        if c.metal_charge_until <= now:
            _release_carry_soft(c, killer, now)
            continue

        _tick_carry_hp_drain(c, killer, combatants, dt, now)
        if not c.alive():
            continue

        sync_carried_killer(c, killer, now, arena_w, arena_h, walls)

    # Debris particles
    for c in combatants:
        if c.char_id != "MetalSonic":
            continue
        new_parts: list[tuple[float, float, float, float, float, tuple[int, int, int]]] = []
        for x, y, vx, vy, exp, col in c.metal_charge_debris:
            if exp <= now:
                continue
            vx *= 0.985
            vy *= 0.985
            new_parts.append((x + vx * dt, y + vy * dt, vx, vy, exp, col))
        c.metal_charge_debris = new_parts
