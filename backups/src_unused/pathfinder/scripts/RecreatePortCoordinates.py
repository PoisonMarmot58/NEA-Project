"""Rebuild grid coordinates from lat/lon and snap to nearby water cells."""

import json
from pathlib import Path

import numpy as np
from scipy.interpolate import LinearNDInterpolator


ROOT = Path(__file__).resolve().parents[3]
GRID_PATH = ROOT / "Pathfinder Algorithm" / "Data" / "FullGridOfEurope.npy"
SOURCE_PORTS = ROOT / "src" / "pathfinder" / "data" / "ports.json"
OUTPUT_PORTS = ROOT / "src" / "pathfinder" / "data" / "ports_recreated_realigned.json"

# Control points spread across North Sea, Atlantic, Mediterranean, Baltic, and Black Sea.
# [latitude, longitude, grid_row, grid_col]
CONTROL_POINTS = np.array(
    [
        [51.923, 4.479, 2001, 1950],   # Rotterdam
        [53.547, 9.987, 2214, 1895],   # Hamburg
        [51.963, 1.351, 1842, 1892],   # Felixstowe
        [50.910, -1.404, 1877, 1948],  # Southampton
        [36.140, -5.435, 1298, 2918],  # Algeciras
        [38.720, -9.140, 1145, 2806],  # Lisbon
        [39.455, -0.320, 1624, 2835],  # Valencia
        [41.350, 2.150, 1683, 2742],   # Barcelona
        [44.410, 8.930, 2193, 2511],   # Genoa
        [45.650, 13.770, 2235, 2224],  # Trieste
        [40.840, 14.250, 2437, 2442],  # Naples
        [37.942, 23.637, 3044, 2918],  # Piraeus
        [38.420, 27.140, 2847, 2796],  # Izmir
        [44.170, 28.650, 2800, 2554],  # Constanta
        [54.360, 18.645, 2615, 1723],  # Gdansk
        [57.700, 11.970, 2241, 1865],  # Gothenburg
    ],
    dtype=float,
)


def predict_with_interpolation(lat: float, lon: float, control_points: np.ndarray):
    """Predict (row, col) with linear interpolation and an IDW fallback."""
    geo = control_points[:, :2]
    rows = control_points[:, 2]
    cols = control_points[:, 3]

    interp_row = LinearNDInterpolator(geo, rows)
    interp_col = LinearNDInterpolator(geo, cols)

    row_val = interp_row(lat, lon)
    col_val = interp_col(lat, lon)

    if np.isnan(row_val) or np.isnan(col_val):
        # Outside the convex hull, use inverse-distance weighting on nearest controls.
        deltas = geo - np.array([lat, lon], dtype=float)
        distances = np.sqrt(np.sum(deltas * deltas, axis=1))
        k = min(4, len(distances))
        idx = np.argsort(distances)[:k]
        d = np.maximum(distances[idx], 1e-9)
        w = 1.0 / np.power(d, 2.0)
        w = w / np.sum(w)

        row_pred = float(np.sum(rows[idx] * w))
        col_pred = float(np.sum(cols[idx] * w))
        return int(round(row_pred)), int(round(col_pred))

    return int(round(float(row_val))), int(round(float(col_val)))


def snap_to_nearest_water(grid: np.ndarray, row: int, col: int, max_radius: int = 180):
    """Snap to nearest water cell (value 0) to align with navigable coastline/water."""
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


def main():
    ports = json.loads(SOURCE_PORTS.read_text(encoding="utf-8-sig"))
    grid = np.load(GRID_PATH, allow_pickle=False)

    recreated = []
    moved_count = 0
    for p in ports:
        lat = float(p["latitude"])
        lon = float(p["longitude"])

        row_pred, col_pred = predict_with_interpolation(lat, lon, CONTROL_POINTS)
        row_snap, col_snap = snap_to_nearest_water(grid, row_pred, col_pred)

        if (row_snap, col_snap) != (p["grid_row"], p["grid_col"]):
            moved_count += 1

        new_record = dict(p)
        new_record["grid_row"] = int(row_snap)
        new_record["grid_col"] = int(col_snap)
        recreated.append(new_record)

    OUTPUT_PORTS.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PORTS.write_text(json.dumps(recreated, indent=2) + "\n", encoding="utf-8")

    print(f"Recreated coordinates file: {OUTPUT_PORTS}")
    print(f"Ports processed: {len(recreated)}")
    print(f"Ports with changed coordinates: {moved_count}")

    for name in ["Izmir", "Piraeus", "Felixstowe", "Rotterdam", "Lisbon", "Constanta"]:
        rec = next((x for x in recreated if x["name"] == name), None)
        if rec:
            print(f"  {name:<12} -> ({rec['grid_row']}, {rec['grid_col']})")


if __name__ == "__main__":
    main()
