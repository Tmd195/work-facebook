"""Reels thị trường cho Page Global: số liệu thật → AI viết lời (tiếng Anh) → giọng nhân bản → video + ảnh bìa.

    JOB=cwg-global python -m src.reels.mkt.build --symbol XAUUSD          # AI viết + dựng
    JOB=cwg-global python -m src.reels.mkt.build --script x.json --fast   # dựng lại, không gọi giọng (xem hình nhanh)
"""
import argparse
import json
import subprocess
from pathlib import Path

from src.config import CONFIG, OUTPUT, ROOT, STATE
from src.content.llm import generate_json
from src.reels import render as old, voice
from src.reels.edu.build import mix
from src.reels.mkt import data as D, render as R

# số nến trên màn hình theo nội dung câu: nói vùng giá → phóng vào; nói xu hướng → lùi ra
ZOOM = {"support": 32, "resistance": 32, "lows": 40, "zoom": 30, "ema": 62, "bollinger": 56, "channel": 62,
        "rsi": 50, "stoch": 50, "none": 48}
OVERLAYS = ["none", "ema", "bollinger", "channel", "support", "resistance", "lows", "rsi", "stoch", "zoom"]
SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "WTI", "USDCHF", "DXY"]
FILE = STATE / "mkt_reels.json"
VOICE_REF = ROOT / "assets" / "private" / "voice_ref_cwg_global.mp3"

SYSTEM = """You write short market Reels (30-50 seconds) for the Facebook Page "CWG Markets Global" (English, traders in
Southeast Asia). Style: like a broker's daily chart story – one asset, one clear technical idea, calm and factual.
STRUCTURE (30-45 seconds total): a punchy title (2-4 words, e.g. "GOLD'S BOUNCE?", "AUDUSD'S UPTREND", "XAUUSD UNDER PRESSURE"), a spoken hook,
3-5 short story lines that walk through the REAL chart, each tied to one on-screen overlay, then a closing question.
RULES: use ONLY the numbers given in the facts (round sensibly); never invent news, prices or probabilities;
no buy/sell signals, no entry/SL/TP, no profit promises; describe what traders watch and possible scenarios
("if it holds… if it breaks…"). Spoken lines must sound natural when read aloud: numbers written as people say them
(e.g. "four thousand one hundred", "zero point six nine"), no symbols like % or $ (say "percent", "dollars").
Overlays available: none, ema (EMA 20/50), bollinger, channel (regression channel of the last 60 four-hour bars), support, resistance,
lows (repeated lows / double-triple bottom – only if facts.repeated_lows exists), rsi, stoch, zoom (zoom to recent bars).
Use 2-4 different overlays that match what you say.
SUBTITLES: for the hook and every line also give the on-screen subtitle ("hook_text", "text") = the same sentence
written for reading, with digits and symbols (e.g. "Down 3.4% this month, below the 20 and 50 EMAs.", "0.6905").
Never use the "~" character (write "about" or just the number). Never mention India, Japan, South Korea, Indonesia or Malaysia."""

SCHEMA = {"type": "object", "properties": {
    "title": {"type": "string"}, "hook": {"type": "string"}, "hook_text": {"type": "string"},
    "lines": {"type": "array", "items": {"type": "object", "properties": {
        "say": {"type": "string"}, "text": {"type": "string"}, "overlay": {"type": "string", "enum": OVERLAYS}},
        "required": ["say", "text", "overlay"]}},
    "question": {"type": "string"}, "caption": {"type": "string"}, "hashtags": {"type": "array", "items": {"type": "string"}}},
    "required": ["title", "hook", "hook_text", "lines", "question", "caption", "hashtags"]}


def _state() -> dict:
    return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {"done": []}


def next_symbol() -> str:
    """Xoay vòng tài sản, ưu tiên mã chưa làm gần đây."""
    done = _state()["done"]
    return min(SYMBOLS, key=lambda s: (done[::-1].index(s) * -1 if s in done else -999, SYMBOLS.index(s)))


def mark_done(symbol: str, title: str = ""):
    st = _state()
    st["done"] = (st["done"] + [symbol])[-30:]
    st.setdefault("titles", []).append(title)
    st["titles"] = st["titles"][-40:]
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def write(symbol: str) -> dict:
    m = D.load(symbol)
    recent = _state().get("titles", [])[-12:]
    user = (f"Asset: {symbol}\nFacts (real data, H4 chart = 4-hour candles; say 'on the four-hour chart'):\n{json.dumps(m.facts, ensure_ascii=False)}\n"
            f"Recent titles of the channel (do not repeat): {recent}\n"
            "Write the Reel. TOTAL video must stay under 45 seconds: hook ≤ 9 words, exactly 3-4 lines, each ≤ 16 words "
            "(short, punchy, one idea per line), question ≤ 9 words "
            "(e.g. 'Would you buy, sell or wait?' or a sharper question about the setup). "
            "caption: 40-80 words, first line = title in CAPS, then 2-4 short lines with emoji bullets; no hashtags inside.")
    s = generate_json(SYSTEM, user, SCHEMA)
    s["symbol"] = symbol
    s["lines"] = [x for x in s["lines"] if x.get("say")][:4]
    if not any(x["overlay"] != "none" for x in s["lines"]):
        s["lines"][-1]["overlay"] = "support"
    return s


def _voices(spec: dict, folder: Path, fast: bool) -> list:
    texts = [spec["hook"]] + [x["say"] for x in spec["lines"]] + [spec["question"]]
    if fast:
        return [(None, max(1.4, len(t.split()) * 0.36)) for t in texts]
    paths = voice.synth(texts, folder / "voice", lang="en", ref=VOICE_REF)
    return [(p, voice.duration(p)) for p in paths]


def timeline(spec: dict, voices: list) -> dict:
    """Mốc thời gian các cảnh + thời điểm từng chỉ báo hiện."""
    vi = iter(voices)
    hook = next(vi)
    # câu mở đầu đọc vắt qua cả cảnh chuyển + click logo (tiêu đề chỉ ~2s như mẫu); câu dài thì kéo intro
    t_intro = max(2.2, hook[1] + 0.25 + 0.3 - (0.8 + R.STING))
    t_trans = 0.8
    c0 = t_intro + t_trans + R.STING
    t, overlays, clips, sub, sub_t = 0.3, [], [(hook[0], 0.25)], None, None
    subs = [(spec.get("hook_text") or spec["hook"], 0.25, hook[1])]              # phụ đề: (câu, giây bắt đầu toàn video, thời lượng)
    cam = []                                           # máy quay: (giây trong cảnh biểu đồ, số nến hiện)
    for line in spec["lines"]:
        p, dur = next(vi)
        clips.append((p, c0 + t))
        subs.append((line.get("text") or line["say"], c0 + t, dur))
        cam.append((t, ZOOM.get(line["overlay"], 48)))
        if line["overlay"] in ("rsi", "stoch") and sub is None:
            sub, sub_t = line["overlay"], t
        elif line["overlay"] not in ("none", "rsi", "stoch"):
            overlays.append((line["overlay"], t + 0.2))
        t += dur + 0.35
    t_chart = t + 0.6
    reveal = min(t_chart * 0.45, max(3.5, voices[1][1] + 0.3))
    q = next(vi)
    q0 = c0 + t_chart
    clips.append((q[0], q0 + 0.3))
    t_q = q[1] + 1.6
    t_end = 3.6
    cam = [(0.0, R.VIEW), (reveal, R.VIEW)] + [(max(reveal, a), b) for a, b in cam[1:]] + [(t_chart, 40)]
    return {"subs": subs, "cam": cam, "intro": t_intro, "trans": t_trans, "sting": R.STING, "chart": t_chart, "q": t_q, "end": t_end, "reveal": reveal,
            "overlays": overlays, "sub": sub, "sub_t": sub_t, "clips": [c for c in clips if c[0]], "q_voice": q[1]}


def frames(spec: dict, tl: dict, m):
    ch = R.Chart(m)
    segs = [("intro", tl["intro"]), ("trans", tl["trans"]), ("sting", tl["sting"]), ("chart", tl["chart"]),
            ("q", tl["q"]), ("end", tl["end"])]
    total = sum(x[1] for x in segs)
    for f in range(int(total * R.FPS)):
        t = f / R.FPS
        acc = 0.0
        for name, dur in segs:
            if t < acc + dur:
                lt = t - acc
                break
            acc += dur
        if name == "intro":
            img = R.intro(lt, dur, m.symbol, spec["title"])
        elif name == "trans":
            img = R.transition(lt, dur, m.symbol)
        elif name == "sting":
            img = R.sting(lt, dur, m.symbol)
        elif name == "chart":
            img = ch.frame(lt, tl["reveal"], tl["overlays"], tl["sub"], tl["sub_t"], dur, tl["cam"])
        elif name == "q":
            img = R.question(lt, dur, m.symbol, spec["question"], tl["q_voice"])
        else:
            img = R.ending(lt, dur)
        img = img.convert("RGB")
        if name in ("intro", "trans", "sting", "chart"):
            R.subtitle(img, t, tl["subs"], dark=name != "trans")
        k = min(1.0, t / 0.25, max(0.0, (total - t) / 0.5))
        if k < 1:
            from PIL import Image
            img = Image.blend(Image.new("RGB", img.size), img, k)
        yield img, t, name


def make(spec: dict, folder: Path, fast: bool = False, music: Path | None = None) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "script.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    m = D.load(spec["symbol"])
    tl = timeline(spec, _voices(spec, folder, fast))
    total = tl["intro"] + tl["trans"] + tl["sting"] + tl["chart"] + tl["q"] + tl["end"]
    silent = folder / "reel.video.mp4"
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{R.W}x{R.H}", "-r", str(R.FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                             "-crf", "19", "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
    thumb = None
    for img, t, name in frames(spec, tl, m):
        proc.stdin.write(img.tobytes())
        if name == "chart" and thumb is None and t > tl["intro"] + tl["trans"] + tl["sting"] + tl["chart"] - 0.5:
            thumb = img
    proc.stdin.close()
    if proc.wait():
        raise RuntimeError("ffmpeg lỗi khi dựng hình")
    c0 = tl["intro"] + tl["trans"] + tl["sting"]
    s0 = tl["intro"] + tl["trans"]
    events = [(0.05, "whoosh", 0.4), (tl["intro"], "whoosh", 0.45), (s0 + R.CLICK, "pop", 0.7),
              (s0 + R.CLICK + 0.3, "whoosh", 0.5), (c0 + tl["chart"], "whoosh", 0.4),
              (c0 + tl["chart"] + tl["q"], "ting", 0.4)] + [(c0 + s, "pop", 0.4) for _, s in tl["overlays"]]
    mix(silent, tl["clips"], events, total, folder / "reel.mp4", music)
    silent.unlink(missing_ok=True)
    # ảnh bìa: khung biểu đồ đầy đủ + tiêu đề
    cover = _cover(spec, m, thumb)
    cover.save(folder / "thumb.jpg", "JPEG", quality=92)
    return {"video": folder / "reel.mp4", "thumb": folder / "thumb.jpg", "duration": round(total, 1)}


def _cover(spec, m, chart_img):
    """Ảnh bìa = khung mở đầu đã hiện đủ (tiêu đề + cờ) – giống ảnh bìa của mẫu."""
    return R.intro(2.4, 2.6, m.symbol, spec["title"]).convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol")
    ap.add_argument("--script")
    ap.add_argument("--out")
    ap.add_argument("--fast", action="store_true")
    a = ap.parse_args()
    spec = json.loads(Path(a.script).read_text(encoding="utf-8")) if a.script else write(a.symbol or next_symbol())
    folder = Path(a.out) if a.out else OUTPUT / "reels" / spec["symbol"]
    r = make(spec, folder, a.fast, None if a.fast else old.pick_music())
    print(json.dumps({k: str(v) for k, v in r.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
