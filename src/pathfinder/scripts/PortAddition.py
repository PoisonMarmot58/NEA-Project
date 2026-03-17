"""Build and update ports.json with grid coordinates inferred from lat/lon."""

import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
PORTS_JSON_PATH = ROOT / "src" / "pathfinder" / "data" / "ports.json"
GRID_PATH = ROOT / "Pathfinder Algorithm" / "Data" / "FullGridOfEurope.npy"


# [latitude, longitude, grid_row, grid_col]
CONTROL_POINTS = np.array(
    [
        [51.923, 4.479, 2001, 1950],   # Rotterdam
        [53.547, 9.987, 2214, 1895],   # Hamburg
        [37.942, 23.637, 3044, 2918],  # Piraeus
        [36.140, -5.435, 1298, 2918],  # Gibraltar
        [39.455, -0.320, 1624, 2835],  # Valencia
        [51.963, 1.351, 1842, 1892],   # Felixstowe
        [44.410, 8.930, 2193, 2511],   # Genoa
        [54.360, 18.645, 2615, 1723],  # Gdansk
        [38.720, -9.140, 1145, 2806],  # Lisbon
    ],
    dtype=float,
)


PORTS = [
    {"name": "Rotterdam", "country": "Netherlands", "city": "Rotterdam", "lat": 51.923, "lon": 4.479},
    {"name": "Amsterdam", "country": "Netherlands", "city": "Amsterdam", "lat": 52.370, "lon": 4.890},
    {"name": "Moerdijk", "country": "Netherlands", "city": "Moerdijk", "lat": 51.700, "lon": 4.630},
    {"name": "Antwerp-Bruges", "country": "Belgium", "city": "Antwerp / Zeebrugge", "lat": 51.260, "lon": 4.400},
    {"name": "Hamburg", "country": "Germany", "city": "Hamburg", "lat": 53.547, "lon": 9.987},
    {"name": "Bremerhaven", "country": "Germany", "city": "Bremerhaven", "lat": 53.540, "lon": 8.580},
    {"name": "Wilhelmshaven/JadeWeser", "country": "Germany", "city": "Wilhelmshaven", "lat": 53.515, "lon": 8.140},
    {"name": "Algeciras", "country": "Spain", "city": "Algeciras", "lat": 36.140, "lon": -5.435},
    {"name": "Valencia", "country": "Spain", "city": "Valencia", "lat": 39.455, "lon": -0.320},
    {"name": "Barcelona", "country": "Spain", "city": "Barcelona", "lat": 41.350, "lon": 2.150},
    {"name": "Bilbao", "country": "Spain", "city": "Bilbao", "lat": 43.260, "lon": -2.930},
    {"name": "Las Palmas (Canary)", "country": "Spain", "city": "Las Palmas", "lat": 28.140, "lon": -15.420},
    {"name": "Trieste", "country": "Italy", "city": "Trieste", "lat": 45.650, "lon": 13.770},
    {"name": "Genoa", "country": "Italy", "city": "Genoa", "lat": 44.410, "lon": 8.930},
    {"name": "La Spezia", "country": "Italy", "city": "La Spezia", "lat": 44.110, "lon": 9.820},
    {"name": "Naples", "country": "Italy", "city": "Naples", "lat": 40.840, "lon": 14.250},
    {"name": "Piraeus", "country": "Greece", "city": "Piraeus (Athens)", "lat": 37.942, "lon": 23.637},
    {"name": "Felixstowe", "country": "United Kingdom", "city": "Felixstowe", "lat": 51.963, "lon": 1.351},
    {"name": "Southampton", "country": "United Kingdom", "city": "Southampton", "lat": 50.910, "lon": -1.404},
    {"name": "London Gateway", "country": "United Kingdom", "city": "Thurrock", "lat": 51.500, "lon": 0.460},
    {
        "name": "Liverpool (Peel Ports)",
        "country": "United Kingdom",
        "city": "Liverpool",
        "lat": 53.400,
        "lon": -3.000,
    },
    {"name": "Le Havre", "country": "France", "city": "Le Havre", "lat": 49.490, "lon": 0.107},
    {"name": "Marseille-Fos", "country": "France", "city": "Marseille / Fos", "lat": 43.380, "lon": 5.040},
    {"name": "Dunkirk", "country": "France", "city": "Dunkirk", "lat": 51.030, "lon": 2.370},
    {"name": "Gdansk", "country": "Poland", "city": "Gdansk", "lat": 54.360, "lon": 18.645},
    {"name": "Gdynia", "country": "Poland", "city": "Gdynia", "lat": 54.520, "lon": 18.530},
    {"name": "Sines", "country": "Portugal", "city": "Sines", "lat": 37.950, "lon": -8.890},
    {"name": "Lisbon", "country": "Portugal", "city": "Lisbon", "lat": 38.720, "lon": -9.140},
    {"name": "Gothenburg", "country": "Sweden", "city": "Gothenburg", "lat": 57.700, "lon": 11.970},
    {"name": "Aarhus", "country": "Denmark", "city": "Aarhus", "lat": 56.150, "lon": 10.210},
    {
        "name": "Copenhagen-Malmo",
        "country": "Denmark/Sweden",
        "city": "Copenhagen / Malmo",
        "lat": 55.670,
        "lon": 12.590,
    },
    {"name": "Helsinki", "country": "Finland", "city": "Helsinki", "lat": 60.170, "lon": 24.940},
    {"name": "Klaipeda", "country": "Lithuania", "city": "Klaipeda", "lat": 55.710, "lon": 21.130},
    {"name": "Constanta", "country": "Romania", "city": "Constanta", "lat": 44.170, "lon": 28.650},
    {"name": "Izmir", "country": "Turkey", "city": "Izmir", "lat": 38.420, "lon": 27.140},
    {"name": "Koper", "country": "Slovenia", "city": "Koper", "lat": 45.550, "lon": 13.730},
    {"name": "Rijeka", "country": "Croatia", "city": "Rijeka", "lat": 45.330, "lon": 14.440},
]


def load_grid_shape(grid_path: Path):
    if not grid_path.exists():
        return None

    try:
        grid = np.load(grid_path)
    except Exception:
        try:
            grid = np.load(grid_path, allow_pickle=True)
        except Exception as exc:
            print(f"Warning: could not read grid file '{grid_path}': {exc}")
            print("Continuing without grid bounds clamping.")
            return None

    # If the file contains a pickled scalar object, unwrap to the actual array-like value.
    if isinstance(grid, np.ndarray) and grid.dtype == object and grid.shape == ():
        grid = grid.item()

    shape = np.shape(grid)
    if len(shape) < 2:
        print(f"Warning: grid file '{grid_path}' does not contain a 2D array shape.")
        print("Continuing without grid bounds clamping.")
        return None
    return int(shape[0]), int(shape[1])


def estimate_grid_coordinates(lat, lon, control_points, nearest_k=4, power=2):
    """Estimate grid row/col with inverse-distance weighting from control points."""
    lat_lon = control_points[:, :2]
    grid_rc = control_points[:, 2:]

    deltas = lat_lon - np.array([lat, lon], dtype=float)
    distances = np.sqrt(np.sum(deltas * deltas, axis=1))

    exact_match = np.where(np.isclose(distances, 0.0))[0]
    if exact_match.size > 0:
        row, col = grid_rc[exact_match[0]]
        return int(round(float(row))), int(round(float(col)))

    nearest_indices = np.argsort(distances)[:nearest_k]
    nearest_distances = distances[nearest_indices]
    weights = 1.0 / np.power(nearest_distances, power)
    weights = weights / np.sum(weights)

    weighted_coords = np.sum(grid_rc[nearest_indices] * weights[:, None], axis=0)
    row, col = weighted_coords
    return int(round(float(row))), int(round(float(col)))


def clamp_to_grid(row, col, grid_shape):
    if grid_shape is None:
        return row, col

    max_row, max_col = grid_shape[0] - 1, grid_shape[1] - 1
    row = max(0, min(row, max_row))
    col = max(0, min(col, max_col))
    return row, col


def build_ports_json_records():
    grid_shape = load_grid_shape(GRID_PATH)

    updated_ports = []
    for port in PORTS:
        row, col = estimate_grid_coordinates(port["lat"], port["lon"], CONTROL_POINTS)
        row, col = clamp_to_grid(row, col, grid_shape)

        updated_ports.append(
            {
                "name": port["name"],
                "country": port["country"],
                "city": port["city"],
                "latitude": round(port["lat"], 6),
                "longitude": round(port["lon"], 6),
                "grid_row": row,
                "grid_col": col,
            }
        )

    return updated_ports


def write_ports_json(output_path: Path):
    records = build_ports_json_records()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
        f.write("\n")

    print(f"Updated {output_path} with {len(records)} ports.")
    print("Example entries:")
    for sample in records[:5]:
        print(
            f"  {sample['name']:<24} lat/lon=({sample['latitude']:.3f}, "
            f"{sample['longitude']:.3f}) -> grid=({sample['grid_row']}, {sample['grid_col']})"
        )


if __name__ == "__main__":
    write_ports_json(PORTS_JSON_PATH)
