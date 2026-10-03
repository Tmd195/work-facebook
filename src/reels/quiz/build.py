"""Reels hằng ngày Page Decode – khuôn "BUY OR SELL?" (theo kênh Trade_the_forex anh gửi, nói tiếng Việt).

Bám sát video mẫu (reel 1026895519790557):
- nền đen tuyền như biểu đồ thật, nến M5, chỉ ghi tên cặp tiền; chữ "BUY OR SeLL?" font hoạt hình (Luckiest Guy)
  xanh / vàng / đỏ, giật glitch lúc xuất hiện
- mở đầu: biểu đồ nhỏ ở giữa rồi PHÓNG TO ra; biểu đồ nằm góc dưới-trái, chừa khoảng trống cho cú chạy
- đếm ngược 05→01 (số bật to rồi thu về vòng tròn), giọng "Bạn sẽ Buy hay Sell?"
- lộ đáp án: toàn bộ hệ thống (kênh song song, vùng hỗ trợ/kháng cự, LEG 1, hộp lệnh SL mỏng – TP cao)
  QUÉT PHÓNG RA trong ~0.15s kèm chớp + giật; giọng chỉ "Buy!" / "Sell!"
- nhạc DROP: 1 vài cây nến khổng lồ VỌT xuyên qua TP (nhịp chạy thật), vùng lời trong hộp lệnh sáng dần theo giá;
  giật / rung / nảy bám đúng cú trống của bài nhạc; kết thúc ngay ở đỉnh khi nhạc đang to (Reels tự lặp).

    JOB=decode-partner python -m src.reels.quiz.build --symbol GBPUSD --system double
"""
import argparse
import json
import random
import subprocess
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from src.config import OUTPUT, ROOT
from src.design.common import sans, serif
from src.reels import voice
from src.reels.edu.build import mix
from src.reels.phonetic import spoken
from src.reels.quiz import music as M
from src.reels.quiz.setup import SYSTEMS, Setup, find

W, H, FPS = 1080, 1920, 30
BG = (0, 0, 0)
UP, DN, WHITE = (38, 166, 154), (239, 83, 80), (255, 255, 255)
T_GREEN, T_YELLOW, T_RED = (62, 200, 62), (250, 230, 0), (240, 22, 22)        # màu chữ tiêu đề như mẫu
GOLD, DIM, ORANGE, SUPP = (247, 205, 15), (215, 215, 225), (255, 160, 60), (70, 200, 90)
COL = {"up": SUPP, "down": DN, "gold": GOLD, "dim": DIM}
T_INTRO = (1.1, 1.7)                                 # biểu đồ nhỏ → phóng to
T_COUNT, T_REVEAL = 2.0, 7.0
BURST = 0.16                                         # hệ thống quét phóng ra trong 0.16s
RUN_T = 1.15                                         # nến vọt từ điểm vào tới đỉnh
HOLD = 0.8                                           # giữ ở đỉnh rồi hết video (nhạc vẫn đang to)
PLOT = (16, 420, 1064, 1700)
MUSIC = ROOT / "assets" / "music" / "cwg"
VOICE_INDEX = 3                                      # Tùng Đặng (chỉ dùng khi thiếu bộ giọng cố định)
VOICE_DIR = ROOT / "assets" / "voice" / "decode_quiz"  # BỘ GIỌNG CỐ ĐỊNH anh đã duyệt: intro / buy / sell



@lru_cache(maxsize=None)
def toon(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(ROOT / "assets" / "fonts" / "LuckiestGuy-Regular.ttf"), size)


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = max(0.0, min(1.0, t))
    return t ** 2.4                                    # chậm lúc đầu → tăng tốc (vọt)


def ease_back(t):
    t = max(0.0, min(1.0, t))
    c = 1.7
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def _logo(name, h):
    im = Image.open(ROOT / "assets" / "brands" / "decode" / name).convert("RGBA")
    return im.resize((round(im.width * h / im.height), h), Image.LANCZOS)


def _txt(img, xy, text, font, col, alpha=1.0, anchor="mm", stroke=0, stroke_col=(0, 0, 0)):
    if alpha <= 0.01:
        return
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    a = int(255 * min(1, alpha))
    ImageDraw.Draw(lay).text(xy, text, font=font, fill=col + (a,), anchor=anchor,
                             stroke_width=stroke, stroke_fill=stroke_col + (a,))
    img.alpha_composite(lay)


def glitch(img: Image.Image, k: float, seed: int, box=None) -> Image.Image:
    """Giật kiểu CapCut: lệch kênh màu + dải ngang xé lệch + rung khung (box: chỉ giật một vùng)."""
    if k <= 0.03:
        return img
    rnd = random.Random(seed)
    if box:
        part = glitch(img.crop(box), k, seed)
        img = img.copy()
        img.paste(part, box[:2])
        return img
    w, h = img.size
    r, g, b, a = img.split()
    sh = int(26 * k)
    img = Image.merge("RGBA", (ImageChops.offset(r, sh, int(sh * 0.3)), g, ImageChops.offset(b, -sh, -int(sh * 0.3)), a))
    for _ in range(int(1 + 6 * k)):
        y0 = rnd.randint(0, max(1, h - 40))
        hh = rnd.randint(8, max(9, min(120, h // 3)))
        band = img.crop((0, y0, w, y0 + hh))
        img.paste(band, (int(rnd.randint(-90, 90) * k), y0))
    return ImageChops.offset(img, int(rnd.randint(-22, 22) * k), int(rnd.randint(-22, 22) * k))


def _dash(d, p0, p1, col, width, seg=18):
    (x0, y0), (x1, y1) = p0, p1
    L = max(1.0, ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5)
    for s in range(0, int(L), seg * 2):
        a, b = s / L, min(1.0, (s + seg) / L)
        d.line([(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a), (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)],
               fill=col, width=width)


def _solid(d, p0, p1, col, width):
    d.line([p0, p1], fill=col, width=width)


def _vline(d, x, y0, y1, col, width):
    """Đường LEG kiểu mẫu: đoạn dọc mảnh + gạch ngang ở hai đầu."""
    d.line([(x, y0), (x, y1)], fill=col, width=width)
    for y in (y0, y1):
        d.line([(x - 60, y), (x + 60, y)], fill=col, width=width)


class Quiz:
    def __init__(self, s: Setup):
        self.s = s
        k, hit = s.k, s.hit
        # khung như mẫu: lùi về trái tới khi biên độ phần trước điểm vào ≈ 1.3 lần cú chạy (LEG 1 ≈ LEG 2)
        # → cú vọt chiếm nửa màn hình; tối thiểu 18 nến, tối đa 34 nến
        run = abs((s.h[hit] if s.side == "buy" else s.l[hit]) - s.entry)
        i0 = k - 18
        while i0 > max(0, k - 34) and max(s.h[i0 - 1: k + 1]) - min(s.l[i0 - 1: k + 1]) <= 1.3 * run:
            i0 -= 1
        self.i0 = max(0, i0)
        lo = min(min(s.l[self.i0: hit + 1]), s.sl, s.tp)
        hi = max(max(s.h[self.i0: hit + 1]), s.sl, s.tp)
        pad = (hi - lo) * 0.04
        self.lo, self.hi = lo - pad, hi + pad
        self.n = (hit + 1 - self.i0) / 0.78            # chừa ~22% bề ngang bên phải cho hộp lệnh
        self.slot = (PLOT[2] - PLOT[0]) / self.n
        # LEG 1: nhịp đẩy gần nhất cùng hướng lệnh trước điểm vào
        a0 = max(self.i0, k - 30)
        if s.side == "buy":
            i_lo = min(range(a0, k + 1), key=lambda i: s.l[i])
            i_hi = max(range(i_lo, k + 1), key=lambda i: s.h[i])
            self.leg1 = (i_hi, s.l[i_lo], s.h[i_hi])
        else:
            i_hi = max(range(a0, k + 1), key=lambda i: s.h[i])
            i_lo = min(range(i_hi, k + 1), key=lambda i: s.l[i])
            self.leg1 = (i_lo, s.h[i_hi], s.l[i_lo])
        # kênh giá song song: đường xu hướng qua giá đóng cửa, dịch ra hai biên
        xs = list(range(a0, k + 1))
        ys = [s.c[i] for i in xs]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        sl = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / max(1e-12, sum((x - mx) ** 2 for x in xs))
        base = lambda i: my + sl * (i - mx)
        self.ch = (a0, base, max(s.h[i] - base(i) for i in xs), min(s.l[i] - base(i) for i in xs))
        self.ann_layer = self._annotations()

    def X(self, i):
        return PLOT[0] + (i - self.i0 + 0.5) * self.slot

    def Y(self, p):
        return PLOT[1] + (self.hi - p) / (self.hi - self.lo) * (PLOT[3] - PLOT[1])

    def _annotations(self) -> Image.Image:
        """Toàn bộ hệ thống giao dịch vẽ sẵn 1 lớp – lúc lộ đáp án lớp này QUÉT PHÓNG RA."""
        s, S = self.s, 2
        lay = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay, "RGBA")
        X = lambda i: self.X(i) * S
        Y = lambda p: self.Y(p) * S
        R = W * S
        texts = []
        # kênh song song
        a0, base, up_off, lo_off = self.ch
        labs = (("Parallel Channel", "Support Line") if s.side == "buy" else ("Resistance Line", "Parallel Channel"))
        rise = base(s.k) - base(a0)
        agree = (rise > 0) if s.side == "buy" else (rise < 0)     # kênh cùng chiều lệnh mới vẽ (tránh mâu thuẫn)
        for off, lab in ((up_off, labs[0]), (lo_off, labs[1])) if agree else ():
            i1 = self.s.hit + 4
            d.line([(X(a0), Y(base(a0) + off)), (X(i1), Y(base(i1) + off))], fill=(235, 235, 240, 210), width=3)
            im = (a0 + s.k) / 2
            texts.append(((self.X(im), self.Y(base(im) + off) + (-26 if off == up_off else 26)), lab, DIM, "mm", False))
        for a in s.ann:
            kind = a[0]
            if kind == "zone":
                _, i0, p0, p1, col, lab = a
                c = COL[col]
                d.rectangle([X(max(i0, self.i0 - 1)), Y(max(p0, p1)), X(s.k) + 8 * S, Y(min(p0, p1))],
                            fill=c + (90,), outline=c + (230,), width=3)
                if lab:
                    texts.append(((self.X(s.k) - 4, self.Y(min(p0, p1)) + 22), lab, c, "rm", False))
            elif kind == "line":
                _, i0, p0, i1, p1, col, lab, dashed = a
                (_dash if dashed else _solid)(d, (X(max(i0, self.i0)), Y(p0)), (X(i1), Y(p1)), COL[col] + (235,), 3)
                if lab:
                    texts.append(((self.X(i1) - 6, self.Y(p1) - 22), lab, COL[col], "rm", False))
            elif kind == "path":
                _, pts, col = a
                d.line([(X(i), Y(p)) for i, p in pts], fill=COL[col] + (255,), width=4, joint="curve")
            elif kind == "tag":
                _, i, p, t, col, above = a
                if i >= self.i0:
                    texts.append(((self.X(i), self.Y(p) + (-28 if above else 28)), t, COL[col], "mm", False))
        # LEG 1
        i1, p_from, p_to = self.leg1
        if i1 >= self.i0 and abs(p_to - p_from) >= 0.4 * abs(s.tp - s.entry):   # nhịp quá ngắn → không ghi LEG 1
            _vline(d, X(i1), Y(p_from), Y(p_to), (225, 160, 70, 230), 3)
            texts.append(((self.X(i1), self.Y(p_to) + (-26 if s.side == "buy" else 26)), "LEG 1", ORANGE, "mm", False))
        # hộp lệnh (công cụ vị thế TradingView): SL mỏng – TP cao; LEG 2 = mục tiêu
        x0 = X(s.k) + 4 * S
        d.rectangle([x0, min(Y(s.entry), Y(s.sl)), R, max(Y(s.entry), Y(s.sl))], fill=(120, 20, 25, 150))
        d.rectangle([x0, min(Y(s.entry), Y(s.tp)), R, max(Y(s.entry), Y(s.tp))], fill=(14, 70, 60, 150))
        xl2 = (self.X(s.k) + W) / 2 + 30
        _vline(d, xl2 * S, Y(s.entry), Y(s.tp), (225, 160, 70, 230), 3)
        sgn = -1 if s.side == "buy" else 1
        name_tp = "Resistance - TP1" if s.side == "buy" else "Support - TP1"
        texts += [((xl2, self.Y(s.tp) + 26 * sgn), "LEG 2", ORANGE, "mm", True),
                  ((W - 14, self.Y(s.tp) - 22 * sgn), name_tp, DN if s.side == "buy" else SUPP, "rm", True),
                  ((W - 14, (self.Y(s.sl) + self.Y(s.entry)) / 2), "SL", (255, 120, 120), "rm", True)]
        out = lay.resize((W, H), Image.LANCZOS)
        clip = Image.new("L", (W, H), 0)                 # đường kẻ chỉ trong vùng biểu đồ (không cắt qua chữ ghi chú)
        ImageDraw.Draw(clip).rectangle([0, PLOT[1] - 60, W, PLOT[3] + 30], fill=255)
        out.putalpha(ImageChops.multiply(out.getchannel("A"), clip))
        self._place(out, texts)
        return out

    def _place(self, out: Image.Image, texts: list):
        """Đặt nhãn không đè nến / không đè nhau / nhãn biểu đồ không lấn vào hộp lệnh; nền tối mờ cho dễ đọc."""
        s = self.s
        f = sans("SemiBold", 25)
        bw = max(5.0, self.slot * 0.7) / 2 + 3
        busy = [(self.X(i) - bw, self.Y(s.h[i]) - 3, self.X(i) + bw, self.Y(s.l[i]) + 3)
                for i in range(max(0, int(self.i0)), s.hit + 1)]
        box = (self.X(s.k) + 4, min(self.Y(s.tp), self.Y(s.sl)), W, max(self.Y(s.tp), self.Y(s.sl)))
        placed = []

        def hit_area(r, rects):
            return sum(max(0, min(r[2], q[2]) - max(r[0], q[0])) * max(0, min(r[3], q[3]) - max(r[1], q[1])) for q in rects)
        d = ImageDraw.Draw(out, "RGBA")
        offs = [(0, 0), (0, -30), (0, 30), (0, -58), (0, 58), (-90, 0), (90, 0), (-90, -30), (90, -30),
                (-90, 30), (90, 30), (0, -90), (0, 90), (-170, 0), (170, 0)]
        for (x, y), t, c, anc, inbox in texts:
            l_, t_, r_, b_ = f.getbbox(t)
            tw, th = r_ - l_, b_ - t_
            best = None
            for dx, dy in offs:
                cx = x + dx
                x0 = cx - tw / 2 if anc == "mm" else (cx if anc == "lm" else cx - tw)
                y0 = y + dy - th / 2
                r = (x0 - 8, y0 - 6, x0 + tw + 8, y0 + th + 6)
                if r[0] < 6 or r[2] > W - 6 or r[1] < PLOT[1] - 80 or r[3] > PLOT[3] + 60:
                    continue
                bad = hit_area(r, busy) * 3 + hit_area(r, placed) * 5 + (0 if inbox else hit_area(r, [box]) * 4)
                if inbox and not (r[0] >= box[0] - 2):
                    bad += 1e6
                if best is None or bad < best[0]:
                    best = (bad, r, x0, y0)
                if bad == 0:
                    break
            if best is None:
                continue
            _, r, x0, y0 = best
            placed.append(r)
            d.rounded_rectangle(r, radius=8, fill=(0, 0, 0, 150))
            d.text((x0 - l_, y0 - t_), t, font=f, fill=c + (255,))

    def candles(self, shown: float, profit_to: float | None) -> Image.Image:
        s, S = self.s, 2
        lay = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay, "RGBA")
        X = lambda i: self.X(i) * S
        Y = lambda p: self.Y(p) * S
        if profit_to is not None:                      # vùng lời sáng dần theo giá (như TradingView)
            x0 = X(s.k) + 4 * S
            d.rectangle([x0, min(Y(s.entry), Y(profit_to)), W * S, max(Y(s.entry), Y(profit_to))], fill=(30, 150, 125, 120))
        bw = max(5.0, self.slot * 0.7) * S
        last = min(int(shown), len(s.c))
        part = shown - int(shown)
        for i in range(max(0, int(self.i0) - 1), last + (1 if part > 0.02 and last < len(s.c) else 0)):
            o_, h_, l_, c_ = s.o[i], s.h[i], s.l[i], s.c[i]
            if i == last:                              # nến đang chạy
                if i == s.hit:                         # nến cú vọt: giá lao thẳng tới đỉnh (dừng video ở đó)
                    ext = h_ if s.side == "buy" else l_
                    c_ = o_ + (ext - o_) * min(1.0, part / 0.75)
                    h_, l_ = max(o_, c_), min(o_, c_)
                else:
                    c_ = o_ + (c_ - o_) * part
                    h_, l_ = max(o_, c_, o_ + (h_ - o_) * part), min(o_, c_, o_ + (l_ - o_) * part)
            col = UP if c_ >= o_ else DN
            d.line([(X(i), Y(h_)), (X(i), Y(l_))], fill=col + (255,), width=max(2, int(self.slot * 0.1 * S)))
            ya, yb = sorted((Y(o_), Y(c_)))
            d.rectangle([X(i) - bw / 2, ya, X(i) + bw / 2, max(yb, ya + 3)], fill=col + (255,))
        return lay.resize((W, H), Image.LANCZOS)


def _scaled(layer: Image.Image, sc: float, cx: float, cy: float) -> Image.Image:
    """Thu/phóng một lớp quanh tâm (cx, cy)."""
    if abs(sc - 1) < 0.002:
        return layer
    w, h = int(W * sc), int(H * sc)
    small = layer.resize((max(1, w), max(1, h)), Image.BILINEAR)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.alpha_composite(small, (int(cx - cx * sc), int(cy - cy * sc))) if sc <= 1 else \
        out.alpha_composite(small.crop((int(cx * sc - cx), int(cy * sc - cy), int(cx * sc - cx) + W, int(cy * sc - cy) + H)))
    return out


def _wipe(layer: Image.Image, k: float) -> Image.Image:
    """Quét lộ từ trái sang phải (mép mềm) – kiểu hệ thống 'phóng ra'."""
    if k >= 1:
        return layer
    edge = int(W * k)
    mask = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(mask)
    dm.rectangle([0, 0, edge, H], fill=255)
    for j in range(60):
        dm.line([(edge + j, 0), (edge + j, H)], fill=int(255 * (1 - j / 60)))
    a = ImageChops.multiply(layer.getchannel("A"), mask)
    out = layer.copy()
    out.putalpha(a)
    return out


def frames(s: Setup, t_run0: float, t_peak: float, total: float, lvl, on):
    q = Quiz(s)
    mark = _logo("official/decode_mark_dark_bg.png", 56)
    wm = _logo("official/decode_mark_dark_bg.png", 420)  # watermark: CHỈ logo (không chữ), giữa màn hình, mờ
    wm.putalpha(wm.getchannel("A").point(lambda a: int(a * 0.16)))
    run_bars = s.hit - s.k
    side_txt = "SELL!" if s.side == "sell" else "BUY!"
    side_col = T_RED if s.side == "sell" else T_GREEN
    risk = abs(s.entry - s.sl)
    t_cross = None
    ccx, ccy = q.X(s.k - 15), q.Y((q.lo + q.hi) / 2)  # tâm phóng to lúc mở đầu (giữa cụm nến)
    for fno in range(int(total * FPS)):
        t = fno / FPS
        e_l, e_o = float(lvl[min(fno, len(lvl) - 1)]), float(on[min(fno, len(on) - 1)])
        img = Image.new("RGBA", (W, H), BG + (255,))
        img.alpha_composite(wm, (W // 2 - wm.width // 2, H // 2 - wm.height // 2))
        # ---- biểu đồ + vùng lời
        if t < t_run0:
            shown, prof = s.k + 1, None
        else:
            shown = min(s.hit + 0.75, s.k + 1 + ease_in((t - t_run0) / RUN_T) * (run_bars - 0.25))
            i, part = int(shown), shown - int(shown)
            done = s.l[s.k + 1: i] if s.side == "sell" else s.h[s.k + 1: i]
            ext = s.l[i] if s.side == "sell" else s.h[i]
            if i == s.hit:
                cur = s.o[i] + (ext - s.o[i]) * min(1.0, part / 0.75)
            else:
                cur = s.o[i] + (ext - s.o[i]) * part
            prof = min(done + [cur, s.entry]) if s.side == "sell" else max(done + [cur, s.entry])
        chart = q.candles(shown, prof)
        if t >= T_REVEAL:                              # hệ thống quét phóng ra + phóng nhẹ 1.06 → 1
            kb = (t - T_REVEAL) / BURST
            ann = _wipe(q.ann_layer, ease(kb))
            ann = _scaled(ann, 1 + 0.06 * (1 - ease((t - T_REVEAL) / 0.3)), W / 2, H / 2)
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            layer.alpha_composite(ann)
            layer.alpha_composite(chart)
            chart = layer
        sc = 0.3 + 0.7 * ease((t - T_INTRO[0]) / (T_INTRO[1] - T_INTRO[0]))   # mở đầu: nhỏ → to
        img.alpha_composite(_scaled(chart, sc, ccx, ccy))
        # ---- thương hiệu + cặp tiền
        img.alpha_composite(mark, (36, 60))
        _txt(img, (36 + mark.width + 12, 60 + mark.height / 2), "DECODE", serif(700, 28), WHITE, 0.95, "lm")
        _txt(img, (W - 36, 60 + mark.height / 2), s.symbol, sans("ExtraBold", 34), WHITE, 0.95, "rm")
        # ---- tiêu đề BUY OR SeLL? (giật lúc xuất hiện) / đáp án
        title = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
        if t < T_REVEAL:
            f = toon(132)
            dt = ImageDraw.Draw(title)
            parts = [("BUY ", T_GREEN), ("OR ", T_YELLOW), ("SeLL?", T_RED)]
            tw = sum(dt.textlength(p, font=f) for p, _ in parts)
            x = W / 2 - tw / 2
            for p, col in parts:
                _txt(title, (x, 160), p, f, col, 1.0, "lm", stroke=4)
                x += dt.textlength(p, font=f)
            if t < 0.4:
                title = glitch(title, 1 - t / 0.4, fno)
        else:
            k = ease_back((t - T_REVEAL) / 0.3)
            _txt(title, (W / 2, 160), side_txt, toon(int(170 * (0.6 + 0.4 * k))), side_col, k, stroke=5)
        img.alpha_composite(title, (0, 110))
        # ---- đếm ngược 05 → 01 (số bật to rồi thu về vòng tròn)
        if T_COUNT <= t < T_REVEAL - 0.1:
            num = 5 - int(t - T_COUNT)
            fr = (t - T_COUNT) % 1
            cx, cy, r = 110, 470, 50
            lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            dl = ImageDraw.Draw(lay)
            dl.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255, 60), width=4)
            dl.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + 360 * (1 - fr), fill=WHITE + (235,), width=5)
            img.alpha_composite(lay)
            pop = 1 - ease(fr / 0.22)
            _txt(img, (cx, cy), f"{num:02d}", sans("Bold", int(44 * (1 + 0.9 * pop))), WHITE)
        # ---- bộ đếm R chạy theo giá
        if t >= t_run0 and prof is not None:
            rr = max(0.0, abs(prof - s.entry) / risk)
            if t_cross is None and rr >= abs(s.tp - s.entry) / risk:
                t_cross = t
            f = toon(int(120 * (1 + 0.16 * e_o)))
            _txt(img, (W / 2, 1800), f"+{rr:.1f}R", f, T_GREEN, ease((t - t_run0) / 0.12), stroke=6)
        elif t < t_run0:
            _txt(img, (W / 2, 1860), "Dữ liệu quá khứ – không phải tín hiệu", sans("Medium", 20), (110, 110, 125), 0.9)
        # ---- hiệu ứng bám nhạc: giật / rung / nảy / chớp
        gk = max(0.9 - abs(t - T_REVEAL - 0.05) / 0.25, 0)
        if t >= t_run0:
            gk = max(gk, 1 - (t - t_run0) / 0.25, (e_o - 0.3) * 1.3 if e_o > 0.3 else 0)
        if t_cross is not None:
            gk = max(gk, 1 - (t - t_cross) / 0.25)
        if gk > 0:
            img = glitch(img, min(1.0, gk), fno)
        for tf_, a_ in [(T_REVEAL, 0.45), (t_run0, 0.7)] + ([(t_cross, 0.6)] if t_cross else []):
            if 0 <= t - tf_ < 0.12:
                img = Image.blend(img, Image.new("RGBA", (W, H), (255, 255, 255, 255)), a_ * (1 - (t - tf_) / 0.12))
        if t >= t_run0:
            zz = 1 + 0.07 * e_o + 0.02 * e_l
            if zz > 1.003:
                cw, ch = int(W / zz), int(H / zz)
                img = img.crop(((W - cw) // 2, (H - ch) // 2, (W + cw) // 2, (H + ch) // 2)).resize((W, H), Image.BILINEAR)
        yield img.convert("RGB"), t


def lines(s: Setup) -> list[str]:
    # "Bạn sẽ…" – nghỉ – "Buy hay Sell?" (đọc tách 2 đoạn để có quãng nghỉ chắc chắn), lúc lộ: "Buy!" / "Sell!"
    return ["Bạn sẽ…", "Buy hay Sell?", "Sell!" if s.side == "sell" else "Buy!"]


def pick_music(t_run0: float, seed=None) -> tuple[Path | None, float]:
    """Bài có điểm drop đủ muộn để đoạn dạo nhạc phủ phần câu đố."""
    tracks = sorted(MUSIC.glob("*.mp3"))
    random.Random(seed).shuffle(tracks)
    best = None
    for p in tracks:
        dt = M.drop_time(p)
        if dt >= t_run0:
            return p, dt
        best = best or (p, dt)
    return best or (None, 0.0)


def make(s: Setup, folder: Path, music: Path | None = None, seed=None) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    says = lines(s)
    fixed = [VOICE_DIR / "intro.wav", VOICE_DIR / ("sell.wav" if s.side == "sell" else "buy.wav")]
    if all(f.exists() for f in fixed):
        # mọi video dùng ĐÚNG 1 bộ giọng đã duyệt (nhịp, cách nói, độ vang giống nhau) – không tạo giọng mới
        voices = [(fixed[0], 0.3), (fixed[1], T_REVEAL + 0.1)]
    else:
        wavs = voice.synth([spoken(x) for x in says], folder / "voice", voice_index=VOICE_INDEX)
        vd = [voice.duration(w) for w in wavs]
        voices = [(wavs[0], 0.3), (wavs[1], 0.3 + vd[0] + 0.45), (wavs[2], T_REVEAL + 0.1)]
    t_run0 = max(voices[-1][1] + voice.duration(voices[-1][0]) + 0.05, T_REVEAL + 0.9)
    t_peak = t_run0 + RUN_T
    total = t_peak + HOLD
    if music is None:
        music, drop = pick_music(t_run0, seed)
    else:
        drop = M.drop_time(music)
    ss = (drop - t_run0) if music else 0.0
    if music:
        lvl, on = M.envelope(music, ss, total, FPS)
    else:
        import numpy as np
        lvl = on = np.zeros(int(total * FPS) + 1)
    silent = folder / "reel.video.mp4"
    wr = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                           "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
    thumb = None
    for img, t in frames(s, t_run0, t_peak, total, lvl, on):
        wr.stdin.write(img.tobytes())
        if thumb is None and t >= 4.0:
            thumb = img
    wr.stdin.close()
    if wr.wait():
        raise RuntimeError("ffmpeg lỗi khi dựng hình")
    events = [(T_COUNT + i, "pop", 0.5) for i in range(5)]
    events += [(T_REVEAL, "whoosh", 0.8), (max(0.0, t_run0 - 1.6), "riser", 0.4), (t_run0, "boom", 0.9)]
    shaped = M.shape(music, ss, T_COUNT, T_REVEAL, t_run0, total, folder / "music.wav") if music else None
    mix(silent, voices, events, total, folder / "reel.mp4", shaped,
        music_ss=0.0, music_vol=1.0, music_fade=0.05, music_norm=False)   # nhạc đã dựng cao trào; hết ngay ở đỉnh
    if shaped:
        shaped.unlink(missing_ok=True)
    silent.unlink(missing_ok=True)
    (thumb or Image.new("RGB", (W, H), BG)).save(folder / "thumb.jpg", quality=92)
    rr = ((s.entry - s.l[s.hit]) if s.side == "sell" else (s.h[s.hit] - s.entry)) / abs(s.entry - s.sl)
    info = {"symbol": s.symbol, "tf": s.tf, "system": s.system, "name": s.name, "side": s.side, "entry": s.entry,
            "sl": s.sl, "tp": s.tp, "bars_to_peak": s.hit - s.k, "rr": round(rr, 1),
            "music": music.name if music else None, "says": says}
    (folder / "setup.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    return {"video": folder / "reel.mp4", "thumb": folder / "thumb.jpg", "duration": round(total, 1), "setup": s,
            "voices": ([v for v, _ in voices], says), "t_run0": t_run0, "t_peak": t_peak}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="GBPUSD")
    ap.add_argument("--system", choices=SYSTEMS)
    ap.add_argument("--tf", default="M5")
    ap.add_argument("--out")
    ap.add_argument("--music")
    ap.add_argument("--entry", type=float, help="dựng lại đúng lệnh cũ theo giá vào")
    a = ap.parse_args()
    s = find(a.symbol, a.tf, [a.system] if a.system else None, want=a.entry)
    if s is None:
        raise SystemExit("Không tìm được setup phù hợp")
    r = make(s, Path(a.out) if a.out else OUTPUT / "reels" / "quiz", Path(a.music) if a.music else None)
    print(json.dumps({k: str(v) for k, v in r.items() if k not in ("setup", "voices")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
