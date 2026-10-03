"""Giọng đọc qua https://audio.aidancing.net/ (miễn phí, không cần đăng nhập).

- Job 1: giọng Thái nhân bản từ file mẫu (upload).
- Job thương hiệu (CWG…): giọng mẫu có sẵn của trang (voice_index 0-11: 0 Adam, 1 Trung Caha, 2 Kiều Linh,
  3 Tùng Đặng trầm ấm, 4 Hạnh, 5 Tùng Đặng điềm tĩnh, 6 Ngân Nguyễn, 7 Triều Dương, 8 Như, 9 Mai, 10 Hải Ly, 11 Tuyết)
  → POST /jobs {text, lang, voiceIndex} → POST /jobs/{uid}/start, không cần file giọng.

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


def _one(text: str, out: Path, session: requests.Session, voice_index: int | None = None,
         lang: str = "vi", ref: Path = VOICE_REF) -> Path:
    body = {"text": text[:2000], "lang": lang}
    if voice_index is not None:
        body["voiceIndex"] = str(voice_index)
    r = session.post(f"{BASE}/jobs", json=body, timeout=60)
    if r.status_code == 409:                         # đang có việc khác chạy → chờ rồi thử lại
        raise VoiceError("busy")
    r.raise_for_status()
    uid = r.json()["jobUid"]
    if voice_index is not None:
        r = session.post(f"{BASE}/jobs/{uid}/start", timeout=60)
    else:
        with open(ref, "rb") as f:
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


def synth(texts: list[str], folder: Path, voice_index: int | None = None, lang: str = "vi",
          ref: Path | None = None) -> list[Path]:
    """Đọc từng đoạn, trả về danh sách file WAV theo thứ tự. Mỗi đoạn thử tối đa 3 lần.
    voice_index=None → giọng nhân bản từ VOICE_REF; số → giọng mẫu của trang."""
    ref = ref or VOICE_REF
    if voice_index is None and not ref.exists():
        raise VoiceError(f"Thiếu file giọng mẫu {ref.relative_to(ROOT)}")
    folder.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    session.get(BASE + "/", timeout=60)
    out = []
    for i, text in enumerate(texts):
        path = folder / f"voice_{i:02d}.wav"
        note = path.with_suffix(".txt")
        key = (text if voice_index is None else f"[{voice_index}] {text}") + ("" if lang == "vi" and ref == VOICE_REF
                                                                              else f" [{lang}:{ref.name}]")
        if path.exists() and note.exists() and note.read_text(encoding="utf-8") == key:
            out.append(path)                          # đã có giọng cho đúng câu này → dùng lại
            continue
        for attempt in range(3):
            try:
                out.append(_one(text, path, session, voice_index, lang, ref))
                note.write_text(key, encoding="utf-8")
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
