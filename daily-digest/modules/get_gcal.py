import os, json, requests, pytz
from datetime import datetime, timedelta
from ics import Calendar
from dotenv import load_dotenv

load_dotenv()

urls = json.loads(os.getenv("CALENDARS", "{}"))
calendars = {}

def run():
    for name in urls.keys():
        ICS_URL = urls[name]
        LOCAL_TZ = pytz.timezone("America/Toronto")  # Change to your local timezone

        r = requests.get(ICS_URL, timeout=10)
        r.raise_for_status()

        cal = Calendar(r.text)
        now = datetime.now(LOCAL_TZ)
        soon = now + timedelta(days=30)

        events = []
        for e in cal.events:
            start = getattr(e.begin, "datetime", e.begin)
            end = getattr(e.end, "datetime", e.end)

            if start:
                if not start.tzinfo:
                    start = LOCAL_TZ.localize(start)
                else:
                    start = start.astimezone(LOCAL_TZ)

            if end:
                if not end.tzinfo:
                    end = LOCAL_TZ.localize(end)
                else:
                    end = end.astimezone(LOCAL_TZ)

            if start and now <= start <= soon:
                events.append({
                    "title": e.name,
                    "start": start.strftime("%A %B %d %Y, %-I:%M%p"),
                    "end": end.strftime("%A %B %d %Y, %-I:%M%p") if end else None,
                })
        calendars[name] = events

    return calendars
