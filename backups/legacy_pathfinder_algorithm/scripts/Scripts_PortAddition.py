"""Scripts PortAddition module."""

import numpy as np
from scipy.interpolate import LinearNDInterpolator


control_points = np.array([
    [51.923,  4.479,  2001,  1950],   # Rotterdam
    [53.547,  9.987,  2214,  1895],   # Hamburg
    [37.942, 23.637,  3044,  2918],   # Piraeus
    [36.140, -5.435, 1298,  2918],   # Giv#braltar
    [38.72,  -9.14,   1145,   2806],   # Lisbon
    [60.17,  24.94,   1842,  1892],   # Felixstowe
    [39.445,  -0.320,  1624,  2835], # Valencia
    [44.410,  8.930,  2193,  2511], # Genoa
    [54.360,  18.645,  2615,  1723], # Gdansk)
])

# Lat and long pixel coords
lats_lons = control_points[:, :2]
pixels    = control_points[:, 2:]     # [row, col]

# Two interpolators
interp_row = LinearNDInterpolator(lats_lons, pixels[:, 0])
interp_col = LinearNDInterpolator(lats_lons, pixels[:, 1])

# list of ports to add
real_ports = [

    # Netherlands
    {"name": "Rotterdam",            "lat": 51.923,  "lon":  4.479}, 
    {"name": "Amsterdam",            "lat": 52.370,  "lon":  4.890},
    {"name": "Moerdijk",             "lat": 51.700,  "lon":  4.630},

    # Belgium
    {"name": "Antwerp-Bruges",       "lat": 51.260,  "lon":  4.400},  

    # Germany
    {"name": "Hamburg",              "lat": 53.547,  "lon":  9.987},
    {"name": "Bremerhaven",          "lat": 53.540,  "lon":  8.580},
    {"name": "Wilhelmshaven/JadeWeser", "lat": 53.515, "lon": 8.140},

    # Spain
    {"name": "Algeciras",            "lat": 36.140,  "lon": -5.435},   
    {"name": "Valencia",             "lat": 39.455,  "lon": -0.320},
    {"name": "Barcelona",            "lat": 41.350,  "lon":  2.150},
    {"name": "Bilbao",               "lat": 43.260,  "lon": -2.930},
    {"name": "Las Palmas (Canary)",  "lat": 28.140,  "lon": -15.420},

    # Italy
    {"name": "Trieste",              "lat": 45.650,  "lon": 13.770},
    {"name": "Genoa",                "lat": 44.410,  "lon":  8.930},
    {"name": "La Spezia",            "lat": 44.110,  "lon":  9.820},
    {"name": "Naples",               "lat": 40.840,  "lon": 14.250},

    # Greece
    {"name": "Piraeus",              "lat": 37.942,  "lon": 23.637}, 

    # United Kingdom
    {"name": "Felixstowe",           "lat": 51.963,  "lon":  1.351},  
    {"name": "Southampton",          "lat": 50.910,  "lon": -1.404},
    {"name": "London Gateway",       "lat": 51.500,  "lon":  0.460},
    {"name": "Liverpool (Peel Ports)", "lat": 53.400, "lon": -3.000},

    # France
    {"name": "Le Havre",             "lat": 49.490,  "lon":  0.107},
    {"name": "Marseille-Fos",        "lat": 43.380,  "lon":  5.040},
    {"name": "Dunkirk",              "lat": 51.030,  "lon":  2.370},

    # Poland
    {"name": "Gdansk",               "lat": 54.360,  "lon": 18.645},
    {"name": "Gdynia",               "lat": 54.520,  "lon": 18.530},

    # Portugal
    {"name": "Sines",                "lat": 37.950,  "lon": -8.890},
    {"name": "Lisbon",               "lat": 38.720,  "lon": -9.140},

    # Scandinavia / Baltic
    {"name": "Gothenburg",           "lat": 57.700,  "lon": 11.970},
    {"name": "Aarhus",               "lat": 56.150,  "lon": 10.210},
    {"name": "Copenhagen-Malmo",     "lat": 55.670,  "lon": 12.590},
    {"name": "Helsinki",             "lat": 60.170,  "lon": 24.940},
    {"name": "Klaipeda",             "lat": 55.710,  "lon": 21.130},

    # Other important
    {"name": "Constanta",            "lat": 44.170,  "lon": 28.650},
    {"name": "Izmir",                "lat": 38.420,  "lon": 27.140},
    {"name": "Koper",                "lat": 45.550,  "lon": 13.730},
    {"name": "Rijeka",               "lat": 45.330,  "lon": 14.440},

]

print("Approximated pixel positions for real ports:\n")
for port in real_ports:
    row_est = interp_row(port["lat"], port["lon"])
    col_est = interp_col(port["lat"], port["lon"])

    if np.isnan(row_est) or np.isnan(col_est):
        print(f"{port['name']:18} → OUTSIDE map area (bad interpolation)")
        continue

    row = int(np.round(row_est))
    col = int(np.round(col_est))

    print(f"{port['name']:18} → row {row:4d}, col {col:4d}")
