import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
import pprint
from pathfinder.algorithms.WeatherEstimator import WeatherImpactEstimator

# Marseille-Fos and Dunkirk grid coords from ports_user_calibrated.json
start = (2570, 1964)
goal = (1982, 1872)

# Build a simple interpolated path with 60 points between start and goal
import numpy as np
n = 60
rows = np.linspace(start[0], goal[0], n)
cols = np.linspace(start[1], goal[1], n)
path = [(int(round(r)), int(round(c))) for r, c in zip(rows, cols)]

print('Path length:', len(path))

w = WeatherImpactEstimator()
res = w.estimate_path_impact(path, ship_profile={'average_speed_knots':16.5}, detailed=True)
pp = pprint.PrettyPrinter(indent=2)
pp.pprint(res)
