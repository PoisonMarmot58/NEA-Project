"""Compatibility shim: lowercase module name expected by imports.

Some parts of the codebase import `pathfinder.algorithms.astar` (lowercase),
but the implementation file is named `Astar.py`. On case-insensitive filesystems
this usually works, but some import mechanisms (and tooling) expect the
lowercase module to exist. Re-export the main symbols from `Astar.py` here.
"""
from .Astar import *  # noqa: F401,F403
"""A* pathfinding (minimal, safe import implementation)."""

import numpy as np
import heapq
from typing import List, Tuple, Optional


class Grid:
    def __init__(self, numpy_path: str):
        # Load numpy grid; keep simple and robust
        try:
            data = np.load(numpy_path, allow_pickle=False)
        except Exception:
            data = np.load(numpy_path, allow_pickle=True)

        # Unwrap object scalar
        if isinstance(data, np.ndarray) and data.dtype == object and data.shape == ():
            data = data.item()

        self.data = np.asarray(data)
        if self.data.ndim < 2:
            raise ValueError("Grid data must be 2D")
        self.height, self.width = self.data.shape

    def is_valid(self, row: int, col: int) -> bool:
        return 0 <= row < self.height and 0 <= col < self.width

    def is_water(self, row: int, col: int) -> bool:
        return self.is_valid(row, col) and int(self.data[row, col]) == 0


class AStarPathfinder:
    """Lightweight A* placeholder implementing 8-neighbour expansion."""

    def __init__(self, grid: Grid):
        self.grid = grid
        self.last_search_mode: Optional[str] = None

    def heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    def get_neighbours(self, pos: Tuple[int, int]) -> List[Tuple[Tuple[int, int], float]]:
        r, c = pos
        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
        result = []
        for dr, dc in dirs:
            nr, nc = r + dr, c + dc
            if self.grid.is_valid(nr, nc):
                cost = 1.0 if dr == 0 or dc == 0 else 2 ** 0.5
                result.append(((nr, nc), cost))
        return result

    def find_path(self, start: Tuple[int, int], goal: Tuple[int, int]):
        # Minimal A* implementation for runtime use; may be slow on large grids.
        openq = []
        heapq.heappush(openq, (0.0, start))
        came_from = {}
        gscore = {start: 0.0}
        closed = set()

        while openq:
            _, current = heapq.heappop(openq)
            if current in closed:
                continue
            closed.add(current)
            if current == goal:
                # reconstruct
                path = [current]
                while path[-1] in came_from:
                    path.append(came_from[path[-1]])
                path.reverse()
                return path

            for nb, move_cost in self.get_neighbours(current):
                nr, nc = nb
                if not self.grid.is_valid(nr, nc):
                    continue
                if int(self.grid.data[nr, nc]) != 0 and nb != goal:
                    # block non-water except allow goal
                    continue
                tentative = gscore[current] + move_cost
                if tentative < gscore.get(nb, float('inf')):
                    came_from[nb] = current
                    gscore[nb] = tentative
                    f = tentative + self.heuristic(nb, goal)
                    heapq.heappush(openq, (f, nb))

        return None
