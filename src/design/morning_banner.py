"""Banner 'Bản tin sáng' 1080x1350: giá 4 mã + lịch tin trong ngày."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from src.config import CONFIG, SYMBOLS
from src.design.theme import COLORS, IMPACT_COLOR, PAD, SIZE, TREND_COLOR, font

W, H = SIZE


def fmt_price(value: float, digits: int) -> str:
    return f"{value:,.{digits}f}" if value >= 1000 else f"{value:.{digits}f}"


def fit(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int) -> str:
    if draw.textlength(text, font=fnt) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=fnt) > max_w:
        text = text[:-1]
    return text.rstrip() + "…"


def background() -> Image.Image:
    img = Image.new("RGB", SIZE, COLORS["bg_top"])
    top, bottom = COLORS["bg_top"], COLORS["bg_bottom"]
    grad = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        grad.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))

    # Vầng sáng vàng góc trên phải + lưới mờ kiểu biểu đồ
    glow = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([W - 520, -380, W + 320, 360], fill=(230, 180, 80, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(140))
    img = Image.alpha_composite(img.convert("RGBA"), glow)

    grid = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    g = ImageDraw.Draw(grid)
    for x in range(0, W, 54):
        g.line([(x, 0), (x, H)], fill=(255, 255, 255, 7))
    for y in range(0, H, 54):
        g.line([(0, y), (W, y)], fill=(255, 255, 255, 7))
    return Image.alpha_composite(img, grid)


def sparkline(img: Image.Image, values: list[float], box: tuple, color: tuple):
    x0, y0, x1, y1 = box
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    pts = [
        (x0 + i * (x1 - x0) / (len(values) - 1), y1 - (v - lo) / span * (y1 - y0))
        for i, v in enumerate(values)
    ]
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.polygon(pts + [(x1, y1), (x0, y1)], fill=color + (38,))
    d.line(pts, fill=color + (255,), width=3, joint="curve")
    lx, ly = pts[-1]
    d.ellipse([lx - 5, ly - 5, lx + 5, ly + 5], fill=color + (255,))
    img.alpha_composite(layer)


def price_card(img: Image.Image, box: tuple, sym: dict, data: dict):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=22, fill=COLORS["card"], outline=COLORS["card_border"], width=2)

    d.text((x0 + 28, y0 + 24), sym["code"], font=font("Bold", 30), fill=COLORS["text"])
    d.text((x0 + 28, y0 + 62), sym["name"], font=font("Regular", 20), fill=COLORS["muted"])

    # Nhãn xu hướng
    trend = data["trend"]
    tcol = TREND_COLOR[trend]
    label = f"D1 · {trend}"
    tw = d.textlength(label, font=font("SemiBold", 18))
    d.rounded_rectangle([x1 - 28 - tw - 28, y0 + 26, x1 - 28, y0 + 60], radius=17, outline=tcol, width=2)
    d.text((x1 - 28 - tw - 14, y0 + 31), label, font=font("SemiBold", 18), fill=tcol)

    # Giá + % thay đổi
    price_txt = fmt_price(data["price"], sym["digits"])
    pf = font("ExtraBold", 42)
    d.text((x0 + 28, y0 + 92), price_txt, font=pf, fill=COLORS["text"])
    chg = data["change_pct"]
    ccol = COLORS["green"] if chg >= 0 else COLORS["red"]
    ty = y0 + 160
    tri = [(x0 + 28, ty + 6), (x0 + 44, ty + 6), (x0 + 36, ty - 7)] if chg >= 0 else           [(x0 + 28, ty - 6), (x0 + 44, ty - 6), (x0 + 36, ty + 7)]
    d.polygon(tri, fill=ccol)
    d.text((x0 + 52, ty), f"{chg:+.2f}%", font=font("SemiBold", 22), fill=ccol, anchor="lm")

    spark_col = COLORS["green"] if data["spark"][-1] >= data["spark"][0] else COLORS["red"]
    sx = x0 + 28 + max(220, int(d.textlength(price_txt, font=pf)) + 28)
    sparkline(img, data["spark"], (sx, y0 + 100, x1 - 28, y0 + 170), spark_col)

    # Vùng giá quan trọng
    d = ImageDraw.Draw(img)
    d.line([(x0 + 28, y0 + 186), (x1 - 28, y0 + 186)], fill=COLORS["divider"], width=1)
    res = data["resistance"][0] if data["resistance"] else data["r1"]
    sup = data["support"][0] if data["support"] else data["s1"]
    small, val = font("Regular", 19), font("Bold", 21)
    col_w = (x1 - x0 - 56) // 2
    for i, (lbl, v, c) in enumerate([("Kháng cự", res, COLORS["red"]), ("Hỗ trợ", sup, COLORS["green"])]):
        cx = x0 + 28 + i * col_w
        d.text((cx, y0 + 196), lbl, font=small, fill=COLORS["muted"])
        d.text((cx, y0 + 220), fmt_price(v, sym["digits"]), font=val, fill=c)


def calendar_table(img: Image.Image, top: int, events: list[dict], bottom: int):
    d = ImageDraw.Draw(img)
    d.text((PAD, top), "LỊCH TIN HÔM NAY", font=font("ExtraBold", 30), fill=COLORS["text"])
    d.text((PAD + d.textlength("LỊCH TIN HÔM NAY", font=font("ExtraBold", 30)) + 14, top + 8),
           "(giờ Việt Nam)", font=font("Regular", 20), fill=COLORS["muted"])

    # Chú thích mức độ tác động
    lx = W - PAD
    for lbl, key in (("Trung bình", "Medium"), ("Cao", "High")):
        tw = d.textlength(lbl, font=font("Regular", 18))
        lx -= tw
        d.text((lx, top + 10), lbl, font=font("Regular", 18), fill=COLORS["muted"])
        lx -= 22
        d.rounded_rectangle([lx, top + 14, lx + 14, top + 28], radius=4, fill=IMPACT_COLOR[key])
        lx -= 22

    y = top + 58
    head = font("SemiBold", 17)
    cols = {"time": PAD + 22, "cur": PAD + 110, "title": PAD + 196, "fc": W - PAD - 200, "pv": W - PAD - 90}
    for key, lbl in (("time", "GIỜ"), ("cur", "TIỀN TỆ"), ("title", "SỰ KIỆN"), ("fc", "DỰ BÁO"), ("pv", "KỲ TRƯỚC")):
        d.text((cols[key], y), lbl, font=head, fill=COLORS["muted"])
    y += 34

    row_h = 50
    capacity = min(CONFIG["calendar"]["max_events_on_banner"], (bottom - y - 30) // row_h)
    ranked = sorted(events, key=lambda e: (e["impact"] != "High", e["datetime"]))[:capacity]
    rows = sorted(ranked, key=lambda e: e["datetime"])
    if not rows:
        d.rounded_rectangle([PAD, y, W - PAD, y + 90], radius=16, fill=COLORS["card"])
        d.text((PAD + 28, y + 28), "Hôm nay không có tin quan trọng của USD / EUR / GBP",
               font=font("Medium", 24), fill=COLORS["muted"])
        return

    for i, e in enumerate(rows):
        if i % 2 == 0:
            d.rounded_rectangle([PAD, y, W - PAD, y + row_h - 6], radius=12, fill=COLORS["card"])
        cy = y + (row_h - 6) // 2
        d.rounded_rectangle([PAD, y, PAD + 6, y + row_h - 6], radius=3, fill=IMPACT_COLOR[e["impact"]])
        d.text((cols["time"], cy), e["time"], font=font("Bold", 22), fill=COLORS["text"], anchor="lm")
        d.rounded_rectangle([cols["cur"], cy - 15, cols["cur"] + 62, cy + 15], radius=8, fill=COLORS["card_border"])
        d.text((cols["cur"] + 31, cy), e["currency"], font=font("Bold", 18), fill=COLORS["gold"], anchor="mm")
        title = fit(d, e["title"], font("Medium", 21), cols["fc"] - cols["title"] - 16)
        d.text((cols["title"], cy), title, font=font("Medium", 21), fill=COLORS["text"], anchor="lm")
        d.text((cols["fc"], cy), e["forecast"] or "-", font=font("SemiBold", 20), fill=COLORS["text"], anchor="lm")
        d.text((cols["pv"], cy), e["previous"] or "-", font=font("Regular", 20), fill=COLORS["muted"], anchor="lm")
        y += row_h

    hidden = len(events) - len(rows)
    if hidden > 0:
        d.text((PAD + 22, y + 4), f"+ {hidden} tin khác - xem chi tiết trong bài viết",
               font=font("Regular", 18), fill=COLORS["muted"])


def render(path: Path, date_label: str, focus: str, markets: dict, events: list[dict]) -> Path:
    img = background()
    d = ImageDraw.Draw(img)

    # Header: thương hiệu
    brand = CONFIG["brand"]["name"]
    d.rounded_rectangle([PAD, 50, PAD + 12, 86], radius=3, fill=COLORS["gold"])
    d.text((PAD + 26, 50), brand, font=font("ExtraBold", 28), fill=COLORS["gold"])
    d.text((W - PAD, 56), "FOREX · GOLD", font=font("SemiBold", 20), fill=COLORS["muted"], anchor="ra")

    # Tiêu đề
    d.text((PAD - 4, 100), "BẢN TIN SÁNG", font=font("ExtraBold", 80), fill=COLORS["text"])
    d.text((PAD, 200), date_label, font=font("Medium", 30), fill=COLORS["gold"])

    # Tiêu điểm hôm nay
    fy = 258
    box = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    ImageDraw.Draw(box).rounded_rectangle([PAD, fy, W - PAD, fy + 60], radius=16,
                                          fill=(230, 180, 80, 30), outline=(230, 180, 80, 255), width=2)
    img.alpha_composite(box)
    d = ImageDraw.Draw(img)
    d.text((PAD + 24, fy + 30), "TIÊU ĐIỂM", font=font("ExtraBold", 20), fill=COLORS["gold"], anchor="lm")
    d.text((PAD + 150, fy + 30), fit(d, focus, font("SemiBold", 25), W - 2 * PAD - 180),
           font=font("SemiBold", 25), fill=COLORS["text"], anchor="lm")

    # 4 thẻ giá
    gap = 20
    cw = (W - 2 * PAD - gap) // 2
    ch = 256
    top = 342
    for i, sym in enumerate(SYMBOLS[:4]):
        x = PAD + (i % 2) * (cw + gap)
        y = top + (i // 2) * (ch + gap)
        price_card(img, (x, y, x + cw, y + ch), sym, markets[sym["code"]])

    footer_y = H - 66
    calendar_table(img, top + 2 * ch + gap + 30, events, footer_y - 6)

    # Footer
    d = ImageDraw.Draw(img)
    d.line([(PAD, footer_y), (W - PAD, footer_y)], fill=COLORS["divider"], width=1)
    d.text((PAD, footer_y + 18), "Thông tin tham khảo, không phải khuyến nghị đầu tư.",
           font=font("Regular", 18), fill=COLORS["muted"])
    d.text((W - PAD, footer_y + 18), CONFIG["brand"]["handle"], font=font("SemiBold", 18),
           fill=COLORS["gold"], anchor="ra")

    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, "PNG", optimize=True)
    return path
