# Control Point Selection Guide

## What Are Control Points?

Control points are known, accurate geographic coordinates that anchor the interpolation system. The more accurate and geographically distributed your control points, the better the interpolation for all other ports.

## How to Use the Interactive Picker

### Launch the Tool
```powershell
cd 'c:\Users\isaac\OneDrive\Desktop\NEA Project new\NEA-Project-2'
python src/pathfinder/scripts/InteractiveCoordinatePicker.py
```

### Workflow
1. **Left-click** on the map where a port should be
2. Enter the **port name** when prompted
3. A red star will mark the location with coordinates in the status box
4. **Right-click** near a star to remove it
5. **Close the window** when done → saves to `user_control_points.json`

### Coordinate Interpretation
- **Row**: Vertical position (0 at top → 3196 at bottom)
- **Column**: Horizontal position (0 at left → 4592 at right)
- Status shows `[WATER]` if cell is on water (good), `[LAND(1)]` if on land (avoid)

---

## Best Practices for Control Point Selection

### 1. Coverage & Distribution
✓ Spread points across Europe (west, east, north, south)
✓ Include both major regional hubs and diverse coastal regions
✓ Minimum 4-5 points; 8-10 points recommended for accuracy

**Recommended Ports** (ordered geographically):

**Northern Europe:**
- Gothenburg (Sweden) — Far north, good for Scandinavia
- Hamburg (Germany) — Major North Sea hub
- Rotterdam (Netherlands) — Biggest European port, critical anchor
- Felixstowe (UK) — Major Atlantic gateway

**Western Europe:**
- Southampton (UK) — Western anchor
- Lisbon (Portugal) — Far west, Atlantic edge
- Algeciras (Spain) — Strategic strait point

**Mediterranean:**
- Barcelona (Spain) — Western Med
- Valencia (Spain) — Central Mediterranean
- Genoa (Italy) — Italian coast
- Naples (Italy) — Southern Italian coast
- Trieste (Italy/Slovenia) — Northern Adriatic

**Eastern Mediterranean & Black Sea:**
- Piraeus (Greece) — Key Mediterranean hub
- Izmir (Turkey) — Turkish Aegean coast
- Constanta (Romania) — Black Sea, far northeast

### 2. Water Cell Requirement
✓ **ALWAYS click on blue water cells**, not land
✗ If you see `[LAND(1)]` in status, move click slightly toward ocean
✓ Major ports are inherently on water/coast, so this should be natural

### 3. Accuracy Tips
- Zoom into the image mentally — use the gridlines as reference
- For well-known ports, be more precise (±10 pixels)
- For less-known ports, ±20 pixels acceptable
- If unsure, slightly favor a larger spread (prefer 8 medium-accuracy points over 5 very-precise ones)

### 4. Example: Finding Izmir
1. Look for Turkey's aegean coast (right side of map, middle latitude)
2. Find the bay/gulf shape that's Izmir
3. Click on the water cell inside that bay
4. Enter "Izmir" when prompted
5. Confirm status shows `[WATER]`

---

## After Selection: Integration

### Step 1: Generate Interpolated Ports
Once you've saved your control points (they auto-save to `user_control_points.json`):

```powershell
python src/pathfinder/scripts/InteractivePortInterpolator.py `
  --from-controls user_control_points.json `
  --output ports_user_calibrated.json `
  --controls-out user_control_points_saved.json
```

### Step 2: Validate the Output
```powershell
python src/pathfinder/scripts/PortsJsonMapRenderer.py `
  --source ports_user_calibrated.json `
  --labels
```
This generates `ports_map_diagram.png` — visually inspect to confirm all ports look reasonable.

### Step 3: Wire to Main App
Edit `src/pathfinder/FullSystem.py` to use the new ports file:
```python
PORTS_FILE = 'src/pathfinder/data/ports_user_calibrated.json'
```

---

## Troubleshooting

### "Some ports ended up on land!"
- Not all original ports may have valid water cells nearby
- This is OK — the interpolator will snap them to nearest water
- If too many are wrong, add more control points to those regions

### "Ports are still in wrong geographic locations"
- Need more control points in that region
- Check if region has control points (look at status box)
- Consider adding a known port from that area

### "How do I know if I got it right?"
- Run `PortsJsonMapRenderer.py` with the output
- Compare `ports_map_diagram.png` against MapOfEuropeNonNamed.png
- Major ports should align with major coastal cities
- No ports should be in interior Europe (except Danube/Black Sea)

---

## Quick Reference: Port Locations (Mental Map)

```
        NORTH
Gothenburg •
          Hamburg • Rotterdam • Felixstowe
WEST ←                              → EAST
    Lisbon •    • Southampton
            Algeciras •
        Barcelona •
        Valencia •
        Genoa •
        • Trieste      Piraeus •  Izmir •
        • Naples                  Constanta •
            SOUTH
```

---

## Alternative: Manual Entry

If you prefer not to use the GUI picker, you can manually create `user_control_points.json`:

```json
{
  "Rotterdam": [1234, 2345],
  "Hamburg": [1100, 2500],
  "Izmir": [2000, 3500],
  "Piraeus": [2200, 3200]
}
```

Format: `{ "PortName": [row, col], ... }`

Then run:
```powershell
python src/pathfinder/scripts/InteractivePortInterpolator.py `
  --from-controls user_control_points.json
```
