"""Dò điểm 'drop' (đoạn nhạc bùng lên mạnh nhất) để căn đúng khoảnh khắc giá cán TP."""
import subprocess
from pathlib import Path

import numpy as np


def drop_time(path: Path, min_t: float = 6.0) -> float:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-t", "100", "-i", str(path), "-ac", "1", "-ar", "8000",
                          "-f", "s16le", "-"], capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32)
    hop = 800                                          # 0.1 giây
    n = len(a) // hop
    if n < 120:
        return min_t
    e = np.sqrt((a[: n * hop].reshape(n, hop) ** 2).mean(1))
    e = np.convolve(e, np.ones(3) / 3, "same")
    best, bt = -1e9, min_t
    for i in range(int(min_t * 10), n - 30):
        after, before = e[i: i + 20].mean(), e[max(0, i - 30): i].mean()
        low = e[max(0, i - 6): i].mean()               # ngay trước drop thường lắng xuống
        score = after - before + 0.5 * (after - low)
        if score > best:
            best, bt = score, i / 10
    return bt


def beat_period(path: Path, start: float, dur: float = 12.0) -> float:
    """Chu kỳ phách (giây) quanh đoạn sau drop – để nảy/giật đúng nhịp nhạc."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, start):.2f}", "-t", f"{dur}", "-i", str(path),
                          "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32)
    hop = 80                                           # 10 ms
    n = len(a) // hop
    if n < 300:
        return 0.5
    e = np.sqrt((a[: n * hop].reshape(n, hop) ** 2).mean(1))
    on = np.maximum(0, np.diff(e))
    on -= on.mean()
    ac = np.correlate(on, on, "full")[len(on) - 1:]
    lo, hi = 30, 80                                    # 0.30–0.80 s (75–200 BPM)
    lag = lo + int(np.argmax(ac[lo:hi]))
    return lag / 100


def envelope(path: Path, ss: float, total: float, fps: int = 30):
    """Năng lượng nhạc theo từng khung hình của video (đã tính độ lệch ss) → (mức to 0..1, cú đánh 0..1).
    Dùng để giật/rung/nảy ĐÚNG theo nhịp trống của bài."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, ss):.3f}", "-t", f"{total + 1:.2f}", "-i", str(path),
                          "-ac", "1", "-ar", "12000", "-f", "s16le", "-"], capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32)
    lead = int(max(0.0, -ss) * 12000)                  # ss âm = nhạc vào muộn
    a = np.concatenate([np.zeros(lead, np.float32), a])
    hop = 12000 // fps
    n = int(total * fps) + 1
    a = np.pad(a, (0, max(0, n * hop - len(a))))[: n * hop]
    e = np.sqrt((a.reshape(n, hop) ** 2).mean(1))
    lvl = e / (np.percentile(e, 98) + 1e-6)
    on = np.maximum(0, np.diff(e, prepend=e[0]))
    on = on / (np.percentile(on, 99) + 1e-6)
    return np.clip(lvl, 0, 1), np.clip(on, 0, 1)


def shape(path: Path, ss: float, t_count: float, t_reveal: float, t_drop: float, total: float, out: Path) -> Path:
    """Dựng nhạc có kịch tính như video mẫu (đo được: đếm ngược ~ -28 dB → tăng dần → drop ~ -6 dB):
    - câu đố: nhạc NHỎ + ĐỤC (như nghe qua tường)
    - đếm ngược → lộ đáp án: to dần, bớt đục (dồn nén)
    - 0.2s trước drop: TẮT hẳn (khoảng lặng)
    - drop: nhạc đầy đủ, TĂNG BASS, to hết cỡ – đúng lúc nến vọt."""
    gap = 0.2
    pre = f"adelay={int(-ss * 1000)}|{int(-ss * 1000)}," if ss < 0 else ""
    a, b, c = t_count, t_reveal, t_drop - gap
    fc = (f"[0:a]aresample=48000,{pre}loudnorm=I=-12:TP=-1.0,asplit=4[s1][s2][s3][s4];"
          f"[s1]atrim=0:{a:.3f},lowpass=f=600,volume=0.42[p1];"
          f"[s2]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,lowpass=f=900,"
          f"volume='0.42+0.2*t/{b - a:.3f}':eval=frame[p2];"
          f"[s3]atrim={b:.3f}:{c:.3f},asetpts=PTS-STARTPTS,highpass=f=250,"
          f"volume='0.62+0.3*t/{max(0.1, c - b):.3f}':eval=frame[p3];"
          f"anullsrc=r=48000:cl=stereo,atrim=0:{gap}[p4];"
          f"[s4]atrim={t_drop:.3f}:{total + 0.5:.3f},asetpts=PTS-STARTPTS,bass=g=6:f=90,volume=1.25[p5];"
          f"[p1][p2][p3][p4][p5]concat=n=5:v=0:a=1,alimiter=limit=0.95[out]")
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, ss):.3f}", "-i", str(path), "-filter_complex", fc,
           "-map", "[out]", "-ac", "2", "-ar", "48000", str(out)]
    if subprocess.run(cmd).returncode:
        raise RuntimeError("ffmpeg lỗi khi dựng nhạc")
    return out
