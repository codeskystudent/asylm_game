"""Top-down Sonic-inspired silhouettes (primitive shapes, no external art)."""

from __future__ import annotations

import math

import pygame

from outcome_game.entities import Combatant


def _n(fx: float, fy: float) -> tuple[float, float]:
    d = math.hypot(fx, fy) or 1.0
    return fx / d, fy / d


def _perp(fx: float, fy: float) -> tuple[float, float]:
    return -fy, fx


def _poly_spike(
    surf: pygame.Surface,
    cx: float,
    cy: float,
    bx: float,
    by: float,
    lx: float,
    ly: float,
    r: float,
    i: float,
    color: tuple[int, int, int],
    outline: tuple[int, int, int] | None,
) -> None:
    """Single hedgehog quill toward back direction (bx,by), lateral offset index i."""
    tip_x = cx + bx * r * 1.02 + lx * i * r * 0.38
    tip_y = cy + by * r * 1.02 + ly * i * r * 0.38
    bc_x = cx + bx * r * 0.28 + lx * i * r * 0.34
    bc_y = cy + by * r * 0.28 + ly * i * r * 0.34
    pts = [
        (int(tip_x), int(tip_y)),
        (int(bc_x + lx * r * 0.26), int(bc_y + ly * r * 0.26)),
        (int(bc_x - lx * r * 0.26), int(bc_y - ly * r * 0.26)),
    ]
    pygame.draw.polygon(surf, color, pts)
    if outline:
        pygame.draw.polygon(surf, outline, pts, width=1)


def _draw_sonic_like(
    surf: pygame.Surface,
    c: Combatant,
    sx: float,
    sy: float,
    *,
    body: tuple[int, int, int],
    belly: tuple[int, int, int],
    shoe: tuple[int, int, int],
    outline: tuple[int, int, int],
    visual_scale: float = 1.0,
) -> None:
    fx, fy = _n(c.facing_x, c.facing_y)
    bx, by = -fx, -fy
    lx, ly = _perp(fx, fy)
    r = max(6.0, c.radius * visual_scale)
    ri = int(r)

    pygame.draw.circle(surf, body, (int(sx), int(sy)), ri)
    # Peach muzzle / belly toward facing
    belly_x = sx + fx * r * 0.38
    belly_y = sy + fy * r * 0.38
    pygame.draw.circle(surf, belly, (int(belly_x), int(belly_y)), max(4, int(r * 0.42)))

    # Shoes (ovals flanking forward)
    ox = lx * r * 0.42
    oy = ly * r * 0.42
    fx1 = sx + fx * r * 0.62 + ox
    fy1 = sy + fy * r * 0.62 + oy
    fx2 = sx + fx * r * 0.62 - ox
    fy2 = sy + fy * r * 0.62 - oy
    pygame.draw.ellipse(
        surf,
        shoe,
        (int(fx1 - r * 0.22), int(fy1 - r * 0.14), int(r * 0.44), int(r * 0.28)),
    )
    pygame.draw.ellipse(
        surf,
        shoe,
        (int(fx2 - r * 0.22), int(fy2 - r * 0.14), int(r * 0.44), int(r * 0.28)),
    )

    for i in (-1.0, 0.0, 1.0):
        _poly_spike(surf, sx, sy, bx, by, lx, ly, r, i, body, outline)

    pygame.draw.circle(surf, outline, (int(sx), int(sy)), ri, width=2)


def _escaped_tint(
    body: tuple[int, int, int],
    belly: tuple[int, int, int],
    shoe: tuple[int, int, int],
    outline: tuple[int, int, int],
) -> tuple[
    tuple[int, int, int],
    tuple[int, int, int],
    tuple[int, int, int],
    tuple[int, int, int],
]:
    def t(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
        return (
            min(255, int(rgb[0] * 0.72 + 95)),
            min(255, int(rgb[1] * 0.88 + 165)),
            min(255, int(rgb[2] * 0.78 + 115)),
        )

    return t(body), t(belly), t(shoe), t(outline)


def draw_topdown_combatant(surf: pygame.Surface, c: Combatant, sx: float, sy: float) -> None:
    """Draw one combatant as a top-down Sonic-style figure."""
    cid = c.char_id
    escaped = c.escaped

    if cid == "X2011":
        body, belly, shoe, outline = (26, 62, 128), (175, 135, 125), (140, 28, 38), (10, 22, 52)
        if escaped:
            body, belly, shoe, outline = _escaped_tint(body, belly, shoe, outline)
        _draw_sonic_like(
            surf,
            c,
            sx,
            sy,
            body=body,
            belly=belly,
            shoe=shoe,
            outline=outline,
            visual_scale=1.22,
        )
        return

    if cid == "Sonic":
        body, belly, shoe, outline = (43, 138, 232), (248, 198, 168), (218, 42, 52), (20, 70, 140)
        if escaped:
            body, belly, shoe, outline = _escaped_tint(body, belly, shoe, outline)
        _draw_sonic_like(surf, c, sx, sy, body=body, belly=belly, shoe=shoe, outline=outline)
        return

    if cid == "Tails":
        fx, fy = _n(c.facing_x, c.facing_y)
        bx, by = -fx, -fy
        lx, ly = _perp(fx, fy)
        r = max(6.0, c.radius)
        ri = int(r)
        body, belly, outline = (235, 125, 45), (255, 235, 205), (180, 85, 25)
        if escaped:
            body, belly, outline, _ = _escaped_tint(body, belly, outline, outline)
        pygame.draw.circle(surf, body, (int(sx), int(sy)), ri)
        pygame.draw.circle(surf, belly, (int(sx + fx * r * 0.35), int(sy + fy * r * 0.35)), max(4, int(r * 0.38)))
        # Twin tails (fluff behind)
        for sign in (-1.0, 1.0):
            tx = sx + bx * r * 0.85 + lx * sign * r * 0.55
            ty = sy + by * r * 0.85 + ly * sign * r * 0.55
            pygame.draw.circle(surf, (255, 210, 140), (int(tx), int(ty)), max(4, int(r * 0.36)))
            pygame.draw.circle(surf, outline, (int(tx), int(ty)), max(4, int(r * 0.36)), width=1)
        pygame.draw.circle(surf, outline, (int(sx), int(sy)), ri, width=2)
        return

    if cid == "Knuckles":
        fx, fy = _n(c.facing_x, c.facing_y)
        lx, ly = _perp(fx, fy)
        r = max(6.0, c.radius)
        ri = int(r)
        body, outline = (195, 48, 58), (120, 28, 38)
        glove = (245, 248, 252)
        if escaped:
            body, glove, outline, _ = _escaped_tint(body, glove, outline, outline)
        pygame.draw.circle(surf, body, (int(sx), int(sy)), ri)
        # White gloves forward
        gx = sx + fx * r * 0.55
        gy = sy + fy * r * 0.55
        pygame.draw.circle(surf, glove, (int(gx), int(gy)), max(5, int(r * 0.48)))
        pygame.draw.circle(surf, outline, (int(gx), int(gy)), max(5, int(r * 0.48)), width=2)
        # Knuckle spikes on sides
        bx, by = -fx, -fy
        for sign in (-1.0, 1.0):
            qx = sx + bx * r * 0.65 + lx * sign * r * 0.5
            qy = sy + by * r * 0.65 + ly * sign * r * 0.5
            pygame.draw.circle(surf, (165, 38, 48), (int(qx), int(qy)), max(3, int(r * 0.22)))
        pygame.draw.circle(surf, outline, (int(sx), int(sy)), ri, width=2)
        return

    if cid == "Amy":
        fx, fy = _n(c.facing_x, c.facing_y)
        bx, by = -fx, -fy
        lx, ly = _perp(fx, fy)
        r = max(6.0, c.radius)
        ri = int(r)
        pink, dark = (245, 140, 190), (170, 70, 120)
        if escaped:
            pink, dark, _, _ = _escaped_tint(pink, dark, dark, dark)
        pygame.draw.circle(surf, pink, (int(sx), int(sy)), ri)
        # Hair hedge behind
        for i in (-1.2, 0.0, 1.2):
            hx = sx + bx * r * 0.9 + lx * i * r * 0.35
            hy = sy + by * r * 0.9 + ly * i * r * 0.35
            pygame.draw.circle(surf, dark, (int(hx), int(hy)), max(4, int(r * 0.38)))
        pygame.draw.circle(surf, (255, 218, 228), (int(sx + fx * r * 0.32), int(sy + fy * r * 0.32)), max(3, int(r * 0.28)))
        pygame.draw.circle(surf, dark, (int(sx), int(sy)), ri, width=2)
        return

    if cid == "Cream":
        fx, fy = _n(c.facing_x, c.facing_y)
        r = max(6.0, c.radius)
        ri = int(r)
        fur, dress, outline = (255, 245, 210), (255, 165, 95), (210, 175, 120)
        if escaped:
            fur, dress, outline, _ = _escaped_tint(fur, dress, outline)
        pygame.draw.circle(surf, fur, (int(sx), int(sy)), ri)
        pygame.draw.circle(surf, dress, (int(sx + fx * r * 0.15), int(sy + fy * r * 0.15)), max(4, int(r * 0.35)))
        # Ears as two small lobes back
        bx, by = -fx, -fy
        for sign in (-1.0, 1.0):
            lx, ly = _perp(fx, fy)
            ex = sx + bx * r * 0.75 + lx * sign * r * 0.35
            ey = sy + by * r * 0.75 + ly * sign * r * 0.35
            pygame.draw.ellipse(surf, fur, (int(ex - r * 0.12), int(ey - r * 0.22), int(r * 0.24), int(r * 0.44)))
        pygame.draw.circle(surf, outline, (int(sx), int(sy)), ri, width=2)
        return

    if cid == "Eggman":
        fx, fy = _n(c.facing_x, c.facing_y)
        lx, ly = _perp(fx, fy)
        r = max(8.0, c.radius * 1.05)
        ri = int(r)
        coat, face, stash = (230, 190, 55), (248, 215, 185), (90, 55, 40)
        if escaped:
            coat, face, stash, _ = _escaped_tint(coat, face, stash)
        pygame.draw.circle(surf, coat, (int(sx), int(sy)), ri)
        pygame.draw.circle(surf, face, (int(sx + fx * r * 0.25), int(sy + fy * r * 0.25)), max(5, int(r * 0.5)))
        # Goggles
        gx = sx + fx * r * 0.42
        gy = sy + fy * r * 0.42
        pygame.draw.circle(surf, (240, 245, 250), (int(gx + lx * r * 0.22), int(gy + ly * r * 0.22)), max(3, int(r * 0.18)))
        pygame.draw.circle(surf, (240, 245, 250), (int(gx - lx * r * 0.22), int(gy - ly * r * 0.22)), max(3, int(r * 0.18)))
        # Mustache wedge
        pygame.draw.line(
            surf,
            stash,
            (int(sx + fx * r * 0.55 - lx * r * 0.35), int(sy + fy * r * 0.55 - ly * r * 0.35)),
            (int(sx + fx * r * 0.72), int(sy + fy * r * 0.72)),
            max(2, int(r * 0.08)),
        )
        pygame.draw.line(
            surf,
            stash,
            (int(sx + fx * r * 0.55 + lx * r * 0.35), int(sy + fy * r * 0.55 + ly * r * 0.35)),
            (int(sx + fx * r * 0.72), int(sy + fy * r * 0.72)),
            max(2, int(r * 0.08)),
        )
        pygame.draw.circle(surf, (160, 120, 40), (int(sx), int(sy)), ri, width=2)
        return

    if cid == "MetalSonic":
        fx, fy = _n(c.facing_x, c.facing_y)
        bx, by = -fx, -fy
        lx, ly = _perp(fx, fy)
        r = max(6.0, c.radius)
        ri = int(r)
        shell = (130, 148, 175)
        hi = (190, 205, 220)
        eye = (220, 40, 50)
        outline_col = (70, 85, 105)
        if escaped:
            shell, hi, eye, outline_col = _escaped_tint(shell, hi, eye, outline_col)
        pygame.draw.circle(surf, shell, (int(sx), int(sy)), ri)
        # Highlight arc (metallic)
        pygame.draw.arc(
            surf,
            hi,
            (int(sx - r * 0.85), int(sy - r * 0.85), int(r * 1.7), int(r * 1.7)),
            math.radians(200),
            math.radians(340),
            width=max(2, int(r * 0.12)),
        )
        # Single red eye forward
        ex = sx + fx * r * 0.38
        ey = sy + fy * r * 0.38
        pygame.draw.circle(surf, eye, (int(ex), int(ey)), max(3, int(r * 0.2)))
        pygame.draw.circle(surf, (40, 10, 15), (int(ex), int(ey)), max(3, int(r * 0.2)), width=1)
        # Fin ears back
        for sign in (-1.0, 1.0):
            tip_x = sx + bx * r * 0.95 + lx * sign * r * 0.25
            tip_y = sy + by * r * 0.95 + ly * sign * r * 0.25
            pygame.draw.polygon(
                surf,
                outline_col,
                [
                    (int(sx + bx * r * 0.4 + lx * sign * r * 0.2), int(sy + by * r * 0.4 + ly * sign * r * 0.2)),
                    (int(tip_x), int(tip_y)),
                    (int(sx + bx * r * 0.4 + lx * sign * r * 0.45), int(sy + by * r * 0.4 + ly * sign * r * 0.45)),
                ],
            )
        pygame.draw.circle(surf, outline_col, (int(sx), int(sy)), ri, width=2)
        return

    if cid == "Kollosios":
        fx, fy = _n(c.facing_x, c.facing_y)
        bx, by = -fx, -fy
        lx, ly = _perp(fx, fy)
        r = max(7.0, c.radius * 1.08)
        ri = int(r)
        cloak = (48, 28, 72)
        mask = (210, 205, 220)
        horn = (95, 75, 125)
        if escaped:
            cloak, mask, horn, _ = _escaped_tint(cloak, mask, horn)
        pygame.draw.circle(surf, cloak, (int(sx), int(sy)), ri)
        # Pale forward mask / face area
        pygame.draw.circle(surf, mask, (int(sx + fx * r * 0.35), int(sy + fy * r * 0.35)), max(4, int(r * 0.38)))
        # Horn silhouette spikes
        for i in (-1.2, 0.0, 1.2):
            tip_x = sx + bx * r * 1.02 + lx * i * r * 0.4
            tip_y = sy + by * r * 1.02 + ly * i * r * 0.4
            pygame.draw.polygon(
                surf,
                horn,
                [
                    (int(sx + bx * r * 0.25 + lx * i * r * 0.12), int(sy + by * r * 0.25 + ly * i * r * 0.12)),
                    (int(tip_x), int(tip_y)),
                    (int(sx + bx * r * 0.18 + lx * i * r * 0.35), int(sy + by * r * 0.18 + ly * i * r * 0.35)),
                ],
            )
        pygame.draw.circle(surf, (25, 15, 42), (int(sx), int(sy)), ri, width=2)
        return

    # Fallback: team-colored marble
    body = (90, 160, 255) if c.team == "Survivors" else (220, 70, 70)
    if escaped:
        body = _escaped_tint(body, body, body, body)[0]
    pygame.draw.circle(surf, body, (int(sx), int(sy)), int(c.radius))
    pygame.draw.circle(surf, (240, 244, 248), (int(sx), int(sy)), int(c.radius), width=2)
