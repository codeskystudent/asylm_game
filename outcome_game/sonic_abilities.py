"""Sonic-only Peelout and Drop Dash state machine and movement helpers."""

from __future__ import annotations

import math

from outcome_game.constants import (
    DROP_DASH_BOUNCE_DISTANCE,
    DROP_DASH_HIT_LOCK_SECONDS,
    DROP_DASH_KILLER_STUN_SECONDS,
    DROP_DASH_MAX_BUMPS,
    DROP_DASH_MAX_SECONDS,
    DROP_DASH_SPEED_VS_KILLER_MULT,
    PEELOUT_CARRY_SECONDS,
    PEELOUT_SPEED,
    PEELOUT_WINDUP_SECONDS,
)
from outcome_game.entities import Combatant, clamp_to_arena
from outcome_game.x2011_rage import apply_executioner_stun_from_now


def _dist(a: Combatant, b: Combatant) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _is_sonic(c: Combatant) -> bool:
    return c.char_id == "Sonic"


def _nearest_other_survivor(sonic: Combatant, combatants: list[Combatant]) -> Combatant | None:
    best: Combatant | None = None
    best_d = 1e18
    for c in combatants:
        if c is sonic or c.team != "Survivors" or not c.alive() or c.escaped:
            continue
        d = _dist(sonic, c)
        if d < best_d:
            best_d = d
            best = c
    return best


def try_start_peelout(sonic: Combatant, now: float, combatants: list[Combatant]) -> bool:
    if not _is_sonic(sonic) or not sonic.alive() or sonic.escaped:
        return False
    if sonic.peelout_phase != "none":
        return False
    if sonic.drop_dash_end > now:
        return False
    sonic.peelout_phase = "windup"
    sonic.peelout_phase_end = now + PEELOUT_WINDUP_SECONDS
    return True


def try_start_drop_dash(sonic: Combatant, killer: Combatant, now: float) -> bool:
    if not _is_sonic(sonic) or not sonic.alive() or sonic.escaped:
        return False
    if sonic.peelout_phase != "none":
        return False
    if sonic.drop_dash_end > now:
        return False
    sonic.drop_dash_end = now + DROP_DASH_MAX_SECONDS
    sonic.drop_dash_bumps = 0
    sonic.drop_dash_hit_lock_until = 0.0
    sonic.drop_dash_speed = max(
        sonic.base_walk_speed * 1.05,
        killer.base_walk_speed * DROP_DASH_SPEED_VS_KILLER_MULT,
    )
    return True


def _release_peelout_partner(sonic: Combatant) -> None:
    if sonic.peelout_partner:
        sonic.peelout_partner.carried_by_peelout = False
    sonic.peelout_partner = None


def tick_peelout_phases(sonic: Combatant, combatants: list[Combatant], now: float) -> None:
    """Windup -> carry, carry -> end."""
    if not _is_sonic(sonic):
        return

    if sonic.peelout_phase == "carry":
        p = sonic.peelout_partner
        if p is None or not p.alive() or p.escaped:
            _release_peelout_partner(sonic)
            sonic.peelout_phase = "none"
            sonic.peelout_phase_end = 0.0
            sonic.peelout_vx = sonic.peelout_vy = 0.0

    if sonic.peelout_phase == "windup" and now >= sonic.peelout_phase_end:
        partner = _nearest_other_survivor(sonic, combatants)
        d = math.hypot(sonic.facing_x, sonic.facing_y) or 1.0
        sonic.peelout_vx = sonic.facing_x / d
        sonic.peelout_vy = sonic.facing_y / d

        if partner:
            sonic.peelout_partner = partner
            partner.carried_by_peelout = True
            sonic.peelout_phase = "carry"
            sonic.peelout_phase_end = now + PEELOUT_CARRY_SECONDS
        else:
            sonic.peelout_phase = "none"
            sonic.peelout_phase_end = 0.0

    elif sonic.peelout_phase == "carry" and now >= sonic.peelout_phase_end:
        _release_peelout_partner(sonic)
        sonic.peelout_phase = "none"
        sonic.peelout_phase_end = 0.0
        sonic.peelout_vx = sonic.peelout_vy = 0.0


def sync_peelout_partner(sonic: Combatant, arena_w: float, arena_h: float) -> None:
    """Keep grabbed survivor tucked behind Sonic during carry."""
    if sonic.peelout_phase != "carry" or not sonic.peelout_partner:
        return
    p = sonic.peelout_partner
    if not p.alive() or p.escaped:
        return
    # Keep partner right behind Sonic (nearly touching circles) during peelout carry.
    off = sonic.radius + p.radius + 2.0
    p.x = sonic.x - sonic.peelout_vx * off
    p.y = sonic.y - sonic.peelout_vy * off
    clamp_to_arena(p, arena_w, arena_h)


def tick_drop_dash_end(sonic: Combatant, now: float) -> None:
    if not _is_sonic(sonic):
        return
    if sonic.drop_dash_end > 0 and now >= sonic.drop_dash_end:
        sonic.drop_dash_end = 0.0
        sonic.drop_dash_speed = 0.0
        sonic.drop_dash_bumps = 0


def process_drop_dash_killer_hits(
    sonic: Combatant,
    killer: Combatant,
    now: float,
    arena_w: float,
    arena_h: float,
    combatants: list[Combatant],
) -> None:
    if not _is_sonic(sonic) or sonic.drop_dash_end <= 0 or now >= sonic.drop_dash_end:
        return
    if not killer.alive() or killer.escaped:
        return
    if now < sonic.drop_dash_hit_lock_until:
        return

    hit_r = sonic.radius + killer.radius + 4.0
    if _dist(sonic, killer) > hit_r:
        return

    apply_executioner_stun_from_now(killer, now, DROP_DASH_KILLER_STUN_SECONDS, combatants)
    sonic.health = min(sonic.max_health, sonic.health + 5.0)
    sonic.drop_dash_bumps += 1
    sonic.drop_dash_hit_lock_until = now + DROP_DASH_HIT_LOCK_SECONDS

    dx = sonic.x - killer.x
    dy = sonic.y - killer.y
    d = math.hypot(dx, dy) or 1.0
    sonic.x += (dx / d) * DROP_DASH_BOUNCE_DISTANCE
    sonic.y += (dy / d) * DROP_DASH_BOUNCE_DISTANCE
    clamp_to_arena(sonic, arena_w, arena_h)

    if sonic.drop_dash_bumps >= DROP_DASH_MAX_BUMPS:
        sonic.drop_dash_end = now
        sonic.drop_dash_speed = 0.0


def pre_movement_tick(combatants: list[Combatant], now: float) -> None:
    """Run before velocity integration: peelout windup -> carry transitions."""
    for c in combatants:
        if _is_sonic(c):
            tick_peelout_phases(c, combatants, now)


def post_movement_tick(
    combatants: list[Combatant],
    killer: Combatant,
    arena_w: float,
    arena_h: float,
    now: float,
) -> None:
    """After positions updated: sync carry partner, hits, expire drop dash."""
    for c in combatants:
        if _is_sonic(c):
            sync_peelout_partner(c, arena_w, arena_h)
    for c in combatants:
        if _is_sonic(c):
            process_drop_dash_killer_hits(c, killer, now, arena_w, arena_h, combatants)
            tick_drop_dash_end(c, now)
