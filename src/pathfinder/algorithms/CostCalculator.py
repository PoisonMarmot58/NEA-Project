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
		# Freight basis: if density > 1 t/m^3, mass usually dominates; otherwise volume.
		self.density_threshold_t_per_m3 = 1.0
		self.fcl_revenue_tonne_capacity = 14000.0
		self.fcl_terminal_handling_per_rt = 9.0
		self.fcl_documentation_fee = 85.0
		# LCL charges are commonly based on revenue tons (W/M): 1 RT = 1 tonne or 1 m^3.
		self.lcl_pricing = {
			"ocean_freight_per_rt": 85.0,
			"origin_thc_per_rt": 18.0,
			"destination_thc_per_rt": 18.0,
			"documentation_fee": 95.0,
			"security_fee": 35.0,
			"customs_entry_fee": 60.0,
			"fuel_surcharge_percent": 0.12,
			"distance_surcharge_per_rt_nm": 0.045,
			"minimum_lcl_charge": 450.0,
		}

		# Try to refresh price from environment / file / remote if requested
		if auto_refresh_prices:
			try:
				self.refresh_prices()
			except Exception:
				# Swallow refresh errors; defaults remain usable
				pass

	def estimate(
		self,
		path_length_cells: int,
		port_calls: int = 2,
		load_type: str = "FCL",
		cargo_mass_tonnes: Optional[float] = None,
		cargo_volume_m3: Optional[float] = None,
		time_multiplier: float = 1.0,
	) -> dict:

		if path_length_cells <= 0:
			return {"error": "Invalid path length"}
		if time_multiplier <= 0:
			time_multiplier = 1.0

		load_key = (load_type or "FCL").upper()
		if load_key not in ("FCL", "LCL"):
			load_key = "FCL"

		cargo_defaults_applied = False
		if cargo_mass_tonnes is None or cargo_volume_m3 is None:
			cargo_mass_tonnes = 1.0
			cargo_volume_m3 = 1.0
			cargo_defaults_applied = True
		if cargo_mass_tonnes <= 0 or cargo_volume_m3 <= 0:
			return {"error": "Cargo mass and cargo volume must be greater than zero"}

		density_t_per_m3 = cargo_mass_tonnes / cargo_volume_m3
		pricing_basis = "mass" if density_t_per_m3 > self.density_threshold_t_per_m3 else "volume"
		chargeable_quantity = cargo_mass_tonnes if pricing_basis == "mass" else cargo_volume_m3

		# Distance in nautical miles
		distance_nm = path_length_cells * self.cell_size_nm

		# Time at sea
		time_hours = distance_nm / self.average_speed_knots
		time_days = (time_hours / 24) * time_multiplier

		if load_key == "LCL":
			lcl_rt = max(cargo_mass_tonnes, cargo_volume_m3)
			ocean_freight = lcl_rt * self.lcl_pricing["ocean_freight_per_rt"]
			origin_thc = lcl_rt * self.lcl_pricing["origin_thc_per_rt"]
			destination_thc = lcl_rt * self.lcl_pricing["destination_thc_per_rt"]
			fuel_surcharge = ocean_freight * self.lcl_pricing["fuel_surcharge_percent"] * time_multiplier
			distance_surcharge = lcl_rt * distance_nm * self.lcl_pricing["distance_surcharge_per_rt_nm"]
			fixed_fees = (
				self.lcl_pricing["documentation_fee"]
				+ self.lcl_pricing["security_fee"]
				+ self.lcl_pricing["customs_entry_fee"]
			)

			subtotal = ocean_freight + origin_thc + destination_thc + fuel_surcharge + distance_surcharge + fixed_fees
			subtotal = max(subtotal, self.lcl_pricing["minimum_lcl_charge"])
			contingency = subtotal * self.contingency_percent
			total_cost = subtotal + contingency

			return {
				"distance_nm": round(distance_nm, 1),
				"time_days": round(time_days, 1),
				"contingency_usd": round(contingency),
				"total_cost_usd": round(total_cost),
				"formatted_total": f"${round(total_cost):,}",
				"fuel_price_per_tonne": round(self.fuel_price_per_tonne, 2),
				"load_type": load_key,
				"cargo_mass_tonnes": round(cargo_mass_tonnes, 3),
				"cargo_volume_m3": round(cargo_volume_m3, 3),
				"cargo_defaults_applied": cargo_defaults_applied,
				"density_t_per_m3": round(density_t_per_m3, 3),
				"pricing_basis": pricing_basis,
				"chargeable_quantity": round(chargeable_quantity, 3),
				"revenue_tonnes": round(lcl_rt, 3),
				"ocean_freight_usd": round(ocean_freight),
				"origin_thc_usd": round(origin_thc),
				"destination_thc_usd": round(destination_thc),
				"fuel_surcharge_usd": round(fuel_surcharge),
				"distance_surcharge_usd": round(distance_surcharge),
				"fixed_fees_usd": round(fixed_fees),
			}

		# FCL: estimate cargo share of vessel voyage cost using density-based charge basis.
		fuel_cost = time_days * self.fuel_consumption_tpd * self.fuel_price_per_tonne
		time_cost = time_days * self.daily_operating_cost
		port_cost = self.port_fee_per_stop * port_calls
		voyage_total = fuel_cost + time_cost + port_cost

		allocation_share = min(max(chargeable_quantity / self.fcl_revenue_tonne_capacity, 0.001), 1.0)
		allocated_voyage_cost = voyage_total * allocation_share
		terminal_handling = chargeable_quantity * self.fcl_terminal_handling_per_rt

		subtotal = allocated_voyage_cost + terminal_handling + self.fcl_documentation_fee
		contingency = subtotal * self.contingency_percent
		total_cost = subtotal + contingency

		return {
			"distance_nm": round(distance_nm, 1),
			"time_days": round(time_days, 1),
			"fuel_cost_usd": round(fuel_cost),
			"operating_cost_usd": round(time_cost),
			"port_fees_usd": round(port_cost),
			"allocated_voyage_usd": round(allocated_voyage_cost),
			"terminal_handling_usd": round(terminal_handling),
			"documentation_fee_usd": round(self.fcl_documentation_fee),
			"contingency_usd": round(contingency),
			"total_cost_usd": round(total_cost),
			"formatted_total": f"${round(total_cost):,}",
			"fuel_price_per_tonne": round(self.fuel_price_per_tonne, 2),
			"load_type": load_key,
			"cargo_mass_tonnes": round(cargo_mass_tonnes, 3),
			"cargo_volume_m3": round(cargo_volume_m3, 3),
			"cargo_defaults_applied": cargo_defaults_applied,
			"density_t_per_m3": round(density_t_per_m3, 3),
			"pricing_basis": pricing_basis,
			"chargeable_quantity": round(chargeable_quantity, 3),
			"allocation_share": round(allocation_share, 6),
		}

	def print_breakdown(self, cost_data: dict):
		"""Nice console print of the cost estimate"""
		if "error" in cost_data:
			print(cost_data["error"])
			return

		print("\nRoute Cost Estimate:")
		print(f"  Distance:      {cost_data['distance_nm']:,} nautical miles")
		print(f"  Time at sea:   ~{cost_data['time_days']} days")
		if 'load_type' in cost_data:
			print(f"  Load type:     {cost_data['load_type']}")
		print("  ────────────────────────────────────")
		print(f"  Fuel:          ${cost_data['fuel_cost_usd']:,}")
		if 'fuel_price_per_tonne' in cost_data:
			print(f"  (fuel price:   ${cost_data['fuel_price_per_tonne']:,} per tonne)")
		print(f"  Operating:     ${cost_data['operating_cost_usd']:,}")
		print(f"  Port fees:     ${cost_data['port_fees_usd']:,}")
		if 'load_handling_usd' in cost_data:
			print(f"  Load handling: ${cost_data['load_handling_usd']:,}")
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
