"""On-screen HUD: health, timer, abilities, roster."""

from __future__ import annotations

import math
import time

import pygame

from outcome_game.arena_maps import ArenaTheme
from outcome_game.character_definitions import registry as char_registry
from outcome_game.topdown_actor_draw import draw_topdown_combatant
from outcome_game.constants import (
    ESCAPE_OPENS_AT_SECONDS_REMAINING,
    METAL_CHARGE_BEATUP_ANIM_SECONDS,
    METAL_DEATH_BURST_VISUAL_SECONDS,
)
from outcome_game.entities import Combatant
from outcome_game.match_service import exits_available_for_escape, is_escape_window_open
from outcome_game.x2011_rage import rage_active

# Full-screen dread vignette ramps up in this many seconds before exits unlock
EXIT_DREAD_WARNING_SECONDS = 28.0

_COL_RING_GRAY = (105, 107, 112)
_COL_RING_GREEN = (42, 188, 108)


def _screen_ray_to_margin_edge(
    cx: float,
    cy: float,
    ux: float,
    uy: float,
    vw: int,
    vh: int,
    margin: float,
) -> tuple[float, float]:
    """Ray from screen center through direction; first hit on inner rectangle."""
    best_t = float("inf")
    best_xy = (cx, cy)
    m = margin
    rm = vw - margin
    bm = vh - margin

    if abs(ux) > 1e-9:
        for x_edge in (m, rm):
            t = (x_edge - cx) / ux
            y = cy + t * uy
            if t >= 0 and m <= y <= bm and t < best_t:
                best_t = t
                best_xy = (x_edge, y)
    if abs(uy) > 1e-9:
        for y_edge in (m, bm):
            t = (y_edge - cy) / uy
            x = cx + t * ux
            if t >= 0 and m <= x <= rm and t < best_t:
                best_t = t
                best_xy = (x, y_edge)

    return best_xy


def _draw_downed_markers_and_metal_burst(
    surf: pygame.Surface,
    combatants: list[Combatant],
    ox: float,
    oy: float,
    viewer: Combatant | None,
    now: float,
) -> None:
    vw, vh = surf.get_size()

    for c in combatants:
        if c.char_id != "MetalSonic" or not c.dead:
            continue
        if c.metal_death_burst_until <= now:
            continue
        bx = (c.metal_death_origin_x or c.x) + ox
        by = (c.metal_death_origin_y or c.y) + oy
        span = max(METAL_DEATH_BURST_VISUAL_SECONDS, 1e-6)
        u = 1.0 - max(0.0, min(1.0, (c.metal_death_burst_until - now) / span))
        for i in range(6):
            rr = int(28 + i * 52 + u * 140)
            pygame.draw.circle(surf, (255, 125 + i * 15, 45), (int(bx), int(by)), rr, width=3)

    if viewer is None or viewer.dead or viewer.downed or viewer.escaped:
        return
    if not viewer.alive():
        return

    margin = 40.0
    cx, cy = vw * 0.5, vh * 0.5
    for target in combatants:
        if not target.downed:
            continue
        if target.team != "Survivors":
            continue
        sx = target.x + ox
        sy = target.y + oy
        if margin <= sx <= vw - margin and margin <= sy <= vh - margin:
            tip_x, tip_y = sx, sy - int(target.radius) - 22
            pygame.draw.polygon(
                surf,
                (255, 75, 95),
                [(tip_x, tip_y), (tip_x - 11, tip_y + 20), (tip_x + 11, tip_y + 20)],
            )
            continue
        dx, dy = sx - cx, sy - cy
        dist = math.hypot(dx, dy) or 1e-6
        ux, uy = dx / dist, dy / dist
        ex, ey = _screen_ray_to_margin_edge(cx, cy, ux, uy, vw, vh, margin)
        ang = math.atan2(uy, ux)
        tip_x = ex + math.cos(ang) * 18
        tip_y = ey + math.sin(ang) * 18
        bx = ex - math.cos(ang) * 8
        by = ey - math.sin(ang) * 8
        pw = math.cos(ang + 1.45) * 11
        ph = math.sin(ang + 1.45) * 11
        pygame.draw.polygon(
            surf,
            (255, 65, 85),
            [(tip_x, tip_y), (bx + pw, by + ph), (bx - pw, by - ph)],
        )


def _draw_exit_countdown_ring(
    surf: pygame.Surface,
    cx: int,
    cy: int,
    radius: int,
    width: int,
    now: float,
    round_start_unix: float,
    round_end_unix: float,
) -> None:
    """
    Ring arc fills clockwise toward the moment exits unlock (timer hits ESCAPE_OPENS_AT_SECONDS_REMAINING).
    Colour shifts from gray toward green as that moment approaches; solid green once open.
    """
    rect = pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2)
    remain = round_end_unix - now
    if remain <= ESCAPE_OPENS_AT_SECONDS_REMAINING:
        pygame.draw.circle(surf, _COL_RING_GREEN, (cx, cy), radius, width=width)
        return

    unlock_at = round_end_unix - ESCAPE_OPENS_AT_SECONDS_REMAINING
    span = unlock_at - round_start_unix
    if span <= 1e-6:
        sweep = 1.0
    else:
        sweep = min(1.0, max(0.0, (now - round_start_unix) / span))

    arc_col = tuple(
        int(_COL_RING_GRAY[i] + (_COL_RING_GREEN[i] - _COL_RING_GRAY[i]) * sweep) for i in range(3)
    )

    pygame.draw.circle(surf, (28, 30, 36), (cx, cy), radius, width=width)

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
    round_end_unix: float,
    killer: Combatant,
    combatants: list[Combatant],
    small_font: pygame.font.Font,
) -> None:
    """Bottom-left compass toward nearest exit when escapes are active (survivor focus only)."""
    now = time.monotonic()
    if not exits_available_for_escape(now, round_end_unix, killer, combatants):
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
    pulse = 0.65 + 0.35 * math.sin(now * 11.0)
    urg_w = max(4, int(4 + pulse * 5))
    gline = int(200 + 55 * pulse)
    arr_col = (110, gline, 175)
    pygame.draw.line(surf, arr_col, (ccx, ccy), (tip_x, tip_y), urg_w)
    wing = 11.0
    a_back = angle + math.pi
    pygame.draw.polygon(
        surf,
        arr_col,
        [
            (tip_x, tip_y),
            (tip_x + math.cos(a_back - 0.45) * wing, tip_y + math.sin(a_back - 0.45) * wing),
            (tip_x + math.cos(a_back + 0.45) * wing, tip_y + math.sin(a_back + 0.45) * wing),
        ],
    )
    surf.blit(small_font.render("Nearest exit — NOW", True, (235, 255, 230)), (ccx - 72, ccy - rad - 24))


def seconds_until_escape_window_opens(now: float, round_end_unix: float) -> float:
    """
    Seconds until exits unlock: ``remain - ESCAPE_OPENS_AT_SECONDS_REMAINING``.
    Negative means exits are already usable (or round ended).
    """
    remain = round_end_unix - now
    return remain - ESCAPE_OPENS_AT_SECONDS_REMAINING


def _draw_fear_vignette(surf: pygame.Surface, intensity: float, now: float) -> None:
    """Dark blood-red edge fog + heartbeat pulse before exits unlock."""
    w, h = surf.get_size()
    pulse = 0.88 + 0.12 * math.sin(now * 6.8)
    intensity = max(0.0, min(1.0, intensity * pulse))
    edge = int(28 + 115 * intensity)
    base_a = int(28 + 165 * intensity)
    v = pygame.Surface((w, h), pygame.SRCALPHA)
    ac = min(220, base_a)
    red = (110, 8, 16, ac)
    pygame.draw.rect(v, red, (0, 0, w, edge))
    pygame.draw.rect(v, red, (0, h - edge, w, edge))
    pygame.draw.rect(v, red, (0, 0, edge, h))
    pygame.draw.rect(v, red, (w - edge, 0, edge, h))
    # Corner weight
    ck = edge // 2
    pygame.draw.rect(v, (40, 2, 8, min(255, ac + 35)), (0, 0, ck, ck))
    pygame.draw.rect(v, (40, 2, 8, min(255, ac + 35)), (w - ck, 0, ck, ck))
    pygame.draw.rect(v, (40, 2, 8, min(255, ac + 35)), (0, h - ck, ck, ck))
    pygame.draw.rect(v, (40, 2, 8, min(255, ac + 35)), (w - ck, h - ck, ck, ck))
    surf.blit(v, (0, 0))


def _draw_rage_sealed_overlay(surf: pygame.Surface, w: int, h: int, now: float) -> None:
    """When 2011X rage seals exits — harsh red wash; stays in color (no grayscale)."""
    flash = 0.55 + 0.45 * math.sin(now * 14.0)
    ov = pygame.Surface((w, h), pygame.SRCALPHA)
    ov.fill((180, 25, 35, int(55 + 55 * flash)))
    surf.blit(ov, (0, 0))
    bar_h = 52
    pygame.draw.rect(surf, (28, 6, 10), (0, 0, w, bar_h))
    pygame.draw.line(surf, (255, 90, 90), (0, bar_h), (w, bar_h), 2)
    bf = pygame.font.SysFont("segoeuisemibold", 26)
    txt = bf.render("EXITS SEALED — SURVIVE THE RAGE", True, (255, 210, 210))
    surf.blit(txt, (w // 2 - txt.get_width() // 2, 12))


def _draw_escape_open_banner(
    surf: pygame.Surface,
    w: int,
    h: int,
    focus: Combatant,
    spectate: bool,
    now: float,
) -> None:
    """After grayscale: stark monochrome call-to-action."""
    pulse = 0.92 + 0.08 * math.sin(now * 10.0)
    band_h = 112
    band = pygame.Surface((w, band_h), pygame.SRCALPHA)
    band.fill((12, 12, 14, int(200 * pulse)))
    surf.blit(band, (0, 0))
    pygame.draw.line(surf, (220, 220, 225), (0, band_h), (w, band_h), 3)

    big = pygame.font.SysFont("segoeuisemibold", 38)
    sub = pygame.font.SysFont("segoeuisemibold", 22)
    title = big.render("EXITS OPEN", True, (248, 248, 252))
    surf.blit(title, (w // 2 - title.get_width() // 2, 10))

    if spectate:
        line = sub.render("Escape zones active — survivors must reach them", True, (190, 192, 198))
    elif focus.team == "Survivors" and focus.alive() and not focus.escaped:
        line = sub.render("RUN — HOLD SHIFT TO SPRINT — STAND IN A ZONE 3s", True, (210, 212, 218))
    else:
        line = sub.render("Stop survivors from reaching the exits", True, (200, 200, 206))
    surf.blit(line, (w // 2 - line.get_width() // 2, 58))


def apply_escape_post_processing(
    surf: pygame.Surface,
    *,
    now: float,
    round_end_unix: float,
    killer: Combatant | None,
    combatants: list[Combatant],
    focus: Combatant,
    spectate: bool,
) -> None:
    """
    Layer fear before exits unlock; full grayscale when escapes are actually usable;
    red alarm when 2011X rage seals exits during the window.
    """
    w, h = surf.get_size()
    time_until = seconds_until_escape_window_opens(now, round_end_unix)

    rage_sealed = (
        killer is not None
        and killer.char_id == "X2011"
        and is_escape_window_open(now, round_end_unix)
        and rage_active(killer, now, combatants)
    )

    if rage_sealed:
        _draw_rage_sealed_overlay(surf, w, h, now)
        return

    if time_until > 0 and time_until <= EXIT_DREAD_WARNING_SECONDS:
        ramp = 1.0 - (time_until / EXIT_DREAD_WARNING_SECONDS)
        _draw_fear_vignette(surf, ramp, now)
        # Thin scanlines (unease)
        scan = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(0, h, 4):
            pygame.draw.line(scan, (0, 0, 0, 14), (0, y), (w, y))
        surf.blit(scan, (0, 0))

    escape_live = killer is not None and exits_available_for_escape(
        now, round_end_unix, killer, combatants
    )
    if escape_live:
        dup = surf.copy()
        gs = pygame.transform.grayscale(dup)
        surf.blit(gs, (0, 0))
        _draw_escape_open_banner(surf, w, h, focus, spectate, now)


def draw_world(
    surf: pygame.Surface,
    combatants: list[Combatant],
    camera_x: float,
    camera_y: float,
    exit_rects_world: list[pygame.Rect],
    wall_rects_world: list[pygame.Rect],
    arena_w: float,
    arena_h: float,
    theme: ArenaTheme,
    round_end_unix: float | None = None,
    killer: Combatant | None = None,
    viewer: Combatant | None = None,
) -> None:
    """Draw arena floor, walls, exit zones, actors (world space -> screen)."""
    surf.fill(theme.bg_outside)
    ox, oy = -camera_x, -camera_y

    tw = 100
    ix = 0
    while ix * tw < arena_w:
        iy = 0
        while iy * tw < arena_h:
            wx = ix * tw
            wy = iy * tw
            rw = min(tw, int(arena_w - wx))
            rh = min(tw, int(arena_h - wy))
            col = theme.floor_a if (ix + iy) % 2 == 0 else theme.floor_b
            pygame.draw.rect(surf, col, (int(wx + ox), int(wy + oy), rw, rh))
            iy += 1
        ix += 1

    # Light structural grid (every few tiles)
    step = tw * 4
    gl = theme.grid_line
    wx = 0
    while wx <= arena_w:
        pygame.draw.line(surf, gl, (int(wx + ox), int(oy)), (int(wx + ox), int(arena_h + oy)), 1)
        wx += step
    wy = 0
    while wy <= arena_h:
        pygame.draw.line(surf, gl, (int(ox), int(wy + oy)), (int(arena_w + ox), int(wy + oy)), 1)
        wy += step

    border = pygame.Rect(int(ox), int(oy), int(arena_w), int(arena_h))
    pygame.draw.rect(surf, theme.border, border, width=6)
    inner = border.inflate(-14, -14)
    pygame.draw.rect(surf, theme.border_accent, inner, width=2)

    for w in wall_rects_world:
        wr = w.move(ox, oy)
        pygame.draw.rect(surf, theme.wall_fill, wr)
        pygame.draw.line(
            surf,
            theme.wall_highlight,
            (wr.left, wr.top + 1),
            (wr.right - 1, wr.top + 1),
            2,
        )
        pygame.draw.rect(surf, theme.wall_edge, wr, width=2)

    font = pygame.font.SysFont("segoeui", 18)
    now = time.monotonic()
    rage_hide_exits = False
    locked = False
    if round_end_unix is not None:
        if killer is not None:
            if exits_available_for_escape(now, round_end_unix, killer, combatants):
                locked = False
            elif (
                is_escape_window_open(now, round_end_unix)
                and killer.char_id == "X2011"
                and rage_active(killer, now, combatants)
            ):
                rage_hide_exits = True
            else:
                locked = not is_escape_window_open(now, round_end_unix)
        else:
            locked = not is_escape_window_open(now, round_end_unix)

    if not rage_hide_exits:
        multi = len(exit_rects_world) > 1
        for i, raw in enumerate(exit_rects_world):
            er = raw.move(ox, oy)
            label = f"EXIT {i + 1}" if multi else "EXIT"
            if locked:
                pygame.draw.rect(surf, theme.exit_locked_border, er, width=4)
                surf.blit(
                    font.render(f"{label} (locked)", True, theme.exit_locked_text),
                    (er.centerx - (58 if multi else 52), er.centery - 10),
                )
            else:
                pygame.draw.rect(surf, theme.exit_open_border, er, width=4)
                surf.blit(
                    font.render(label, True, theme.exit_open_text),
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

    # Metal Sonic trail during killer charge.
    for c in combatants:
        if c.char_id != "MetalSonic" or not c.metal_charge_trail:
            continue
        for tx, ty, tt in c.metal_charge_trail:
            age = now - tt
            if age < 0.0 or age > 0.34:
                continue
            fade = 1.0 - (age / 0.34)
            rr = max(3, int(c.radius * (0.26 + 0.26 * fade)))
            sx = tx + ox
            sy = ty + oy
            pygame.draw.circle(surf, (145, 188, 238), (int(sx), int(sy)), rr, width=2)

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
            # Metal has no downed state — draw a short-lived wreck read so the bot doesn't read as "deleted".
            if c.char_id == "MetalSonic" and c.metal_death_burst_until > now:
                sx = (c.metal_death_origin_x or c.x) + ox
                sy = (c.metal_death_origin_y or c.y) + oy
                r = max(8, int(c.radius))
                pygame.draw.circle(surf, (72, 82, 102), (int(sx), int(sy)), r)
                pygame.draw.circle(surf, (38, 44, 58), (int(sx), int(sy)), r, width=2)
            continue
        sx = c.x + ox
        sy = c.y + oy
        vis_r = c.radius * (1.22 if c.char_id == "X2011" else 1.0)
        draw_topdown_combatant(surf, c, sx, sy)
        if c.downed:
            pygame.draw.circle(surf, (140, 35, 45), (int(sx), int(sy)), int(vis_r + 10), width=4)
        drop_dash_finale = c.char_id == "Sonic" and c.drop_dash_finale_until > now
        metal_charge_windup = c.char_id == "MetalSonic" and c.metal_charge_windup_until > now
        if c.ability_flash_until > now or drop_dash_finale or metal_charge_windup:
            if drop_dash_finale:
                pulse = 6.0 + (math.sin(now * 28.0) * 0.5 + 0.5) * 5.0
            elif metal_charge_windup:
                pulse = 7.0 + (math.sin(now * 42.0) * 0.5 + 0.5) * 7.0
            else:
                pulse = 1.0 + (c.ability_flash_until - now) * 3.0
            fr = int(vis_r + 4 + min(9.0, pulse * 3.0))
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
        if c.downed:
            name += " — DOWN"
        t = font.render(name[:22], True, (230, 234, 240))
        surf.blit(t, (int(sx - t.get_width() // 2), int(sy - vis_r - 22)))

    # Metal Sonic — wall slam debris + beat-up strike lines
    for c in combatants:
        if c.char_id != "MetalSonic" or c.dead:
            continue
        for x, y, _, _, exp, col in c.metal_charge_debris:
            if exp <= now:
                continue
            pygame.draw.circle(surf, col, (int(x + ox), int(y + oy)), max(2, int(3)))
        if c.metal_beatup_anim_until > now:
            sx = c.x + ox
            sy = c.y + oy
            rem = c.metal_beatup_anim_until - now
            pulsed = 1.0 - max(0.0, min(1.0, rem / METAL_CHARGE_BEATUP_ANIM_SECONDS))
            ang_base = now * 48.0
            for i in range(7):
                ang = ang_base + i * (math.tau / 7.0) + (i % 2) * 0.35 * math.sin(now * 58.0)
                rad = c.radius + 10 + i * 6 * (0.35 + 0.65 * pulsed)
                x2 = sx + math.cos(ang) * rad
                y2 = sy + math.sin(ang) * rad
                pygame.draw.line(
                    surf,
                    (255, 210, 100),
                    (int(sx), int(sy)),
                    (int(x2), int(y2)),
                    max(2, int(2 + pulsed * 3)),
                )
                pygame.draw.line(
                    surf,
                    (255, 95, 65),
                    (int(sx + math.cos(ang + 0.12) * 5), int(sy + math.sin(ang + 0.12) * 5)),
                    (int(x2), int(y2)),
                    2,
                )

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

    _draw_downed_markers_and_metal_burst(surf, combatants, ox, oy, viewer, now)


def draw_hud(
    surf: pygame.Surface,
    focus: Combatant,
    combatants: list[Combatant],
    round_end_unix: float,
    round_start_unix: float,
    exit_rects: list[pygame.Rect],
    fonts: tuple[pygame.font.Font, pygame.font.Font],
    *,
    spectate: bool = False,
    killer: Combatant | None = None,
    map_display_name: str | None = None,
    seconds_until_exit_open: float | None = None,
) -> None:
    """HUD layout: timer top-center, health bottom-left, ability circles bottom-right."""
    title_f, body_f = fonts
    w, h = surf.get_size()
    now = time.monotonic()

    # --- Timer (top-middle) ---
    remain = max(0.0, round_end_unix - now)
    m, s = divmod(int(remain), 60)

    su_o = seconds_until_exit_open
    dread_active = (
        su_o is not None and su_o > 0 and su_o <= EXIT_DREAD_WARNING_SECONDS
    )
    if dread_active and su_o is not None:
        ur = 1.0 - su_o / EXIT_DREAD_WARNING_SECONDS
        rim_pulse = int(72 + 88 * ur + 48 * ur * abs(math.sin(now * 9.2)))
        timer_col = (255, max(78, int(248 - 155 * ur)), max(58, int(252 - 190 * ur)))
        fill_bg = (int(20 + 38 * ur), int(10 + 14 * ur), int(12 + 18 * ur))
        rim_timer = (min(255, rim_pulse), int(38 + 55 * ur), int(40 + 35 * ur))
    else:
        timer_col = (245, 248, 252)
        fill_bg = (14, 18, 24)
        rim_timer = (70, 80, 96)

    timer_txt = title_f.render(f"{m:02d}:{s:02d}", True, timer_col)
    tpad_x, tpad_y = 18, 10
    ring_r = 22
    ring_gap = 10
    tw = timer_txt.get_width() + tpad_x * 2
    th = timer_txt.get_height() + tpad_y * 2
    total_bar_w = ring_r * 2 + ring_gap + tw
    bar_left = w // 2 - total_bar_w // 2
    ring_cx = bar_left + ring_r
    timer_box = pygame.Rect(bar_left + ring_r * 2 + ring_gap, 14, tw, th)
    ring_cy = timer_box.centery
    pygame.draw.rect(surf, fill_bg, timer_box, border_radius=12)
    pygame.draw.rect(surf, rim_timer, timer_box, width=2, border_radius=12)
    surf.blit(timer_txt, (timer_box.centerx - timer_txt.get_width() // 2, timer_box.y + tpad_y))

    _draw_exit_countdown_ring(
        surf,
        ring_cx,
        ring_cy,
        ring_r,
        4,
        now,
        round_start_unix,
        round_end_unix,
    )

    hud_stack_bottom = timer_box.bottom
    if dread_active and su_o is not None:
        sec_show = max(0.0, su_o)
        ur = 1.0 - sec_show / EXIT_DREAD_WARNING_SECONDS
        urgency = body_f.render(
            f"EXITS OPEN IN {math.ceil(sec_show)}s  ·  GET READY",
            True,
            (255, int(130 - 55 * ur), int(105 - 45 * ur)),
        )
        uy = hud_stack_bottom + 8
        surf.blit(urgency, (w // 2 - urgency.get_width() // 2, uy))
        hud_stack_bottom = uy + urgency.get_height() + 6

    if map_display_name:
        map_f = pygame.font.SysFont("segoeui", 14)
        mt = map_f.render(map_display_name, True, (175, 185, 200))
        surf.blit(mt, (16, hud_stack_bottom + 10))

    # --- Health (bottom-left) ---
    hp_x = 14
    hp_w = 300
    hp_h = 18
    hp_y = h - 44

    if focus.team == "Survivors" and focus.alive() and not focus.downed and not focus.escaped:
        for o in combatants:
            if not o.downed:
                continue
            if math.hypot(focus.x - o.x, focus.y - o.y) <= focus.radius + o.radius + 2.0:
                hint = body_f.render("Stay in contact to revive", True, (255, 215, 140))
                hint_y = hp_y - 56 - hint.get_height()
                surf.blit(hint, (w // 2 - hint.get_width() // 2, hint_y))
                break
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
        draw_exit_direction_ui(surf, focus, exit_rects, round_end_unix, killer, combatants, body_f)

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


def _lobby_section_title(surf: pygame.font.Font, text: str, color: tuple[int, int, int]) -> pygame.Surface:
    return surf.render(text.upper(), True, color)


def _wrap_lobby_line(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    """Split a single line into multiple lines that fit max_width (for menu columns)."""
    if not text:
        return [""]
    words = text.split()
    if not words:
        return [""]
    out: list[str] = []
    line_words: list[str] = []
    for word in words:
        trial = " ".join(line_words + [word])
        if font.size(trial)[0] <= max_width:
            line_words.append(word)
            continue
        if line_words:
            out.append(" ".join(line_words))
            line_words = []
        if font.size(word)[0] <= max_width:
            line_words.append(word)
            continue
        chunk = ""
        for ch in word:
            t2 = chunk + ch
            if font.size(t2)[0] <= max_width:
                chunk = t2
            else:
                if chunk:
                    out.append(chunk)
                chunk = ch
        if chunk:
            line_words = [chunk]
    if line_words:
        out.append(" ".join(line_words))
    return out if out else [""]


def draw_lobby(
    surf: pygame.Surface,
    human_role: str,
    executioner_id: str,
    human_survivor_id: str | None,
    bot_only: bool,
    font: pygame.font.Font,
) -> None:
    w, h = surf.get_size()
    now = time.monotonic()
    pulse = 0.5 + 0.5 * math.sin(now * 2.2)

    surf.fill((8, 10, 16))
    # Soft vignette (bottom-heavy)
    vignette = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(12):
        a = min(80, 8 + i * 6)
        pygame.draw.rect(vignette, (0, 0, 0, a), (0, h - (i + 1) * (h // 14), w, h // 14))
    surf.blit(vignette, (0, 0))

    top_ac = int(28 + 35 * pulse)
    pygame.draw.rect(surf, (top_ac, 72, 128), (0, 0, w, 5))
    pygame.draw.line(surf, (110, 185, 245), (0, 5), (w, 5), 1)

    title_font = pygame.font.SysFont("segoeuisemibold", 46)
    sub_font = pygame.font.SysFont("segoeui", 17)
    sec_font = pygame.font.SysFont("segoeuisemibold", 15)
    body_font = pygame.font.SysFont("segoeui", 16)
    lobby_body = pygame.font.SysFont("segoeui", 14)
    small_font = pygame.font.SysFont("segoeui", 14)

    surv_label = "Random" if not human_survivor_id else (
        (char_registry.get_definition(human_survivor_id) or {}).get("display_name", human_survivor_id)
    )

    title_s = title_font.render("Outcome Game", True, (248, 250, 255))
    surf.blit(title_s, (w // 2 - title_s.get_width() // 2, 42))
    sub = sub_font.render(
        "Top-down arena prototype · pygame · PC controls",
        True,
        (152, 164, 182),
    )
    surf.blit(sub, (w // 2 - sub.get_width() // 2, 94))

    underline_w = min(420, int(260 + 160 * pulse))
    ux0 = w // 2 - underline_w // 2
    pygame.draw.line(surf, (90, 170, 235), (ux0, 126), (ux0 + underline_w, 126), 2)

    panel_w = min(940, w - 72)
    panel_x = (w - panel_w) // 2
    panel_y = 148
    panel_h = 468
    pygame.draw.rect(surf, (14, 18, 28), (panel_x, panel_y, panel_w, panel_h), border_radius=20)
    pygame.draw.rect(surf, (48, 58, 76), (panel_x, panel_y, panel_w, panel_h), width=2, border_radius=20)

    # Inner glow along top edge of panel
    hi = pygame.Surface((panel_w - 8, 3), pygame.SRCALPHA)
    hi.fill((120, 175, 235, 35))
    surf.blit(hi, (panel_x + 4, panel_y + 6))

    pad = 28
    cx = panel_x + pad
    cy = panel_y + pad
    col_gap = 36
    col_w = (panel_w - pad * 2 - col_gap) // 2
    text_max_w = max(120, col_w - 10)
    line_skip = 18

    ts = _lobby_section_title(sec_font, "Match setup (lobby keys)", (130, 205, 255))
    surf.blit(ts, (cx, cy))
    cy += 26

    setup_lines = [
        "6 survivors + 1 executioner · exits unlock in the last 80 seconds on the timer",
        "Downed allies revive when you touch them (once each); Metal Sonic cannot be revived.",
        "Survivors win if everyone escapes; killers hunt them down",
        "Arena layout & colors pick randomly each match (four maps).",
        "",
        "1  Survivor + survivor bots + killer bot",
        "2  You are the Executioner + survivor bots",
        "3  Bot-only match (camera follows killer)",
        "",
        "Q / E  Choose killer (2011X or Kollosios)",
        "Z / X  Cycle survivor (Random · Sonic · Tails · …)",
    ]
    for line in setup_lines:
        if line == "":
            cy += line_skip
            continue
        for part in _wrap_lobby_line(lobby_body, line, text_max_w):
            surf.blit(lobby_body.render(part, True, (205, 212, 222)), (cx, cy))
            cy += line_skip

    left_bottom = cy

    cy = panel_y + pad
    cx2 = panel_x + pad + col_w + col_gap

    ts2 = _lobby_section_title(sec_font, "In-match controls", (255, 205, 140))
    surf.blit(ts2, (cx2, cy))
    cy += 26

    ctrl_lines = [
        "WASD  Move",
        "Shift  Sprint (survivors)",
        "Q · E · R  Abilities",
        "",
        "Executioner: hold LMB — basic melee",
        "Survivors & killer use abilities above",
    ]
    for line in ctrl_lines:
        if line == "":
            cy += line_skip
            continue
        for part in _wrap_lobby_line(lobby_body, line, text_max_w):
            surf.blit(lobby_body.render(part, True, (205, 212, 222)), (cx2, cy))
            cy += line_skip

    right_bottom = cy
    content_bottom = max(left_bottom, right_bottom)

    roster_str = (
        "Roster: Sonic, Tails, Knuckles, Amy, Eggman, Metal Sonic, Cream · "
        "Executioners: 2011X, Kollosios"
    )
    roster_parts = _wrap_lobby_line(small_font, roster_str, panel_w - 40)
    roster_line_skip = 15
    roster_block_h = max(roster_line_skip, len(roster_parts) * roster_line_skip)
    strip_h = 52
    panel_bottom = panel_y + panel_h
    # Roster above strip; push strip down if wrapped columns need more room
    strip_y = max(
        panel_y + panel_h - 76,
        content_bottom + 12 + roster_block_h + 10,
    )
    strip_y = min(strip_y, panel_bottom - strip_h)
    roster_y0 = strip_y - 8 - roster_block_h
    if roster_y0 < content_bottom + 6:
        roster_y0 = content_bottom + 6

    # Selection strip
    pygame.draw.rect(surf, (22, 28, 40), (panel_x + 14, strip_y, panel_w - 28, strip_h), border_radius=12)
    pygame.draw.rect(surf, (58, 72, 92), (panel_x + 14, strip_y, panel_w - 28, strip_h), width=1, border_radius=12)

    role_disp = "BOT ONLY" if bot_only else human_role
    sel_txt = (
        f"Ready  ·  Role: {role_disp}  ·  Survivor: {surv_label}  ·  Killer: {executioner_id}"
    )
    sel_parts = _wrap_lobby_line(body_font, sel_txt, panel_w - 48)
    sel_line_h = 20
    sel_block = len(sel_parts) * sel_line_h
    sel_y0 = strip_y + max(8, (strip_h - sel_block) // 2)
    for i, sp in enumerate(sel_parts):
        st = body_font.render(sp, True, (232, 238, 248))
        surf.blit(st, (panel_x + (panel_w - st.get_width()) // 2, sel_y0 + i * sel_line_h))

    for i, rh in enumerate(roster_parts):
        rt = small_font.render(rh, True, (130, 138, 155))
        surf.blit(rt, (panel_x + (panel_w - rt.get_width()) // 2, roster_y0 + i * roster_line_skip))

    # Footer CTA
    footer_y = panel_y + panel_h + 28
    cta_w = 520
    cta_x = (w - cta_w) // 2
    pygame.draw.rect(surf, (26, 36, 52), (cta_x, footer_y, cta_w, 54), border_radius=14)
    pygame.draw.rect(surf, (100, 165, 235), (cta_x, footer_y, cta_w, 54), width=2, border_radius=14)
    cta_font = pygame.font.SysFont("segoeuisemibold", 22)
    cta_t = cta_font.render("SPACE   Start match", True, (255, 248, 235))
    surf.blit(cta_t, (w // 2 - cta_t.get_width() // 2, footer_y + 14))

    quit_t = small_font.render("ESC  Quit to desktop", True, (160, 168, 180))
    surf.blit(quit_t, (w // 2 - quit_t.get_width() // 2, footer_y + 62))


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
