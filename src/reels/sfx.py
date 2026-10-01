"""Hiệu ứng âm thanh tự tổng hợp (không cần tải file): ting, vút (chuyển cảnh), bụp (chữ bật lên), bút (khoanh/kẻ).

render_track(events, total, path) → 1 file WAV chứa mọi hiệu ứng đúng thời điểm, để trộn cùng giọng + nhạc.
events: [(giây, kiểu, âm lượng 0-1)]
"""
import wave
from pathlib import Path

import numpy as np

SR = 48000


def _env(n, attack=0.004, decay=6.0):
    t = np.arange(n) / SR
    a = np.minimum(1, t / attack) if attack else 1
    return a * np.exp(-decay * t)


def ting(dur=0.9):
    """Tiếng chuông nhỏ trong trẻo (2 tầng hoà âm)."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * 1760 * t) + 0.5 * np.sin(2 * np.pi * 2637 * t) + 0.25 * np.sin(2 * np.pi * 3520 * t))
    return 0.35 * s * _env(n, 0.002, 5.5)


def whoosh(dur=0.45, rng=np.random.default_rng(3)):
    """Tiếng vút: nhiễu lọc dải, lên rồi xuống."""
    n = int(SR * dur)
    noise = rng.standard_normal(n)
    out, y1, y2 = np.zeros(n), 0.0, 0.0
    for i in range(n):                                   # lọc thông dải đơn giản, tần số quét lên
        fc = 400 + 3800 * (i / n)
        a = np.exp(-2 * np.pi * fc / SR)
        y1 = (1 - a) * noise[i] + a * y1
        y2 = (1 - a) * y1 + a * y2
        out[i] = y1 - y2
    shape = np.sin(np.pi * np.arange(n) / n) ** 2
    out = out * shape
    return 0.9 * out / (np.abs(out).max() + 1e-9)


def pop(dur=0.12):
    """Tiếng bụp ngắn: sin trượt tần số xuống."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = 900 * np.exp(-t * 28) + 180
    return 0.6 * np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.001, 30)


def pen(dur=0.6, rng=np.random.default_rng(7)):
    """Tiếng bút dạ khoanh trên giấy: nhiễu cao tần rung nhẹ."""
    n = int(SR * dur)
    noise = rng.standard_normal(n)
    hp = np.diff(noise, prepend=0)
    t = np.arange(n) / SR
    wob = 0.6 + 0.4 * np.sin(2 * np.pi * 9 * t)
    shape = np.minimum(1, t / 0.03) * np.minimum(1, (dur - t) / 0.08)
    return 0.16 * hp * wob * shape


KINDS = {"ting": ting, "whoosh": whoosh, "pop": pop, "pen": pen}
_CACHE: dict = {}


def render_track(events: list[tuple[float, str, float]], total: float, path: Path) -> Path:
    buf = np.zeros(int(SR * (total + 1)))
    for at, kind, gain in events:
        if kind not in _CACHE:
            _CACHE[kind] = KINDS[kind]()
        s = _CACHE[kind] * gain
        i = int(at * SR)
        if 0 <= i < len(buf):
            j = min(len(buf), i + len(s))
            buf[i:j] += s[: j - i]
    buf = np.clip(buf, -1, 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((buf * 32767).astype(np.int16).tobytes())
    return path
