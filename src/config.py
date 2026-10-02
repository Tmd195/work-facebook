"""Đọc config.yaml và biến môi trường (.env) – hỗ trợ nhiều Job (mỗi Job = 1 Facebook Page).

Chọn Job bằng biến môi trường JOB (mặc định "duy-thai-dang" = Page đầu tiên, giữ nguyên đường dẫn cũ).
Job khác: cấu hình riêng ở jobs/<job>/job.yaml (ghi đè lên config.yaml), trạng thái ở state/<job>/, bài ở output/<job>/.
Token riêng từng Job: trên GitHub map secret vào FB_PAGE_ID / FB_PAGE_TOKEN; trên máy dùng .env với hậu tố,
ví dụ FB_PAGE_TOKEN__CWG_VN (env() tự tìm bản có hậu tố trước).
"""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DEFAULT_JOB = "duy-thai-dang"
JOB = os.environ.get("JOB", DEFAULT_JOB).strip() or DEFAULT_JOB
JOB_KEY = JOB.upper().replace("-", "_")
JOB_DIR = ROOT / "jobs" / JOB
IS_DEFAULT_JOB = JOB == DEFAULT_JOB
OUTPUT = ROOT / "output" if IS_DEFAULT_JOB else ROOT / "output" / JOB
STATE = ROOT / "state" if IS_DEFAULT_JOB else ROOT / "state" / JOB

# Biến môi trường riêng từng Job (các biến khác dùng chung: Claude, Telegram, Twelve Data...)
JOB_SCOPED_ENV = {"FB_PAGE_ID", "FB_PAGE_TOKEN"}


def _load_dotenv():
    """Nạp .env (nếu có) vào os.environ - không ghi đè biến đã có."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


_load_dotenv()

with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)
if not IS_DEFAULT_JOB:
    job_file = JOB_DIR / "job.yaml"
    if not job_file.exists():
        raise SystemExit(f"Không có cấu hình Job: {job_file}")
    with open(job_file, encoding="utf-8") as f:
        job_cfg = yaml.safe_load(f) or {}
    if "schedule" in job_cfg:                       # lịch của Job thay hẳn lịch mặc định, không gộp
        CONFIG.pop("schedule", None)
    CONFIG = _merge(CONFIG, job_cfg)
CONFIG.setdefault("job", {}).setdefault("id", JOB)

TZ = ZoneInfo(CONFIG["timezone"])
SYMBOLS = CONFIG["symbols"]


def env(name: str, default: str = "") -> str:
    if not IS_DEFAULT_JOB and name in JOB_SCOPED_ENV:
        scoped = os.environ.get(f"{name}__{JOB_KEY}")
        if scoped:
            return scoped
        if not os.environ.get("GITHUB_ACTIONS"):
            return default                           # trên máy: không dùng nhầm token của Page Thái
    return os.environ.get(name, default)
