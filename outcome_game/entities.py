from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field

import pygame

from outcome_game.constants import METAL_SONIC_HEAL_CAP


@dataclass
class Combatant:
    """Top-down actor (human or bot). Positions are in world space (pixels)."""

    char_id: str
    team: str  # "Survivors" | "Executioners"
    is_bot: bool
    is_human: bool
    x: float = 0.0
    y: float = 0.0
    radius: float = 22.0
    health: float = 100.0
    max_health: float = 100.0
    base_walk_speed: float = 200.0
    facing_x: float = 1.0
    facing_y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    escaped: bool = False
    dead: bool = False
    downed: bool = False
    revive_used: bool = False
    revive_progress: float = 0.0
    metal_death_burst_until: float = 0.0
    metal_death_origin_x: float = 0.0
    metal_death_origin_y: float = 0.0
    internal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    # Buffs / debuffs: end time (monotonic seconds)
    armor_until: float = 0.0
    speed_mult_until: float = 0.0
    speed_mult: float = 1.0
    stunned_until: float = 0.0
    slowed_until: float = 0.0
    slow_mult: float = 1.0
    dash_until: float = 0.0
    dash_vx: float = 0.0
    dash_vy: float = 0.0
    invulnerable_until: float = 0.0
    knuckles_punch_armed: bool = False
    knuckles_block_until: float = 0.0
    ability_flash_until: float = 0.0
    stun_hitbox_until: float = 0.0
    stun_hitbox_radius: float = 0.0
    stun_splash_until: float = 0.0
    stun_immunity_until: float = 0.0
    stun_active_last_tick: bool = False
    exit_zone_time: float = 0.0  # consecutive seconds in exit zone
    ability_cooldowns: dict[str, float] = field(default_factory=dict)
    # Sonic only — Peelout / Drop Dash (see sonic_abilities.py)
    peelout_phase: str = "none"  # none | windup | carry
    peelout_phase_end: float = 0.0
    peelout_partner: Combatant | None = None
    peelout_vx: float = 0.0
    peelout_vy: float = 0.0
    carried_by_peelout: bool = False
    drop_dash_end: float = 0.0
    drop_dash_speed: float = 0.0
    drop_dash_bumps: int = 0
    drop_dash_hit_lock_until: float = 0.0
    # Last bump: freeze until this time, then resolve bounce (see sonic_abilities.py).
    drop_dash_finale_until: float = 0.0
    sonic_trail: list[tuple[float, float, float]] = field(default_factory=list)
    # Cream — healing aura (see ability_service.tick_healing_auras)
    healing_aura_until: float = 0.0
    healing_aura_range: float = 0.0
    # Metal Sonic — self repair + killer charge (ability_service)
    metal_self_heal_until: float = 0.0
    metal_self_heal_last_flash_sec: int = -1
    metal_charge_until: float = 0.0
    metal_charge_windup_until: float = 0.0
    metal_charge_grab_used: bool = False
    # Metal Sonic — charge carries X2011 (see metal_charge_carry.py)
    metal_charge_carry_target: Combatant | None = None
    metal_beatup_anim_until: float = 0.0
    metal_charge_debris: list[tuple[float, float, float, float, float, tuple[int, int, int]]] = field(
        default_factory=list
    )
    metal_carry_hp_drain_bank: float = 0.0
    metal_carry_hp_drained_total: float = 0.0
    metal_charge_trail: list[tuple[float, float, float]] = field(default_factory=list)
    # Executioner — grabbed by Metal's charge (only X2011 in practice)
    held_by_metal_charge_carrier: Combatant | None = None
    # Eggman — electric shield (reflect stun on killer hit; see melee_attack)
    eggman_shield_until: float = 0.0
    # Amy — hammer visuals + throw projectile (ability_service / hud)
    amy_hammer_swing_until: float = 0.0
    amy_hammer_throw_active: bool = False
    amy_hammer_throw_until: float = 0.0
    amy_hammer_throw_x: float = 0.0
    amy_hammer_throw_y: float = 0.0
    amy_hammer_throw_vx: float = 0.0
    amy_hammer_throw_vy: float = 0.0
    amy_hammer_throw_hit: bool = False
    # Tails — hand cannon (tails_cannon.py)
    tails_cannon_phase: str = "none"  # none | charging | beaming
    tails_cannon_end: float = 0.0
    tails_cannon_beam_dx: float = 1.0
    tails_cannon_beam_dy: float = 0.0
    tails_cannon_contact_bank: float = 0.0
    # 2011X grab charge / survivor grabbed (x2011_grab.py)
    x2011_grab_charge_until: float = 0.0
    x2011_grab_victim: Combatant | None = None
    x2011_grab_until: float = 0.0
    x2011_charge_trail: list[tuple[float, float, float]] = field(default_factory=list)
    x2011_charge_warn_count: int = 0
    x2011_stun_count: int = 0
    x2011_rage_until: float = 0.0
    grabbed_by: Combatant | None = None
    grab_break_progress: float = 0.0
    # Kollosios multi-grab charge (kollosios_charge.py)
    kollosios_charge_until: float = 0.0
    kollosios_grabbed_survivors: list = field(default_factory=list)
    held_by_kollosios_charge: bool = False
    # Kollosios — basic-hit random grab (kollosios_basic_grab.py)
    kollosios_basic_grab_until: float = 0.0
    kollosios_basic_grab_victim: Combatant | None = None
    kollosios_basic_grab_start: float = 0.0
    kollosios_basic_grab_last_pulse_sec: int = 0
    held_by_kollosios_basic_grab: bool = False

    def pos(self) -> pygame.Vector2:
        return pygame.Vector2(self.x, self.y)

    def dist_sq_to(self, other: Combatant) -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        return dx * dx + dy * dy

    def alive(self) -> bool:
        return not self.dead and self.health > 0


def heal_ceiling_for(c: Combatant) -> float:
    """Maximum HP that healing can restore (Metal Sonic uses max pool but heal cap)."""
    if c.char_id == "MetalSonic":
        return min(c.max_health, METAL_SONIC_HEAL_CAP)
    return c.max_health


def clamp_to_arena(c: Combatant, arena_w: float, arena_h: float) -> None:
    c.x = max(c.radius, min(arena_w - c.radius, c.x))
    c.y = max(c.radius, min(arena_h - c.radius, c.y))


def separate_circles(a: Combatant, b: Combatant) -> None:
    """Push apart if overlapping (equal mass)."""
    dx = b.x - a.x
    dy = b.y - a.y
    dist = math.hypot(dx, dy)
    min_dist = a.radius + b.radius
    if dist < 1e-6 or dist >= min_dist:
        return
    overlap = (min_dist - dist) * 0.5
    nx = dx / dist
    ny = dy / dist
    a.x -= nx * overlap
    a.y -= ny * overlap
    b.x += nx * overlap
    b.y += ny * overlap
