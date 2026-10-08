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

from src.config import CONFIG, OUTPUT, STATE, TZ
from src.publish import facebook, telegram

NY = ZoneInfo("America/New_York")
MAX_EARLY = timedelta(minutes=60)      # chạy sớm hơn giờ đăng quá mức này thì bỏ (cron mùa hè/đông trùng nhau)


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
    if job == "cwg_macro" and sched[job].get("after_fx"):      # Page Global: vĩ mô sau bài đồng tiền cuối cùng
        from src.content.cwg_daily import macro_after_fx
        return macro_after_fx(now)
    return hm(sched[job]["time"])


def _reel_mod(job: str):
    """reel = Reels chính của Page; reel_story = Reels kể chuyện (Page Decode, cách ngày)."""
    if job == "reel_story":
        from src.reels.story import job as mod
    elif job == "reel_quiz":                              # Page Decode: Reels "BUY OR SELL?" mỗi ngày
        from src.reels.quiz import job as mod
    elif job == "reel_indi":                              # Page DecodeFx Trading: Reels indicator Sniper AI V4/V7
        from src.reels.indi import job as mod
    elif job == "reel_smc":                               # Page DecodeFx Trading: Reels kiến thức hệ thống
        from src.reels.smc import job as mod
    else:
        from src.reels import job as mod
    return mod


def skip_today(job: str, now: datetime) -> bool:
    """Ô lịch không có bài hôm nay (vd. Page Global chỉ chọn 2/6 đồng tiền) → bỏ qua, không báo lỗi."""
    if job.startswith("cwg_fx_"):
        from src.content.cwg_daily import skip_today as fx_skip
        return fx_skip(job, now)
    return False


def wait_until(t: datetime):
    while (left := (t - datetime.now(TZ)).total_seconds()) > 0:
        time.sleep(min(left, 30))


# ===================================================================== chống đăng trùng

POSTED = STATE / "posted.json"


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
    if job == "weekly":
        return {}
    if job.startswith("reel"):
        reel = _reel_mod(job)
        return reel.meta(out_dir)
    if job.startswith("cwg_"):
        return {}
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


def record_followers():
    """Lưu số người theo dõi theo ngày (cho báo cáo tuần)."""
    import json
    path = STATE / "metrics.json"
    try:
        n = facebook.page_stats().get("followers_count")
    except Exception:
        return
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"followers": {}, "weekly": {}}
    data.setdefault("followers", {})[datetime.now(TZ).strftime("%Y-%m-%d")] = n
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


# ===================================================================== tạo bài

def _files(job: str, out_dir):
    if job == "morning":
        return out_dir / "morning.txt", [out_dir / "morning.png"]
    if job == "knowledge":
        return out_dir / "knowledge.txt", sorted(out_dir.glob("knowledge_[0-9][0-9].png"))
    if job == "weekly":
        return out_dir / "weekly.txt", sorted(out_dir.glob("weekly_[0-9][0-9].png"))
    if job.startswith("reel"):
        reel = _reel_mod(job)
        cap, video, thumb = reel.files(out_dir)
        return cap, [video, thumb]
    if job.startswith("cwg_"):
        from src.content import cwg_daily, cwg_weekend
        return (cwg_weekend if job.startswith("cwg_wk_") else cwg_daily).files(job, out_dir)
    s = job.split("_")[1]
    return out_dir / f"strategy_{s}.txt", sorted(out_dir.glob(f"strategy_{s}_[0-9][0-9].png"))


def generate(job: str):
    import run
    if job == "morning":
        return run.run_morning()
    if job == "knowledge":
        return run.run_knowledge()
    if job == "weekly":
        return run.run_weekly()
    if job.startswith("reel"):
        reel = _reel_mod(job)
        return reel.generate(OUTPUT / datetime.now(TZ).strftime("%Y-%m-%d"))
    if job.startswith("cwg_"):
        from src.content import cwg_daily, cwg_weekend
        mod = cwg_weekend if job.startswith("cwg_wk_") else cwg_daily
        return mod.generate(job, OUTPUT / datetime.now(TZ).strftime("%Y-%m-%d"))
    return run.run_strategy(job.split("_")[1])


def label(job: str) -> str:
    if job.startswith("cwg_"):
        from src.content.cwg_daily import JOB_NAMES
        from src.content.cwg_weekend import JOB_NAMES as WK
        return {**JOB_NAMES, **WK}.get(job, job)
    if job == "knowledge":
        from src.content import knowledge
        nxt = knowledge.next_lesson()
        return f"Kiến thức: {nxt[0]['name']} – Phần {nxt[1]['part']}/{len(nxt[0]['lessons'])}" if nxt else "Kiến thức"
    return {"morning": "Bản tin sáng", "weekly": "Tổng quan tuần mới", "reel": "Video Reels", "reel_story": "Reels kể chuyện nghề IB", "reel_quiz": "Reels BUY OR SELL?", "reel_indi": "Reels Sniper AI", "reel_smc": "Reels kiến thức hệ thống", "strategy_ae": "Chiến lược XAUUSD phiên Á – Âu",
            "strategy_us": "Chiến lược XAUUSD phiên Mỹ"}[job]


# ===================================================================== chạy 1 việc

def run_job(job: str, dry_run: bool = False, no_wait: bool = False, attempts: int = 3, at: str | None = None) -> bool:
    if not (CONFIG.get("autopost") or {}).get("live", False):
        dry_run = True                       # công tắc an toàn: chưa bật đăng thật
    now = datetime.now(TZ)
    day = now.strftime("%d/%m")
    target = (now.replace(hour=int(at[:2]), minute=int(at[3:]), second=0, microsecond=0) if at
              else target_time(job, now))
    early = timedelta(hours=3, minutes=15) if job.startswith("reel") else MAX_EARLY   # Reels dựng sớm để kịp kiểm tra
    if not no_wait and target - now > early:
        print(f"Bỏ qua: giờ đăng {target:%H:%M}, còn quá sớm (lịch chạy của mùa khác)")
        return True
    if not no_wait and now - target > timedelta(hours=2):
        print(f"Bỏ qua: đã quá giờ đăng {target:%H:%M} hơn 2 tiếng")
        return True
    if skip_today(job, now):
        print(f"Bỏ qua: {job} hôm nay không có bài (ô lịch trống)")
        return True
    if not dry_run and already_posted(job, target):
        print(f"Bỏ qua: {job} {target:%H:%M} hôm nay đã đăng rồi")
        return True
    name = label(job)
    out_dir = OUTPUT / now.strftime("%Y-%m-%d")
    had_error = False

    # --- 1. Tạo bài – SỬA ĐẾN KHI ĐƯỢC (anh chốt 06/10/2026): thử lại liên tục tới hạn chót (giờ đăng + 2 tiếng),
    #        không bỏ cuộc sau vài lần. Reels: bộ kiểm tra tự sửa tới sát giờ đăng (qa.DEADLINE).
    upload = timedelta(minutes=12) if job.startswith("reel") else timedelta(minutes=3)
    if job.startswith("reel"):
        from src.reels import qa as _qa
        _qa.DEADLINE = max(target - upload, datetime.now(TZ) + timedelta(minutes=20))
    give_up = max(target, datetime.now(TZ)) + timedelta(hours=2)
    k = 0
    while True:
        k += 1
        err = None
        try:
            if generate(job):
                break
            err = "không tạo được nội dung (AI hoặc dữ liệu không đạt kiểm tra)"
        except Exception as exc:
            if type(exc).__name__ == "QAFail":           # đã tự sửa 2 lần vẫn lỗi, đã báo kèm ảnh → không đăng
                traceback.print_exc()
                import json                              # khoá lượt hôm nay: bộ điều phối không chạy lại lần 2
                att_file = STATE / "attempts.json"
                att = json.loads(att_file.read_text(encoding="utf-8")) if att_file.exists() else {}
                att[_slot(job, target)] = 99
                att_file.parent.mkdir(parents=True, exist_ok=True)
                att_file.write_text(json.dumps(att, ensure_ascii=False, indent=1), encoding="utf-8")
                return False
            err = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
        had_error = True
        if k == 1:
            telegram.send(f"⚠️ {name} {day} lỗi:\n{err}\n🔧 Em tự sửa và thử lại liên tục tới khi được.")
        wait = min(60 * k, 300)
        if datetime.now(TZ) + timedelta(seconds=wait) > give_up:
            telegram.need_fix(f"❌ {name} {day}: đã thử {k} lần tới quá giờ đăng 2 tiếng vẫn lỗi.\n"
                              f"Lỗi cuối: {err}\nEm cần anh kiểm tra giúp.")
            return False
        if k % 5 == 0:
            telegram.send(f"🔧 {name} {day}: vẫn đang sửa (lần {k}) – lỗi: {err[:200]}")
        time.sleep(wait)
    if had_error:
        telegram.send("✅ Đã sửa xong lỗi, tiếp tục đăng bài.")

    caption_file, images = _files(job, out_dir)

    # --- 1b. Soát ẢNH trước khi đăng (chữ đè / tràn / bị cắt / biểu đồ trắng…) – lỗi nặng → tạo lại bài + ảnh, lặp tới khi ĐẠT.
    #         KHÔNG đăng ảnh lỗi (anh chốt 07/10/2026: "đăng ảnh trắng thì đăng làm gì"): quá giờ đăng vẫn sửa tiếp và
    #         đăng trễ; tới giờ đăng + 2 tiếng vẫn lỗi → không đăng, báo anh. Reels có bộ kiểm tra riêng.
    if not job.startswith("reel"):
        from src.design import qa_image
        k, late_note = 0, False
        while True:
            rep = qa_image.check(images, out_dir, job)
            if rep["ok"]:
                if rep["minor"]:
                    print(f"  ~ ảnh: góp ý nhẹ (vẫn đăng): {rep['minor']}", flush=True)
                break
            k += 1
            print(f"  ! ảnh lỗi (lần {k}): {rep['major']}", flush=True)
            if datetime.now(TZ) > give_up:
                telegram.need_fix(f"❌ {name} {day}: đã sửa ảnh {k} lần tới quá giờ đăng 2 tiếng vẫn lỗi – em KHÔNG đăng ảnh hỏng:\n"
                                  + "\n".join(rep["major"]))
                return False
            if datetime.now(TZ) > target - upload and not late_note:
                late_note = True
                telegram.send(f"⏳ {name} {day}: ảnh còn lỗi ({'; '.join(rep['major'])[:300]}) – em sửa tiếp, "
                              f"đạt mới đăng (sẽ trễ giờ một chút).")
            while True:                                  # tạo lại bài + ảnh (lỗi dữ liệu/AI → chờ rồi thử tiếp)
                try:
                    if generate(job):
                        break
                except Exception:
                    traceback.print_exc()
                if datetime.now(TZ) > give_up:
                    break
                time.sleep(60)
            caption_file, images = _files(job, out_dir)
    caption = caption_file.read_text(encoding="utf-8")

    # --- 2. Chờ đúng giờ rồi đăng
    if not no_wait and not dry_run:
        wait_until(target)
    meta = post_meta(job, out_dir)
    if job.startswith("reel"):
        name = f"Video Reels: {meta.get('topic', '')}"
    if dry_run and job.startswith("reel"):
        telegram.send(f"🧪 [XEM TRƯỚC - chưa đăng] {name} {day} ({meta.get('duration')}s)\n"
                      f"Video đã dựng xong (chế độ chạy thử, không gửi file cho nhẹ).\n\n{caption}")
        if not already_posted(job, target):
            mark_posted(job, target, "preview", None, meta, preview=True)
        return True
    if dry_run:
        telegram.send_preview(f"🧪 [XEM TRƯỚC - chưa đăng] {name} {day}\n{len(images)} ảnh · bài đầy đủ bên dưới. "
                              f"Anh duyệt, nếu ổn nhắn em bật đăng thật.", caption, images)
        if not already_posted(job, target):
            mark_posted(job, target, "preview", None, meta, preview=True)
        return True
    try:
        if job.startswith("reel"):
            link, post_id = facebook.publish_reel(images[0], caption, images[1])
        else:
            link, post_id = facebook.publish(caption, images)
    except facebook.FacebookError as exc:
        hint = ("\n👉 Token Facebook hết hạn hoặc thiếu quyền - cần anh lấy lại token theo hướng dẫn."
                if exc.needs_user else "")
        telegram.need_fix(f"❌ {name} {day}: đăng Facebook thất bại.\n{exc}{hint}")
        return False

    mark_posted(job, target, link, post_id, meta)
    record_followers()
    if job == "knowledge":
        import json
        from src.content import knowledge
        meta = json.loads((out_dir / "knowledge.json").read_text(encoding="utf-8"))
        series = next(s for s in knowledge.load_series() if s["id"] == meta["series"])
        knowledge.mark_done(series, series["lessons"][meta["part"] - 1])
    if job.startswith("reel"):
        reel = _reel_mod(job)
        reel.mark_done(meta)

    telegram.send(f"✅ Đã hoàn thành: {name} {day}\n🔗 Link bài viết: {link}\nAnh kiểm tra nếu cần sửa đổi.")
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--dry-run", action="store_true", help="tạo bài + báo Telegram, không đăng")
    ap.add_argument("--now", action="store_true", help="không chờ đúng giờ đăng")
    ap.add_argument("--at", help="đăng vào giờ chỉ định HH:MM (giờ VN), dùng cho bài đăng bổ sung")
    a = ap.parse_args()
    sys.exit(0 if run_job(a.job, a.dry_run, a.now, at=a.at) else 1)
