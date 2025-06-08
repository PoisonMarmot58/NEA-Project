from dotenv import load_dotenv
from pprint import pprint
import requests
import os
import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry

#this is open meteos own exception handling - may change
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)


load_dotenv()

#subroutine to get the weather for the specific coordinates
def get_specific_weather(latitude = '53.405439', longitude = '3.53827'):
    url = "https://marine-api.open-meteo.com/v1/marine"
    params = {
        'latitude': latitude,
        'longitude': longitude, 
        'daily': ["wind_speed_10m_max", "wind_direction_10m_dominant"]  #change to whatever parameters needed
    }
    response = openmeteo.weather_api(url, params=params)

    return response
