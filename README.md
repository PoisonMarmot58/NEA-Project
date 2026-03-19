# NEA Project 2 - Europe Sea Route Pathfinder

A Python project that computes maritime routes between European ports using an A* grid search, with both a Tkinter GUI and a console interface.

The project combines:
- A grid-based map model of Europe (`.npy` data).
- A pathfinding engine (A* over water cells).
- Port coordinate selection.
- Basic shipping cost estimation from route length.

## Project Goals

- Model realistic sea navigation constraints on a raster grid.
- Find shortest traversable routes between ports.
- Provide an interactive interface for selecting routes.
- Estimate journey cost from route distance and vessel assumptions.

## Key Features

- A* pathfinding over map cells (`water` + selected `port` cells).
- Tkinter desktop GUI with embedded Matplotlib map rendering.
- Console interface for quick testing without the GUI.
- Cost estimator with breakdown:
	- Distance (nautical miles)
	- Time at sea (days)
	- Fuel cost
	- Operating cost
	- Port fees
- Utility scripts to:
	- Convert an image map to a grid.
	- Detect coastline-adjacent potential ports.
	- Visualize and inspect generated grids.

## Repository Layout

Primary code is in `src/pathfinder`.

```text
	src/
	pathfinder/
		app.py                           # Tkinter GUI application (renamed from FullSystem.py)
		pathfinder_interface.py          # Console application
		algorithms/
			astar.py                       # Grid model + A* implementation (snake_case)
			cost_calculator.py              # Route cost estimator (snake_case)
			PriorityQueue.py               # Simple queue helper
			Raycaster.py                   # Raycast utility (experimental)
		scripts/
			MapToGrid.py                   # Image -> grid pipeline
			PortAddition.py                # Port coordinate interpolation helper
			mapVisualiser.py               # Grid inspection visualizer
		data/
			ports.json                     # Port metadata sample
```

There is also a legacy/backup area under `Pathfinder Algorithm/Backups` containing older snapshots.

## Grid Encoding

The map grid values are interpreted as:

- `0` = water (traversable)
- `1` = land (blocked)
- `2` = border/other blocked terrain
- `3` = potential port
- `4` = real major port

In pathfinding, water cells are traversable and the goal can be a port cell.

## How Pathfinding Works

`AStarPathfinder` in `src/pathfinder/algorithms/astar.py`:

- Uses Euclidean distance heuristic.
- Uses 8-connected movement (allows diagonal steps for more natural sea routes).
- Rejects land and non-walkable cells; ports are allowed as goals.
- Reconstructs the route from `cameFrom` when goal is reached.

Current step cost distinguishes straight vs diagonal moves (diagonals ~√2), so the route minimizes realistic travel distance on the grid.

## Requirements

Recommended:
- Python 3.11+ (project currently runs on Python 3.12 in your workspace)
- `tkinter` support (usually bundled with standard Python on Windows)

Core packages used by runtime and scripts:
- `numpy`
- `matplotlib`
- `scipy`
- `pillow`

The repository currently includes a pinned dependency file at:
- `Interface/requirements.txt`

## Setup

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r Interface/requirements.txt
pip install matplotlib scipy pillow
```

Notes:
- `matplotlib`, `scipy`, and `pillow` are needed by the pathfinder scripts but are not currently pinned in `Interface/requirements.txt`.
- If PowerShell blocks activation, run:
	`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

## Running the Project

Run commands from the repository root.

### 1. GUI Application (Main)

```powershell
python src/pathfinder/app.py
```

What you get:
- Start/goal port dropdowns.
- Route plotting on the map.
- Cost estimate panel.

### 2. Console Interface

```powershell
python src/pathfinder/pathfinder_interface.py
```

What you get:
- Menu-driven terminal flow.
- Port listing and route selection.
- Route summary (length and sample steps).

### 3. Data Preparation Utilities (Optional)

```powershell
python src/pathfinder/scripts/MapToGrid.py
python src/pathfinder/scripts/PortAddition.py
python src/pathfinder/scripts/mapVisualiser.py
```

Use these when rebuilding or validating the map grid data pipeline.

## Configuration You Will Likely Edit

The following values are hardcoded and should be reviewed for portability:

- `GRID_FILE` in:
	- `src/pathfinder/app.py`
	- `src/pathfinder/pathfinder_interface.py`
- Script input paths in:
	- `src/pathfinder/scripts/MapToGrid.py`
	- `src/pathfinder/scripts/mapVisualiser.py`
	- `src/pathfinder/data/temp.py`
- Port lists in:
	- `src/pathfinder/app.py`
	- `src/pathfinder/pathfinder_interface.py`

Most of these currently point to absolute local Windows paths. If you move machines or directories, update these to valid local paths.

## Typical Workflow

1. Prepare or load a valid grid (`FullGridOfEurope.npy`).
2. Launch GUI (`app.py`) or CLI (`pathfinder_interface.py`).
3. Select start and goal ports.
4. Run route computation.
5. Review route and estimated shipping cost.

## Known Limitations

- Several files use hardcoded absolute paths.
- Port datasets are partially duplicated across modules.
- Movement is currently 4-directional only (no diagonals).
- Cost model is a simplified estimator and not tied to dynamic weather, draft, canal fees, or real vessel schedules.
- Dependency management is split (only `Interface/requirements.txt` exists today).

## Suggested Next Improvements

- Replace absolute paths with relative paths using `pathlib`.
- Create a single root `requirements.txt` for this project.
- Move port data into one canonical data source (JSON/CSV).
- Add automated tests for:
	- Grid validity checks
	- A* route correctness
	- Cost calculator outputs
- Add support for weighted costs (currents, congestion, risk zones).

## Troubleshooting

- `ModuleNotFoundError: pathfinder`
	- Run from repository root and keep `src` layout intact.

- `Could not load grid` / file not found errors
	- Verify `GRID_FILE` paths point to your local `.npy` file.

- GUI does not open
	- Check Python has `tkinter` and that Matplotlib installed successfully.

- No route found
	- Start/goal may be invalid, blocked, or disconnected in the current grid.

## Academic Context

This repository appears structured for an NEA/coursework project and includes iterative backups and development scripts alongside the runnable source package.

