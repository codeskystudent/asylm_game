"""Static arena walls, circle-vs-AABB resolution, and grid A* for NPC pathfinding."""

from __future__ import annotations

import heapq
import math

import pygame

from outcome_game.constants import ARENA_H, ARENA_W

PATH_CELL = 44
PATH_CLEARANCE = 24.0
# Aim at a waypoint this far along the path (world units) — avoids stiff cell-to-cell motion
PATH_LOOKAHEAD_MIN_DIST = 88.0

_blocked_cache: list[list[bool]] | None = None
_grid_cols = 0
_grid_rows = 0

_active_walls: list[pygame.Rect] | None = None


def set_active_walls(walls: list[pygame.Rect]) -> None:
    """Swap collision/pathfinding walls (called when a match loads a map)."""
    global _active_walls, _blocked_cache
    _active_walls = walls
    _blocked_cache = None


def get_arena_walls() -> list[pygame.Rect]:
    if _active_walls is not None:
        return _active_walls
    from outcome_game.arena_maps import MAPS

    return list(MAPS["hangar"].walls)


def _ensure_grid() -> tuple[list[list[bool]], int, int]:
    global _blocked_cache, _grid_cols, _grid_rows
    if _blocked_cache is not None:
        return _blocked_cache, _grid_cols, _grid_rows
    cols = max(1, int(math.ceil(ARENA_W / PATH_CELL)))
    rows = max(1, int(math.ceil(ARENA_H / PATH_CELL)))
    blocked: list[list[bool]] = [[False] * cols for _ in range(rows)]
    inflate = int(PATH_CLEARANCE * 2)
    for cy in range(rows):
        for cx in range(cols):
            px = cx * PATH_CELL + PATH_CELL * 0.5
            py = cy * PATH_CELL + PATH_CELL * 0.5
            for w in get_arena_walls():
                ew = w.inflate(inflate, inflate)
                if ew.collidepoint(px, py):
                    blocked[cy][cx] = True
                    break
    _blocked_cache = blocked
    _grid_cols = cols
    _grid_rows = rows
    return blocked, cols, rows


def _world_to_cell(x: float, y: float) -> tuple[int, int]:
    cx = int(x // PATH_CELL)
    cy = int(y // PATH_CELL)
    return cx, cy


def _cell_center_world(cx: int, cy: int) -> tuple[float, float]:
    return cx * PATH_CELL + PATH_CELL * 0.5, cy * PATH_CELL + PATH_CELL * 0.5


def _lookahead_world_goal(
    path: list[tuple[int, int]],
    from_x: float,
    from_y: float,
) -> tuple[float, float]:
    """Pick a waypoint far enough ahead on the path for smooth steering (not only next tile)."""
    if len(path) < 2:
        cx, cy = path[-1]
        return _cell_center_world(cx, cy)
    for i in range(1, len(path)):
        wx, wy = _cell_center_world(path[i][0], path[i][1])
        if math.hypot(wx - from_x, wy - from_y) >= PATH_LOOKAHEAD_MIN_DIST:
            return wx, wy
    cx, cy = path[-1]
    return _cell_center_world(cx, cy)


def _nearest_walkable(cx: int, cy: int, blocked: list[list[bool]], cols: int, rows: int) -> tuple[int, int]:
    if 0 <= cx < cols and 0 <= cy < rows and not blocked[cy][cx]:
        return cx, cy
    for r in range(1, 18):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if abs(dx) != r and abs(dy) != r:
                    continue
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < cols and 0 <= ny < rows and not blocked[ny][nx]:
                    return nx, ny
    return max(0, min(cx, cols - 1)), max(0, min(cy, rows - 1))


def _heuristic(a: tuple[int, int], b: tuple[int, int]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _astar(blocked: list[list[bool]], cols: int, rows: int, start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
    if blocked[goal[1]][goal[0]] or blocked[start[1]][start[0]]:
        return []
    open_h: list[tuple[float, tuple[int, int]]] = []
    heapq.heappush(open_h, (0.0, start))
    came: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    gscore: dict[tuple[int, int], float] = {start: 0.0}

    neighbors = (
        (-1, 0),
        (1, 0),
        (0, -1),
        (0, 1),
        (-1, -1),
        (1, -1),
        (-1, 1),
        (1, 1),
    )

    closed: set[tuple[int, int]] = set()
    while open_h:
        _, current = heapq.heappop(open_h)
        if current in closed:
            continue
        closed.add(current)
        if current == goal:
            path: list[tuple[int, int]] = []
            while current is not None:
                path.append(current)
                current = came[current]
            path.reverse()
            return path

        for dx, dy in neighbors:
            nx, ny = current[0] + dx, current[1] + dy
            if nx < 0 or ny < 0 or nx >= cols or ny >= rows:
                continue
            if blocked[ny][nx]:
                continue
            step = math.hypot(dx, dy)
            tentative = gscore[current] + step
            neighbor = (nx, ny)
            if neighbor not in gscore or tentative < gscore[neighbor]:
                came[neighbor] = current
                gscore[neighbor] = tentative
                f = tentative + _heuristic(neighbor, goal)
                heapq.heappush(open_h, (f, neighbor))
    return []


def pathfind_direction(
    from_x: float,
    from_y: float,
    to_x: float,
    to_y: float,
    _agent_radius: float,
) -> tuple[float, float]:
    """Unit direction toward next waypoint on an A* path, or straight fallback."""
    blocked, cols, rows = _ensure_grid()
    sx, sy = _world_to_cell(from_x, from_y)
    gx, gy = _world_to_cell(to_x, to_y)
    sx = max(0, min(sx, cols - 1))
    sy = max(0, min(sy, rows - 1))
    gx = max(0, min(gx, cols - 1))
    gy = max(0, min(gy, rows - 1))
    start = _nearest_walkable(sx, sy, blocked, cols, rows)
    goal = _nearest_walkable(gx, gy, blocked, cols, rows)
    path = _astar(blocked, cols, rows, start, goal)
    if len(path) >= 2:
        wx, wy = _lookahead_world_goal(path, from_x, from_y)
        dx = wx - from_x
        dy = wy - from_y
        d = math.hypot(dx, dy)
        if d > 1e-6:
            return dx / d, dy / d
    dx = to_x - from_x
    dy = to_y - from_y
    d = math.hypot(dx, dy)
    if d < 1e-6:
        return 0.0, 0.0
    return dx / d, dy / d


def resolve_combatant_walls(c: "Combatant", walls: list[pygame.Rect]) -> None:
    """Push combatant circle out of axis-aligned wall segments."""
    r = c.radius
    for w in walls:
        test_x = c.x
        test_y = c.y
        if c.x < w.left:
            test_x = float(w.left)
        elif c.x > w.right:
            test_x = float(w.right)
        if c.y < w.top:
            test_y = float(w.top)
        elif c.y > w.bottom:
            test_y = float(w.bottom)

        dist_x = c.x - test_x
        dist_y = c.y - test_y
        distance = math.sqrt(dist_x * dist_x + dist_y * dist_y)

        if distance >= r:
            continue

        if distance > 1e-8:
            overlap = r - distance
            c.x += (dist_x / distance) * overlap
            c.y += (dist_y / distance) * overlap
        else:
            rcx = w.centerx
            rcy = w.centery
            dx = c.x - rcx
            dy = c.y - rcy
            d = math.hypot(dx, dy)
            if d > 1e-8:
                c.x += (dx / d) * (r + 2.0)
                c.y += (dy / d) * (r + 2.0)
            else:
                c.x = float(w.right) + r + 1.0
