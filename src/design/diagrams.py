"""Bộ vẽ hình minh họa cho bài Kiến thức. AI mô tả hình bằng JSON (DIAGRAM_SPEC), code vẽ theo phong cách Block.

Các loại hình:
- chart:     biểu đồ nến minh họa sinh từ "path" (các điểm đỉnh/đáy) + vùng, đường, nhãn, mũi tên, Fibonacci,
             Pivot, EMA/SMA, RSI, volume, Ichimoku
- pattern:   vài cây nến cận cảnh từ "candles" [[o,h,l,c],...]
- compare:   so sánh 2 cột
- formula:   bảng tính: các dòng nhãn → giá trị + kết quả
- checklist: danh sách quy tắc
"""
import hashlib
import math
import random

from PIL import Image, ImageDraw

from src.design.common import fit, sans, wrap
from src.design.styles.block import CREAM, DIVIDER, DOWN, GREEN, INK, LIME, MUTED, UP

GOLD = (201, 150, 40)
CARD = (236, 231, 219)
PALETTE = {"red": DOWN, "green": UP, "ink": INK, "gold": GOLD, "gray": MUTED, "lime": (150, 180, 40)}

DIAGRAM_SPEC = """Trường "diagram" là JSON mô tả hình minh họa, chọn 1 trong 5 loại:

1) {"type":"chart", "path":[...], ...} - biểu đồ nến minh họa (giá giả định quanh 100).
   path: 4-9 điểm đỉnh/đáy liên tiếp mà giá đi qua, ví dụ [100,106,103,110,107,115] = xu hướng tăng.
   bars_per_leg: số nến mỗi nhịp (3-8, mặc định 5).
   Chỉ số i trong các mục dưới = chỉ số điểm trong path (0 = điểm đầu). i lớn hơn điểm cuối = tương lai (dùng cho mũi tên).
   points:  [{"at":i, "label":"HH"}]  nhãn tại đỉnh/đáy (≤ 8 ký tự)
   hlines:  [{"price":p, "label":"Kháng cự", "color":"red|green|ink|gold", "style":"solid|dashed"}]
   zones:   [{"from":p1, "to":p2, "label":"Order Block", "color":"red|green|gold|gray", "start":i}]  vùng giá tô màu
   lines:   [{"from":[i,p], "to":[j,p], "label":"Trendline", "color":"..."}]  đường xiên (trendline, kênh giá)
   arrows:  [{"from":[i,p], "to":[j,p], "color":"green|red"}]  kịch bản giá
   fib:     {"from":i, "to":j, "levels":[0.382,0.5,0.618]}  Fibonacci thoái lui giữa 2 điểm
   pivot:   {"high":p, "low":p, "close":p}  vẽ P, R1, R2, S1, S2 (classic)
   indicators: chọn trong ["ema20","ema50","sma200","rsi","volume","ichimoku"]
   volume:  [hệ số cho từng nhịp, ví dụ 1,1,3,1] khi cần nhấn mạnh volume lớn/nhỏ ở nhịp nào
2) {"type":"pattern", "candles":[[o,h,l,c],...], "points":[{"at":chỉ số nến,"label":"..."}], "hlines":[...], "zones":[...], "arrows":[...]}
   3-12 cây nến cận cảnh, đúng h ≥ max(o,c), l ≤ min(o,c). Dùng cho mô hình nến.
3) {"type":"compare", "left":{"title":"...","tone":"good|bad|neutral","items":["..."]}, "right":{...}}  2-4 ý mỗi cột, ≤ 45 ký tự/ý
4) {"type":"formula", "rows":[{"label":"Vốn","value":"$1,000"}], "result":{"label":"Khối lượng","value":"0.05 lot"}, "note":"..."}  2-6 dòng
5) {"type":"checklist", "items":["..."]}  3-6 quy tắc, ≤ 60 ký tự/ý
Chỉ dùng số giả định, không dùng giá thị trường thật."""


# ===================================================================== Dữ liệu nến

def synth_candles(path: list[float], bars_per_leg: int) -> list[list[float]]:
    """Sinh nến đi qua đúng các điểm đỉnh/đáy trong path (ngẫu nhiên nhưng cố định theo path)."""
    rng = random.Random(int(hashlib.md5(str(path).encode()).hexdigest()[:8], 16))
    legs = list(zip(path, path[1:]))
    avg_leg = sum(abs(b - a) for a, b in legs) / len(legs)
    candles, prev = [], path[0]
    for k, (a, b) in enumerate(legs):
        for s in range(1, bars_per_leg + 1):
            t = s / bars_per_leg
            target = a + (b - a) * t
            jitter = 0 if s == bars_per_leg else (rng.random() - 0.5) * avg_leg * 0.25
            top, bottom = max(a, b), min(a, b)
            close = min(top, max(bottom, target + jitter))
            o = prev
            wick = avg_leg * (0.05 + rng.random() * 0.08)
            # Râu nến không vượt đỉnh/đáy của nhịp để điểm path luôn là đỉnh/đáy thật
            h = min(top, max(o, close) + wick * rng.random()) if s < bars_per_leg else max(o, close)
            l = max(bottom, min(o, close) - wick * rng.random()) if s < bars_per_leg else min(o, close)
            h, l = max(h, o, close), min(l, o, close)
            candles.append([o, h, l, close])
            prev = close
        # Điểm cuối nhịp chạm đúng giá đỉnh/đáy
        last = candles[-1]
        if b >= a:
            last[1] = b
        else:
            last[2] = b
        last[1], last[2] = max(last[1], last[0], last[3]), min(last[2], last[0], last[3])
    return candles


def ma(values: list[float], period: int, kind: str = "ema") -> list[float]:
    out, e = [], values[0]
    for i, v in enumerate(values):
        if kind == "ema":
            k = 2 / (period + 1)
            e = v * k + e * (1 - k) if i else v
            out.append(e)
        else:
            window = values[max(0, i - period + 1):i + 1]
            out.append(sum(window) / len(window))
    return out


def rsi_series(closes: list[float], period: int = 14) -> list[float]:
    out, ag, al = [50.0], 0.0, 0.0
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        g, l = max(ch, 0), max(-ch, 0)
        n = min(i, period)
        ag, al = ag + (g - ag) / n, al + (l - al) / n
        out.append(100 - 100 / (1 + ag / al) if al else 100.0)
    return out


# ===================================================================== Vẽ chung

def color(name: str | None, default=INK):
    return PALETTE.get(name or "", default)


def dashed(d, x0, x1, y, col, dash=12, gap=8, width=2):
    x = x0
    while x < x1:
        d.line([(x, y), (min(x + dash, x1), y)], fill=col, width=width)
        x += dash + gap


def arrow(d, p0, p1, col, width=5):
    d.line([p0, p1], fill=col, width=width)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    s = 18
    d.polygon([p1, (p1[0] - s * math.cos(ang - 0.45), p1[1] - s * math.sin(ang - 0.45)),
               (p1[0] - s * math.cos(ang + 0.45), p1[1] - s * math.sin(ang + 0.45))], fill=col)


def icon(d, cx, cy, kind: str, col, size: int = 12, width: int = 5):
    if kind == "good":
        d.line([(cx - size, cy), (cx - size / 3, cy + size * 0.7), (cx + size, cy - size * 0.7)], fill=col, width=width)
    elif kind == "bad":
        d.line([(cx - size * 0.7, cy - size * 0.7), (cx + size * 0.7, cy + size * 0.7)], fill=col, width=width)
        d.line([(cx - size * 0.7, cy + size * 0.7), (cx + size * 0.7, cy - size * 0.7)], fill=col, width=width)
    else:
        d.ellipse([cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2], fill=col)


def tag(d, x, y, text, bg, fg=CREAM, size=18, anchor="lm"):
    f = sans("Bold", size)
    w = d.textlength(text, font=f) + 20
    x0 = x if anchor == "lm" else x - w / 2 if anchor == "mm" else x - w
    d.rounded_rectangle([x0, y - size * 0.85, x0 + w, y + size * 0.85], radius=8, fill=bg)
    d.text((x0 + 10, y), text, font=f, fill=fg, anchor="lm")


# ===================================================================== chart / pattern

def draw_chart(img: Image.Image, spec: dict, box: tuple):
    x0, y0, x1, y1 = box
    is_pattern = spec.get("type") == "pattern"
    if is_pattern:
        candles = [list(map(float, c)) for c in spec["candles"]]
        bars = 1
        anchors = list(range(len(candles)))
    else:
        path = [float(p) for p in spec["path"]]
        bars = int(min(8, max(3, spec.get("bars_per_leg", 5))))
        candles = synth_candles(path, bars)
        candles.insert(0, [path[0], path[0] + 0.1, path[0] - 0.1, path[0]])
        anchors = [k * bars for k in range(len(path))]          # chỉ số nến tại mỗi điểm path

    inds = [i.lower() for i in spec.get("indicators") or []]
    closes = [c[3] for c in candles]
    n = len(candles)

    # Chừa chỗ cho tương lai (mũi tên) và nhãn bên phải
    max_idx = max([a["to"][0] for a in spec.get("arrows") or []] + [len(anchors) - 1])
    future_slots = (max_idx - (len(anchors) - 1)) * (1 if is_pattern else bars)
    has_labels = any(spec.get(k) for k in ("hlines", "zones", "fib", "pivot"))
    label_w = 170 if has_labels else 0

    sub_h = (y1 - y0) * 0.26 if ("rsi" in inds or "volume" in inds) else 0
    main_y1 = y1 - sub_h - (14 if sub_h else 0)
    plot_x1 = x1 - label_w
    step = (plot_x1 - x0) / (n + future_slots + 0.5)
    cx = lambda i: x0 + step * (i + 0.5)

    def idx_x(i):
        if i < len(anchors):
            return cx(anchors[i])
        return cx(anchors[-1] + (i - len(anchors) + 1) * (1 if is_pattern else bars))

    # --- Các mức giá cần nằm trong khung
    prices = [c[1] for c in candles] + [c[2] for c in candles]
    prices += [h["price"] for h in spec.get("hlines") or []]
    for z in spec.get("zones") or []:
        prices += [z["from"], z["to"]]
    for ln in (spec.get("lines") or []) + (spec.get("arrows") or []):
        prices += [ln["from"][1], ln["to"][1]]
    pivot_lines = []
    if spec.get("pivot"):
        pv = spec["pivot"]
        p = (pv["high"] + pv["low"] + pv["close"]) / 3
        rng_ = pv["high"] - pv["low"]
        pivot_lines = [("R2", p + rng_, DOWN), ("R1", 2 * p - pv["low"], DOWN), ("P", p, INK),
                       ("S1", 2 * p - pv["high"], UP), ("S2", p - rng_, UP)]
        prices += [v for _, v, _ in pivot_lines]
    fib_lines = []
    if spec.get("fib") and not is_pattern:
        f = spec["fib"]
        a, b = path[f["from"]], path[f["to"]]
        for lv in [0.0] + list(f.get("levels") or [0.382, 0.5, 0.618]) + [1.0]:
            fib_lines.append((f"{lv * 100:g}%", b - (b - a) * lv))
    lo, hi = min(prices), max(prices)
    pad = (hi - lo) * 0.08 or 1
    lo, hi = lo - pad, hi + pad
    py = lambda v: main_y1 - (v - lo) / (hi - lo) * (main_y1 - y0 - 30) - 0

    d = ImageDraw.Draw(img)
    for g in range(5):
        gy = y0 + 30 + g * (main_y1 - y0 - 30) / 4
        d.line([(x0, gy), (plot_x1, gy)], fill=DIVIDER, width=1)

    # --- Vùng giá
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    zone_labels = []
    for z in spec.get("zones") or []:
        col = color(z.get("color"), GOLD)
        zx = idx_x(z["start"]) if z.get("start") is not None else x0
        ya, yb = sorted([py(z["from"]), py(z["to"])])
        ld.rectangle([zx, ya, plot_x1, yb], fill=col + (60,), outline=col + (160,), width=2)
        zone_labels.append(((ya + yb) / 2, z.get("label", ""), col))
    img.alpha_composite(layer)
    d = ImageDraw.Draw(img)

    # --- Fibonacci / Pivot / đường ngang
    right_labels = []
    if fib_lines:
        fx = idx_x(spec["fib"]["from"])
        for name, v in fib_lines:
            d.line([(fx, py(v)), (plot_x1, py(v))], fill=GOLD, width=2)
            right_labels.append((py(v), name, GOLD))
    for name, v, col in pivot_lines:
        dashed(d, x0, plot_x1, py(v), col)
        right_labels.append((py(v), name, col))
    for h in spec.get("hlines") or []:
        col = color(h.get("color"))
        if h.get("style") == "solid":
            d.line([(x0, py(h["price"])), (plot_x1, py(h["price"]))], fill=col, width=3)
        else:
            dashed(d, x0, plot_x1, py(h["price"]), col)
        right_labels.append((py(h["price"]), h.get("label", ""), col))
    right_labels += zone_labels

    # --- Ichimoku (chu kỳ thu nhỏ theo số nến để vẫn thấy mây)
    if "ichimoku" in inds:
        sc = max(0.25, min(1.0, n / 110))
        t_p, k_p, b_p = max(3, round(9 * sc)), max(5, round(26 * sc)), max(8, round(52 * sc))
        mid = lambda i, p: (max(c[1] for c in candles[max(0, i - p + 1):i + 1]) +
                            min(c[2] for c in candles[max(0, i - p + 1):i + 1])) / 2
        tenkan = [mid(i, t_p) for i in range(n)]
        kijun = [mid(i, k_p) for i in range(n)]
        span_a = [(t + k) / 2 for t, k in zip(tenkan, kijun)]
        span_b = [mid(i, b_p) for i in range(n)]
        cl = Image.new("RGBA", img.size, (0, 0, 0, 0))
        cd = ImageDraw.Draw(cl)
        for i in range(n - 1):
            xa, xb = cx(min(i + k_p, n + future_slots)), cx(min(i + 1 + k_p, n + future_slots))
            if xb > plot_x1:
                break
            up = span_a[i] >= span_b[i]
            cd.polygon([(xa, py(span_a[i])), (xb, py(span_a[i + 1])), (xb, py(span_b[i + 1])), (xa, py(span_b[i]))],
                       fill=(UP if up else DOWN) + (55,))
        img.alpha_composite(cl)
        d = ImageDraw.Draw(img)
        d.line([(cx(i), py(v)) for i, v in enumerate(tenkan)], fill=(40, 90, 200), width=2)
        d.line([(cx(i), py(v)) for i, v in enumerate(kijun)], fill=(150, 40, 60), width=2)

    # --- Nến
    body = max(5, step * 0.62)
    for i, (o, h, l, c) in enumerate(candles):
        col = UP if c >= o else DOWN
        d.line([(cx(i), py(h)), (cx(i), py(l))], fill=col, width=2 if not is_pattern else 4)
        top, bot = py(max(o, c)), py(min(o, c))
        d.rectangle([cx(i) - body / 2, top, cx(i) + body / 2, max(bot, top + 2)], fill=col)

    # --- Đường trung bình
    for key, col in (("ema20", (40, 90, 200)), ("ema50", GOLD), ("sma200", INK)):
        if key in inds:
            period = int(key[3:])
            vals = ma(closes, max(2, min(period, n // 2)), key[:3])
            d.line([(cx(i), py(v)) for i, v in enumerate(vals)], fill=col, width=3)
            d.text((cx(n - 1) + 8, py(vals[-1])), key.upper(), font=sans("Bold", 16), fill=col, anchor="lm")

    # --- Đường xiên, mũi tên, nhãn điểm
    for ln in spec.get("lines") or []:
        col = color(ln.get("color"))
        p0, p1 = (idx_x(ln["from"][0]), py(ln["from"][1])), (idx_x(ln["to"][0]), py(ln["to"][1]))
        d.line([p0, p1], fill=col, width=3)
        if ln.get("label"):
            tag(d, (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 - 22, ln["label"], col, size=16, anchor="mm")
    for ar in spec.get("arrows") or []:
        arrow(d, (idx_x(ar["from"][0]), py(ar["from"][1])), (idx_x(ar["to"][0]), py(ar["to"][1])),
              color(ar.get("color"), INK))
    for pt in spec.get("points") or []:
        i = pt["at"]
        if is_pattern:
            if not 0 <= i < n:
                continue
            ci, c = i, candles[i]
            above = c[3] >= c[0] if pt.get("pos") is None else pt["pos"] == "above"
            yv = c[1] if above else c[2]
        else:
            if not 0 <= i < len(path):
                continue
            ci = anchors[i]
            prev_v = path[i - 1] if i else path[i + 1] if len(path) > 1 else path[i]
            above = path[i] >= prev_v if pt.get("pos") is None else pt["pos"] == "above"
            yv = candles[ci][1] if above else candles[ci][2]
        y = py(yv) + (-26 if above else 26)
        tag(d, cx(ci), y, pt["label"][:10], INK, size=17, anchor="mm")

    # --- Nhãn bên phải (dàn đều để không chồng nhau)
    if right_labels and label_w:
        right_labels.sort(key=lambda r: r[0])
        ys, last = [], -1e9
        for y, _, _ in right_labels:
            y = max(y, last + 34)
            ys.append(y)
            last = y
        shift = max(0, ys[-1] - (main_y1 - 10))
        for (_, text, col), y in zip(right_labels, ys):
            tag(d, plot_x1 + 12, y - shift, fit(d, text, sans("Bold", 17), label_w - 36), col, size=17)

    # --- Panel phụ: RSI hoặc volume
    if sub_h:
        sy0, sy1 = y1 - sub_h, y1
        d.rectangle([x0, sy0, plot_x1, sy1], outline=DIVIDER, width=2)
        if "rsi" in inds:
            r = rsi_series(closes)
            ry = lambda v: sy1 - v / 100 * (sy1 - sy0)
            for lvl in (70, 30):
                dashed(d, x0, plot_x1, ry(lvl), MUTED, dash=8, gap=6)
                d.text((plot_x1 + 10, ry(lvl)), str(lvl), font=sans("Medium", 16), fill=MUTED, anchor="lm")
            d.line([(cx(i), ry(v)) for i, v in enumerate(r)], fill=(120, 60, 160), width=3)
            d.text((x0 + 8, sy0 + 6), "RSI 14", font=sans("Bold", 16), fill=(120, 60, 160))
        else:
            mult = spec.get("volume") or []
            vols = []
            for i, (o, h, l, c) in enumerate(candles):
                leg = min(len(mult) - 1, max(0, (i - 1) // bars)) if mult else 0
                vols.append((h - l) * (mult[leg] if mult else 1))
            vmax = max(vols) or 1
            for i, v in enumerate(vols):
                col = UP if candles[i][3] >= candles[i][0] else DOWN
                d.rectangle([cx(i) - body / 2, sy1 - v / vmax * (sub_h - 8), cx(i) + body / 2, sy1], fill=col)
            d.text((x0 + 8, sy0 + 6), "Volume", font=sans("Bold", 16), fill=MUTED)


# ===================================================================== compare / formula / checklist

def draw_compare(img, spec: dict, box: tuple):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    gap = 24
    w = (x1 - x0 - gap) / 2
    tone_col = {"good": UP, "bad": DOWN, "neutral": GREEN}
    for k, side in enumerate((spec["left"], spec["right"])):
        cx0 = x0 + k * (w + gap)
        col = tone_col.get(side.get("tone"), GREEN)
        d.rectangle([cx0, y0, cx0 + w, y1], fill=CARD)
        d.rectangle([cx0, y0, cx0 + w, y0 + 8], fill=col)
        d.ellipse([cx0 + 24, y0 + 34, cx0 + 64, y0 + 74], fill=col)
        icon(d, cx0 + 44, y0 + 54, side.get("tone", "neutral"), CREAM, size=10, width=4)
        d.text((cx0 + 80, y0 + 54), fit(d, side["title"], sans("ExtraBold", 28), w - 100),
               font=sans("ExtraBold", 28), fill=INK, anchor="lm")
        y = y0 + 110
        for item in side.get("items", [])[:4]:
            lines = wrap(d, item, sans("SemiBold", 24), w - 70, max_lines=3)
            d.ellipse([cx0 + 28, y + 11, cx0 + 38, y + 21], fill=col)
            for ln in lines:
                d.text((cx0 + 52, y), ln, font=sans("SemiBold", 24), fill=INK)
                y += 34
            y += 22


def draw_formula(img, spec: dict, box: tuple):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=CARD)
    rows = spec.get("rows", [])[:6]
    y = y0 + 36
    row_h = min(78, (y1 - y0 - 200) / max(1, len(rows)))
    for r in rows:
        d.text((x0 + 36, y + row_h / 2), fit(d, r["label"], sans("Medium", 26), (x1 - x0) * 0.55),
               font=sans("Medium", 26), fill=MUTED, anchor="lm")
        d.text((x1 - 36, y + row_h / 2), str(r["value"]), font=sans("Bold", 30), fill=INK, anchor="rm")
        y += row_h
        d.line([(x0 + 36, y), (x1 - 36, y)], fill=DIVIDER, width=2)
    res = spec.get("result")
    if res:
        y += 24
        d.rectangle([x0 + 24, y, x1 - 24, y + 96], fill=GREEN)
        d.text((x0 + 52, y + 48), res["label"], font=sans("Bold", 28), fill=LIME, anchor="lm")
        d.text((x1 - 52, y + 48), str(res["value"]), font=sans("ExtraBold", 40), fill=CREAM, anchor="rm")
        y += 96
    if spec.get("note"):
        for ln in wrap(d, spec["note"], sans("Medium", 21), x1 - x0 - 72, max_lines=2):
            d.text((x0 + 36, y + 22), ln, font=sans("Medium", 21), fill=MUTED)
            y += 30


def draw_checklist(img, spec: dict, box: tuple):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    items = spec.get("items", [])[:6]
    row_h = min(124, (y1 - y0) / max(4, len(items)))
    for i, item in enumerate(items):
        y = y0 + i * row_h
        d.rounded_rectangle([x0, y + 10, x0 + 52, y + 62], radius=12, fill=GREEN)
        icon(d, x0 + 26, y + 36, "good", LIME, size=12, width=5)
        for j, ln in enumerate(wrap(d, item, sans("Bold", 28), x1 - x0 - 90, max_lines=2)):
            d.text((x0 + 80, y + 16 + j * 38), ln, font=sans("Bold", 28), fill=INK)
        if i < len(items) - 1:
            d.line([(x0 + 80, y + row_h - 6), (x1, y + row_h - 6)], fill=DIVIDER, width=2)


DRAWERS = {"chart": draw_chart, "pattern": draw_chart, "compare": draw_compare,
           "formula": draw_formula, "checklist": draw_checklist}


def draw(img: Image.Image, spec: dict, box: tuple) -> None:
    DRAWERS[spec["type"]](img, spec, box)


def is_valid(spec) -> bool:
    if not isinstance(spec, dict) or spec.get("type") not in DRAWERS:
        return False
    t = spec["type"]
    if t == "chart":
        return isinstance(spec.get("path"), list) and 3 <= len(spec["path"]) <= 12
    if t == "pattern":
        cs = spec.get("candles") or []
        return 2 <= len(cs) <= 16 and all(len(c) == 4 and c[1] >= max(c[0], c[3]) and c[2] <= min(c[0], c[3])
                                          for c in cs)
    if t == "compare":
        return bool(spec.get("left")) and bool(spec.get("right"))
    if t == "formula":
        return bool(spec.get("rows"))
    return bool(spec.get("items"))
