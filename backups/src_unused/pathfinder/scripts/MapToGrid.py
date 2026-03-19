"""MapToGrid module."""

import numpy as np
from PIL import Image
import os
from scipy.signal import convolve2d
from scipy.interpolate import LinearNDInterpolator


# CONFIGURATION

IMAGE_PATH = (
    r"c:\Users\isaac\OneDrive\Desktop\NEA Project new\NEA-Project-2"
    r"\Pathfinder Algorithm\Maps\MapOfEuropeNonNamed.png"
)

GRID_FILE = "BackupGrid.npy"
GRID_WITH_PORTS_FILE = "FullGridOfEurope.npy"


# Build the base grid

def create_grid(image_path=IMAGE_PATH):
    """Load the image and build a base 2D grid."""
    if not os.path.exists(image_path):
        print("ERROR: Image not found!")
        print("Path:", image_path)
        return None

    try:
        img = Image.open(image_path).convert('RGB')
    except Exception as e:
        print(f"Failed to open image: {e}")
        return None

    arr = np.array(img)

    grid = np.zeros(arr.shape[:2], dtype=np.uint8)

    grid[np.all(arr == [255, 255, 250], axis=-1)] = 0   # water
    grid[np.all(arr == [0, 0, 0],         axis=-1)] = 1   # land
    grid[np.all(arr == [163, 73, 164],    axis=-1)] = 2   # border

    print("Grid created successfully!")
    print(f"Shape: {grid.shape[0]:4d} × {grid.shape[1]:4d}")
    print(f"Water:  {np.sum(grid==0):7,d}")
    print(f"Land:   {np.sum(grid==1):7,d}")
    print(f"Border: {np.sum(grid==2):7,d}\n")

    return grid

# Detect coastline candidates

def detect_potential_ports(grid, use_8_directions=False):
    """Find land pixels (1) adjacent to water (0) → mark as 3"""
    if grid is None:
        return None

    land_mask  = (grid == 1)
    water_mask = (grid == 0)

    if use_8_directions:
        kernel = np.ones((3, 3), dtype=int)
        kernel[1, 1] = 0  # don't count center
    else:
        kernel = np.array([[0,1,0],
                           [1,0,1],
                           [0,1,0]])

    water_neighbors = convolve2d(water_mask.astype(int), kernel, mode='same')
    port_mask = land_mask & (water_neighbors > 0)

    new_grid = grid.copy()
    new_grid[port_mask] = 3  # 3 = potential port

    count = np.sum(port_mask)
    print(f"Detected {count:,} potential port pixels "
          f"({'8-dir' if use_8_directions else '4-dir'})")

    return new_grid

#add ports

def add_real_major_ports(grid, control_points_list, real_ports_list):
    """Approximate real ports using control points interpolation"""
    if not control_points_list:
        print("No control points provided → skipping real ports")
        return grid

    control_points = np.array(control_points_list)
    lats_lons = control_points[:, :2]
    pixels    = control_points[:, 2:]   # [row_y, col_x]

    interp_row = LinearNDInterpolator(lats_lons, pixels[:, 0])
    interp_col = LinearNDInterpolator(lats_lons, pixels[:, 1])

    new_grid = grid.copy()

    print("\nReal major ports approximation:")
    for port in real_ports_list:
        row = interp_row(port["lat"], port["lon"])
        col = interp_col(port["lat"], port["lon"])

        if np.isnan(row) or np.isnan(col):
            print(f"{port['name']:18} → outside map area")
            continue

        row = int(np.round(interp_row(port["lat"], port["lon"])))
        col = int(np.round(interp_col(port["lat"], port["lon"])))

        if 0 <= row < new_grid.shape[0] and 0 <= col < new_grid.shape[1]:
            # Mark small area around the point (5×5)
            r_start = max(0, row-2)
            r_end   = min(new_grid.shape[0], row+3)
            c_start = max(0, col-2)
            c_end   = min(new_grid.shape[1], col+3)

            new_grid[r_start:r_end, c_start:c_end] = 4  # 4 = real major port

            print(f"{port['name']:18} → ({row:4d}, {col:4d})")
        else:
            print(f"{port['name']:18} → coordinates out of bounds")

    return new_grid

# Main

if __name__ == "__main__":
    print("Europe port locator\n")

    #  Create or load basic grid
    if not os.path.exists(GRID_FILE):
        print("Creating grid from image...")
        grid = create_grid()
        if grid is not None:
            np.save(GRID_FILE, grid)
            print(f"Saved basic grid: {GRID_FILE}\n")
    else:
        print(f"Loading existing grid: {GRID_FILE}")
        grid = np.load(GRID_FILE)

    if grid is None:
        print("Cannot continue - grid creation/loading failed.")
    else:
        #Detect potential ports (coastline)
        print("Detecting potential ports...")
        grid_with_ports = detect_potential_ports(grid, use_8_directions=False)

        #Optional: Add real major ports (fill these!)
        
        control_points = [
            # [lat,   lon,    pixel_row(y), pixel_col(x)]
            [51.923,  4.479,  2001,         1950],    # Rotterdam
            [53.547,  9.987,  2214,         1895],    # Hamburg
            [36.140, -5.435,  1298,        3025],    # Gibraltar
            [37.942, 23.637,  3044,         2918],   # Piraeus
            [38.710, -9.126,  1145,         2806],   # Lisbon
            [51.962, 1.351,  1842,         1892]   # Felixstowe
        ]

        real_ports = [
    # Netherlands
    {"name": "Rotterdam",            "lat": 51.923,  "lon":  4.479},   # Europe's largest port
    {"name": "Amsterdam",            "lat": 52.370,  "lon":  4.890},
    {"name": "Moerdijk",             "lat": 51.700,  "lon":  4.630},

    # Belgium
    {"name": "Antwerp-Bruges",       "lat": 51.260,  "lon":  4.400},   # 2nd largest in Europe

    # Germany
    {"name": "Hamburg",              "lat": 53.547,  "lon":  9.987},
    {"name": "Bremerhaven",          "lat": 53.540,  "lon":  8.580},
    {"name": "Wilhelmshaven/JadeWeser", "lat": 53.515, "lon": 8.140},

    # Spain
    {"name": "Algeciras",            "lat": 36.140,  "lon": -5.435},   # Major transshipment hub
    {"name": "Valencia",             "lat": 39.455,  "lon": -0.320},
    {"name": "Barcelona",            "lat": 41.350,  "lon":  2.150},
    {"name": "Bilbao",               "lat": 43.260,  "lon": -2.930},
    {"name": "Las Palmas (Canary)",  "lat": 28.140,  "lon": -15.420},

    # Italy
    {"name": "Trieste",              "lat": 45.650,  "lon": 13.770},
    {"name": "Genoa",                "lat": 44.410,  "lon":  8.930},
    {"name": "La Spezia",            "lat": 44.110,  "lon":  9.820},
    {"name": "Naples",               "lat": 40.840,  "lon": 14.250},

    # Greece
    {"name": "Piraeus",              "lat": 37.942,  "lon": 23.637},   # COSCO controlled – very large

    # United Kingdom
    {"name": "Felixstowe",           "lat": 51.963,  "lon":  1.351},   # UK's largest container port
    {"name": "Southampton",          "lat": 50.910,  "lon": -1.404},
    {"name": "London Gateway",       "lat": 51.500,  "lon":  0.460},
    {"name": "Liverpool (Peel Ports)", "lat": 53.400, "lon": -3.000},

    # France
    {"name": "Le Havre",             "lat": 49.490,  "lon":  0.107},
    {"name": "Marseille-Fos",        "lat": 43.380,  "lon":  5.040},
    {"name": "Dunkirk",              "lat": 51.030,  "lon":  2.370},

    # Poland
    {"name": "Gdansk",               "lat": 54.360,  "lon": 18.645},
    {"name": "Gdynia",               "lat": 54.520,  "lon": 18.530},

    # Portugal
    {"name": "Sines",                "lat": 37.950,  "lon": -8.890},   # Growing fast
    {"name": "Lisbon",               "lat": 38.720,  "lon": -9.140},

    # Scandinavia / Baltic
    {"name": "Gothenburg",           "lat": 57.700,  "lon": 11.970},   # Sweden
    {"name": "Aarhus",               "lat": 56.150,  "lon": 10.210},   # Denmark
    {"name": "Copenhagen-Malmo",     "lat": 55.670,  "lon": 12.590},
    {"name": "Helsinki",             "lat": 60.170,  "lon": 24.940},   # Finland
    {"name": "Klaipeda",             "lat": 55.710,  "lon": 21.130},   # Lithuania

    # Other important / emerging
    {"name": "Constanta",            "lat": 44.170,  "lon": 28.650},   # Romania – Black Sea
    {"name": "Izmir",                "lat": 38.420,  "lon": 27.140},   # Turkey
    {"name": "Koper",                "lat": 45.550,  "lon": 13.730},   # Slovenia
    {"name": "Rijeka",               "lat": 45.330,  "lon": 14.440},   # Croatia
]
        # ------------------------------------------------------------------

        if control_points:
            print("Adding approximated real major ports...")
            final_grid = add_real_major_ports(grid_with_ports, control_points, real_ports)
        else:
            final_grid = grid_with_ports

        # 4. Save final result
        np.save(GRID_WITH_PORTS_FILE, final_grid)
        print(f"\nFinal grid saved as: {GRID_WITH_PORTS_FILE}")

# 0- water
# 1- land
# 2- border
# 3- potential port
# 4- real major ports
