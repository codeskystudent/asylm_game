from __future__ import annotations

import math
import random
import time

import pygame

from outcome_game import ability_service, lms_audio
from outcome_game.x2011_rage import update_killer_stun_immunity
from outcome_game.ai_service import (
    choose_survivor_bot_ability_index,
    reset_brains,
    should_force_cream_heal_attempt,
    should_force_survivor_stun_attempt,
    should_try_ability,
    should_try_survivor_ability,
    steer_executioner,
    steer_survivor,
)
from outcome_game.character_definitions import registry as char_registry
from outcome_game.constants import (
    ARENA_H,
    ARENA_W,
    GLOBAL_MOVEMENT_SPEED_MULT,
    NUM_SURVIVOR_SLOTS,
    PC_SPRINT_SPEED_MULT,
    X2011_GRAB_MASH_PER_KEY,
)
from outcome_game.entities import Combatant
from outcome_game.survivor_death_revive import tick_revives
from outcome_game.arena_maps import activate_random_map, get_active_map_display_name, get_active_theme
from outcome_game.hud import (
    apply_escape_post_processing,
    draw_end,
    draw_hud,
    draw_lobby,
    draw_world,
    seconds_until_escape_window_opens,
)
from outcome_game.match_service import (
    Phase,
    check_winner,
    get_exit_rects,
    reset_exit_rects,
    update_exit_zone,
)
from outcome_game import (
    kollosios_basic_grab,
    kollosios_charge,
    metal_charge_carry,
    sonic_abilities,
    tails_cannon,
    x2011_grab,
)
from outcome_game.arena_navigation import get_arena_walls
from outcome_game.planar_movement import apply_input_to_velocity, integrate_and_collide


VIEW_W = 1280
VIEW_H = 720


def _make_combatant(
    char_id: str,
    team: str,
    *,
    is_human: bool,
    is_bot: bool,
    x: float,
    y: float,
) -> Combatant:
    d = char_registry.get_definition(char_id)
    if not d:
        raise ValueError(char_id)
    return Combatant(
        char_id=char_id,
        team=team,
        is_bot=is_bot,
        is_human=is_human,
        x=x,
        y=y,
        health=float(d["max_health"]),
        max_health=float(d["max_health"]),
        base_walk_speed=float(d["base_walk_speed"]) * GLOBAL_MOVEMENT_SPEED_MULT,
    )


def _survivor_spawn(i: int, n: int) -> tuple[float, float]:
    angle = math.tau * (i / n) + 0.3
    cx, cy = ARENA_W * 0.5, ARENA_H * 0.72
    r = min(ARENA_W, ARENA_H) * 0.28
    return cx + math.cos(angle) * r, cy + math.sin(angle) * r * 0.55


def build_match(
    human_role: str,
    executioner_id: str,
    *,
    human_survivor_id: str | None = None,
    bot_only: bool = False,
) -> tuple[list[Combatant], Combatant]:
    """
    Exactly NUM_SURVIVOR_SLOTS survivors + 1 executioner (7 fighters).
    One human player + 6 bots: you are either a random survivor or the executioner;
    bot-only mode is all AI.
    """
    reset_brains()
    activate_random_map()
    reset_exit_rects()
    combatants: list[Combatant] = []
    pool = char_registry.get_all_survivor_ids()
    if len(pool) < NUM_SURVIVOR_SLOTS:
        raise ValueError(f"Need at least {NUM_SURVIVOR_SLOTS} survivor definitions, got {len(pool)}")
    force_human_survivor = (
        (not bot_only)
        and human_role == "Survivor"
        and human_survivor_id is not None
        and human_survivor_id in pool
    )
    if force_human_survivor:
        other_ids = [sid for sid in pool if sid != human_survivor_id]
        survivor_ids = random.sample(other_ids, NUM_SURVIVOR_SLOTS - 1)
        human_survivor_slot = random.randrange(NUM_SURVIVOR_SLOTS)
        survivor_ids.insert(human_survivor_slot, human_survivor_id)
    else:
        survivor_ids = random.sample(pool, NUM_SURVIVOR_SLOTS)
        human_survivor_slot = random.randrange(NUM_SURVIVOR_SLOTS)

    for i, sid in enumerate(survivor_ids):
        is_human = (
            (not bot_only)
            and human_role == "Survivor"
            and i == human_survivor_slot
        )
        x, y = _survivor_spawn(i, NUM_SURVIVOR_SLOTS)
        combatants.append(
            _make_combatant(sid, "Survivors", is_human=is_human, is_bot=not is_human, x=x, y=y)
        )

    exec_ids = char_registry.get_all_executioner_ids()
    if executioner_id in exec_ids:
        kd = executioner_id
    else:
        # Fall back to any available killer definition instead of hard-locking X2011.
        kd = random.choice(exec_ids) if exec_ids else "X2011"
    k_human = (not bot_only) and human_role == "Executioner"
    killer = _make_combatant(
        kd,
        "Executioners",
        is_human=k_human,
        is_bot=not k_human,
        x=ARENA_W * 0.5,
        y=120.0,
    )
    combatants.append(killer)
    return combatants, killer


def _get_human(combatants: list[Combatant]) -> Combatant | None:
    for c in combatants:
        if c.is_human:
            return c
    return None


def _camera_focus(combatants: list[Combatant], bot_only: bool) -> Combatant:
    if bot_only:
        return _killer(combatants)
    h = _get_human(combatants)
    return h if h else combatants[0]


def _killer(combatants: list[Combatant]) -> Combatant:
    for c in combatants:
        if c.team == "Executioners":
            return c
    raise RuntimeError("no killer")


def _update_human_mouse_aim(human: Combatant) -> None:
    """Point the local human combatant toward current mouse world position."""
    cam_x = max(0.0, min(ARENA_W - VIEW_W, human.x - VIEW_W * 0.5))
    cam_y = max(0.0, min(ARENA_H - VIEW_H, human.y - VIEW_H * 0.5))
    mx, my = pygame.mouse.get_pos()
    world_mx = cam_x + mx
    world_my = cam_y + my
    dx = world_mx - human.x
    dy = world_my - human.y
    d = math.hypot(dx, dy)
    if d > 1e-6:
        human.facing_x = dx / d
        human.facing_y = dy / d


def _update_sonic_trails(combatants: list[Combatant], now: float) -> None:
    """Track short-lived trail points while Sonic is in Peelout/Drop Dash."""
    ttl = 0.34
    for c in combatants:
        if c.char_id != "Sonic":
            continue
        c.sonic_trail = [(x, y, t) for (x, y, t) in c.sonic_trail if now - t <= ttl]
        in_peelout = c.peelout_phase == "carry" and now < c.peelout_phase_end
        in_drop_dash = c.drop_dash_end > now
        if in_peelout or in_drop_dash:
            if not c.sonic_trail or (c.x - c.sonic_trail[-1][0]) ** 2 + (c.y - c.sonic_trail[-1][1]) ** 2 >= 18.0 * 18.0:
                c.sonic_trail.append((c.x, c.y, now))


def _update_metal_charge_trails(combatants: list[Combatant], now: float) -> None:
    """Track short-lived trail points while Metal Sonic's killer charge is active."""
    ttl = 0.34
    step_sq = 18.0 * 18.0
    for c in combatants:
        if c.char_id != "MetalSonic":
            continue
        c.metal_charge_trail = [(x, y, t) for (x, y, t) in c.metal_charge_trail if now - t <= ttl]
        if c.metal_charge_until > now:
            if (
                not c.metal_charge_trail
                or (c.x - c.metal_charge_trail[-1][0]) ** 2 + (c.y - c.metal_charge_trail[-1][1]) ** 2 >= step_sq
            ):
                c.metal_charge_trail.append((c.x, c.y, now))


def main() -> None:
    pygame.init()
    pygame.mixer.init()
    pygame.display.set_caption("Outcome-style (Python) — PC: WASD · Shift sprint · Q/E/R · LMB melee (killer)")
    screen = pygame.display.set_mode((VIEW_W, VIEW_H))
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("segoeui", 22)
    body_font = pygame.font.SysFont("segoeui", 18)
    lobby_font = pygame.font.SysFont("segoeui", 22)

    phase = Phase.LOBBY
    human_role = "Survivor"
    bot_only = False
    executioner_id = "X2011"
    human_survivor_id: str | None = None
    combatants: list[Combatant] = []
    round_end_unix = 0.0
    round_start_unix = 0.0
    round_duration_initial = 0.0
    winner: str | None = None

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        now = time.monotonic()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if phase == Phase.LOBBY:
                    if event.key == pygame.K_1:
                        human_role = "Survivor"
                        bot_only = False
                    elif event.key == pygame.K_2:
                        human_role = "Executioner"
                        bot_only = False
                    elif event.key == pygame.K_3:
                        bot_only = True
                    elif event.key == pygame.K_q:
                        executioner_id = "X2011"
                    elif event.key == pygame.K_e:
                        executioner_id = "Kollosios"
                    elif event.key in (pygame.K_z, pygame.K_x):
                        picks: list[str | None] = [None, *char_registry.get_all_survivor_ids()]
                        cur = human_survivor_id if human_survivor_id in picks else None
                        i = picks.index(cur)
                        step = 1 if event.key == pygame.K_x else -1
                        human_survivor_id = picks[(i + step) % len(picks)]
                    elif event.key == pygame.K_SPACE:
                        lms_audio.reset_lms_music_state()
                        combatants, _ = build_match(
                            human_role,
                            executioner_id,
                            human_survivor_id=human_survivor_id,
                            bot_only=bot_only,
                        )
                        round_start_unix = now
                        round_duration_initial = lms_audio.get_round_duration_seconds(combatants)
                        round_end_unix = now + round_duration_initial
                        phase = Phase.IN_ROUND
                        winner = None
                elif phase == Phase.ENDED:
                    if event.key == pygame.K_r:
                        phase = Phase.LOBBY
                        winner = None
                        combatants = []
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                elif phase == Phase.IN_ROUND and not bot_only:
                    hum = _get_human(combatants)
                    kl = _killer(combatants)
                    if hum and hum.grabbed_by and event.key == pygame.K_SPACE:
                        hum.grab_break_progress = min(100.0, hum.grab_break_progress + X2011_GRAB_MASH_PER_KEY)
                    if hum:
                        if hum.char_id == "Knuckles" and event.key == pygame.K_q:
                            hum.knuckles_punch_armed = True
                            hum.ability_flash_until = max(hum.ability_flash_until, now + 0.14)
                            continue
                        ab_idx: int | None = None
                        if event.key == pygame.K_q:
                            ab_idx = 0
                        elif event.key == pygame.K_e:
                            ab_idx = 1
                        elif event.key == pygame.K_r:
                            ab_idx = 2
                        if ab_idx is not None:
                            dfn = char_registry.get_definition(hum.char_id)
                            n_ab = len(dfn["abilities"]) if dfn and dfn.get("abilities") else 0
                            if n_ab > 0:
                                ab_idx = min(ab_idx, n_ab - 1)
                                ability_service.try_use_ability(hum, ab_idx, now, combatants, kl)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
            if (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and phase == Phase.IN_ROUND
                and not bot_only
            ):
                hum = _get_human(combatants)
                kl = _killer(combatants)
                if (
                    hum
                    and hum.char_id == "Knuckles"
                    and hum.alive()
                    and not hum.escaped
                    and hum.knuckles_punch_armed
                ):
                    ability_service.try_use_ability(hum, 0, now, combatants, kl)

        if phase == Phase.IN_ROUND:
            human = _get_human(combatants)
            killer = _killer(combatants)

            ability_service.tick_metal_charge_windup(combatants, now)
            sonic_abilities.pre_movement_tick(combatants, now)

            keys = pygame.key.get_pressed()
            ix, iy = 0.0, 0.0
            if not bot_only and human and human.alive() and not human.escaped:
                if keys[pygame.K_w]:
                    iy -= 1.0
                if keys[pygame.K_s]:
                    iy += 1.0
                if keys[pygame.K_a]:
                    ix -= 1.0
                if keys[pygame.K_d]:
                    ix += 1.0
                _update_human_mouse_aim(human)

            for c in combatants:
                if not c.is_bot or c.dead or c.downed or c.escaped:
                    continue
                if c.team == "Survivors":
                    bx, by = steer_survivor(c, killer, now, dt, round_end_unix, combatants)
                    apply_input_to_velocity(c, bx, by, dt, now, combatants)
                else:
                    sx, sy = steer_executioner(c, combatants, now, dt)
                    apply_input_to_velocity(c, sx, sy, dt, now, combatants, sprint_mult=1.0)
                    if should_try_ability(c, now):
                        ability_service.try_use_ability(
                            c,
                            random.randint(0, 2),
                            now,
                            combatants,
                            killer,
                        )

            if not bot_only and human and human.alive() and not human.escaped:
                sprint = PC_SPRINT_SPEED_MULT if keys[pygame.K_LSHIFT] else 1.0
                apply_input_to_velocity(human, ix, iy, dt, now, combatants, sprint_mult=sprint)

            # Bot survivors: stun / heal priorities (faster cadence than random slot picks)
            for c in combatants:
                if c.team == "Survivors" and c.is_bot and c.alive() and not c.escaped:
                    if (
                        should_try_survivor_ability(c, now)
                        or should_force_survivor_stun_attempt(c, killer, now)
                        or should_force_cream_heal_attempt(c, combatants, now)
                    ):
                        ab_idx = choose_survivor_bot_ability_index(c, killer, combatants)
                        ability_service.try_use_ability(c, ab_idx, now, combatants, killer)

            metal_charge_carry.tick_metal_charge_pre_integrate(combatants, killer, get_arena_walls(), now)

            integrate_and_collide(combatants, ARENA_W, ARENA_H, get_arena_walls())

            sonic_abilities.post_movement_tick(combatants, killer, ARENA_W, ARENA_H, now)

            ability_service.tick_healing_auras(combatants, now, dt)
            ability_service.tick_metal_self_heal(combatants, now, dt)
            metal_charge_carry.tick_metal_charge_post_integrate(
                combatants, killer, ARENA_W, ARENA_H, get_arena_walls(), now, dt
            )
            ability_service.tick_amy_hammer_throw(combatants, killer, now, dt)
            tails_cannon.tick_tails_hand_cannon(combatants, killer, now, dt)
            x2011_grab.tick_x2011_grab(combatants, killer, ARENA_W, ARENA_H, now, dt)
            kollosios_basic_grab.tick_kollosios_basic_grab(killer, combatants, ARENA_W, ARENA_H, now)
            kollosios_charge.tick_kollosios_charge(combatants, killer, ARENA_W, ARENA_H, now)
            _update_sonic_trails(combatants, now)
            _update_metal_charge_trails(combatants, now)

            # Killer basic melee: AI always tries; human uses LMB (held), Q/E/R are abilities 1–3
            mouse_left = pygame.mouse.get_pressed()[0]
            killer_wants_melee = killer.is_bot or (
                not bot_only
                and human
                and human.team == "Executioners"
                and mouse_left
            )
            if (
                killer_wants_melee
                and killer.alive()
                and not killer.escaped
                and killer.x2011_grab_victim is None
                and killer.kollosios_basic_grab_victim is None
                and not (killer.char_id == "Kollosios" and killer.kollosios_charge_until > now)
            ):
                ability_service.try_use_ability(killer, 0, now, combatants, killer)

            update_exit_zone(combatants, dt, now, round_end_unix, killer)

            tick_revives(combatants, now, dt)

            update_killer_stun_immunity(killer, now)

            lms_audio.tick_lms_music(combatants)

            w = check_winner(combatants, round_end_unix, now)
            if w:
                winner = w
                lms_audio.reset_lms_music_state()
                phase = Phase.ENDED

        # --- Render ---
        if phase == Phase.LOBBY:
            draw_lobby(screen, human_role, executioner_id, human_survivor_id, bot_only, lobby_font)
        elif phase == Phase.IN_ROUND:
            focus = _camera_focus(combatants, bot_only)
            cam_x = focus.x - VIEW_W * 0.5
            cam_y = focus.y - VIEW_H * 0.5
            cam_x = max(0.0, min(ARENA_W - VIEW_W, cam_x))
            cam_y = max(0.0, min(ARENA_H - VIEW_H, cam_y))
            draw_world(
                screen,
                combatants,
                cam_x,
                cam_y,
                get_exit_rects(),
                get_arena_walls(),
                ARENA_W,
                ARENA_H,
                get_active_theme(),
                round_end_unix,
                killer,
                viewer=focus,
            )
            draw_hud(
                screen,
                focus,
                combatants,
                round_end_unix,
                round_start_unix,
                get_exit_rects(),
                (title_font, body_font),
                spectate=bot_only,
                killer=killer,
                map_display_name=get_active_map_display_name(),
                seconds_until_exit_open=seconds_until_escape_window_opens(now, round_end_unix),
            )
            apply_escape_post_processing(
                screen,
                now=now,
                round_end_unix=round_end_unix,
                killer=killer,
                combatants=combatants,
                focus=focus,
                spectate=bot_only,
            )
        elif phase == Phase.ENDED and winner:
            if combatants:
                killer = _killer(combatants)
                focus = _camera_focus(combatants, bot_only)
                cam_x = max(0.0, min(ARENA_W - VIEW_W, focus.x - VIEW_W * 0.5))
                cam_y = max(0.0, min(ARENA_H - VIEW_H, focus.y - VIEW_H * 0.5))
                draw_world(
                    screen,
                    combatants,
                    cam_x,
                    cam_y,
                    get_exit_rects(),
                    get_arena_walls(),
                    ARENA_W,
                    ARENA_H,
                    get_active_theme(),
                    round_end_unix,
                    killer,
                    viewer=focus,
                )
                draw_hud(
                    screen,
                    focus,
                    combatants,
                    round_end_unix,
                    round_start_unix,
                    get_exit_rects(),
                    (title_font, body_font),
                    spectate=bot_only,
                    killer=killer,
                    map_display_name=get_active_map_display_name(),
                )
            draw_end(screen, winner, title_font)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
