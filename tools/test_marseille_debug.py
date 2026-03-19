import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from pathfinder.algorithms.WeatherEstimator import WeatherImpactEstimator
import numpy as np

start = (2570, 1964)
goal = (1982, 1872)

n = 60
rows = np.linspace(start[0], goal[0], n)
cols = np.linspace(start[1], goal[1], n)
path = [(int(round(r)), int(round(c))) for r, c in zip(rows, cols)]

w = WeatherImpactEstimator()
full_latlons = [w.grid_to_latlon(r, c) for r, c in path]
print('first latlon', full_latlons[0])
print('last latlon', full_latlons[-1])

# distances between consecutive points
from math import isfinite
dists = []
for i in range(1, len(full_latlons)):
    a = full_latlons[i-1]
    b = full_latlons[i]
    try:
        d = w._haversine_m(a, b)
    except Exception as e:
        d = None
    dists.append(d)

print('min dist', min([d for d in dists if d is not None]))
print('max dist', max([d for d in dists if d is not None]))
print('sum dist km', sum([d for d in dists if d is not None]) / 1000.0)

# cumulative
cum = [0.0]
for d in dists:
    cum.append(cum[-1] + (d or 0.0))
print('cumdist last km', cum[-1]/1000.0)

# sample indices
from pathfinder.algorithms.WeatherEstimator import WeatherImpactEstimator
idxs = w._sample_indices(len(path), max_samples=5)
print('sample idxs', idxs)
for idx in idxs:
    print(idx, path[idx], full_latlons[idx], 'cum_km', cum[idx]/1000.0)

# print a few latlons around the large jump (if any)
big_jumps = [i for i,d in enumerate(dists) if d and d > 100000]
print('big jumps indices', big_jumps)

