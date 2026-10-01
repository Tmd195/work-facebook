"""Bộ điều phối: tạo bài → chờ đúng giờ → đăng Facebook → báo Telegram. Tự thử lại & báo từng bước khi lỗi.

    python -m src.runner morning              # chạy thật (đăng bài)
    python -m src.runner knowledge --dry-run  # tạo bài + báo Telegram, KHÔNG đăng
    python -m src.runner strategy_us --now    # không chờ giờ đăng
"""
import argparse
import sys
import time
import traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.config import CONFIG, OUTPUT, TZ
from src.publish import facebook, telegram

NY = ZoneInfo("America/New_York")
MAX_EARLY = timedelta(minutes=45)       # chạy sớm hơn giờ đăng quá mức này thì bỏ (cron mùa hè/đông trùng nhau)


# ===================================================================== giờ đăng

def target_time(job: str, now: datetime) -> datetime:
    sched = CONFIG["schedule"]
    hm = lambda s: now.replace(hour=int(s[:2]), minute=int(s[3:]), second=0, microsecond=0)
    if job == "strategy_us":
        # 1 tiếng trước giờ mở cửa New York 08:30 (tự theo giờ mùa hè/đông)
        ny_open = datetime(now.year, now.month, now.day, 8, 30, tzinfo=NY).astimezone(TZ)
        return ny_open - timedelta(hours=1)
    if job == "knowledge":
        slots = [hm(t) for t in sched["knowledge"]["times"]]
        return min(slots, key=lambda t: abs((t - now).total_seconds()))
    return hm(sched[job]["time"])


def wait_until(t: datetime):
    while (left := (t - datetime.now(TZ)).total_seconds()) > 0:
        time.sleep(min(left, 30))


# ===================================================================== chống đăng trùng

POSTED = OUTPUT.parent / "state" / "posted.json"


def _slot(job: str, target: datetime) -> str:
    return f"{target:%Y-%m-%d} {job} {target:%H:%M}"


def load_posted() -> dict:
    import json
    return json.loads(POSTED.read_text(encoding="utf-8")) if POSTED.exists() else {}


def already_posted(job: str, target: datetime) -> bool:
    entry = load_posted().get(_slot(job, target))
    return bool(entry) and not (isinstance(entry, dict) and entry.get("preview"))


def post_meta(job: str, out_dir) -> dict:
    """Dữ liệu cần cho các comment theo dõi sau này (output/ không được lưu giữa các lần chạy)."""
    import json
    if job == "morning":
        ctx = json.loads((out_dir / "morning.json").read_text(encoding="utf-8"))["context"]
        return {"events": ctx["calendar"]}
    if job == "knowledge":
        meta = json.loads((out_dir / "knowledge.json").read_text(encoding="utf-8"))
        return {"series": meta["series"], "part": meta["part"]}
    s = job.split("_")[1]
    d = json.loads((out_dir / f"strategy_{s}.json").read_text(encoding="utf-8"))
    return {"session": s, "scenarios": d["result"]["scenarios"], "price": d["data"]["giá_hiện_tại"],
            "title": d["result"]["title"]}


def mark_posted(job: str, target: datetime, link: str, post_id: str | None = None, meta: dict | None = None,
                preview: bool = False):
    import json
    data = load_posted()
    data[_slot(job, target)] = {"job": job, "link": link, "post_id": post_id, "posted_at": datetime.now(TZ).isoformat(),
                                "preview": preview, "meta": meta or {}}
    keep = sorted(data)[-200:]                     # giữ 200 bài gần nhất
    POSTED.parent.mkdir(parents=True, exist_ok=True)
    POSTED.write_text(json.dumps({k: data[k] for k in keep}, ensure_ascii=False, indent=1), encoding="utf-8")


# ===================================================================== tạo bài

def _files(job: str, out_dir):
    if job == "morning":
        return out_dir / "morning.txt", [out_dir / "morning.png"]
    if job == "knowledge":
        return out_dir / "knowledge.txt", sorted(out_dir.glob("knowledge_[0-9][0-9].png"))
    s = job.split("_")[1]
    return out_dir / f"strategy_{s}.txt", sorted(out_dir.glob(f"strategy_{s}_[0-9][0-9].png"))


def generate(job: str):
    import run
    if job == "morning":
        return run.run_morning()
    if job == "knowledge":
        return run.run_knowledge()
    return run.run_strategy(job.split("_")[1])


def label(job: str) -> str:
    if job == "knowledge":
        from src.content import knowledge
        nxt = knowledge.next_lesson()
        return f"Kiến thức: {nxt[0]['name']} – Phần {nxt[1]['part']}/{len(nxt[0]['lessons'])}" if nxt else "Kiến thức"
    return {"morning": "Bản tin sáng", "strategy_ae": "Chiến lược XAUUSD phiên Á – Âu",
            "strategy_us": "Chiến lược XAUUSD phiên Mỹ"}[job]


# ===================================================================== chạy 1 việc

def run_job(job: str, dry_run: bool = False, no_wait: bool = False, attempts: int = 3) -> bool:
    if not (CONFIG.get("autopost") or {}).get("live", False):
        dry_run = True                       # công tắc an toàn: chưa bật đăng thật
    now = datetime.now(TZ)
    day = now.strftime("%d/%m")
    target = target_time(job, now)
    if not no_wait and target - now > MAX_EARLY:
        print(f"Bỏ qua: giờ đăng {target:%H:%M}, còn quá sớm (lịch chạy của mùa khác)")
        return True
    if not no_wait and now - target > timedelta(hours=2):
        print(f"Bỏ qua: đã quá giờ đăng {target:%H:%M} hơn 2 tiếng")
        return True
    if not dry_run and already_posted(job, target):
        print(f"Bỏ qua: {job} {target:%H:%M} hôm nay đã đăng rồi")
        return True
    name = label(job)
    out_dir = OUTPUT / now.strftime("%Y-%m-%d")
    had_error = False

    # --- 1. Tạo bài (thử lại tối đa `attempts` lần)
    for k in range(1, attempts + 1):
        err = None
        try:
            if generate(job):
                break
            err = "không tạo được nội dung (AI hoặc dữ liệu không đạt kiểm tra)"
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
        had_error = True
        if k == 1:
            telegram.send(f"⚠️ {name} {day} lỗi:\n{err}")
        if k < attempts:
            telegram.send(f"🔧 Đang sửa lỗi: thử lại lần {k + 1}/{attempts} (đổi nguồn dữ liệu dự phòng, cho AI viết lại)...")
            time.sleep(60 * k)
    else:
        telegram.send(f"❌ {name} {day} KHÔNG hoàn thành sau {attempts} lần thử.\n"
                      f"Lỗi cuối: {err}\nBài này sẽ không được đăng. Em cần anh kiểm tra giúp.")
        return False
    if had_error:
        telegram.send("✅ Đã sửa xong lỗi, tiếp tục đăng bài.")

    caption_file, images = _files(job, out_dir)
    caption = caption_file.read_text(encoding="utf-8")

    # --- 2. Chờ đúng giờ rồi đăng
    if not no_wait and not dry_run:
        wait_until(target)
    meta = post_meta(job, out_dir)
    if dry_run:
        telegram.send_preview(f"🧪 [XEM TRƯỚC - chưa đăng] {name} {day}\n{len(images)} ảnh · bài đầy đủ bên dưới. "
                              f"Anh duyệt, nếu ổn nhắn em bật đăng thật.", caption, images)
        if not already_posted(job, target):
            mark_posted(job, target, "preview", None, meta, preview=True)
        return True
    try:
        link, post_id = facebook.publish(caption, images)
    except facebook.FacebookError as exc:
        hint = ("\n👉 Token Facebook hết hạn hoặc thiếu quyền - cần anh lấy lại token theo hướng dẫn."
                if exc.needs_user else "")
        telegram.send(f"❌ {name} {day}: đăng Facebook thất bại.\n{exc}{hint}")
        return False

    mark_posted(job, target, link, post_id, meta)
    if job == "knowledge":
        import json
        from src.content import knowledge
        meta = json.loads((out_dir / "knowledge.json").read_text(encoding="utf-8"))
        series = next(s for s in knowledge.load_series() if s["id"] == meta["series"])
        knowledge.mark_done(series, series["lessons"][meta["part"] - 1])

    telegram.send(f"✅ Đã hoàn thành: {name} {day}\n🔗 Link bài viết: {link}\nAnh kiểm tra nếu cần sửa đổi.")
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("job", choices=["morning", "strategy_ae", "knowledge", "strategy_us"])
    ap.add_argument("--dry-run", action="store_true", help="tạo bài + báo Telegram, không đăng")
    ap.add_argument("--now", action="store_true", help="không chờ đúng giờ đăng")
    a = ap.parse_args()
    sys.exit(0 if run_job(a.job, a.dry_run, a.now) else 1)
