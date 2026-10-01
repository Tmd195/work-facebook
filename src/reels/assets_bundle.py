"""Đóng gói + mã hoá ảnh/giọng của Thái và bộ nhạc để đưa lên repo công khai an toàn.

    python -m src.reels.assets_bundle pack     # máy anh: assets/private + assets/music → assets/private.tar.gz.enc
    python -m src.reels.assets_bundle unpack   # GitHub: giải mã ra lại (cần biến môi trường ASSETS_KEY)

Khoá ASSETS_KEY chỉ nằm trong .env và GitHub Secrets. Đổi ảnh/nhạc/giọng → chạy pack rồi commit file .enc.
"""
import os
import subprocess
import sys
import tarfile

from src.config import ROOT, env

BUNDLE = ROOT / "assets" / "private.tar.gz.enc"
PARTS = ["assets/private", "assets/music"]
_ENC = ["-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-pass", "env:ASSETS_KEY"]


def _key_env() -> dict:
    key = os.environ.get("ASSETS_KEY") or env("ASSETS_KEY")
    if not key:
        raise SystemExit("Thiếu ASSETS_KEY (.env hoặc GitHub Secrets)")
    return {**os.environ, "ASSETS_KEY": key}


def pack():
    tmp = BUNDLE.with_suffix("")                      # .tar.gz tạm
    with tarfile.open(tmp, "w:gz") as tar:
        for part in PARTS:
            tar.add(ROOT / part, arcname=part)
    subprocess.run(["openssl", "enc", *_ENC, "-salt", "-in", str(tmp), "-out", str(BUNDLE)], check=True, env=_key_env())
    tmp.unlink()
    print(f"Đã đóng gói {BUNDLE.relative_to(ROOT)} ({BUNDLE.stat().st_size / 1e6:.1f} MB)")


def unpack():
    if not BUNDLE.exists():
        raise SystemExit("Chưa có assets/private.tar.gz.enc")
    tmp = BUNDLE.with_suffix("")
    subprocess.run(["openssl", "enc", "-d", *_ENC, "-in", str(BUNDLE), "-out", str(tmp)], check=True, env=_key_env())
    with tarfile.open(tmp, "r:gz") as tar:
        tar.extractall(ROOT, filter="data")
    tmp.unlink()
    print("Đã giải mã ảnh, giọng và nhạc cho Reels")


if __name__ == "__main__":
    {"pack": pack, "unpack": unpack}[sys.argv[1]]()
