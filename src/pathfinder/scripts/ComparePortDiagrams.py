"""Create a comparison diagram for old vs recreated port coordinates."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[3]
GRID_PATH = ROOT / "Pathfinder Algorithm" / "Data" / "FullGridOfEurope.npy"
OLD_PORTS_PATH = ROOT / "backups" / "data" / "ports_remapped_izmir.json"
NEW_PORTS_PATH = ROOT / "src" / "pathfinder" / "data" / "ports_recreated_realigned.json"
OUT_PATH = ROOT / "ports_comparison_diagram.png"


def parse_args():
    parser = argparse.ArgumentParser(description="Compare old vs recreated port coordinates.")
    parser.add_argument("--grid", type=Path, default=GRID_PATH)
    parser.add_argument("--old", type=Path, default=OLD_PORTS_PATH)
    parser.add_argument("--new", type=Path, default=NEW_PORTS_PATH)
    parser.add_argument("--output", type=Path, default=OUT_PATH)
    parser.add_argument("--block-size", type=int, default=12)
    return parser.parse_args()


def load_ports(path: Path):
    records = json.loads(path.read_text(encoding="utf-8-sig"))
    by_name = {}
    for r in records:
        by_name[r["name"]] = (int(r["grid_row"]), int(r["grid_col"]))
    return by_name


def build_diagram(grid: np.ndarray, block_size: int) -> np.ndarray:
    h, w = grid.shape
    rows = (h + block_size - 1) // block_size
    cols = (w + block_size - 1) // block_size
    diagram = np.zeros((rows, cols), dtype=np.uint8)

    for r in range(rows):
        r0 = r * block_size
        r1 = min(h, r0 + block_size)
        for c in range(cols):
            c0 = c * block_size
            c1 = min(w, c0 + block_size)
            block = grid[r0:r1, c0:c1]
            diagram[r, c] = 0 if np.mean(block == 0) >= 0.5 else 1
    return diagram


def main():
    args = parse_args()
    grid = np.load(args.grid, allow_pickle=False)
    h, w = grid.shape

    old_ports = load_ports(args.old)
    new_ports = load_ports(args.new)

    common_names = sorted(set(old_ports) & set(new_ports))
    moved_names = [n for n in common_names if old_ports[n] != new_ports[n]]

    diagram = build_diagram(grid, max(1, int(args.block_size)))
    cmap = plt.matplotlib.colors.ListedColormap(["#3f8be0", "#4e8c4a"])

    fig, axes = plt.subplots(1, 3, figsize=(21, 8), constrained_layout=True)

    for ax in axes:
        ax.imshow(diagram, origin="upper", cmap=cmap, interpolation="nearest", extent=[0, w, h, 0])
        ax.axis("off")

    # Left: old coordinates
    old_cols = [old_ports[n][1] for n in common_names]
    old_rows = [old_ports[n][0] for n in common_names]
    axes[0].scatter(old_cols, old_rows, s=22, c="#ffd400", edgecolors="black", linewidths=0.4)
    axes[0].set_title(f"Old Coordinates\n{args.old.name}")

    # Middle: new coordinates
    new_cols = [new_ports[n][1] for n in common_names]
    new_rows = [new_ports[n][0] for n in common_names]
    axes[1].scatter(new_cols, new_rows, s=22, c="#ff8c00", edgecolors="black", linewidths=0.4)
    axes[1].set_title(f"Recreated Coordinates\n{args.new.name}")

    # Right: vector movement old -> new
    axes[2].scatter(old_cols, old_rows, s=14, c="#ffd400", alpha=0.55)
    axes[2].scatter(new_cols, new_rows, s=14, c="#ff8c00", alpha=0.85)

    for n in moved_names:
        r0, c0 = old_ports[n]
        r1, c1 = new_ports[n]
        axes[2].arrow(
            c0,
            r0,
            c1 - c0,
            r1 - r0,
            width=1.2,
            head_width=10,
            head_length=12,
            color="#ffffff",
            alpha=0.55,
            length_includes_head=True,
        )

    axes[2].set_title(f"Movement Vectors (Old -> New)\nMoved ports: {len(moved_names)}")

    fig.suptitle("Port Coordinate Comparison Diagram", fontsize=16)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=180)
    plt.close(fig)

    print(f"Saved comparison diagram: {args.output}")
    print(f"Common ports compared: {len(common_names)}")
    print(f"Ports moved: {len(moved_names)}")


if __name__ == "__main__":
    main()
