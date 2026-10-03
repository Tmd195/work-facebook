"""Khung hình Reels thị trường (Page Global) theo khuôn mẫu: mở đầu tiêu đề + cờ → chuyển cảnh →
biểu đồ giá thật + chỉ báo hiện dần → thẻ câu hỏi → thẻ logo CWG. 1080×1920, 30 fps."""
import math
import random

from PIL import Image, ImageDraw, ImageFilter

from src.config import ROOT
from src.design.common import sans, wrap
from src.reels.mkt.flags import icon, pair_codes
from src.reels.qa import clean

W, H, FPS = 1080, 1920, 30
NAVY = (9, 13, 30)
GRID = (26, 32, 52)
AXIS = (120, 130, 155)
CANDLE = (38, 166, 154)          # nến tăng xanh ngọc, thân đặc (kiểu MT5/TradingView)
DOWN = (239, 83, 80)              # nến giảm đỏ, thân đặc
VARIANT = 0                       # bố cục thay thế khi bộ kiểm tra thấy lỗi hiển thị (dời nhãn, cỡ chữ)
VIEW = 62                         # số nến hiện trên màn hình (giống biểu đồ điện thoại – thân nến dày)
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


def _text(img: Image.Image, xy, text: str, font, col, alpha: float, anchor: str = "la"):
    """Vẽ chữ có độ mờ (PIL bỏ qua alpha của chữ khi vẽ thẳng) – qua lớp trong suốt rồi dán bằng mặt nạ."""
    if alpha <= 0.01 or not text:
        return
    d0 = ImageDraw.Draw(img)
    l, t_, r, b = d0.textbbox(xy, text, font=font, anchor=anchor)
    pad = 4
    lay = Image.new("L", (int(r - l) + pad * 2, int(b - t_) + pad * 2), 0)
    ImageDraw.Draw(lay).text((xy[0] - l + pad, xy[1] - t_ + pad), text, font=font, fill=int(255 * min(1.0, alpha)),
                             anchor=anchor)
    img.paste(col[:3], (int(l) - pad, int(t_) - pad), lay)


def _logo(h: int, name: str = "icon.png") -> Image.Image:
    img = Image.open(ROOT / "assets" / "brands" / "cwg" / name).convert("RGBA")
    return img.resize((round(img.width * h / img.height), h), Image.LANCZOS)


def watermark(img: Image.Image, dark: bool = True):
    """Dấu thương hiệu cố định ở đáy khung: logo ở trên, chữ ở dưới, cả hai căn đúng tâm màn hình (anh chốt)."""
    ic = _logo(46)
    y0 = 1596
    _put(img, ic, (W // 2 - ic.width // 2, y0))
    col = (255, 255, 255) if dark else (30, 30, 36)
    lay = Image.new("RGBA", (W, 50), (0, 0, 0, 0))
    ImageDraw.Draw(lay).text((W / 2, 25), "CWG MARKETS GLOBAL", font=sans("ExtraBold", 24), fill=col + (160,), anchor="mm")
    _put(img, lay, (0, y0 + ic.height + 4))


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
        lines = wrap(ImageDraw.Draw(img), clean(title).upper(), f, 880, max_lines=3)
        if len(lines) <= 2 and "…" not in lines[-1] or size <= 70:
            break
        size -= 8
    layer = Image.new("RGBA", (W, 420), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for n, ln in enumerate(lines):
        ld.text((W / 2 + 4, 110 + n * size * 1.1 + 6), ln, font=f, fill=(0, 0, 0, 150), anchor="mm")
        ld.text((W / 2, 110 + n * size * 1.1), ln, font=f, fill=(255, 255, 255, 255), anchor="mm")
    layer = layer.transform(layer.size, Image.AFFINE, (1, 0.18, -40, 0, 1, 0), Image.BICUBIC)   # nghiêng chữ
    dx = int((1 - k) * W * 0.9)                         # trượt vào từ bên phải, có vệt chuyển động
    lay = layer
    if dx > 4:
        lay = layer.filter(ImageFilter.BoxBlur(min(18, dx // 25)))
    img.alpha_composite(lay, (dx, 330))
    kf = max(0.0, min(1.0, (t - 0.35) / 0.55))
    if kf > 0:                                         # 2 cờ rơi từ trên xuống, nảy
        y = 820 - (1 - ease_back(kf)) * 520
        pair_icons(img, symbol, W / 2, y, 170, 1.0)
    watermark(img)
    return img


# ------------------------------------------------------------------ cảnh 2: chuyển cảnh nền sáng
def transition(t: float, dur: float, symbol: str) -> Image.Image:
    img = Image.new("RGBA", (W, H), LIGHT + (255,))
    a, b = pair_codes(symbol)
    paths = [(a, -150, 0.30, 700, 1.0), (b, W + 150, 0.62, 860, 1.15), (b, -150, 0.12, 1180, 0.9),
             (a, W + 150, 0.86, 1080, 1.05)]
    for code, xs, xe, yb, sp in paths:                  # cờ bay vào theo đường nảy
        k = min(1.0, t / dur * 1.6 * sp)
        x = xs + (W * xe - xs) * ease(k)
        y = yb - abs(math.sin(k * math.pi * 1.5)) * 260 * (1 - k * 0.6)
        img.alpha_composite(icon(code, 130), (int(x - 65), int(y - 65)))
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
              dur: float = 30.0, cam: list | None = None) -> Image.Image:
        """overlays: [(kind, t_start)]; reveal_end: lúc nến hiện đủ; sub: 'rsi'/'stoch' (khung phụ)."""
        m = self.m
        img = Image.new("RGB", (W, H), NAVY)              # nền RGB: Draw(..,"RGBA") pha màu trong suốt đúng
        d = ImageDraw.Draw(img, "RGBA")
        # đầu khung: cờ + mã + khung thời gian
        kh = prog(t, 0.0, 0.5)
        pair_icons(img, m.symbol, 118, 190, 76, kh, gap=0.5)
        _text(img, (190 + 30 * (1 - kh), 190), m.symbol, sans("Bold", 46), (255, 255, 255), kh, "lm")
        _pop_tag(img, 948, 190, "H4", RED, ease_back(prog(t, 0.25, 0.45)), size=24, pad=22)
        d = ImageDraw.Draw(img, "RGBA")
        # khung phụ (RSI/Stoch) đẩy vùng giá lên
        ks = prog(t, sub_t, 0.6) if sub and sub_t is not None else 0.0
        top, bot = 290, 1420 - 260 * ks
        x0, x1 = 50, 880
        # khung nhìn: phóng to về 45 nến cuối khi có "zoom"
        zt = next((s for k_, s in overlays if k_ == "zoom"), None)
        kz = prog(t, zt, 1.0) if zt is not None else 0.0
        base = self.n - VIEW
        nb = _cam(cam, t) if cam else VIEW               # số nến trên màn hình (zoom in/out theo câu)
        nb = nb + (30 - nb) * kz
        i0 = self.n - nb
        i1 = self.n - 1 + 4 * nb / VIEW
        shown = base + (self.n - base) * min(1.0, max(0.0, t / reveal_end)) if reveal_end > 0 else self.n
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
        tags = []                                           # nhãn vẽ sau cùng (không bị lớp mờ che)
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
                lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                ld = ImageDraw.Draw(lay)
                ld.polygon(poly, fill=CHAN + (int(46 * k),))
                ld.line(poly[:2], fill=CHAN + (230,), width=3)
                ld.line(poly[2:], fill=CHAN + (230,), width=3)
                _dash(ld, (X(ia), Y(mid(ia))), (X(ie), Y(mid(ie))), CHAN + (160,))
                ld.rectangle([0, 0, W, top - 6], fill=(0, 0, 0, 0))
                ld.rectangle([0, bot + 6, W, H], fill=(0, 0, 0, 0))
                ld.rectangle([x1 + 2, 0, W, H], fill=(0, 0, 0, 0))
                img.paste(lay, (0, 0), lay)
                d = ImageDraw.Draw(img, "RGBA")
            elif kind in ("support", "resistance"):
                lv = m.facts[kind]
                col = SUP if kind == "support" else RES
                y = Y(lv)
                _dash(d, (x0, y), (x0 + (x1 - x0) * k, y), col + (255,), w=3)
                tx = (x0 + 170, x1 - 300, x0 + 20)[VARIANT % 3]          # bố cục khác: nhãn sang phải / sát trái
                ty = y - 27 if VARIANT % 2 == 0 else y + 27                # bố cục lẻ: nhãn dưới đường
                tags.append((tx, ty, f"{kind.upper()} {lv:,.{m.digits}f}", col, ease_back(k)))
            elif kind == "lows" and m.ind.get("lows"):
                lw = m.ind["lows"]
                y = Y(lw["level"])
                _dash(d, (x0, y), (x0 + (x1 - x0) * k, y), SUP + (255,), w=3)
                for j in lw["idx"]:
                    if j >= i0:
                        r = 20 * k
                        d.ellipse([X(j) - r, Y(m.l[j]) + 8 - r * 0.2, X(j) + r, Y(m.l[j]) + 8 + r * 1.8],
                                  outline=SUP + (255,), width=3)
        # nến: vẽ ở độ phân giải gấp đôi rồi thu nhỏ (nét mịn, bấc mảnh như biểu đồ thật)
        S = 2
        cl = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
        dc = ImageDraw.Draw(cl)
        bw = max(3.0, slot * 0.72)
        for i in range(max(int(base), int(i0) - 1), last):
            gx = X(i)
            if gx < x0 - bw:
                continue
            up = m.c[i] >= m.o[i]
            col = CANDLE if up else DOWN
            grow = 1.0 if i < last - 1 or shown >= self.n else min(1.0, (shown - int(shown)) * 1.6 + 0.2)
            hi_, lo_ = m.h[i], m.l[i]
            if grow < 1:                                  # nến mới mọc từ giá mở cửa
                mid_ = m.o[i]
                hi_, lo_ = mid_ + (hi_ - mid_) * grow, mid_ - (mid_ - lo_) * grow
            dc.line([(gx * S, Y(hi_) * S), (gx * S, Y(lo_) * S)], fill=col + (255,), width=4)
            ya, yb = sorted((Y(m.o[i]), Y(m.o[i] + (m.c[i] - m.o[i]) * grow)))
            box = [(gx - bw / 2) * S, ya * S, (gx + bw / 2) * S, max(yb, ya + 2) * S]
            dc.rectangle(box, fill=col + (255,))
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
                pts = [(X(i) * S, Y(v[i]) * S) for i in range(max(int(i0), 20 if key != "ema20" else 10), int(end))]
                if len(pts) > 1:
                    dc.line(pts, fill=col + (255,), width=5, joint="curve")
        # ghép lớp nến: quầng sáng mờ + nét chính, rồi mờ dần ở đáy/trái như máy quay có chiều sâu
        cd_ = ImageDraw.Draw(cl)                           # cắt đường/ nến tràn ra ngoài khung giá
        cd_.rectangle([0, 0, W * S, (top - 8) * S], fill=(0, 0, 0, 0))
        cd_.rectangle([0, (bot + 8) * S, W * S, H * S], fill=(0, 0, 0, 0))
        cd_.rectangle([(x1 + 4) * S, 0, W * S, H * S], fill=(0, 0, 0, 0))
        img = img.convert("RGBA")
        glow = cl.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.BILINEAR)
        glow.putalpha(glow.getchannel("A").point(lambda v: int(v * 0.25)))
        img.alpha_composite(glow)
        img.alpha_composite(cl.resize((W, H), Image.LANCZOS))
        _depth_fade(img, x0, top, bot)
        img = img.convert("RGB")
        for tg in tags:
            _pop_tag(img, *tg)
        d = ImageDraw.Draw(img, "RGBA")
        # giá hiện tại
        if shown >= self.n - 0.5:
            kp = ease_back(prog(t, reveal_end, 0.45)) if reveal_end > 0 else 1.0
            y = Y(m.c[-1])
            _dash(d, (x0, y), (x0 + (x1 - x0) * min(1, kp), y), RED + (200,), w=2)
            _pop_tag(img, x1 + 8, y, f"{m.c[-1]:,.{m.digits}f}", RED, kp)
            d = ImageDraw.Draw(img, "RGBA")
        # khung phụ
        if ks > 0:
            st_top = bot + 60
            st_bot = st_top + 180
            key, lab = ("rsi", "RSI 14") if sub == "rsi" else ("stoch_k", "STOCH 14,3")
            v = m.ind[key]
            Ys = lambda q: st_bot - q / 100 * (st_bot - st_top)
            a = int(255 * ks)
            d.rectangle([x0, Ys(70), x1, Ys(30) if sub == "rsi" else Ys(20)], fill=CHAN + (int(30 * ks),))
            _text(img, (x0, st_top - 26), lab, sans("Bold", 22), AXIS, ks, "lm")
            for q in ((70, 30) if sub == "rsi" else (80, 20)):
                _dash(d, (x0, Ys(q)), (x1, Ys(q)), AXIS + (int(120 * ks),))
                _text(img, (x1 + 18, Ys(q)), str(q), f, AXIS, ks, "lm")
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


def _cam(keys: list, t: float) -> float:
    """Nội suy mượt số nến trên màn hình giữa các mốc (chuyển 0.9s, kiểu máy quay đẩy/lùi)."""
    v = keys[0][1]
    for (ta, va) in keys:
        if t >= ta:
            k = ease((t - ta) / 0.9)
            v = v + (va - v) * k
    return v


def subtitle(img: Image.Image, t: float, subs: list, dark: bool = True):
    """Phụ đề tiếng Anh chạy theo giọng: cụm ≤ 6 từ, từ đang đọc tô đỏ CWG."""
    cur = next(((txt, st, du) for txt, st, du in subs if st <= t < st + du + 0.15), None)
    if not cur:
        return
    txt, st, du = cur
    txt = clean(txt)                                   # bỏ ký tự font không vẽ được (vd. "~" hiện thành "-")
    words = txt.split()
    if not words:
        return
    weights = [len(w) + 2 + (4 if w[-1] in ",.;:!?" else 0) for w in words]
    tot = sum(weights)
    acc, idx = 0.0, len(words) - 1
    for i, wt in enumerate(weights):
        if (t - st) / max(0.3, du * 0.95) < (acc + wt) / tot:
            idx = i
            break
        acc += wt
    g0 = idx // 6 * 6
    group = words[g0: g0 + 6]
    f = sans("ExtraBold", 50 - 4 * min(VARIANT, 3))
    d = ImageDraw.Draw(img, "RGBA")
    space = d.textlength(" ", font=f)
    widths = [d.textlength(w, font=f) for w in group]
    lines, cur_l, cw = [], [], 0.0
    for w, wd in zip(group, widths):
        if cur_l and cw + space + wd > 900:
            lines.append(cur_l)
            cur_l, cw = [], 0.0
        cur_l.append((w, wd))
        cw += (space if cw else 0) + wd
    lines.append(cur_l)
    y = 1515 - (len(lines) - 1) * 36                   # dưới khung chỉ báo phụ (RSI/Stoch), trên logo đáy
    n = g0
    for ln in lines:
        lw = sum(wd for _, wd in ln) + space * (len(ln) - 1)
        x = W / 2 - lw / 2                              # chính giữa màn hình
        d.rounded_rectangle([x - 22, y - 38, x + lw + 22, y + 36], radius=16, fill=(0, 0, 0, 150) if dark else (20, 24, 40, 200))
        for w, wd in ln:
            col = RED if n == idx else (255, 255, 255)
            d.text((x + 3, y + 3), w, font=f, fill=(0, 0, 0), anchor="lm")
            d.text((x, y), w, font=f, fill=col, anchor="lm")
            x += wd + space
            n += 1
        y += 72


def _pop_tag(img, x, y, text, col, k, size=22, pad=14):
    """Nhãn bo góc bật lên (phóng từ 0 → hơi quá → 1) quanh điểm neo trái-giữa (x, y)."""
    if k <= 0.02:
        return
    f = sans("Bold", size)
    d0 = ImageDraw.Draw(img)
    w = int(d0.textlength(text, font=f) + pad * 2)
    h = size + 18
    tag = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    td = ImageDraw.Draw(tag)
    td.rounded_rectangle([0, 0, w - 1, h - 1], radius=8, fill=col + (255,))
    td.text((w / 2, h / 2), text, font=f, fill=(255, 255, 255), anchor="mm")
    sc = max(0.05, k)
    tw, th = max(1, int(w * sc)), max(1, int(h * sc))
    tag = tag.resize((tw, th), Image.LANCZOS)
    if k < 1:
        tag.putalpha(tag.getchannel("A").point(lambda v: int(v * min(1.0, k * 1.4))))
    _put(img, tag, (int(x + (w - tw) / 2), int(y - th / 2)))


def _depth_fade(img, x0, top, bot):
    """Mờ dần nến ở đáy vùng giá và mép trái (cảm giác chiều sâu như video mẫu)."""
    g = Image.linear_gradient("L").resize((W, 220))
    img.paste(NAVY + (255,), (0, int(bot) - 150), g.point(lambda v: int(v * 0.85)))
    g2 = Image.linear_gradient("L").rotate(90, expand=True).resize((150, H))
    img.paste(NAVY + (255,), (0, 0), g2.point(lambda v: int(v * 0.6)))


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
    text = clean(text)
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


# ------------------------------------------------------------------ đoạn nhận diện: con trỏ bấm vào logo CWG
STING = 1.9
CLICK = 1.0


def _cursor(d, x, y, s=1.0):
    pts = [(0, 0), (0, 58), (15, 45), (26, 70), (37, 65), (26, 41), (46, 41)]
    pts = [(x + px * s * 1.3, y + py * s * 1.3) for px, py in pts]
    d.polygon(pts, fill=(255, 255, 255, 255), outline=(20, 24, 40, 255))


def sting(t: float, dur: float, symbol: str) -> Image.Image:
    cx, cy = W / 2, H / 2
    lay = Image.new("RGBA", (W, H), NAVY + (255,))
    d = ImageDraw.Draw(lay, "RGBA")
    rot = t * 24
    for r, col in ((200, (48, 58, 86)), (330, (40, 50, 76)), (470, (34, 42, 66)), (640, (30, 38, 60))):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col + (255,), width=3)
    # cung nến xoay quanh tâm (đỏ/trắng như biểu đồ)
    rnd = random.Random(9)
    for ring, (r0, span, n, sign) in enumerate(((540, 150, 30, 1), (720, 120, 26, -1))):
        for k in range(n):
            a = math.radians(rot * sign + (200 if ring else 20) + k * span / n)
            hgt = rnd.uniform(26, 90)
            col = (236, 238, 242) if rnd.random() > 0.45 else (225, 0, 22)
            x, y = cx + r0 * math.cos(a), cy + r0 * math.sin(a)
            dx, dy = math.cos(a), math.sin(a)
            tx, ty = -dy, dx
            w2 = 9
            poly = [(x - tx * w2 - dx * hgt / 2, y - ty * w2 - dy * hgt / 2),
                    (x + tx * w2 - dx * hgt / 2, y + ty * w2 - dy * hgt / 2),
                    (x + tx * w2 + dx * hgt / 2, y + ty * w2 + dy * hgt / 2),
                    (x - tx * w2 + dx * hgt / 2, y - ty * w2 + dy * hgt / 2)]
            d.polygon(poly, fill=col + (200,))
    # biểu tượng bay quanh
    codes = list(dict.fromkeys(list(pair_codes(symbol)) + ["EUR", "GBP", "JPY", "XAU"]))[:6]
    for k, code in enumerate(codes):
        a = math.radians(-rot * 1.4 + k * 60)
        lay.alpha_composite(icon(code, 86), (int(cx + 400 * math.cos(a) - 43), int(cy + 400 * math.sin(a) - 43)))
    # logo CWG ở giữa, nảy khi bị bấm
    kc = max(0.0, t - CLICK)
    pulse = 1 + 0.18 * math.sin(min(1.0, kc / 0.35) * math.pi) if kc > 0 else 1.0
    lg = _logo(int(170 * pulse))
    lay.alpha_composite(lg, (int(cx - lg.width / 2), int(cy - lg.height / 2)))
    if kc > 0:                                         # vòng đỏ loang ra từ cú bấm
        r = 90 + kc * 900
        a = max(0, int(255 * (1 - kc / 0.6)))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=RED + (a,), width=10)
    # con trỏ di vào logo rồi bấm
    km = ease(min(1.0, max(0.0, (t - 0.25) / (CLICK - 0.3))))
    px, py = 860 + (cx + 20 - 860) * km, 1420 + (cy + 30 - 1420) * km
    if t < CLICK + 0.45:
        _cursor(d, px, py, 0.82 if CLICK - 0.05 < t < CLICK + 0.12 else 1.0)
    # máy quay: lùi ra lúc đầu, sau cú bấm lao xuyên qua logo
    z = 1.35 - 0.35 * ease(t / 0.6)
    if t > CLICK + 0.3:
        z = 1 + 7 * ((t - CLICK - 0.3) / max(0.1, dur - CLICK - 0.3)) ** 2
    if abs(z - 1) > 0.01:
        cw, ch_ = W / z, H / z
        lay = lay.crop((int(cx - cw / 2), int(cy - ch_ / 2), int(cx + cw / 2), int(cy + ch_ / 2))).resize((W, H), Image.BILINEAR)
    if t > dur - 0.25:                                 # tối dần vào biểu đồ
        lay = Image.blend(lay, Image.new("RGBA", (W, H), NAVY + (255,)), min(1.0, (t - (dur - 0.25)) / 0.25))
    return lay


# ------------------------------------------------------------------ đoạn kết: chấm → chữ CWG → logo + cảnh báo
def ending(t: float, dur: float) -> Image.Image:
    img = Image.new("RGB", (W, H), NAVY)              # nền RGB để chữ mờ dần pha màu đúng
    d = ImageDraw.Draw(img, "RGBA")
    up = 150 * ease((t - 1.5) / 0.6)                   # cả cụm logo dịch lên nhường chỗ cảnh báo
    f = sans("ExtraBold", 190)
    letters = "CWG"
    widths = [d.textlength(ch, font=f) for ch in letters]
    total = sum(widths) + 24 * 2
    x = W / 2 - total / 2 + 60
    cy = 900 - up
    for n, (ch, w) in enumerate(zip(letters, widths)):
        cxl = x + w / 2
        kd = ease_back(prog(t, 0.05 + n * 0.08, 0.3))          # chấm bật lên
        kl = prog(t, 0.55 + n * 0.12, 0.35)                     # chấm → chữ
        if kl < 1:
            r = 16 * kd * (1 - kl)
            d.ellipse([cxl - r, cy - r, cxl + r, cy + r], fill=RED + (255,))
        if kl > 0:
            s = ease_back(kl)
            lt = Image.new("RGBA", (int(w) + 40, 260), (0, 0, 0, 0))
            ImageDraw.Draw(lt).text((lt.width / 2, 130), ch, font=f, fill=RED + (255,), anchor="mm")
            sw, sh = max(1, int(lt.width * s)), max(1, int(lt.height * s))
            _put(img, lt.resize((sw, sh), Image.LANCZOS), (int(cxl - sw / 2), int(cy - sh / 2)))
        x += w + 24
    ki = ease_back(prog(t, 1.0, 0.4))
    if ki > 0.02:
        lg = _logo(max(1, int(150 * ki)))
        _put(img, lg, (int(W / 2 - total / 2 - 50 - lg.width / 2), int(cy - lg.height / 2)))
    km = prog(t, 1.15, 0.45)
    d = ImageDraw.Draw(img, "RGBA")
    _text(img, (W / 2 + 60 * (1 - km), cy + 150), "MARKETS GLOBAL", sans("ExtraBold", 54), (255, 255, 255), km, "mm")
    k2 = prog(t, 1.8, 0.6)
    y = cy + 260
    _text(img, (W / 2, y), "facebook.com/CWG.Markets.Global", sans("Bold", 30), RED, k2, "mm")
    y += 80
    for ln in wrap(d, DISCLAIMER, sans("Regular", 24), 860, max_lines=8):
        _text(img, (W / 2, y), ln, sans("Regular", 24), AXIS, k2, "mm")
        y += 36
    return img
