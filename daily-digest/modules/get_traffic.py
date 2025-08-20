# pip install requests python-dateutil
import os, requests, time
from typing import Union, Tuple, Dict, Any
from datetime import datetime, timezone
from dateutil import tz
from dotenv import load_dotenv

load_dotenv()

def _normalize_place(p: Union[str, Tuple[float, float]]) -> str:
    """Accepts '1600 Amphitheatre Pkwy, Mountain View' or (lat, lon)."""
    if isinstance(p, (tuple, list)) and len(p) == 2:
        lat, lon = p
        return f"{lat},{lon}"
    return str(p)

def google_distance_matrix(
    origin: Union[str, Tuple[float, float]],
    destination: Union[str, Tuple[float, float]],
    mode: str = "driving",
    departure: Union[str, datetime, None] = None,  # None, "now" or datetime
    units: str = "metric",
    transit_mode: str = None,                # e.g., "subway|train"
    api_key: str = None,
    region: str = "ca",
) -> Dict[str, Any]:
    """
    Returns dict with distance (m, text), duration (s, text), and
    duration_in_traffic (if driving with departure) from Google Distance Matrix.
    """
    api_key = api_key or os.getenv("GMAPS_API_KEY")
    if not api_key:
        raise ValueError("Set GMAPS_API_KEY in env or pass api_key=")

    if isinstance(departure, datetime):
        # Google expects seconds since epoch (UTC)
        departure = int(departure.replace(tzinfo=timezone.utc).timestamp())

    params = {
        "origins": _normalize_place(origin),
        "destinations": _normalize_place(destination),
        "mode": mode,
        "units": units,
        "key": api_key,
        "region": region,
    }
    if departure is not None:
        params["departureTime"] = departure  # "now" or epoch seconds
    if mode == "transit" and transit_mode:
        params["transit_mode"] = transit_mode

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    if data.get("status") != "OK":
        raise RuntimeError(f"API error: {data.get('status')} - {data.get('error_message')}")

    elem = data["rows"][0]["elements"][0]
    if elem.get("status") != "OK":
        raise RuntimeError(f"Route error: {elem.get('status')}")

    out = {
        "origin": data["origin_addresses"][0],
        "destination": data["destination_addresses"][0],
        "distance_m": elem["distance"]["value"],
        "distance_text": elem["distance"]["text"],
        "duration_s": elem["duration"]["value"],
        "duration_text": elem["duration"]["text"],
    }
    if "duration_in_traffic" in elem:
        out["duration_in_traffic_s"] = elem["duration_in_traffic"]["value"]
        out["duration_in_traffic_text"] = elem["duration_in_traffic"]["text"]
    return out

# --- Examples ---
def run(departure_time):
    # Driving with live traffic (Toronto time now)
    tor_tz = tz.gettz("America/Toronto")

    res_drive = google_distance_matrix(
        origin=os.getenv("TRAFFIC_ORIGIN"),
        destination=os.getenv("TRAFFIC_DESTINATION"),
        mode="driving",
        departure=departure_time,  # or now_local
        units="metric",
    )
    return res_drive.get("duration_in_traffic_text", res_drive['duration_text'])
