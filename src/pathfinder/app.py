"""Application entrypoint (renamed from FullSystem.py).

This file replaces the previous `FullSystem.py` filename and imports the
refactored snake_case algorithm modules.
"""

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
try:
    from pathfinder.algorithms.astar import Grid, AStarPathfinder
except Exception:
    # Fallback: load directly from file location to avoid import-order issues
    import importlib.util as _il, os as _os
    _base = Path(__file__).resolve().parent
    _fp = _base / "algorithms" / "astar.py"
    spec = _il.spec_from_file_location("pathfinder.algorithms.astar", str(_fp))
    _mod = _il.module_from_spec(spec)
    spec.loader.exec_module(_mod)
    Grid = _mod.Grid
    AStarPathfinder = _mod.AStarPathfinder

from pathfinder.algorithms.cost_calculator import RouteCostEstimator
from pathfinder.algorithms.weather_estimator import WeatherImpactEstimator

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
        self._view_target = None
        self._view_animating = False
        self._view_anim_after_id = None
        self._view_last_tick = time.perf_counter()
        self._last_view_input = self._view_last_tick
        self._view_fps = 120
        self._view_tau = 0.045
        self._last_interaction_draw = 0.0
        self._interaction_draw_interval = 1.0 / 120.0

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
