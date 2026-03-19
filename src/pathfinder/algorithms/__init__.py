"""Algorithms subpackage.

This module exposes the public classes used by the rest of the project.
The package provides both the original CamelCase modules and new
snake_case modules; imports here prefer the new snake_case names but keep
the public API names stable for consumers.
"""

"""Lightweight algorithms package initializer with lazy imports.

Avoid importing submodules at package-import time to prevent import-order
problems when tools call `importlib.util.find_spec` for submodules.
"""

import importlib
import typing

# Ensure import system caches are refreshed so submodule files (e.g. astar.py)
# created at runtime are discoverable by importlib.find_spec on some setups.
importlib.invalidate_caches()
from pathlib import Path

# Force a concrete list for __path__ so PathFinder looks in the right folder
# even if package import machinery wrapped it in a namespace path object.
__path__ = [str(Path(__file__).resolve().parent)]

# Eagerly register the lowercase `astar` module if present so consumers
# that expect `pathfinder.algorithms.astar` can import it reliably.
try:
	from . import astar  # type: ignore
except Exception:
	# If import fails, keep package lazy-loading behaviour unchanged.
	pass


def __getattr__(name: str):
	# Lazy-load the snake_case modules on attribute access.
	if name in ("Grid", "AStarPathfinder"):
		mod = importlib.import_module(".astar", __name__)
		return getattr(mod, name)
	if name == "RouteCostEstimator":
		mod = importlib.import_module(".cost_calculator", __name__)
		return getattr(mod, name)

	# Backwards compatibility: try old CamelCase modules if present
	if name in ("Grid_old", "AStarPathfinder_old"):
		try:
			mod = importlib.import_module(".Astar", __name__)
			return getattr(mod, name.replace("_old", ""))
		except Exception:
			raise AttributeError(name)
	if name == "RouteCostEstimator_old":
		try:
			mod = importlib.import_module(".CostCalculator", __name__)
			return getattr(mod, "RouteCostEstimator")
		except Exception:
			raise AttributeError(name)

	raise AttributeError(name)


__all__ = ["Grid", "AStarPathfinder", "RouteCostEstimator"]
