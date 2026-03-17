"""CostCalculator module."""

import math

class RouteCostEstimator:
    """
    Parameters:
    - cell_size_nm: How many nautical miles one grid cell represents
    - fuel_cost_per_nm: USD per nautical mile
    - port_fee_per_stop: USD per port call (applied to start + goal)
    - daily_operating_cost: USD per day at sea
    - average_speed_knots: Ship speed in knots
    """
    
    def __init__(
        self,
        cell_size_nm: float = 2.0,             # nautical miles per grid cell
        fuel_cost_per_nm: float = 0.9,         # GBP/nm
        port_fee_per_stop: float = 18646.98,    # GBP per port
        daily_operating_cost: float = 13425.82, # GBP/day
        average_speed_knots: float = 20.0      # knots
    ):
        self.cell_size_nm = cell_size_nm
        self.fuel_cost_per_nm = fuel_cost_per_nm
        self.port_fee_per_stop = port_fee_per_stop
        self.daily_operating_cost = daily_operating_cost
        self.average_speed_knots = average_speed_knots

    def estimate(self, path_length_cells: int) -> dict:

        if path_length_cells <= 0:
            return {"error": "Invalid path length"}

        # Distance in nautical miles
        distance_nm = path_length_cells * self.cell_size_nm

        # Time at sea
        time_hours = distance_nm / self.average_speed_knots
        time_days = time_hours / 24

        # Cost components
        fuel_cost = distance_nm * self.fuel_cost_per_nm
        time_cost = time_days * self.daily_operating_cost
        port_cost = self.port_fee_per_stop * 2  # start + goal

        total_cost = fuel_cost + time_cost + port_cost

        return {
            "distance_nm": round(distance_nm, 1),
            "time_days": round(time_days, 1),
            "fuel_cost_usd": round(fuel_cost),
            "operating_cost_usd": round(time_cost),
            "port_fees_usd": round(port_cost),
            "total_cost_usd": round(total_cost),
            "formatted_total": f"${round(total_cost):,}"
        }

    def print_breakdown(self, cost_data: dict):
        """Nice console print of the cost estimate"""
        if "error" in cost_data:
            print(cost_data["error"])
            return

        print("\nRoute Cost Estimate:")
        print(f"  Distance:      {cost_data['distance_nm']:,} nautical miles")
        print(f"  Time at sea:   ~{cost_data['time_days']} days")
        print("  ────────────────────────────────────")
        print(f"  Fuel:          ${cost_data['fuel_cost_usd']:,}")
        print(f"  Operating:     ${cost_data['operating_cost_usd']:,}")
        print(f"  Port fees:     ${cost_data['port_fees_usd']:,}")
        print("  ────────────────────────────────────")
        print(f"  TOTAL:         {cost_data['formatted_total']}")
