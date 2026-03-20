# Software Requirements Specification (SRS)

## Restored Data Artifact

- **Filename added:** `src/pathfinder/data/FullGridOfEurope.npy`
- **Restored from commit:** `e539c13653353e3560e5635771eb3cbc29354cbc`
- **Original path in commit:** `backups/data/legacy_root/FullGridOfEurope.npy`
- **Date recovered:** 2026-03-19

This file was recovered from the repository history and placed into the project data folder so the GUI and scripts can load the grid without prompting for a file.

If you prefer the grid kept outside the repository (recommended for very large binary data), remove this file and use the `GRID_FILE` environment variable to point to a local copy instead.
