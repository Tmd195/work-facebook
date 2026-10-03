"""Kiểm tra chất lượng video Reels TRƯỚC KHI ĐĂNG – 3 lớp:

1. Máy tự đo (code, chắc chắn): thời lượng, có tiếng / không rè, đủ giọng, con số khớp dữ liệu thật,
   từ cấm, ký tự font không có (tự thay trước khi dựng – xem clean()).
2. AI xem lại hình: cắt ~10 khung rải đều video thành 1 ảnh, Claude chấm theo danh sách lỗi đã gặp.
3. Tự sửa: lỗi dựng → dựng lại; lỗi nội dung → viết kịch bản mới (tối đa 2 lần, do job gọi).
   Vẫn lỗi → KHÔNG đăng, báo Telegram kèm lý do + ảnh khung lỗi (QAFail).

    python -m src.reels.qa <video.mp4> [--kind market|edu|thai]     # kiểm tra 1 video có sẵn
"""
import argparse
import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path

from PIL import Image

from src.design.common import sans


class QAFail(RuntimeError):
    """Video không đạt sau các lần tự sửa – không đăng."""

    def __init__(self, msg: str, sheet: Path | None = None):
        super().__init__(msg)
        self.sheet = sheet


# ------------------------------------------------------------------ 0. ký tự font không có
_SWAP = {"~": "", "≈": "", "“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "…": "...", "→": "->",
         "×": "x", "•": "·", "\u00a0": " "}


@lru_cache(maxsize=None)
def _notdef(weight: str) -> bytes:
    f = sans(weight, 40)
    return bytes(f.getmask("\U0010fffe"))


@lru_cache(maxsize=4096)
def has_glyph(ch: str, weight: str = "Bold") -> bool:
    if ch.isspace() or ord(ch) < 128 and ch.isprintable() and ch != "~":
        return True
    f = sans(weight, 40)
    return bytes(f.getmask(ch)) != _notdef(weight)


def clean(text: str, weight: str = "Bold") -> str:
    """Thay/bỏ ký tự font Be Vietnam Pro không vẽ được (vd. '~' hiện thành '-') – gọi trước khi vẽ chữ."""
    out = []
    for ch in text or "":
        if ch in _SWAP:
            out.append(_SWAP[ch])
        elif has_glyph(ch, weight) or ord(ch) > 0x1F000:      # emoji không vẽ lên video
            out.append(ch if ord(ch) <= 0x1F000 else "")
        else:
            out.append("")
    return re.sub(r" {2,}", " ", "".join(out)).strip()


# ------------------------------------------------------------------ 1. máy tự đo
def probe(video: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
                          "-of", "json", str(video)], capture_output=True, text=True).stdout
    j = json.loads(out or "{}")
    vol = subprocess.run(["ffmpeg", "-i", str(video), "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    mean = re.search(r"mean_volume: ([-\d.]+)", vol)
    peak = re.search(r"max_volume: ([-\d.]+)", vol)
    sil = subprocess.run(["ffmpeg", "-i", str(video), "-af", "silencedetect=n=-45dB:d=2.5", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    gaps = [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", sil)]
    streams = {s["codec_type"]: s for s in j.get("streams", [])}
    return {"duration": float((j.get("format") or {}).get("duration", 0)), "has_audio": "audio" in streams,
            "size": (streams.get("video", {}).get("width"), streams.get("video", {}).get("height")),
            "mean_db": float(mean.group(1)) if mean else -99, "peak_db": float(peak.group(1)) if peak else -99,
            "silences": gaps}


def media_errors(info: dict, min_dur: float, max_dur: float) -> list[str]:
    e = []
    if info["size"] != (1080, 1920):
        e.append(f"kích thước video sai {info['size']}")
    if not min_dur <= info["duration"] <= max_dur:
        e.append(f"thời lượng {info['duration']:.1f}s ngoài khoảng {min_dur:.0f}-{max_dur:.0f}s")
    if not info["has_audio"] or info["mean_db"] < -35:
        e.append(f"gần như không có tiếng (trung bình {info['mean_db']} dB)")
    if info["peak_db"] > -0.05:
        e.append("âm thanh bị rè/vỡ (chạm 0 dB)")
    long_gaps = [g for g in info["silences"] if g > 4.5]
    if long_gaps:
        e.append(f"có đoạn im lặng dài {max(long_gaps):.1f}s (mất giọng/nhạc)")
    return e


def voice_errors(paths: list, texts: list[str]) -> list[str]:
    """Mỗi câu phải có file giọng, độ dài hợp lý với số chữ (giọng bị cắt / đọc lố)."""
    from src.reels.voice import duration
    e = []
    for p, t in zip(paths, texts):
        if not p or not Path(p).exists():
            e.append(f"thiếu giọng đọc cho câu: {t[:40]}")
            continue
        d, words = duration(Path(p)), max(1, len(t.split()))
        if d < words * 0.18 or d > words * 0.75 + 2.5:
            e.append(f"giọng đọc bất thường ({d:.1f}s cho {words} từ): {t[:40]}")
    return e


_NUM = re.compile(r"(?<![\w.])[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|(?<![\w.])\d+(?:\.\d+)?")
SAFE_NUMS = {1, 2, 3, 4, 5, 10, 14, 20, 30, 50, 60, 70, 80, 100, 200}


def _flat(v):
    if isinstance(v, dict):
        for x in v.values():
            yield from _flat(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _flat(x)
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        yield float(v)


def number_errors(texts: list[str], facts: dict) -> list[str]:
    """Mọi con số trên màn hình/caption phải khớp dữ liệu thật (giá lệch ≤ 0.35%, % lệch ≤ 0.15 điểm)."""
    vals = list(_flat(facts))
    e = []
    for t in texts:
        for m in _NUM.finditer(t or ""):
            raw = m.group(0)
            x = abs(float(raw.replace(",", "")))
            if x in SAFE_NUMS or x == 0:
                continue
            pct = t[m.end(): m.end() + 2].strip().startswith("%")
            dec = len(raw.split(".")[1]) if "." in raw else 0
            ok = any(abs(x - abs(v)) <= (0.15 if pct else max(abs(v) * 0.0035, 10 ** -6))
                     or abs(x - abs(v)) <= 0.5 * 10 ** -dec + 1e-9           # làm tròn hợp lý (RSI 45.5 → "45")
                     for v in vals)
            if not ok:
                e.append(f"số {raw}{'%' if pct else ''} không có trong dữ liệu thật: \"{t[:60]}\"")
    return e


def banned_errors(texts: list[str], words: list[str]) -> list[str]:
    e = []
    for t in texts:
        for w in words:
            if re.search(rf"(?i)\b{re.escape(w)}\b", t or ""):
                e.append(f"có từ cấm \"{w}\": \"{(t or '')[:60]}\"")
    return e


# ------------------------------------------------------------------ 2. AI xem lại hình
def contact_sheet(video: Path, out: Path, n: int = 10) -> Path:
    """n khung rải đều video, ghép 5 cột (mỗi khung 432×768) + ghi giây."""
    dur = probe(video)["duration"] or 1
    frames = []
    tmp = out.parent / "_qa_frames"
    tmp.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        t = dur * (i + 0.5) / n
        f = tmp / f"f{i:02d}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                        "-vf", "scale=432:768", str(f)], check=True)
        frames.append((t, f))
    cols = 5
    rows = (n + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 432, rows * 800), (255, 255, 255))
    from PIL import ImageDraw
    d = ImageDraw.Draw(sheet)
    for i, (t, f) in enumerate(frames):
        x, y = (i % cols) * 432, (i // cols) * 800
        sheet.paste(Image.open(f), (x, y))
        d.text((x + 8, y + 772), f"#{i + 1}  {t:.1f}s", font=sans("Bold", 22), fill=(0, 0, 0))
    sheet.save(out, quality=88)
    for _, f in frames:
        f.unlink(missing_ok=True)
    return out


CHECKLIST = """Bạn là người duyệt video Reels trước khi đăng Facebook. Ảnh là 10 khung hình rải đều của 1 video dọc 1080×1920
(số # và giây ghi dưới mỗi khung). Kiểm tra KỸ từng khung theo danh sách lỗi đã từng gặp:
- chữ bị cắt mất, tràn ra ngoài khung hình, chữ đè lên chữ, hoặc tiêu đề bị "…" mất chữ
- ký tự lạ/ô vuông/sai dấu (vd. "~" hiện thành "-" làm sai nghĩa số liệu)
- nhãn (SUPPORT/RESISTANCE/giá) bị che, bị cắt, đè lên nhau không đọc được
- biểu đồ/kênh/đường chỉ báo tràn ra ngoài vùng biểu đồ, đè lên tiêu đề hoặc cột giá
- nến mảnh như sợi chỉ, biểu đồ trống/không có nến khi lẽ ra phải có, hình vỡ/nhiễu
- phụ đề sai chính tả nặng, dính chữ, quá dài che biểu đồ
- logo/thương hiệu bị méo, mất; khung đen/trắng trống bất thường giữa video (khung cuối mờ dần là bình thường)
Chỉ báo lỗi THẬT nhìn thấy rõ; hiệu ứng đang chuyển cảnh/mờ dần/bật lên là bình thường."""


def visual_review(sheet: Path, context: str = "") -> dict:
    from src.content.llm import review_image
    schema = {"type": "object", "properties": {
        "ok": {"type": "boolean"},
        "issues": {"type": "array", "items": {"type": "object", "properties": {
            "frame": {"type": "integer"}, "problem": {"type": "string"},
            "severity": {"type": "string", "enum": ["major", "minor"]}},
            "required": ["frame", "problem", "severity"]}}},
        "required": ["ok", "issues"]}
    return review_image(CHECKLIST + ("\n" + context if context else ""), sheet,
                        "Duyệt video. severity=major khi người xem KHÔNG đọc được/hiểu sai (chữ bị che mất, cắt mất, "
                        "đè lên nhau không đọc được, ký tự sai làm đổi nghĩa, khung hỏng); minor khi vẫn đọc được "
                        "nhưng chưa đẹp (sát nhau, hơi chồng). ok=false chỉ khi có lỗi major.", schema)


# ------------------------------------------------------------------ tổng hợp
def run(video: Path, folder: Path, *, min_dur: float, max_dur: float, texts: list[str] | None = None,
        facts: dict | None = None, banned: list[str] | None = None, voices: tuple | None = None,
        context: str = "", ai: bool = True) -> dict:
    """Trả {ok, errors, notes, fix, sheet}. errors = lỗi NẶNG (chặn đăng); notes = lỗi nhẹ (vẫn đăng, ghi lại).
    fix luôn là 'rewrite' khi có lỗi: dựng lại cùng kịch bản cho ra đúng hình cũ, phải viết kịch bản/bố cục mới."""
    info = probe(video)
    errors = media_errors(info, min_dur, max_dur)
    fix = "rerender" if errors else None
    content = []
    if texts and facts:
        content += number_errors(texts, facts)
    if texts and banned:
        content += banned_errors(texts, banned)
    if voices:
        content += voice_errors(*voices)
    if content:
        errors += content
        fix = "rewrite"
    sheet = contact_sheet(video, folder / "qa_sheet.jpg")
    notes = []
    if ai:
        try:
            r = visual_review(sheet, context)
            for it in r.get("issues") or []:
                msg = f"[AI xem hình] khung #{it.get('frame')}: {it.get('problem')}"
                (errors if it.get("severity") == "major" else notes).append(msg)
        except Exception as exc:                       # AI xem hình lỗi → không chặn đăng, chỉ ghi chú
            notes.append(f"không chạy được bước AI xem hình: {exc}")
    if errors:
        fix = "rewrite"
    report = {"ok": not errors, "errors": errors, "notes": notes, "fix": fix, "sheet": str(sheet), "media": info}
    (folder / "qa.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


def fail_alert(name: str, report: dict, attempts: int):
    """Báo Telegram: video không đạt, không đăng – kèm ảnh khung."""
    from src.publish import telegram
    lines = "\n".join(f"• {e}" for e in report["errors"][:8])
    telegram.send_preview(f"❌ {name}: video KHÔNG ĐẠT kiểm tra sau {attempts} lần dựng – KHÔNG đăng.",
                          f"Lỗi tìm thấy:\n{lines}\n\nEm cần anh xem giúp (ảnh các khung hình kèm theo).",
                          [Path(report["sheet"])])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--min", type=float, default=20)
    ap.add_argument("--max", type=float, default=95)
    ap.add_argument("--no-ai", action="store_true")
    a = ap.parse_args()
    v = Path(a.video)
    r = run(v, v.parent, min_dur=a.min, max_dur=a.max, ai=not a.no_ai)
    print(json.dumps({k: r[k] for k in ("ok", "errors", "notes", "fix", "sheet")}, ensure_ascii=False, indent=1))
