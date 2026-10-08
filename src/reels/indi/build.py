"""Reels "SIGNAL REPLAY" – quảng bá indicator BOSS M5 SNIPER AI (V7 / V4) cho Page DecodeFx Trading.

Khuôn (không lời – chỉ chữ + nhạc + hiệu ứng, nên không phụ thuộc dịch vụ giọng đọc):
  0.0s  tiêu đề + tên indicator giật vào, biểu đồ vàng M5 kiểu TradingView tua nhanh tới trước điểm vào
  ~3s   nến tín hiệu đóng → chớp sáng, NHÃN LỆNH bật ra đúng như indicator vẽ (BUY/SELL, ENTRY, SL, TP1-3, điểm xác nhận)
        + kẻ các mức ENTRY / SL / TP1 / TP2 / TP3 (nhạc drop đúng lúc này)
  sau đó nến chạy thật tới khi đóng lệnh: chạm TP nào bật huy hiệu TP đó, V7 dời SL về hoà / khoá TP1 như indicator
  cuối  thẻ kết quả: +pips, thời gian giữ lệnh, tên indicator, lời kêu gọi
Dòng chú thích luôn hiện: dữ liệu quá khứ, tín hiệu chọn lọc, không phải lời khuyên đầu tư.

    python -m src.reels.indi.build --version V7 --pick 0
"""
import argparse
import json
import random
import subprocess
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.config import OUTPUT, ROOT
from src.design.common import sans
from src.reels.edu.build import mix
from src.reels.indi import boss
from src.reels.quiz import music as M
from src.reels.quiz.build import ease, ease_back, glitch

W, H, FPS = 1080, 1920, 30
VN = ZoneInfo("Asia/Ho_Chi_Minh")
BG, GRID, AXIS = (13, 16, 23), (28, 33, 44), (120, 126, 140)
UP, DN = (38, 166, 154), (239, 83, 80)
WHITE, GOLD, GREEN, RED, BLUE = (255, 255, 255), (247, 205, 15), (34, 197, 94), (239, 68, 68), (59, 130, 246)
AQUA, ORANGE = (0, 188, 212), (255, 152, 0)
PLOT = (28, 500, 952, 1480)                  # vùng nến; trục giá bên phải tới mép
HIST = 46                                    # số nến trước điểm vào hiện trên khung
T_SIG = 3.2                                  # nến tín hiệu đóng
T_RUN = 4.6                                  # bắt đầu chạy lệnh
OUTRO = 3.2
MUSIC = ROOT / "assets" / "music" / "cwg"
# Slogan + lời kêu gọi (anh chốt 08/10/2026) – hiện chữ VÀ đọc bằng giọng voice 01
SLOGAN = ("1 CHỈ BÁO MIỄN PHÍ", "GIÚP ANH CHỊ EM KIẾM 100PIP MỖI NGÀY")
SLOGAN_VOICE = "Một chỉ báo miễn phí, giúp anh chị em kiếm một trăm píp mỗi ngày."
CTA_END = "Liên hệ qua Page để sử dụng miễn phí"
CTA_VOICE = "Liên hệ qua Pết để sử dụng miễn phí nhá."        # "Pết": giọng đọc tự nhiên, chữ trên video vẫn là "Page"
VOICE = ROOT / "assets" / "private" / "voice_ref_decode_trading.mp3"
NAME = {"V7": "SNIPER AI V7", "V4": "SNIPER AI V4"}


@lru_cache(maxsize=None)
def toon(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(ROOT / "assets" / "fonts" / "LuckiestGuy-Regular.ttf"), size)


def _logo(name, h):
    im = Image.open(ROOT / "assets" / "brands" / "decode" / "official" / name).convert("RGBA")
    return im.resize((round(im.width * h / im.height), h), Image.LANCZOS)


def pips(x: float) -> int:
    return round(abs(x) * 10)                 # vàng: 1 pip = 0.1 giá


class Replay:
    def __init__(self, d, t: boss.Trade):
        self.d, self.t = d, t
        self.i_start = max(0, t.i0 - HIST)
        self.i_end = min(len(d) - 1, t.i1 + 4)
        self.n = self.i_end - self.i_start + 1
        self.slot = (PLOT[2] - PLOT[0]) / (self.n + 7)          # chừa khoảng phải cho nhãn các mức
        seg = d.iloc[self.i_start:self.i_end + 1]
        lo = min(seg.low.min(), t.sl, t.tp(2))
        hi = max(seg.high.max(), t.sl, t.tp(2))
        span = hi - lo
        # chừa chỗ cho nhãn lệnh (BUY: dưới nến, SELL: trên nến) như TradingView
        if t.side == 1:
            lo -= span * 0.42
        else:
            hi += span * 0.42
        self.lo, self.hi = lo - span * 0.04, hi + span * 0.04
        self.O, self.Hh, self.L, self.C = (d[c].to_numpy() for c in ("open", "high", "low", "close"))
        self.e20, self.e50 = d.e20.to_numpy(), d.e50.to_numpy()

    def X(self, i):
        return PLOT[0] + (i - self.i_start + 0.8) * self.slot

    def Y(self, p):
        return PLOT[1] + (self.hi - p) / (self.hi - self.lo) * (PLOT[3] - PLOT[1])

    def grid(self) -> Image.Image:
        img = Image.new("RGBA", (W, H), BG + (255,))
        d = ImageDraw.Draw(img)
        step = _nice((self.hi - self.lo) / 7)
        p = (self.lo // step + 1) * step
        f = sans("Medium", 22)
        while p < self.hi:
            y = self.Y(p)
            d.line([(PLOT[0], y), (PLOT[2], y)], fill=GRID, width=1)
            d.text((PLOT[2] + 12, y), f"{p:.0f}" if step >= 1 else f"{p:.1f}", font=f, fill=AXIS, anchor="lm")
            p += step
        for i in range(self.i_start, self.i_end + 1, 12):
            d.line([(self.X(i), PLOT[1]), (self.X(i), PLOT[3])], fill=GRID, width=1)
            d.text((self.X(i), PLOT[3] + 22), self.d.index[i].astimezone(VN).strftime("%H:%M"), font=f, fill=AXIS,
                   anchor="mm")
        d.line([(PLOT[2], PLOT[1] - 20), (PLOT[2], PLOT[3])], fill=(40, 46, 60), width=2)
        return img

    def chart(self, shown: float, img: Image.Image):
        """shown: số nến (thực) đã chạy kể từ i_start – nến cuối đang hình thành dở."""
        d = ImageDraw.Draw(img, "RGBA")
        last = self.i_start + int(shown)
        part = shown - int(shown)
        bw = max(4.0, self.slot * 0.68)
        for e, col in ((self.e50, ORANGE), (self.e20, AQUA)):
            pts = [(self.X(i), self.Y(e[i])) for i in range(self.i_start, min(last, self.i_end) + 1) if not np.isnan(e[i])]
            if len(pts) > 1:
                d.line(pts, fill=col + (200,), width=3, joint="curve")
        for i in range(self.i_start, min(last, self.i_end) + 1):
            o, h, l, c = self.O[i], self.Hh[i], self.L[i], self.C[i]
            if i == last and part < 0.999:                       # nến đang chạy
                k = part
                c = o + (c - o) * k
                h, l = max(o, c, o + (h - o) * min(1, k * 1.4)), min(o, c, o + (l - o) * min(1, k * 1.4))
            elif i == last:
                pass
            col = UP if c >= o else DN
            x = self.X(i)
            d.line([(x, self.Y(h)), (x, self.Y(l))], fill=col, width=max(2, int(self.slot * 0.12)))
            ya, yb = sorted((self.Y(o), self.Y(c)))
            d.rectangle([x - bw / 2, ya, x + bw / 2, max(yb, ya + 2)], fill=col)
        if last <= self.i_end:                                   # nhãn giá hiện tại trên trục
            i = min(last, self.i_end)
            c = self.C[i] if part >= 0.999 or i != last else self.O[i] + (self.C[i] - self.O[i]) * part
            col = UP if c >= self.O[i] else DN
            y = self.Y(c)
            d.line([(PLOT[0], y), (PLOT[2], y)], fill=col + (90,), width=1)
            d.rectangle([PLOT[2] + 2, y - 17, W, y + 17], fill=col)
            d.text((PLOT[2] + 12, y), f"{c:.2f}", font=sans("Bold", 22), fill=WHITE, anchor="lm")
            return c
        return self.C[self.i_end]

    def levels(self, img, k: float, stop: float, hit: set):
        """Các mức của lệnh (kẻ dần từ điểm vào sang phải, k 0..1)."""
        t = self.t
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        x0 = self.X(t.i0)
        x1 = x0 + (PLOT[2] - x0) * ease(k)
        f = sans("Bold", 21)
        rows = [("ENTRY", t.entry, BLUE, 3), ("SL" if stop == t.sl else ("BE" if stop == t.entry else "SL→TP1"), stop,
                                               RED if stop == t.sl else ORANGE, 4)]
        rows += [(f"TP{j + 1}", t.tp(j), GREEN, 2 + j) for j in range(3)]
        if stop == t.sl:                                         # vùng lỗ / lời như công cụ vị thế
            d.rectangle([x0, min(self.Y(t.entry), self.Y(t.sl)), x1, max(self.Y(t.entry), self.Y(t.sl))], fill=RED + (34,))
        d.rectangle([x0, min(self.Y(t.entry), self.Y(t.tp(2))), x1, max(self.Y(t.entry), self.Y(t.tp(2)))],
                    fill=GREEN + (26,))
        for name, p, col, wdt in rows:
            y = self.Y(p)
            d.line([(x0, y), (x1, y)], fill=col + (235,), width=wdt)
            if k > 0.6:
                a = int(255 * min(1, (k - 0.6) / 0.4))
                tag = name
                tw = d.textlength(tag, font=f)
                xr = x1 - 4 - (90 if name != "SL" and col == ORANGE else 0)   # SL đã dời trùng mức khác → lệch trái
                d.rounded_rectangle([xr - tw - 18, y - 30, xr, y - 4], radius=6, fill=col + (int(a * 0.9),))
                d.text((xr - 9 - tw, y - 17), tag, font=f, fill=WHITE + (a,), anchor="lm")
        img.alpha_composite(lay)

    def label(self, img, k: float):
        """Nhãn lệnh đúng nội dung indicator vẽ trên TradingView."""
        if k <= 0:
            return
        t = self.t
        lines = [f"{'BUY' if t.side == 1 else 'SELL'} {t.setup}" if t.version == "V7" else ("BUY" if t.side == 1 else "SELL"),
                 f"ENTRY: {t.entry:.2f}", f"SL: {t.sl:.2f}", f"TP1: {t.tp(0):.2f}", f"TP2: {t.tp(1):.2f}",
                 f"TP3: {t.tp(2):.2f}",
                 f"CONFIRM: {t.score}/5" if t.version == "V7" else f"SCORE: {t.score}/9"]
        f, fb = sans("SemiBold", 25), sans("ExtraBold", 28)
        lh = 34
        wbox = max(ImageDraw.Draw(img).textlength(s, font=fb if j == 0 else f) for j, s in enumerate(lines)) + 36
        hbox = lh * len(lines) + 22
        col = GREEN if t.side == 1 else RED
        x = self.X(t.i0)
        anchor_y = self.Y(self.L[t.i0]) + 12 if t.side == 1 else self.Y(self.Hh[t.i0]) - 12
        bx = min(max(x - wbox / 2, PLOT[0] + 4), PLOT[2] - wbox - 4)
        by = anchor_y + 16 if t.side == 1 else anchor_y - 16 - hbox
        sc = 0.4 + 0.6 * ease_back(k)
        lay = Image.new("RGBA", (int(wbox) + 2, int(hbox) + 2), (0, 0, 0, 0))
        dl = ImageDraw.Draw(lay)
        dl.rounded_rectangle([0, 0, wbox, hbox], radius=10, fill=col + (245,))
        for j, s in enumerate(lines):
            dl.text((18, 12 + j * lh), s, font=fb if j == 0 else f, fill=WHITE)
        if sc != 1:
            lay = lay.resize((max(1, int(lay.width * sc)), max(1, int(lay.height * sc))), Image.LANCZOS)
        cx = bx + wbox / 2
        cy = by if t.side == 1 else by + hbox
        d = ImageDraw.Draw(img, "RGBA")
        tip = [(x, anchor_y), (x - 12, cy if t.side == 1 else cy), (x + 12, cy)]
        d.polygon(tip, fill=col + (245,))
        px = int(cx - lay.width / 2)
        py = int(cy) if t.side == 1 else int(cy - lay.height)
        img.alpha_composite(lay, (px, py))


def _nice(x):
    for m in (0.5, 1, 2, 2.5, 5, 10, 20, 25, 50):
        if x <= m:
            return m
    return 100


def _txt(img, xy, text, font, col, alpha=1.0, anchor="mm", stroke=0):
    if alpha <= 0.01:
        return
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    a = int(255 * min(1, alpha))
    ImageDraw.Draw(lay).text(xy, text, font=font, fill=col + (a,), anchor=anchor, stroke_width=stroke,
                             stroke_fill=(0, 0, 0, a))
    img.alpha_composite(lay)


def timeline(t: boss.Trade):
    """Thời điểm từng nến: tua nhanh lịch sử → nến tín hiệu → chạy lệnh (mỗi nến ~0.5s, chậm dần khi tới TP)."""
    n_hist = t.i0 - max(0, t.i0 - HIST)
    run = t.i1 - t.i0
    per = min(0.75, max(0.32, 5.0 / max(1, run)))
    t_end = T_RUN + run * per
    return n_hist, run, per, t_end


def frames(r: Replay, lvl, on, total):
    t = r.t
    n_hist, run, per, t_end = timeline(t)
    base = r.grid()
    mark = _logo("decode_mark_dark_bg.png", 64)
    wm = _logo("decode_mark_dark_bg.png", 460)
    wm.putalpha(wm.getchannel("A").point(lambda a: int(a * 0.07)))
    base.alpha_composite(wm, (PLOT[0] + (PLOT[2] - PLOT[0]) // 2 - wm.width // 2, (PLOT[1] + PLOT[3]) // 2 - wm.height // 2))
    hit_at = {name: T_RUN + (i - t.i0 - 0.35) * per for i, name, _ in t.hits}
    minutes = (t.i1 - t.i0) * 5
    gain = pips(t.pnl)
    dt_vn = r.d.index[t.i0].astimezone(VN)
    for fno in range(int(total * FPS)):
        s = fno / FPS
        e_o = float(on[min(fno, len(on) - 1)])
        img = base.copy()
        # ---- tiến trình nến
        if s < T_SIG - 0.6:
            shown = ease(s / (T_SIG - 0.6)) * (n_hist - 0.001)
        elif s < T_SIG:
            shown = n_hist + (s - (T_SIG - 0.6)) / 0.6 - 0.001          # nến tín hiệu hình thành
        elif s < T_RUN:
            shown = n_hist + 0.999
        else:
            shown = min(n_hist + run + 0.999, n_hist + 1 + (s - T_RUN) / per)
            if s >= t_end:
                shown = min(r.n - 0.001, n_hist + run + 1 + (s - t_end) / 0.3)
        cur_bar = r.i_start + int(shown)
        hit = {name for i, name, _ in t.hits if i < cur_bar or (i == cur_bar and shown - int(shown) > 0.65)}
        stop = t.sl
        if t.version == "V7":
            if "TP2" in hit:
                stop = t.tp(0)
            elif "TP1" in hit:
                stop = t.entry
        if s >= T_SIG:
            r.levels(img, min(1, (s - T_SIG) / 0.45), stop, hit)
        price = r.chart(shown, img)
        if s >= T_SIG:
            r.label(img, min(1, (s - T_SIG) / 0.35))
        # ---- đầu trang: thương hiệu + tiêu đề
        img.alpha_composite(mark, (40, 64))
        _txt(img, (40 + mark.width + 14, 64 + mark.height / 2), "DecodeFx Trading", sans("ExtraBold", 34), WHITE, 1, "lm")
        _txt(img, (W - 40, 64 + mark.height / 2), "XAUUSD · M5", sans("Bold", 30), (200, 205, 215), 1, "rm")
        head = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
        _txt(head, (W / 2, 70), NAME[t.version], sans("ExtraBold", 40), GOLD, 1)
        _txt(head, (W / 2, 160), SLOGAN[0], sans("ExtraBold", 100), GOLD, 1, stroke=4)   # font có đủ dấu tiếng Việt
        _txt(head, (W / 2, 250), SLOGAN[1], sans("ExtraBold", 46), WHITE, 1, stroke=3)
        if s < 0.45:
            head = glitch(head, 1 - s / 0.45, fno)
        img.alpha_composite(head, (0, 160))
        # ---- bộ đếm pips trôi theo giá (sau khi vào lệnh)
        if s >= T_RUN and s < total - OUTRO:
            fl = t.pnl if s >= t_end else t.side * (price - t.entry)    # đóng lệnh xong: giữ đúng kết quả
            col = GREEN if fl >= 0 else RED
            _txt(img, (W / 2, 1600), f"{'+' if fl >= 0 else '-'}{pips(fl)} pips", toon(int(104 * (1 + 0.12 * e_o))), col,
                 1, stroke=5)
        # ---- huy hiệu TP vừa chạm (chỉ hiện mức mới nhất)
        recent = [(at, name) for name, at in hit_at.items() if name.startswith("TP") and 0 <= s - at < 1.2]
        if recent and s < total - OUTRO:
            at, name = max(recent)
            k = (s - at) / 1.2
            j = int(name[2]) - 1
            _txt(img, (W / 2, 1730), f"CHẠM {name}  ·  +{pips(boss.TP[j])} PIPS",
                 sans("ExtraBold", int(56 * (0.7 + 0.3 * ease_back(min(1, k * 3))))), GREEN, 1 - max(0, (k - 0.75) / 0.25))
        _txt(img, (W / 2, 1872), "Công cụ chỉ báo hỗ trợ · không phải lời khuyên đầu tư",
             sans("Medium", 22), (120, 126, 140), 1)
        # ---- thẻ kết quả cuối video
        if s >= total - OUTRO:
            k = (s - (total - OUTRO)) / 0.35
            dim = Image.new("RGBA", (W, H), (5, 7, 12, int(200 * min(1, k))))
            img.alpha_composite(dim)
            ko = ease_back(min(1, k))
            _txt(img, (W / 2, 640), "KẾT QUẢ LỆNH", sans("Bold", 40), (200, 205, 215), min(1, k))
            _txt(img, (W / 2, 800), f"+{gain} PIPS", toon(int(190 * (0.6 + 0.4 * ko))), GREEN, min(1, k), stroke=6)
            _txt(img, (W / 2, 950), f"Chạm {t.result} sau {minutes} phút", sans("Bold", 50), WHITE, min(1, (k - 0.6) * 2))
            _txt(img, (W / 2, 1040), f"{'BUY' if t.side == 1 else 'SELL'} {t.entry:.2f}  >>  {t.entry + t.side * t.pnl:.2f}",
                 sans("Medium", 38), (200, 205, 215), min(1, (k - 0.8) * 2))
            box = (110, 1180, W - 110, 1380)
            if k > 1:
                a = min(1, (k - 1) * 2)
                bl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                ImageDraw.Draw(bl).rounded_rectangle(box, radius=24, outline=GOLD + (int(220 * a),), width=3,
                                                     fill=(247, 205, 15, int(22 * a)))
                img.alpha_composite(bl)
                _txt(img, (W / 2, 1245), NAME[t.version], sans("ExtraBold", 44), GOLD, a)
                _txt(img, (W / 2, 1318), CTA_END, sans("SemiBold", 36), WHITE, a)
        # ---- hiệu ứng: chớp + giật lúc tín hiệu, nảy theo nhạc khi chạy lệnh
        gk = max(0.0, 0.85 - abs(s - T_SIG) / 0.22)
        for at in hit_at.values():
            gk = max(gk, 0.6 - abs(s - at) / 0.2)
        if gk > 0:
            img = glitch(img, min(1.0, gk), fno)
        if 0 <= s - T_SIG < 0.12:
            img = Image.blend(img, Image.new("RGBA", (W, H), (255, 255, 255, 255)), 0.5 * (1 - (s - T_SIG) / 0.12))
        if T_SIG <= s < total - OUTRO:
            zz = 1 + 0.035 * e_o
            if zz > 1.003:
                cw, ch = int(W / zz), int(H / zz)
                img = img.crop(((W - cw) // 2, (H - ch) // 2, (W + cw) // 2, (H + ch) // 2)).resize((W, H), Image.BILINEAR)
        yield img.convert("RGB"), s


def pick_music(seed=None):
    tracks = sorted(MUSIC.glob("*.mp3"))
    random.Random(seed).shuffle(tracks)
    for p in tracks:
        dt = M.drop_time(p)
        if dt >= T_SIG:
            return p, dt
    return (tracks[0], M.drop_time(tracks[0])) if tracks else (None, 0.0)


def cover(frame: Image.Image, t: boss.Trade) -> Image.Image:
    """Thumbnail: slogan khổng lồ trên nền tối + chart lúc tín hiệu bật ra."""
    img = frame.convert("RGBA")
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dt = ImageDraw.Draw(top)
    dt.rectangle([0, 0, W, 800], fill=BG + (255,))
    dt.rounded_rectangle([W / 2 - 200, 170, W / 2 + 200, 236], radius=33, fill=GOLD + (255,))
    img.alpha_composite(top)
    mark = _logo("decode_mark_dark_bg.png", 64)
    img.alpha_composite(mark, (40, 64))
    _txt(img, (40 + mark.width + 14, 96), "DecodeFx Trading", sans("ExtraBold", 34), WHITE, 1, "lm")
    _txt(img, (W / 2, 203), NAME[t.version], sans("ExtraBold", 38), BG, 1)
    _txt(img, (W / 2, 365), "1 CHỈ BÁO", sans("ExtraBold", 132), GOLD, 1, stroke=6)   # giãn dòng: dấu Ễ không chạm dòng trên
    _txt(img, (W / 2, 560), "MIỄN PHÍ", sans("ExtraBold", 132), GREEN, 1, stroke=6)
    _txt(img, (W / 2, 720), "KIẾM 100PIP MỖI NGÀY", sans("ExtraBold", 68), WHITE, 1, stroke=4)
    return img.convert("RGB")


def make(d, t: boss.Trade, folder: Path, music: Path | None = None, seed=None, voice_on: bool = True) -> dict:
    global T_SIG, T_RUN, OUTRO
    folder.mkdir(parents=True, exist_ok=True)
    voices = []
    T_SIG, T_RUN, OUTRO = 3.2, 4.6, 3.2
    if voice_on and VOICE.exists():
        from src.reels import voice
        w_slogan, w_cta = voice.synth([SLOGAN_VOICE, CTA_VOICE], folder / "voice", ref=VOICE)
        d1, d2 = voice.duration(w_slogan), voice.duration(w_cta)
        T_SIG = max(3.2, 0.25 + d1 + 0.4)                   # tín hiệu bật ra ngay sau câu slogan
        T_RUN = T_SIG + 1.4
        OUTRO = max(3.2, d2 + 1.2)
        voices = [(w_slogan, 0.25), (w_cta, None)]
    r = Replay(d, t)
    _, _, _, t_end = timeline(t)
    total = t_end + 0.8 + OUTRO
    voices = [(w, at if at is not None else total - OUTRO + 0.5) for w, at in voices]
    if music is None:
        music, drop = pick_music(seed)
    else:
        drop = M.drop_time(music)
    ss = drop - T_SIG if music else 0.0                    # drop nhạc rơi đúng lúc tín hiệu bật ra
    if music:
        lvl, on = M.envelope(music, ss, total, FPS)
    else:
        lvl = on = np.zeros(int(total * FPS) + 1)
    silent = folder / "reel.video.mp4"
    wr = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                           "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
    thumb = None
    for img, s in frames(r, lvl, on, total):
        wr.stdin.write(img.tobytes())
        if thumb is None and s >= T_SIG + 0.8:
            thumb = cover(img, t)
    wr.stdin.close()
    if wr.wait():
        raise RuntimeError("ffmpeg lỗi khi dựng hình")
    n_hist, run, per, _ = timeline(t)
    events = [(T_SIG, "boom", 0.8), (T_SIG - 1.6, "riser", 0.35), (total - OUTRO, "whoosh", 0.7)]
    events += [(T_RUN + (i - t.i0 - 0.35) * per, "ting", 0.8) for i, name, _ in t.hits if name.startswith("TP")]
    mix(silent, voices, events, total, folder / "reel.mp4", music, music_ss=ss, music_vol=0.9, music_fade=1.2)
    silent.unlink(missing_ok=True)
    (thumb or Image.new("RGB", (W, H), BG)).save(folder / "thumb.jpg", quality=92)
    info = {"version": t.version, "side": "buy" if t.side == 1 else "sell", "setup": t.setup, "score": t.score,
            "time_utc": d.index[t.i0].isoformat(), "time_vn": d.index[t.i0].astimezone(VN).strftime("%d/%m/%Y %H:%M"),
            "entry": t.entry, "sl": t.sl, "result": t.result, "pips": pips(t.pnl), "minutes": (t.i1 - t.i0) * 5,
            "music": music.name if music else None}
    (folder / "trade.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"video": folder / "reel.mp4", "thumb": folder / "thumb.jpg", "duration": round(total, 1), "info": info}


def best_trades(version: str, raw=None, min_bars: int = 4):
    """Lệnh đẹp để làm nội dung: chạm TP3, đi qua đủ TP1→TP2→TP3 (có diễn biến), nhanh trước."""
    d, tr = boss.run(version, raw=raw)
    good = [t for t in tr if t.result == "TP3" and t.i1 - t.i0 >= min_bars and t.i1 + 4 < len(d)]
    good.sort(key=lambda t: (t.i1 - t.i0))
    return d, good


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="V7", choices=["V7", "V4"])
    ap.add_argument("--pick", type=int, default=0)
    ap.add_argument("--out")
    a = ap.parse_args()
    d, good = best_trades(a.version)
    t = good[a.pick]
    r = make(d, t, Path(a.out) if a.out else OUTPUT / "decode-trading" / "reels" / f"indi_{a.version}_{a.pick}")
    print(json.dumps({k: str(v) for k, v in r.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
