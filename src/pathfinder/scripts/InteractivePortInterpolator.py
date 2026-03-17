"""Interactive port coordinate interpolation.

Enter control points (port name + grid row/col), then interpolate all remaining ports
from lat/lon and save a new ports JSON.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from scipy.interpolate import LinearNDInterpolator


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE = ROOT / "src" / "pathfinder" / "data" / "ports.json"
DEFAULT_GRID = ROOT / "Pathfinder Algorithm" / "Data" / "FullGridOfEurope.npy"
DEFAULT_OUTPUT = ROOT / "src" / "pathfinder" / "data" / "ports_interpolated_user_controls.json"
DEFAULT_CONTROLS_OUT = ROOT / "src" / "pathfinder" / "data" / "user_control_points.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactively enter control-point coordinates and interpolate remaining ports."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Input ports JSON")
    parser.add_argument("--grid", type=Path, default=DEFAULT_GRID, help="Grid .npy file (for optional water snapping)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output ports JSON")
    parser.add_argument(
        "--controls-out",
        type=Path,
        default=DEFAULT_CONTROLS_OUT,
        help="Where to save entered control points",
    )
    parser.add_argument(
        "--no-snap",
        action="store_true",
        help="Disable snap-to-water after interpolation",
    )
    parser.add_argument(
        "--snap-radius",
        type=int,
        default=180,
        help="Max radius for snap-to-water search",
    )
    parser.add_argument(
        "--min-controls",
        type=int,
        default=4,
        help="Minimum number of control points required",
    )
    parser.add_argument(
        "--from-controls",
        type=Path,
        default=None,
        help="Optional JSON file with control points to skip prompts",
    )
    return parser.parse_args()


def normalize_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def load_ports(path: Path) -> List[dict]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_port_lookup(ports: List[dict]) -> Dict[str, dict]:
    return {normalize_name(p["name"]): p for p in ports}


def parse_row_col(raw: str) -> Tuple[int, int] | None:
    s = raw.strip().replace("(", "").replace(")", "")
    for sep in [",", " "]:
        if sep in s:
            parts = [x for x in s.split(sep) if x]
            if len(parts) == 2:
                try:
                    return int(parts[0]), int(parts[1])
                except ValueError:
                    return None
    return None


def interactive_collect_controls(ports: List[dict], min_controls: int) -> Dict[str, Tuple[int, int]]:
    print("\n=== Interactive Control Points ===")
    print("Enter port names + coordinates as: row,col")
    print("Type 'list' to show ports, 'done' to finish, 'remove <port>' to delete one.\n")

    lookup = build_port_lookup(ports)
    controls: Dict[str, Tuple[int, int]] = {}

    while True:
        name_in = input("Port name (or command): ").strip()
        if not name_in:
            continue

        cmd = normalize_name(name_in)
        if cmd == "list":
            print("\nPorts:")
            for p in ports:
                print(f"  - {p['name']}")
            print()
            continue

        if cmd.startswith("remove "):
            target = normalize_name(name_in[7:])
            if target in controls:
                del controls[target]
                print(f"Removed control point: {target}")
            else:
                print("Control point not found.")
            continue

        if cmd == "done":
            if len(controls) < min_controls:
                print(f"Need at least {min_controls} control points. Currently: {len(controls)}")
                continue
            break

        if cmd not in lookup:
            print("Port not found. Type 'list' to view valid names.")
            continue

        coord_in = input("Coordinate row,col: ").strip()
        parsed = parse_row_col(coord_in)
        if parsed is None:
            print("Invalid coordinate format. Example: 1842,1892")
            continue

        controls[cmd] = parsed
        print(f"Added: {lookup[cmd]['name']} -> {parsed}")

    return controls


def load_controls_file(path: Path, ports: List[dict]) -> Dict[str, Tuple[int, int]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    lookup = build_port_lookup(ports)
    controls: Dict[str, Tuple[int, int]] = {}

    if isinstance(payload, list):
        for row in payload:
            name = normalize_name(str(row["name"]))
            if name in lookup:
                controls[name] = (int(row["grid_row"]), int(row["grid_col"]))
    elif isinstance(payload, dict):
        for k, v in payload.items():
            name = normalize_name(str(k))
            if name in lookup and isinstance(v, (list, tuple)) and len(v) == 2:
                controls[name] = (int(v[0]), int(v[1]))

    return controls


def idw_fallback(lat: float, lon: float, control_points: np.ndarray, k: int = 4, power: float = 2.0) -> Tuple[int, int]:
    geo = control_points[:, :2]
    rc = control_points[:, 2:]

    delta = geo - np.array([lat, lon], dtype=float)
    dist = np.sqrt(np.sum(delta * delta, axis=1))

    exact = np.where(np.isclose(dist, 0.0))[0]
    if exact.size > 0:
        rr, cc = rc[exact[0]]
        return int(round(float(rr))), int(round(float(cc)))

    k = min(k, len(dist))
    idx = np.argsort(dist)[:k]
    d = np.maximum(dist[idx], 1e-9)
    w = 1.0 / np.power(d, power)
    w = w / np.sum(w)

    pred = np.sum(rc[idx] * w[:, None], axis=0)
    return int(round(float(pred[0]))), int(round(float(pred[1])))


def predict_row_col(lat: float, lon: float, control_points: np.ndarray) -> Tuple[int, int]:
    geo = control_points[:, :2]
    rows = control_points[:, 2]
    cols = control_points[:, 3]

    interp_row = LinearNDInterpolator(geo, rows)
    interp_col = LinearNDInterpolator(geo, cols)

    rv = interp_row(lat, lon)
    cv = interp_col(lat, lon)

    if np.isnan(rv) or np.isnan(cv):
        return idw_fallback(lat, lon, control_points)

    return int(round(float(rv))), int(round(float(cv)))


def snap_to_nearest_water(grid: np.ndarray, row: int, col: int, max_radius: int) -> Tuple[int, int]:
    h, w = grid.shape
    row = max(0, min(h - 1, row))
    col = max(0, min(w - 1, col))

    if grid[row, col] == 0:
        return row, col

    best = None
    best_dist = float("inf")

    r0 = max(0, row - max_radius)
    r1 = min(h - 1, row + max_radius)
    c0 = max(0, col - max_radius)
    c1 = min(w - 1, col + max_radius)

    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if grid[r, c] != 0:
                continue
            d = (r - row) ** 2 + (c - col) ** 2
            if d < best_dist:
                best_dist = d
                best = (r, c)

    return best if best is not None else (row, col)


def main() -> None:
    args = parse_args()

    ports = load_ports(args.source)
    lookup = build_port_lookup(ports)

    if args.from_controls:
        controls = load_controls_file(args.from_controls, ports)
        if len(controls) < args.min_controls:
            raise ValueError(
                f"Loaded {len(controls)} controls from file, but min required is {args.min_controls}."
            )
        print(f"Loaded {len(controls)} control points from {args.from_controls}")
    else:
        controls = interactive_collect_controls(ports, args.min_controls)

    grid = np.load(args.grid, allow_pickle=False)

    control_points = []
    for name_norm, (row, col) in controls.items():
        p = lookup[name_norm]
        control_points.append([float(p["latitude"]), float(p["longitude"]), float(row), float(col)])

    control_points_np = np.array(control_points, dtype=float)

    output_records = []
    changed = 0
    snapped = 0

    for p in ports:
        name_norm = normalize_name(p["name"])

        if name_norm in controls:
            row, col = controls[name_norm]
        else:
            row, col = predict_row_col(float(p["latitude"]), float(p["longitude"]), control_points_np)

        if not args.no_snap:
            r2, c2 = snap_to_nearest_water(grid, int(row), int(col), max_radius=max(1, args.snap_radius))
            if (r2, c2) != (row, col):
                snapped += 1
            row, col = r2, c2

        rec = dict(p)
        if (int(rec.get("grid_row", -1)), int(rec.get("grid_col", -1))) != (int(row), int(col)):
            changed += 1
        rec["grid_row"] = int(row)
        rec["grid_col"] = int(col)
        output_records.append(rec)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output_records, indent=2) + "\n", encoding="utf-8")

    controls_out_payload = [
        {
            "name": lookup[nm]["name"],
            "latitude": float(lookup[nm]["latitude"]),
            "longitude": float(lookup[nm]["longitude"]),
            "grid_row": int(rc[0]),
            "grid_col": int(rc[1]),
        }
        for nm, rc in sorted(controls.items())
    ]
    args.controls_out.parent.mkdir(parents=True, exist_ok=True)
    args.controls_out.write_text(json.dumps(controls_out_payload, indent=2) + "\n", encoding="utf-8")

    print("\n=== Interpolation Complete ===")
    print(f"Source ports: {args.source}")
    print(f"Output ports: {args.output}")
    print(f"Saved controls: {args.controls_out}")
    print(f"Control points used: {len(controls)}")
    print(f"Ports changed: {changed}")
    print(f"Ports snapped to water: {snapped}")


if __name__ == "__main__":
    main()
