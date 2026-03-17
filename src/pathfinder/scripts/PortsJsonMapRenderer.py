"""Create a simplified map diagram and overlay port locations from a ports JSON file."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GRID = ROOT / "Pathfinder Algorithm" / "Data" / "FullGridOfEurope.npy"
DEFAULT_PORTS = ROOT / "src" / "pathfinder" / "data" / "ports_recreated_realigned.json"
DEFAULT_OUTPUT = ROOT / "ports_map_diagram.png"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create a simplified map diagram + ports from JSON and save as an image."
    )
    parser.add_argument("--grid", type=Path, default=DEFAULT_GRID, help="Path to .npy grid file")
    parser.add_argument("--ports", type=Path, default=DEFAULT_PORTS, help="Path to ports JSON file")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Path to output PNG")
    parser.add_argument(
        "--show",
        action="store_true",
        help="Also open a matplotlib window after saving",
    )
    parser.add_argument(
        "--labels",
        action="store_true",
        help="Draw port name labels next to markers",
    )
    parser.add_argument(
        "--block-size",
        type=int,
        default=12,
        help="Block size used to simplify the map into a diagram (higher = simpler)",
    )
    return parser.parse_args()


def load_ports(ports_path: Path):
    # utf-8-sig gracefully handles files with or without BOM.
    with ports_path.open("r", encoding="utf-8-sig") as f:
        records = json.load(f)

    ports = []
    for rec in records:
        if "grid_row" not in rec or "grid_col" not in rec:
            continue
        ports.append(
            {
                "name": str(rec.get("name", "Unknown")),
                "country": str(rec.get("country", "")),
                "row": int(rec["grid_row"]),
                "col": int(rec["grid_col"]),
            }
        )
    return ports


def build_diagram_grid(grid: np.ndarray, block_size: int) -> np.ndarray:
    """Reduce detailed raster map into a coarse diagram grid (water vs land)."""
    if block_size < 1:
        block_size = 1

    h, w = grid.shape
    rows = (h + block_size - 1) // block_size
    cols = (w + block_size - 1) // block_size

    diagram = np.zeros((rows, cols), dtype=np.uint8)

    # 0 = water-dominant block, 1 = land-dominant block
    for r in range(rows):
        r0 = r * block_size
        r1 = min(h, r0 + block_size)
        for c in range(cols):
            c0 = c * block_size
            c1 = min(w, c0 + block_size)
            block = grid[r0:r1, c0:c1]
            water_ratio = float(np.mean(block == 0))
            diagram[r, c] = 0 if water_ratio >= 0.5 else 1

    return diagram


def snap_to_nearest_water(grid: np.ndarray, row: int, col: int, max_radius: int = 160):
    """Snap a point to nearest water cell (value 0) to improve visual port placement."""
    h, w = grid.shape
    if not (0 <= row < h and 0 <= col < w):
        return row, col
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
            dist = (r - row) ** 2 + (c - col) ** 2
            if dist < best_dist:
                best_dist = dist
                best = (r, c)

    return best if best is not None else (row, col)


def main():
    args = parse_args()

    if not args.grid.exists():
        raise FileNotFoundError(f"Grid file not found: {args.grid}")
    if not args.ports.exists():
        raise FileNotFoundError(f"Ports file not found: {args.ports}")

    grid = np.load(args.grid, allow_pickle=False)
    ports = load_ports(args.ports)

    height, width = grid.shape
    valid_ports = []
    out_of_bounds = []
    moved_ports = 0

    for p in ports:
        if 0 <= p["row"] < height and 0 <= p["col"] < width:
            snapped_row, snapped_col = snap_to_nearest_water(grid, p["row"], p["col"])
            if (snapped_row, snapped_col) != (p["row"], p["col"]):
                moved_ports += 1
            p["plot_row"] = snapped_row
            p["plot_col"] = snapped_col
            valid_ports.append(p)
        else:
            out_of_bounds.append(p)

    block_size = max(1, int(args.block_size))
    diagram = build_diagram_grid(grid, block_size)

    # Diagram palette: blue water, green land
    cmap = plt.matplotlib.colors.ListedColormap(["#3f8be0", "#4e8c4a"])

    fig, ax = plt.subplots(figsize=(16, 10))
    ax.imshow(
        diagram,
        origin="upper",
        cmap=cmap,
        interpolation="nearest",
        extent=[0, width, height, 0],
    )

    if valid_ports:
        cols = [p["plot_col"] for p in valid_ports]
        rows = [p["plot_row"] for p in valid_ports]
        ax.scatter(
            cols,
            rows,
            s=36,
            c="#ffd400",
            edgecolors="black",
            linewidths=0.6,
            alpha=0.95,
            label=f"JSON ports ({len(valid_ports)})",
            zorder=4,
        )

        if args.labels:
            for p in valid_ports:
                ax.text(
                    p["plot_col"] + 10,
                    p["plot_row"] - 10,
                    p["name"],
                    fontsize=7,
                    color="white",
                    bbox={"facecolor": "black", "alpha": 0.35, "pad": 1.2},
                    zorder=5,
                )

    ax.set_title(
        f"Map Diagram With Ports ({args.ports.name})\n"
        f"Grid simplified by {block_size}x{block_size} blocks"
    )
    ax.axis("off")
    ax.legend(loc="lower left")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(args.output, dpi=180)

    print(f"Saved map diagram: {args.output}")
    print(f"Grid shape: {height} x {width}")
    print(f"Ports loaded: {len(ports)}")
    print(f"Ports plotted: {len(valid_ports)}")
    print(f"Ports snapped to water: {moved_ports}")
    print(f"Ports out of bounds: {len(out_of_bounds)}")

    if out_of_bounds:
        print("Out-of-bounds examples:")
        for p in out_of_bounds[:10]:
            print(f"  {p['name']}: ({p['row']}, {p['col']})")

    if args.show:
        plt.show()
    else:
        plt.close(fig)


if __name__ == "__main__":
    main()
