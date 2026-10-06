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
    try:
        session.get(BASE + "/", timeout=30)
    except Exception as exc:                          # trang giọng sập → dùng giọng dự phòng cho cả video
        if lang not in FALLBACK:
            raise VoiceError(f"Trang tạo giọng không kết nối được ({exc}) – Page tiếng Việt không dùng giọng khác") from exc
        print(f"  ! trang giọng không kết nối được ({exc}) → giọng dự phòng Edge TTS", flush=True)
        return _fallback_all(texts, folder, lang)
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
                    if lang not in FALLBACK:
                        raise VoiceError(f"Không tạo được giọng đọc đoạn {i + 1}: {exc}") from exc
                    print("  ! trang giọng lỗi liên tục → giọng dự phòng Edge TTS cho cả video", flush=True)
                    return _fallback_all(texts, folder, lang)   # cùng 1 giọng cho cả video, không trộn 2 giọng
                time.sleep(20)
    return out


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout
    return float(out.strip())


# ------------------------------------------------------------------ giọng dự phòng
FALLBACK = {"en": "en-US-AvaNeural"}   # Microsoft Edge TTS (miễn phí). Chỉ Page tiếng Anh (anh cho phép giọng nữ);
                                       # Page tiếng Việt KHÔNG đổi giọng (phải trùng giọng đã duyệt)


def _edge(text: str, out: Path, lang: str):
    import asyncio
    import edge_tts
    mp3 = out.with_suffix(".edge.mp3")
    base = text.strip().rstrip("?.!…")
    last = None
    for variant in (text, base + ".", base + "!", base, " " + base + " ."):   # dịch vụ đôi khi từ chối 1 cách viết dấu câu

        async def run(t=variant):
            await edge_tts.Communicate(t, FALLBACK[lang]).save(str(mp3))
        try:
            asyncio.run(run())
            break
        except Exception as exc:
            last = exc
    else:
        raise VoiceError(f"Edge TTS không đọc được: {last}")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-ar", "24000", "-ac", "1", str(out)], check=True)
    mp3.unlink(missing_ok=True)
    return out


def _fallback_all(texts: list[str], folder: Path, lang: str) -> list[Path]:
    """Đọc lại TOÀN BỘ câu bằng giọng dự phòng (không trộn với giọng chính). Báo Telegram 1 lần."""
    out = []
    for i, text in enumerate(texts):
        path = folder / f"voice_{i:02d}.wav"
        for attempt in range(3):
            try:
                out.append(_edge(text, path, lang))
                path.with_suffix(".txt").write_text(f"[edge] {text}", encoding="utf-8")
                break
            except Exception as exc:
                if attempt == 2:
                    raise VoiceError(f"Giọng chính và giọng dự phòng đều lỗi (đoạn {i + 1}): {exc}") from exc
                time.sleep(10)
    try:
        from src.publish import telegram
        telegram.send("🔊 Trang tạo giọng (aidancing) đang lỗi – video tiếng Anh hôm nay dùng giọng nữ dự phòng Microsoft, vẫn đăng đúng giờ.")
    except Exception:
        pass
    return out
