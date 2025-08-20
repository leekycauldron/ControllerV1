from modules import get_weather, get_gcal, get_news, get_traffic, summarize, podcaster
from datetime import datetime, timedelta
from config_crontab import *
import pytz

#TODO: Adjust calendar range to be day only (its big now for testing)


def _parse_event_start(s: str, local_tz):
    # Try ISO 8601 first
    try:
        iso = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        return dt if dt.tzinfo else local_tz.localize(dt)
    except Exception:
        pass

    # Fallback to pretty formats
    for fmt in (
        "%A %B %d %Y, %-I:%M%p",  # Unix-style hour without leading zero
        "%A %B %d %Y, %#I:%M%p",  # Windows-style hour without leading zero
        "%A %B %d %Y, %I:%M%p",   # Accept 01:00PM as well
    ):
        try:
            dt_naive = datetime.strptime(s, fmt)
            return local_tz.localize(dt_naive)
        except Exception:
            continue

    raise ValueError(f"Unrecognized datetime format: {s!r}")

def get_departure_time(data, local_tz_str: str = "America/Toronto"):
    local_tz = pytz.timezone(local_tz_str)

    if not data or not data[0].get("start"):
        return datetime.now(local_tz)

    start_str = data[0]["start"]
    start_dt = _parse_event_start(start_str, local_tz)

    # Subtract 1 hour
    return start_dt - timedelta(hours=1)

demo = False
if __name__ == "__main__":
    if not demo:
        # Set Alarm to 10 minutes from now.
        new_time = datetime.now() + timedelta(minutes=10)
        new_time = new_time.replace(second=0, microsecond=0)

        new_h, new_m = change_task_time(
            new_time,
            script_name="/home/bryson/code_projects/ControllerV1/daily-digest/entry_wakeup.py",
        )

        print(f"Updated schedule for wakeup.py: {new_h:02d}:{new_m:02d}")
    out_string = ""
    out_string += "Current Time: "+datetime.now().strftime("%A %B %d %Y, %-I:%M%p")+"\n"
    out_string += "Weather: "+ str(get_weather.run())+"\n"
    calendars = get_gcal.run()
    out_string += "Calendars: "+ str(calendars)+"\n"
    departure_time = get_departure_time(calendars.get('classes',[]))
    out_string+="Time to GO Station: "+str(get_traffic.run(departure_time=departure_time))+"\n"
    out_string+="News: "+str(get_news.run())
    summary = summarize.run(out_string)
    print(out_string)
    print(summary)
    print(podcaster.run(summary))