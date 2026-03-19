import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
import importlib
import sys as _s
import pathfinder.algorithms as pa
print('in sys.modules:', 'pathfinder.algorithms.astar' in _s.modules)
print('pa.__path__ =', getattr(pa, '__path__', None))
print('pa.__file__ =', getattr(pa, '__file__', None))
print('listing files in path:', list(getattr(pa, '__path__', [])))
import pkgutil
print('pkgutil.iter_modules:', [m.name for m in pkgutil.iter_modules(getattr(pa, "__path__", []))])
print('sys.modules keys sample:', [k for k in _s.modules.keys() if k.startswith('pathfinder')])
