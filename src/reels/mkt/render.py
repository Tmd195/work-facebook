"""Khung hình Reels thị trường (Page Global) theo khuôn mẫu: mở đầu tiêu đề + cờ → chuyển cảnh →
biểu đồ giá thật + chỉ báo hiện dần → thẻ câu hỏi → thẻ logo CWG. 1080×1920, 30 fps."""
import math
import random

from PIL import Image, ImageDraw, ImageFilter

from src.config import ROOT
from src.design.common import sans, wrap
from src.reels.mkt.flags import icon, pair_codes

W, H, FPS = 1080, 1920, 30
NAVY = (9, 13, 30)
GRID = (26, 32, 52)
AXIS = (120, 130, 155)
CANDLE = (236, 238, 242)
DOWN = (236, 70, 82)
RED = (225, 0, 22)
LIGHT = (226, 231, 228)
INK = (24, 26, 32)
EMA20, EMA50, BB, CHAN = (66, 165, 245), (255, 159, 28), (236, 70, 82), (80, 140, 255)
SUP, RES = (46, 204, 130), (236, 70, 82)


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_back(t):
    t = max(0.0, min(1.0, t))
    c = 1.7
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def prog(t, start, dur):
    return ease((t - start) / dur) if dur > 0 else float(t >= start)


def _put(img: Image.Image, ic: Image.Image, xy):
    """Dán ảnh trong suốt lên nền RGB hoặc RGBA."""
    if img.mode == "RGBA":
        img.alpha_composite(ic, xy)
    else:
        img.paste(ic, xy, ic)


def _logo(h: int, name: str = "icon.png") -> Image.Image:
    img = Image.open(ROOT / "assets" / "brands" / "cwg" / name).convert("RGBA")
    return img.resize((round(img.width * h / img.height), h), Image.LANCZOS)


def watermark(img: Image.Image, dark: bool = True):
    """Dấu thương hiệu nhỏ cố định ở đáy khung (trên vùng nút của Reels)."""
    d = ImageDraw.Draw(img, "RGBA")
    ic = _logo(40)
    x = W // 2 - 150
    img.paste(ic, (x, 1622), ic)
    d.text((x + 52, 1642), "CWG MARKETS GLOBAL", font=sans("ExtraBold", 26),
           fill=(255, 255, 255, 150) if dark else (30, 30, 36, 160), anchor="lm")


def pair_icons(img: Image.Image, symbol: str, cx: float, cy: float, size: int, k: float = 1.0, gap: float = 0.62):
    a, b = pair_codes(symbol)
    s = max(2, int(size * (0.6 + 0.4 * ease_back(k))))
    for code, dx in ((b, gap * s / 2), (a, -gap * s / 2)):
        ic = icon(code, s)
        if k < 1:
            ic = ic.copy()
            ic.putalpha(ic.getchannel("A").point(lambda v: int(v * min(1, k * 1.5))))
        _put(img, ic, (int(cx + dx - s / 2), int(cy - s / 2)))


# ------------------------------------------------------------------ cảnh 1: mở đầu
_FIELD = None


def _field():
    global _FIELD
    if _FIELD is None:
        rnd = random.Random(4)
        codes = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "XAU", "OIL", "DXY"]
        _FIELD = [(rnd.choice(codes), rnd.randint(90, 170), rnd.uniform(-40, W), rnd.uniform(860, 2300), rnd.uniform(25, 60))
                  for _ in range(46)]
    return _FIELD


def intro(t: float, dur: float, symbol: str, title: str) -> Image.Image:
    img = Image.new("RGBA", (W, H), NAVY + (255,))
    for code, s, x, y, sp in _field():                # thảm biểu tượng trôi lên, mờ
        yy = y - sp * t - 180 * prog(t, 0, 0.8)
        ic = icon(code, s).copy()
        ic.putalpha(ic.getchannel("A").point(lambda v: int(v * 0.28)))
        img.alpha_composite(ic, (int(x), int(yy)))
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shade).rectangle([0, 0, W, 900], fill=NAVY + (210,))
    img.alpha_composite(shade.filter(ImageFilter.GaussianBlur(80)))
    # tiêu đề nghiêng, đập vào
    k = prog(t, 0.05, 0.45)
    size = 118
    while True:                                        # tự thu nhỏ để tiêu đề luôn đủ chữ trong 2 dòng
        f = sans("ExtraBold", size)
        lines = wrap(ImageDraw.Draw(img), title.upper(), f, 880, max_lines=3)
        if len(lines) <= 2 and "…" not in lines[-1] or size <= 70:
            break
        size -= 8
    layer = Image.new("RGBA", (W, 420), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for n, ln in enumerate(lines):
        ld.text((W / 2 + 4, 110 + n * size * 1.1 + 6), ln, font=f, fill=(0, 0, 0, 150), anchor="mm")
        ld.text((W / 2, 110 + n * size * 1.1), ln, font=f, fill=(255, 255, 255, 255), anchor="mm")
    layer = layer.transform(layer.size, Image.AFFINE, (1, 0.18, -40, 0, 1, 0), Image.BICUBIC)   # nghiêng chữ
    s = 1.25 - 0.25 * k
    lw, lh = int(W * s), int(420 * s)
    lay = layer.resize((lw, lh), Image.LANCZOS)
    lay.putalpha(lay.getchannel("A").point(lambda v: int(v * k)))
    img.alpha_composite(lay, ((W - lw) // 2, 330 - (lh - 420) // 2))
    pair_icons(img, symbol, W / 2, 820, 170, prog(t, 0.35, 0.5))
    watermark(img)
    return img


# ------------------------------------------------------------------ cảnh 2: chuyển cảnh nền sáng
def transition(t: float, dur: float, symbol: str) -> Image.Image:
    img = Image.new("RGBA", (W, H), LIGHT + (255,))
    a, b = pair_codes(symbol)
    k = ease(t / dur)
    for code, x0, x1, y in ((b, W + 120, W * 0.66, 900), (a, -120, W * 0.34, 980)):
        x = x0 + (x1 - x0) * k
        img.alpha_composite(icon(code, 150), (int(x - 75), int(y - 75)))
    if t > dur * 0.6:                                  # vòng tròn tối loang ra → vào biểu đồ
        r = (t - dur * 0.6) / (dur * 0.4) * 1300
        ImageDraw.Draw(img).ellipse([W / 2 - r, 960 - r, W / 2 + r, 960 + r], fill=NAVY + (255,))
    return img


# ------------------------------------------------------------------ cảnh 3: biểu đồ
class Chart:
    def __init__(self, m):
        self.m = m
        self.n = len(m.c)

    def frame(self, t: float, reveal_end: float, overlays: list, sub: str | None, sub_t: float | None,
              dur: float = 30.0) -> Image.Image:
        """overlays: [(kind, t_start)]; reveal_end: lúc nến hiện đủ; sub: 'rsi'/'stoch' (khung phụ)."""
        m = self.m
        img = Image.new("RGB", (W, H), NAVY)              # nền RGB: Draw(..,"RGBA") pha màu trong suốt đúng
        d = ImageDraw.Draw(img, "RGBA")
        # đầu khung: cờ + mã + khung thời gian
        pair_icons(img, m.symbol, 118, 190, 76, 1.0, gap=0.5)
        d.text((190, 190), m.symbol, font=sans("Bold", 46), fill=(255, 255, 255), anchor="lm")
        d.rounded_rectangle([948, 170, 1020, 210], radius=20, fill=RED)
        d.text((984, 190), "D1", font=sans("ExtraBold", 24), fill=(255, 255, 255), anchor="mm")
        # khung phụ (RSI/Stoch) đẩy vùng giá lên
        ks = prog(t, sub_t, 0.6) if sub and sub_t is not None else 0.0
        top, bot = 290, 1420 - 260 * ks
        x0, x1 = 50, 880
        # khung nhìn: phóng to về 45 nến cuối khi có "zoom"
        zt = next((s for k_, s in overlays if k_ == "zoom"), None)
        kz = prog(t, zt, 1.0) if zt is not None else 0.0
        drift = 30 * ease(max(0.0, t - reveal_end) / max(1.0, dur - reveal_end))   # máy quay phóng dần sau khi nến hiện đủ
        i0 = drift + (self.n - 46 - drift) * kz
        i1 = self.n - 1 + 4
        shown = self.n * min(1.0, max(0.0, t / reveal_end)) if reveal_end > 0 else self.n
        last = max(1, int(shown))
        vis = range(int(i0), self.n)                      # khung giá cố định theo toàn bộ nến → nến mọc dần lấp vào
        lo = min(m.l[i] for i in vis) if vis else m.l[0]
        hi = max(m.h[i] for i in vis) if vis else m.h[0]
        # gồm cả chỉ báo đang hiện trong khung giá
        for kind, st in overlays:
            if t >= st and kind == "bollinger":
                lo = min(lo, min(m.ind["bb_lo"][i] for i in vis))
                hi = max(hi, max(m.ind["bb_up"][i] for i in vis))
        pad = (hi - lo) * 0.08
        lo, hi = lo - pad, hi + pad
        slot = (x1 - x0) / (i1 - i0 + 1)
        X = lambda i: x0 + (i - i0 + 0.5) * slot
        Y = lambda p: top + (hi - p) / (hi - lo) * (bot - top)
        # lưới + trục giá
        step = _nice((hi - lo) / 7)
        p = math.ceil(lo / step) * step
        f = sans("Medium", 22)
        while p < hi:
            y = Y(p)
            d.line([(x0, y), (x1, y)], fill=GRID + (255,), width=1)
            d.text((x1 + 18, y), f"{p:,.{m.digits}f}", font=f, fill=AXIS, anchor="lm")
            p += step
        # chỉ báo phía sau nến
        for kind, st in overlays:
            k = prog(t, st, 1.0)
            if k <= 0:
                continue
            if kind == "channel":
                ch = m.ind["channel"]
                ia, ib = ch["i0"], self.n - 1 + 3
                ie = ia + (ib - ia) * k
                mid = lambda i: ch["a"] + ch["b"] * i
                poly = [(X(ia), Y(mid(ia) + ch["hi"])), (X(ie), Y(mid(ie) + ch["hi"])),
                        (X(ie), Y(mid(ie) + ch["lo"])), (X(ia), Y(mid(ia) + ch["lo"]))]
                d.polygon(poly, fill=CHAN + (int(46 * k),))
                d.line(poly[:2], fill=CHAN + (230,), width=3)
                d.line(poly[2:], fill=CHAN + (230,), width=3)
                _dash(d, (X(ia), Y(mid(ia))), (X(ie), Y(mid(ie))), CHAN + (160,))
            elif kind in ("support", "resistance"):
                lv = m.facts[kind]
                col = SUP if kind == "support" else RES
                y = Y(lv)
                _dash(d, (x0, y), (x0 + (x1 - x0) * k, y), col + (255,), w=3)
                lab = f"{kind.upper()} {lv:,.{m.digits}f}"
                fw = d.textlength(lab, font=sans("Bold", 22)) + 28
                d.rounded_rectangle([x0 + 10, y - 44, x0 + 10 + fw, y - 10], radius=8, fill=col + (int(235 * k),))
                d.text((x0 + 24, y - 27), lab, font=sans("Bold", 22), fill=(255, 255, 255, int(255 * k)), anchor="lm")
            elif kind == "lows" and m.ind.get("lows"):
                lw = m.ind["lows"]
                y = Y(lw["level"])
                _dash(d, (x0, y), (x0 + (x1 - x0) * k, y), SUP + (255,), w=3)
                for j in lw["idx"]:
                    if j >= i0:
                        r = 20 * k
                        d.ellipse([X(j) - r, Y(m.l[j]) + 8 - r * 0.2, X(j) + r, Y(m.l[j]) + 8 + r * 1.8],
                                  outline=SUP + (255,), width=3)
        # nến
        bw = max(2.0, slot * 0.62)
        for i in range(max(0, int(i0) - 1), last):
            gx = X(i)
            if gx < x0 - bw:
                continue
            up = m.c[i] >= m.o[i]
            col = CANDLE if up else DOWN
            d.line([(gx, Y(m.h[i])), (gx, Y(m.l[i]))], fill=col + (255,), width=2)
            ya, yb = sorted((Y(m.o[i]), Y(m.c[i])))
            if up:
                d.rectangle([gx - bw / 2, ya, gx + bw / 2, max(yb, ya + 2)], outline=col + (255,), width=2)
            else:
                d.rectangle([gx - bw / 2, ya, gx + bw / 2, max(yb, ya + 2)], fill=col + (255,))
        # chỉ báo dạng đường (trên nến)
        for kind, st in overlays:
            k = prog(t, st, 1.2)
            if k <= 0:
                continue
            series = {"ema": [("ema20", EMA20), ("ema50", EMA50)], "bollinger": [("bb_up", BB), ("bb_lo", BB)]}.get(kind)
            if not series:
                continue
            for key, col in series:
                v = m.ind[key]
                end = int(i0) + (last - int(i0)) * k
                pts = [(X(i), Y(v[i])) for i in range(max(int(i0), 20 if key != "ema20" else 10), int(end))]
                if len(pts) > 1:
                    d.line(pts, fill=col + (255,), width=3, joint="curve")
        # giá hiện tại
        if shown >= self.n - 0.5:
            y = Y(m.c[-1])
            _dash(d, (x0, y), (x1, y), RED + (200,), w=2)
            lab = f"{m.c[-1]:,.{m.digits}f}"
            fw = d.textlength(lab, font=sans("Bold", 22)) + 20
            d.rounded_rectangle([x1 + 8, y - 18, x1 + 8 + fw, y + 18], radius=6, fill=RED)
            d.text((x1 + 18, y), lab, font=sans("Bold", 22), fill=(255, 255, 255), anchor="lm")
        # khung phụ
        if ks > 0:
            st_top = bot + 60
            st_bot = st_top + 180
            key, lab = ("rsi", "RSI 14") if sub == "rsi" else ("stoch_k", "STOCH 14,3")
            v = m.ind[key]
            Ys = lambda q: st_bot - q / 100 * (st_bot - st_top)
            a = int(255 * ks)
            d.rectangle([x0, Ys(70), x1, Ys(30) if sub == "rsi" else Ys(20)], fill=CHAN + (int(30 * ks),))
            d.text((x0, st_top - 26), lab, font=sans("Bold", 22), fill=AXIS + (a,), anchor="lm")
            for q in ((70, 30) if sub == "rsi" else (80, 20)):
                _dash(d, (x0, Ys(q)), (x1, Ys(q)), AXIS + (int(120 * ks),))
                d.text((x1 + 18, Ys(q)), str(q), font=f, fill=AXIS + (a,), anchor="lm")
            k2 = prog(t, sub_t + 0.3, 1.2)
            end = int(i0) + (last - int(i0)) * k2
            pts = [(X(i), Ys(v[i])) for i in range(max(int(i0), 15), int(end))]
            if len(pts) > 1:
                d.line(pts, fill=EMA50 + (a,), width=3, joint="curve")
            if sub == "stoch":
                pts = [(X(i), Ys(m.ind["stoch_d"][i])) for i in range(max(int(i0), 15), int(end))]
                if len(pts) > 1:
                    d.line(pts, fill=BB + (a,), width=2, joint="curve")
        watermark(img)
        return img


def _nice(raw):
    p = 10 ** math.floor(math.log10(raw))
    for k in (1, 2, 2.5, 5, 10):
        if raw <= k * p:
            return k * p
    return 10 * p


def _dash(d, a, b, col, w=2, dash=14, gap=9):
    (xa, ya), (xb, yb) = a, b
    L = math.hypot(xb - xa, yb - ya)
    if L < 1:
        return
    ux, uy = (xb - xa) / L, (yb - ya) / L
    s = 0.0
    while s < L:
        e = min(L, s + dash)
        d.line([(xa + ux * s, ya + uy * s), (xa + ux * e, ya + uy * e)], fill=col, width=w)
        s += dash + gap


# ------------------------------------------------------------------ cảnh 4: câu hỏi
def question(t: float, dur: float, symbol: str, text: str, voice_dur: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), LIGHT + (255,))
    d = ImageDraw.Draw(img, "RGBA")
    big = sans("Medium", 210)
    for y, sp in ((300, -90), (1500, 70)):              # chữ lớn mờ trôi ngang phía sau
        d.text((80 + sp * t - (300 if sp > 0 else 0), y), text, font=big, fill=(208, 214, 211, 255), anchor="lm")
    pair_icons(img, symbol, W / 2, 790, 110, prog(t, 0.0, 0.4), gap=0.55)
    f = sans("Medium", 54)
    n = int(len(text) * min(1.0, t / max(0.4, voice_dur * 0.85)))
    lines = wrap(d, text, f, 860, max_lines=4)
    shown, y = n, 900
    for ln in lines:
        part = ln[:max(0, shown)]
        shown -= len(ln) + 1
        d.text((W / 2 - d.textlength(ln, font=f) / 2, y), part, font=f, fill=INK)
        y += 70
    ka = prog(t, voice_dur * 0.9, 0.4)
    if ka > 0:
        yy = y + 70 + 14 * math.sin(t * 5)
        d.line([(W / 2, yy), (W / 2, yy + 110)], fill=INK + (int(255 * ka),), width=5)
        d.line([(W / 2 - 26, yy + 84), (W / 2, yy + 112), (W / 2 + 26, yy + 84)], fill=INK + (int(255 * ka),), width=5)
    watermark(img, dark=False)
    return img


# ------------------------------------------------------------------ cảnh 5: logo
DISCLAIMER = ("CFD and Forex trading carries a high level of risk and may not be suitable for all investors. You may lose "
              "all of your capital. This video is for general market information only and is not investment advice. "
              "The CWG Markets group is licensed by FCA, FSCA and VFSC; each entity is licensed in its respective jurisdiction.")


def ending(t: float, dur: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), NAVY + (255,))
    d = ImageDraw.Draw(img, "RGBA")
    k = prog(t, 0, 0.5)
    lg = _logo(200)
    lg.putalpha(lg.getchannel("A").point(lambda v: int(v * k)))
    img.alpha_composite(lg, ((W - lg.width) // 2, 560 + int(30 * (1 - k))))
    d.text((W / 2, 830), "CWG MARKETS GLOBAL", font=sans("ExtraBold", 64), fill=(255, 255, 255, int(255 * k)), anchor="mm")
    d.text((W / 2, 905), "facebook.com/CWG.Markets.Global", font=sans("Bold", 30), fill=RED + (int(255 * k),), anchor="mm")
    k2 = prog(t, 0.4, 0.6)
    y = 1010
    for ln in wrap(d, DISCLAIMER, sans("Regular", 24), 860, max_lines=8):
        d.text((W / 2, y), ln, font=sans("Regular", 24), fill=AXIS + (int(255 * k2),), anchor="mm")
        y += 36
    return img
