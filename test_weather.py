import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from pathfinder.algorithms.WeatherEstimator import WeatherImpactEstimator

w = WeatherImpactEstimator()
path = [(2001,1950),(2050,1975),(2100,2000)]
res = w.estimate_path_impact(path, ship_profile={'average_speed_knots':16.5})
print(res)
