"""Bộ săn tin: quét nguồn tin nhanh (fxtin) ~60 giây/lần, lọc 2 tầng, tin đủ mạnh thì viết + đăng bài TIN NÓNG.

Tầng 1 (quy tắc, không tốn AI): tin số liệu từ 2 sao, tin gắn cờ quan trọng, chứa từ khoá lớn.
Tầng 2 (AI): gom tin ứng viên, chấm điểm ảnh hưởng 0-10, chỉ tin ≥ 7 điểm thành bài.
Chống spam: cách nhau ≥ 30 phút, tối đa N bài/ngày; tin số liệu 3 sao trở lên xử lý ngay, tin khác gom 5 phút.

    JOB=cwg-vn python -m src.hunter --once        # quét 1 lần (thử)
"""
import argparse
import json
import re
import time
import traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from src.config import CONFIG, IS_DEFAULT_JOB, OUTPUT, STATE, TZ
from src.publish import facebook, telegram

CFG = CONFIG.get("hunter") or {}
FILE = STATE / "hunter.json"
URL = "https://www.fxtin.com/page/finance/information"
HEAD = {"User-Agent": "Mozilla/5.0", "Origin": "https://fxtin.com", "Referer": "https://fxtin.com/"}
KEYWORDS = re.compile(r"Fed|FOMC|Powell|ECB|Lagarde|BoJ|BOJ|Ueda|BoE|BOE|Bailey|RBA|BoC|PBOC|lãi suất|thuế quan|OPEC|"
                      r"chiến tranh|tấn công|lệnh trừng phạt|đình chiến|CPI|PCE|phi nông nghiệp|NFP|GDP|lạm phát|"
                      r"vàng|dầu|Brent|WTI|USD|đồng đô la|lợi suất|Trump|Nhà Trắng|khẩn cấp", re.I)


def _load() -> dict:
    d = json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
    d.setdefault("seen", [])
    d.setdefault("pending", [])
    d.setdefault("posts", {})
    d.setdefault("last_post", "")
    d.setdefault("fail", 0)
    return d


def _save(d: dict):
    d["seen"] = d["seen"][-600:]
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


ARCHIVE = STATE / "hunter_archive.json"


def _archive(items: list):
    """Kho tin quan trọng 9 ngày gần nhất – dùng cho bài 'Top 5 tin của tuần' thứ 7."""
    if not items:
        return
    arch = json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else []
    cut = (datetime.now(TZ) - timedelta(days=9)).isoformat()
    arch = [x for x in arch if x["at"] >= cut] + items
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVE.write_text(json.dumps(arch, ensure_ascii=False), encoding="utf-8")


def active(now: datetime) -> bool:
    """Săn tin cả tuần; cuối tuần (thứ 7 04:00 → thứ 2 05:00) chỉ nhận tin cực lớn (xem weekend())."""
    return True


def weekend(now: datetime) -> bool:
    wd, h = now.weekday(), now.hour
    return (wd == 5 and h >= 4) or wd == 6 or (wd == 0 and h < 5)


def fetch() -> list[dict]:
    r = requests.post(URL, json={"limit": 40, "page": 1}, headers=HEAD, timeout=20)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != 200:                 # vd. "访问过于频繁" = truy cập quá thường xuyên → coi là lỗi, không phải "hết tin"
        raise RuntimeError(f"nguồn tin từ chối: {j.get('msg')}")
    out = []
    for x in (j.get("data") or {}).get("list") or []:
        t = datetime.fromisoformat(x["pub_time_tz"]).replace(tzinfo=ZoneInfo("Asia/Bangkok")).astimezone(TZ)
        out.append({"id": str(x["id"]), "at": t.isoformat(), "time": t.strftime("%H:%M"), "text": x["translate"],
                    "important": x["important"] != "0", "star": int(x["star"] or 0), "actual": x["actual"],
                    "forecast": x["consensus"], "previous": x["previous"]})
    return out


def tier1(x: dict) -> bool:
    if x["star"] >= 2:
        return True
    return x["important"] and bool(KEYWORDS.search(x["text"]))


def tick(dry_run: bool | None = None) -> str:
    """Một lượt quét. Trả về mô tả ngắn để ghi log."""
    now = datetime.now(TZ)
    if not active(now):
        return "ngoài giờ thị trường"
    if dry_run is None:
        dry_run = not (CONFIG.get("autopost") or {}).get("live", False)
    d = _load()
    try:
        items = fetch()
        if d["fail"] >= 5:
            telegram.send("✅ Bộ săn tin đã kết nối lại nguồn tin nhanh.")
        d["fail"] = 0
    except Exception as exc:
        d["fail"] += 1
        if d["fail"] == 5:                     # ~5 phút liên tục không lấy được tin
            telegram.send(f"⚠️ Bộ săn tin không lấy được nguồn tin nhanh ({type(exc).__name__}). "
                          "🔧 Hệ thống tự thử lại mỗi phút; các bài theo lịch vẫn chạy bình thường.")
        if d["fail"] == 60:
            telegram.need_fix("❌ Bộ săn tin mất nguồn tin nhanh fxtin hơn 1 giờ (có thể bị chặn).")
        _save(d)
        return f"lỗi nguồn tin ({exc})"

    new = [x for x in items if x["id"] not in d["seen"]]
    d["seen"] += [x["id"] for x in new]
    _archive([x for x in new if tier1(x)])
    cutoff = now - timedelta(minutes=40)
    fresh = [x for x in new if datetime.fromisoformat(x["at"]) >= cutoff]
    d["pending"] = [x for x in d["pending"] if datetime.fromisoformat(x["at"]) >= cutoff] + [x for x in fresh if tier1(x)]

    msg = f"{len(new)} tin mới, {len(d['pending'])} ứng viên"
    if not d["pending"]:
        _save(d)
        return msg
    urgent = any(x["star"] >= 3 for x in d["pending"])
    oldest = min(datetime.fromisoformat(x["at"]) for x in d["pending"])
    if not urgent and now - oldest < timedelta(minutes=CFG.get("batch_minutes", 5)):
        _save(d)
        return msg + " (chờ gom)"

    today = now.strftime("%Y-%m-%d")
    done_today = d["posts"].get(today, 0)
    wk = weekend(now)
    cap = CFG.get("weekend_max_per_day", 2) if wk else CFG.get("max_per_day", 4)
    last = datetime.fromisoformat(d["last_post"]) if d["last_post"] else None
    gap = timedelta(minutes=CFG.get("min_gap_minutes", 30))
    if done_today >= cap or (last and now - last < gap and not urgent):
        d["pending"] = [] if done_today >= cap else d["pending"]
        _save(d)
        return msg + " (giới hạn tần suất)"

    from src.content import cwg_daily
    cand, d["pending"] = d["pending"], []
    _save(d)
    need = CFG.get("weekend_min_score", 8) if wk else 7
    groups = cwg_daily.pick_breaking(cand, n=1, min_score=need)
    if not groups:
        return msg + f" → không tin nào đủ {need} điểm"
    group = groups[0]
    folder = OUTPUT / now.strftime("%Y-%m-%d") / f"breaking_{now:%H%M}"
    folder.mkdir(parents=True, exist_ok=True)
    snap = cwg_daily.snapshot()
    if ((CONFIG.get("hunter") or {}).get("style")) == "editorial":    # Page DecodeFx Trading: khuôn mẫu 12
        from src.content import trading_daily
        p = trading_daily.post_breaking(now.date(), group, snap, folder)
    else:
        p = cwg_daily.post_breaking(now.date(), group, snap, folder)
    (folder / "caption.txt").write_text(p["caption"], encoding="utf-8")
    title = f"⚡ Tin nóng {now:%H:%M %d/%m}"
    if dry_run:
        telegram.send_preview(f"🧪 [XEM TRƯỚC - chưa đăng] {title}", p["caption"], p["images"])
        link = "preview"
    else:
        link, post_id = facebook.publish(p["caption"], p["images"])
        from src.runner import mark_posted
        mark_posted("cwg_breaking", now, link, post_id, {"news": [x["text"][:120] for x in group]})
        telegram.send(f"✅ Đã hoàn thành: {title}\n🔗 Link bài viết: {link}\nAnh kiểm tra nếu cần sửa đổi.")
    d = _load()
    d["posts"][today] = done_today + 1
    d["posts"] = dict(sorted(d["posts"].items())[-10:])
    d["last_post"] = now.isoformat()
    _save(d)
    return msg + f" → ĐÃ {'gửi xem trước' if dry_run else 'đăng'} tin nóng: {link}"


def run_forever(stop_at: datetime, interval: int = 60):
    """Chạy trong luồng riêng của bộ điều phối."""
    while datetime.now(TZ) < stop_at:
        try:
            print(f"[săn tin {datetime.now(TZ):%H:%M:%S}] {tick()}", flush=True)
        except Exception:
            traceback.print_exc()
        time.sleep(interval)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if IS_DEFAULT_JOB:
        raise SystemExit("Bộ săn tin chạy cho Job thương hiệu (vd. JOB=cwg-vn)")
    print(tick(True if a.dry_run else None))
