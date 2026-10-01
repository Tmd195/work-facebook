"""Mẫu 'Clean' - kiểu báo cáo phân tích của broker: nền trắng, dải xanh đậm, bảng số liệu rõ ràng."""
from PIL import Image, ImageDraw

from src.config import CONFIG, SYMBOLS
from src.design.common import SIZE_4X5, fit, fmt_price, key_levels, pick_events, sans, save, wrap

WHITE = (255, 255, 255)
BAND = (20, 52, 110)
TEXT = (17, 24, 39)
MUTED = (107, 114, 128)
ZEBRA = (243, 245, 248)
LINE = (226, 230, 236)
UP = (22, 128, 61)
DOWN = (200, 40, 40)
IMPACT = {"High": (200, 40, 40), "Medium": (217, 119, 6)}
TREND = {"Tăng": UP, "Giảm": DOWN, "Đi ngang": MUTED}

W, H = SIZE_4X5
M = 60


def render(path, date_label: str, focus: str, markets: dict, events: list[dict]):
    img = Image.new("RGBA", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    # --- Dải tiêu đề
    d.rectangle([0, 0, W, 262], fill=BAND)
    d.text((M, 48), CONFIG["brand"]["name"], font=sans("Bold", 24), fill=(170, 190, 225))
    d.text((W - M, 50), date_label, font=sans("Medium", 24), fill=(210, 222, 242), anchor="ra")
    d.text((M - 3, 92), "Bản tin sáng", font=sans("ExtraBold", 84), fill=WHITE)

    # --- Tiêu điểm
    y = 300
    lines = wrap(d, focus, sans("Bold", 34), W - 2 * M - 30, max_lines=2)
    d.rectangle([M, y + 4, M + 6, y + 46 * len(lines) - 2], fill=BAND)
    for line in lines:
        d.text((M + 26, y), line, font=sans("Bold", 34), fill=TEXT)
        y += 46
    y = max(y, 392) + 30

    # --- Bảng giá
    cols = [("Mã", M + 16), ("Giá", M + 190), ("Thay đổi", M + 360), ("Xu hướng D1", M + 510),
            ("Hỗ trợ", W - M - 170), ("Kháng cự", W - M - 16)]
    for i, (lbl, x) in enumerate(cols):
        d.text((x, y), lbl.upper(), font=sans("SemiBold", 18), fill=MUTED, anchor="ra" if i >= 4 else "la")
    y += 34
    row_h = 78
    for r, sym in enumerate(SYMBOLS[:4]):
        data = markets[sym["code"]]
        if r % 2 == 0:
            d.rectangle([M, y, W - M, y + row_h], fill=ZEBRA)
        cy = y + row_h // 2
        d.text((cols[0][1], cy - 12), sym["code"], font=sans("Bold", 26), fill=TEXT, anchor="lm")
        d.text((cols[0][1], cy + 18), sym["name"], font=sans("Regular", 18), fill=MUTED, anchor="lm")
        d.text((cols[1][1], cy), fmt_price(data["price"], sym["digits"]), font=sans("Bold", 30), fill=TEXT, anchor="lm")
        chg = data["change_pct"]
        d.text((cols[2][1], cy), f"{'+' if chg >= 0 else ''}{chg:.2f}%", font=sans("Bold", 26),
               fill=UP if chg >= 0 else DOWN, anchor="lm")
        d.text((cols[3][1], cy), data["trend"], font=sans("SemiBold", 24), fill=TREND[data["trend"]], anchor="lm")
        res, sup = key_levels(data)
        d.text((cols[4][1], cy), fmt_price(sup, sym["digits"]), font=sans("Medium", 24), fill=TEXT, anchor="rm")
        d.text((cols[5][1], cy), fmt_price(res, sym["digits"]), font=sans("Medium", 24), fill=TEXT, anchor="rm")
        y += row_h
    d.line([(M, y), (W - M, y)], fill=LINE, width=2)

    # --- Lịch kinh tế
    y += 40
    d.text((M, y), "Lịch kinh tế hôm nay", font=sans("ExtraBold", 32), fill=TEXT)
    d.text((W - M, y + 10), "Giờ Việt Nam", font=sans("Medium", 20), fill=MUTED, anchor="ra")
    y += 60
    footer = H - 80
    row_h = 58
    rows = pick_events(events, min(CONFIG["calendar"]["max_events_on_banner"], (footer - y - 10) // row_h))
    if not rows:
        d.text((M, y + 10), "Hôm nay không có tin quan trọng của USD, EUR, GBP.", font=sans("Medium", 24), fill=MUTED)
    for e in rows:
        cy = y + row_h // 2
        d.rectangle([M, y + 12, M + 5, y + row_h - 12], fill=IMPACT.get(e["impact"], MUTED))
        d.text((M + 22, cy), e["time"], font=sans("Bold", 26), fill=TEXT, anchor="lm")
        d.text((M + 118, cy), e["currency"], font=sans("Bold", 22), fill=BAND, anchor="lm")
        right = f"{e['forecast'] or '-'}  /  {e['previous'] or '-'}"
        rw = d.textlength(right, font=sans("Medium", 22))
        d.text((W - M, cy), right, font=sans("Medium", 22), fill=MUTED, anchor="rm")
        d.text((M + 196, cy), fit(d, e["title"], sans("Medium", 24), W - 2 * M - 196 - rw - 30),
               font=sans("Medium", 24), fill=TEXT, anchor="lm")
        y += row_h
        d.line([(M, y), (W - M, y)], fill=LINE, width=1)
    if rows:
        d.text((W - M, y + 10), "Dự báo / Kỳ trước", font=sans("Regular", 18), fill=MUTED, anchor="ra")

    # --- Footer
    d.rectangle([0, footer, W, H], fill=ZEBRA)
    d.text((M, footer + 40), "Thông tin tham khảo, không phải khuyến nghị đầu tư.",
           font=sans("Regular", 20), fill=MUTED, anchor="lm")
    d.text((W - M, footer + 40), CONFIG["brand"]["handle"], font=sans("Bold", 20), fill=BAND, anchor="rm")
    save(img, path)
    return path
