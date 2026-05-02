"""Survivor elimination: first KO is downed (revivable once); Metal Sonic explodes instead."""

from __future__ import annotations

import math

from outcome_game.constants import (
    ARENA_H,
    ARENA_W,
    METAL_DEATH_BURST_VISUAL_SECONDS,
    METAL_DEATH_EXPLOSION_RADIUS,
    METAL_DEATH_STUN_X2011_SECONDS,
    REVIVE_CHANNEL_SECONDS,
    REVIVE_HP_FRACTION,
)
from outcome_game.entities import Combatant, clamp_to_arena


def resolve_survivor_zero_hp(target: Combatant, now: float, combatants: list[Combatant]) -> None:
    """
    Survivor HP has reached 0. Metal Sonic always detonates; others enter downed once unless already revived.
    """
    if target.team != "Survivors":
        return
    target.health = 0.0
    if target.char_id == "MetalSonic":
        # Keep death/VFX in the arena so explosion isn't drawn in margin / off playable floor.
        clamp_to_arena(target, ARENA_W, ARENA_H)
        _trigger_metal_self_destruct(target, now, combatants)
        target.dead = True
        target.downed = False
        return
    if target.revive_used:
        target.dead = True
        target.downed = False
        return
    target.downed = True
    target.dead = False


def _trigger_metal_self_destruct(metal: Combatant, now: float, combatants: list[Combatant]) -> None:
    metal.metal_death_origin_x = metal.x
    metal.metal_death_origin_y = metal.y
    metal.metal_death_burst_until = now + METAL_DEATH_BURST_VISUAL_SECONDS
    ox, oy = metal.metal_death_origin_x, metal.metal_death_origin_y
    for c in combatants:
        if c.team != "Executioners" or c.char_id != "X2011":
            continue
        if not c.alive():
            continue
        if math.hypot(c.x - ox, c.y - oy) <= METAL_DEATH_EXPLOSION_RADIUS + c.radius:
            c.stunned_until = max(c.stunned_until, now + METAL_DEATH_STUN_X2011_SECONDS)


def apply_revive_pickup(victim: Combatant, now: float) -> None:
    victim.downed = False
    victim.revive_used = True
    victim.health = victim.max_health * REVIVE_HP_FRACTION
    victim.revive_progress = 0.0


def _touching(a: Combatant, b: Combatant) -> bool:
    dist = math.hypot(a.x - b.x, a.y - b.y)
    return dist <= a.radius + b.radius + 1.5


def tick_revives(combatants: list[Combatant], now: float, dt: float) -> None:
    """Revive channels while an alive survivor overlaps the downed body (circles touching)."""
    for victim in combatants:
        if not victim.downed:
            continue
        reviver: Combatant | None = None
        best_d = 1e18
        for rev in combatants:
            if rev is victim or rev.team != "Survivors" or rev.dead or rev.downed or rev.escaped:
                continue
            if not rev.alive():
                continue
            if not _touching(rev, victim):
                continue
            d = math.hypot(rev.x - victim.x, rev.y - victim.y)
            if d < best_d:
                best_d = d
                reviver = rev
        if reviver is None:
            victim.revive_progress = max(0.0, victim.revive_progress - dt * 2.2)
            continue
        victim.revive_progress += dt
        if victim.revive_progress >= REVIVE_CHANNEL_SECONDS:
            apply_revive_pickup(victim, now)
