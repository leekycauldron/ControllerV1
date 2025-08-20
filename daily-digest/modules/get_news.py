# pip install feedparser python-dateutil
from typing import Iterable, List, Dict, Optional
import feedparser
from datetime import datetime, timezone
from dateutil import tz
import html
import re
from urllib.parse import urlparse
import os
from dotenv import load_dotenv


load_dotenv()

LOCAL_TZ = tz.gettz("America/Toronto")
USER_AGENT = "PersonalAlarmNewsBot/0.1 (+you@example.com)"

var = os.getenv("NEWS_FEEDS", "")
FEEDS = var.split(",") if var else []

def _strip_html(s: str) -> str:
    if not s:
        return ""
    s = html.unescape(s)
    return re.sub(r"<[^>]+>", "", s).strip()

def _fmt_time_struct(t) -> Optional[datetime]:
    """Convert feedparser time struct to localized datetime."""
    if not t:
        return None
    dt = datetime(*t[:6], tzinfo=timezone.utc)
    return dt.astimezone(LOCAL_TZ)

def fetch_feed(url: str, limit: int = 10) -> List[Dict]:
    """Fetch a single RSS/Atom feed and return normalized article dicts."""
    fp = feedparser.parse(url, request_headers={"User-Agent": USER_AGENT})
    if getattr(fp, "bozo", False) and not fp.entries:
        # Failed parse or empty; return nothing but don’t crash your pipeline
        return []

    out = []
    source_title = (fp.feed.get("title") or urlparse(url).netloc).strip()

    for e in fp.entries[: max(1, limit)]:
        published_dt = _fmt_time_struct(e.get("published_parsed") or e.get("updated_parsed"))
        out.append({
            "source": source_title,
            "title": e.get("title", "").strip(),
            "link": e.get("link", "").strip(),
            "summary": _strip_html(e.get("summary") or e.get("description") or ""),
            "published": published_dt.isoformat() if published_dt else None,
            "published_human": published_dt.strftime("%a %b %d, %I:%M %p") if published_dt else "—",
        })
    return out

def aggregate_feeds(feeds: Iterable[str], per_feed: int = 5, total_cap: Optional[int] = 50,
                    dedupe: bool = True) -> List[Dict]:
    """Fetch many feeds, optionally dedupe by (title, link) and cap total."""
    seen = set()
    all_items: List[Dict] = []
    for url in feeds:
        items = fetch_feed(url, limit=per_feed)
        for it in items:
            key = (it["title"], it["link"])
            if not dedupe or key not in seen:
                seen.add(key)
                all_items.append(it)

    # Sort newest first if we have timestamps
    all_items.sort(key=lambda x: x["published"] or "", reverse=True)
    return all_items[: total_cap] if total_cap else all_items

def format_bullets(items: List[Dict]) -> str:
    """Pretty text list you can send to your phone or TTS."""
    lines = []
    for it in items:
        lines.append(f"• {it['title']} — {it['source']} ({it['published_human']})\n  {it['link']}\n {it['summary']}")
    return "\n".join(lines)

def run():
    articles = aggregate_feeds(FEEDS, per_feed=3, total_cap=100)
    #print(articles)
    return format_bullets(articles)

if __name__ == "__main__":
    print(run())
