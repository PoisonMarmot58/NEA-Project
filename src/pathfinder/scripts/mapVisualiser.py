import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

# Your file path
NPY_PATH = r"c:\Users\isaac\OneDrive\Desktop\NEA Project new\NEA-Project-2\Pathfinder Algorithm\Data\FullGridOfEurope.npy"

print("Loading .npy file...")
try:
    arr = np.load(NPY_PATH)
    print(f"Success! Array shape: {arr.shape}")
    print(f"Data type: {arr.dtype}")
except Exception as e:
    print(f"Failed to load file:\n{e}")
    exit()

# ─────────────── Basic statistics ───────────────
unique_vals, counts = np.unique(arr, return_counts=True)
print("\nUnique values in the array:")
for v, c in zip(unique_vals, counts):
    print(f"  Value {v:3d} → {c:8,} pixels ({c / arr.size * 100:5.2f}%)")

print(f"\nMin value: {arr.min()}")
print(f"Max value: {arr.max()}")
print(f"Contains 0? {0 in unique_vals}")
print(f"Contains 3 or 4? {3 in unique_vals or 4 in unique_vals}")

# ─────────────── Visualization ───────────────
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

# Left: raw values as grayscale
ax1.imshow(arr, cmap='gray', origin='upper')
ax1.set_title("Raw array values (grayscale)")
ax1.axis('off')

# Right: color-coded interpretation
colors = ['#000000', '#444444', '#888888', '#FF0000', '#FF5555']  # 0 black, 1 dark gray, 2 light gray, 3 red, 4 bright red
cmap = ListedColormap(colors)

# Clip values outside 0-4 to avoid index errors
arr_clipped = np.clip(arr, 0, 4)

ax2.imshow(arr_clipped, cmap=cmap, origin='upper', interpolation='nearest')
ax2.set_title("Interpreted map\n(black=0 water, gray=land/border, red=ports)")
ax2.axis('off')

plt.suptitle("Map Debug Visualization", fontsize=16)
plt.tight_layout()
plt.show()

print("\nDone. Close the plot window to exit.")
