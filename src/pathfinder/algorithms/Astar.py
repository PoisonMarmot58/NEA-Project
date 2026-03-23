"""Astar module."""

import numpy as np
import heapq
import math
from typing import List, Tuple, Optional

class Grid:
    def __init__(self, numpyPath: str):
        with open(numpyPath, "rb") as f:
            header = f.read(64)
        if header.startswith(b"version https://git-lfs.github.com/spec/"):
            raise ValueError(
                f"Grid file '{numpyPath}' is a Git LFS pointer, not the real .npy data. "
                "Fetch LFS files first (for example: git lfs pull)."
            )

        try:
            data = np.load(numpyPath, allow_pickle=False)
        except ValueError as exc:
            # Retry only for the known legacy-object-array case.
            if "allow_pickle=False" not in str(exc):
                raise ValueError(f"Failed to load grid '{numpyPath}': {exc}") from exc

            data = np.load(numpyPath, allow_pickle=True)

        # Unwrap a scalar object array if needed.
        if isinstance(data, np.ndarray) and data.dtype == object and data.shape == ():
            data = data.item()

        # If an .npz archive is provided, use the first stored array.
        if isinstance(data, np.lib.npyio.NpzFile):
            if not data.files:
                raise ValueError(f"Grid archive '{numpyPath}' does not contain arrays")
            data = data[data.files[0]]

        self.data = np.asarray(data)
        if self.data.ndim < 2:
            raise ValueError(f"Grid data in '{numpyPath}' is not 2D")

        self.height, self.width = self.data.shape

    def is_valid(self, row: int, column: int) -> bool:
        if 0 <= row < self.height and 0 <= column < self.width:
            valid = True
        else:
            valid = False
        return valid
    
    def is_water(self, row: int, column: int) -> bool:
        return self.is_valid(row, column) and self.data[row, column] == 0
    
    def is_port(self, row: int, column: int) -> bool:
        if not self.is_valid(row,column):
            return False
        return self.data[row,column] in (3,4)
    
class AStarPathfinder:
    def __init__(self, grid: Grid):
        self.grid = grid
        # Cache coastal penalties so neighbor expansion does not repeatedly
        # rescan surrounding cells for the same coordinates.
        # Cache stores raw count of neighbouring non-water cells per cell.
        self._coastal_nonwater_count = {}
        # Slightly weighted heuristic for faster convergence on long routes.
        # Values >1.0 trade exact optimality for speed.
        self.heuristic_weight = 1.15
        # Safety cap to avoid very long searches when no path exists.
        self.max_expansions = 900000
        # Coastal penalty scale used by fast mode.
        self.coastal_penalty_scale = 0.3
        # Exposed status for UI: 'fast', 'fallback', 'failed', or None.
        self.last_search_mode: Optional[str] = None
        # Precompute neighbor offsets and movement costs to avoid allocations.
        self._directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
        self._diag_cost = math.sqrt(2.0)
        # Route cache to avoid recomputing common port pairs.
        self._route_cache = {}
        self._route_cache_limit = 64
        # Long-route threshold (in grid-cell Euclidean distance) for trying
        # bidirectional search early.
        self.long_route_threshold = 1800.0

    def heuristic(self, a:Tuple[int,int], b: Tuple[int,int]) -> float:
        # use math.hypot implemented in C for speed
        return math.hypot(a[0]-b[0], a[1]-b[1])
    
    def get_neighbours(self, pos:Tuple[int,int])-> List[Tuple[Tuple[int,int], float]]:
        row, column = pos
        neighbours: List[Tuple[Tuple[int,int], float]] = []
        for dr, dc in self._directions:
            newRow, newColumn = row + dr, column + dc
            if self.grid.is_valid(newRow, newColumn):
                move_cost = 1.0 if (dr == 0 or dc == 0) else self._diag_cost
                neighbours.append(((newRow, newColumn), move_cost))
        return neighbours

    def _coastal_penalty(self, cell: Tuple[int, int], scale: float) -> float:
        """Return coastal penalty for a cell using cached non-water counts.

        Cache stores the raw count of adjacent non-water cells so the penalty
        computation is a cheap multiplication by the provided scale.
        """
        if cell in self._coastal_nonwater_count:
            count_non_water = self._coastal_nonwater_count[cell]
            return float(scale) * count_non_water

        r0, c0 = cell
        count_non_water = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                rr, cc = r0 + dr, c0 + dc
                if not self.grid.is_valid(rr, cc):
                    continue
                if not self.grid.is_water(rr, cc):
                    count_non_water += 1

        self._coastal_nonwater_count[cell] = count_non_water
        return float(scale) * count_non_water

    def _reconstruct_path(self, cameFrom: dict, start: Tuple[int, int], goal: Tuple[int, int]) -> List[Tuple[int, int]]:
        path = []
        current = goal
        while current in cameFrom:
            path.append(current)
            current = cameFrom[current]
        path.append(start)
        path.reverse()
        return path

    def _find_path_internal(
        self,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        heuristic_weight: float,
        max_expansions: Optional[int],
        coastal_penalty_scale: float,
        corridor_bounds: Optional[Tuple[int, int, int, int]] = None,
    ) -> Optional[List[Tuple[int, int]]]:
        openSet: List[Tuple[float, Tuple[int,int]]] = []
        heapq.heappush(openSet, (0.0, start))

        cameFrom = {}
        currentScore = {start: 0.0}
        closedSet = set()

        while openSet:
            _, current = heapq.heappop(openSet)

            # Skip stale entries that were already finalized.
            if current in closedSet:
                continue
            closedSet.add(current)

            if max_expansions is not None and len(closedSet) > max_expansions:
                return None

            if current == goal:
                return self._reconstruct_path(cameFrom, start, goal)

            # Local bindings for speed
            neigh_func = self.get_neighbours
            walkable = self.is_walkable
            cost_func = self._coastal_penalty
            hw = heuristic_weight
            for neighbour, move_cost in neigh_func(current):
                if corridor_bounds is not None and not self._in_bounds(neighbour, corridor_bounds):
                    if neighbour != goal and neighbour != start:
                        continue
                isNeighbourGoal = (neighbour == goal)
                if not walkable(neighbour[0], neighbour[1], isNeighbourGoal):
                    continue

                tentativeScore = currentScore[current] + move_cost
                tentativeScore += cost_func(neighbour, coastal_penalty_scale)

                prev = currentScore.get(neighbour)
                if prev is not None and tentativeScore >= prev:
                    continue

                cameFrom[neighbour] = current
                currentScore[neighbour] = tentativeScore

                # Re-open node when a better route is found after it was closed.
                if neighbour in closedSet:
                    closedSet.remove(neighbour)

                fscore = tentativeScore + (hw * self.heuristic(neighbour, goal))
                heapq.heappush(openSet, (fscore, neighbour))

        return None

    def _in_bounds(self, cell: Tuple[int, int], bounds: Tuple[int, int, int, int]) -> bool:
        r, c = cell
        r0, r1, c0, c1 = bounds
        return r0 <= r <= r1 and c0 <= c <= c1

    def _corridor_bounds(self, start: Tuple[int, int], goal: Tuple[int, int], pad: int) -> Tuple[int, int, int, int]:
        sr, sc = start
        gr, gc = goal
        r0 = max(0, min(sr, gr) - pad)
        r1 = min(self.grid.height - 1, max(sr, gr) + pad)
        c0 = max(0, min(sc, gc) - pad)
        c1 = min(self.grid.width - 1, max(sc, gc) + pad)
        return (r0, r1, c0, c1)

    def _cache_get(self, start: Tuple[int, int], goal: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        key = (start, goal)
        path = self._route_cache.get(key)
        if path is None:
            return None
        # Return a copy to avoid accidental caller mutation of cached path.
        return list(path)

    def _cache_put(self, start: Tuple[int, int], goal: Tuple[int, int], path: List[Tuple[int, int]]) -> None:
        if not path:
            return
        key = (start, goal)
        self._route_cache[key] = list(path)
        rev_key = (goal, start)
        self._route_cache[rev_key] = list(reversed(path))
        while len(self._route_cache) > self._route_cache_limit:
            try:
                self._route_cache.pop(next(iter(self._route_cache)))
            except Exception:
                break

    def _reconstruct_bidirectional(
        self,
        meet: Tuple[int, int],
        start: Tuple[int, int],
        goal: Tuple[int, int],
        parent_f: dict,
        parent_b: dict,
    ) -> List[Tuple[int, int]]:
        # start -> meet from forward parents
        left = [meet]
        cur = meet
        while cur in parent_f:
            cur = parent_f[cur]
            left.append(cur)
        left.reverse()

        # meet -> goal from backward parents
        right = [meet]
        cur = meet
        while cur in parent_b:
            cur = parent_b[cur]
            right.append(cur)

        # Avoid duplicating meet node
        return left + right[1:]

    def _find_path_bidirectional(
        self,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        max_expansions: Optional[int],
        corridor_bounds: Optional[Tuple[int, int, int, int]] = None,
    ) -> Optional[List[Tuple[int, int]]]:
        if start == goal:
            return [start]

        open_f: List[Tuple[float, Tuple[int, int]]] = []
        open_b: List[Tuple[float, Tuple[int, int]]] = []
        heapq.heappush(open_f, (0.0, start))
        heapq.heappush(open_b, (0.0, goal))

        g_f = {start: 0.0}
        g_b = {goal: 0.0}
        parent_f = {}
        parent_b = {}
        closed_f = set()
        closed_b = set()

        meet = None
        best_total = float("inf")
        expansions = 0

        while open_f and open_b:
            if max_expansions is not None and expansions > max_expansions:
                return None

            # Expand whichever frontier currently looks more promising.
            expand_forward = open_f[0][0] <= open_b[0][0]
            if expand_forward:
                _fscore, current = heapq.heappop(open_f)
                if current in closed_f:
                    continue
                closed_f.add(current)
                expansions += 1

                for neighbour, move_cost in self.get_neighbours(current):
                    if corridor_bounds is not None and not self._in_bounds(neighbour, corridor_bounds):
                        if neighbour != goal and neighbour != start:
                            continue
                    if not self.is_walkable(neighbour[0], neighbour[1], is_goal=(neighbour == goal)):
                        continue

                    tentative = g_f[current] + move_cost
                    old = g_f.get(neighbour)
                    if old is not None and tentative >= old:
                        continue

                    g_f[neighbour] = tentative
                    parent_f[neighbour] = current
                    h = self.heuristic(neighbour, goal)
                    heapq.heappush(open_f, (tentative + (1.05 * h), neighbour))

                    other = g_b.get(neighbour)
                    if other is not None:
                        total = tentative + other
                        if total < best_total:
                            best_total = total
                            meet = neighbour
            else:
                _fscore, current = heapq.heappop(open_b)
                if current in closed_b:
                    continue
                closed_b.add(current)
                expansions += 1

                for neighbour, move_cost in self.get_neighbours(current):
                    if corridor_bounds is not None and not self._in_bounds(neighbour, corridor_bounds):
                        if neighbour != goal and neighbour != start:
                            continue
                    if not self.is_walkable(neighbour[0], neighbour[1], is_goal=(neighbour == start)):
                        continue

                    tentative = g_b[current] + move_cost
                    old = g_b.get(neighbour)
                    if old is not None and tentative >= old:
                        continue

                    g_b[neighbour] = tentative
                    parent_b[neighbour] = current
                    h = self.heuristic(neighbour, start)
                    heapq.heappush(open_b, (tentative + (1.05 * h), neighbour))

                    other = g_f.get(neighbour)
                    if other is not None:
                        total = tentative + other
                        if total < best_total:
                            best_total = total
                            meet = neighbour

            if meet is not None:
                # Stop when both frontiers cannot beat current best meeting cost.
                if open_f and open_b and (open_f[0][0] + open_b[0][0]) >= best_total:
                    return self._reconstruct_bidirectional(meet, start, goal, parent_f, parent_b)

        if meet is not None:
            return self._reconstruct_bidirectional(meet, start, goal, parent_f, parent_b)
        return None
    
    def is_walkable(self, row:int, column:int, is_goal:bool = False) -> bool:
        if not self.grid.is_valid(row, column):
           return False
    
        value = self.grid.data[row, column]

        if value == 0: # current is water which is walkable
            return True
        
        if value in (3,4) and is_goal: # port which is the goal
            return True
        
        return False
    
    def find_path(self, start:Tuple[int,int], goal:Tuple[int,int]) -> Optional[List[Tuple[int, int]]]:
        self.last_search_mode = None
        if not self.is_walkable(start[0], start[1], is_goal=True):
            print("Error, start cell is not a port or water cell")
            self.last_search_mode = 'failed'
            return None
        if not self.is_walkable(goal[0],goal[1],is_goal=True):
            print("Error, Goal is not a port")
            self.last_search_mode = 'failed'
            return None

        cached = self._cache_get(start, goal)
        if cached is not None:
            self.last_search_mode = 'fast-cache'
            return cached

        dist = self.heuristic(start, goal)
        pad = int(max(160.0, min(900.0, dist * 0.22)))
        corridor = self._corridor_bounds(start, goal, pad)
        
        # Fast pass 1: weighted/coastal search inside a corridor around start-goal.
        path = self._find_path_internal(
            start,
            goal,
            heuristic_weight=self.heuristic_weight,
            max_expansions=min(self.max_expansions, 550000),
            coastal_penalty_scale=self.coastal_penalty_scale,
            corridor_bounds=corridor,
        )
        if path:
            self.last_search_mode = 'fast-corridor'
            self._cache_put(start, goal, path)
            return path

        # Try bidirectional search before expensive fallback stages.
        # Start with corridor-bounded attempts, then allow full-map search.
        for limit, bounds in (
            (120000, corridor),
            (260000, corridor),
            (None, None),
        ):
            # Preserve previous behavior for very short routes: skip low-limit
            # bidirectional tries unless route is beyond threshold.
            if dist < self.long_route_threshold and bounds is corridor:
                continue
            path = self._find_path_bidirectional(
                start,
                goal,
                max_expansions=limit,
                corridor_bounds=bounds,
            )
            if path:
                self.last_search_mode = 'bidirectional'
                self._cache_put(start, goal, path)
                return path

        # Fast pass 2: weighted/coastal search across full map.
        path = self._find_path_internal(
            start,
            goal,
            heuristic_weight=self.heuristic_weight,
            max_expansions=self.max_expansions,
            coastal_penalty_scale=self.coastal_penalty_scale,
        )
        if path:
            self.last_search_mode = 'fast'
            self._cache_put(start, goal, path)
            return path

        # Robust fallback in stages to avoid jumping immediately to unlimited search.
        for limit in (180000, 420000, None):
            path = self._find_path_internal(
                start,
                goal,
                heuristic_weight=1.0,
                max_expansions=limit,
                coastal_penalty_scale=0.0,
                corridor_bounds=corridor if limit in (180000, 420000) else None,
            )
            if path:
                self.last_search_mode = 'fallback' if limit is None else 'fallback-limited'
                self._cache_put(start, goal, path)
                return path

        print("No path found between these ports")
        self.last_search_mode = 'failed'
        return None

    
#test

if __name__ == "__main__":
    # Resolve grid file relative to this package so the module can be run
    # from any working directory without relying on a hardcoded absolute path.
    from pathlib import Path

    grid_path = Path(__file__).resolve().parents[1] / "data" / "FullGridOfEurope.npy"
    if not grid_path.exists():
        raise FileNotFoundError(
            f"Grid file not found: {grid_path!s}\n"
            "Place FullGridOfEurope.npy in src/pathfinder/data/ or set up the correct path."
        )

    grid = Grid(str(grid_path))
    pathfinder = AStarPathfinder(grid)

    start_port = (618, 482)   # Rotterdam
    goal_port = (952, 1182)   # Piraeus

    print(f"Finding sea route from {start_port} → {goal_port}...\n")
    path = pathfinder.find_path(start_port, goal_port)

    if path:
        print(f"Success! Path found with {len(path)} steps")
        print("Start →", path[0])
        print("End   →", path[-1])
        print("\nFirst 10 steps:", path[:10])
        print("Last 10 steps :", path[-10:])
    else:
        print("No route found.")
