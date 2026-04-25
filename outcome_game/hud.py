"""On-screen HUD: health, timer, abilities, roster."""

from __future__ import annotations

import math
import time

import pygame

from outcome_game.character_definitions import registry as char_registry
from outcome_game.constants import ESCAPE_OPENS_AT_ROUND_FRACTION
from outcome_game.entities import Combatant
from outcome_game.match_service import exits_available_for_escape, is_escape_window_open
from outcome_game.x2011_rage import rage_active

# Ring next to timer: last N seconds before exits unlock, color shifts gray → green
EXIT_RING_APPROACH_MIN = 18.0
EXIT_RING_APPROACH_MAX = 52.0


def _draw_exit_countdown_ring(
    surf: pygame.Surface,
    cx: int,
    cy: int,
    radius: int,
    width: int,
    now: float,
    round_start_unix: float,
    round_duration_initial: float,
) -> None:
    """
    Ring fills clockwise toward the moment exits unlock; turns green when opening is soon.
    """
    threshold = ESCAPE_OPENS_AT_ROUND_FRACTION * max(round_duration_initial, 1e-6)
    open_at = round_start_unix + threshold
    rect = pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2)

    if now >= open_at:
        pygame.draw.circle(surf, (52, 200, 118), (cx, cy), radius, width=width)
        return

    elapsed = max(0.0, now - round_start_unix)
    sweep = min(1.0, elapsed / threshold)
    time_until = open_at - now
    span = round_duration_initial
    approach = min(EXIT_RING_APPROACH_MAX, max(EXIT_RING_APPROACH_MIN, span * 0.14))

    if time_until >= approach:
        arc_col = (88, 98, 112)
    else:
        u = 1.0 - (time_until / approach)
        arc_col = (
            int(88 + (48 - 88) * u),
            int(98 + (205 - 98) * u),
            int(112 + (128 - 112) * u),
        )

    pygame.draw.circle(surf, (30, 34, 42), (cx, cy), radius, width=width)

    start = -math.pi / 2
    end = start + sweep * math.tau
    if sweep >= 0.999:
        pygame.draw.circle(surf, arc_col, (cx, cy), radius, width=width)
    elif sweep > 0.002:
        pygame.draw.arc(surf, arc_col, rect, start, end, width=width)


def draw_exit_direction_ui(
    surf: pygame.Surface,
    focus: Combatant,
    exit_rects: list[pygame.Rect],
    round_start_unix: float,
    round_duration_initial: float,
    killer: Combatant,
    combatants: list[Combatant],
    small_font: pygame.font.Font,
) -> None:
    """Bottom-left compass toward nearest exit when escapes are active (survivor focus only)."""
    now = time.monotonic()
    if not exits_available_for_escape(now, round_start_unix, round_duration_initial, killer, combatants):
        return
    if focus.team != "Survivors" or not focus.alive() or focus.escaped:
        return
    if not exit_rects:
        return
    px, py = focus.x, focus.y
    best_d = 1e18
    ex = ey = 0.0
    for r in exit_rects:
        cx = r.x + r.width / 2
        cy = r.y + r.height / 2
        d = (cx - px) ** 2 + (cy - py) ** 2
        if d < best_d:
            best_d = d
            ex, ey = cx, cy
    angle = math.atan2(ey - py, ex - px)
    w, h = surf.get_size()
    ccx, ccy = 108, h - 168
    rad = 42
    pygame.draw.circle(surf, (20, 24, 32), (ccx, ccy), rad + 2)
    pygame.draw.circle(surf, (14, 18, 26), (ccx, ccy), rad)
    pygame.draw.circle(surf, (70, 120, 100), (ccx, ccy), rad, 2)
    tip_x = ccx + math.cos(angle) * (rad - 6)
    tip_y = ccy + math.sin(angle) * (rad - 6)
    pygame.draw.line(surf, (140, 230, 180), (ccx, ccy), (tip_x, tip_y), 5)
    wing = 11.0
    a_back = angle + math.pi
    pygame.draw.polygon(
        surf,
        (140, 230, 180),
        [
            (tip_x, tip_y),
            (tip_x + math.cos(a_back - 0.45) * wing, tip_y + math.sin(a_back - 0.45) * wing),
            (tip_x + math.cos(a_back + 0.45) * wing, tip_y + math.sin(a_back + 0.45) * wing),
        ],
    )
    surf.blit(small_font.render("Nearest exit", True, (190, 210, 200)), (ccx - 48, ccy - rad - 24))


def draw_world(
    surf: pygame.Surface,
    combatants: list[Combatant],
    camera_x: float,
    camera_y: float,
    exit_rects_world: list[pygame.Rect],
    wall_rects_world: list[pygame.Rect],
    arena_w: float,
    arena_h: float,
    round_end_unix: float | None = None,
    round_start_unix: float | None = None,
    round_duration_initial: float | None = None,
    killer: Combatant | None = None,
) -> None:
    """Draw arena floor, walls, exit zones, actors (world space -> screen)."""
    surf.fill((18, 22, 28))
    ox, oy = -camera_x, -camera_y

    # Arena border
    border = pygame.Rect(ox, oy, int(arena_w), int(arena_h))
    pygame.draw.rect(surf, (40, 48, 58), border, width=4)

    for w in wall_rects_world:
        wr = w.move(ox, oy)
        pygame.draw.rect(surf, (55, 58, 68), wr)
        pygame.draw.rect(surf, (95, 100, 118), wr, width=2)

    font = pygame.font.SysFont("segoeui", 18)
    now = time.monotonic()
    rage_hide_exits = False
    locked = False
    if (
        round_end_unix is not None
        and round_start_unix is not None
        and round_duration_initial is not None
    ):
        if killer is not None:
            if exits_available_for_escape(now, round_start_unix, round_duration_initial, killer, combatants):
                locked = False
            elif (
                is_escape_window_open(now, round_start_unix, round_duration_initial)
                and killer.char_id == "X2011"
                and rage_active(killer, now, combatants)
            ):
                rage_hide_exits = True
            else:
                locked = not is_escape_window_open(now, round_start_unix, round_duration_initial)
        else:
            locked = not is_escape_window_open(now, round_start_unix, round_duration_initial)

    if not rage_hide_exits:
        multi = len(exit_rects_world) > 1
        for i, raw in enumerate(exit_rects_world):
            er = raw.move(ox, oy)
            label = f"EXIT {i + 1}" if multi else "EXIT"
            if locked:
                pygame.draw.rect(surf, (90, 55, 55), er, width=3)
                surf.blit(
                    font.render(f"{label} (locked)", True, (220, 180, 170)),
                    (er.centerx - (58 if multi else 52), er.centery - 10),
                )
            else:
                pygame.draw.rect(surf, (60, 140, 90), er, width=3)
                surf.blit(
                    font.render(label, True, (180, 240, 200)),
                    (er.centerx - (28 if multi else 22), er.centery - 10),
                )

    killer_actor = next((z for z in combatants if z.team == "Executioners"), None)
    if killer_actor and killer_actor.stun_immunity_until > now and killer_actor.alive() and not killer_actor.escaped:
        ksx = killer_actor.x + ox
        ksy = killer_actor.y + oy
        phase = 1.0 - max(0.0, min(1.0, (killer_actor.stun_immunity_until - now) / 5.0))
        rr = int(killer_actor.radius + 10.0 + 2.5 * math.sin(phase * math.tau * 4.0))
        pygame.draw.circle(surf, (255, 70, 70), (int(ksx), int(ksy)), rr, width=3)
    if killer_actor and killer_actor.stun_splash_until > now and killer_actor.alive() and not killer_actor.escaped:
        ksx = killer_actor.x + ox
        ksy = killer_actor.y + oy
        t = 1.0 - max(0.0, min(1.0, (killer_actor.stun_splash_until - now) / 0.28))
        base = killer_actor.radius + 6.0
        for i, col in enumerate(((150, 230, 255), (200, 245, 255), (120, 210, 255))):
            rr = int(base + t * 20.0 + i * 7.0)
            pygame.draw.circle(surf, col, (int(ksx), int(ksy)), rr, width=2)

    # Sonic speed trail while peelout/drop dash is active.
    for c in combatants:
        if c.char_id != "Sonic" or not c.sonic_trail:
            continue
        for tx, ty, tt in c.sonic_trail:
            age = now - tt
            if age < 0.0 or age > 0.34:
                continue
            fade = 1.0 - (age / 0.34)
            rr = max(3, int(c.radius * (0.28 + 0.28 * fade)))
            sx = tx + ox
            sy = ty + oy
            pygame.draw.circle(surf, (90, 200, 255), (int(sx), int(sy)), rr, width=2)

    # 2011X charge trail while grab charge is active.
    for c in combatants:
        if c.char_id != "X2011" or not c.x2011_charge_trail:
            continue
        for tx, ty, tt in c.x2011_charge_trail:
            age = now - tt
            if age < 0.0 or age > 0.3:
                continue
            fade = 1.0 - (age / 0.3)
            rr = max(4, int(c.radius * (0.26 + 0.3 * fade)))
            sx = tx + ox
            sy = ty + oy
            pygame.draw.circle(surf, (255, 96, 86), (int(sx), int(sy)), rr, width=2)

    for c in combatants:
        if c.team != "Survivors" or c.stun_hitbox_until <= now or c.dead or c.escaped:
            continue
        sx = c.x + ox
        sy = c.y + oy
        r = int(max(0.0, c.stun_hitbox_radius))
        if r > 0:
            pygame.draw.circle(surf, (120, 210, 255), (int(sx), int(sy)), r, width=2)
        if killer_actor and killer_actor.alive() and not killer_actor.escaped:
            kx = killer_actor.x + ox
            ky = killer_actor.y + oy
            pygame.draw.circle(surf, (255, 110, 110), (int(kx), int(ky)), int(killer_actor.radius), width=2)

    for c in combatants:
        if c.dead and not c.escaped:
            continue
        sx = c.x + ox
        sy = c.y + oy
        color = (90, 160, 255) if c.team == "Survivors" else (220, 70, 70)
        if c.escaped:
            color = (120, 220, 160)
        pygame.draw.circle(surf, color, (int(sx), int(sy)), int(c.radius))
        pygame.draw.circle(surf, (240, 244, 248), (int(sx), int(sy)), int(c.radius), width=2)
        if c.ability_flash_until > now:
            pulse = 1.0 + (c.ability_flash_until - now) * 3.0
            fr = int(c.radius + 4 + min(9.0, pulse * 3.0))
            pygame.draw.circle(surf, (255, 246, 190), (int(sx), int(sy)), fr, width=3)
        if c.char_id == "Cream" and c.healing_aura_until > now:
            hr = int(max(0.0, c.healing_aura_range + c.radius))
            if hr > 0:
                pygame.draw.circle(surf, (94, 230, 164), (int(sx), int(sy)), hr, width=2)
                pygame.draw.circle(surf, (60, 170, 122), (int(sx), int(sy)), max(0, hr - 8), width=1)
        if c.char_id == "Amy":
            fx, fy = c.facing_x, c.facing_y
            fd = math.hypot(fx, fy) or 1.0
            fx /= fd
            fy /= fd
            if c.amy_hammer_swing_until > now:
                # Quick swing arc from one side of facing to the other.
                p = 1.0 - max(0.0, min(1.0, (c.amy_hammer_swing_until - now) / 0.18))
                ang = (p - 0.5) * 1.5
                ca = math.cos(ang)
                sa = math.sin(ang)
                hx = fx * ca - fy * sa
                hy = fx * sa + fy * ca
            else:
                hx, hy = fx, fy
            handle_len = c.radius * 0.9
            head_r = max(6, int(c.radius * 0.42))
            base_x = sx + hx * (c.radius + 2.0)
            base_y = sy + hy * (c.radius + 2.0)
            head_x = base_x + hx * handle_len
            head_y = base_y + hy * handle_len
            pygame.draw.line(surf, (166, 124, 86), (int(base_x), int(base_y)), (int(head_x), int(head_y)), 4)
            pygame.draw.circle(surf, (236, 132, 178), (int(head_x), int(head_y)), head_r)
            pygame.draw.circle(surf, (252, 202, 226), (int(head_x), int(head_y)), head_r, width=2)
        if c.is_human and c.alive() and not c.escaped:
            aim_len = c.radius + 28.0
            ax = sx + c.facing_x * aim_len
            ay = sy + c.facing_y * aim_len
            pygame.draw.line(surf, (255, 226, 138), (int(sx), int(sy)), (int(ax), int(ay)), 3)
            pygame.draw.circle(surf, (255, 226, 138), (int(ax), int(ay)), 5, width=2)
        label = char_registry.get_definition(c.char_id)
        name = label["display_name"] if label else c.char_id
        if c.is_human:
            name += " (you)"
        t = font.render(name[:18], True, (230, 234, 240))
        surf.blit(t, (int(sx - t.get_width() // 2), int(sy - c.radius - 22)))

    # Amy throw projectile (travels in the direction Amy aimed when cast).
    for c in combatants:
        if c.char_id != "Amy" or not c.amy_hammer_throw_active or c.dead or c.escaped:
            continue
        tx = c.amy_hammer_throw_x + ox
        ty = c.amy_hammer_throw_y + oy
        pygame.draw.circle(surf, (236, 132, 178), (int(tx), int(ty)), 9)
        pygame.draw.circle(surf, (252, 202, 226), (int(tx), int(ty)), 9, width=2)
        bx = tx - c.amy_hammer_throw_vx * 0.014
        by = ty - c.amy_hammer_throw_vy * 0.014
        pygame.draw.line(surf, (166, 124, 86), (int(bx), int(by)), (int(tx), int(ty)), 3)


def draw_hud(
    surf: pygame.Surface,
    focus: Combatant,
    combatants: list[Combatant],
    round_end_unix: float,
    round_start_unix: float,
    round_duration_initial: float,
    exit_rects: list[pygame.Rect],
    fonts: tuple[pygame.font.Font, pygame.font.Font],
    *,
    spectate: bool = False,
    killer: Combatant | None = None,
) -> None:
    """HUD layout: timer top-center, health bottom-left, ability circles bottom-right."""
    title_f, body_f = fonts
    w, h = surf.get_size()
    now = time.monotonic()

    # --- Timer (top-middle) ---
    remain = max(0.0, round_end_unix - now)
    m, s = divmod(int(remain), 60)
    timer_txt = title_f.render(f"{m:02d}:{s:02d}", True, (245, 248, 252))
    tpad_x, tpad_y = 18, 10
    timer_box = pygame.Rect(
        w // 2 - (timer_txt.get_width() // 2 + tpad_x),
        14,
        timer_txt.get_width() + tpad_x * 2,
        timer_txt.get_height() + tpad_y * 2,
    )
    pygame.draw.rect(surf, (14, 18, 24), timer_box, border_radius=12)
    pygame.draw.rect(surf, (70, 80, 96), timer_box, width=2, border_radius=12)
    surf.blit(timer_txt, (timer_box.centerx - timer_txt.get_width() // 2, timer_box.y + tpad_y))

    # --- Health (bottom-left) ---
    hp_x = 14
    hp_w = 300
    hp_h = 18
    hp_y = h - 44
    ratio = 0.0 if focus.max_health <= 0 else max(0.0, min(1.0, focus.health / focus.max_health))
    pygame.draw.rect(surf, (20, 24, 32), (hp_x - 2, hp_y - 2, hp_w + 4, hp_h + 4))
    pygame.draw.rect(surf, (50, 54, 62), (hp_x, hp_y, hp_w, hp_h))
    pygame.draw.rect(surf, (80, 200, 120), (hp_x, hp_y, int(hp_w * ratio), hp_h))
    hp_label = f"HP {focus.health:.0f}/{focus.max_health:.0f}"
    if spectate:
        hp_label = "Executioner " + hp_label
    surf.blit(body_f.render(hp_label, True, (230, 234, 240)), (hp_x, hp_y - 24))

    # --- Abilities as circles (bottom-right) ---
    d = char_registry.get_definition(focus.char_id)
    key_names = ("Q", "E", "R")
    if d:
        abilities = list(d["abilities"])
        slot_r = 34
        gap = 84
        start_x = w - 24 - slot_r - gap * (len(abilities) - 1)
        cy = h - 52
        for i, ab in enumerate(abilities):
            cx = start_x + i * gap
            aid = ab["id"]
            cd_total = float(ab.get("cooldown") or 0.0)
            last = focus.ability_cooldowns.get(aid, -9999.0)
            cd_left = max(0.0, cd_total - (now - last))
            ready = cd_left <= 0.0
            base_col = (26, 32, 42) if ready else (34, 30, 30)
            rim_col = (120, 220, 170) if ready else (190, 96, 96)
            pygame.draw.circle(surf, base_col, (cx, cy), slot_r)
            pygame.draw.circle(surf, rim_col, (cx, cy), slot_r, width=3)
            if cd_total > 0.0 and cd_left > 0.0:
                p = min(1.0, cd_left / cd_total)
                arc_rect = pygame.Rect(cx - slot_r, cy - slot_r, slot_r * 2, slot_r * 2)
                pygame.draw.arc(
                    surf,
                    (230, 120, 120),
                    arc_rect,
                    -math.pi / 2,
                    -math.pi / 2 + math.tau * p,
                    width=4,
                )
            key_txt = body_f.render(key_names[i] if i < len(key_names) else str(i + 1), True, (236, 242, 248))
            surf.blit(key_txt, (cx - key_txt.get_width() // 2, cy - key_txt.get_height() // 2 - 8))
            if cd_left > 0.0:
                cd_txt = body_f.render(f"{cd_left:.1f}", True, (245, 170, 170))
                surf.blit(cd_txt, (cx - cd_txt.get_width() // 2, cy + 6))
            else:
                name_txt = body_f.render(ab["name"][:8], True, (176, 214, 196))
                surf.blit(name_txt, (cx - name_txt.get_width() // 2, cy + 6))

    if killer is not None:
        draw_exit_direction_ui(surf, focus, exit_rects, round_start_unix, round_duration_initial, killer, combatants, body_f)

    # Grab escape (2011X): mash SPACE — progress bar
    for c in combatants:
        if c.is_human and c.grabbed_by:
            bx = w // 2 - 200
            by = h - 108
            pygame.draw.rect(surf, (24, 26, 34), (bx, by, 400, 58))
            pygame.draw.rect(surf, (80, 90, 110), (bx, by, 400, 58), width=2)
            surf.blit(
                title_f.render("MASH SPACE — break free!", True, (255, 220, 130)),
                (bx + 24, by + 10),
            )
            pr = max(0.0, min(1.0, c.grab_break_progress / 100.0))
            pygame.draw.rect(surf, (45, 48, 58), (bx + 24, by + 40, 352, 12))
            pygame.draw.rect(surf, (90, 200, 255), (bx + 24, by + 40, int(352 * pr), 12))
            break


def draw_lobby(
    surf: pygame.Surface,
    human_role: str,
    executioner_id: str,
    human_survivor_id: str | None,
    bot_only: bool,
    font: pygame.font.Font,
) -> None:
    surf.fill((14, 16, 20))
    surv_label = "Random" if not human_survivor_id else (
        (char_registry.get_definition(human_survivor_id) or {}).get("display_name", human_survivor_id)
    )
    lines = [
        "Outcome-style (Python / pygame) — top-down 2D — PC controls",
        "Roster pool: Sonic, Tails, Knuckles, Amy, Eggman, Metal Sonic, Cream",
        "Each match: 6 survivors + 1 executioner — you + 6 bots",
        "Round: 3:00 (Sonic/Knuckles + LMS file = song length) — exits open after 75% of round",
        "Survivors win only if all 6 (including you) escape",
        "Executioners: 2011X, Kollosios",
        "",
        "In-match: WASD move · Left Shift sprint · Q / E / R abilities",
        "Executioner: hold LMB for basic melee + Q/E/R for abilities",
        "",
        "1 = You play selected survivor + 5 survivor bots + killer bot",
        "2 = You play Executioner + 6 survivor bots",
        "3 = Bot-only (all AI; camera follows killer)",
        "Q / E (lobby only) = pick killer: 2011X / Kollosios",
        "Z / X (lobby only) = pick survivor: Random/Sonic/Tails/Knuckles/Amy/Eggman/Metal Sonic/Cream",
        f"Selected: {'BOT ONLY' if bot_only else human_role}    Survivor: {surv_label}    Killer: {executioner_id}",
        "",
        "SPACE = Start match    ESC = Quit",
    ]
    y = 80
    for line in lines:
        surf.blit(font.render(line, True, (230, 234, 240)), (60, y))
        y += 32


def draw_end(
    surf: pygame.Surface,
    winner: str,
    font: pygame.font.Font,
) -> None:
    overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    surf.blit(overlay, (0, 0))
    msg = f"{winner} win!"
    t = font.render(msg, True, (250, 252, 255))
    surf.blit(t, (surf.get_width() // 2 - t.get_width() // 2, surf.get_height() // 2 - 40))
    s = font.render("R = rematch (lobby)   ESC = quit", True, (200, 204, 210))
    surf.blit(s, (surf.get_width() // 2 - s.get_width() // 2, surf.get_height() // 2 + 10))
