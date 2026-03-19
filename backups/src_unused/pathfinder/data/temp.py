"""temp module."""

import numpy as np

file = r"c:\Users\isaac\OneDrive\Desktop\NEA Project new\NEA-Project-2\Pathfinder Algorithm\Data\FullGridOfEurope.npy"
arr = np.load(file)

unique, counts = np.unique(arr, return_counts=True)
print("Values in your .npy file:")
for v, cnt in zip(unique, counts):
    print(f"  {v:3d} → {cnt:8,} pixels")

print(f"\nTotal pixels: {arr.size}")
print(f"Ports (3+4): {np.sum((arr == 3) | (arr == 4))}")
