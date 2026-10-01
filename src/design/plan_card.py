"""Ảnh bài Plan A/B - phong cách Block: biểu đồ H1 thật của XAUUSD + mũi tên 2 kịch bản + 2 thẻ plan."""
from PIL import Image, ImageDraw

from src.config import CONFIG
from src.design.common import SIZE_4X5, fit, fmt_price, sans, save, wrap
from src.design.knowledge_card import dashed
from src.design.styles.block import CREAM, DIVIDER, DOWN, GREEN, INK, LIME, MUTED, UP

W, H = SIZE_4X5
M = 56
CARD = (236, 231, 219)


def arrow(d: ImageDraw.ImageDraw, pts: list[tuple], color, width: int = 5):
    d.line(pts, fill=color, width=width, joint="curve")
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    import math
    ang = math.atan2(y1 - y0, x1 - x0)
    size = 18
    left = (x1 - size * math.cos(ang - 0.45), y1 - size * math.sin(ang - 0.45))
    right = (x1 - size * math.cos(ang + 0.45), y1 - size * math.sin(ang + 0.45))
    d.polygon([(x1, y1), left, right], fill=color)


def spread_labels(ys: list[float], gap: int, lo: float, hi: float) -> list[float]:
    """Đẩy các nhãn giá ra xa nhau để không chồng lên nhau."""
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    out = ys[:]
    for a, b in zip(order, order[1:]):
        if out[b] - out[a] < gap:
            out[b] = out[a] + gap
    overflow = out[order[-1]] - hi if order else 0
    if overflow > 0:
        for i in order:
            out[i] -= overflow
    return [max(lo, y) for y in out]


def draw_chart(img: Image.Image, box: tuple, chart: list, price: float, plan: dict, digits: int):
    x0, y0, x1, y1 = box
    candles = chart[-48:]
    a, b = plan["plan_a"], plan["plan_b"]
    marks = [(a["entry"], DOWN, "A · Entry"), (a["tp"], DOWN, "A · TP"),
             (b["entry"], UP, "B · Entry"), (b["tp"], UP, "B · TP")]

    lo = min(min(c[3] for c in candles), *(m[0] for m in marks))
    hi = max(max(c[2] for c in candles), *(m[0] for m in marks))
    pad = (hi - lo) * 0.06
    lo, hi = lo - pad, hi + pad
    py = lambda p: y1 - (p - lo) / (hi - lo) * (y1 - y0)

    label_w = 230
    future_w = 170
    cx1 = x1 - label_w - future_w
    step = (cx1 - x0) / len(candles)
    body = max(4, step * 0.62)

    d = ImageDraw.Draw(img)
    for i in range(5):  # lưới ngang mờ
        gy = y0 + i * (y1 - y0) / 4
        d.line([(x0, gy), (x1 - label_w, gy)], fill=DIVIDER, width=1)

    for m_price, color, _ in marks:
        dashed(d, x0, x1 - label_w + 6, py(m_price), color, dash=10, gap=7, width=2)

    for i, (_, o, h, l, c) in enumerate(candles):
        cx = x0 + i * step + step / 2
        col = UP if c >= o else DOWN
        d.line([(cx, py(h)), (cx, py(l))], fill=col, width=2)
        top, bot = py(max(o, c)), py(min(o, c))
        d.rectangle([cx - body / 2, top, cx + body / 2, max(bot, top + 2)], fill=col)

    # Giá hiện tại
    yp = py(price)
    lx = x0 + len(candles) * step
    d.ellipse([lx - 7, yp - 7, lx + 7, yp + 7], fill=INK)

    # Mũi tên kịch bản
    fx = cx1 + future_w - 10
    for s, col in ((a, DOWN), (b, UP)):
        arrow(d, [(lx + 10, yp), (cx1 + future_w * 0.45, py(s["entry"])), (fx, py(s["tp"]))], col)

    # Nhãn giá bên phải
    ys = spread_labels([py(m[0]) for m in marks] + [yp], 38, y0, y1)
    items = marks + [(price, INK, "Hiện tại")]
    for (m_price, color, name), y in zip(items, ys):
        text = f"{name}  {fmt_price(m_price, digits)}"
        d.rounded_rectangle([x1 - label_w + 12, y - 17, x1, y + 17], radius=8, fill=color)
        d.text((x1 - label_w + 24, y), text, font=sans("Bold", 18), fill=CREAM, anchor="lm")


def tv_chart(chart: list, plan: dict, digits: int) -> Image.Image:
    """Biểu đồ H1 thật giao diện TradingView: vùng Entry/TP/SL của 2 kịch bản + mũi tên."""
    from datetime import datetime

    from src.data.prices import Candle
    from src.design.tvchart import TV, TVChart

    rows = chart[-60:]
    candles = [Candle(datetime.fromisoformat(r[0]), *r[1:5]) for r in rows]
    ch = TVChart(plan["symbol"], "1H", candles, digits, right_offset=10)
    a, b = plan["plan_a"], plan["plan_b"]
    ch.price_line(a["entry"], TV["down"], "A · Entry", style=0, width=2)
    ch.price_line(a["tp"], TV["down"], "A · TP")
    ch.price_line(b["entry"], TV["up"], "B · Entry", style=0, width=2)
    ch.price_line(b["tp"], TV["up"], "B · TP")
    last, price = len(candles) - 1, candles[-1].close
    ch.segment(last, price, last + 4, a["entry"], TV["down"], width=2)
    ch.segment(last + 4, a["entry"], last + 9, a["tp"], TV["down"], width=2, arrow=True)
    ch.segment(last, price, last + 4, b["entry"], TV["up"], width=2)
    ch.segment(last + 4, b["entry"], last + 9, b["tp"], TV["up"], width=2, arrow=True)
    return ch.render(640, 274, scale=3)


def plan_card(img: Image.Image, box: tuple, name: str, subtitle: str, s: dict, color, digits: int):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=CARD)
    d.rectangle([x0, y0, x1, y0 + 8], fill=color)
    d.text((x0 + 28, y0 + 30), name, font=sans("ExtraBold", 34), fill=INK)
    side_w = d.textlength(s["side"], font=sans("Bold", 22)) + 32
    d.rounded_rectangle([x1 - 28 - side_w, y0 + 32, x1 - 28, y0 + 72], radius=20, fill=color)
    d.text((x1 - 28 - side_w / 2, y0 + 52), s["side"], font=sans("Bold", 22), fill=CREAM, anchor="mm")
    d.text((x0 + 28, y0 + 80), subtitle, font=sans("Medium", 20), fill=MUTED)

    y = y0 + 124
    for line in wrap(d, s["condition"], sans("Bold", 23), x1 - x0 - 56, max_lines=2):
        d.text((x0 + 28, y), line, font=sans("Bold", 23), fill=INK)
        y += 32
    y = y0 + 208
    for label, key in (("Entry", "entry"), ("Stop loss", "sl"), ("Take profit", "tp")):
        d.line([(x0 + 28, y), (x1 - 28, y)], fill=DIVIDER, width=2)
        d.text((x0 + 28, y + 30), label, font=sans("Medium", 22), fill=MUTED, anchor="lm")
        d.text((x1 - 28, y + 30), fmt_price(s[key], digits), font=sans("ExtraBold", 28),
               fill=color if key == "tp" else INK, anchor="rm")
        y += 60


def render(path, date_label: str, focus: str, events: list[dict], chart: list, price: float,
           plan: dict, digits: int):
    img = Image.new("RGBA", (W, H), CREAM)
    d = ImageDraw.Draw(img)

    # --- Header
    d.rectangle([0, 0, W, 320], fill=GREEN)
    d.text((M, 52), CONFIG["brand"]["name"], font=sans("Bold", 24), fill=LIME)
    d.text((W - M, 54), date_label, font=sans("SemiBold", 22), fill=(170, 200, 185), anchor="ra")
    tag = "PLAN A/B TRƯỚC TIN" if events else "PLAN A/B PHIÊN MỸ"
    tw = d.textlength(tag, font=sans("Bold", 24))
    d.rounded_rectangle([M, 108, M + tw + 44, 156], radius=24, fill=LIME)
    d.text((M + 22, 132), tag, font=sans("Bold", 24), fill=GREEN, anchor="lm")
    size = next((sz for sz in (56, 50, 44, 40) if d.textlength(focus, font=sans("ExtraBold", sz)) <= W - 2 * M), 40)
    d.text((M - 2, 178 + (56 - size) // 2), fit(d, focus, sans("ExtraBold", size), W - 2 * M),
           font=sans("ExtraBold", size), fill=CREAM)
    if events:
        e = events[0]
        sub = f"{e['time']}  ·  {e['currency']} {e['title']}  ·  Dự báo {e['forecast'] or '-'}  ·  Trước {e['previous'] or '-'}"
        d.text((M, 266), fit(d, sub, sans("Medium", 22), W - 2 * M), font=sans("Medium", 22), fill=(190, 215, 200))

    # --- Biểu đồ
    d.text((M, 352), f"Kịch bản trên biểu đồ {plan['symbol']} H1 (giá thật)", font=sans("Bold", 24), fill=INK)
    tv = tv_chart(chart, plan, digits)
    shot = tv.resize((W - 2 * M, int(tv.height * (W - 2 * M) / tv.width)), Image.LANCZOS)
    d.rectangle([M - 2, 408, W - M + 1, 410 + shot.height + 1], outline=(214, 208, 196), width=2)
    img.alpha_composite(shot, (M, 410))

    # --- 2 thẻ plan
    gap = 24
    cw = (W - 2 * M - gap) // 2
    top = 856
    plan_card(img, (M, top, M + cw, top + 400), "PLAN A", "Nếu số liệu ủng hộ USD", plan["plan_a"], DOWN, digits)
    plan_card(img, (M + cw + gap, top, W - M, top + 400), "PLAN B", "Nếu số liệu bất lợi cho USD",
              plan["plan_b"], UP, digits)

    d = ImageDraw.Draw(img)
    d.text((M, H - 48), "Kịch bản tham khảo, chờ giá xác nhận sau tin 5-15 phút.", font=sans("Regular", 19),
           fill=MUTED, anchor="lm")
    d.text((W - M, H - 48), CONFIG["brand"]["handle"], font=sans("Bold", 19), fill=GREEN, anchor="rm")
    save(img, path)
    return path
