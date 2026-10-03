"""Dựng video Reels 1080x1920 từ kịch bản: mỗi khung hình vẽ bằng Pillow rồi đẩy thẳng vào ffmpeg.

Cảnh: hook (chữ bật từng từ) → 3 cảnh nội dung (thẻ trắng: tiêu đề, nhãn, biểu đồ, các ý hiện dần theo lời đọc,
câu cảnh báo) → cảnh kêu gọi comment. Mỗi cảnh một kiểu vào/ra khác nhau; nền chuyển động chậm suốt video.
"""
import math
import random
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from src.config import CONFIG, ROOT
from src.design.common import sans, wrap
from src.reels import marks, sfx
from src.design.palette import ACCENT, DOWN, INK, MUTED, PRIMARY, UP

W, H, FPS = 1080, 1920, 30
PHOTOS = ROOT / "assets" / "private" / "photos"
MUSIC = ROOT / "assets" / "music"
CARD_X, CARD_W = 56, 1080 - 112
WHITE = (255, 255, 255)
RED_SOFT = (253, 236, 234)


# ------------------------------------------------------------------ tiện ích

def ease_out(t):
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3


def ease_back(t):
    t = min(1.0, max(0.0, t))
    c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def prog(t, start, dur):
    return min(1.0, max(0.0, (t - start) / dur))


def with_alpha(img: Image.Image, a: float) -> Image.Image:
    if a >= 0.999:
        return img
    out = img.copy()
    out.putalpha(out.getchannel("A").point(lambda v: int(v * max(0.0, a))))
    return out


def paste(dst: Image.Image, src: Image.Image, x: float, y: float, alpha: float = 1.0, scale: float = 1.0):
    if alpha <= 0.01:
        return
    if abs(scale - 1) > 0.005:
        src = src.resize((max(1, int(src.width * scale)), max(1, int(src.height * scale))), Image.BILINEAR)
        x -= (src.width - src.width / scale) / 2
        y -= (src.height - src.height / scale) / 2
    dst.alpha_composite(with_alpha(src, alpha), (int(x), int(y)))


def photos() -> list[Path]:
    return sorted(p for p in PHOTOS.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))


def center_x(path: Path) -> float:
    """Tâm cắt ngang của ảnh (assets/private/photos/photos.json) để giữ mặt khi cắt sang 9:16."""
    import json
    meta = PHOTOS / "photos.json"
    data = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {}
    return data.get(path.name, {}).get("cx", 0.5)


def cover(img: Image.Image, size, cx: float = 0.5) -> Image.Image:
    return ImageOps.fit(img.convert("RGB"), size, Image.LANCZOS, centering=(cx, 0.35))


def brand_bg(seed: int = 1) -> Image.Image:
    """Nền thương hiệu khi chưa có ảnh: gradient màu chủ đạo + dải nến mờ."""
    bg = Image.new("RGB", (W, H), PRIMARY)
    top = tuple(min(255, int(c * 1.35) + 8) for c in PRIMARY)
    bot = tuple(int(c * 0.45) for c in PRIMARY)
    d = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    rnd = random.Random(seed)
    for row, y0 in enumerate((210, 1760)):
        price = 0
        for i in range(36):
            o = price
            price += rnd.uniform(-1, 1.1)
            c = UP if price >= o else DOWN
            x = 14 + i * 30
            hi, lo = max(o, price) + rnd.uniform(0.2, 0.8), min(o, price) - rnd.uniform(0.2, 0.8)
            k = 18
            ld.line([(x + 6, y0 - hi * k), (x + 6, y0 - lo * k)], fill=c + (70,), width=2)
            ld.rectangle([x, y0 - max(o, price) * k, x + 12, y0 - min(o, price) * k - 1], fill=c + (80,))
    bg = bg.convert("RGBA")
    bg.alpha_composite(layer)
    return bg


def photo_bg(path: Path, blur: int = 16, dark: float = 0.55) -> Image.Image:
    img = cover(Image.open(path), (int(W * 1.12), int(H * 1.12)), center_x(path)).filter(ImageFilter.GaussianBlur(blur))
    img = Image.blend(img, Image.new("RGB", img.size, (8, 10, 14)), dark)
    return img.convert("RGBA")


# ------------------------------------------------------------------ thành phần

def brand_tag() -> Image.Image:
    name = CONFIG["brand"]["name"]
    f = sans("ExtraBold", 30)
    tw = int(ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(name, font=f))
    img = Image.new("RGBA", (tw + 64, 72), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, img.width - 1, 71], radius=36, fill=(0, 0, 0, 150))
    d.text((img.width / 2, 36), name, font=f, fill=WHITE, anchor="mm")
    return img


def text_block(lines: list[str], font, fill, width: int, align="mm", lh: float = 1.18) -> Image.Image:
    step = int(font.size * lh)
    img = Image.new("RGBA", (width, step * len(lines) + 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        if align == "mm":
            d.text((width / 2, step * i + step / 2 + 4), ln, font=font, fill=fill, anchor="mm")
        else:
            d.text((0, step * i + 4), ln, font=font, fill=fill)
    return img


@dataclass
class Part:
    img: Image.Image
    x: int
    y: int
    start: float          # giây kể từ đầu cảnh
    kind: str = "fade"    # fade | pop | rise | wipe | right
    sfx: str | None = None


@dataclass
class Overlay:
    """Lớp đánh dấu động (khoanh tròn, kẻ đường, dời SL...) vẽ lên 1 sơ đồ trong thẻ."""
    x: int
    y: int
    w: int
    h: int
    marks: list
    f: float
    starts: list


@dataclass
class Scene:
    duration: float
    voice: Path | None
    style: str                       # kiểu vào: up | right | zoom | drop
    parts: list[Part] = field(default_factory=list)
    card: tuple | None = None        # (y, h) thẻ trắng
    background: Image.Image | None = None
    voice_at: float = 0.3
    overlays: list[Overlay] = field(default_factory=list)


def _measure(text, font):
    return ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(text, font=font)


_D = ImageDraw.Draw(Image.new("RGB", (1, 1)))
INNER = CARD_W - 96


def _header(slide: dict, parts: list, y: int) -> int:
    tfont = sans("ExtraBold", 96 if len(slide["title"]) <= 14 else 80)
    title = text_block(wrap(_D, slide["title"].upper(), tfont, INNER, max_lines=2), tfont, INK, INNER)
    parts.append(Part(title, 48, y, 0.15, "pop", "pop"))
    y += title.height + 10
    pfont = sans("Bold", 40)
    pl = wrap(_D, slide["pill"], pfont, INNER - 80, max_lines=2)
    pw = int(max(_measure(s, pfont) for s in pl)) + 72
    ph = 62 + (len(pl) - 1) * 46
    pill = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pill)
    pd.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=31, fill=PRIMARY)
    for i, s in enumerate(pl):
        pd.text((pw / 2, 32 + i * 46), s, font=pfont, fill=ACCENT, anchor="mm")
    parts.append(Part(pill, 48 + (INNER - pw) // 2, y, 0.4, "wipe"))
    return y + ph + 28


def _bullet(text: str, width: int, size: int = 40, num: int | None = None, color=DOWN) -> Image.Image:
    f = sans("SemiBold", size)
    indent = 66 if num is not None else 50
    lines = wrap(_D, text, f, width - indent - 6, max_lines=3)
    step = int(size * 1.33)
    img = Image.new("RGBA", (width, step * len(lines) + 8), (0, 0, 0, 0))
    bd = ImageDraw.Draw(img)
    if num is None:
        bd.ellipse([4, size * 0.42, 4 + size * 0.58, size * 1.0], fill=color)
    else:
        r = size * 0.66
        bd.ellipse([0, size * 0.72 - r, 2 * r, size * 0.72 + r], fill=color)
        bd.text((r, size * 0.72), str(num), font=sans("ExtraBold", int(size * 0.8)), fill=WHITE, anchor="mm")
    for i, s in enumerate(lines):
        bd.text((indent, 4 + i * step), s, font=f, fill=INK)
    return img


def _warning(text: str) -> Image.Image:
    wfont = sans("Bold", 36)
    wl = wrap(_D, text, wfont, INNER - 110, max_lines=2)
    warn = Image.new("RGBA", (INNER, 40 + 46 * len(wl)), (0, 0, 0, 0))
    wd = ImageDraw.Draw(warn)
    wd.rounded_rectangle([0, 0, INNER - 1, warn.height - 1], radius=24, fill=RED_SOFT, outline=(240, 190, 184), width=2)
    wd.ellipse([22, warn.height / 2 - 24, 70, warn.height / 2 + 24], fill=DOWN)
    wd.text((46, warn.height / 2), "!", font=sans("ExtraBold", 34), fill=WHITE, anchor="mm")
    for i, s in enumerate(wl):
        wd.text((92, 20 + i * 46), s, font=wfont, fill=DOWN)
    return warn


def _framed(img: Image.Image, w: int, max_h: int) -> tuple[Image.Image, float]:
    """Thu ảnh sơ đồ về rộng w (cắt đáy nếu quá cao) + viền mảnh. → (ảnh, tỉ lệ)."""
    f = w / img.width
    h = min(max_h, int(img.height * f))
    small = img.resize((w, int(img.height * f)), Image.LANCZOS).crop((0, 0, w, h))
    frame = Image.new("RGBA", (w + 4, h + 4), (226, 226, 222, 255))
    frame.alpha_composite(small, (2, 2))
    return frame, f


def _times(n: int, duration: float) -> list[float]:
    """Thời điểm hiện từng ý, rải đều theo lời đọc."""
    span = max(1.5, (duration - 1.9) * 0.72)
    return [0.9 + span * k / max(1, n) for k in range(max(1, n))]


def _mark_starts(ms: list, times: list[float]) -> list[float]:
    out, used = [], {}
    for m in ms:
        st = min(len(times), max(1, int(m.get("step", 1)))) - 1
        k = used.get(st, 0)
        used[st] = k + 1
        out.append(times[st] + 0.2 + 0.55 * k)
    return out


def content_scene(slide: dict, idx: int, total: int, duration: float, voice: Path, visual) -> Scene:
    """Cảnh nội dung. slide["type"]: diagram | compare | steps. visual: sơ đồ đã dựng sẵn (xem build.py)."""
    parts, overlays = [], []
    y = _header(slide, parts, 52)
    kind = slide.get("type", "diagram")
    bullets = [b for b in slide.get("bullets") or [] if b.strip()][:3]

    if kind == "compare" and visual:
        cw = (INNER - 28) // 2
        cols = [visual["left"], visual["right"]]
        col_t = [0.8, max(1.6, duration * 0.42)]
        col_h = 0
        for c, (side, t0) in enumerate(zip(cols, col_t)):
            x0 = 48 + c * (cw + 28)
            yy = y
            color = UP if c == 0 else DOWN
            name = Image.new("RGBA", (cw, 70), (0, 0, 0, 0))
            nd = ImageDraw.Draw(name)
            nd.rounded_rectangle([0, 0, cw - 1, 69], radius=20, fill=color)
            nd.text((cw / 2, 35), side["name"].upper()[:18], font=sans("ExtraBold", 40), fill=WHITE, anchor="mm")
            parts.append(Part(name, x0, yy, t0, "pop", "pop"))
            yy += 84
            if side.get("img") is not None:
                frame, f = _framed(side["img"], cw - 4, 520)
                parts.append(Part(frame, x0, yy, t0 + 0.15, "rise"))
                ms = side.get("marks") or []
                overlays.append(Overlay(x0 + 2, yy + 2, frame.width - 4, frame.height - 4, ms, f,
                                        [t0 + 0.6 + 0.5 * k for k in range(len(ms))]))
                yy += frame.height + 16
            for k, pt in enumerate((side.get("points") or [])[:3]):
                b = _bullet(pt, cw, 32, color=color)
                parts.append(Part(b, x0, yy, t0 + 1.0 + 0.45 * k, "right", "ting" if k == 0 else None))
                yy += b.height + 6
            col_h = max(col_h, yy - y)
        y += col_h + 18
    elif kind == "steps":
        items = (slide.get("steps") or [])[:3] or [{"title": b, "text": ""} for b in bullets]
        times = _times(len(items), duration)
        if visual and visual.get("img") is not None:
            frame, f = _framed(visual["img"], INNER - 4, 470)
            parts.append(Part(frame, 46, y, 0.6, "rise"))
            ms = visual.get("marks") or []
            overlays.append(Overlay(48, y + 2, frame.width - 4, frame.height - 4, ms, f, _mark_starts(ms, times)))
            y += frame.height + 22
        for k, (it, t0) in enumerate(zip(items, times)):
            txt = it["title"] + (": " + it["text"] if it.get("text") else "")
            b = _bullet(txt, INNER, 40, num=k + 1, color=PRIMARY)
            parts.append(Part(b, 48, y, t0, "right", "ting"))
            y += b.height + 12
    else:                                                   # diagram
        times = _times(len(bullets), duration)
        if visual and visual.get("img") is not None:
            frame, f = _framed(visual["img"], INNER - 4, 760)
            parts.append(Part(frame, 46, y, 0.55, "rise"))
            ms = visual.get("marks") or []
            overlays.append(Overlay(48, y + 2, frame.width - 4, frame.height - 4, ms, f, _mark_starts(ms, times)))
            y += frame.height + 24
        for b_text, t0 in zip(bullets, times):
            b = _bullet(b_text, INNER, 40)
            parts.append(Part(b, 48, y, t0, "right", "ting"))
            y += b.height + 10

    y += 12
    if slide.get("warning"):
        warn = _warning(slide["warning"])
        parts.append(Part(warn, 48, y, max(1.8, duration * 0.8), "rise", "pop"))
        y += warn.height + 44
    num = Image.new("RGBA", (130, 50), (0, 0, 0, 0))
    ImageDraw.Draw(num).text((0, 0), f"{idx:02d}/{total:02d}", font=sans("ExtraBold", 28), fill=MUTED)
    parts.append(Part(num, CARD_W - 140, 18, 0.1, "fade"))
    card_y = max(210, min(330, (H - y) // 2 + 30))
    return Scene(duration, voice, ["up", "right", "zoom", "drop"][idx % 4], parts, (card_y, y), voice_at=0.35,
                 overlays=overlays)


def scene_sfx(scene: Scene, t0: float, first: bool) -> list[tuple[float, str, float]]:
    """Các tiếng hiệu ứng của 1 cảnh (thời điểm tuyệt đối trong video)."""
    ev = [] if first else [(max(0.0, t0 - 0.12), "whoosh", 0.55)]
    for p in scene.parts:
        if p.sfx:
            ev.append((t0 + p.start, p.sfx, {"ting": 0.45, "pop": 0.5}.get(p.sfx, 0.5)))
        elif p.kind == "pop":
            ev.append((t0 + p.start, "pop", 0.45))
    for ov in scene.overlays:
        for st in ov.starts:
            ev.append((t0 + st, "pen", 0.8))
    return [e for e in ev if e[0] < t0 + scene.duration]


def hook_scene(text: str, duration: float, voice: Path, background: Image.Image) -> Scene:
    """Chữ lớn bật lên từng dòng, dòng cuối tô nền màu nhấn."""
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    f = sans("ExtraBold", 100)
    lines = wrap(d, text.upper(), f, W - 140, max_lines=4)
    parts, y = [], 0
    total_h = len(lines) * 132
    y0 = int(H * 0.56 - total_h / 2)
    for i, ln in enumerate(lines):
        tw = int(_measure(ln, f))
        last = i == len(lines) - 1
        img = Image.new("RGBA", (tw + 56, 128), (0, 0, 0, 0))
        dd = ImageDraw.Draw(img)
        if last:
            dd.rounded_rectangle([0, 6, img.width - 1, 124], radius=18, fill=ACCENT)
        dd.text((28 + 4, 68), ln, font=f, fill=(0, 0, 0, 120) if not last else (0, 0, 0, 0), anchor="lm")
        dd.text((28, 64), ln, font=f, fill=PRIMARY if last else WHITE, anchor="lm")
        parts.append(Part(img, (W - img.width) // 2, y0 + i * 132, 0.1 + i * min(0.45, duration / (len(lines) + 2)), "pop"))
    return Scene(duration, voice, "zoom", parts, None, background, voice_at=0.15)


def cta_scene(text: str, duration: float, voice: Path, background: Image.Image) -> Scene:
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    inner = CARD_W - 96
    parts, y = [], 60
    bubble = Image.new("RGBA", (150, 130), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bubble)
    bd.rounded_rectangle([0, 0, 149, 100], radius=30, fill=PRIMARY)
    bd.polygon([(36, 96), (36, 129), (72, 98)], fill=PRIMARY)
    for k in range(3):
        bd.ellipse([34 + k * 32, 42, 50 + k * 32, 58], fill=ACCENT)
    parts.append(Part(bubble, 48 + (inner - 150) // 2, y, 0.1, "pop"))
    y += 160
    tf = sans("ExtraBold", 64)
    t = text_block(wrap(d, "BẠN MUỐN BIẾT ĐIỀU GÌ?", tf, inner, 2), tf, INK, inner)
    parts.append(Part(t, 48, y, 0.3, "pop"))
    y += t.height + 20
    bf = sans("SemiBold", 42)
    body = text_block(wrap(d, text, bf, inner, 5), bf, INK, inner, lh=1.32)
    parts.append(Part(body, 48, y, 0.7, "rise"))
    y += body.height + 36
    pf = sans("Bold", 36)
    label = "COMMENT NGAY BÊN DƯỚI"
    pw = int(_measure(label, pf)) + 80
    pill = Image.new("RGBA", (pw, 76), (0, 0, 0, 0))
    ImageDraw.Draw(pill).rounded_rectangle([0, 0, pw - 1, 75], radius=38, fill=DOWN)
    ImageDraw.Draw(pill).text((pw / 2, 38), label, font=pf, fill=WHITE, anchor="mm")
    parts.append(Part(pill, 48 + (inner - pw) // 2, y, min(2.0, duration * 0.45), "pop"))
    y += 76 + 60
    return Scene(duration, voice, "up", parts, ((H - y) // 2 + 60, y), background, voice_at=0.3)


# ------------------------------------------------------------------ dựng khung

def _part_state(p: Part, t: float):
    """→ (dx, dy, alpha, scale, wipe 0-1)."""
    k = prog(t, p.start, 0.45)
    if k <= 0:
        return None
    e = ease_out(k)
    if p.kind == "pop":
        return 0, 0, e, 0.8 + 0.2 * ease_back(k), 1
    if p.kind == "rise":
        return 0, 50 * (1 - e), e, 1, 1
    if p.kind == "right":
        return -60 * (1 - e), 0, e, 1, 1
    if p.kind == "wipe":
        return 0, 0, 1, 1, e
    return 0, 0, e, 1, 1


def _card_frame(scene: Scene, t: float) -> Image.Image:
    cy, chh = scene.card
    card = Image.new("RGBA", (CARD_W, chh), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle([0, 0, CARD_W - 1, chh - 1], radius=40, fill=WHITE)
    for p in scene.parts:
        st = _part_state(p, t)
        if not st:
            continue
        dx, dy, a, s, wipe = st
        img = p.img
        if wipe < 1:
            w = max(1, int(img.width * wipe))
            img = img.crop((0, 0, w, img.height))
            dx += (p.img.width - w) / 2
        paste(card, img, p.x + dx, p.y + dy, a, s)
    for ov in scene.overlays:
        if ov.marks and t >= min(ov.starts):
            layer = Image.new("RGBA", (ov.w, ov.h), (0, 0, 0, 0))
            marks.draw(layer, ov.marks, ov.f, t, ov.starts)
            card.alpha_composite(layer, (ov.x, ov.y))
    return card


OVER = 0.45   # thời gian cảnh cũ rời đi, gối lên phần mở đầu của cảnh mới


def _enter(style: str, t: float):
    """Thẻ đi vào trong 0.55s đầu cảnh → (dx, dy, alpha, scale)."""
    k = prog(t, 0, 0.55)
    e = ease_out(k)
    if style == "up":
        return 0, 300 * (1 - e), min(1, k * 2), 1
    if style == "right":
        return W * (1 - e), 0, 1, 1
    if style == "zoom":
        return 0, 0, min(1, k * 4), 0.72 + 0.28 * ease_back(k)
    return 0, -320 * (1 - e), min(1, k * 2), 1          # drop


def _exit(next_style: str, k: float):
    """Thẻ cũ rời đi theo hướng ngược với cách thẻ mới đi vào (k: 0→1)."""
    e = ease_out(k)
    if next_style == "right":
        return -W * e, 0, 1, 1                            # đẩy sang trái, thẻ mới vào từ phải
    if next_style == "up":
        return 0, -260 * e, max(0.0, 1 - 1.6 * e), 1
    if next_style == "zoom":
        return 0, 0, max(0.0, 1 - 2.2 * e), 1 + 0.12 * e
    return 0, 320 * e, max(0.0, 1 - 1.6 * e), 1         # drop: thẻ cũ rơi xuống


def _bg_frame(bg: Image.Image, gt: float, total: float) -> Image.Image:
    z = 1 + 0.07 * (gt / total)                          # nền phóng chậm suốt video
    cw, chh = int(bg.width / z), int(bg.height / z)
    left, top = (bg.width - cw) // 2, (bg.height - chh) // 2
    return bg.crop((left, top, left + cw, top + chh)).resize((W, H), Image.BILINEAR)


def _draw_scene(frame: Image.Image, scene: Scene, t: float, out: tuple | None = None):
    """Vẽ 1 cảnh tại thời điểm t; out = (dx, dy, alpha, scale) khi cảnh đang rời đi."""
    if scene.card:
        dx, dy, a, sc = out if out else _enter(scene.style, t)
        paste(frame, _card_frame(scene, t), CARD_X + dx, scene.card[0] + dy, a, sc)
        return
    odx, ody, oa, osc = out if out else (0, 0, 1, 1)
    for p in scene.parts:
        st = _part_state(p, t)
        if st:
            dx, dy, a, sc, _ = st
            paste(frame, p.img, p.x + dx + odx, p.y + dy + ody, a * oa, sc * osc)


def frames(scenes: list[Scene], base_bg: Image.Image, overlay: Image.Image):
    total = sum(s.duration for s in scenes)
    tag = brand_tag()
    t0 = 0.0
    for i, scene in enumerate(scenes):
        prev = scenes[i - 1] if i else None
        last = i == len(scenes) - 1
        for f in range(int(round(scene.duration * FPS))):
            t = f / FPS
            gt = t0 + t
            frame = _bg_frame(scene.background or base_bg, gt, total)
            # nền chuyển mềm khi cảnh trước dùng nền khác
            if prev and t < OVER and (prev.background or base_bg) is not (scene.background or base_bg):
                old = _bg_frame(prev.background or base_bg, gt, total)
                frame = Image.blend(old, frame, ease_out(t / OVER))
            if prev and t < OVER:
                _draw_scene(frame, prev, prev.duration + t, _exit(scene.style, t / OVER))
            _draw_scene(frame, scene, t)
            frame.alpha_composite(overlay)
            paste(frame, tag, (W - tag.width) / 2, 96)
            d = ImageDraw.Draw(frame)
            d.rectangle([0, 0, W, 10], fill=(255, 255, 255, 60))
            d.rectangle([0, 0, int(W * min(1, gt / (total - 1.2))), 10], fill=ACCENT)
            if last and t > scene.duration - 1.2:           # kết thúc: mờ dần về đen
                k = ease_out((t - scene.duration + 1.2) / 1.2)
                frame = Image.blend(frame, Image.new("RGBA", frame.size, (0, 0, 0, 255)), k * 0.92)
            yield frame.convert("RGB").tobytes()
        t0 += scene.duration


def encode(scenes: list[Scene], base_bg: Image.Image, out: Path, music: Path | None = None) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))   # chỗ để chèn lớp phủ chung nếu cần
    silent = out.with_suffix(".video.mp4")
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                             "-crf", "19", "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
    for raw in frames(scenes, base_bg, overlay):
        proc.stdin.write(raw)
    proc.stdin.close()
    if proc.wait():
        raise RuntimeError("ffmpeg lỗi khi dựng hình")

    # âm thanh: mỗi đoạn giọng đặt đúng thời điểm cảnh + nhạc nền nhỏ
    total = sum(s.duration for s in scenes)
    inputs, filters, labels, t0 = [], [], [], 0.0
    for s in scenes:
        if s.voice:
            k = len(inputs) // 2
            inputs += ["-i", str(s.voice)]
            ms = int((t0 + s.voice_at) * 1000)
            filters.append(f"[{k + 1}:a]aresample=48000,adelay={ms}|{ms}[v{k}]")
            labels.append(f"[v{k}]")
        t0 += s.duration
    mix = f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,loudnorm=I=-15:TP=-1.5[voice]"
    # hiệu ứng âm thanh (ting, vút, bụp, bút) gộp thành 1 rãnh
    events, t0 = [], 0.0
    for i, s in enumerate(scenes):
        events += scene_sfx(s, t0, i == 0)
        t0 += s.duration
    fx = sfx.render_track(events, total, out.with_suffix(".sfx.wav"))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), *inputs, "-i", str(fx)]
    x = len(labels) + 1
    filters.append(mix)
    filters.append(f"[{x}:a]aresample=48000,volume=0.9[fx]")
    filters.append("[voice]apad,asplit=2[vo][sc]")
    if music:
        m = x + 1
        cmd += ["-stream_loop", "-1", "-ss", f"{music_offset(music):.1f}", "-i", str(music)]   # vào thẳng đoạn nhạc lên
        # nhạc tự hạ khi Thái nói (sidechain), lên lại ở khoảng nghỉ và đoạn kết; mờ dần 3.2s cuối
        filters.append(f"[{m}:a]aresample=48000,loudnorm=I=-14:TP=-1.5,volume=0.85,afade=t=in:d=0.6,"
                       f"afade=t=out:st={total - 3.2:.2f}:d=3.2[bgm]")
        filters.append("[bgm][sc]sidechaincompress=threshold=0.06:ratio=3.5:attack=20:release=350[duck]")
        filters.append("[vo][duck][fx]amix=inputs=3:normalize=0:duration=longest,"
                       "alimiter=limit=0.89:attack=5:release=50:level=disabled[a]")   # chặn vỡ tiếng (đỉnh ≤ -1 dB)
    else:
        filters.append("[sc]anullsink")
        filters.append("[vo][fx]amix=inputs=2:normalize=0:duration=longest,"
                       "alimiter=limit=0.89:attack=5:release=50:level=disabled[a]")
    cmd += ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[a]", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}", "-movflags", "+faststart", str(out)]
    if subprocess.run(cmd).returncode:
        raise RuntimeError("ffmpeg lỗi khi ghép âm thanh")
    silent.unlink(missing_ok=True)
    return out


def music_offset(path: Path) -> float:
    """Giây bắt đầu đoạn nhạc 'lên' (năng lượng cao) để video vào nhịp mạnh ngay, bỏ phần dạo đầu nhẹ."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-t", "75", "-i", str(path), "-ac", "1", "-ar", "8000",
                          "-f", "s16le", "-"], capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32)
    if len(a) < 8000 * 10:
        return 0.0
    rms = np.sqrt(np.convolve(a ** 2, np.ones(8000) / 8000, "valid")[::4000])   # RMS cửa sổ 1s, bước 0.5s
    hit = np.nonzero(rms >= 0.8 * rms.max())[0]
    return max(0.0, float(hit[0]) * 0.5 - 0.5) if len(hit) else 0.0


def pick_music() -> Path | None:
    import os
    if os.environ.get("REEL_MUSIC"):                       # chọn bài cụ thể khi dựng thử
        return MUSIC / os.environ["REEL_MUSIC"]
    tracks = sorted(p for p in MUSIC.glob("*") if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".ogg"))
    return random.choice(tracks) if tracks else None
