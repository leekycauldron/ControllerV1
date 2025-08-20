import requests
import copy
from typing import Any, Dict
from dotenv import load_dotenv
import os
from datetime import datetime
import pytz

load_dotenv()

def truncate_hourly(data: Dict[str, Any], x: int) -> Dict[str, Any]:
    """
    Return a deep-copied JSON-like dict where 'hourly' is truncated to x items.
    All other fields (current, daily, minutely, alerts, etc.) are preserved as-is.
    If 'hourly' is missing or not a list, the object is returned unchanged.

    - Negative x -> empty hourly list.
    - x >= len(hourly) -> unchanged hourly.
    """
    out = copy.deepcopy(data)
    hourly = out.get("hourly")
    if isinstance(hourly, list):
        out["hourly"] = hourly[:max(0, int(x))]
    return out

def format_weather(data: dict) -> str:
    tz = pytz.timezone(data.get("timezone", "UTC"))

    # --- Current Weather ---
    curr = data["current"]
    curr_temp_c = round(curr["temp"] - 273.15, 1)
    curr_wind = f"{curr['wind_speed']} m/s"
    curr_weather = curr["weather"][0]["description"].capitalize()
    curr_str = f"Current Weather: {curr_temp_c}°C, {curr_wind}, {curr_weather}"

    # --- Hourly Forecast ---
    hourly_parts = []
    for hour in data.get("hourly", []):
        dt = datetime.fromtimestamp(hour["dt"], tz)
        time_str = dt.strftime("%H:%M")
        temp_c = round(hour["temp"] - 273.15, 1)
        wind = f"{hour['wind_speed']} m/s"
        weather = hour["weather"][0]["description"].capitalize()
        hourly_parts.append(f"{time_str} {temp_c}°C, {wind}, {weather}")

    hourly_str = "Hourly:\n" + "\n".join(hourly_parts)

    return f"{curr_str}\n{hourly_str}"

url = f"https://api.openweathermap.org/data/3.0/onecall?lat={os.getenv('LATITUDE')}&lon={os.getenv('LONGITUDE')}&exclude=minutely,daily&appid={os.getenv('OPENWEATHER_API_KEY')}"

def run():
    payload = {}
    headers = {}

    response = requests.request("GET", url, headers=headers, data=payload)

    # Parse the JSON response and truncate hourly data to 6 items
    weather_data = response.json()
    truncated_data = truncate_hourly(weather_data, 12)

    return format_weather(truncated_data)

if __name__ == "__main__":
    print(run())
