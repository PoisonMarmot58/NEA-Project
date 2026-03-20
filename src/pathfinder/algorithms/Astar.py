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
        
        # Fast pass
        path = self._find_path_internal(
            start,
            goal,
            heuristic_weight=self.heuristic_weight,
            max_expansions=self.max_expansions,
            coastal_penalty_scale=self.coastal_penalty_scale,
        )
        if path:
            self.last_search_mode = 'fast'
            return path

        # Robust fallback: disable shortcuts that can occasionally miss long/complex routes.
        path = self._find_path_internal(
            start,
            goal,
            heuristic_weight=1.0,
            max_expansions=None,
            coastal_penalty_scale=0.0,
        )
        if path:
            self.last_search_mode = 'fallback'
            return path

        print("No path found between these ports")
        self.last_search_mode = 'failed'
        return None

    
#test

if __name__ == "__main__":
    grid = Grid(
        r"c:\Users\isaac\OneDrive\Desktop\NEA Project new\NEA-Project-2"
        r"\Pathfinder Algorithm\Data\FullGridOfEurope.npy"
    )
    pathfinder = AStarPathfinder(grid)


    start_port = (618, 482)   # Rotterdam
    goal_port  = (952, 1182)  # Piraeus

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
