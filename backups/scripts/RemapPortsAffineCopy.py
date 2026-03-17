"""Build a remapped copy of ports.json using an affine lat/lon-to-grid transform."""

import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
PORTS_IN = ROOT / "src" / "pathfinder" / "data" / "ports.json"
PORTS_OUT = ROOT / "src" / "pathfinder" / "data" / "ports_remapped_izmir.json"


EXCLUDE_FROM_FIT = {
    "Izmir",  # suspected bad coordinate
}

REMAP_ONLY = {
    "Izmir",
}


def fit_affine(records):
    # row = a0 + a1*lat + a2*lon
    # col = b0 + b1*lat + b2*lon
    x_rows = []
    y_row = []
    y_col = []

    for rec in records:
        if rec["name"] in EXCLUDE_FROM_FIT:
            continue
        lat = float(rec["latitude"])
        lon = float(rec["longitude"])
        x_rows.append([1.0, lat, lon])
        y_row.append(float(rec["grid_row"]))
        y_col.append(float(rec["grid_col"]))

    x = np.array(x_rows, dtype=float)
    row_target = np.array(y_row, dtype=float)
    col_target = np.array(y_col, dtype=float)

    row_coef, *_ = np.linalg.lstsq(x, row_target, rcond=None)
    col_coef, *_ = np.linalg.lstsq(x, col_target, rcond=None)
    return row_coef, col_coef


def predict(lat, lon, row_coef, col_coef):
    v = np.array([1.0, float(lat), float(lon)], dtype=float)
    row = int(round(float(v @ row_coef)))
    col = int(round(float(v @ col_coef)))
    return row, col


def main():
    with PORTS_IN.open("r", encoding="utf-8") as f:
        records = json.load(f)

    row_coef, col_coef = fit_affine(records)

    remapped = []
    for rec in records:
        lat = rec["latitude"]
        lon = rec["longitude"]
        new_rec = dict(rec)
        if rec["name"] in REMAP_ONLY:
            row, col = predict(lat, lon, row_coef, col_coef)
            new_rec["grid_row"] = row
            new_rec["grid_col"] = col
        remapped.append(new_rec)

    PORTS_OUT.parent.mkdir(parents=True, exist_ok=True)
    with PORTS_OUT.open("w", encoding="utf-8") as f:
        json.dump(remapped, f, indent=2)
        f.write("\n")

    iz = next(r for r in remapped if r["name"] == "Izmir")
    pi = next(r for r in remapped if r["name"] == "Piraeus")
    print(f"Wrote: {PORTS_OUT}")
    print(f"Izmir remapped -> ({iz['grid_row']}, {iz['grid_col']})")
    print(f"Piraeus unchanged -> ({pi['grid_row']}, {pi['grid_col']})")


if __name__ == "__main__":
    main()
