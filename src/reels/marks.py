"""Sơ đồ minh họa (nến TradingView dựng từ các đỉnh/đáy) + lớp đánh dấu chuyển động vẽ dần theo lời đọc.

Kiểu đánh dấu (AI chọn trong kịch bản, "at"/"start" = số thứ tự điểm trong path, "step" = ý thứ mấy):
  circle  {"type":"circle","at":k,"label":"Đỉnh trước","color":"red","step":1}       khoanh tròn đỉnh/đáy
  hline   {"type":"hline","price":p,"from":k,"label":"Entry","color":"blue","step":2}  đường giá vẽ dần
  move    {"type":"move","at":k,"from_price":p1,"to_price":p2,"label_from":"SL cũ","label_to":"SL mới","step":3}
  arrow   {"type":"arrow","from":[k,p],"to":[k2,p2],"label":"Phá đỉnh","color":"green","step":2}
  zone    {"type":"zone","from":p1,"to":p2,"start":k,"label":"Vùng vào lệnh","color":"gold","step":1}
"""
import math

from PIL import Image, ImageDraw

from src.design.common import sans

COLORS = {"red": (214, 48, 49), "green": (22, 150, 90), "gold": (226, 150, 20), "blue": (41, 98, 255),
          "gray": (120, 120, 120), "ink": (25, 25, 25)}
MARKS_SPEC = """Sơ đồ minh họa "diagram": {"path":[5-12 điểm đỉnh/đáy, giá quanh 100, xen kẽ lên xuống],"bars_per_leg":4-6,
  "indicators":[tùy chọn: ema9|ema20|ema50|sma20|bollinger|supertrend|rsi|macd - chỉ báo của hệ thống đang nói],
  "marks":[...]}  - marks là các hiệu ứng vẽ dần lên sơ đồ khi Thái nói tới (k = số thứ tự điểm trong path, bắt đầu 0;
  step = ý thứ mấy trong bullets, 1-3, mỗi step 1-2 mark):
  {"type":"circle","at":k,"label":"Đỉnh trước","color":"red|green|gold|blue","step":1}   khoanh tròn 1 đỉnh/đáy
  {"type":"hline","price":p,"from":k,"label":"Entry","color":"blue","step":2}           kẻ đường giá (Entry, SL, TP...)
  {"type":"move","at":k,"from_price":p1,"to_price":p2,"label_from":"SL cũ","label_to":"SL mới","step":3}
                                                                       đường SL/TP dịch chuyển từ p1 tới p2
  {"type":"arrow","from":[k,p],"to":[k2,p2],"label":"Phá đỉnh","color":"green","step":2}  mũi tên chỉ hướng
  {"type":"zone","from":p1,"to":p2,"start":k,"label":"Vùng vào lệnh","color":"gold","step":1}  tô vùng giá
  Nhãn tối đa 3 từ. Giá p phải nằm trong biên độ của path (hoặc sát ngoài 1-3 đơn vị cho SL/TP).
  Sơ đồ phải ĐÚNG kỹ thuật: ví dụ Buy thì SL dưới đáy, TP phía trên; dời SL thì SL mới nằm dưới đáy mới cao hơn."""


_PLACED: list = []          # nhãn đã đặt trong khung hình hiện tại (x, y, w, h)


def _font(size):
    return sans("Bold", size)


def _indicators(ch, inds: list[str]):
    """Vẽ thêm đường chỉ báo lên sơ đồ minh họa (tính trên chính các nến minh họa)."""
    from types import SimpleNamespace

    from src.chart_tools import bollinger, ema, macd, sma, supertrend
    from src.design.tvchart import TV

    c = [SimpleNamespace(**x) for x in ch.spec["candles"]]
    closes = [x.close for x in c]
    palette = [TV["blue"], TV["orange"], TV["purple"]]
    k = 0
    for name in inds:
        if name.startswith(("ema", "sma")) and name[3:].isdigit():
            fn = ema if name.startswith("ema") else sma
            ch.line(fn(closes, int(name[3:])), palette[k % 3], name.upper(), width=3)
            k += 1
        elif name == "bollinger":
            mid, up, lo = bollinger(closes)
            for v in (up, lo):
                ch.line(v, TV["blue"], "", width=2)
            ch.line(mid, TV["orange"], "", width=2, style=2)
        elif name == "supertrend":
            st = supertrend(c, 7, 2.0)
            # mỗi đoạn cùng chiều là 1 đường riêng → đứt nét khi đổi chiều như TradingView
            first = True
            i = 0
            while i < len(st):
                j = i
                while j + 1 < len(st) and st[j + 1][1] == st[i][1]:
                    j += 1
                seg = [v if i <= n <= j else None for n, (v, _) in enumerate(st)]
                ch.line(seg, TV["up"] if st[i][1] == 1 else TV["down"], "SuperTrend" if first else "", width=3)
                first = False
                i = j + 1
        elif name == "macd":
            m, sg, h = macd(closes, 6, 13, 5)
            ch.pane([{"kind": "histogram", "values": h, "colors": [("#26a69a" if x >= 0 else "#ef5350") for x in h]},
                     {"kind": "line", "values": m, "color": TV["blue"]}, {"kind": "line", "values": sg, "color": TV["orange"]}])


def build(diagram: dict, css_w: int, css_h: int, scale: int = 3):
    """→ (ảnh sơ đồ, danh sách mark đã kèm toạ độ pixel trên ảnh)."""
    from src.chart_tools import build_illustration

    path = [float(p) for p in diagram["path"]]
    bars = int(min(8, max(3, diagram.get("bars_per_leg", 5))))
    inds = [str(i).lower() for i in diagram.get("indicators") or []]
    ch, _ = build_illustration({"path": path, "bars_per_leg": bars,
                                "indicators": [i for i in inds if i in ("rsi", "volume")][:1]})
    ch.spec["hideLegend"] = True
    _indicators(ch, inds)
    n = len(ch.spec["candles"])
    right = n - 1 + 5
    marks = [dict(m) for m in diagram.get("marks") or []]
    idx = lambda k: min(len(path) - 1, max(0, int(k))) * bars
    probe = []
    for m in marks:
        t = m.get("type")
        try:
            if t == "circle":
                k = idx(m["at"])
                j = k // bars
                nb = [path[i] for i in (j - 1, j + 1) if 0 <= i < len(path)]
                m["_low"] = all(path[j] <= v for v in nb)
                m["_pts"] = [(k, path[j])]
            elif t == "hline":
                m["_pts"] = [(idx(m.get("from", 0)), float(m["price"])), (right, float(m["price"]))]
            elif t == "move":
                k = idx(m.get("at", 0))
                m["_pts"] = [(k, float(m["from_price"])), (k, float(m["to_price"])), (right, float(m["to_price"]))]
            elif t == "arrow":
                m["_pts"] = [(idx(m["from"][0]), float(m["from"][1])), (idx(m["to"][0]), float(m["to"][1]))]
            elif t == "zone":
                m["_pts"] = [(idx(m.get("start", 0)), float(m["from"])), (right, float(m["to"]))]
            else:
                continue
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        ch.include(*[p for _, p in m["_pts"]])
        m["_slot"] = len(probe)
        probe += m["_pts"]
    img, coords = ch.render_probe(css_w, css_h, scale, probe)
    out = []
    for m in marks:
        if "_slot" not in m:
            continue
        pts = coords[m["_slot"]:m["_slot"] + len(m["_pts"])]
        if any(x is None or y is None for x, y in pts):
            continue
        if m["type"] in ("hline", "move", "zone"):              # kéo tới sát thang giá bên phải
            pts = [(p[0], p[1]) for p in pts[:-1]] + [(min(pts[-1][0], img.width - 62 * scale), pts[-1][1])]
        m["xy"] = pts
        out.append(m)
    return img, out


# ------------------------------------------------------------------ vẽ từng khung

def _label(d: ImageDraw.ImageDraw, x, y, text, color, size, anchor="mm", alpha=255):
    if not text or alpha <= 0:
        return
    f = _font(size)
    w = d.textlength(text, font=f) + size * 0.9
    h = size * 1.5
    if anchor == "lm":
        x += w / 2
    elif anchor == "rm":
        x -= w / 2
    lw_, lh_ = d.im.size                                    # giữ nhãn nằm trọn trong sơ đồ
    x = min(max(x, w / 2 + 2), lw_ - w / 2 - 2)
    y = min(max(y, h / 2 + 2), lh_ - h / 2 - 2)
    # né nhãn đã đặt trước (thứ tự cố định theo mark nên vị trí không nhảy giữa các khung hình)
    for _ in range(6):
        hit = next((r for r in _PLACED if abs(r[0] - x) < (r[2] + w) / 2 + 4 and abs(r[1] - y) < (r[3] + h) / 2 + 4), None)
        if not hit:
            break
        down = y >= hit[1] and hit[1] + (hit[3] + h) / 2 + 6 + h / 2 < lh_
        y = hit[1] + (hit[3] + h) / 2 + 6 if down else hit[1] - (hit[3] + h) / 2 - 6
        y = min(max(y, h / 2 + 2), lh_ - h / 2 - 2)
    _PLACED.append((x, y, w, h))
    d.rounded_rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], radius=h / 2, fill=color + (alpha,))
    d.text((x, y), text, font=f, fill=(255, 255, 255, alpha), anchor="mm")


def _dashed(d, x0, y, x1, color, width, dash=14):
    x = x0
    while x < x1:
        d.line([(x, y), (min(x + dash, x1), y)], fill=color, width=width)
        x += dash * 2


def draw(layer: Image.Image, marks: list, f: float, t: float, starts: list[float]):
    """Vẽ các mark lên layer (đã cùng kích thước khung sơ đồ trên thẻ). f = tỉ lệ thu nhỏ ảnh sơ đồ."""
    d = ImageDraw.Draw(layer)
    _PLACED.clear()
    lw = max(4, int(6 * f * 2.2))
    fs = max(22, int(30 * f * 2.2))
    for m, start in zip(marks, starts):
        p = min(1.0, max(0.0, (t - start) / 0.75))
        if p <= 0:
            continue
        e = 1 - (1 - p) ** 3
        col = COLORS.get(m.get("color"), COLORS["red"])
        pts = [(x * f, y * f) for x, y in m["xy"]]
        la = int(255 * min(1, max(0, (p - 0.55) / 0.3)))
        if m["type"] == "circle":
            x, y = pts[0]
            pulse = 1 + 0.05 * math.sin((t - start) * 6) if p >= 1 else 1
            rx, ry = 46 * f * 2.2 * pulse, 36 * f * 2.2 * pulse
            d.arc([x - rx, y - ry, x + rx, y + ry], -90, -90 + 360 * e, fill=col + (255,), width=lw)
            ly = y + ry + fs * 1.1 if m.get("_low") else y - ry - fs * 1.1
            ly = min(layer.height - fs, max(fs, ly))
            _label(d, x, ly, m.get("label", ""), col, fs, alpha=la)
        elif m["type"] == "hline":
            (x0, y), (x1, _) = pts
            d.line([(x0, y), (x0 + (x1 - x0) * e, y)], fill=col + (255,), width=lw)
            _label(d, x1, y, m.get("label", ""), col, fs, "rm", la)
        elif m["type"] == "move":
            (x0, y0), (_, y1), (x1, _) = pts
            red, green = COLORS["red"], COLORS["green"]
            _dashed(d, x0, y0, x1, COLORS["gray"] + (200,), max(3, lw - 2))
            _label(d, x1, y0, m.get("label_from", "SL cũ"), COLORS["gray"], fs - 4, "rm")
            y = y0 + (y1 - y0) * e
            d.line([(x0, y), (x1, y)], fill=green + (255,), width=lw)
            if abs(y1 - y0) > 20:                              # mũi tên chỉ hướng dời
                ax = x0 + (x1 - x0) * 0.35
                d.line([(ax, y0), (ax, y)], fill=green + (255,), width=max(3, lw - 2))
                s = 1 if y1 < y0 else -1
                d.polygon([(ax, y - s * 2), (ax - 12, y + s * 16), (ax + 12, y + s * 16)], fill=green + (255,))
            _label(d, x1, y, m.get("label_to", "SL mới"), green, fs, "rm", la)
        elif m["type"] == "arrow":
            (x0, y0), (x1, y1) = pts
            xe, ye = x0 + (x1 - x0) * e, y0 + (y1 - y0) * e
            d.line([(x0, y0), (xe, ye)], fill=col + (255,), width=lw)
            ang = math.atan2(ye - y0, xe - x0)
            hl = lw * 3.2
            d.polygon([(xe, ye), (xe - hl * math.cos(ang - 0.45), ye - hl * math.sin(ang - 0.45)),
                       (xe - hl * math.cos(ang + 0.45), ye - hl * math.sin(ang + 0.45))], fill=col + (255,))
            side = -1 if x1 >= x0 else 1                          # nhãn cạnh đầu mũi tên, phía ngoài
            _label(d, x1 + side * fs * 0.6, y1 + (fs * 1.3 if y1 > y0 else -fs * 1.3), m.get("label", ""), col, fs,
                   "rm" if side < 0 else "lm", la)
        elif m["type"] == "zone":
            (x0, ya), (x1, yb) = pts
            top, bot = min(ya, yb), max(ya, yb)
            xe = x0 + (x1 - x0) * e
            d.rectangle([x0, top, xe, bot], fill=col + (60,), outline=col + (230,), width=max(2, lw // 2))
            _label(d, x0 + 6, top - fs * 0.95, m.get("label", ""), col, fs - 2, "lm", la)
