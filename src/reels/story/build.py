"""Reels STORYTELLING (Page Decode Global & Partner): kịch bản kể chuyện → giọng đọc → video nền (Pixabay/Mixkit)
đổi theo từng câu → lớp phủ thương hiệu Decode (tông tím chàm, logo, tiêu đề chữ có chân, phụ đề vàng) → đoạn kết logo.

    JOB=decode-partner python -m src.reels.story.build                 # AI viết + dựng
    JOB=decode-partner python -m src.reels.story.build --script x.json # dựng lại (giữ giọng đã có)
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from src.config import CONFIG, OUTPUT, ROOT
from src.design.common import sans, serif, wrap
from src.reels import render as old, voice
from src.reels.edu.build import mix
from src.reels.phonetic import spoken
from src.reels.qa import clean
from src.reels.story import stock

W, H, FPS = 1080, 1920, 30
INDIGO, GOLD, WHITE = (26, 22, 72), (247, 205, 15), (255, 255, 255)
XF = 0.45                     # chuyển cảnh mờ chồng giữa 2 đoạn video nền
GAP = 0.3                     # nghỉ sau mỗi câu
END = 3.6                     # đoạn kết logo
_TAG = re.compile(r"\[y\](.*?)\[/y\]")
TRANS = ["fade", "smoothleft", "circleopen", "dissolve", "zoomin", "smoothup", "radial", "fadeblack"]


def plain(t: str) -> str:
    return _TAG.sub(lambda m: m.group(1), t)


# ------------------------------------------------------------------ video nền
def _probe_dur(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def segment(src: Path, out: Path, dur: float, k: int):
    """1 đoạn nền dọc 1080×1920: phủ kín khung, máy quay đẩy chậm (xen kẽ đẩy vào / kéo ra), chỉnh màu điện ảnh."""
    sd = _probe_dur(src)
    off = max(0.0, min(sd - dur - 0.1, sd * 0.2)) if sd > dur + 0.5 else 0.0
    z0, z1 = (1.0, 1.09) if k % 2 == 0 else (1.09, 1.0)
    nfr = max(1, int(dur * FPS))
    vf = (f"fps={FPS},scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
          f"zoompan=z='{z0}+({z1}-{z0})*on/{nfr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps={FPS},"
          f"setsar=1,eq=saturation=0.82:contrast=1.06:brightness=-0.03")
    cmd = ["ffmpeg", "-v", "error", "-y", "-stream_loop", "-1", "-ss", f"{off:.2f}", "-i", str(src), "-t", f"{dur:.3f}",
           "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(out)]
    subprocess.run(cmd, check=True)


def background(clips: list[Path], durs: list[float], folder: Path) -> Path:
    segs = []
    for k, (c, d) in enumerate(zip(clips, durs)):
        s = folder / f"seg_{k:02d}.mp4"
        segment(c, s, d + XF, k)
        segs.append(s)
    out = folder / "bg.mp4"
    if len(segs) == 1:
        segs[0].replace(out)
        return out
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for s in segs:
        cmd += ["-i", str(s)]
    f, prev, start = [], "[0:v]", 0.0
    for k in range(1, len(segs)):
        start += durs[k - 1]
        lab = f"[v{k}]"
        f.append(f"{prev}[{k}:v]xfade=transition={TRANS[(k - 1) % len(TRANS)]}:duration={XF}:offset={start:.3f}{lab}")
        prev = lab
    cmd += ["-filter_complex", ";".join(f), "-map", prev, "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
            "-pix_fmt", "yuv420p", str(out)]
    subprocess.run(cmd, check=True)
    for s in segs:
        s.unlink(missing_ok=True)
    return out


# ------------------------------------------------------------------ lớp phủ
def _logo(name: str, h: int) -> Image.Image:
    im = Image.open(ROOT / "assets" / "brands" / "decode" / name).convert("RGBA")
    return im.resize((round(im.width * h / im.height), h), Image.LANCZOS)


def _grade() -> Image.Image:
    """Tông tím chàm + tối dần trên/dưới để chữ nổi."""
    g = Image.new("RGBA", (W, H), INDIGO + (60,))
    d = ImageDraw.Draw(g)
    for y in range(H):                                 # tối dần mịn ở trên (tiêu đề) và dưới (phụ đề), không lộ ranh giới
        top = 150 * max(0.0, 1 - y / 760) ** 2
        bot = 200 * max(0.0, (y - 760) / (H - 760)) ** 1.4
        a = int(60 + max(top, bot) * (195 / 255))
        d.line([(0, y), (W, y)], fill=INDIGO + (min(235, a),))
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2)
    vig = np.clip((r - 0.55) / 0.6, 0, 1) ** 1.6 * 200
    v = np.zeros((H, W, 4), np.uint8)
    v[..., 3] = vig.astype(np.uint8)
    g.alpha_composite(Image.fromarray(v, "RGBA"))
    return g


def _grain(n: int = 4) -> list:
    """Hạt phim: vài lớp nhiễu mịn luân phiên mỗi khung."""
    out = []
    rng = np.random.default_rng(3)
    for _ in range(n):
        a = np.zeros((H // 2, W // 2, 4), np.uint8)
        noise = rng.integers(0, 255, (H // 2, W // 2), dtype=np.uint8)
        a[..., 0] = a[..., 1] = a[..., 2] = noise
        a[..., 3] = 16
        out.append(Image.fromarray(a, "RGBA").resize((W, H), Image.NEAREST))
    return out


def _leak() -> Image.Image:
    """Lóe sáng vàng (light leak) – quét qua khi chuyển cảnh."""
    lay = Image.new("RGBA", (1500, 1500), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.ellipse([250, 250, 1250, 1250], fill=(255, 196, 70, 150))
    d.ellipse([500, 420, 1150, 1050], fill=(255, 236, 170, 120))
    return lay.filter(ImageFilter.GaussianBlur(160))


def _text(img, xy, text, font, col, alpha=1.0, anchor="mm", shadow=True):
    if alpha <= 0.01:
        return
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    if shadow:
        d.text((xy[0] + 3, xy[1] + 4), text, font=font, fill=(0, 0, 0, int(170 * alpha)), anchor=anchor)
    d.text(xy, text, font=font, fill=col + (int(255 * alpha),), anchor=anchor)
    img.alpha_composite(lay)


def _ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def overlay(img: Image.Image, t: float, spec: dict, beats: list, grade: Image.Image, mark: Image.Image,
            fx: dict | None = None):
    img.alpha_composite(grade)
    if fx:
        img.alpha_composite(fx["grain"][int(t * FPS) % len(fx["grain"])])
        for k, b in enumerate(beats[1:], 1):            # lóe sáng vàng quét qua mỗi lần chuyển cảnh
            dt = t - b["start"]
            if -0.45 < dt < 0.55:
                a = max(0.0, 1 - abs(dt - 0.05) / 0.5)
                lk = fx["leak"].copy()
                lk.putalpha(lk.getchannel("A").point(lambda v: int(v * a)))
                x = int(-700 + (dt + 0.45) * 1400) if k % 2 else int(W - 800 - (dt + 0.45) * 1400)
                img.alpha_composite(lk, (x, 200 + (k * 337) % 700))
    # dấu thương hiệu trên cùng: biểu tượng nữ thần + DECODE
    img.alpha_composite(mark, (W // 2 - mark.width // 2, 150))
    _text(img, (W // 2, 150 + mark.height + 26), "DECODE", serif(700, 34), WHITE, 0.92)
    # mở đầu: nhãn + tiêu đề lớn chữ có chân (4.5s đầu)
    k = min(_ease(t / 0.6), _ease((4.6 - t) / 0.6))
    if k > 0:
        f = sans("Bold", 26)
        kick = clean(spec.get("kicker", "CÂU CHUYỆN NGHỀ IB")).upper()
        tw = ImageDraw.Draw(img).textlength(kick, font=f) + 44
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(lay).rounded_rectangle([W / 2 - tw / 2, 330, W / 2 + tw / 2, 380], radius=25,
                                              fill=GOLD + (int(240 * k),))
        img.alpha_composite(lay)
        _text(img, (W / 2, 355), kick, f, INDIGO, k, shadow=False)
        tf = serif(700, 76)
        lines = wrap(ImageDraw.Draw(img), clean(spec["title"]).upper(), tf, 940, max_lines=3)
        for n, ln in enumerate(lines):
            _text(img, (W / 2, 450 + n * 92 + 30 * (1 - k)), ln, tf, WHITE, k)
    # phụ đề giữa màn hình: cụm ≤ 7 từ, từ đang đọc + từ khoá tô vàng
    cur = next((b for b in beats if b["start"] <= t < b["start"] + b["dur"]), None)
    if cur:
        _subtitle(img, t, cur)


def _subtitle(img, t, b):
    words, gold = [], []
    pos = 0
    text = re.sub(r"\s+([.,!?;:…])", r"\1", clean(b["text"]))
    text = re.sub(r"\[y\]([^\[]*?)\s*\[/y\]([.,!?;:…])", r"[y]\1\2[/y]", text)   # "…[/y]." → dấu câu dính vào từ
    for m in _TAG.finditer(text):
        for w in text[pos:m.start()].split():
            words.append(w); gold.append(False)
        for w in m.group(1).split():
            words.append(w); gold.append(True)
        pos = m.end()
    for w in text[pos:].split():
        words.append(w); gold.append(False)
    if not words:
        return
    frac = (t - b["voice_at"]) / max(0.3, b["vdur"] * 0.95)
    weights = [len(w) + 2 for w in words]
    acc, idx, tot = 0, len(words) - 1, sum(weights)
    for i, wt in enumerate(weights):
        if frac < (acc + wt) / tot:
            idx = i
            break
        acc += wt
    w_start = b["voice_at"] + max(0.3, b["vdur"] * 0.95) * acc / tot
    pop = max(0.0, 1 - (t - w_start) / 0.18)                 # từ vừa được đọc bật lên
    g0 = idx // 7 * 7
    grp = list(range(g0, min(len(words), g0 + 7)))
    f = sans("ExtraBold", 60)
    d = ImageDraw.Draw(img)
    sp = d.textlength(" ", font=f)
    lines, cur, cw = [], [], 0.0
    for i in grp:
        wd = d.textlength(words[i], font=f)
        if cur and cw + sp + wd > 900:
            lines.append(cur); cur, cw = [], 0.0
        cur.append((i, wd)); cw += (sp if cw else 0) + wd
    lines.append(cur)
    y = 1240 - (len(lines) - 1) * 40
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    ytop = y - 52
    ybot = y + (len(lines) - 1) * 80 + 52
    maxw = max(sum(wd for _, wd in ln) + sp * (len(ln) - 1) for ln in lines)
    band = Image.new("RGBA", img.size, (0, 0, 0, 0))     # dải nền tối mờ sau phụ đề: rõ chữ trên mọi video nền
    ImageDraw.Draw(band).rounded_rectangle([W / 2 - maxw / 2 - 40, ytop, W / 2 + maxw / 2 + 40, ybot], radius=34,
                                           fill=(12, 10, 34, 150))
    img.alpha_composite(band.filter(ImageFilter.GaussianBlur(10)))
    for ln in lines:
        lw = sum(wd for _, wd in ln) + sp * (len(ln) - 1)
        x = W / 2 - lw / 2
        for i, wd in ln:
            col = GOLD if (gold[i] or i == idx) else WHITE
            a = 255 if i <= idx else 150
            yy = y - (14 * pop if i == idx else 0)
            ld.text((x + 3, yy + 4), words[i], font=f, fill=(0, 0, 0, 190), anchor="lm")
            ld.text((x, yy), words[i], font=f, fill=col + (a,), anchor="lm")
            x += wd + sp
        y += 80
    img.alpha_composite(lay)


def end_card(t: float, logo: Image.Image, slogan: str = "", slogan_at: float = 0.6) -> Image.Image:
    img = Image.new("RGBA", (W, H), INDIGO + (255,))
    k = _ease(t / 0.6)
    lg = logo.copy()
    lg.putalpha(lg.getchannel("A").point(lambda v: int(v * k)))
    img.alpha_composite(lg, (W // 2 - lg.width // 2, 560 + int(40 * (1 - k))))
    if 0.7 < t < 1.9:                                    # vệt sáng quét chéo qua logo
        band = Image.new("L", (W, H), 0)
        x = -400 + (t - 0.7) / 1.2 * (W + 800)
        ImageDraw.Draw(band).polygon([(x, 500), (x + 120, 500), (x - 260, 1300), (x - 380, 1300)], fill=150)
        band = band.filter(ImageFilter.GaussianBlur(30))
        shine = Image.new("RGBA", (W, H), (255, 236, 170, 0))
        shine.putalpha(ImageChops.multiply(band, img.getchannel("A")))
        lm = Image.new("L", (W, H), 0)
        lm.paste(lg.getchannel("A"), (W // 2 - lg.width // 2, 560 + int(40 * (1 - k))))
        shine.putalpha(ImageChops.multiply(shine.getchannel("A"), lm))
        img.alpha_composite(shine)
    k2 = _ease((t - 0.5) / 0.6)
    y = 560 + lg.height + 70
    _text(img, (W / 2, y), "DECODE GLOBAL & PARTNER", serif(700, 54), WHITE, k2, shadow=False)
    _text(img, (W / 2, y + 70), "Đối tác IB của DecodeFX", sans("Medium", 32), GOLD, k2, shadow=False)
    k3 = _ease((t - slogan_at) / 0.7)                 # slogan hiện theo giọng đọc
    tail = slogan.split("–", 1)[-1].strip() if slogan else ""
    yy = y + 150
    if tail:
        d0 = ImageDraw.Draw(img)
        sf = serif(500, 40)
        for ln in wrap(d0, f"“{tail}”", sf, 880, max_lines=3):
            _text(img, (W / 2, yy + 20 * (1 - k3)), ln, sf, (240, 232, 205), k3, shadow=False)
            yy += 56
        yy += 30
    _text(img, (W / 2, yy + 20), (CONFIG.get("brand") or {}).get("handle", ""), sans("Bold", 30), WHITE, k2 * 0.8,
          shadow=False)
    return img


# ------------------------------------------------------------------ dựng
def make(spec: dict, folder: Path, music: Path | None = None) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "script.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    slogan = (CONFIG.get("story") or {}).get("slogan", "")
    says = [spoken(b.get("say") or plain(b["text"])) for b in spec["beats"]] + ([spoken(slogan)] if slogan else [])
    vi = int((CONFIG.get("story") or {}).get("voice_index", 3))
    wavs = voice.synth(says, folder / "voice", voice_index=vi)
    vdurs = [voice.duration(w) for w in wavs]
    s_wav, s_dur = (wavs[-1], vdurs[-1]) if slogan else (None, 0.0)
    if slogan:
        wavs, vdurs = wavs[:-1], vdurs[:-1]
    durs = [v + GAP + (0.3 if k == 0 else 0) for k, v in enumerate(vdurs)]
    used, clips = set(), []
    for k, b in enumerate(spec["beats"]):
        c = stock.fetch(list(b.get("queries") or []) + ["city night", "business people"], used, seed=k)
        if c is None:
            raise RuntimeError(f"Không tìm được video nền cho câu {k + 1}")
        clips.append(c)
    bg = background(clips, durs, folder)
    beats, t = [], 0.0
    for k, (b, d, vd) in enumerate(zip(spec["beats"], durs, vdurs)):
        va = t + (0.3 if k == 0 else 0.05)
        beats.append({"text": b["text"], "start": t, "dur": d, "voice_at": va, "vdur": vd})
        t += d
    main_len = t
    s_at = 0.9                                          # slogan đọc sau khi logo hiện
    end_len = max(END, s_at + s_dur + 1.6) if slogan else END
    total = main_len + end_len
    grade, mark = _grade(), _logo("official/decode_mark_dark_bg.png", 86)
    fx = {"grain": _grain(), "leak": _leak()}
    tp = beats[max(1, round(len(beats) * 0.55))]["start"]      # bước ngoặt câu chuyện
    logo_full = _logo("official/decode_mark_dark_bg.png", 400)
    silent = folder / "reel.video.mp4"
    rd = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(bg), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                          stdout=subprocess.PIPE)
    wr = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                           "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
    last = None
    thumb = None
    for fno in range(int(total * FPS)):
        t = fno / FPS
        if t < main_len:
            raw = rd.stdout.read(W * H * 3)
            if len(raw) == W * H * 3:
                last = Image.frombytes("RGB", (W, H), raw)
            img = last.convert("RGBA")
            if 0 <= t - tp < 0.4:                              # bước ngoặt: lệch màu RGB thoáng qua
                sh = int(14 * (1 - (t - tp) / 0.4))
                r_, g_, b_, a_ = img.split()
                img = Image.merge("RGBA", (ImageChops.offset(r_, sh, 0), g_, ImageChops.offset(b_, -sh, 0), a_))
            overlay(img, t, spec, beats, grade, mark, fx)
            if 0 <= t - tp < 0.28:                             # chớp sáng
                img = Image.blend(img, Image.new("RGBA", (W, H), (255, 250, 235, 255)), 0.75 * (1 - (t - tp) / 0.28))
            if thumb is None and t >= 2.4:
                thumb = img.convert("RGB")
            if t > main_len - 0.5:                         # mờ dần sang đoạn kết
                img = Image.blend(img, end_card(0, logo_full, slogan, s_at), (t - (main_len - 0.5)) / 0.5)
        else:
            img = end_card(t - main_len, logo_full, slogan, s_at)
        k = min(1.0, t / 0.3, (total - t) / 0.4)
        out = img.convert("RGB")
        if k < 1:
            out = Image.blend(Image.new("RGB", (W, H)), out, max(0.0, k))
        wr.stdin.write(out.tobytes())
    rd.stdout.close()
    rd.wait()
    wr.stdin.close()
    if wr.wait():
        raise RuntimeError("ffmpeg lỗi khi dựng hình")
    events = ([(b["start"] - 0.2, "whoosh", 0.3) for b in beats[1:]] + [(main_len + 0.4, "ting", 0.35)]
              + [(max(0.0, tp - 2.2), "riser", 0.45), (tp, "boom", 0.7)])
    clips_ = [(w, b["voice_at"]) for w, b in zip(wavs, beats)] + ([(s_wav, main_len + s_at)] if s_wav else [])
    mix(silent, clips_, events, total, folder / "reel.mp4", music)
    silent.unlink(missing_ok=True)
    (thumb or Image.new("RGB", (W, H), INDIGO)).save(folder / "thumb.jpg", quality=92)
    return {"video": folder / "reel.mp4", "thumb": folder / "thumb.jpg", "duration": round(total, 1),
            "voices": (wavs, says)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.script:
        spec = json.loads(Path(a.script).read_text(encoding="utf-8"))
    else:
        from src.reels.story import script
        spec = script.write()
    folder = Path(a.out) if a.out else OUTPUT / "reels" / "story"
    r = make(spec, folder, old.pick_music())
    print(json.dumps({k: str(v) for k, v in r.items() if k != "voices"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
