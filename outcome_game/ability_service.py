from __future__ import annotations

import math
import random
import time

from outcome_game.constants import (
    CREAM_HEAL_DURATION_SECONDS,
    CREAM_HEAL_PER_SECOND,
    AMY_HAMMER_SWING_SECONDS,
    KILLER_MELEE_DAMAGE,
    KILLER_MELEE_REACH,
    METAL_CHARGE_DURATION_SECONDS,
    METAL_CHARGE_DAMAGE_REDUCTION_FLAT,
    METAL_CHARGE_HP_COST,
    METAL_CHARGE_KILLER_STUN_SECONDS,
    METAL_EGGMAN_HEAL_NEARBY_MULT,
    METAL_EGGMAN_HEAL_NEARBY_RADIUS,
    METAL_SELF_HEAL_DURATION_SECONDS,
    METAL_SELF_HEAL_PER_SECOND,
    AMY_HAMMER_STUN_SECONDS,
    AMY_HAMMER_THROW_MAX_SECONDS,
    AMY_HAMMER_THROW_SPEED,
    EGGMAN_SHIELD_STUN_SECONDS,
    EGGMAN_SHIELD_DURATION_SECONDS,
    EGGMAN_SPEED_BOOST_DURATION_SECONDS,
    EGGMAN_SPEED_BOOST_MULT,
    KOLLOSIOS_BASIC_GRAB_CHANCE,
    KNUCKLES_BLOCK_GRAB_GUARD_SECONDS,
    KNUCKLES_PUNCH_CHARGE_DAMAGE_MULT,
    KNUCKLES_PUNCH_RELEASE_IFRAMES_SECONDS,
)
from outcome_game.entities import Combatant
from outcome_game.hit_reaction import apply_survivor_hit_speed_boost
from outcome_game.last_man_standing import last_man_incoming_damage_multiplier
from outcome_game.x2011_rage import apply_executioner_stun_from_now, rage_damage_multiplier

# Ability range checks use same units as world (pixels).


def _flat_dist(a: "Combatant", b: "Combatant") -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _mark_stun_hitbox(user: Combatant, now: float, reach: float) -> None:
    """Short-lived debug overlay for survivor stun cast range."""
    user.stun_hitbox_until = max(user.stun_hitbox_until, now + 0.24)
    user.stun_hitbox_radius = max(0.0, reach + user.radius)


def try_use_ability(
    user: Combatant,
    ability_index: int,
    now: float,
    combatants: list[Combatant],
    killer: Combatant | None,
) -> bool:
    """Returns True if ability fired. Mutates user cooldowns and world state."""
    from outcome_game.character_definitions.registry import get_definition

    if user.dead or user.escaped or now < user.stunned_until:
        return False
    if user.grabbed_by is not None:
        return False
    if user.char_id == "X2011" and user.x2011_grab_victim is not None:
        return False
    if user.held_by_kollosios_charge:
        return False
    if user.held_by_kollosios_basic_grab:
        return False
    if user.char_id == "Kollosios" and user.kollosios_charge_until > now:
        return False
    if user.char_id == "Kollosios" and user.kollosios_basic_grab_victim is not None:
        return False
    d = get_definition(user.char_id)
    if not d or ability_index < 0 or ability_index >= len(d["abilities"]):
        return False
    ab = d["abilities"][ability_index]
    aid = ab["id"]
    cd = float(ab["cooldown"]) if ab.get("cooldown") is not None else 0.0
    if cd > 0.0 and aid in user.ability_cooldowns and now - user.ability_cooldowns[aid] < cd:
        return False

    key = ab["server_behavior_key"]
    ok = _apply_behavior(key, user, ab, now, combatants, killer)
    if ok and cd > 0.0:
        user.ability_cooldowns[aid] = now
    return ok


def tick_healing_auras(combatants: list[Combatant], now: float, dt: float) -> None:
    """Cream: heal other survivors inside aura at CREAM_HEAL_PER_SECOND while aura is active."""
    for c in combatants:
        if c.char_id != "Cream" or not c.alive() or c.escaped:
            continue
        if c.healing_aura_until <= now:
            continue
        r = c.healing_aura_range
        for t in combatants:
            if t is c or t.team != "Survivors" or not t.alive() or t.escaped:
                continue
            if _flat_dist(c, t) <= r + c.radius + t.radius:
                t.health = min(t.max_health, t.health + CREAM_HEAL_PER_SECOND * dt)


def tick_metal_self_heal(combatants: list[Combatant], now: float, dt: float) -> None:
    """Metal Sonic: regenerate self while repair is active."""
    for c in combatants:
        if c.char_id != "MetalSonic" or not c.alive() or c.escaped:
            continue
        if c.metal_self_heal_until <= now:
            c.metal_self_heal_last_flash_sec = -1
            continue
        heal_per_sec = METAL_SELF_HEAL_PER_SECOND
        for ally in combatants:
            if ally is c or ally.char_id != "Eggman" or ally.team != "Survivors":
                continue
            if not ally.alive() or ally.escaped:
                continue
            if _flat_dist(c, ally) <= METAL_EGGMAN_HEAL_NEARBY_RADIUS + c.radius + ally.radius:
                heal_per_sec *= METAL_EGGMAN_HEAL_NEARBY_MULT
                break
        c.health = min(c.max_health, c.health + heal_per_sec * dt)
        sec = int(now)
        if sec != c.metal_self_heal_last_flash_sec:
            c.metal_self_heal_last_flash_sec = sec
            c.ability_flash_until = max(c.ability_flash_until, now + 0.16)


def process_metal_charge_grab(combatants: list[Combatant], killer: Combatant, now: float) -> None:
    """During charge window, first collision with killer stuns them and costs HP."""
    if not killer.alive() or killer.escaped:
        return
    for c in combatants:
        if c.char_id != "MetalSonic" or not c.alive() or c.escaped:
            continue
        if c.metal_charge_until <= now or c.metal_charge_grab_used:
            continue
        if _flat_dist(c, killer) > c.radius + killer.radius + 10.0:
            continue
        apply_executioner_stun_from_now(killer, now, METAL_CHARGE_KILLER_STUN_SECONDS, combatants)
        c.health -= METAL_CHARGE_HP_COST
        if c.health <= 0:
            c.health = 0.0
            c.dead = True
        c.metal_charge_grab_used = True


def tick_amy_hammer_throw(combatants: list[Combatant], killer: Combatant | None, now: float, dt: float) -> None:
    """Move Amy throw projectile and stun killer on first contact."""
    if killer is None or not killer.alive() or killer.escaped:
        for c in combatants:
            if c.char_id == "Amy":
                c.amy_hammer_throw_active = False
        return
    for c in combatants:
        if c.char_id != "Amy" or not c.alive() or c.escaped:
            continue
        if not c.amy_hammer_throw_active:
            continue
        if now >= c.amy_hammer_throw_until:
            c.amy_hammer_throw_active = False
            continue
        c.amy_hammer_throw_x += c.amy_hammer_throw_vx * dt
        c.amy_hammer_throw_y += c.amy_hammer_throw_vy * dt
        if c.amy_hammer_throw_hit:
            continue
        dx = c.amy_hammer_throw_x - killer.x
        dy = c.amy_hammer_throw_y - killer.y
        hit_r = killer.radius + c.radius * 0.65
        if dx * dx + dy * dy <= hit_r * hit_r:
            apply_executioner_stun_from_now(killer, now, AMY_HAMMER_STUN_SECONDS, combatants)
            c.amy_hammer_throw_hit = True
            c.amy_hammer_throw_active = False


def _apply_behavior(
    key: str,
    user: Combatant,
    ab: dict,
    now: float,
    combatants: list[Combatant],
    killer: Combatant | None,
) -> bool:
    rng = ab.get("range") or 0.0

    if key == "killer_basic_hit":
        if user.team != "Executioners":
            return False
        reach = float(rng) if rng and rng > 0 else KILLER_MELEE_REACH
        if user.char_id == "Kollosios":
            candidates = _survivors_in_melee_reach(user, combatants, reach, time.monotonic())
            if not candidates:
                return False
            if random.random() < KOLLOSIOS_BASIC_GRAB_CHANCE:
                from outcome_game.kollosios_basic_grab import try_begin_basic_grab

                try_begin_basic_grab(user, random.choice(candidates), now)
                return True
        target = _nearest_survivor(user, combatants)
        if not target:
            return False
        if _flat_dist(user, target) > reach + user.radius + target.radius:
            return False
        return melee_attack(user, target, now, reach, KILLER_MELEE_DAMAGE, combatants)

    if key == "cream_heal_aura":
        if user.char_id != "Cream":
            return False
        r = float(rng) if rng and rng > 0 else 140.0
        user.healing_aura_until = now + CREAM_HEAL_DURATION_SECONDS
        user.healing_aura_range = r
        return True

    if key == "metal_self_heal":
        if user.char_id != "MetalSonic":
            return False
        if user.metal_charge_until > now:
            return False
        if user.metal_self_heal_until > now:
            return False
        user.metal_self_heal_until = now + METAL_SELF_HEAL_DURATION_SECONDS
        user.metal_self_heal_last_flash_sec = -1
        return True

    if key == "metal_killer_charge":
        if user.char_id != "MetalSonic":
            return False
        if user.metal_charge_until > now:
            return False
        # Charge is an active commit action; cancel self-repair lockout so movement works immediately.
        user.metal_self_heal_until = 0.0
        user.metal_charge_until = now + METAL_CHARGE_DURATION_SECONDS
        user.metal_charge_grab_used = False
        return True

    if key == "survivor_dash":
        sp = user.base_walk_speed * 2.8
        user.dash_until = now + 0.28
        user.dash_vx = user.facing_x * sp
        user.dash_vy = user.facing_y * sp
        return True

    if key == "survivor_speed_aura":
        user.speed_mult_until = now + 4.0
        user.speed_mult = 1.35
        return True

    if key == "eggman_speed_boost":
        if user.char_id != "Eggman":
            return False
        user.speed_mult_until = now + EGGMAN_SPEED_BOOST_DURATION_SECONDS
        user.speed_mult = EGGMAN_SPEED_BOOST_MULT
        return True

    if key == "eggman_electric_shield":
        if user.char_id != "Eggman":
            return False
        user.eggman_shield_until = now + EGGMAN_SHIELD_DURATION_SECONDS
        return True

    if key == "tails_hand_cannon":
        from outcome_game.tails_cannon import try_start_hand_cannon

        return try_start_hand_cannon(user, now)

    if key == "x2011_grab_charge":
        from outcome_game.x2011_grab import try_start_grab_charge

        return try_start_grab_charge(user, now)

    if key == "kollosios_grab_charge":
        from outcome_game.kollosios_charge import try_start_kollosios_charge

        return try_start_kollosios_charge(user, now)

    if key == "survivor_armor":
        user.armor_until = now + 5.0
        return True

    if key == "survivor_stun_pulse":
        reach = float(rng) if rng and rng > 0 else 120.0
        _mark_stun_hitbox(user, now, reach)
        if killer and killer.alive() and not killer.escaped:
            if _flat_dist(user, killer) <= reach + killer.radius:
                apply_executioner_stun_from_now(killer, now, 1.2, combatants)
                return True
        return False

    if key == "amy_hammer_melee":
        if user.char_id != "Amy" or not killer or not killer.alive() or killer.escaped:
            return False
        reach = float(rng) if rng and rng > 0 else 58.0
        _mark_stun_hitbox(user, now, reach)
        user.amy_hammer_swing_until = now + AMY_HAMMER_SWING_SECONDS
        if _flat_dist(user, killer) > reach + user.radius + killer.radius:
            return False
        apply_executioner_stun_from_now(killer, now, AMY_HAMMER_STUN_SECONDS, combatants)
        return True

    if key == "amy_hammer_throw":
        if user.char_id != "Amy" or not killer or not killer.alive() or killer.escaped:
            return False
        reach = float(rng) if rng and rng > 0 else 220.0
        _mark_stun_hitbox(user, now, reach)
        d = math.hypot(user.facing_x, user.facing_y) or 1.0
        user.amy_hammer_swing_until = now + AMY_HAMMER_SWING_SECONDS
        user.amy_hammer_throw_active = True
        user.amy_hammer_throw_until = now + AMY_HAMMER_THROW_MAX_SECONDS
        user.amy_hammer_throw_x = user.x + (user.facing_x / d) * (user.radius + 12.0)
        user.amy_hammer_throw_y = user.y + (user.facing_y / d) * (user.radius + 12.0)
        user.amy_hammer_throw_vx = (user.facing_x / d) * AMY_HAMMER_THROW_SPEED
        user.amy_hammer_throw_vy = (user.facing_y / d) * AMY_HAMMER_THROW_SPEED
        user.amy_hammer_throw_hit = False
        return True

    if key == "survivor_lunge_punch":
        # Forward lunge; if killer is in range at cast time, also apply stun.
        if not killer or not killer.alive() or killer.escaped:
            return False
        user.knuckles_punch_armed = False
        reach = float(rng) if rng and rng > 0 else 100.0
        _mark_stun_hitbox(user, now, reach)
        face_d = math.hypot(user.facing_x, user.facing_y) or 1.0
        sp = user.base_walk_speed * 3.0
        user.dash_until = now + 0.25
        user.dash_vx = (user.facing_x / face_d) * sp
        user.dash_vy = (user.facing_y / face_d) * sp
        user.invulnerable_until = max(user.invulnerable_until, now + KNUCKLES_PUNCH_RELEASE_IFRAMES_SECONDS)
        user.ability_flash_until = max(user.ability_flash_until, now + 0.18)
        if _flat_dist(user, killer) <= reach + user.radius + killer.radius:
            apply_executioner_stun_from_now(killer, now, 3.0, combatants)
        return True

    if key == "survivor_block_stun":
        # Melee block: stuns killer for 2s if in range (no dash).
        user.knuckles_block_until = max(user.knuckles_block_until, now + KNUCKLES_BLOCK_GRAB_GUARD_SECONDS)
        melee = float(rng) if rng and rng > 0 else 70.0
        _mark_stun_hitbox(user, now, melee)
        user.ability_flash_until = max(user.ability_flash_until, now + 0.18)
        if killer and killer.alive() and not killer.escaped and _flat_dist(user, killer) <= melee + user.radius + killer.radius:
            apply_executioner_stun_from_now(killer, now, 2.0, combatants)
        return True

    if key == "killer_lunge":
        if rng <= 0:
            return False
        # Lunge toward nearest survivor in front cone or nearest
        target = _nearest_survivor(user, combatants)
        if not target:
            return False
        if _flat_dist(user, target) > rng * 1.5:
            return False
        dx = target.x - user.x
        dy = target.y - user.y
        dist = math.hypot(dx, dy) or 1.0
        sp = user.base_walk_speed * 3.2
        user.dash_until = now + 0.22
        user.dash_vx = (dx / dist) * sp
        user.dash_vy = (dy / dist) * sp
        return True

    if key == "killer_slow_aura":
        for c in combatants:
            if c.team == "Survivors" and c.alive() and not c.escaped:
                if _flat_dist(user, c) <= (rng if rng > 0 else 180):
                    c.slowed_until = max(c.slowed_until, now + 3.5)
                    c.slow_mult = 0.55
        return True

    if key == "killer_grab":
        target = _nearest_survivor(user, combatants)
        if not target or _flat_dist(user, target) > (rng if rng > 0 else 130):
            return False
        target.stunned_until = max(target.stunned_until, now + 1.5)
        # Pull slightly toward killer
        dx = user.x - target.x
        dy = user.y - target.y
        dist = math.hypot(dx, dy) or 1.0
        pull = 60.0
        target.x += (dx / dist) * pull * 0.1
        target.y += (dy / dist) * pull * 0.1
        return True

    if key == "sonic_peelout":
        from outcome_game.sonic_abilities import try_start_peelout

        return try_start_peelout(user, now, combatants)

    if key == "sonic_drop_dash":
        from outcome_game.sonic_abilities import try_start_drop_dash

        if not killer:
            return False
        return try_start_drop_dash(user, killer, now)

    return False


def _survivors_in_melee_reach(
    killer: Combatant,
    combatants: list[Combatant],
    reach: float,
    now: float,
) -> list[Combatant]:
    out: list[Combatant] = []
    for s in combatants:
        if s.team != "Survivors" or not s.alive() or s.escaped:
            continue
        if s.grabbed_by is not None:
            continue
        if s.held_by_kollosios_charge:
            continue
        if s.held_by_kollosios_basic_grab:
            continue
        if s.char_id == "Knuckles" and s.knuckles_block_until > now:
            # Knuckles block can deny grab attempts while active.
            continue
        if _flat_dist(killer, s) <= reach + killer.radius + s.radius:
            out.append(s)
    return out


def _nearest_survivor(killer: Combatant, combatants: list[Combatant]) -> Combatant | None:
    best: Combatant | None = None
    best_d = 1e18
    for c in combatants:
        if c.team != "Survivors" or not c.alive() or c.escaped:
            continue
        d = _flat_dist(killer, c)
        if d < best_d:
            best_d = d
            best = c
    return best


def melee_attack(
    attacker: Combatant,
    target: Combatant,
    now: float,
    reach: float,
    damage: float,
    combatants: list[Combatant],
) -> bool:
    if not attacker.alive() or not target.alive() or target.escaped:
        return False
    if now < attacker.stunned_until:
        return False
    if _flat_dist(attacker, target) > reach + attacker.radius + target.radius:
        return False
    if target.char_id == "Knuckles" and now < target.knuckles_block_until:
        return True
    if now < target.invulnerable_until:
        return True
    if (
        target.char_id == "Eggman"
        and now < target.eggman_shield_until
        and attacker.team == "Executioners"
    ):
        apply_executioner_stun_from_now(attacker, now, EGGMAN_SHIELD_STUN_SECONDS, combatants)
    armor = 1.0
    if now < target.armor_until:
        armor = 0.65
    dmg = damage * rage_damage_multiplier(attacker, now, combatants)
    if target.char_id == "Knuckles" and target.knuckles_punch_armed:
        dmg *= KNUCKLES_PUNCH_CHARGE_DAMAGE_MULT
    if target.char_id == "MetalSonic" and target.metal_charge_until > now:
        dmg = max(0.0, dmg - METAL_CHARGE_DAMAGE_REDUCTION_FLAT)
    lms = last_man_incoming_damage_multiplier(target, combatants)
    target.health -= dmg * armor * lms
    apply_survivor_hit_speed_boost(target, now)
    if target.health <= 0:
        target.health = 0
        target.dead = True
    return True
