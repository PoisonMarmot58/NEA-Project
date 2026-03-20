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
        # Allow overriding the Open-Meteo endpoint via environment; prefer a clearly
        # named variable to avoid accidentally using unrelated URLs.
        self.open_meteo_url = os.environ.get("OPEN_METEO_URL") or open_meteo_url
        # Simple in-memory cache for API responses to reduce duplicate calls
        self._cache = {}
        self._cache_limit = 2500
        # Build interpolators for pixel(row,col) -> lat & lon using control points
        # Create shared interpolators once and reuse across instances to avoid
        # repeated expensive construction when many estimator instances are used.
        if not hasattr(WeatherImpactEstimator, '_shared_interps_built'):
            try:
                cps = _CONTROL_POINTS
                pixels = [(c[2], c[3]) for c in cps]
                lats = [c[0] for c in cps]
                lons = [c[1] for c in cps]
                WeatherImpactEstimator._interp_lat = LinearNDInterpolator(pixels, lats)
                WeatherImpactEstimator._interp_lon = LinearNDInterpolator(pixels, lons)
            except Exception:
                WeatherImpactEstimator._interp_lat = None
                WeatherImpactEstimator._interp_lon = None
            WeatherImpactEstimator._shared_interps_built = True

        # Reuse a single HTTP session across estimator instances to avoid
        # repeatedly paying connection setup costs.
        if not hasattr(WeatherImpactEstimator, '_shared_session'):
            try:
                WeatherImpactEstimator._shared_session = requests.Session() if requests else None
            except Exception:
                WeatherImpactEstimator._shared_session = None

        # Instance views of shared interpolators
        self._interp_lat = WeatherImpactEstimator._interp_lat
        self._interp_lon = WeatherImpactEstimator._interp_lon

        # small cache for grid_to_latlon results to avoid repeated interpolation
        self._latlon_cache = {}

    def _cache_put(self, key, value):
        self._cache[key] = value
        if len(self._cache) > self._cache_limit:
            try:
                self._cache.pop(next(iter(self._cache)))
            except Exception:
                pass

    def _rounded_key(self, lat: float, lon: float, mode: str):
        return (round(float(lat), 3), round(float(lon), 3), mode)

    def _fetch_json(self, *, lat: float, lon: float, params: dict, timeout: int, mode: str):
        key = self._rounded_key(lat, lon, mode)
        if key in self._cache:
            return self._cache[key], key

        data = None
        try:
            client = getattr(WeatherImpactEstimator, '_shared_session', None) or requests
            r = client.get(self.open_meteo_url, params=params, timeout=timeout)
            r.raise_for_status()
            data = r.json()
        except Exception:
            data = None

        self._cache_put(key, data)
        return data, key

    def _current_weather_from_payload(self, payload):
        cw = (payload or {}).get('current_weather') or {}
        w_m_s = cw.get('windspeed') or cw.get('windspeed_10m') or cw.get('wind_speed')
        w_dir = cw.get('winddirection') or cw.get('wind_dir') or cw.get('winddirection_10m')
        return w_m_s, w_dir

    def grid_to_latlon(self, row: int, col: int) -> Tuple[float, float]:
        """Approximate lat,lon for a grid cell by inverting the linear mapping.

        We use a simple search over control point deltas: find the nearest
        control point and assume small linear offsets.
        """
        # Check small cache first
        key = (int(row), int(col))
        if key in self._latlon_cache:
            return self._latlon_cache[key]

        # Prefer interpolation from known control points
        try:
            if self._interp_lat is not None and self._interp_lon is not None:
                latv = self._interp_lat((row, col))
                lonv = self._interp_lon((row, col))
                # LinearNDInterpolator returns numpy scalar or array
                latv = np.asarray(latv).item()
                lonv = np.asarray(lonv).item()
                # If interpolation produced NaN (point outside convex hull), fall back
                if not np.isfinite(latv) or not np.isfinite(lonv):
                    raise ValueError("interpolator returned NaN")
                latv = float(latv)
                lonv = float(lonv)
                self._latlon_cache[key] = (latv, lonv)
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
        latf, lonf = float(lat), float(lon)
        self._latlon_cache[key] = (latf, lonf)
        return latf, lonf

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
    def _haversine_m(self, a: Tuple[float, float], b: Tuple[float, float]) -> float:
        lat1, lon1 = a
        lat2, lon2 = b
        R = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        x = math.sin(dphi/2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2) ** 2
        return 2 * R * math.asin(min(1, math.sqrt(x)))

    def _bearing_deg(self, a_lat, a_lon, b_lat, b_lon):
        phi1 = math.radians(a_lat)
        phi2 = math.radians(b_lat)
        dlon = math.radians(b_lon - a_lon)
        x = math.sin(dlon) * math.cos(phi2)
        y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlon)
        br = (math.degrees(math.atan2(x, y)) + 360) % 360
        return br

    def _sample_indices(self, n: int, max_samples: int = 5):
        if n <= max_samples:
            return list(range(n))
        idxs = [0]
        for i in range(1, max_samples - 1):
            idxs.append(int(round(i * (n - 1) / (max_samples - 1))))
        idxs.append(n - 1)
        return idxs

    def estimate_path_impact(self, path: List[Tuple[int, int]], ship_profile=None, detailed: bool = False):
        """Return (time_multiplier, summary) or (time_multiplier, summary, sample_records).

        - When `detailed` is False (default) use current-weather samples (fast).
        - When `detailed` is True query hourly forecasts and compute ETA-based samples
          returning per-sample records suitable for the UI.
        """
        if not path:
            return 1.0, "No path samples"

        if requests is None:
            return 1.0, "Weather unavailable (requests not installed)"

        # Simple mode: sample up to 5 waypoints and use 'current_weather'
        if not detailed:
            latlons = self.sample_path_points(path)
            if not latlons:
                return 1.0, "No path samples"

            winds_knots = []
            sampled_keys = set()
            for lat, lon in latlons:
                key = self._rounded_key(lat, lon, 'cw')
                if key in sampled_keys:
                    continue
                sampled_keys.add(key)
                try:
                    data, _ = self._fetch_json(
                        lat=lat,
                        lon=lon,
                        params={
                        'latitude': lat,
                        'longitude': lon,
                        'current_weather': True,
                        },
                        timeout=5,
                        mode='cw',
                    )
                    w_m_s, _w_dir = self._current_weather_from_payload(data)
                    if w_m_s is None:
                        continue
                    knots = float(w_m_s) * 1.943844
                    winds_knots.append(knots)
                except Exception:
                    continue

            if not winds_knots:
                return 1.0, "Weather data unavailable for sampled points"

            avg_knots = sum(winds_knots) / len(winds_knots)

            # Ship-aware sensitivity
            sensitivity = 0.02
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

        # Detailed mode: compute ETA-based hourly forecast samples and penalties
        from datetime import datetime

        # full lat/lon for every path cell
        full_latlons = [self.grid_to_latlon(r, c) for r, c in path]
        if not full_latlons:
            return 1.0, "No path samples"

        # determine ship speed
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

        # cumulative distance (meters)
        cumdist = [0.0]
        for i in range(1, len(full_latlons)):
            d = self._haversine_m(full_latlons[i-1], full_latlons[i])
            cumdist.append(cumdist[-1] + d)

        n = len(path)
        idxs = self._sample_indices(n, max_samples=5)
        # Prepare collectors and query hourly forecasts for each sample
        winds_knots = []
        wind_dirs = []
        wave_heights = []
        sample_records = []
        # Query hourly forecasts and pick the hour nearest each sample's ETA
        hourly_params_base = {
            'hourly': 'windspeed_10m,winddirection_10m,significant_wave_height',
            'timezone': 'UTC',
        }
        cw_params_base = {'current_weather': True}
        # Prefer nearby checks first. We first inspect cache for these offsets,
        # then only allow a bounded number of network tries.
        neighbour_offsets = [(0, 0)]
        for radius in (1, 2, 3):
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    if max(abs(dr), abs(dc)) != radius:
                        continue
                    neighbour_offsets.append((dr, dc))

        route_failed_hourly = set()
        for idx in idxs:
            lat, lon = full_latlons[idx]
            eta_seconds = cumdist[idx] / (speed_mps if speed_mps > 0 else 1.0)
            eta_hours = int(round(eta_seconds / 3600.0))

            key = self._rounded_key(lat, lon, 'hourly')
            data = None
            if key not in route_failed_hourly:
                data, key = self._fetch_json(
                    lat=lat,
                    lon=lon,
                    params={**hourly_params_base, 'latitude': lat, 'longitude': lon},
                    timeout=8,
                    mode='hourly',
                )

            if not data:
                route_failed_hourly.add(key)
                # Try nearby grid neighbours. Check cache first, then perform
                # a limited number of network requests for nearest candidates.
                found = False
                base_r, base_c = path[idx]
                neighbour_points = []
                for dr, dc in neighbour_offsets:
                    try:
                        lat2, lon2 = self.grid_to_latlon(base_r + dr, base_c + dc)
                    except Exception:
                        continue
                    neighbour_points.append((lat2, lon2))

                # First pass: cache-only lookup.
                for lat2, lon2 in neighbour_points:
                    k2 = self._rounded_key(lat2, lon2, 'hourly')
                    if k2 in route_failed_hourly:
                        continue
                    if k2 in self._cache and self._cache[k2]:
                        data = self._cache[k2]
                        found = True
                        lat = lat2
                        lon = lon2
                        key = k2
                        break

                # Second pass: bounded network queries for nearest points only.
                if not found:
                    network_checks = 0
                    max_network_checks = 12
                    for lat2, lon2 in neighbour_points:
                        k2 = self._rounded_key(lat2, lon2, 'hourly')
                        if k2 in route_failed_hourly or k2 in self._cache:
                            continue
                        data, k2 = self._fetch_json(
                            lat=lat2,
                            lon=lon2,
                            params={**hourly_params_base, 'latitude': lat2, 'longitude': lon2},
                            timeout=6,
                            mode='hourly',
                        )
                        network_checks += 1
                        if data:
                            found = True
                            lat = lat2
                            lon = lon2
                            key = k2
                            break
                        route_failed_hourly.add(k2)
                        if network_checks >= max_network_checks:
                            break

                # if grid-neighbour search failed, try small degree offset fallbacks
                if not found and not data:
                    for dlat, dlon in [(0.05, 0), (-0.05, 0), (0, 0.05), (0, -0.05)]:
                        lat2 = lat + dlat
                        lon2 = lon + dlon
                        k2 = self._rounded_key(lat2, lon2, 'hourly')
                        if k2 in route_failed_hourly:
                            continue
                        if k2 in self._cache:
                            data = self._cache[k2]
                        else:
                            data, k2 = self._fetch_json(
                                lat=lat2,
                                lon=lon2,
                                params={**hourly_params_base, 'latitude': lat2, 'longitude': lon2},
                                timeout=6,
                                mode='hourly',
                            )
                        if data:
                            found = True
                            lat = lat2
                            lon = lon2
                            key = k2
                            break
                        route_failed_hourly.add(k2)

                # final fallback to current_weather for original point
                if not found and not data:
                    try:
                        cwdata, _kcw = self._fetch_json(
                            lat=lat,
                            lon=lon,
                            params={**cw_params_base, 'latitude': lat, 'longitude': lon},
                            timeout=5,
                            mode='cw',
                        )
                        w_ms, w_dir = self._current_weather_from_payload(cwdata)
                        if w_ms is None:
                            continue
                        knots = float(w_ms) * 1.943844
                        winds_knots.append(knots)
                        wind_dirs.append(float(w_dir) if w_dir is not None else None)
                        sample_records.append({'path_index': idx, 'grid_cell': path[idx], 'latlon': (lat, lon), 'eta_hours': eta_hours, 'wind_knots': knots, 'wind_dir': float(w_dir) if w_dir is not None else None, 'wave_m': None})
                        continue
                    except Exception:
                        continue

            hourly = data.get('hourly', {})
            times = hourly.get('time') or []
            if not times:
                continue

            # choose index relative to now hour and clamp
            idx_hour = eta_hours
            if idx_hour < 0:
                idx_hour = 0
            max_i = len(times) - 1
            if idx_hour > max_i:
                idx_hour = max_i

            def pick_at(i, k):
                arr = hourly.get(k)
                if not arr:
                    return None
                try:
                    return arr[i]
                except Exception:
                    return None

            # search within a +/-3 hour window for first available wind value
            w_ms = None
            w_dir = None
            wave = None
            window = 3
            for offset in range(0, window + 1):
                for sign in (1, -1) if offset > 0 else (1,):
                    i = idx_hour + sign * offset
                    if i < 0 or i > max_i:
                        continue
                    w_ms = pick_at(i, 'windspeed_10m') or pick_at(i, 'windspeed') or pick_at(i, 'wind_speed')
                    w_dir = pick_at(i, 'winddirection_10m') or pick_at(i, 'winddirection') or pick_at(i, 'wind_dir')
                    wave = pick_at(i, 'significant_wave_height') or pick_at(i, 'wave_height') or pick_at(i, 'swh')
                    if w_ms is not None:
                        break
                if w_ms is not None:
                    break

            # if nothing in hourly window, fallback to current_weather (cached)
            if w_ms is None:
                try:
                    cwdata, _ = self._fetch_json(
                        lat=lat,
                        lon=lon,
                        params={**cw_params_base, 'latitude': lat, 'longitude': lon},
                        timeout=5,
                        mode='cw',
                    )
                    cw_w_ms, cw_w_dir = self._current_weather_from_payload(cwdata)
                    w_ms = cw_w_ms
                    w_dir = w_dir or cw_w_dir
                except Exception:
                    w_ms = None

            if w_ms is None:
                continue

            try:
                knots = float(w_ms) * 1.943844
            except Exception:
                continue
            winds_knots.append(knots)
            wind_dirs.append(float(w_dir) if w_dir is not None else None)
            if wave is not None:
                try:
                    wave_heights.append(float(wave))
                except Exception:
                    pass
            sample_records.append({'path_index': idx, 'grid_cell': path[idx], 'latlon': (lat, lon), 'eta_hours': eta_hours, 'wind_knots': knots, 'wind_dir': float(w_dir) if w_dir is not None else None, 'wave_m': float(wave) if wave is not None else None})

        # End of per-sample collection — compute summary and penalties
        if not winds_knots:
            return 1.0, "Weather data unavailable for sampled points"

        avg_knots = sum(winds_knots) / len(winds_knots)
        avg_wave = (sum(wave_heights) / len(wave_heights)) if wave_heights else 0.0

        # route heading
        try:
            lat0, lon0 = full_latlons[0]
            lat1, lon1 = full_latlons[-1]
            route_heading = self._bearing_deg(lat0, lon0, lat1, lon1)
        except Exception:
            route_heading = None

        # average wind direction for summary
        wind_dirs_clean = [d for d in wind_dirs if d is not None]
        avg_wind_dir = (sum(wind_dirs_clean) / len(wind_dirs_clean)) if wind_dirs_clean else None

        # compute per-sample penalties
        penalties = []
        for rec in sample_records:
            w_k = rec.get('wind_knots', 0.0)
            w_d = rec.get('wind_dir')
            wave_v = rec.get('wave_m') or 0.0

            sample_headwind = 0.0
            if w_d is not None and route_heading is not None:
                wind_to = (w_d + 180.0) % 360.0
                rel_ang = abs(((wind_to - route_heading + 180) % 360) - 180)
                comp = w_k * math.cos(math.radians(rel_ang))
                sample_headwind = max(0.0, -comp)

            head_pen = sample_headwind * 0.02 * (16.5 / (avg_speed_knots if avg_speed_knots > 0 else 16.5))
            wave_pen = wave_v * 0.05 * (16.5 / (avg_speed_knots if avg_speed_knots > 0 else 16.5))
            pen = head_pen + wave_pen
            penalties.append(pen)
            rec['headwind_knots'] = sample_headwind
            rec['penalty_fraction'] = pen

        avg_penalty = (sum(penalties) / len(penalties)) if penalties else 0.0
        total_multiplier = 1.0 + avg_penalty

        parts = [f"Avg wind: {avg_knots:.1f} kt"]
        if avg_wind_dir is not None:
            parts.append(f"wind_to: {avg_wind_dir + 180:.0f}°")
        if any(p.get('headwind_knots', 0.0) > 0 for p in sample_records):
            parts.append(f"headwind: {max(p.get('headwind_knots', 0.0) for p in sample_records):.1f} kt")
        if avg_wave:
            parts.append(f"wave: {avg_wave:.2f} m")

        summary = "; ".join(parts) + f" -> time x {total_multiplier:.3f}"
        return total_multiplier, summary, sample_records
