import numpy as np
from pathlib import Path
p = Path(__file__).resolve().parents[1] / 'src' / 'pathfinder' / 'data' / 'FullGridOfEurope.npy'
print('checking', p)
if not p.exists():
    print('MISSING')
    raise SystemExit(1)
arr = np.load(p)
print('loaded ok; shape=', getattr(arr, 'shape', None), 'dtype=', getattr(arr, 'dtype', None))
