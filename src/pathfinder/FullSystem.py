import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from collections import deque
import json
import sys
from pathlib import Path

# Ensure `src` directory is on sys.path so `import pathfinder` works
# when running this file directly (as a script).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pathfinder.algorithms.Astar import Grid, AStarPathfinder
from pathfinder.algorithms.CostCalculator import RouteCostEstimator

# ────────────────────────────────────────────────
#                     CONFIG
# ────────────────────────────────────────────────

GRID_FILE = r"c:\Users\isaac\OneDrive\Desktop\NEA Project new\NEA-Project-2\Pathfinder Algorithm\Data\FullGridOfEurope.npy"
PORTS_FILE = Path(__file__).resolve().parent / "data" / "ports_user_calibrated.json"

SHIP_PROFILES = {
    "Feeder (1k-3k TEU)": {
        "average_speed_knots": 15.0,
        "fuel_consumption_tpd": 30.0,
        "fuel_price_per_tonne": 620.0,
        "daily_operating_cost": 14000.0,
        "port_fee_per_stop": 40000.0,
        "contingency_percent": 0.10,
    },
    "Panamax (3k-5k TEU)": {
        "average_speed_knots": 16.0,
        "fuel_consumption_tpd": 45.0,
        "fuel_price_per_tonne": 620.0,
        "daily_operating_cost": 22000.0,
        "port_fee_per_stop": 65000.0,
        "contingency_percent": 0.11,
    },
    "Post-Panamax (5k-10k TEU)": {
        "average_speed_knots": 16.5,
        "fuel_consumption_tpd": 70.0,
        "fuel_price_per_tonne": 620.0,
        "daily_operating_cost": 35000.0,
        "port_fee_per_stop": 125000.0,
        "contingency_percent": 0.12,
    },
    "New Panamax (10k-14k TEU)": {
        "average_speed_knots": 17.0,
        "fuel_consumption_tpd": 95.0,
        "fuel_price_per_tonne": 620.0,
        "daily_operating_cost": 48000.0,
        "port_fee_per_stop": 165000.0,
        "contingency_percent": 0.13,
    },
    "ULCS (14k+ TEU)": {
        "average_speed_knots": 17.5,
        "fuel_consumption_tpd": 125.0,
        "fuel_price_per_tonne": 620.0,
        "daily_operating_cost": 65000.0,
        "port_fee_per_stop": 220000.0,
        "contingency_percent": 0.14,
    },
}

def load_ports_from_json(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    ports = []
    for entry in data:
        name = entry.get("name")
        row = entry.get("grid_row")
        col = entry.get("grid_col")

        if name is None or row is None or col is None:
            continue

        ports.append(
            {
                "name": str(name),
                "coords": (int(row), int(col)),
                "country": entry.get("country", ""),
                "city": entry.get("city", ""),
            }
        )

    if len(ports) < 2:
        raise ValueError("ports.json must contain at least 2 ports with grid_row and grid_col")

    return ports


PORTS = load_ports_from_json(PORTS_FILE)

# ────────────────────────────────────────────────
#                    GUI APPLICATION
# ────────────────────────────────────────────────

class PathfinderGUI:
    def __init__(self, root):
        self.root = root
        self.ports = PORTS
        self.primary_water_mask = None
        self.ship_profile_names = sorted(SHIP_PROFILES.keys())
        self.port_options = sorted(
            self.ports,
            key=lambda p: (p.get("country", "").lower(), p.get("name", "").lower())
        )
        self.port_labels = [f"{p.get('country', 'Unknown')} - {p['name']}" for p in self.port_options]
        self.label_to_port = {label: port for label, port in zip(self.port_labels, self.port_options)}
        self.root.title("Europe Sea Route Finder")
        self.root.geometry("1800x1050")
        self.root.minsize(1300, 860)
        self.root.configure(bg="#e8f0f8")

        self.style = ttk.Style()
        self.style.configure("Port.TCombobox", font=("Arial", 38, "bold"))
        self.style.configure("StartGoal.TCombobox", font=("Arial", 44, "bold"))
        self.style.configure("Large.TCombobox", font=("Arial", 26))
        self.root.option_add("*TCombobox*Listbox.font", ("Arial", 24))
        try:
            # Start maximized on Windows for a larger map workspace.
            self.root.state("zoomed")
        except Exception:
            pass

        # Load grid and pathfinder
        self.load_grid()

        self.selected_ship_profile = self.ship_profile_names[2] if len(self.ship_profile_names) >= 3 else self.ship_profile_names[0]
        self.cost_estimator = self.build_cost_estimator(self.selected_ship_profile)

        # ── Header ──
        tk.Label(root, text="Sea Route Pathfinder", font=("Arial", 22, "bold"), bg="#e8f0f8", fg="#2c3e50").pack(pady=15)

        # ── Port selection ──
        frame = tk.Frame(root, bg="#e8f0f8")
        frame.pack(pady=10)

        tk.Label(frame, text="Start Port:", font=("Arial", 16, "bold"), bg="#e8f0f8").grid(row=0, column=0, padx=22, pady=12, sticky="e")
        self.start_var = tk.StringVar(value=self.port_labels[0])
        self.start_menu = ttk.Combobox(frame, textvariable=self.start_var, values=self.port_labels, state="normal", width=64, style="StartGoal.TCombobox")
        self.start_menu.configure(font=("Arial", 44, "bold"))
        self.start_menu.grid(row=0, column=1, padx=22, pady=12)
        self.enable_port_autocomplete(self.start_menu, self.start_var)

        tk.Label(frame, text="Goal Port:", font=("Arial", 16, "bold"), bg="#e8f0f8").grid(row=1, column=0, padx=22, pady=12, sticky="e")
        self.goal_var = tk.StringVar(value=self.port_labels[1])
        self.goal_menu = ttk.Combobox(frame, textvariable=self.goal_var, values=self.port_labels, state="normal", width=64, style="StartGoal.TCombobox")
        self.goal_menu.configure(font=("Arial", 44, "bold"))
        self.goal_menu.grid(row=1, column=1, padx=22, pady=12)
        self.enable_port_autocomplete(self.goal_menu, self.goal_var)

        tk.Label(frame, text="Ship Profile:", font=("Arial", 16, "bold"), bg="#e8f0f8").grid(row=2, column=0, padx=22, pady=12, sticky="e")
        self.ship_profile_var = tk.StringVar(value=self.selected_ship_profile)
        self.ship_profile_menu = ttk.Combobox(
            frame,
            textvariable=self.ship_profile_var,
            values=self.ship_profile_names,
            state="normal",
            width=64,
            style="StartGoal.TCombobox",
        )
        # Match Start/Goal combobox font/size so all three look identical
        self.ship_profile_menu.configure(font=("Arial", 44, "bold"))
        self.ship_profile_menu.grid(row=2, column=1, padx=22, pady=12)
        self.enable_ship_profile_autocomplete(self.ship_profile_menu, self.ship_profile_var)

        # ── Buttons ──
        btn_frame = tk.Frame(root, bg="#e8f0f8")
        btn_frame.pack(pady=20)

        tk.Button(btn_frame, text="Find Route", font=("Arial", 13, "bold"), bg="#27ae60", fg="white", width=18, height=2,
                  command=self.find_route).pack(side=tk.LEFT, padx=20)

        tk.Button(btn_frame, text="Clear Map", font=("Arial", 13, "bold"), bg="#c0392b", fg="white", width=18, height=2,
                  command=self.clear_map).pack(side=tk.LEFT, padx=20)

        tk.Button(btn_frame, text="Exit", font=("Arial", 13, "bold"), bg="#34495e", fg="white", width=18, height=2,
                  command=self.exit_app).pack(side=tk.LEFT, padx=20)

        # ── Status label ──
        self.status_label = tk.Label(root, text="Ready – select ports and click 'Find Route'", font=("Arial", 15), bg="#e8f0f8", fg="#34495e")
        self.status_label.pack(pady=10)

        # ── Cost display box ──
        self.cost_frame = tk.LabelFrame(root, text="Estimated Shipping Cost", font=("Arial", 17, "bold"), bg="#f8f9fa", padx=18, pady=18)
        self.cost_frame.pack(fill=tk.X, padx=15, pady=5)

        self.cost_text = tk.Text(self.cost_frame, height=14, width=132, font=("Arial", 15), wrap=tk.WORD, padx=10, pady=10)
        self.cost_text.pack(fill=tk.BOTH, expand=True)
        self.cost_text.insert(tk.END, "Cost estimate will appear here after finding a route.")
        self.cost_text.config(state="disabled")

        # ── Matplotlib canvas for map ──
        self.fig, self.ax = plt.subplots(figsize=(16.5, 10.0))
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        self.toolbar = NavigationToolbar2Tk(self.canvas, root)
        self.toolbar.update()

        # Mouse-wheel zoom for fast close-up inspection of short routes.
        self.canvas.mpl_connect("scroll_event", self.on_scroll_zoom)

        # Start with blank map (no base map shown on startup)
        self.draw_blank_map()

    def load_grid(self):
        try:
            self.grid = Grid(GRID_FILE)
            self.pathfinder = AStarPathfinder(self.grid)
        except Exception as e:
            messagebox.showerror("Load Error", f"Could not load grid:\n{e}")
            self.root.quit()

    def draw_blank_map(self):
        self.ax.clear()
        self.ax.text(0.5, 0.5, "Map will appear here after finding a route", ha='center', va='center',
                     fontsize=14, color='gray', transform=self.ax.transAxes)
        self.ax.axis('off')
        self.canvas.draw()

    def clear_map(self):
        self.draw_blank_map()
        self.cost_text.config(state="normal")
        self.cost_text.delete(1.0, tk.END)
        self.cost_text.insert(tk.END, "Cost estimate will appear here after finding a route.")
        self.cost_text.config(state="disabled")
        self.status_label.config(text="Map & cost cleared – ready for new route")

    def exit_app(self):
        if messagebox.askokcancel("Exit", "Are you sure you want to close the program?"):
            self.root.quit()

    def build_cost_estimator(self, profile_name):
        profile = SHIP_PROFILES[profile_name]
        return RouteCostEstimator(
            cell_size_nm=2.5,
            average_speed_knots=profile["average_speed_knots"],
            fuel_consumption_tpd=profile["fuel_consumption_tpd"],
            fuel_price_per_tonne=profile["fuel_price_per_tonne"],
            daily_operating_cost=profile["daily_operating_cost"],
            port_fee_per_stop=profile["port_fee_per_stop"],
            contingency_percent=profile["contingency_percent"],
        )

    def enable_port_autocomplete(self, combobox, variable):
        """Enable typing + live filter behaviour for a port combobox."""
        combobox.bind(
            "<KeyRelease>",
            lambda event, cb=combobox, var=variable: self.on_port_keyrelease(event, cb, var)
        )
        combobox.bind(
            "<FocusIn>",
            lambda _event, cb=combobox: cb.configure(values=self.port_labels)
        )

    def filter_port_labels(self, query):
        q = query.strip().lower()
        if not q:
            return self.port_labels

        starts = [label for label in self.port_labels if label.lower().startswith(q)]
        contains = [
            label for label in self.port_labels
            if q in label.lower() and label not in starts
        ]
        return starts + contains

    def on_port_keyrelease(self, event, combobox, variable):
        if event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return

        matches = self.filter_port_labels(variable.get())
        combobox.configure(values=matches if matches else self.port_labels)

    def enable_ship_profile_autocomplete(self, combobox, variable):
        combobox.bind(
            "<KeyRelease>",
            lambda event, cb=combobox, var=variable: self.on_ship_keyrelease(event, cb, var)
        )
        combobox.bind(
            "<FocusIn>",
            lambda _event, cb=combobox: cb.configure(values=self.ship_profile_names)
        )

    def filter_ship_profile_labels(self, query):
        q = query.strip().lower()
        if not q:
            return self.ship_profile_names

        starts = [label for label in self.ship_profile_names if label.lower().startswith(q)]
        contains = [
            label for label in self.ship_profile_names
            if q in label.lower() and label not in starts
        ]
        return starts + contains

    def on_ship_keyrelease(self, event, combobox, variable):
        if event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return

        matches = self.filter_ship_profile_labels(variable.get())
        combobox.configure(values=matches if matches else self.ship_profile_names)

    def resolve_ship_profile_entry(self, text):
        if text in SHIP_PROFILES:
            return text

        lowered = text.strip().lower()
        if not lowered:
            return None

        for name in self.ship_profile_names:
            if name.lower() == lowered:
                return name

        starts = [name for name in self.ship_profile_names if name.lower().startswith(lowered)]
        if len(starts) == 1:
            return starts[0]

        contains = [name for name in self.ship_profile_names if lowered in name.lower()]
        if len(contains) == 1:
            return contains[0]

        return None

    def resolve_port_entry(self, text):
        """Resolve typed/selected combobox text into a single port record."""
        if text in self.label_to_port:
            return self.label_to_port[text]

        lowered = text.strip().lower()
        if not lowered:
            return None

        # Exact case-insensitive label match.
        for label in self.port_labels:
            if label.lower() == lowered:
                return self.label_to_port[label]

        # Unique startswith fallback.
        starts = [label for label in self.port_labels if label.lower().startswith(lowered)]
        if len(starts) == 1:
            return self.label_to_port[starts[0]]

        # Unique substring fallback.
        contains = [label for label in self.port_labels if lowered in label.lower()]
        if len(contains) == 1:
            return self.label_to_port[contains[0]]

        return None

    def nearest_navigable_cell(self, coords, prefer_port=True, max_radius=120):
        """Snap a coordinate to the nearest usable cell on the map."""
        row0, col0 = coords

        if self.pathfinder.is_walkable(row0, col0, is_goal=True):
            return coords

        best_port = None
        best_water = None
        best_port_dist = float("inf")
        best_water_dist = float("inf")

        r_start = max(0, row0 - max_radius)
        r_end = min(self.grid.height - 1, row0 + max_radius)
        c_start = max(0, col0 - max_radius)
        c_end = min(self.grid.width - 1, col0 + max_radius)

        for row in range(r_start, r_end + 1):
            for col in range(c_start, c_end + 1):
                value = self.grid.data[row, col]
                if value not in (0, 3, 4):
                    continue

                dist = (row - row0) ** 2 + (col - col0) ** 2
                if value in (3, 4):
                    if dist < best_port_dist:
                        best_port_dist = dist
                        best_port = (row, col)
                elif dist < best_water_dist:
                    best_water_dist = dist
                    best_water = (row, col)

        if prefer_port and best_port is not None:
            return best_port
        if best_water is not None:
            return best_water
        if best_port is not None:
            return best_port

        return coords

    def nearest_water_cell(self, coords, max_radius=400):
        """Find nearest open-water cell (value 0) around a coordinate."""
        row0, col0 = coords

        if self.grid.is_valid(row0, col0) and self.grid.data[row0, col0] == 0:
            return coords

        best = None
        best_dist = float("inf")

        r_start = max(0, row0 - max_radius)
        r_end = min(self.grid.height - 1, row0 + max_radius)
        c_start = max(0, col0 - max_radius)
        c_end = min(self.grid.width - 1, col0 + max_radius)

        for row in range(r_start, r_end + 1):
            for col in range(c_start, c_end + 1):
                if self.grid.data[row, col] != 0:
                    continue

                dist = (row - row0) ** 2 + (col - col0) ** 2
                if dist < best_dist:
                    best_dist = dist
                    best = (row, col)

        return best if best is not None else coords

    def build_primary_water_component(self):
        """Build the main connected water component from a reliable seed port."""
        if self.primary_water_mask is not None:
            return

        seed_name = "Southampton"
        if not any(p["name"] == seed_name for p in self.ports):
            seed_name = self.ports[0]["name"]

        seed_raw = next(p["coords"] for p in self.ports if p["name"] == seed_name)
        seed = self.nearest_water_cell(seed_raw)

        mask = np.zeros((self.grid.height, self.grid.width), dtype=bool)
        if not self.grid.is_valid(seed[0], seed[1]) or self.grid.data[seed[0], seed[1]] != 0:
            self.primary_water_mask = mask
            return

        queue = deque([seed])
        mask[seed[0], seed[1]] = True

        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        while queue:
            row, col = queue.popleft()
            for dr, dc in directions:
                nr, nc = row + dr, col + dc
                if not self.grid.is_valid(nr, nc):
                    continue
                if mask[nr, nc]:
                    continue
                if self.grid.data[nr, nc] != 0:
                    continue
                mask[nr, nc] = True
                queue.append((nr, nc))

        self.primary_water_mask = mask

    def nearest_component_water_cell(self, coords, max_radius=500, avoid_cell=None):
        """Snap to nearest water cell that is in the main connected sea component."""
        self.build_primary_water_component()

        row0, col0 = coords
        if (
            self.grid.is_valid(row0, col0)
            and self.primary_water_mask[row0, col0]
            and (avoid_cell is None or (row0, col0) != avoid_cell)
        ):
            return coords

        best = None
        best_dist = float("inf")

        r_start = max(0, row0 - max_radius)
        r_end = min(self.grid.height - 1, row0 + max_radius)
        c_start = max(0, col0 - max_radius)
        c_end = min(self.grid.width - 1, col0 + max_radius)

        for row in range(r_start, r_end + 1):
            for col in range(c_start, c_end + 1):
                if not self.primary_water_mask[row, col]:
                    continue
                if avoid_cell is not None and (row, col) == avoid_cell:
                    continue

                dist = (row - row0) ** 2 + (col - col0) ** 2
                if dist < best_dist:
                    best_dist = dist
                    best = (row, col)

        if best is not None:
            return best

        fallback = self.nearest_water_cell(coords)
        if avoid_cell is not None and fallback == avoid_cell:
            return coords
        return fallback

    def find_route(self):
        start_label = self.start_var.get()
        goal_label = self.goal_var.get()

        if start_label == goal_label:
            messagebox.showwarning("Warning", "Start and goal ports cannot be the same.")
            return

        start_port = self.resolve_port_entry(start_label)
        goal_port = self.resolve_port_entry(goal_label)

        if start_port is None or goal_port is None:
            messagebox.showerror(
                "Selection Error",
                "Please select a valid start and goal port from the suggestions."
            )
            return

        ship_profile_name = self.resolve_ship_profile_entry(self.ship_profile_var.get())
        if ship_profile_name is None:
            messagebox.showerror(
                "Selection Error",
                "Please select a valid ship profile from the suggestions."
            )
            return

        self.selected_ship_profile = ship_profile_name
        self.cost_estimator = self.build_cost_estimator(ship_profile_name)

        start_name = start_port["name"]
        goal_name = goal_port["name"]

        raw_start = start_port["coords"]
        raw_goal = goal_port["coords"]

        # If the provided grid coordinate already contains a port cell, use it.
        # Otherwise snap to the nearest water cell in the main component to avoid picking
        # an unrelated nearby port (e.g., Piraeus) when the intended port isn't encoded as a port cell.
        if self.grid.is_port(raw_start[0], raw_start[1]):
            start = raw_start
        else:
            start = self.nearest_component_water_cell(raw_start)

        if self.grid.is_port(raw_goal[0], raw_goal[1]):
            goal = raw_goal
        else:
            goal = self.nearest_component_water_cell(raw_goal, avoid_cell=start)

        # If both snapped to the same cell, try widening the search for the goal
        if start == goal:
            goal = self.nearest_component_water_cell(raw_goal, max_radius=900, avoid_cell=start)

        # Debugging output: show raw vs snapped coords and grid cell values
        try:
            print(f"DEBUG: {start_name} raw={raw_start} val={self.grid.data[raw_start[0], raw_start[1]]} -> snapped={start} val={self.grid.data[start[0], start[1]]}")
            print(f"DEBUG: {goal_name} raw={raw_goal} val={self.grid.data[raw_goal[0], raw_goal[1]]} -> snapped={goal} val={self.grid.data[goal[0], goal[1]]}")
        except Exception:
            pass

        if start == goal:
            self.status_label.config(text="Ports map to the same sea cell")
            messagebox.showinfo(
                "No Distinct Route",
                "The selected ports currently map to the same navigable cell on this grid. "
                "Choose a different pair of ports."
            )
            return

        self.status_label.config(text=f"Computing route: {start_name} → {goal_name} ...")
        self.root.update_idletasks()

        try:
            path = self.pathfinder.find_path(start, goal)

            if path:
                length = len(path) - 1
                self.status_label.config(text=f"Route found! {length} steps")

                # Calculate cost
                cost_data = self.cost_estimator.estimate(length)

                if "error" in cost_data:
                    cost_text = (
                        f"Route: {start_name} → {goal_name}\n"
                        f"Path length: {length} steps\n\n"
                        f"Cost estimate unavailable: {cost_data['error']}"
                    )
                else:
                    distance_nm = cost_data.get("distance_nm", 0)
                    time_days = cost_data.get("time_days", 0)
                    fuel_cost = cost_data.get("fuel_cost_usd", 0)
                    operating_cost = cost_data.get("operating_cost_usd", 0)
                    port_fees = cost_data.get("port_fees_usd", 0)
                    contingency = cost_data.get("contingency_usd", 0)
                    total = cost_data.get("formatted_total", f"${cost_data.get('total_cost_usd', 0):,}")
                    divider = "-" * 40

                    # Show cost in text box
                    cost_text = (
                        f"Route: {start_name} → {goal_name}\n"
                        f"Ship profile: {self.selected_ship_profile}\n"
                        f"Distance: {distance_nm:,} nautical miles\n"
                        f"Time at sea: ~{time_days} days\n"
                        f"{divider}\n"
                        f"Fuel cost:          ${fuel_cost:,}\n"
                        f"Operating cost:     ${operating_cost:,}\n"
                        f"Port fees (start+goal): ${port_fees:,}\n"
                        f"Contingency:        ${contingency:,}\n"
                        f"{divider}\n"
                        f"TOTAL ESTIMATED COST: {total}"
                    )

                self.cost_text.config(state="normal")
                self.cost_text.delete(1.0, tk.END)
                self.cost_text.insert(tk.END, cost_text)
                self.cost_text.config(state="disabled")

                self.draw_route(path, start, goal, start_name, goal_name)
            else:
                self.status_label.config(text="No route found")
                messagebox.showinfo("Result", "No valid sea route between these ports.")
                self.cost_text.config(state="normal")
                self.cost_text.delete(1.0, tk.END)
                self.cost_text.insert(tk.END, "No route found – no cost estimate available.")
                self.cost_text.config(state="disabled")

        except Exception as e:
            self.status_label.config(text="Error during pathfinding")
            messagebox.showerror("Error", f"Pathfinding failed:\n{e}")
            self.cost_text.config(state="normal")
            self.cost_text.delete(1.0, tk.END)
            self.cost_text.insert(tk.END, f"Error occurred:\n{e}")
            self.cost_text.config(state="disabled")

    def draw_route(self, path, start, goal, start_name, goal_name):
        self.ax.clear()

        # Build a true-color background so only matching cells are colored.
        rgb = np.zeros((self.grid.height, self.grid.width, 3), dtype=np.uint8)

        water_mask = self.grid.data == 0
        land_mask = (self.grid.data == 1) | (self.grid.data == 2)
        port_mask = (self.grid.data == 3) | (self.grid.data == 4)

        rgb[water_mask] = [47, 128, 237]   # blue water
        rgb[land_mask] = [46, 125, 50]     # green land
        rgb[port_mask] = [211, 47, 47]     # red ports

        self.ax.imshow(rgb, origin='upper')

        # Route line + markers
        rows, cols = zip(*path)
        self.ax.plot(cols, rows, 'r-', linewidth=3, alpha=0.9, label='Sea Route')
        self.ax.plot(cols[0], rows[0], 'go', markersize=14, label=f'Start: {start_name}')
        self.ax.plot(cols[-1], rows[-1], 'yo', markersize=14, label=f'Goal: {goal_name}')

        self.ax.set_title(f"Route: {start_name} → {goal_name}  ({len(path)-1} steps)", fontsize=14)
        self.ax.legend(loc='upper right', fontsize=10)
        self.ax.axis('off')
        self.canvas.draw()

    def on_scroll_zoom(self, event):
        if event.inaxes != self.ax:
            return

        xdata, ydata = event.xdata, event.ydata
        if xdata is None or ydata is None:
            return

        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()
        xspan = (cur_xlim[1] - cur_xlim[0])
        yspan = (cur_ylim[1] - cur_ylim[0])

        scale = 1.15 if event.button == 'down' else (1 / 1.15)

        new_width = xspan * scale
        new_height = yspan * scale

        relx = (xdata - cur_xlim[0]) / xspan if xspan else 0.5
        rely = (ydata - cur_ylim[0]) / yspan if yspan else 0.5

        self.ax.set_xlim([xdata - new_width * relx, xdata + new_width * (1 - relx)])
        self.ax.set_ylim([ydata - new_height * rely, ydata + new_height * (1 - rely)])
        self.canvas.draw_idle()


# ────────────────────────────────────────────────
#                     RUN THE GUI
# ────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app = PathfinderGUI(root)
    root.mainloop()
