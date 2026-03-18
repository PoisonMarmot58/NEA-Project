"""Weather impact estimator for sea routes.

This module maps grid cells to lat/lon using a small set of control points
(matching `MapToGrid.py`), samples points along a computed path, queries
Open-Meteo for current wind speed, and returns a time multiplier and a
small human-readable summary of the effect.

Behaviour:
- Sample up to 5 points along the path (start, 1/4, 1/2, 3/4, end).
- Query Open-Meteo `current_weather` for each sample point (if `requests`
  is available). Wind speed (m/s) is converted to knots.
- If average wind > 10 knots, each knot above 10 adds 2% extra time.
  (multiplier = 1 + (avg_knots - 10) * 0.02)

If network or requests is unavailable, returns multiplier=1 and a note.
"""

from typing import List, Tuple
from scipy.interpolate import LinearNDInterpolator
from pathlib import Path
import math
import os
import numpy as np

try:
    import requests
except Exception:
    requests = None

# Control points mapping lat/lon -> pixel row/col (copied from MapToGrid)
_CONTROL_POINTS = [
    # [lat, lon, pixel_row(y), pixel_col(x)]
    [51.923,  4.479,  2001, 1950],    # Rotterdam
    [53.547,  9.987,  2214, 1895],    # Hamburg
    [36.140, -5.435,  1298, 3025],    # Gibraltar
    [37.942, 23.637,  3044, 2918],    # Piraeus
    [38.710, -9.126,  1145, 2806],    # Lisbon
    [51.962,  1.351,  1842, 1892],    # Felixstowe
]


class WeatherImpactEstimator:
    def __init__(self, open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"):
        self.open_meteo_url = os.environ.get("BUNKER_PRICE_URL") or open_meteo_url
        # Build interpolators for pixel(row,col) -> lat & lon using control points
        cps = _CONTROL_POINTS
        pixels = [(c[2], c[3]) for c in cps]
        lats = [c[0] for c in cps]
        lons = [c[1] for c in cps]
        try:
            self._interp_lat = LinearNDInterpolator(pixels, lats)
            self._interp_lon = LinearNDInterpolator(pixels, lons)
        except Exception:
            self._interp_lat = None
            self._interp_lon = None

    def grid_to_latlon(self, row: int, col: int) -> Tuple[float, float]:
        """Approximate lat,lon for a grid cell by inverting the linear mapping.

        We use a simple search over control point deltas: find the nearest
        control point and assume small linear offsets.
        """
        # Prefer interpolation from known control points
        try:
            if self._interp_lat is not None and self._interp_lon is not None:
                latv = self._interp_lat((row, col))
                lonv = self._interp_lon((row, col))
                # LinearNDInterpolator returns numpy scalar or array
                latv = float(np.asarray(latv).item())
                lonv = float(np.asarray(lonv).item())
                return latv, lonv
        except Exception:
            pass

        # Fallback: nearest control point heuristic
        best = None
        best_dist = float('inf')
        for lat, lon, prow, pcol in _CONTROL_POINTS:
            d = (prow - row) ** 2 + (pcol - col) ** 2
            if d < best_dist:
                best_dist = d
                best = (lat, lon, prow, pcol)

        if best is None:
            return 0.0, 0.0

        lat0, lon0, prow0, pcol0 = best
        deg_per_row = 0.0005
        deg_per_col = 0.0005
        lat = lat0 + (row - prow0) * (-deg_per_row)
        lon = lon0 + (col - pcol0) * (deg_per_col)
        return float(lat), float(lon)

    def sample_path_points(self, path: List[Tuple[int, int]], max_samples: int = 5):
        n = len(path)
        if n == 0:
            return []
        if n <= max_samples:
            idxs = list(range(n))
        else:
            idxs = [0]
            for i in range(1, max_samples - 1):
                idxs.append(int(round(i * (n - 1) / (max_samples - 1))))
            idxs.append(n - 1)

        pts = [path[i] for i in idxs]
        latlons = [self.grid_to_latlon(r, c) for r, c in pts]
        return latlons

    def estimate_path_impact(self, path: List[Tuple[int, int]], ship_profile=None):
        """Return (time_multiplier: float, summary: str).

        If weather data is unavailable returns multiplier 1.0 and a note.
        """
        latlons = self.sample_path_points(path)
        if not latlons:
            return 1.0, "No path samples"

        if requests is None:
            return 1.0, "Weather unavailable (requests not installed)"
            from datetime import datetime, timedelta
            # Build full lat/lon list for the whole path (for distance/ETA calculation)
            full_latlons = [self.grid_to_latlon(r, c) for r, c in path]
            if not full_latlons:
                return 1.0, "No path samples"

            if requests is None:
                return 1.0, "Weather unavailable (requests not installed)"

            # compute cumulative distance along full path (meters)
            def haversine_m(a, b):
                lat1, lon1 = a
                lat2, lon2 = b
                R = 6371000.0
                phi1 = math.radians(lat1)
                phi2 = math.radians(lat2)
                dphi = math.radians(lat2 - lat1)
                dlambda = math.radians(lon2 - lon1)
                x = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
                return 2 * R * math.asin(min(1, math.sqrt(x)))

            cumdist = [0.0]
            for i in range(1, len(full_latlons)):
                d = haversine_m(full_latlons[i-1], full_latlons[i])
                cumdist.append(cumdist[-1] + d)

            # sample indices (same logic as sample_path_points)
            n = len(path)
            max_samples = 5
            if n <= max_samples:
                idxs = list(range(n))
            else:
                idxs = [0]
                for i in range(1, max_samples - 1):
                    idxs.append(int(round(i * (n - 1) / (max_samples - 1))))
                idxs.append(n - 1)

            samples = [full_latlons[i] for i in idxs]

            # Determine ship speed (m/s) from profile or default
            try:
                if ship_profile is None:
                    avg_speed_knots = 16.5
                elif isinstance(ship_profile, dict):
                    avg_speed_knots = ship_profile.get('average_speed_knots', 16.5)
                else:
                    avg_speed_knots = getattr(ship_profile, 'average_speed_knots', 16.5)
                avg_speed_knots = float(avg_speed_knots)
            except Exception:
                avg_speed_knots = 16.5
            speed_mps = avg_speed_knots * 0.514444

            now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

            winds_knots = []
            wind_dirs = []
            wave_heights = []

            # Query hourly forecasts and pick the hour nearest each sample's ETA
            for idx in idxs:
                lat, lon = full_latlons[idx]
                # ETA in seconds
                eta_seconds = cumdist[idx] / (speed_mps if speed_mps > 0 else 1.0)
                eta_hours = int(round(eta_seconds / 3600.0))

                params = {
                    'latitude': lat,
                    'longitude': lon,
                    'hourly': 'windspeed_10m,winddirection_10m,significant_wave_height',
                    'timezone': 'UTC',
                }
                try:
                    r = requests.get(self.open_meteo_url, params=params, timeout=8)
                    r.raise_for_status()
                    data = r.json()
                    hourly = data.get('hourly', {})
                    times = hourly.get('time') or []

                    # index into hourly arrays using eta_hours (relative to now hour)
                    if not times:
                        continue
                    # find nearest index: usually index = eta_hours (0 == now)
                    idx_hour = eta_hours
                    if idx_hour < 0:
                        idx_hour = 0
                    # clamp to available range
                    max_i = len(times) - 1
                    if idx_hour > max_i:
                        idx_hour = max_i

                    def pick(k):
                        arr = hourly.get(k)
                        if not arr:
                            return None
                        try:
                            return arr[idx_hour]
                        except Exception:
                            return None

                    w_ms = pick('windspeed_10m') or pick('windspeed') or pick('wind_speed')
                    w_dir = pick('winddirection_10m') or pick('winddirection') or pick('wind_dir')
                    wave = pick('significant_wave_height') or pick('wave_height') or pick('swh')

                    if w_ms is None:
                        continue
                    knots = float(w_ms) * 1.943844
                    winds_knots.append(knots)
                    wind_dirs.append(float(w_dir) if w_dir is not None else None)
                    if wave is not None:
                        try:
                            wave_heights.append(float(wave))
                        except Exception:
                            pass
                except Exception:
                    continue

            if not winds_knots:
                return 1.0, "Weather data unavailable for sampled points"

            # average wind & wave
            avg_knots = sum(winds_knots) / len(winds_knots)
            avg_wave = (sum(wave_heights) / len(wave_heights)) if wave_heights else 0.0

            # compute overall route heading from start to end
            try:
                lat0, lon0 = full_latlons[0]
                lat1, lon1 = full_latlons[-1]
                def bearing(a_lat, a_lon, b_lat, b_lon):
                    phi1 = math.radians(a_lat)
                    phi2 = math.radians(b_lat)
                    dlon = math.radians(b_lon - a_lon)
                    x = math.sin(dlon) * math.cos(phi2)
                    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlon)
                    br = (math.degrees(math.atan2(x, y)) + 360) % 360
                    return br
                route_heading = bearing(lat0, lon0, lat1, lon1)
            except Exception:
                route_heading = None

            # average wind direction
            wind_dirs_clean = [d for d in wind_dirs if d is not None]
            avg_wind_dir = (sum(wind_dirs_clean) / len(wind_dirs_clean)) if wind_dirs_clean else None

            headwind_knots = 0.0
            if avg_wind_dir is not None and route_heading is not None:
                wind_to = (avg_wind_dir + 180.0) % 360.0
                rel_ang = abs(((wind_to - route_heading + 180) % 360) - 180)
                comp = avg_knots * math.cos(math.radians(rel_ang))
                headwind_knots = max(0.0, -comp)

            # Ship-aware scaling
            try:
                avg_speed = float(avg_speed_knots)
            except Exception:
                avg_speed = 16.5

            # compute per-sample penalties and return them for visualization
            sample_records = []
            penalties = []
            for i, idx in enumerate(idxs):
                rowcol = path[idx] if idx < len(path) else (None, None)
                w_k = winds_knots[i] if i < len(winds_knots) else 0.0
                w_d = wind_dirs[i] if i < len(wind_dirs) else None
                wave_v = wave_heights[i] if i < len(wave_heights) else 0.0

                # per-sample headwind
                sample_headwind = 0.0
                if w_d is not None and route_heading is not None:
                    wind_to = (w_d + 180.0) % 360.0
                    rel_ang = abs(((wind_to - route_heading + 180) % 360) - 180)
                    comp = w_k * math.cos(math.radians(rel_ang))
                    sample_headwind = max(0.0, -comp)

                head_pen = sample_headwind * 0.02 * (16.5 / avg_speed)
                wave_pen = wave_v * 0.05 * (16.5 / avg_speed)
                pen = head_pen + wave_pen
                penalties.append(pen)

                sample_records.append({
                    'path_index': idx,
                    'grid_cell': rowcol,
                    'latlon': full_latlons[idx],
                    'eta_hours': int(round(cumdist[idx] / (speed_mps if speed_mps>0 else 1.0) / 3600.0)),
                    'wind_knots': w_k,
                    'wind_dir': w_d,
                    'wave_m': wave_v,
                    'headwind_knots': sample_headwind,
                    'penalty_fraction': pen,
                })

            avg_penalty = (sum(penalties) / len(penalties)) if penalties else 0.0
            total_multiplier = 1.0 + avg_penalty

            parts = [f"Avg wind: {avg_knots:.1f} kt"]
            if avg_wind_dir is not None:
                parts.append(f"wind_to: {avg_wind_dir + 180 if avg_wind_dir is not None else 'N/A'}°")
            if headwind_knots > 0:
                parts.append(f"headwind: {headwind_knots:.1f} kt")
            if avg_wave:
                parts.append(f"wave: {avg_wave:.2f} m")

            summary = "; ".join(parts) + f" -> time x {total_multiplier:.3f}"
            return total_multiplier, summary, sample_records
        winds_knots = []
        for lat, lon in latlons:
            try:
                params = {
                    'latitude': lat,
                    'longitude': lon,
                    'current_weather': True,
                }
                r = requests.get(self.open_meteo_url, params=params, timeout=5)
                r.raise_for_status()
                data = r.json()
                cw = data.get('current_weather') or {}
                w_m_s = cw.get('windspeed') or cw.get('windspeed_10m') or cw.get('wind_speed')
                w_dir = cw.get('winddirection') or cw.get('wind_dir') or cw.get('winddirection_10m')
                if w_m_s is None:
                    continue
                # Open-Meteo reports m/s; convert to knots
                knots = float(w_m_s) * 1.943844
                winds_knots.append(knots)
            except Exception:
                continue

        if not winds_knots:
            return 1.0, "Weather data unavailable for sampled points"

        avg_knots = sum(winds_knots) / len(winds_knots)

        # Ship-aware sensitivity: base sensitivity scaled by ship speed
        # Default sensitivity = 0.02 per knot above threshold
        sensitivity = 0.02
        # If a ship profile or estimator with attribute average_speed_knots is provided,
        # scale sensitivity so faster ships are slightly less affected.
        try:
            avg_speed = None
            if ship_profile is None:
                avg_speed = None
            elif isinstance(ship_profile, dict):
                avg_speed = ship_profile.get('average_speed_knots')
            else:
                avg_speed = getattr(ship_profile, 'average_speed_knots', None)

            if avg_speed and avg_speed > 0:
                sensitivity = 0.02 * (16.5 / float(avg_speed))
        except Exception:
            sensitivity = 0.02

        threshold = 10.0
        extra = max(0.0, avg_knots - threshold)
        multiplier = 1.0 + extra * sensitivity

        summary = f"Avg wind: {avg_knots:.1f} kt -> time x {multiplier:.3f}"
        return multiplier, summary
