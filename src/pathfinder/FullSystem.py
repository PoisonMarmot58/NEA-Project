"""FullSystem module."""

import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm, colors
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from collections import deque
import json
import sys
from pathlib import Path
import os
from tkinter import filedialog
import threading
import time
import math

# Ensure `src` directory is on sys.path so `import pathfinder` works
# when running this file directly (as a script).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pathfinder.algorithms.Astar import Grid, AStarPathfinder
from pathfinder.algorithms.CostCalculator import RouteCostEstimator
from pathfinder.algorithms.WeatherEstimator import WeatherImpactEstimator

# config
# The GRID file is resolved at runtime so the project can run on other machines.
# The loader will check an environment variable, common repo locations, and
# finally prompt the user to pick the file if necessary.
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

#gui application

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
        self.port_labels = [
            f"{p.get('country', 'Unknown')} - {p['name']}" for p in self.port_options
        ]
        self.label_to_port = {label: port for label, port in zip(self.port_labels, self.port_options)}

        def _label_for_port(port_name, fallback_label):
            for label, port in self.label_to_port.items():
                if port.get('name') == port_name:
                    return label
            return fallback_label

        default_start_label = _label_for_port("Felixstowe", self.port_labels[0])
        default_goal_label = _label_for_port("Bremerhaven", self.port_labels[1])
        self.root.title("Europe Sea Route Finder")
        self.root.geometry("1800x1050")
        self.root.minsize(1300, 860)
        self.root.configure(bg="#e8f0f8")

        self.style = ttk.Style()
        self.style.configure("Port.TCombobox", font=("Arial", 18, "bold"))
        self.style.configure("StartGoal.TCombobox", font=("Arial", 18, "bold"))
        self.style.configure("Large.TCombobox", font=("Arial", 14))
        self.root.option_add("*TCombobox*Listbox.font", ("Arial", 14))
        try:
            # Start maximized on Windows for a larger map workspace.
            self.root.state("zoomed")
        except Exception:
            pass

        # Load grid and pathfinder
        self.load_grid()

        self.selected_ship_profile = (
            self.ship_profile_names[2]
            if len(self.ship_profile_names) >= 3
            else self.ship_profile_names[0]
        )
        self.cost_estimator = self.build_cost_estimator(self.selected_ship_profile)
        # Reuse one estimator so HTTP/session and weather cache are shared between routes.
        self.weather_estimator = WeatherImpactEstimator()

        # ── Header ──
        tk.Label(
            root,
            text="Sea Route Pathfinder",
            font=("Arial", 17, "bold"),
            bg="#e8f0f8",
            fg="#2c3e50",
        ).pack(pady=6)

        # ── Port selection ──
        frame = tk.Frame(root, bg="#e8f0f8")
        frame.pack(pady=4)

        tk.Label(
            frame,
            text="Start Port:",
            font=("Arial", 12, "bold"),
            bg="#e8f0f8",
        ).grid(row=0, column=0, padx=10, pady=4, sticky="e")
        self.start_var = tk.StringVar(value=default_start_label)
        self.start_menu = ttk.Combobox(
            frame,
            textvariable=self.start_var,
            values=self.port_labels,
            state="normal",
            width=58,
            style="StartGoal.TCombobox",
        )
        self.start_menu.configure(font=("Arial", 18, "bold"))
        self.start_menu.grid(row=0, column=1, padx=10, pady=4)
        self.enable_port_autocomplete(self.start_menu, self.start_var)

        tk.Label(
            frame,
            text="Goal Port:",
            font=("Arial", 12, "bold"),
            bg="#e8f0f8",
        ).grid(row=1, column=0, padx=10, pady=4, sticky="e")
        self.goal_var = tk.StringVar(value=default_goal_label)
        self.goal_menu = ttk.Combobox(
            frame,
            textvariable=self.goal_var,
            values=self.port_labels,
            state="normal",
            width=58,
            style="StartGoal.TCombobox",
        )
        self.goal_menu.configure(font=("Arial", 18, "bold"))
        self.goal_menu.grid(row=1, column=1, padx=10, pady=4)
        self.enable_port_autocomplete(self.goal_menu, self.goal_var)

        tk.Label(
            frame,
            text="Ship Profile:",
            font=("Arial", 12, "bold"),
            bg="#e8f0f8",
        ).grid(row=2, column=0, padx=10, pady=4, sticky="e")
        self.ship_profile_var = tk.StringVar(value=self.selected_ship_profile)
        self.ship_profile_menu = ttk.Combobox(
            frame,
            textvariable=self.ship_profile_var,
            values=self.ship_profile_names,
            state="normal",
            width=58,
            style="StartGoal.TCombobox",
        )
        # Match Start/Goal combobox font/size so all three look identical
        self.ship_profile_menu.configure(font=("Arial", 18, "bold"))
        self.ship_profile_menu.grid(row=2, column=1, padx=10, pady=4)
        self.enable_ship_profile_autocomplete(self.ship_profile_menu, self.ship_profile_var)

        # ── Buttons ──
        btn_frame = tk.Frame(root, bg="#e8f0f8")
        btn_frame.pack(pady=8)

        tk.Button(
            btn_frame,
            text="Find Route",
            font=("Arial", 11, "bold"),
            bg="#27ae60",
            fg="white",
            width=14,
            height=1,
            command=self.find_route,
        ).pack(side=tk.LEFT, padx=10)

        tk.Button(btn_frame, text="Clear Map", font=("Arial", 11, "bold"), bg="#c0392b", fg="white", width=14, height=1,
                  command=self.clear_map).pack(side=tk.LEFT, padx=10)

        tk.Button(btn_frame, text="Exit", font=("Arial", 11, "bold"), bg="#34495e", fg="white", width=14, height=1,
                  command=self.exit_app).pack(side=tk.LEFT, padx=10)

        # Weather markers toggle
        self.show_weather_var = tk.BooleanVar(value=True)
        tk.Checkbutton(btn_frame, text="Show weather markers", variable=self.show_weather_var, bg="#e8f0f8",
                   font=("Arial", 11), command=lambda: self.canvas.draw_idle()).pack(side=tk.LEFT, padx=12)

        # ── Status label ──
        self.status_label = tk.Label(
            root,
            text="Ready – select ports and click 'Find Route'",
            font=("Arial", 12),
            bg="#e8f0f8",
            fg="#34495e",
        )
        self.status_label.pack(pady=4)
        # ── Info panels: cost (left) and weather (right) ──
        info_frame = tk.Frame(root, bg="#e8f0f8")
        info_frame.pack(fill=tk.X, padx=12, pady=3)
        # Use grid inside info_frame so cost and weather frames can share width equally
        info_frame.columnconfigure(0, weight=1, uniform="info")
        info_frame.columnconfigure(1, weight=1, uniform="info")

        self.cost_frame = tk.LabelFrame(
            info_frame,
            text="Estimated Shipping Cost",
            font=("Arial", 13, "bold"),
            bg="#f8f9fa",
            padx=10,
            pady=8,
        )
        self.cost_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 8), pady=0)

        self.cost_text = tk.Text(
            self.cost_frame,
            height=12,
            width=60,
            font=("Arial", 12),
            wrap=tk.WORD,
            padx=8,
            pady=6,
        )
        self.cost_text.pack(fill=tk.BOTH, expand=True)
        self.cost_text.insert(tk.END, "Cost estimate will appear here after finding a route.")
        self.cost_text.config(state="disabled")

        self.weather_frame = tk.LabelFrame(
            info_frame,
            text="Weather Samples",
            font=("Arial", 13, "bold"),
            bg="#f8f9fa",
            padx=10,
            pady=8,
        )
        # Place weather panel in the info_frame grid to match cost frame size
        self.weather_frame.grid(row=0, column=1, sticky='nsew', padx=(8, 0), pady=0)

        # Larger, clearer weather text area for readability
        self.weather_text = tk.Text(
            self.weather_frame,
            height=12,
            width=60,
            font=("Arial", 12),
            wrap=tk.WORD,
            padx=8,
            pady=6,
        )
        self.weather_text.pack(fill=tk.BOTH, expand=True)
        self.weather_text.insert(tk.END, "Weather samples will appear here after finding a route.")
        self.weather_text.config(state="disabled")

        # ── Matplotlib canvas for map ──
        self.fig, self.ax = plt.subplots(figsize=(18.5, 12.0))
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        self.toolbar = NavigationToolbar2Tk(self.canvas, root)
        self.toolbar.update()

        # Mouse-wheel zoom for fast close-up inspection of short routes.
        self.canvas.mpl_connect("scroll_event", self.on_scroll_zoom)
        # Left-click drag panning for intuitive map navigation.
        self.canvas.mpl_connect("button_press_event", self.on_pan_press)
        self.canvas.mpl_connect("motion_notify_event", self.on_pan_drag)
        self.canvas.mpl_connect("button_release_event", self.on_pan_release)

        self._pan_active = False
        self._pan_last = None
        self._pan_last_data = None
        self._pan_last_ts = None
        self._pan_velocity_data = (0.0, 0.0)
        self._pan_inertia_active = False
        self._pan_inertia_after_id = None
        self._pan_inertia_last_tick = None
        self._view_target = None
        self._view_animating = False
        self._view_anim_after_id = None
        self._view_last_tick = time.perf_counter()
        self._last_view_input = self._view_last_tick
        self._view_fps = 144
        self._view_tau_zoom = 0.055
        self._view_tau_pan = 0.028
        self._view_interaction_mode = "idle"
        self._last_interaction_draw = 0.0
        self._interaction_draw_interval = 1.0 / 144.0

        # Start with blank map (no base map shown on startup)
        self.draw_blank_map()

    def load_grid(self):
        # Determine grid file path
        env_path = os.environ.get("GRID_FILE") or os.environ.get("PATHFINDER_GRID_FILE")
        candidates = []
        if env_path:
            candidates.append(Path(env_path))

        # Project root (two parents up from this file)
        project_root = Path(__file__).resolve().parents[2]
        # Common places in this repository where the full grid may be stored
        candidates.extend([
            project_root / "backups" / "data" / "legacy_root" / "FullGridOfEurope.npy",
            project_root / "backups" / "data" / "FullGridOfEurope.npy",
            Path(__file__).resolve().parent / "data" / "FullGridOfEurope.npy",
        ])

        grid_file = None
        for p in candidates:
            if p and p.exists():
                grid_file = p
                break

        if grid_file is None:
            # Ask the user to locate the .npy grid file
            messagebox.showinfo(
                "Locate Grid File",
                "Full grid file not found automatically. Please locate the FullGridOfEurope.npy file."
            )
            chosen = filedialog.askopenfilename(
                title="Select FullGridOfEurope.npy",
                filetypes=[("NumPy files", "*.npy"), ("All files", "*")],
            )
            if chosen:
                grid_file = Path(chosen)

        if grid_file is None:
            messagebox.showerror("Load Error", "Could not locate a grid file. Exiting.")
            self.root.quit()
            return

        try:
            self.grid = Grid(str(grid_file))
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
            print(
                f"DEBUG: {start_name} raw={raw_start} "
                f"val={self.grid.data[raw_start[0], raw_start[1]]} -> "
                f"snapped={start} val={self.grid.data[start[0], start[1]]}"
            )
            print(
                f"DEBUG: {goal_name} raw={raw_goal} "
                f"val={self.grid.data[raw_goal[0], raw_goal[1]]} -> "
                f"snapped={goal} val={self.grid.data[goal[0], goal[1]]}"
            )
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
                search_mode = getattr(self.pathfinder, 'last_search_mode', None)
                if search_mode == 'fallback':
                    self.status_label.config(text=f"Route found (robust fallback)! {length} steps")
                else:
                    self.status_label.config(text=f"Route found! {length} steps")

                # Calculate cost
                cost_data = self.cost_estimator.estimate(length)

                # Start a background weather fetch so the UI doesn't block.
                # We display base cost now, then update the UI when weather completes.
                try:
                    if search_mode == 'fallback':
                        self.status_label.config(text="Querying weather... (route used robust fallback)")
                    else:
                        self.status_label.config(text="Querying weather...")
                    t = threading.Thread(
                        target=self._fetch_weather_and_apply,
                        args=(path, start, goal, start_name, goal_name, cost_data),
                        daemon=True,
                    )
                    t.start()
                    # set safe defaults until background thread updates the UI
                    multiplier = 1.0
                    weather_summary = "Weather: fetching..."
                    weather_samples = None
                except Exception:
                    # If threading fails, fall back to a synchronous call.
                    try:
                        res = self.weather_estimator.estimate_path_impact(
                            path,
                            ship_profile=self.cost_estimator,
                            detailed=getattr(self, 'show_weather_var', None) and self.show_weather_var.get(),
                        )
                        if isinstance(res, tuple) and len(res) == 3:
                            multiplier, weather_summary, weather_samples = res
                        else:
                            multiplier, weather_summary = res
                            weather_samples = None
                    except Exception:
                        multiplier, weather_summary = 1.0, "Weather check failed"
                        weather_samples = None

                if multiplier != 1.0:
                    # Adjust time-based components while keeping distance unchanged
                    base_time_days = cost_data.get("time_days", 0)
                    adjusted_time_days = round(base_time_days * multiplier, 1)

                    # Recompute fuel and operating costs using adjusted time
                    fuel_cost = adjusted_time_days * self.cost_estimator.fuel_consumption_tpd * self.cost_estimator.fuel_price_per_tonne
                    operating_cost = adjusted_time_days * self.cost_estimator.daily_operating_cost
                    port_fees = cost_data.get("port_fees_usd", 0)
                    subtotal = fuel_cost + operating_cost + port_fees
                    contingency = subtotal * self.cost_estimator.contingency_percent
                    total = subtotal + contingency

                    # Update displayed cost data
                    cost_data.update({
                        "time_days": adjusted_time_days,
                        "fuel_cost_usd": round(fuel_cost),
                        "operating_cost_usd": round(operating_cost),
                        "port_fees_usd": round(port_fees),
                        "contingency_usd": round(contingency),
                        "total_cost_usd": round(total),
                        "formatted_total": f"${round(total):,}",
                        "weather_summary": weather_summary,
                        "weather_multiplier": round(multiplier, 3),
                    })
                else:
                    cost_data["weather_summary"] = weather_summary

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
                # Weather details are shown in the separate weather panel, not the cost box.

                self.cost_text.config(state="normal")
                self.cost_text.delete(1.0, tk.END)
                self.cost_text.insert(tk.END, cost_text)
                self.cost_text.config(state="disabled")

                # Populate weather details panel with plain-English summary and samples
                try:
                    self.weather_text.config(state="normal")
                    self.weather_text.delete(1.0, tk.END)
                    parts = []
                    ws = cost_data.get('weather_summary')
                    wm = cost_data.get('weather_multiplier')
                    if ws:
                        parts.append(f"Weather summary: {ws}")
                    if wm:
                        parts.append(f"Estimated travel time: {wm}x normal")
                    if ws or wm:
                        parts.append('')

                    if weather_samples:
                        parts.append('Detailed samples along the route:')
                        def deg_to_compass(deg):
                            if deg is None:
                                return 'N/A'
                            dirs = [
                                'N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                                'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'
                            ]
                            ix = int((deg + 11.25) / 22.5) % 16
                            return dirs[ix]

                        for s in weather_samples:
                            idx = s.get('path_index')
                            eta = s.get('eta_hours')
                            latlon = s.get('latlon') or s.get('grid_cell')
                            if isinstance(latlon, tuple) and len(latlon) == 2 and isinstance(latlon[0], float):
                                latlon_str = f"{latlon[0]:.3f}, {latlon[1]:.3f}"
                            else:
                                latlon_str = f"{latlon[0]},{latlon[1]}" if latlon else 'N/A'
                            wk = s.get('wind_knots')
                            wd = s.get('wind_dir')
                            wv = s.get('wave_m')
                            pen = s.get('penalty_fraction') or 0.0
                            if wk is not None:
                                compass = deg_to_compass(wd)
                                wind_part = f"{wk:.1f} kt from {compass} ({int(wd)}°)" if wd is not None else f"{wk:.1f} kt"
                            else:
                                wind_part = 'Wind: N/A'
                            wave_part = f"{wv:.2f} m" if wv is not None else 'N/A'
                            pen_pct = int(round(pen * 100))
                            pen_part = f"+{pen_pct}% longer"
                            parts.append(f"• Sample {idx}: in ~{eta} h — at {latlon_str} — Wind: {wind_part}; Waves: {wave_part}; Time change: {pen_part}")
                    else:
                        if ws:
                            parts.append(ws)
                        else:
                            parts.append('No weather samples available for this route.')

                    self.weather_text.insert(tk.END, "\n".join(parts))
                except Exception:
                    try:
                        self.weather_text.insert(tk.END, 'Weather display failed')
                    except Exception:
                        pass
                finally:
                    try:
                        self.weather_text.config(state='disabled')
                    except Exception:
                        pass

                self.draw_route(path, start, goal, start_name, goal_name, weather_samples=weather_samples)
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

    def draw_route(self, path, start, goal, start_name, goal_name, weather_samples=None):
        self.ax.clear()
        # Cache the background RGB map (water/land/ports) so we do not recompute
        # it on every redraw. Recompute when grid shape or checksum changes.
        try:
            grid_sum = int(self.grid.data.sum())
        except Exception:
            grid_sum = None

        need_build = True
        if hasattr(self, '_bg_rgb') and hasattr(self, '_bg_grid_sum') and hasattr(self, '_bg_shape'):
            if self._bg_shape == (self.grid.height, self.grid.width) and self._bg_grid_sum == grid_sum:
                need_build = False

        if need_build:
            rgb = np.zeros((self.grid.height, self.grid.width, 3), dtype=np.uint8)
            water_mask = self.grid.data == 0
            land_mask = (self.grid.data == 1) | (self.grid.data == 2)
            port_mask = (self.grid.data == 3) | (self.grid.data == 4)

            # Try to remove small artifacts if scipy available
            try:
                from scipy.ndimage import label
                combined = (land_mask | port_mask).astype(int)
                labeled, ncomp = label(combined)
                if ncomp:
                    SMALL_COMP = 30
                    for comp in range(1, ncomp + 1):
                        comp_mask = (labeled == comp)
                        if comp_mask.sum() <= SMALL_COMP:
                            combined[comp_mask] = 0
                    land_mask = land_mask & combined.astype(bool)
                    port_mask = port_mask & combined.astype(bool)
            except Exception:
                pass

            # hide area outside outer land rectangle if available
            try:
                rows = np.where(land_mask.any(axis=1))[0]
                cols = np.where(land_mask.any(axis=0))[0]
                if rows.size and cols.size:
                    rmin, rmax = int(rows.min()), int(rows.max())
                    cmin, cmax = int(cols.min()), int(cols.max())
                    PADDING = 1
                    rmin = max(0, rmin + PADDING)
                    rmax = min(self.grid.height - 1, rmax - PADDING)
                    cmin = max(0, cmin + PADDING)
                    cmax = min(self.grid.width - 1, cmax - PADDING)
                    outside_rows = np.ones(self.grid.height, dtype=bool)
                    outside_rows[rmin:rmax + 1] = False
                    outside_cols = np.ones(self.grid.width, dtype=bool)
                    outside_cols[cmin:cmax + 1] = False
                    outside_mask = np.outer(outside_rows, np.ones(self.grid.width, dtype=bool)) | np.outer(np.ones(self.grid.height, dtype=bool), outside_cols)
                    water_mask = water_mask | outside_mask
                    land_mask = land_mask & (~outside_mask)
                    port_mask = port_mask & (~outside_mask)
            except Exception:
                pass

            rgb[water_mask] = [47, 128, 237]   # blue water
            rgb[land_mask] = [46, 125, 50]     # green land
            rgb[port_mask] = [211, 47, 47]     # red ports

            self._bg_rgb = rgb
            self._bg_grid_sum = grid_sum
            self._bg_shape = (self.grid.height, self.grid.width)
        else:
            rgb = self._bg_rgb.copy()

        self.ax.imshow(rgb, origin='upper')

        # Route line + markers
        rows, cols = zip(*path)
        self.ax.plot(cols, rows, 'r-', linewidth=3, alpha=0.9, label='Sea Route')
        self.ax.plot(cols[0], rows[0], 'o', color='red', markersize=14, label=f'Start: {start_name}')
        self.ax.plot(cols[-1], rows[-1], 'o', color='purple', markersize=14, label=f'Goal: {goal_name}')
        # Draw weather impact samples if provided
        if weather_samples and getattr(self, 'show_weather_var', None) and self.show_weather_var.get():
            cols_s = []
            rows_s = []
            pens = []
            for s in weather_samples:
                gc = s.get('grid_cell')
                if gc and isinstance(gc, (list, tuple)) and len(gc) == 2:
                    r, c = gc
                else:
                    pi = s.get('path_index')
                    if pi is not None and pi < len(path):
                        r, c = path[pi]
                    else:
                        continue
                cols_s.append(c)
                rows_s.append(r)
                pens.append(s.get('penalty_fraction', 0.0))

            if pens:
                vmax = max(pens) if pens else 0.01
                norm = colors.Normalize(vmin=0.0, vmax=max(vmax, 0.001))
                sc = self.ax.scatter(cols_s, rows_s, c=pens, cmap='Reds', norm=norm, s=[60 + p * 1200 for p in pens], edgecolor='black', alpha=0.9, zorder=5)
                # annotate each sample with percent increase
                for x, y, p in zip(cols_s, rows_s, pens):
                    pct = int(round(p * 100))
                    if pct > 0:
                        self.ax.text(x, y - 6, f'+{pct}%', color='white', fontsize=9, ha='center', va='bottom', weight='bold', zorder=6)

        self.ax.set_title(f"Route: {start_name} → {goal_name}  ({len(path)-1} steps)", fontsize=14)
        self.ax.legend(loc='upper right', fontsize=10)
        self.ax.axis('off')
        self.canvas.draw()

    def _fetch_weather_and_apply(self, path, start, goal, start_name, goal_name, cost_data):
        """Background worker: fetch weather and schedule UI update."""
        try:
            detailed = getattr(self, 'show_weather_var', None) and self.show_weather_var.get()
            res = self.weather_estimator.estimate_path_impact(
                path,
                ship_profile=self.cost_estimator,
                detailed=detailed,
            )
        except Exception as e:
            res = (1.0, f"Weather check failed: {e}")

        # schedule application on the main thread
        try:
            self.root.after(0, lambda: self._apply_weather_result(res, path, start, goal, start_name, goal_name, cost_data))
        except Exception:
            # best-effort: try direct call
            try:
                self._apply_weather_result(res, path, start, goal, start_name, goal_name, cost_data)
            except Exception:
                pass

    def _apply_weather_result(self, res, path, start, goal, start_name, goal_name, cost_data):
        """Apply weather result (runs on main thread)."""
        try:
            if isinstance(res, tuple) and len(res) == 3:
                multiplier, weather_summary, weather_samples = res
            else:
                multiplier, weather_summary = res
                weather_samples = None

            # update cost_data if needed
            if multiplier != 1.0:
                base_time_days = cost_data.get('time_days', 0)
                adjusted_time_days = round(base_time_days * multiplier, 1)
                fuel_cost = adjusted_time_days * self.cost_estimator.fuel_consumption_tpd * self.cost_estimator.fuel_price_per_tonne
                operating_cost = adjusted_time_days * self.cost_estimator.daily_operating_cost
                port_fees = cost_data.get('port_fees_usd', 0)
                subtotal = fuel_cost + operating_cost + port_fees
                contingency = subtotal * self.cost_estimator.contingency_percent
                total = subtotal + contingency
                cost_data.update({
                    'time_days': adjusted_time_days,
                    'fuel_cost_usd': round(fuel_cost),
                    'operating_cost_usd': round(operating_cost),
                    'port_fees_usd': round(port_fees),
                    'contingency_usd': round(contingency),
                    'total_cost_usd': round(total),
                    'formatted_total': f"${round(total):,}",
                    'weather_summary': weather_summary,
                    'weather_multiplier': round(multiplier, 3),
                })
            else:
                cost_data['weather_summary'] = weather_summary

            # refresh cost_text
            try:
                if 'error' in cost_data:
                    cost_text = (
                        f"Route: {start_name} → {goal_name}\n"
                        f"Path length: {len(path) - 1} steps\n\n"
                        f"Cost estimate unavailable: {cost_data['error']}"
                    )
                else:
                    distance_nm = cost_data.get('distance_nm', 0)
                    time_days = cost_data.get('time_days', 0)
                    fuel_cost = cost_data.get('fuel_cost_usd', 0)
                    operating_cost = cost_data.get('operating_cost_usd', 0)
                    port_fees = cost_data.get('port_fees_usd', 0)
                    contingency = cost_data.get('contingency_usd', 0)
                    total = cost_data.get('formatted_total', f"${cost_data.get('total_cost_usd', 0):,}")
                    divider = '-' * 40
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
                # Weather details shown in the weather panel (not in cost text).

                self.cost_text.config(state='normal')
                self.cost_text.delete(1.0, tk.END)
                self.cost_text.insert(tk.END, cost_text)
                self.cost_text.config(state='disabled')
            except Exception:
                pass

            # update weather details panel (readable summary + samples)
            try:
                self.weather_text.config(state='normal')
                self.weather_text.delete(1.0, tk.END)
                lines = []
                ws = cost_data.get('weather_summary')
                wm = cost_data.get('weather_multiplier')
                if ws:
                    lines.append(f"Summary: {ws}")
                if wm:
                    lines.append(f"Time multiplier: {wm}x")
                if ws or wm:
                    lines.append('-' * 40)

                if weather_samples:
                    lines.append(f"{'Sample':<8} {'ETA(h)':<7} {'Lat,Lon':<20} {'Wind':<18} {'Wave':<8} {'Penalty':<8}")
                    for s in weather_samples:
                        idx = s.get('path_index')
                        eta = s.get('eta_hours')
                        latlon = s.get('latlon') or s.get('grid_cell')
                        if isinstance(latlon, tuple) and len(latlon) == 2 and isinstance(latlon[0], float):
                            latlon_str = f"{latlon[0]:.3f},{latlon[1]:.3f}"
                        else:
                            latlon_str = f"{latlon[0]},{latlon[1]}" if latlon else 'N/A'
                        wk = s.get('wind_knots')
                        wd = s.get('wind_dir')
                        wv = s.get('wave_m')
                        pen = s.get('penalty_fraction') or 0.0
                        wind_str = f"{wk:.1f} kt @{int(wd) if wd is not None else 'N/A'}°" if wk is not None else 'N/A'
                        wave_str = f"{wv:.2f} m" if wv is not None else 'N/A'
                        pen_str = f"+{int(round(pen*100))}%"
                        lines.append(f"{str(idx):<8} {str(eta):<7} {latlon_str:<20} {wind_str:<18} {wave_str:<8} {pen_str:<8}")
                else:
                    if ws:
                        lines.append(ws)
                    else:
                        lines.append('No weather samples available.')

                self.weather_text.insert(tk.END, "\n".join(lines))
            except Exception:
                try:
                    self.weather_text.insert(tk.END, 'Weather display failed')
                except Exception:
                    pass
            finally:
                try:
                    self.weather_text.config(state='disabled')
                except Exception:
                    pass

            # redraw route with weather markers if present
            try:
                self.draw_route(path, start, goal, start_name, goal_name, weather_samples=weather_samples)
            except Exception:
                pass

            mode_suffix = ""
            try:
                if getattr(self.pathfinder, 'last_search_mode', None) == 'fallback':
                    mode_suffix = " (robust fallback)"
            except Exception:
                mode_suffix = ""
            self.status_label.config(text=f"Route ready: {start_name} → {goal_name}{mode_suffix}")
        except Exception as e:
            self.status_label.config(text="Weather update failed")
            print('Weather apply failed:', e)

    def on_scroll_zoom(self, event):
        if event.inaxes != self.ax:
            return

        self._stop_pan_inertia()
        self._view_interaction_mode = "zoom"

        cur_x0, cur_x1, cur_y0, cur_y1 = self._view_target or self._get_current_window_normalized()
        xspan = max(1e-9, cur_x1 - cur_x0)
        yspan = max(1e-9, cur_y1 - cur_y0)

        # Support high-resolution wheel/trackpad events using event.step when available.
        raw_step = getattr(event, "step", None)
        if raw_step is None:
            raw_step = -1.0 if getattr(event, "button", None) == "down" else 1.0
        step = max(-6.0, min(6.0, float(raw_step)))
        # Exponential scaling provides smoother zoom progression than fixed jumps.
        scale = 1.12 ** (-step)

        # Prevent zooming so far out the map appears tiny, and so far in it is unusable.
        min_w, min_h, max_w, max_h = self._window_limits()

        new_width = min(max(xspan * scale, min_w), max_w)
        new_height = min(max(yspan * scale, min_h), max_h)

        # Anchor zoom on cursor position when available for precise control.
        if event.xdata is not None and event.ydata is not None:
            anchor_x = float(event.xdata)
            anchor_y = float(event.ydata)
        else:
            anchor_x = (cur_x0 + cur_x1) / 2.0
            anchor_y = (cur_y0 + cur_y1) / 2.0

        x_ratio = (anchor_x - cur_x0) / xspan
        y_ratio = (anchor_y - cur_y0) / yspan
        x_ratio = min(max(x_ratio, 0.0), 1.0)
        y_ratio = min(max(y_ratio, 0.0), 1.0)

        x0 = anchor_x - (new_width * x_ratio)
        x1 = x0 + new_width
        y0 = anchor_y - (new_height * y_ratio)
        y1 = y0 + new_height

        x0, x1, y0, y1 = self._clamp_window_normalized(x0, x1, y0, y1)
        self._queue_view_target(x0, x1, y0, y1)

    def _draw_interaction_frame(self, force=False):
        now = time.perf_counter()
        if force or (now - self._last_interaction_draw) >= self._interaction_draw_interval:
            self.canvas.draw_idle()
            self._last_interaction_draw = now

    def _window_limits(self):
        x_min_data, x_max_data, y_min_data, y_max_data = self._get_data_bounds()
        full_w = x_max_data - x_min_data
        full_h = y_max_data - y_min_data
        min_w = max(18.0, full_w * 0.006)
        min_h = max(18.0, full_h * 0.006)
        max_w = full_w * 1.02
        max_h = full_h * 1.02
        return min_w, min_h, max_w, max_h

    def _get_data_bounds(self):
        return -0.5, self.grid.width - 0.5, -0.5, self.grid.height - 0.5

    def _get_current_window_normalized(self):
        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()
        x0, x1 = (cur_xlim[0], cur_xlim[1]) if cur_xlim[0] <= cur_xlim[1] else (cur_xlim[1], cur_xlim[0])
        y0, y1 = (cur_ylim[0], cur_ylim[1]) if cur_ylim[0] <= cur_ylim[1] else (cur_ylim[1], cur_ylim[0])
        return float(x0), float(x1), float(y0), float(y1)

    def _clamp_window_normalized(self, x0, x1, y0, y1):
        x_min_data, x_max_data, y_min_data, y_max_data = self._get_data_bounds()

        width = max(1e-9, x1 - x0)
        height = max(1e-9, y1 - y0)
        min_w, min_h, max_w, max_h = self._window_limits()
        width = min(max(width, min_w), max_w)
        height = min(max(height, min_h), max_h)

        cx = (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0
        x0 = cx - (width / 2.0)
        x1 = cx + (width / 2.0)
        y0 = cy - (height / 2.0)
        y1 = cy + (height / 2.0)

        if x0 < x_min_data:
            shift = x_min_data - x0
            x0 += shift
            x1 += shift
        if x1 > x_max_data:
            shift = x1 - x_max_data
            x0 -= shift
            x1 -= shift

        if y0 < y_min_data:
            shift = y_min_data - y0
            y0 += shift
            y1 += shift
        if y1 > y_max_data:
            shift = y1 - y_max_data
            y0 -= shift
            y1 -= shift

        return x0, x1, y0, y1

    def _set_window_from_normalized(self, x0, x1, y0, y1):
        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()
        xinverted = cur_xlim[0] > cur_xlim[1]
        yinverted = cur_ylim[0] > cur_ylim[1]
        self.ax.set_xlim([x1, x0] if xinverted else [x0, x1])
        self.ax.set_ylim([y1, y0] if yinverted else [y0, y1])

    def _queue_view_target(self, x0, x1, y0, y1):
        self._view_target = (float(x0), float(x1), float(y0), float(y1))
        self._last_view_input = time.perf_counter()
        if not self._view_animating:
            self._view_animating = True
            self._view_last_tick = self._last_view_input
            self._animate_view_step()

    def _animate_view_step(self):
        if not self._view_animating or self._view_target is None:
            self._view_animating = False
            self._view_anim_after_id = None
            return

        now = time.perf_counter()
        dt = max(1e-4, now - self._view_last_tick)
        self._view_last_tick = now

        tau = self._view_tau_pan if self._view_interaction_mode == "pan" else self._view_tau_zoom
        alpha = 1.0 - math.exp(-dt / tau)
        alpha = min(max(alpha, 0.12), 0.72)

        cx0, cx1, cy0, cy1 = self._get_current_window_normalized()
        tx0, tx1, ty0, ty1 = self._view_target

        nx0 = cx0 + (tx0 - cx0) * alpha
        nx1 = cx1 + (tx1 - cx1) * alpha
        ny0 = cy0 + (ty0 - cy0) * alpha
        ny1 = cy1 + (ty1 - cy1) * alpha
        nx0, nx1, ny0, ny1 = self._clamp_window_normalized(nx0, nx1, ny0, ny1)

        self._set_window_from_normalized(nx0, nx1, ny0, ny1)
        self._draw_interaction_frame(force=False)

        err = max(abs(tx0 - nx0), abs(tx1 - nx1), abs(ty0 - ny0), abs(ty1 - ny1))
        settle = err < 0.03
        idle_long_enough = (now - self._last_view_input) > 0.05

        if settle and idle_long_enough:
            tx0, tx1, ty0, ty1 = self._clamp_window_normalized(tx0, tx1, ty0, ty1)
            self._set_window_from_normalized(tx0, tx1, ty0, ty1)
            self._draw_interaction_frame(force=True)
            self._view_target = None
            self._view_animating = False
            self._view_anim_after_id = None
            self._view_interaction_mode = "idle"
            return

        delay_ms = max(1, int(round(1000.0 / self._view_fps)))
        try:
            self._view_anim_after_id = self.root.after(delay_ms, self._animate_view_step)
        except Exception:
            self._view_animating = False
            self._view_anim_after_id = None

    def on_pan_press(self, event):
        # Left mouse button starts panning when pointer is inside axes.
        if event.inaxes != self.ax or event.button != 1:
            return
        if self.ax.get_navigate_mode() in ("PAN", "ZOOM"):
            return
        if event.x is None or event.y is None:
            return

        self._stop_pan_inertia()
        self._view_interaction_mode = "pan"
        self._pan_active = True
        # Track pixel-space mouse position for stable drag math.
        self._pan_last = (event.x, event.y)
        self._pan_last_data = (
            float(event.xdata) if event.xdata is not None else None,
            float(event.ydata) if event.ydata is not None else None,
        )
        self._pan_last_ts = time.perf_counter()
        self._pan_velocity_data = (0.0, 0.0)

    def on_pan_drag(self, event):
        if not self._pan_active:
            return
        if event.x is None or event.y is None or self._pan_last is None:
            return

        last_x, last_y = self._pan_last
        dx_px = event.x - last_x
        dy_px = event.y - last_y
        self._pan_last = (event.x, event.y)

        now = time.perf_counter()
        dt = max(1e-4, now - (self._pan_last_ts or now))
        self._pan_last_ts = now

        base_x0, base_x1, base_y0, base_y1 = self._view_target or self._get_current_window_normalized()

        # Prefer data-space deltas for stable, low-jitter panning at all zoom levels.
        x_shift = None
        y_shift = None
        if event.xdata is not None and event.ydata is not None:
            last_dx, last_dy = self._pan_last_data or (None, None)
            if last_dx is not None and last_dy is not None:
                x_shift = -(float(event.xdata) - float(last_dx))
                y_shift = -(float(event.ydata) - float(last_dy))
            self._pan_last_data = (float(event.xdata), float(event.ydata))

        if x_shift is None or y_shift is None:
            bbox = self.ax.bbox
            if bbox is None or bbox.width == 0 or bbox.height == 0:
                return
            cur_xlim = self.ax.get_xlim()
            cur_ylim = self.ax.get_ylim()
            xsign = -1.0 if cur_xlim[0] > cur_xlim[1] else 1.0
            ysign = -1.0 if cur_ylim[0] > cur_ylim[1] else 1.0
            xspan_signed = (base_x1 - base_x0) * xsign
            yspan_signed = (base_y1 - base_y0) * ysign
            x_shift = -dx_px * (xspan_signed / bbox.width)
            y_shift = -dy_px * (yspan_signed / bbox.height)

        # Shift window so map content follows mouse drag direction.
        x0 = base_x0 + x_shift
        x1 = base_x1 + x_shift
        y0 = base_y0 + y_shift
        y1 = base_y1 + y_shift
        x0, x1, y0, y1 = self._clamp_window_normalized(x0, x1, y0, y1)

        inst_vx = x_shift / dt
        inst_vy = y_shift / dt
        old_vx, old_vy = self._pan_velocity_data
        self._pan_velocity_data = (
            (old_vx * 0.65) + (inst_vx * 0.35),
            (old_vy * 0.65) + (inst_vy * 0.35),
        )
        self._queue_view_target(x0, x1, y0, y1)

    def on_pan_release(self, event):
        if event.button == 1:
            self._pan_active = False
            self._pan_last = None
            self._pan_last_data = None
            self._start_pan_inertia()
            self._draw_interaction_frame(force=True)

    def _stop_pan_inertia(self):
        self._pan_inertia_active = False
        if self._pan_inertia_after_id is not None:
            try:
                self.root.after_cancel(self._pan_inertia_after_id)
            except Exception:
                pass
        self._pan_inertia_after_id = None

    def _start_pan_inertia(self):
        vx, vy = self._pan_velocity_data
        speed = math.hypot(vx, vy)
        if speed < 6.0:
            self._view_interaction_mode = "idle"
            return
        self._stop_pan_inertia()
        self._pan_inertia_active = True
        self._pan_inertia_last_tick = time.perf_counter()
        self._animate_pan_inertia()

    def _animate_pan_inertia(self):
        if not self._pan_inertia_active:
            self._pan_inertia_after_id = None
            return

        now = time.perf_counter()
        dt = max(1e-4, now - (self._pan_inertia_last_tick or now))
        self._pan_inertia_last_tick = now

        vx, vy = self._pan_velocity_data
        decay = math.exp(-dt / 0.22)
        vx *= decay
        vy *= decay
        self._pan_velocity_data = (vx, vy)

        if math.hypot(vx, vy) < 1.0:
            self._stop_pan_inertia()
            self._view_interaction_mode = "idle"
            return

        base_x0, base_x1, base_y0, base_y1 = self._view_target or self._get_current_window_normalized()
        x_shift = vx * dt
        y_shift = vy * dt
        x0 = base_x0 + x_shift
        x1 = base_x1 + x_shift
        y0 = base_y0 + y_shift
        y1 = base_y1 + y_shift
        x0, x1, y0, y1 = self._clamp_window_normalized(x0, x1, y0, y1)
        self._view_interaction_mode = "pan"
        self._queue_view_target(x0, x1, y0, y1)

        delay_ms = max(1, int(round(1000.0 / self._view_fps)))
        try:
            self._pan_inertia_after_id = self.root.after(delay_ms, self._animate_pan_inertia)
        except Exception:
            self._stop_pan_inertia()
            self._view_interaction_mode = "idle"


# run the program

if __name__ == "__main__":
    root = tk.Tk()
    app = PathfinderGUI(root)
    root.mainloop()
