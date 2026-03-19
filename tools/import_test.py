import os
import sys

# Force headless matplotlib backend to avoid GUI requirements during import.
os.environ.setdefault('MPLBACKEND', 'Agg')

base = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src'))
print('DEBUG: adding to sys.path ->', base)
print('DEBUG: exists?', os.path.exists(base))
sys.path.insert(0, base)
print('DEBUG: file check astar ->', os.path.exists(os.path.join(base, 'pathfinder', 'algorithms', 'astar.py')))

try:
    import pathfinder.FullSystem as app
    print('IMPORT_OK')
except Exception as e:
    import traceback
    traceback.print_exc()
    print('IMPORT_FAIL')
