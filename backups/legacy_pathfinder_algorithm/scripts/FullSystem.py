"""FullSystem module."""

import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from Astar import Grid, AStarPathfinder   
from CostCalculator import RouteCostEstimator

# ────────────────────────────────────────────────
#                     CONFIG
# ────────────────────────────────────────────────

GRID_FILE = (
    r"C:\Users\isaac\OneDrive\Desktop\NEA Project new\NEA-Project-2"
    r"\Pathfinder Algorithm\Data\FullGridOfEurope.npy"
)

PORTS = [
    {"name": "Rotterdam",   "coords": (595, 475)},
    {"name": "Hamburg",     "coords": (540, 680)},
    {"name": "Piraeus",     "coords": (965, 1140)},
    {"name": "Algeciras",   "coords": (1050, 180)},
    {"name": "Valencia",    "coords": (920, 320)},
    {"name": "Felixstowe",  "coords": (580, 520)},
    {"name": "Le Havre",    "coords": (650, 480)},
    {"name": "Antwerp",     "coords": (610, 465)},
    # Add ports: these are wrong
]

# ────────────────────────────────────────────────
#                    GUI APPLICATION
# ────────────────────────────────────────────────

class PathfinderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Europe Sea Route Finder")
        self.root.geometry("1100x850")
        self.root.configure(bg="#e8f0f8")

        # Load grid and pathfinder
        self.load_grid()

        # Cost estimator (these values must be changed)
        self.cost_estimator = RouteCostEstimator(
            cell_size_nm=2.5,
            fuel_cost_per_nm=1.3,
            port_fee_per_stop=30000,
            daily_operating_cost=20000,
            average_speed_knots=21.0 
        )

        # ── Header ──
        tk.Label(
            root,
            text="Sea Route Pathfinder",
            font=("Arial", 22, "bold"),
            bg="#e8f0f8",
            fg="#2c3e50",
        ).pack(pady=15)

        # ── Port selection ──
        frame = tk.Frame(root, bg="#e8f0f8")
        frame.pack(pady=10)

        tk.Label(
            frame,
            text="Start Port:",
            font=("Arial", 12),
            bg="#e8f0f8",
        ).grid(row=0, column=0, padx=15, pady=8, sticky="e")
        self.start_var = tk.StringVar(value=PORTS[0]["name"])
        self.start_menu = ttk.Combobox(
            frame,
            textvariable=self.start_var,
            values=[p["name"] for p in PORTS],
            state="readonly",
            width=35,
            font=("Arial", 11),
        )
        self.start_menu.grid(row=0, column=1, padx=15, pady=8)

        tk.Label(
            frame,
            text="Goal Port:",
            font=("Arial", 12),
            bg="#e8f0f8",
        ).grid(row=1, column=0, padx=15, pady=8, sticky="e")
        self.goal_var = tk.StringVar(value=PORTS[2]["name"])
        self.goal_menu = ttk.Combobox(
            frame,
            textvariable=self.goal_var,
            values=[p["name"] for p in PORTS],
            state="readonly",
            width=35,
            font=("Arial", 11),
        )
        self.goal_menu.grid(row=1, column=1, padx=15, pady=8)

        # ── Buttons ──
        btn_frame = tk.Frame(root, bg="#e8f0f8")
        btn_frame.pack(pady=20)

        tk.Button(
            btn_frame,
            text="Find Route",
            font=("Arial", 13, "bold"),
            bg="#27ae60",
            fg="white",
            width=18,
            height=2,
            command=self.find_route,
        ).pack(side=tk.LEFT, padx=20)

        tk.Button(btn_frame, text="Clear Map", font=("Arial", 13, "bold"), bg="#c0392b", fg="white", width=18, height=2,
                  command=self.clear_map).pack(side=tk.LEFT, padx=20)

        tk.Button(btn_frame, text="Exit", font=("Arial", 13, "bold"), bg="#34495e", fg="white", width=18, height=2,
                  command=self.exit_app).pack(side=tk.LEFT, padx=20)

        # ── Status label ──
        self.status_label = tk.Label(
            root,
            text="Ready – select ports and click 'Find Route'",
            font=("Arial", 11),
            bg="#e8f0f8",
            fg="#34495e",
        )
        self.status_label.pack(pady=10)

        # ── Cost display box ──
        self.cost_frame = tk.LabelFrame(
            root,
            text="Estimated Shipping Cost",
            font=("Arial", 12, "bold"),
            bg="#f8f9fa",
            padx=10,
            pady=10,
        )
        self.cost_frame.pack(fill=tk.X, padx=15, pady=5)

        self.cost_text = tk.Text(self.cost_frame, height=7, width=60, font=("Arial", 10), wrap=tk.WORD)
        self.cost_text.pack(fill=tk.BOTH, expand=True)
        self.cost_text.insert(tk.END, "Cost estimate will appear here after finding a route.")
        self.cost_text.config(state="disabled")

        # ── Matplotlib canvas for map ──
        self.fig, self.ax = plt.subplots(figsize=(10, 6.5))
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

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

    def find_route(self):
        start_name = self.start_var.get()
        goal_name  = self.goal_var.get()

        if start_name == goal_name:
            messagebox.showwarning("Warning", "Start and goal ports cannot be the same.")
            return

        start = next(p["coords"] for p in PORTS if p["name"] == start_name)
        goal  = next(p["coords"] for p in PORTS if p["name"] == goal_name)

        self.status_label.config(text=f"Computing route: {start_name} → {goal_name} ...")
        self.root.update_idletasks()

        try:
            path = self.pathfinder.find_path(start, goal)

            if path:
                length = len(path) - 1
                self.status_label.config(text=f"Route found! {length} steps")

                # Calculate cost
                cost_data = self.cost_estimator.estimate(length)

                # Show cost in text box
                cost_text = (
                    f"Route: {start_name} → {goal_name}\n"
                    f"Distance: {cost_data['distance_nm']:,} nautical miles\n"
                    f"Time at sea: ~{cost_data['time_days']} days\n"
                    f"─" * 40 + "\n"
                    f"Fuel cost:          ${cost_data['fuel_cost_usd']:,}\n"
                    f"Operating cost:     ${cost_data['operating_cost_usd']:,}\n"
                    f"Port fees (start+goal): ${cost_data['port_fees_usd']:,}\n"
                    f"─" * 40 + "\n"
                    f"TOTAL ESTIMATED COST: {cost_data['formatted_total']}"
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

        # Background
        water = (self.grid.data == 0)
        land  = (self.grid.data == 1) | (self.grid.data == 2)
        ports = (self.grid.data == 3) | (self.grid.data == 4)

        self.ax.imshow(water, cmap='Blues', alpha=0.35, origin='upper')
        self.ax.imshow(land,  cmap='Greys',  alpha=0.75, origin='upper')
        self.ax.imshow(ports, cmap='Reds',   alpha=0.95, origin='upper')

        # Route line + markers
        rows, cols = zip(*path)
        self.ax.plot(cols, rows, 'r-', linewidth=3, alpha=0.9, label='Sea Route')
        self.ax.plot(cols[0], rows[0], 'go', markersize=14, label=f'Start: {start_name}')
        self.ax.plot(cols[-1], rows[-1], 'yo', markersize=14, label=f'Goal: {goal_name}')

        self.ax.set_title(f"Route: {start_name} → {goal_name}  ({len(path)-1} steps)", fontsize=14)
        self.ax.legend(loc='upper right', fontsize=10)
        self.ax.axis('off')
        self.canvas.draw()


# ────────────────────────────────────────────────
#                     RUN THE GUI
# ────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app = PathfinderGUI(root)
    root.mainloop()
