"""Lịch kinh tế từ feed JSON miễn phí của ForexFactory (faireconomy.media)."""
import json
from datetime import datetime, timedelta

import requests

from src.config import CONFIG, ROOT, TZ

FEED_URL = "https://nfs.faireconomy.media/ff_calendar_{which}.json"


CACHE_DIR = ROOT / "state"
CACHE_TTL = timedelta(hours=1)


def fetch_week(which: str = "thisweek") -> list[dict]:
    """which: thisweek | nextweek. Feed giới hạn số lần gọi, nên lưu đệm 1 giờ; nếu feed lỗi thì dùng bản đệm cũ."""
    CACHE = CACHE_DIR / ("calendar_week.json" if which == "thisweek" else f"calendar_{which}.json")
    if CACHE.exists() and datetime.now() - datetime.fromtimestamp(CACHE.stat().st_mtime) < CACHE_TTL:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    try:
        resp = requests.get(FEED_URL.format(which=which), timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        if CACHE.exists():
            print(f"  ! Lịch kinh tế lỗi ({exc}), dùng bản lưu đệm")
            return json.loads(CACHE.read_text(encoding="utf-8"))
        raise
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def events_for_session(now: datetime) -> list[dict]:
    """Tin trong 'ngày giao dịch' tính theo giờ VN: từ bây giờ đến 06:00 sáng hôm sau.

    Khung này bao trọn phiên Á, Âu và Mỹ (tin Mỹ ra buổi tối/đêm giờ VN).
    """
    cfg = CONFIG["calendar"]
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1, hours=6)

    events = []
    for e in fetch_week():
        if e.get("country") not in cfg["currencies"] or e.get("impact") not in cfg["impacts"]:
            continue
        try:
            when = datetime.fromisoformat(e["date"]).astimezone(TZ)
        except (KeyError, ValueError):
            continue
        if not (start <= when < end):
            continue
        events.append({
            "time": when.strftime("%H:%M"),
            "datetime": when.isoformat(),
            "currency": e["country"],
            "impact": e["impact"],
            "title": e["title"],
            "forecast": e.get("forecast") or "",
            "previous": e.get("previous") or "",
        })
    events.sort(key=lambda x: x["datetime"])
    return events
