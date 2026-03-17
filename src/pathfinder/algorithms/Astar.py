"""Astar module."""

import numpy as np
import heapq
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

    def heuristic(self, a:Tuple[int,int], b: Tuple[int,int]) -> float:
        return ((a[0]-b[0]) ** 2 + (a[1] - b[1]) **2) **0.5
    
    def get_neighbours(self, pos:Tuple[int,int])-> List[Tuple[int,int]]:
        row, column = pos
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        #directions += [(-1,-1), (-1,1), (1,-1), (1,1)] 

        neighbours = []
        for dr, dc in directions:
            newRow, newColumn = (row + dr), (column + dc)
            if self.grid.is_valid(newRow, newColumn):
                neighbours.append((newRow, newColumn))
        return neighbours
    
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
        if not self.is_walkable(start[0], start[1], is_goal=True):
            print("Error, start cell is not a port or water cell")
            return None
        if not self.is_walkable(goal[0],goal[1],is_goal=True):
            print("Error, Goal is not a port")
            return None
        
        openSet = []
        heapq.heappush(openSet, (0,start))

        cameFrom = {}
        currentScore = {start: 0}
        estimatedScore = {start: self.heuristic(start,goal)}

        while openSet:
            _, current = heapq.heappop(openSet)

            if current == goal:
                path = []
                while current in cameFrom:
                    path.append(current)
                    current = cameFrom[current]
                path.append(start)
                path.reverse()
                return path
            for neighbour in self.get_neighbours(current):
                isNeighbourGoal = (neighbour == goal)
                if not self.is_walkable(neighbour[0], neighbour[1], isNeighbourGoal):
                    continue
                tentativeScore = currentScore[current] + 1

                if neighbour not in currentScore or tentativeScore < currentScore[neighbour]:
                    cameFrom[neighbour] = current
                    currentScore[neighbour] = tentativeScore
                    estimatedScore[neighbour] = tentativeScore + self.heuristic(neighbour,goal)
                    heapq.heappush(openSet, (estimatedScore[neighbour], neighbour))
        
        print("No path found between these ports")
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
