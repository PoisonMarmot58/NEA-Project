from pathlib import Path
import numpy as np

GRID_FILE = r"c:\Users\isaac\OneDrive\Desktop\NEA Project new\NEA-Project-2\Pathfinder Algorithm\Data\FullGridOfEurope.npy"

izmir = (2985, 2841)
piraeus = (3044, 2918)

print(f"Loading grid from {GRID_FILE}")
arr = np.load(GRID_FILE, allow_pickle=False)
height, width = arr.shape
print(f"Grid shape: {height} x {width}")

def val_at(pt):
    r, c = pt
    if 0 <= r < height and 0 <= c < width:
        return int(arr[r, c])
    return None

for name, pt in [("Izmir", izmir), ("Piraeus", piraeus)]:
    v = val_at(pt)
    print(f"{name} at {pt}: value={v}")

# Find nearest port cell (value 3 or 4) to Izmir within radius
from collections import deque

def find_nearest_of_type(start, desired_vals, max_radius=800):
    r0, c0 = start
    visited = set()
    q = deque()
    q.append((r0, c0, 0))
    visited.add((r0, c0))
    while q:
        r, c, d = q.popleft()
        if 0 <= r < height and 0 <= c < width:
            if arr[r, c] in desired_vals:
                return (r, c, arr[r, c], d)
        if d >= max_radius:
            continue
        for dr, dc in ((-1,0),(1,0),(0,-1),(0,1)):
            nr, nc = r+dr, c+dc
            if (nr, nc) not in visited and 0 <= nr < height and 0 <= nc < width:
                visited.add((nr, nc))
                q.append((nr, nc, d+1))
    return None

nearest_port = find_nearest_of_type(izmir, (3,4), max_radius=1200)
nearest_water = find_nearest_of_type(izmir, (0,), max_radius=1200)
print("Nearest port to Izmir (within 1200 steps):", nearest_port)
print("Nearest water to Izmir (within 1200 steps):", nearest_water)

nearest_port_p = find_nearest_of_type(piraeus, (3,4), max_radius=1200)
print("Nearest port to Piraeus (within 1200 steps):", nearest_port_p)

# Show a few nearby values around Izmir
print("Values around Izmir (radius 3):")
for dr in range(-3,4):
    row = []
    for dc in range(-3,4):
        pt = (izmir[0]+dr, izmir[1]+dc)
        row.append(str(val_at(pt)))
    print(" ".join(row))

print("Done.")

# Recreate primary water component seeding used by the GUI
import json
PORTS_FILE = Path(__file__).resolve().parent / "data" / "ports.json"
with open(PORTS_FILE, 'r', encoding='utf-8') as f:
    ports = json.load(f)

seed_name = "Southampton"
if not any(p["name"] == seed_name for p in ports):
    seed_name = ports[0]["name"]

# Find the port record for the seed
seed_port = next((p for p in ports if p["name"] == seed_name), None)
seed_coords = (seed_port["grid_row"], seed_port["grid_col"]) if seed_port else None
print(f"Seed port: {seed_name} -> {seed_coords}")

# nearest water cell for seed
seed_nearest_water = find_nearest_of_type(seed_coords, (0,), max_radius=1200) if seed_coords else None
print("Seed nearest water:", seed_nearest_water)

# Build primary water mask floodfill from seed_nearest_water
mask = np.zeros((height, width), dtype=bool)
if seed_nearest_water:
    sr, sc = seed_nearest_water[0], seed_nearest_water[1]
    q = deque([(sr, sc)])
    mask[sr, sc] = True
    while q:
        r, c = q.popleft()
        for dr, dc in ((-1,0),(1,0),(0,-1),(0,1)):
            nr, nc = r+dr, c+dc
            if 0 <= nr < height and 0 <= nc < width and not mask[nr, nc] and arr[nr, nc] == 0:
                mask[nr, nc] = True
                q.append((nr, nc))

print(f"Izmir in primary water mask? {mask[izmir[0], izmir[1]]}")
print(f"Piraeus in primary water mask? {mask[piraeus[0], piraeus[1]]}")

# Find nearest mask cell to Izmir if not in mask
def find_nearest_mask_cell(start):
    r0, c0 = start
    visited = set()
    q = deque()
    q.append((r0, c0, 0))
    visited.add((r0, c0))
    while q:
        r, c, d = q.popleft()
        if 0 <= r < height and 0 <= c < width and mask[r, c]:
            return (r, c, d)
        for dr, dc in ((-1,0),(1,0),(0,-1),(0,1)):
            nr, nc = r+dr, c+dc
            if (nr, nc) not in visited and 0 <= nr < height and 0 <= nc < width:
                visited.add((nr, nc))
                q.append((nr, nc, d+1))
    return None

nearest_mask_izmir = find_nearest_mask_cell(izmir)
print("Nearest primary water mask cell to Izmir:", nearest_mask_izmir)

# Simulate GUI snapping for Izmir -> Felixstowe
def snap_port(port_name):
    rec = next((p for p in ports if p["name"] == port_name), None)
    if not rec:
        return None
    raw = (rec["grid_row"], rec["grid_col"])
    if arr[raw[0], raw[1]] in (3,4):
        snapped = raw
    elif mask[raw[0], raw[1]]:
        snapped = raw
    else:
        nm = find_nearest_mask_cell(raw)
        snapped = (nm[0], nm[1]) if nm else raw
    return raw, snapped

print("\nSimulated snapping:")
print("Izmir ->", snap_port("Izmir"))
print("Felixstowe ->", snap_port("Felixstowe"))

# Compare to interpolated coordinates from control points (as MapToGrid does)
from scipy.interpolate import LinearNDInterpolator
control_points = np.array([
    [51.923,  4.479,  2001,         1950],    # Rotterdam
    [53.547,  9.987,  2214,         1895],    # Hamburg
    [36.140, -5.435,  1298,        3025],    # Gibraltar
    [37.942, 23.637,  3044,         2918],   # Piraeus
    [38.710, -9.126,  1145,         2806],   # Lisbon
    [51.962, 1.351,  1842,         1892]   # Felixstowe
])
latlons = control_points[:, :2]
pixels = control_points[:, 2:]
interp_row = LinearNDInterpolator(latlons, pixels[:, 0])
interp_col = LinearNDInterpolator(latlons, pixels[:, 1])

iz_lat, iz_lon = 38.42, 27.14
row_est = interp_row(iz_lat, iz_lon)
col_est = interp_col(iz_lat, iz_lon)
print(f"Interpolated Izmir -> row_est={row_est}, col_est={col_est}")

# Try interpolation from existing ports.json entries (leave Izmir out)
pts = np.array([[p["latitude"], p["longitude"]] for p in ports if p["name"] != "Izmir"])
pix = np.array([[p["grid_row"], p["grid_col"]] for p in ports if p["name"] != "Izmir"])
interp_r2 = LinearNDInterpolator(pts, pix[:,0])
interp_c2 = LinearNDInterpolator(pts, pix[:,1])
row_e2 = interp_r2(iz_lat, iz_lon)
col_e2 = interp_c2(iz_lat, iz_lon)
print(f"Ports.json-based interpolation Izmir -> row={row_e2}, col={col_e2}")
