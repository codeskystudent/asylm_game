"""World and tuning constants."""

from __future__ import annotations

import pygame

# World size (pixels) — wall layouts live in arena_maps.py (scaled to this size)
ARENA_W = 3600.0
ARENA_H = 2400.0

# Scales walk speeds (character defs), peelout/metal charge speeds, and knockback/throw velocities together.
GLOBAL_MOVEMENT_SPEED_MULT = 2.0

# Exit gates: 2–3 rects per match (see match_service.reset_exit_rects)

# Survivors per match (human + bots fill these slots; one executioner extra).
NUM_SURVIVOR_SLOTS = 6

# Round length when the roster has no Sonic/Knuckles LMS audio (see lms_audio)
DEFAULT_ROUND_SECONDS = 180.0
# Legacy default (unused for new matches; kept for reference)
ROUND_SECONDS = 300.0
# Exit zones unlock when the round timer has at most this many seconds left
ESCAPE_OPENS_AT_SECONDS_REMAINING = 80.0

# Survivor down / revive (Metal Sonic skips down — explodes on elimination)
REVIVE_CHANNEL_SECONDS = 2.75
REVIVE_HP_FRACTION = 0.52
METAL_DEATH_EXPLOSION_RADIUS = 340.0
METAL_DEATH_STUN_X2011_SECONDS = 6.0
METAL_DEATH_BURST_VISUAL_SECONDS = 1.85

# PC controls: hold Left Shift while moving (WASD) for a modest speed boost
PC_SPRINT_SPEED_MULT = 1.32

# Last survivor alive (not escaped): walk speed mult — tuned vs executioner base speeds so LMS+sprint
# does not exceed the slowest killer (see character_definitions/executioners/*.py)
LAST_MAN_STANDING_SPEED_MULT = 1.06

# Melee
KILLER_MELEE_REACH = 55.0
KILLER_MELEE_DAMAGE = 38.0
KILLER_ATTACK_COOLDOWN = 0.85

# Sonic — Peelout / Drop Dash
PEELOUT_WINDUP_SECONDS = 3.0
PEELOUT_CARRY_SECONDS = 8.0
PEELOUT_SPEED = 445.0 * GLOBAL_MOVEMENT_SPEED_MULT
DROP_DASH_MAX_SECONDS = 10.0
DROP_DASH_MAX_BUMPS = 3
DROP_DASH_KILLER_STUN_SECONDS = 1.0
DROP_DASH_HIT_LOCK_SECONDS = 0.22
DROP_DASH_BOUNCE_DISTANCE = 52.0 * GLOBAL_MOVEMENT_SPEED_MULT
# Final bump: Sonic + killer hold position together while Sonic flashes, then bounce apart.
DROP_DASH_FINALE_SECONDS = 1.0
# Speed vs killer when drop dash starts (multiplier on killer base walk speed)
DROP_DASH_SPEED_VS_KILLER_MULT = 1.27

# Cream — healing aura (other survivors in radius)
CREAM_HEAL_PER_SECOND = 10.0
CREAM_HEAL_DURATION_SECONDS = 5.0

# Metal Sonic — self repair + killer charge
METAL_SELF_HEAL_DURATION_SECONDS = 20.0
METAL_SELF_HEAL_PER_SECOND = 5.0
METAL_EGGMAN_HEAL_NEARBY_RADIUS = 260.0
METAL_EGGMAN_HEAL_NEARBY_MULT = 1.8
# Killer charge without carrying X2011; pickup grants longer window (metal_charge_carry.py).
METAL_CHARGE_DURATION_SECONDS = 8.0
METAL_CHARGE_DURATION_WITH_X2011_CARRY_SECONDS = 10.0
METAL_CHARGE_WINDUP_SECONDS = 1.0
METAL_CHARGE_KILLER_STUN_SECONDS = 5.0
# X2011 after Metal charge carry (not used for Kollosios touch)
METAL_CHARGE_X2011_DROP_STUN_SECONDS = 8.0
METAL_CHARGE_X2011_SLAM_STUN_SECONDS = 10.0
METAL_CHARGE_HP_COST = 30.0
METAL_CHARGE_SPEED_MULT = 1.5
METAL_CHARGE_DAMAGE_REDUCTION_FLAT = 20.0
# Metal Sonic max_health stays higher for damage pool; heals cannot exceed this.
METAL_SONIC_HEAL_CAP = 155.0
# Metal carries X2011 during charge; slam into wall to drop + damage
METAL_CHARGE_WALL_SLAM_DEPTH = 2.35
METAL_CHARGE_SLAM_DAMAGE = 52.0
METAL_CHARGE_BEATUP_ANIM_SECONDS = 0.58
METAL_CHARGE_SLAM_KNOCKBACK_MULT = 520.0 * GLOBAL_MOVEMENT_SPEED_MULT
METAL_CHARGE_SLAM_KNOCKBACK_SECONDS = 0.42
METAL_CHARGE_DEBRIS_COUNT = 20
METAL_CHARGE_DEBRIS_LIFETIME = 0.72
METAL_CHARGE_DEBRIS_SPEED_MIN = 180.0 * GLOBAL_MOVEMENT_SPEED_MULT
METAL_CHARGE_DEBRIS_SPEED_MAX = 620.0 * GLOBAL_MOVEMENT_SPEED_MULT
METAL_CHARGE_CARRY_HP_DRAIN_PER_TICK = 1.0
METAL_CHARGE_CARRY_HP_DRAIN_INTERVAL = 0.1
# Total HP lost from carry drain ends killer charge early (release X2011).
METAL_CHARGE_CARRY_HP_LOSS_END_CHARGE = 40.0

# Amy — hammer (melee swing + throw)
AMY_HAMMER_STUN_SECONDS = 3.0
AMY_HAMMER_SWING_SECONDS = 0.18
AMY_HAMMER_THROW_SPEED = 760.0 * GLOBAL_MOVEMENT_SPEED_MULT
AMY_HAMMER_THROW_MAX_SECONDS = 0.55

# Eggman — overdrive + electric shield
EGGMAN_SPEED_BOOST_DURATION_SECONDS = 5.0
EGGMAN_SPEED_BOOST_MULT = 1.95
EGGMAN_SHIELD_DURATION_SECONDS = 5.0
EGGMAN_SHIELD_STUN_SECONDS = 3.0

# Tails — hand cannon (charge, beam, stun stacks per second in beam)
TAILS_CANNON_CHARGE_SECONDS = 5.0
TAILS_CANNON_BEAM_SECONDS = 5.0
TAILS_CANNON_BEAM_LENGTH = 450.0
TAILS_CANNON_BEAM_HALF_WIDTH = 32.0

# 2011X — grab charge (sprint, grab, DPS, mash escape)
X2011_GRAB_CHARGE_SECONDS = 10.0
X2011_GRAB_DPS = 5.0
X2011_GRAB_BREAK_STUN_SECONDS = 3.0
X2011_GRAB_CHARGE_SPEED_MULT = 1.65
X2011_GRAB_MASH_PER_KEY = 14.0
X2011_GRAB_BOT_ESCAPE_PER_SECOND = 20.0 * GLOBAL_MOVEMENT_SPEED_MULT

# 2011X — rage (after many stuns)
X2011_RAGE_STUNS_TO_ACTIVATE = 10
X2011_RAGE_DURATION_SECONDS = 60.0
X2011_RAGE_SPEED_MULT = 1.25
X2011_RAGE_DAMAGE_MULT = 1.25
X2011_RAGE_STUN_RECEIVED_MULT = 0.5
KILLER_STUN_KNOCKBACK_DISTANCE = 34.0 * GLOBAL_MOVEMENT_SPEED_MULT
KILLER_STUN_IMMUNITY_SECONDS = 5.0

# Kollosios — multi-grab charge
KOLLOSIOS_CHARGE_SECONDS = 10.0
KOLLOSIOS_CHARGE_SPEED_MULT = 1.6
KOLLOSIOS_CHARGE_DAMAGE = 20.0
KOLLOSIOS_CHARGE_LOW_HP_THRESHOLD = 19.0
KOLLOSIOS_CHARGE_LOW_HP_HEAL = 25.0

# Kollosios — basic attack random grab (hold, punch rolls, throw)
KOLLOSIOS_BASIC_GRAB_SECONDS = 5.0
KOLLOSIOS_BASIC_GRAB_CHANCE = 0.5
KOLLOSIOS_BASIC_GRAB_PUNCH_CHANCE = 0.6
KOLLOSIOS_BASIC_GRAB_THROW_SPEED = 780.0 * GLOBAL_MOVEMENT_SPEED_MULT
KOLLOSIOS_BASIC_GRAB_THROW_DASH_SECONDS = 0.55

# AI tuning
SURVIVOR_FLEE_RADIUS = 320.0
# Keep survivor bot patrol goals away from arena bounds (reduces edge-rubbing pathfinding)
SURVIVOR_INTERIOR_GOAL_MARGIN = 120.0
AI_REPATH_INTERVAL = 0.35
BOT_ABILITY_TRY_INTERVAL = 2.8

# Survivor hit reaction: brief adrenaline burst after taking damage
SURVIVOR_HIT_SPEED_BOOST_MULT = 1.85
SURVIVOR_HIT_SPEED_BOOST_SECONDS = 1.2

# Knuckles — Lunge Punch tuning
KNUCKLES_PUNCH_CHARGE_DAMAGE_MULT = 0.2  # 80% damage resistance while punch is armed
KNUCKLES_PUNCH_RELEASE_IFRAMES_SECONDS = 0.3
KNUCKLES_BLOCK_GRAB_GUARD_SECONDS = 2.0
