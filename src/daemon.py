"""Bộ điều phối chạy liên tục trên GitHub Actions - KHÔNG phụ thuộc độ chính xác của cron.

Mỗi phiên chạy ~5 giờ 20 phút:
  - mỗi ~2 phút: kiểm tra lịch → bài nào sắp tới giờ (trong 25 phút tới) thì tạo bài, chờ đúng giờ và đăng
  - chạy comment theo dõi (tin đỏ, ví dụ Kiến thức, cập nhật lệnh 22:00)
  - Chủ nhật 23:00: báo cáo đánh giá tuần
  - lưu trạng thái lên repo sau mỗi việc
Hết phiên → tự khởi động phiên kế tiếp (workflow_dispatch). Cron 30 phút/lần chỉ để "gác": nếu chuỗi bị đứt thì khởi động lại.

    python -m src.daemon            # chạy 1 phiên
    python -m src.daemon --once     # chỉ quét 1 vòng (kiểm tra)
"""
import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta

from src.config import CONFIG, IS_DEFAULT_JOB, JOB, ROOT, STATE, TZ
from src.publish import telegram

SESSION = timedelta(hours=5, minutes=20)
LEAD = timedelta(minutes=25)               # bắt đầu tạo bài trước giờ đăng
LEAD_REEL = timedelta(hours=3)             # Reels dựng sớm 3 tiếng (kiểm tra + viết lại nhiều lần vẫn kịp giờ)
REEL_PROCS: dict = {}                      # Reels chạy tiến trình riêng (không chặn bài khác): slot → Popen
ATTEMPTS = STATE / "attempts.json"
ST = STATE.relative_to(ROOT).as_posix()       # state hoặc state/<job>
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def sh(cmd: str, timeout: int = 3600) -> int:
    print(f"$ {cmd}", flush=True)
    try:
        return subprocess.run(cmd, shell=True, cwd=ROOT, timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        print("  ! quá thời gian", flush=True)
        return 1


def sync():
    sh("git pull --rebase --autostash -q || (git rebase --abort; git pull -q --no-rebase --autostash)", 120)


def save_state(msg: str):
    if "GITHUB_ACTIONS" not in os.environ:
        return
    # chỉ đưa file ĐANG CÓ vào git add – 1 đường dẫn không tồn tại làm cả lệnh thất bại, không lưu được gì
    files = " ".join(f"{ST}/{n}.json" for n in ("posted", "series_progress", "followups", "metrics", "attempts",
                                                 "reels_progress", "brand_progress", "hunter", "hunter_archive",
                                                 "edu_reels", "fx_pick", "story_reels", "quiz_reels",
                                                 "indi_reels", "smc_reels") if (STATE / f"{n}.json").exists())
    if not files:
        return
    sh(f"git add {files} 2>/dev/null; git diff --cached --quiet || "
       f"(git commit -qm '{msg}' && (git push -q || (git pull --rebase -q && git push -q)))", 180)


def _attempts() -> dict:
    return json.loads(ATTEMPTS.read_text(encoding="utf-8")) if ATTEMPTS.exists() else {}


def due_jobs(now: datetime) -> list[tuple[str, datetime]]:
    from src.runner import _slot, already_posted, skip_today, target_time
    out = []
    for job, cfg in CONFIG["schedule"].items():
        if DAYS[now.weekday()] not in cfg.get("days", DAYS):
            continue
        try:
            if skip_today(job, now):
                continue
        except Exception as exc:                         # lỗi đọc lịch tin → vẫn thử chạy để runner báo lỗi rõ
            print(f"! skip_today {job}: {exc}", flush=True)
        if cfg.get("dates") and now.strftime("%Y-%m-%d") not in cfg["dates"]:
            continue
        if cfg.get("every") and now.date().toordinal() % int(cfg["every"]) != int(cfg.get("offset", 0)):
            continue                                     # vd. every: 2 = cách ngày
        targets = []
        if job == "knowledge":
            for t in cfg["times"]:
                targets.append(now.replace(hour=int(t[:2]), minute=int(t[3:]), second=0, microsecond=0))
        else:
            targets.append(target_time(job, now))
        for t in targets:
            slot = _slot(job, t)
            lead = LEAD_REEL if job.startswith("reel") else LEAD
            if t - lead <= now <= t + timedelta(hours=2) and not already_posted(job, t) \
                    and _attempts().get(slot, 0) < 6:
                out.append((job, t))
    return sorted(out, key=lambda x: x[1])


def run_post(job: str, target: datetime):
    from src.runner import _slot
    att = _attempts()
    slot = _slot(job, target)
    att[slot] = att.get(slot, 0) + 1
    ATTEMPTS.parent.mkdir(parents=True, exist_ok=True)
    ATTEMPTS.write_text(json.dumps(dict(sorted(att.items())[-100:]), ensure_ascii=False, indent=1), encoding="utf-8")
    sh(f"python -m src.runner {job} --at {target:%H:%M}", 3600)
    save_state(f"Đăng bài {job} {target:%H:%M}")


def weekly_report_due(now: datetime) -> bool:
    if now.weekday() != 6 or now.hour < 23:
        return False
    metrics = STATE / "metrics.json"
    weekly = json.loads(metrics.read_text(encoding="utf-8")).get("weekly", {}) if metrics.exists() else {}
    return now.strftime("%Y-%m-%d") not in weekly


def start_reel(job: str, target: datetime, session_end: datetime | None):
    """Dựng + đăng Reels ở tiến trình riêng: dựng sớm, tự chờ đúng giờ đăng, các bài khác vẫn chạy song song."""
    from src.runner import _slot
    slot = _slot(job, target)
    p = REEL_PROCS.get(slot)
    if p is not None:
        if p.poll() is None:
            return                                      # đang dựng / đang chờ giờ
        del REEL_PROCS[slot]
        save_state(f"Đăng bài {job} {target:%H:%M}")
        return
    now = datetime.now(TZ)
    if session_end and target + timedelta(minutes=10) > session_end:
        return                                          # phiên hết trước giờ đăng → để phiên kế tiếp dựng
    att = _attempts()
    att[slot] = att.get(slot, 0) + 1
    ATTEMPTS.parent.mkdir(parents=True, exist_ok=True)
    ATTEMPTS.write_text(json.dumps(dict(sorted(att.items())[-100:]), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"$ [nền] python -m src.runner {job} --at {target:%H:%M} (dựng sớm {(target - now).seconds // 60}')", flush=True)
    REEL_PROCS[slot] = subprocess.Popen([sys.executable, "-m", "src.runner", job, "--at", f"{target:%H:%M}"], cwd=ROOT)


SESSION_END = None


def one_round():
    sync()
    now = datetime.now(TZ)
    for slot, p in list(REEL_PROCS.items()):            # Reels nền đã xong → lưu trạng thái
        if p.poll() is not None:
            del REEL_PROCS[slot]
            save_state(f"Đăng Reels {slot}")
    for job, target in due_jobs(now):
        if job.startswith("reel"):
            start_reel(job, target, SESSION_END)
            continue
        run_post(job, target)
    if IS_DEFAULT_JOB:                                   # comment theo dõi + báo cáo tuần: riêng Page Thái
        sh("python -m src.followup auto", 2400)
    save_state("Cập nhật trạng thái")
    if IS_DEFAULT_JOB and weekly_report_due(datetime.now(TZ)):
        sh("python -m src.report", 1800)
        save_state("Lưu số liệu báo cáo tuần")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    if a.once:
        one_round()
        return
    global SESSION_END
    start = datetime.now(TZ)
    SESSION_END = start + SESSION
    print(f"Bộ điều phối [{JOB}] bắt đầu {start:%H:%M %d/%m}, chạy tới {start + SESSION:%H:%M}", flush=True)
    if (CONFIG.get("hunter") or {}).get("enabled"):     # bộ săn tin chạy luồng riêng, không bị bài theo lịch chặn
        import threading
        from src import hunter
        threading.Thread(target=hunter.run_forever, args=(start + SESSION - timedelta(minutes=2),
                                                         CONFIG["hunter"].get("interval", 60)), daemon=True).start()
    errors = 0
    while datetime.now(TZ) < start + SESSION:
        try:
            one_round()
            errors = 0
        except Exception as exc:
            traceback.print_exc()
            errors += 1
            if errors == 3:
                telegram.need_fix(f"❌ Bộ điều phối lỗi 3 lần liên tiếp: {type(exc).__name__}: {exc}")
        time.sleep(120)
    for slot, p in REEL_PROCS.items():                  # chờ Reels nền đăng xong rồi mới kết thúc phiên
        try:
            p.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            print(f"  ! Reels {slot} chưa xong khi hết phiên", flush=True)
    if REEL_PROCS:
        save_state("Đăng Reels (cuối phiên)")
    print("Hết phiên - khởi động phiên kế tiếp", flush=True)


if __name__ == "__main__":
    sys.exit(main())
