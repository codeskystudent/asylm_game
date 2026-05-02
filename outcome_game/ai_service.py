"""Bot steering for survivors (evade + exit) and executioner (chase + attack)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from outcome_game.arena_navigation import pathfind_direction
from outcome_game.character_definitions import registry as char_registry
from outcome_game.constants import (
    ARENA_H,
    ARENA_W,
    SURVIVOR_FLEE_RADIUS,
    SURVIVOR_INTERIOR_GOAL_MARGIN,
)
from outcome_game.match_service import exits_available_for_escape, get_exit_rects
from outcome_game.entities import Combatant


@dataclass
class BotBrain:
    """Staggered timers so bots don't all pathfind on the same frame."""

    next_path_t: float = 0.0
    next_ability_t: float = 0.0
    next_survivor_ability_t: float = 0.0
    wander_angle: float = 0.0
    smooth_dx: float = 0.0
    smooth_dy: float = 0.0


_bot_state: dict[str, BotBrain] = {}
_STUN_BEHAVIOR_KEYS = {
    "survivor_stun_pulse",
    "amy_hammer_melee",
    "amy_hammer_throw",
    "survivor_lunge_punch",
    "survivor_block_stun",
    "tails_hand_cannon",
    "sonic_drop_dash",
    "metal_killer_charge",
}
_STUN_DEFAULT_RANGES = {
    "survivor_stun_pulse": 120.0,
    "survivor_block_stun": 70.0,
    "survivor_lunge_punch": 100.0,
    "amy_hammer_melee": 70.0,
    "amy_hammer_throw": 220.0,
    "tails_hand_cannon": 400.0,
    "sonic_drop_dash": 270.0,
    "metal_killer_charge": 340.0,
}


def reset_brains() -> None:
    _bot_state.clear()


def _smoothed_steer(bot: Combatant, ix: float, iy: float, dt: float) -> tuple[float, float]:
    """Blend steering toward raw path direction so bots curve instead of snapping axis-aligned."""
    if ix * ix + iy * iy < 1e-10:
        b = _brain(bot)
        b.smooth_dx = 0.0
        b.smooth_dy = 0.0
        return 0.0, 0.0
    d = math.hypot(ix, iy)
    tx, ty = ix / d, iy / d
    b = _brain(bot)
    if b.smooth_dx * b.smooth_dx + b.smooth_dy * b.smooth_dy < 1e-10:
        b.smooth_dx, b.smooth_dy = tx, ty
        return tx, ty
    alpha = min(1.0, 12.0 * dt)
    nx = b.smooth_dx + (tx - b.smooth_dx) * alpha
    ny = b.smooth_dy + (ty - b.smooth_dy) * alpha
    nd = math.hypot(nx, ny)
    if nd < 1e-8:
        b.smooth_dx, b.smooth_dy = tx, ty
        return tx, ty
    b.smooth_dx, b.smooth_dy = nx / nd, ny / nd
    return b.smooth_dx, b.smooth_dy


def _nearest_downed_teammate(bot: Combatant, combatants: list[Combatant]) -> Combatant | None:
    best: Combatant | None = None
    best_d = 1e18
    for c in combatants:
        if c is bot or c.team != "Survivors" or not c.downed:
            continue
        d = _flat_dist(bot, c)
        if d < best_d:
            best_d = d
            best = c
    return best


def _brain(c: Combatant) -> BotBrain:
    bid = c.internal_id
    if bid not in _bot_state:
        _bot_state[bid] = BotBrain(
            next_path_t=0.0,
            next_ability_t=random.uniform(0.5, 2.5),
            next_survivor_ability_t=random.uniform(0.2, 0.85),
            wander_angle=random.random() * math.tau,
        )
    return _bot_state[bid]


def steer_survivor(
    bot: Combatant,
    killer: Combatant | None,
    now: float,
    dt: float,
    round_end_unix: float,
    combatants: list[Combatant],
) -> tuple[float, float]:
    """
    Flees killer when close (exits closed) or blends flee/exit when open.
    Exit availability follows match_service (timer within last ESCAPE_OPENS_AT_SECONDS_REMAINING seconds).
    When exits are closed and killer is beyond flee radius, patrols interior instead of hugging map edges.
    """
    if killer is None:
        escape_open = False
    else:
        escape_open = exits_available_for_escape(now, round_end_unix, killer, combatants)
    if bot.char_id == "Eggman":
        healing_metal = _nearest_healing_metal_sonic(bot, combatants, now)
        killer_near = killer is not None and killer.alive() and _flat_dist(bot, killer) < SURVIVOR_FLEE_RADIUS * 0.85
        if healing_metal is not None and not killer_near:
            rx, ry = pathfind_direction(bot.x, bot.y, healing_metal.x, healing_metal.y, bot.radius)
            return _smoothed_steer(bot, rx, ry, dt)
    if bot.char_id == "Cream":
        heal_target = _cream_heal_target(bot, combatants)
        killer_near = killer is not None and killer.alive() and _flat_dist(bot, killer) < SURVIVOR_FLEE_RADIUS * 0.9
        if heal_target is not None and not killer_near:
            rx, ry = pathfind_direction(bot.x, bot.y, heal_target.x, heal_target.y, bot.radius)
            return _smoothed_steer(bot, rx, ry, dt)
    down_ally = _nearest_downed_teammate(bot, combatants)
    if (
        down_ally is not None
        and killer is not None
        and killer.alive()
        and _flat_dist(bot, killer) > SURVIVOR_FLEE_RADIUS * 1.06
    ):
        rx, ry = pathfind_direction(bot.x, bot.y, down_ally.x, down_ally.y, bot.radius)
        return _smoothed_steer(bot, rx, ry, dt)
    if killer is not None and killer.alive():
        stun_range = _ready_stun_engage_range(bot, now)
        if stun_range is not None:
            # Stun-capable bots actively close distance when a stun is ready.
            if _flat_dist(bot, killer) > stun_range:
                rx, ry = pathfind_direction(bot.x, bot.y, killer.x, killer.y, bot.radius)
                return _smoothed_steer(bot, rx, ry, dt)
    rx = ry = 0.0
    if not escape_open:
        if killer and killer.alive():
            dx = bot.x - killer.x
            dy = bot.y - killer.y
            d = math.hypot(dx, dy) or 1.0
            if d < SURVIVOR_FLEE_RADIUS:
                fx, fy = dx / d, dy / d
                m = SURVIVOR_INTERIOR_GOAL_MARGIN
                gx = _clamp(bot.x + fx * 480.0, m, ARENA_W - m)
                gy = _clamp(bot.y + fy * 480.0, m, ARENA_H - m)
                rx, ry = pathfind_direction(bot.x, bot.y, gx, gy, bot.radius)
            else:
                rx, ry = _path_toward_interior_patrol(bot, now)
    elif not killer or not killer.alive():
        rx, ry = _path_toward_nearest_exit(bot)
    else:
        dx = bot.x - killer.x
        dy = bot.y - killer.y
        dist = math.hypot(dx, dy) or 1.0
        if dist < SURVIVOR_FLEE_RADIUS:
            ex, ey = _nearest_exit_goal(bot)
            fx, fy = dx / dist, dy / dist
            m = SURVIVOR_INTERIOR_GOAL_MARGIN
            gx = _clamp(bot.x + fx * 0.75 * 420.0 + (ex - bot.x) * 0.25, m, ARENA_W - m)
            gy = _clamp(bot.y + fy * 0.75 * 420.0 + (ey - bot.y) * 0.25, m, ARENA_H - m)
            rx, ry = pathfind_direction(bot.x, bot.y, gx, gy, bot.radius)
        else:
            rx, ry = _path_toward_nearest_exit(bot)
    return _smoothed_steer(bot, rx, ry, dt)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _nearest_exit_goal(bot: Combatant) -> tuple[float, float]:
    rects = get_exit_rects()
    if not rects:
        return bot.x, bot.y
    best_d = 1e18
    cx = cy = 0.0
    for r in rects:
        tx = r.x + r.width / 2
        ty = r.y + r.height / 2
        d = (tx - bot.x) ** 2 + (ty - bot.y) ** 2
        if d < best_d:
            best_d = d
            cx, cy = tx, ty
    return cx, cy


def _path_toward_nearest_exit(bot: Combatant) -> tuple[float, float]:
    cx, cy = _nearest_exit_goal(bot)
    return pathfind_direction(bot.x, bot.y, cx, cy, bot.radius)


def _path_toward_interior_patrol(bot: Combatant, now: float) -> tuple[float, float]:
    """
    Roam near map center when exits are closed and the killer is not in chase range.
    Avoids steering toward perimeter goals that hug the arena edge.
    """
    b = _brain(bot)
    m = SURVIVOR_INTERIOR_GOAL_MARGIN
    if now >= b.next_path_t:
        b.next_path_t = now + random.uniform(1.1, 2.6)
        b.wander_angle = random.random() * math.tau
    cx = ARENA_W * 0.5 + math.cos(b.wander_angle) * (ARENA_W * 0.22)
    cy = ARENA_H * 0.5 + math.sin(b.wander_angle) * (ARENA_H * 0.20)
    gx = _clamp(cx, m, ARENA_W - m)
    gy = _clamp(cy, m, ARENA_H - m)
    return pathfind_direction(bot.x, bot.y, gx, gy, bot.radius)


def _nearest_healing_metal_sonic(bot: Combatant, combatants: list[Combatant], now: float) -> Combatant | None:
    best: Combatant | None = None
    best_d = 1e18
    for c in combatants:
        if c is bot or c.team != "Survivors" or c.char_id != "MetalSonic":
            continue
        if not c.alive() or c.escaped:
            continue
        if c.metal_self_heal_until <= now:
            continue
        d = (c.x - bot.x) ** 2 + (c.y - bot.y) ** 2
        if d < best_d:
            best_d = d
            best = c
    return best


def steer_executioner(
    bot: Combatant,
    survivors: list[Combatant],
    now: float,
    dt: float,
) -> tuple[float, float]:
    """Chase nearest living survivor."""
    best: Combatant | None = None
    best_d = 1e18
    for s in survivors:
        if s is bot or s.team != "Survivors":
            continue
        if not s.alive() or s.escaped:
            continue
        d = (s.x - bot.x) ** 2 + (s.y - bot.y) ** 2
        if d < best_d:
            best_d = d
            best = s
    if not best:
        return _smoothed_steer(bot, 0.0, 0.0, dt)
    rx, ry = pathfind_direction(bot.x, bot.y, best.x, best.y, bot.radius)
    return _smoothed_steer(bot, rx, ry, dt)


def should_try_ability(bot: Combatant, now: float) -> bool:
    b = _brain(bot)
    if now >= b.next_ability_t:
        b.next_ability_t = now + random.uniform(1.8, 4.0)
        return True
    return False


def should_try_survivor_ability(bot: Combatant, now: float) -> bool:
    """Faster cadence than executioner bots — survivor bots pressure with stuns / heals."""
    b = _brain(bot)
    if now >= b.next_survivor_ability_t:
        b.next_survivor_ability_t = now + random.uniform(0.75, 1.65)
        return True
    return False


def _flat_dist(a: Combatant, b: Combatant) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def choose_survivor_bot_ability_index(
    bot: Combatant,
    killer: Combatant,
    combatants: list[Combatant],
) -> int:
    """
    Prefer abilities that stun the killer when in range; Cream prioritizes healing allies.
    Falls back to 0 when killer absent or character has a single relevant mode.
    """
    if not killer.alive() or killer.escaped:
        return 0

    d = _flat_dist(bot, killer)
    cid = bot.char_id

    if cid == "Cream":
        for t in combatants:
            if t.team != "Survivors" or not t.alive() or t.escaped:
                continue
            if t.health < t.max_health * 0.92:
                return 0
        return 1

    if cid == "Amy":
        if d <= 70.0:
            return 0
        if d <= 220.0:
            return 1
        return 0

    if cid == "Knuckles":
        if d <= 72.0:
            return 1
        if d <= 118.0:
            return 0
        return 0

    if cid == "Tails":
        if d <= 400.0:
            return 0
        return 1

    if cid == "Eggman":
        if d <= 115.0:
            return 1
        return 0

    if cid == "MetalSonic":
        if bot.health < bot.max_health * 0.42:
            return 0
        if d <= 340.0:
            return 1
        return 0

    if cid == "Sonic":
        if d <= 270.0:
            return 1
        return 0

    return 0


def _ready_stun_engage_range(bot: Combatant, now: float) -> float | None:
    d = char_registry.get_definition(bot.char_id)
    if not d:
        return None
    best = 0.0
    for ab in d.get("abilities", ()):
        key = ab.get("server_behavior_key")
        if key not in _STUN_BEHAVIOR_KEYS:
            continue
        aid = ab.get("id")
        if not aid:
            continue
        cd = float(ab.get("cooldown") or 0.0)
        last = bot.ability_cooldowns.get(aid, -1e9)
        if cd > 0 and now - last < cd:
            continue
        rng = float(ab.get("range") or 0.0)
        if rng <= 0:
            rng = _STUN_DEFAULT_RANGES.get(key, 120.0)
        best = max(best, rng)
    return best if best > 0 else None


def should_force_survivor_stun_attempt(bot: Combatant, killer: Combatant, now: float) -> bool:
    if not killer.alive() or killer.escaped:
        return False
    stun_range = _ready_stun_engage_range(bot, now)
    if stun_range is None:
        return False
    return _flat_dist(bot, killer) <= stun_range + bot.radius + killer.radius + 8.0


def should_force_cream_heal_attempt(bot: Combatant, combatants: list[Combatant], now: float) -> bool:
    if bot.char_id != "Cream" or not bot.alive() or bot.escaped:
        return False
    last = bot.ability_cooldowns.get("chao_heal", -1e9)
    if now - last < 30.0:
        return False
    return _cream_heal_target(bot, combatants) is not None


def _cream_heal_target(bot: Combatant, combatants: list[Combatant]) -> Combatant | None:
    """Prefer injured human survivor, else nearest injured ally."""
    human_injured: Combatant | None = None
    nearest: Combatant | None = None
    best_d = 1e18
    for t in combatants:
        if t is bot or t.team != "Survivors" or not t.alive() or t.escaped:
            continue
        if t.health >= t.max_health * 0.96:
            continue
        if t.is_human:
            human_injured = t
            break
        d = (t.x - bot.x) ** 2 + (t.y - bot.y) ** 2
        if d < best_d:
            best_d = d
            nearest = t
    return human_injured if human_injured is not None else nearest
