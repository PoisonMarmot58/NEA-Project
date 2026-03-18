"""CostCalculator module.

This module supports overriding the bunker fuel price at runtime so estimates
can use up-to-date prices. Resolution order (highest precedence first):

- Environment variable `BUNKER_PRICE_PER_TON` (USD per tonne)
- JSON file at `src/pathfinder/data/prices.json` with key
    `bunker_price_per_tonne`
- Optional fetch from URL in `BUNKER_PRICE_URL` (expects JSON with a
    recognizable price field)

If none are present, the default hardcoded value is used.
"""

import math
import os
import json
from pathlib import Path
from typing import Optional

try:
        import requests
except Exception:
        requests = None


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
        auto_refresh_prices: bool = True,
    ):
        self.cell_size_nm = cell_size_nm
        self.average_speed_knots = average_speed_knots
        self.fuel_consumption_tpd = fuel_consumption_tpd
        # Initial price (may be overridden below)
        self.fuel_price_per_tonne = fuel_price_per_tonne
        self.daily_operating_cost = daily_operating_cost
        self.port_fee_per_stop = port_fee_per_stop
        self.contingency_percent = contingency_percent

        # Try to refresh price from environment / file / remote if requested
        if auto_refresh_prices:
            try:
                self.refresh_prices()
            except Exception:
                # Swallow refresh errors; defaults remain usable
                pass

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
            "formatted_total": f"${round(total_cost):,}",
            "fuel_price_per_tonne": round(self.fuel_price_per_tonne, 2),
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
        if 'fuel_price_per_tonne' in cost_data:
            print(f"  (fuel price:   ${cost_data['fuel_price_per_tonne']:,} per tonne)")
        print(f"  Operating:     ${cost_data['operating_cost_usd']:,}")
        print(f"  Port fees:     ${cost_data['port_fees_usd']:,}")
        print(f"  Contingency:   ${cost_data['contingency_usd']:,}")
        print("  ────────────────────────────────────")
        print(f"  TOTAL:         {cost_data['formatted_total']}")

    def refresh_prices(self, prices_json_path: Optional[str] = None) -> None:
        """Refresh bunker price using environment, a local JSON file, or
        a remote URL. This method updates `self.fuel_price_per_tonne` when a
        newer value is found.

        `prices_json_path` can be used to point to a specific JSON file. If
        not provided the method looks for `src/pathfinder/data/prices.json`.
        """
        # 1) Environment variable override
        env_price = os.environ.get("BUNKER_PRICE_PER_TON")
        if env_price:
            try:
                self.fuel_price_per_tonne = float(env_price)
                return
            except ValueError:
                pass

        # 2) Local prices.json file
        if prices_json_path:
            p = Path(prices_json_path)
        else:
            p = Path(__file__).resolve().parents[1] / "data" / "prices.json"

        if p.exists():
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                val = raw.get("bunker_price_per_tonne") or raw.get("fuel_price_per_tonne")
                if val:
                    self.fuel_price_per_tonne = float(val)
                    return
            except Exception:
                pass

        # 3) Remote fetch (optional) via BUNKER_PRICE_URL
        url = os.environ.get("BUNKER_PRICE_URL")
        if url and requests is not None:
            try:
                resp = requests.get(url, timeout=6)
                resp.raise_for_status()
                data = resp.json()
                # Try common keys
                for key in ("price", "bunker_price_per_tonne", "fuel_price_per_tonne", "value"):
                    v = data.get(key)
                    if v:
                        self.fuel_price_per_tonne = float(v)
                        return
                # Nested search: look for numeric value in first level
                for v in data.values():
                    try:
                        if isinstance(v, (int, float)):
                            self.fuel_price_per_tonne = float(v)
                            return
                    except Exception:
                        continue
            except Exception:
                # Ignore remote errors
                pass
