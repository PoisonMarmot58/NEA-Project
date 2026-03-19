#!/usr/bin/env python3
"""
Coordinate picker for control points.
Click on the map to get grid coordinates of major ports.
Keeps a running list of selected control points.
Supports zooming and panning.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import json

try:
    import tkinter as tk
    from tkinter import simpledialog
except Exception:
    tk = None
    simpledialog = None

# Configuration
GRID_PATH = 'Pathfinder Algorithm/Data/FullGridOfEurope.npy'
OUTPUT_FILE = 'user_control_points.json'

# Load grid
grid = np.load(GRID_PATH)
print(f"Grid loaded: {grid.shape}")

# Prepare display
fig, ax = plt.subplots(figsize=(18, 14), dpi=100)
grid_display = np.where(grid == 0, 0, np.where(grid == 1, 1, 2))
im = ax.imshow(grid_display, cmap='terrain', origin='upper', interpolation='nearest')

# Add gridlines
major_interval = 200
ax.set_xticks(np.arange(0, grid.shape[1], major_interval), minor=False)
ax.set_yticks(np.arange(0, grid.shape[0], major_interval), minor=False)
ax.set_xticks(np.arange(0, grid.shape[1], 100), minor=True)
ax.set_yticks(np.arange(0, grid.shape[0], 100), minor=True)
ax.grid(which='major', color='gray', linestyle='-', linewidth=0.5, alpha=0.5)
ax.grid(which='minor', color='gray', linestyle=':', linewidth=0.3, alpha=0.3)

ax.set_xlabel('Column (X / Longitude)', fontsize=12, fontweight='bold')
ax.set_ylabel('Row (Y / Latitude)', fontsize=12, fontweight='bold')
ax.set_title(
    'Interactive Control Point Picker\n'
    'Click to mark port locations | Right-click to remove | '
    'Scroll to zoom | Middle-drag to pan',
    fontsize=14,
    fontweight='bold',
)

# Legend
water_patch = mpatches.Patch(color='#0000FF', label='Water')
land_patch = mpatches.Patch(color='#C2B280', label='Land')
ax.legend(handles=[water_patch, land_patch], loc='upper right', fontsize=10)

# State
control_points = {}  # { port_name: (row, col), ... }
markers = {}  # { port_name: marker_object, ... }
text_objects = {}  # { port_name: text_object, ... }
auto_point_counter = 1

# Keep one hidden Tk root for dialogs (more reliable than creating per-click).
dialog_root = None
if tk is not None and simpledialog is not None:
    try:
        dialog_root = tk.Tk()
        dialog_root.withdraw()
    except Exception:
        dialog_root = None

# Status text
status_text = ax.text(0.02, 0.98, '', transform=ax.transAxes,
                      verticalalignment='top', fontsize=10,
                      bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
                      family='monospace')

def update_status():
    """Update status display"""
    lines = [
        "CONTROL POINTS:",
        "-" * 40,
    ]
    if control_points:
        for port, (row, col) in sorted(control_points.items()):
            # Check if on water
            cell_value = grid[int(row), int(col)]
            is_water = "WATER" if cell_value == 0 else f"LAND({cell_value})"
            lines.append(f"  {port:20s} R:{row:4d} C:{col:4d} [{is_water}]")
    else:
        lines.append("  (none selected yet)")
    
    lines.extend([
        "-" * 40,
        f"Total: {len(control_points)} points",
    ])
    
    status_text.set_text('\n'.join(lines))
    fig.canvas.draw_idle()

def on_click(event):
    """Handle mouse clicks on the map"""
    global auto_point_counter

    if event.inaxes != ax:
        return

    if event.xdata is None or event.ydata is None:
        return

    # If Matplotlib navigation mode is active, left click is consumed for zoom/pan.
    nav_mode = ax.get_navigate_mode()
    if nav_mode in ("PAN", "ZOOM"):
        print(f"Navigation mode '{nav_mode}' is active. Disable it to add/remove points.")
        return
    
    col, row = int(np.round(event.xdata)), int(np.round(event.ydata))
    
    # Bounds check
    if row < 0 or row >= grid.shape[0] or col < 0 or col >= grid.shape[1]:
        print(f"Out of bounds: ({row}, {col})")
        return
    
    if event.button == 1:  # Left click - add point
        # Ask for port name
        port_name = None
        if dialog_root is not None and simpledialog is not None:
            try:
                port_name = simpledialog.askstring(
                    "Port Name",
                    f"Enter port name for ({row}, {col}):",
                    parent=dialog_root,
                )
            except Exception:
                port_name = None

        if port_name is None or not port_name.strip():
            port_name = f"Point_{auto_point_counter}"
            auto_point_counter += 1
            print(f"No name entered. Using auto name: {port_name}")
        
        if port_name:
            port_name = port_name.strip()
            
            # Remove old marker if exists
            if port_name in markers:
                markers[port_name].remove()
                text_objects[port_name].remove()
            
            # Add new marker
            marker, = ax.plot(col, row, 'r*', markersize=20, markeredgecolor='white', 
                            markeredgewidth=2, label=port_name, zorder=5)
            text_obj = ax.text(col + 50, row - 50, port_name, color='red', 
                             fontsize=9, fontweight='bold',
                             bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
            
            control_points[port_name] = (row, col)
            markers[port_name] = marker
            text_objects[port_name] = text_obj
            
            # Check water status
            cell_val = grid[row, col]
            cell_type = "WATER" if cell_val == 0 else f"LAND({cell_val})"
            print(f"Added: {port_name:20s} @ ({row:4d}, {col:4d}) [{cell_type}]")
            
            update_status()
    
    elif event.button == 3:  # Right click - remove point
        # Find closest point
        min_dist = float('inf')
        closest_port = None
        for port, (p_row, p_col) in control_points.items():
            dist = np.sqrt((row - p_row)**2 + (col - p_col)**2)
            if dist < min_dist:
                min_dist = dist
                closest_port = port
        
        if closest_port and min_dist < 100:
            markers[closest_port].remove()
            text_objects[closest_port].remove()
            del control_points[closest_port]
            del markers[closest_port]
            del text_objects[closest_port]
            print(f"Removed: {closest_port}")
            update_status()

def on_close(event):
    """Save when window closes"""
    if dialog_root is not None:
        try:
            dialog_root.destroy()
        except Exception:
            pass

    if control_points:
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(control_points, f, indent=2)
        print(f"\nSaved {len(control_points)} control points to {OUTPUT_FILE}")
        print("\nNext step: Run InteractivePortInterpolator.py with:")
        print(f"  python InteractivePortInterpolator.py --from-controls {OUTPUT_FILE}")
    else:
        print("No control points selected.")

def on_scroll(event):
    """Scroll wheel zoom"""
    if event.inaxes != ax:
        return
    
    # Get current axis limits
    cur_xlim = ax.get_xlim()
    cur_ylim = ax.get_ylim()
    
    xdata = event.xdata
    ydata = event.ydata
    
    # Zoom factor
    if event.button == 'up':
        scale_factor = 0.8  # Zoom in
    elif event.button == 'down':
        scale_factor = 1.2  # Zoom out
    else:
        return
    
    # Calculate new limits
    new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
    new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor
    
    relx = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
    rely = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])
    
    ax.set_xlim([xdata - new_width * (1 - relx), xdata + new_width * relx])
    ax.set_ylim([ydata - new_height * (1 - rely), ydata + new_height * rely])
    
    fig.canvas.draw_idle()

# Connect events
fig.canvas.mpl_connect('button_press_event', on_click)
fig.canvas.mpl_connect('scroll_event', on_scroll)
fig.canvas.mpl_connect('close_event', on_close)

# Add instructions panel
instruction_text = ax.text(0.98, 0.02, 
    'LEFT-CLICK: Add point\nRIGHT-CLICK: Remove\nSCROLL: Zoom\nMIDDLE-DRAG: Pan',
    transform=ax.transAxes, fontsize=9,
    verticalalignment='bottom', horizontalalignment='right',
    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8),
    family='monospace')

print("\nCoordinate picker")
print("- Left-click: add/update point")
print("- Right-click: remove nearest point")
print("- Scroll: zoom")
print("- Middle-drag: pan")
print("Close the window to save to user_control_points.json\n")

update_status()
plt.tight_layout()
plt.show()
