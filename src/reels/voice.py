"""Giọng đọc của Thái - nhân bản từ file mẫu qua https://audio.aidancing.net/ (miễn phí, không cần đăng nhập).

Luồng của trang: POST /jobs {text, lang} → POST /jobs/{uid}/upload (file giọng mẫu) → GET /jobs tới khi COMPLETED
→ tải outputUrl (WAV 24 kHz). Mỗi cảnh của video đọc một đoạn riêng để biết chính xác thời lượng từng cảnh.
"""
import subprocess
import time
from pathlib import Path

import requests

from src.config import ROOT

BASE = "https://audio.aidancing.net"
VOICE_REF = ROOT / "assets" / "private" / "voice_ref.mp3"


class VoiceError(RuntimeError):
    pass


def _one(text: str, out: Path, session: requests.Session) -> Path:
    r = session.post(f"{BASE}/jobs", json={"text": text[:2000], "lang": "vi"}, timeout=60)
    if r.status_code == 409:                         # đang có việc khác chạy → chờ rồi thử lại
        raise VoiceError("busy")
    r.raise_for_status()
    uid = r.json()["jobUid"]
    with open(VOICE_REF, "rb") as f:
        r = session.post(f"{BASE}/jobs/{uid}/upload", files={"file": ("voice.mp3", f, "audio/mpeg")}, timeout=180)
    r.raise_for_status()
    t0 = time.time()
    while time.time() - t0 < 600:
        time.sleep(5)
        job = next((j for j in session.get(f"{BASE}/jobs", timeout=60).json()
                    if j.get("jobUid") == uid or j.get("uid") == uid), None)
        status = (job or {}).get("status")
        if status == "FAILED":
            raise VoiceError("trang tạo giọng báo FAILED")
        if status == "COMPLETED" and job.get("outputUrl"):
            url = job["outputUrl"]
            data = session.get(url if url.startswith("http") else BASE + url, timeout=120).content
            out.write_bytes(data)
            return out
    raise VoiceError("tạo giọng quá 10 phút")


def synth(texts: list[str], folder: Path) -> list[Path]:
    """Đọc từng đoạn, trả về danh sách file WAV theo thứ tự. Mỗi đoạn thử tối đa 3 lần."""
    if not VOICE_REF.exists():
        raise VoiceError(f"Thiếu file giọng mẫu {VOICE_REF.relative_to(ROOT)}")
    folder.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    session.get(BASE + "/", timeout=60)
    out = []
    for i, text in enumerate(texts):
        path = folder / f"voice_{i:02d}.wav"
        note = path.with_suffix(".txt")
        if path.exists() and note.exists() and note.read_text(encoding="utf-8") == text:
            out.append(path)                          # đã có giọng cho đúng câu này → dùng lại
            continue
        for attempt in range(3):
            try:
                out.append(_one(text, path, session))
                note.write_text(text, encoding="utf-8")
                break
            except Exception as exc:
                print(f"  ! giọng đoạn {i + 1} lỗi ({exc}), thử lại", flush=True)
                if attempt == 2:
                    raise VoiceError(f"Không tạo được giọng đọc đoạn {i + 1}: {exc}") from exc
                time.sleep(20)
    return out


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout
    return float(out.strip())
