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

from src.config import CONFIG, ROOT, TZ
from src.publish import telegram

SESSION = timedelta(hours=5, minutes=20)
LEAD = timedelta(minutes=25)               # bắt đầu tạo bài trước giờ đăng
LEAD_REEL = timedelta(minutes=55)          # video dựng lâu hơn (AI + giọng + dựng hình)
ATTEMPTS = ROOT / "state" / "attempts.json"
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def sh(cmd: str, timeout: int = 3600) -> int:
    print(f"$ {cmd}", flush=True)
    try:
        return subprocess.run(cmd, shell=True, cwd=ROOT, timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        print("  ! quá thời gian", flush=True)
        return 1


def sync():
    sh("git pull --rebase -q || (git rebase --abort; git pull -q --no-rebase)", 120)


def save_state(msg: str):
    if "GITHUB_ACTIONS" not in os.environ:
        return
    sh("git add state/posted.json state/series_progress.json state/followups.json state/metrics.json "
       "state/attempts.json state/reels_progress.json 2>/dev/null; git diff --cached --quiet || "
       f"(git commit -qm '{msg}' && (git push -q || (git pull --rebase -q && git push -q)))", 180)


def _attempts() -> dict:
    return json.loads(ATTEMPTS.read_text(encoding="utf-8")) if ATTEMPTS.exists() else {}


def due_jobs(now: datetime) -> list[tuple[str, datetime]]:
    from src.runner import _slot, already_posted, target_time
    out = []
    for job, cfg in CONFIG["schedule"].items():
        if DAYS[now.weekday()] not in cfg.get("days", []):
            continue
        targets = []
        if job == "knowledge":
            for t in cfg["times"]:
                targets.append(now.replace(hour=int(t[:2]), minute=int(t[3:]), second=0, microsecond=0))
        else:
            targets.append(target_time(job, now))
        for t in targets:
            slot = _slot(job, t)
            lead = LEAD_REEL if job == "reel" else LEAD
            if t - lead <= now <= t + timedelta(hours=2) and not already_posted(job, t) \
                    and _attempts().get(slot, 0) < 2:
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
    metrics = ROOT / "state" / "metrics.json"
    weekly = json.loads(metrics.read_text(encoding="utf-8")).get("weekly", {}) if metrics.exists() else {}
    return now.strftime("%Y-%m-%d") not in weekly


def one_round():
    sync()
    now = datetime.now(TZ)
    for job, target in due_jobs(now):
        run_post(job, target)
    sh("python -m src.followup auto", 2400)
    save_state("Cập nhật trạng thái comment")
    if weekly_report_due(datetime.now(TZ)):
        sh("python -m src.report", 1800)
        save_state("Lưu số liệu báo cáo tuần")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    if a.once:
        one_round()
        return
    start = datetime.now(TZ)
    print(f"Bộ điều phối bắt đầu {start:%H:%M %d/%m}, chạy tới {start + SESSION:%H:%M}", flush=True)
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
    print("Hết phiên - khởi động phiên kế tiếp", flush=True)


if __name__ == "__main__":
    sys.exit(main())
