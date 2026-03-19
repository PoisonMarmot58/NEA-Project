import os, sys
base = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, base)
print('sys.path[0]=', sys.path[0])
import importlib.util
spec = importlib.util.find_spec('pathfinder')
print('pathfinder spec:', spec)
spec2 = importlib.util.find_spec('pathfinder.algorithms')
print('pathfinder.algorithms spec:', spec2)
try:
    spec3 = importlib.util.find_spec('pathfinder.algorithms.astar')
    print('pathfinder.algorithms.astar spec:', spec3)
except Exception as e:
    print('find_spec for astar raised:', repr(e))

try:
    import pathfinder.algorithms.astar as astar
    print('Imported astar from', getattr(astar, '__file__', None))
except Exception as e:
    import traceback
    traceback.print_exc()

print('\nAttempting direct load by file path:')
fp = os.path.join(base, 'pathfinder', 'algorithms', 'astar.py')
print('astar file exists?', os.path.exists(fp), fp)
try:
    spec = importlib.util.spec_from_file_location('pathfinder.algorithms.astar', fp)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print('Loaded directly, module file:', getattr(mod, '__file__', None))
except Exception:
    import traceback
    traceback.print_exc()
