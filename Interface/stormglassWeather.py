import requests
import json
from datetime import datetime, timedelta



API_KEY = "4d848c4e-4486-11f0-976d-0242ac130006-4d848cda-4486-11f0-976d-0242ac130006"


def getWeatherData(latitude, longitude):
    url = 'https://api.stormglass.io/v2/weather/point'
    start = datetime.utcnow().isoformat()
    end = (datetime.utcnow() + timedelta(hours=24)).isoformat()

    params = {
    'lat': float(latitude), 
    'lng': float(longitude), 
    'params': ','.join(['windDirection', 'windSpeed', 'waveHeight', 'waveDirection', 'currentSpeed', 'currentDirection']),
    'start': start,
    'end': end,
    'source': 'sg'
}


    headers = {'Authorization': API_KEY}
        
    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None
    
data = getWeatherData(58.7984, 17.8081)
if data:
     print(json.dumps(data, indent=2))

