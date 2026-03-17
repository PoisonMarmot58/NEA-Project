"""CostCalculator module."""

import math

class RouteCostEstimator:
    """
    Parameters:
    - cell_size_nm: Nautical miles represented by one grid cell
    - average_speed_knots: Service speed in knots
    - fuel_consumption_tpd: Fuel burn in tonnes per day
    - fuel_price_per_tonne: Bunker fuel price in USD per tonne
    - daily_operating_cost: Vessel operating cost in USD per day
    - port_fee_per_stop: Port call fee in USD (applied to start + goal)
    - contingency_percent: Extra % for routing/weather/handling variability
    """
    
    def __init__(
        self,
        cell_size_nm: float = 2.5,
        average_speed_knots: float = 16.5,
        fuel_consumption_tpd: float = 70.0,
        fuel_price_per_tonne: float = 620.0,
        daily_operating_cost: float = 35000.0,
        port_fee_per_stop: float = 125000.0,
        contingency_percent: float = 0.12,
    ):
        self.cell_size_nm = cell_size_nm
        self.average_speed_knots = average_speed_knots
        self.fuel_consumption_tpd = fuel_consumption_tpd
        self.fuel_price_per_tonne = fuel_price_per_tonne
        self.daily_operating_cost = daily_operating_cost
        self.port_fee_per_stop = port_fee_per_stop
        self.contingency_percent = contingency_percent

    def estimate(self, path_length_cells: int, port_calls: int = 2) -> dict:

        if path_length_cells <= 0:
            return {"error": "Invalid path length"}

        # Distance in nautical miles
        distance_nm = path_length_cells * self.cell_size_nm

        # Time at sea
        time_hours = distance_nm / self.average_speed_knots
        time_days = time_hours / 24

        # Cost components
        fuel_cost = time_days * self.fuel_consumption_tpd * self.fuel_price_per_tonne
        time_cost = time_days * self.daily_operating_cost
        port_cost = self.port_fee_per_stop * port_calls

        subtotal = fuel_cost + time_cost + port_cost
        contingency = subtotal * self.contingency_percent
        total_cost = subtotal + contingency

        return {
            "distance_nm": round(distance_nm, 1),
            "time_days": round(time_days, 1),
            "fuel_cost_usd": round(fuel_cost),
            "operating_cost_usd": round(time_cost),
            "port_fees_usd": round(port_cost),
            "contingency_usd": round(contingency),
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
        print(f"  Contingency:   ${cost_data['contingency_usd']:,}")
        print("  ────────────────────────────────────")
        print(f"  TOTAL:         {cost_data['formatted_total']}")
