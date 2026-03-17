"""Generate a remapped copy of ports.json without modifying the original."""

from pathlib import Path

from PortAddition import write_ports_json


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[3]
    output_path = root / "src" / "pathfinder" / "data" / "ports_remapped.json"
    write_ports_json(output_path)
    print(f"Remapped ports copy written to: {output_path}")
