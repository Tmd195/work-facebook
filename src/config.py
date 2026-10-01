"""Đọc config.yaml và biến môi trường (.env)."""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
OUTPUT = ROOT / "output"


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


_load_dotenv()

with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

TZ = ZoneInfo(CONFIG["timezone"])
SYMBOLS = CONFIG["symbols"]


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)
