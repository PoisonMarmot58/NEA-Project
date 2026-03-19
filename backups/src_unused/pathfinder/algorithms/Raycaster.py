"""Raycaster module."""

class RayCaster:
    def __init__(self, grid):
        self.grid = grid.grid
        self.rows, self.columns = self.grid.shape

    def water_or_port(self, r, c, startOrGoal = False):
        if not (0<= r <self.rows and 0<= c < self.columns):
            return False
        value = self.grid[r,c]
        if value == 0:        # if it is water
            return True
        if value in (3,4) and startOrGoal:
            return True
        return False
    
    def raycast(self, start, goal, step_size = 0.5):
        x0, y0 = start[1], start[0]
        x1, y1 = goal[1], goal[0]
        dx = x1 -x0
        dy = y1-y0
        distance = max(abs(dx), abs(dy), 1e-6)
        step_x = dx/distance
        step_y = dy/distance
        x,y = x0, y0 
        path = []


        while True:
            currentx = int(round(x))
            currenty = int(round(y))
            isStart = (currenty, currentx) == start
            isGoal = (currenty, currentx) == goal
            
            if not self.water_or_port(currentx, currenty, startOrGoal=(isStart or isGoal)):
                return False, (currentx, currenty)
            
            if not path or path[-1] != (currentx, currenty):
                path.append((currentx, currenty))

            
            path.append((currentx, currenty))

            if (step_x >= 0 and x >= x1) or (step_x < 0 and x <= x1):
                if (step_y >= 0 and y >= y1) or (step_y < 0 and y <= y1):
                    break

            
            x += step_x * step_size
            y += step_y * step_size
            
            if len(path) > self.rows * self.columns *2:
                return False, None
            
        return True, path
    
