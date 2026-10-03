"""Dựng khung hình Reels kiến thức (phong cách thẻ tối + biểu đồ minh họa) có thương hiệu CWG.

Bố cục 1080×1920 (an toàn với giao diện Reels: chữ/biểu đồ nằm giữa, chừa đáy cho nút + caption):
  ┌ thẻ tối bo góc ───────────────────────────────┐
  │ [NHÃN CHƯƠNG] ───── tiến trình video     [logo] │
  │ Câu thoại hiện dần, [y]từ khoá[/y] tô màu        │
  │ biểu đồ nến minh họa + trục giá + khối lượng   │
  │ (logo CWG chìm giữa biểu đồ)                    │
  │ [icon] CWG MARKETS & PARTNER · handle           │
  └ Dữ liệu minh họa — không phải giá thực ────────┘
"""
import math
import re
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFilter

from src.config import ROOT
from src.design.common import sans
from src.reels.edu.chart import Chart

W, H, FPS = 1080, 1920, 30

BG = (7, 9, 14)
CARD = (13, 17, 25)
CARD_LINE = (36, 43, 58)
GRID = (27, 33, 45)
AXIS = (104, 114, 134)
UP = (38, 196, 160)
DN = (236, 78, 94)
TEXT = (238, 241, 246)
MUTED = (128, 138, 158)
BRAND = (225, 0, 22)
COLORS = {"y": (255, 196, 46), "o": (255, 150, 52), "r": (255, 86, 98), "g": (46, 214, 152),
          "c": (64, 204, 255), "b": (102, 154, 255), "p": (176, 136, 255), "w": TEXT}

VARIANT = 0                       # bố cục thay thế khi bộ kiểm tra thấy nhãn đè/che
# vùng an toàn giao diện Reels (safezone.py): đáy thẻ ≤ 1545 (tên Page + caption), nội dung dưới y=1000 không
# vượt x=915 (cột nút Like/Comment/Share)
CARD_BOX = (40, 165, 1040, 1540)
PLOT = (84, 600, 810, 1310)          # vùng nến (trái, trên, phải, dưới)
VOL = (84, 1325, 810, 1390)
AXIS_X = 822
HEAD_Y = 290
HEAD_W = 912
HEAD_FONT = 50
HEAD_LH = 66


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def prog(t: float, start: float, dur: float) -> float:
    return ease((t - start) / dur) if dur > 0 else float(t >= start)


def mix(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


# ------------------------------------------------------------------ chữ có tô màu
_TAG = re.compile(r"\[(\w)\](.*?)\[/\1\]")


def tokens(text: str) -> list[tuple[str, tuple, bool]]:
    """"Đây là [y]3 giai đoạn[/y]." → [(Đây, trắng), (là, trắng), (3, vàng), (giai, vàng), (đoạn, vàng), (., trắng, dính)].
    Phần tử thứ 3 = True khi dính liền chữ trước (dấu câu ngay sau thẻ màu)."""
    from src.reels.qa import clean
    text = clean(text)
    out, pos = [], 0

    def add(chunk: str, col, before: str):
        first = True
        for w in chunk.split(" "):
            if w:
                glue = first and bool(out) and before not in ("", " ")
                out.append((w, col, glue))
            first = False

    for m in _TAG.finditer(text):
        add(text[pos:m.start()], TEXT, text[pos - 1: pos] if pos else "")
        add(m.group(2), COLORS.get(m.group(1), COLORS["y"]), text[m.start() - 1: m.start()] if m.start() else "")
        pos = m.end()
    add(text[pos:], TEXT, text[pos - 1: pos] if pos else "")
    return out


def plain(text: str) -> str:
    return _TAG.sub(lambda m: m.group(2), text)


def layout(toks, font, width: int) -> list[tuple[float, int, str, tuple]]:
    """Vị trí từng từ: (x, dòng, chữ, màu)."""
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    space = d.textlength(" ", font=font)
    out, x, line = [], 0.0, 0
    for w, col, glue in toks:
        tw = d.textlength(w, font=font)
        if glue and out:
            x -= space
        elif x > 0 and x + tw > width:
            x, line = 0.0, line + 1
        out.append((x, line, w, col))
        x += tw + space
    return out


def word_times(toks, dur: float) -> list[float]:
    """Thời điểm từng từ xuất hiện, bám nhịp đọc (dấu câu = ngừng hơi)."""
    weights = [(0.15 if g else 1.0) + (0.9 if w[-1] in ",.;:!?…" else 0) for w, _, g in toks]
    tot = sum(weights) or 1
    out, acc = [], 0.0
    for wt in weights:
        out.append(dur * 0.92 * acc / tot)
        acc += wt
    return out


# ------------------------------------------------------------------ cấu trúc cảnh
@dataclass
class Mark:
    spec: dict
    at: float            # giây (theo thời gian toàn video) lúc bắt đầu hiện
    key: str


@dataclass
class Scene:
    start: float
    dur: float
    tag: str
    text: str
    chart_id: str | None
    reveal: int                      # số nến hiện tới hết cảnh
    reveal_from: int
    view: tuple                      # (i_trái, i_phải, giá_thấp, giá_cao)
    marks: list = field(default_factory=list)   # Mark hiện trong cảnh này (đã gồm mark cũ còn giữ)
    card: dict | None = None
    voice_at: float = 0.15
    voice_dur: float = 0.0
    toks: list = field(default_factory=list)
    lay: list = field(default_factory=list)
    times: list = field(default_factory=list)


# ------------------------------------------------------------------ nền tĩnh (dựng 1 lần)
def _logo(height: int, path: str = "logo.png") -> Image.Image:
    img = Image.open(ROOT / "assets" / "brands" / "cwg" / path).convert("RGBA")
    return img.resize((round(img.width * height / img.height), height), Image.LANCZOS)


def base_frame() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    glow = Image.new("RGB", (W, H), BG)
    g = ImageDraw.Draw(glow)
    g.ellipse([140, -260, 940, 300], fill=(90, 8, 16))
    g.ellipse([-200, 1500, 500, 2150], fill=(40, 6, 12))
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(160)), 1.0)
    # bóng thẻ
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).rounded_rectangle([CARD_BOX[0] + 6, CARD_BOX[1] + 18, CARD_BOX[2] + 6, CARD_BOX[3] + 24],
                                         radius=40, fill=170)
    img.paste((0, 0, 0), mask=sh.filter(ImageFilter.GaussianBlur(26)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(CARD_BOX, radius=38, fill=CARD, outline=CARD_LINE, width=2)
    # vạch đỏ thương hiệu mảnh trên mép thẻ
    d.rounded_rectangle([CARD_BOX[0] + 300, CARD_BOX[1] - 2, CARD_BOX[2] - 300, CARD_BOX[1] + 3], radius=3, fill=BRAND)
    # logo góc phải trên
    lg = _logo(64, "icon.png")
    img.paste(lg, (CARD_BOX[2] - 44 - lg.width, 190), lg)
    # logo chìm (watermark): cả cụm logo + chữ nằm CHÍNH GIỮA MÀN HÌNH (anh chốt 03/10/2026)
    wm = _logo(260, "icon.png")
    wm.putalpha(wm.getchannel("A").point(lambda v: int(v * 0.07)))
    f = sans("ExtraBold", 40)
    gap, th = 26, 40
    cx = W // 2
    top = H // 2 - (wm.height + gap + th) // 2
    img.paste(wm, (cx - wm.width // 2, top), wm)
    d.text((cx, top + wm.height + gap), "CWG MARKETS", font=f, fill=mix(CARD, TEXT, 0.07), anchor="mt")
    # chân thẻ: thương hiệu + ghi chú dữ liệu minh họa
    ic = _logo(40, "icon.png")
    y = 1442
    img.paste(ic, (84, y - 20), ic)
    d.text((84 + ic.width + 14, y), "CWG MARKETS & PARTNER", font=sans("ExtraBold", 26), fill=TEXT, anchor="lm")
    d.text((84 + ic.width + 14, y + 40), "facebook.com/CWG.Partner", font=sans("Medium", 22), fill=MUTED, anchor="lm")
    d.text((84, 1508), "Dữ liệu minh họa — không phải giá thực", font=sans("Regular", 20), fill=(92, 101, 120),
           anchor="lm")
    return img


# ------------------------------------------------------------------ vẽ thành phần
def _pill(d: ImageDraw.ImageDraw, x: float, y: float, text: str, col, anchor: str = "mm", alpha: float = 1.0,
          size: int = 23, solid: bool = False):
    if alpha <= 0.01:
        return
    size = max(14, size - 2 * min(VARIANT, 3))
    f = sans("Bold", size)
    tw = d.textlength(text, font=f)
    w, h = tw + 34, size + 22
    if anchor[0] == "l":
        x0 = x
    elif anchor[0] == "r":
        x0 = x - w
    else:
        x0 = x - w / 2
    right = 915 if y > 990 else CARD_BOX[2] - 24          # dưới y≈1000 chừa cột nút Like/Comment/Share
    x0 = max(CARD_BOX[0] + 24, min(right - w, x0))
    y0 = y - h / 2
    a = int(255 * alpha)
    if solid:
        d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=9, fill=col + (a,))
        d.text((x0 + w / 2, y0 + h / 2), text, font=f, fill=(255, 255, 255, a), anchor="mm")
    else:
        d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=9, fill=CARD + (int(235 * alpha),),
                            outline=col + (a,), width=2)
        d.text((x0 + w / 2, y0 + h / 2), text, font=f, fill=col + (a,), anchor="mm")


def _dashed_h(d, x0, x1, y, col, a, dash=12, gap=8, width=2):
    x = x0
    while x < x1:
        d.line([(x, y), (min(x + dash, x1), y)], fill=col + (a,), width=width)
        x += dash + gap


def _dashed_v(d, x, y0, y1, col, a, dash=12, gap=8, width=2):
    y = y0
    while y < y1:
        d.line([(x, y), (x, min(y + dash, y1))], fill=col + (a,), width=width)
        y += dash + gap


def _dashed_rect(d, box, col, a):
    x0, y0, x1, y1 = box
    _dashed_h(d, x0, x1, y0, col, a)
    _dashed_h(d, x0, x1, y1, col, a)
    _dashed_v(d, x0, y0, y1, col, a)
    _dashed_v(d, x1, y0, y1, col, a)


class View:
    def __init__(self, v: tuple):
        self.i0, self.i1, self.lo, self.hi = v
        self.slot = (PLOT[2] - PLOT[0]) / max(1.0, self.i1 - self.i0 + 1)

    def x(self, i: float) -> float:
        return PLOT[0] + (i - self.i0 + 0.5) * self.slot

    def y(self, p: float) -> float:
        return PLOT[1] + (self.hi - p) / max(1e-6, self.hi - self.lo) * (PLOT[3] - PLOT[1])


def lerp_view(a: tuple, b: tuple, k: float) -> tuple:
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(4))


def _nice_step(span: float) -> float:
    raw = span / 6
    p = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * p:
            return m * p
    return 10 * p


def draw_grid(d: ImageDraw.ImageDraw, v: View):
    step = _nice_step(v.hi - v.lo)
    p = math.ceil(v.lo / step) * step
    f = sans("Medium", 22)
    while p <= v.hi:
        y = v.y(p)
        if PLOT[1] + 6 < y < PLOT[3] - 6:
            d.line([(PLOT[0], y), (PLOT[2], y)], fill=GRID + (255,), width=1)
            d.text((AXIS_X, y), f"{p:g}", font=f, fill=AXIS + (255,), anchor="lm")
        p += step


def draw_candles(d: ImageDraw.ImageDraw, ch: Chart, v: View, shown: float, alpha: float = 1.0):
    """shown = số nến đã hiện (phần lẻ = nến cuối đang mọc)."""
    n = int(shown)
    frac = shown - n
    bw = max(3.0, v.slot * 0.62)
    vmax = max(b.v for b in ch.bars) or 1
    a = int(255 * alpha)
    for i in range(max(0, int(v.i0) - 1), min(len(ch.bars), n + (1 if frac > 0 else 0))):
        b = ch.bars[i]
        k = 1.0 if i < n else ease(frac)
        c = b.o + (b.c - b.o) * k
        hi = max(b.o, c) + (b.h - max(b.o, b.c)) * k
        lo = min(b.o, c) - (min(b.o, b.c) - b.l) * k
        col = UP if b.c >= b.o else DN
        x = v.x(i)
        if x < PLOT[0] - bw or x > PLOT[2] + bw:
            continue
        d.line([(x, v.y(hi)), (x, v.y(lo))], fill=col + (a,), width=2)
        y0, y1 = sorted((v.y(b.o), v.y(c)))
        d.rectangle([x - bw / 2, y0, x + bw / 2, max(y1, y0 + 2)], fill=col + (a,))
        vh = (VOL[3] - VOL[1]) * b.v / vmax * k
        d.rectangle([x - bw / 2, VOL[3] - vh, x + bw / 2, VOL[3]], fill=col + (int(a * 0.55),))


# ------------------------------------------------------------------ khung chú thích
def mark_geom(ch: Chart, m: dict):
    """Trả thông tin hình học (theo chỉ số nến + giá) của 1 chú thích, None nếu không hợp lệ."""
    t = m.get("type")
    s = ch.seg(m.get("seg", ""))
    if t in ("box", "band") and s:
        return {"i0": s.i0, "i1": s.i1, "lo": s.lo, "hi": s.hi}
    if t == "level" and s:
        at = m.get("at", "low")
        return {"i0": s.lo_i if at == "low" else s.hi_i, "p": s.lo if at == "low" else s.hi}
    if t == "fvg":
        f = ch.fvg(m.get("seg", ""))
        if f:
            return {"i0": f[0] - 1, "lo": f[1], "hi": f[2]}
    if t == "ob":
        ob = ch.order_block(m.get("seg", ""))
        if ob:
            return {"i0": ob[0], "lo": ob[1], "hi": ob[2]}
    if t in ("x", "dot", "arrow") and s:
        at = m.get("at", "low")
        return {"i0": s.lo_i if at == "low" else s.hi_i, "p": s.lo if at == "low" else s.hi, "at": at}
    return None


def mark_needs(ch: Chart, m: dict) -> int:
    """Chỉ số nến phải hiện xong trước khi vẽ chú thích này."""
    s = ch.seg(m.get("seg", ""))
    if m.get("type") == "ob" and s:
        return s.i0 + 1
    if s:
        return s.i1
    return 0


def _cx(x: float) -> float:
    return max(PLOT[0], min(PLOT[2], x))


def draw_marks(d: ImageDraw.ImageDraw, ch: Chart, v: View, marks: list[Mark], t: float, alpha: float = 1.0,
               layer: str = "back"):
    bands = 0
    for mk in marks:
        m = mk.spec
        g = mark_geom(ch, m)
        if not g:
            continue
        k = prog(t, mk.at, 0.45) * alpha
        if k <= 0:
            continue
        col = COLORS.get(m.get("color", ""), None) or {"band": COLORS["b"], "box": COLORS["b"], "level": COLORS["y"],
                                                        "fvg": COLORS["o"], "ob": COLORS["o"], "x": COLORS["r"],
                                                        "dot": COLORS["r"], "arrow": COLORS["y"]}[m["type"]]
        label = (m.get("label") or "").upper()
        typ = m["type"]
        if typ == "band":
            x0, x1 = _cx(v.x(g["i0"]) - v.slot / 2), _cx(v.x(g["i1"]) + v.slot / 2)
            if x1 - x0 < 4:
                continue
            if layer == "back":
                d.rectangle([x0, PLOT[1], x0 + (x1 - x0) * k, PLOT[3]], fill=col + (int(30 * k),))
                _dashed_v(d, x0, PLOT[1], PLOT[3], col, int(90 * k))
            else:
                _pill(d, (x0 + x1) / 2, PLOT[1] + 28 + 46 * bands, label, col, alpha=k, size=20)
            bands += 1
        elif typ in ("box", "fvg", "ob"):
            if typ == "box":
                x0, x1 = v.x(g["i0"]) - v.slot / 2, v.x(g["i1"]) + v.slot / 2
            else:
                x0 = v.x(g["i0"]) - v.slot / 2
                x1 = x0 + v.slot * float(m.get("extend", 7))
            x0, x1 = _cx(x0), _cx(x1)
            if x1 - x0 < 4:
                continue
            y0, y1 = v.y(g["hi"]) - 4, v.y(g["lo"]) + 4
            xe = x0 + (x1 - x0) * k
            if layer == "back":
                d.rectangle([x0, y0, xe, y1], fill=col + (int(40 * k),))
                _dashed_rect(d, (x0, y0, xe, y1), col, int(220 * k))
            elif label:
                if typ == "box":
                    below = (m.get("label_pos") == "below") != (VARIANT % 2 == 1)
                    _pill(d, (x0 + x1) / 2, (y1 + 34) if below else (y0 - 34), label, col, alpha=k)
                else:
                    if VARIANT % 2 == 1:                     # bố cục lẻ: nhãn FVG/OB đặt phía trên vùng
                        _pill(d, (x0 + x1) / 2, y0 - 30, label, col, alpha=k)
                    else:
                        _pill(d, x1 + 10, (y0 + y1) / 2, label, col, anchor="lm", alpha=k)
        elif typ == "level":
            y = v.y(g["p"])
            x0 = _cx(v.x(g["i0"]) - v.slot / 2)
            xe = x0 + (PLOT[2] - x0) * k
            if layer == "back":
                _dashed_h(d, x0, xe, y, col, int(255 * k), width=3)
            elif label:
                _pill(d, PLOT[2] - 6, y + (30 if m.get("at", "low") == "low" else -30), label, col, anchor="rm",
                      alpha=k, size=20)
        elif typ in ("x", "dot", "arrow") and layer == "front":
            x, y = v.x(g["i0"]), v.y(g["p"])
            low = g["at"] == "low"
            if typ == "x":
                r = 16 * (0.6 + 0.4 * k)
                yy = y + (26 if low else -26)
                d.line([(x - r, yy - r), (x + r, yy + r)], fill=col + (int(255 * k),), width=5)
                d.line([(x - r, yy + r), (x + r, yy - r)], fill=col + (int(255 * k),), width=5)
                if label:
                    _pill(d, x, yy + (52 if low else -52), label, col, alpha=k, size=20)
            elif typ == "dot":
                r = 11 * (0.5 + 0.5 * k)
                d.ellipse([x - r, y - r, x + r, y + r], fill=col + (int(255 * k),))
                d.ellipse([x - r * 2.2, y - r * 2.2, x + r * 2.2, y + r * 2.2], outline=col + (int(120 * k),), width=2)
                if label:
                    _pill(d, x, y + (48 if low else -48), label, col, alpha=k, size=20)
            else:
                sign = 1 if low else -1                # mũi tên chỉ vào râu nến
                tip = y + sign * 12
                tail = tip + sign * 90 * k
                d.line([(x, tail), (x, tip + sign * 14)], fill=col + (int(255 * k),), width=4)
                d.polygon([(x, tip), (x - 13, tip + sign * 20), (x + 13, tip + sign * 20)], fill=col + (int(255 * k),))
                if label:
                    _pill(d, x, tail + sign * 30, label, col, alpha=k, size=20)


# ------------------------------------------------------------------ thẻ phủ (tiêu đề / danh sách / kết)
def draw_card(img: Image.Image, card: dict, t: float, t0: float):
    """t, t0 tính theo giây toàn video (t0 = lúc cảnh bắt đầu)."""
    k = prog(t, t0, 0.4)
    if k <= 0:
        return
    d = ImageDraw.Draw(img, "RGBA")
    # làm tối biểu đồ phía sau
    d.rectangle([PLOT[0] - 10, PLOT[1] - 20, AXIS_X + 72, VOL[3] + 10], fill=CARD + (int(200 * k),))
    kind = card.get("kind")
    cx, cy = (PLOT[0] + AXIS_X + 60) / 2, (PLOT[1] + VOL[3]) / 2
    rise = (1 - k) * 40
    if kind == "title":
        f1, f2 = sans("Bold", 34), sans("ExtraBold", 112)
        lines = [ln for ln in str(card.get("title", "")).split("\n") if ln][:3]
        h = 60 + len(lines) * 124 + (70 if card.get("sub") else 0)
        y = cy - h / 2 + rise
        d.text((cx, y), str(card.get("kicker", "")).upper(), font=f1, fill=COLORS["y"] + (int(255 * k),), anchor="mt")
        y += 66
        for ln in lines:
            d.text((cx, y), ln.upper(), font=f2, fill=TEXT + (int(255 * k),), anchor="mt")
            y += 124
        if card.get("sub"):
            kk = prog(t, t0 + 0.5, 0.4)
            d.line([(cx - 60, y + 6), (cx + 60, y + 6)], fill=BRAND + (int(255 * kk),), width=4)
            d.text((cx, y + 28), card["sub"], font=sans("Bold", 36), fill=COLORS["y"] + (int(255 * kk),), anchor="mt")
    elif kind in ("list", "check"):
        items = card.get("items", [])[:5]
        title = card.get("title", "")
        f, fs = sans("Bold", 40), sans("Medium", 26)
        row = 132
        h = len(items) * row + (90 if title else 0)
        y = cy - h / 2 + rise
        if title:
            d.text((cx, y), title.upper(), font=sans("ExtraBold", 40), fill=COLORS["y"] + (int(255 * k),), anchor="mt")
            y += 90
        step = max(0.35, (card.get("_dur", 4) * 0.7) / max(1, len(items)))
        for n, it in enumerate(items):
            ki = prog(t, t0 + 0.3 + n * step, 0.35)
            if ki <= 0:
                continue
            a = int(255 * ki)
            x0, x1 = PLOT[0] + 20, AXIS_X + 40
            on = kind == "check" and t >= t0 + 0.3 + n * step + 0.5
            d.rounded_rectangle([x0, y, x1, y + row - 22], radius=16,
                                fill=(mix(CARD, UP, 0.16) if on else (22, 28, 40)) + (a,),
                                outline=(UP if on else CARD_LINE) + (a,), width=2)
            d.rounded_rectangle([x0 + 22, y + 28, x0 + 78, y + 84], radius=10, fill=(40, 48, 64, a))
            d.text((x0 + 50, y + 56), str(n + 1), font=sans("ExtraBold", 30), fill=TEXT + (a,), anchor="mm")
            name, _, sub = str(it).partition("|")
            d.text((x0 + 100, y + (38 if sub else 55)), name.strip().upper() if kind == "check" else name.strip(),
                   font=f, fill=TEXT + (a,), anchor="lm")
            if sub:
                d.text((x0 + 100, y + 80), sub.strip(), font=fs, fill=MUTED + (a,), anchor="lm")
            if on:
                ox, oy = x1 - 52, y + 55
                d.ellipse([ox - 22, oy - 22, ox + 22, oy + 22], fill=UP + (a,))
                d.line([(ox - 10, oy), (ox - 3, oy + 8), (ox + 11, oy - 9)], fill=(10, 30, 24, a), width=5)
            y += row
    elif kind == "cta":
        lg = _logo(190, "icon.png")
        lg.putalpha(lg.getchannel("A").point(lambda v: int(v * k)))
        y = cy - 330 + rise
        img.paste(lg, (int(cx - lg.width / 2), int(y)), lg)
        d = ImageDraw.Draw(img, "RGBA")
        y += lg.height + 46
        d.text((cx, y), "CWG MARKETS & PARTNER", font=sans("ExtraBold", 58), fill=TEXT + (int(255 * k),), anchor="mt")
        y += 84
        d.text((cx, y), card.get("line", "Kiến thức giao dịch mỗi ngày"), font=sans("Medium", 34),
               fill=MUTED + (int(255 * k),), anchor="mt")
        kb = prog(t, t0 + 0.6, 0.45)
        y += 100
        bt = card.get("button", "THEO DÕI PAGE")
        f = sans("ExtraBold", 40)
        bw = d.textlength(bt, font=f) + 110
        s = 0.85 + 0.15 * kb
        d.rounded_rectangle([cx - bw / 2 * s, y, cx + bw / 2 * s, y + 96 * s], radius=48 * s,
                            fill=BRAND + (int(255 * kb),))
        d.text((cx, y + 48 * s), bt, font=f, fill=(255, 255, 255, int(255 * kb)), anchor="mm")
        y += 140
        d.text((cx, y), "facebook.com/CWG.Partner", font=sans("Bold", 30), fill=COLORS["y"] + (int(255 * kb),),
               anchor="mt")


# ------------------------------------------------------------------ đầu thẻ: nhãn chương + tiến trình + câu thoại
def draw_head(d: ImageDraw.ImageDraw, sc: Scene, t: float, total: float, prev: Scene | None):
    # nhãn chương (đổi nhãn → hiệu ứng trượt nhẹ)
    tag = (sc.tag or "").upper()
    k = 1.0 if prev and prev.tag == sc.tag else prog(t, sc.start, 0.35)
    f = sans("Bold", 24)
    tw = d.textlength(tag, font=f)
    x0, y0 = 84, 200
    if tag:
        d.rounded_rectangle([x0, y0, x0 + (tw + 36) * (0.4 + 0.6 * k), y0 + 46], radius=10,
                            fill=BRAND + (int(255 * k),))
        d.text((x0 + 18, y0 + 23), tag, font=f, fill=(255, 255, 255, int(255 * k)), anchor="lm")
    lx0 = x0 + tw + 56
    lx1 = 880
    d.line([(lx0, y0 + 23), (lx1, y0 + 23)], fill=(46, 53, 70, 255), width=3)
    d.line([(lx0, y0 + 23), (lx0 + (lx1 - lx0) * min(1, t / total), y0 + 23)], fill=COLORS["y"] + (255,), width=3)
    # câu thoại: từ hiện dần theo nhịp đọc
    f = sans("Bold", HEAD_FONT)
    base = sc.start + sc.voice_at
    for (x, line, w, col), wt in zip(sc.lay, sc.times):
        kw = prog(t, base + wt, 0.18)
        if kw <= 0:
            continue
        y = HEAD_Y + line * HEAD_LH + (1 - kw) * 14
        c = col if col != TEXT else mix(MUTED, TEXT, kw)
        d.text((84 + x, y), w, font=f, fill=c + (int(255 * kw),))
