"""Mẫu 'Block' - kiểu social media đậm chất thương hiệu: khối màu lớn, chữ to, ít chi tiết."""
from PIL import Image, ImageDraw

from src.config import CONFIG, SYMBOLS
from src.design.common import SIZE_4X5, fit, fmt_price, key_levels, pick_events, sans, save, sparkline, wrap

GREEN = (18, 61, 47)
CREAM = (245, 241, 232)
INK = (20, 20, 20)
MUTED = (110, 108, 100)
LIME = (214, 242, 92)
UP = (26, 127, 75)
DOWN = (196, 52, 40)
DIVIDER = (214, 208, 196)

W, H = SIZE_4X5
M = 64


def render(path, date_label: str, focus: str, markets: dict, events: list[dict]):
    img = Image.new("RGBA", (W, H), CREAM)
    d = ImageDraw.Draw(img)

    # --- Khối màu trên
    d.rectangle([0, 0, W, 560], fill=GREEN)
    d.text((M, 56), CONFIG["brand"]["name"], font=sans("Bold", 24), fill=LIME)
    d.text((W - M, 58), "FOREX · VÀNG", font=sans("SemiBold", 22), fill=(170, 200, 185), anchor="ra")
    d.text((M - 5, 104), "BẢN TIN SÁNG", font=sans("ExtraBold", 108), fill=CREAM)

    pill_w = d.textlength(date_label, font=sans("Bold", 26)) + 44
    d.rounded_rectangle([M, 252, M + pill_w, 302], radius=25, fill=LIME)
    d.text((M + 22, 277), date_label, font=sans("Bold", 26), fill=GREEN, anchor="lm")

    y = 340
    for line in wrap(d, focus, sans("Bold", 46), W - 2 * M, max_lines=3):
        d.text((M, y), line, font=sans("Bold", 46), fill=CREAM)
        y += 60

    # --- 4 cột giá
    top, col_w = 604, (W - 2 * M) // 4
    for i, sym in enumerate(SYMBOLS[:4]):
        data = markets[sym["code"]]
        x = M + i * col_w + (18 if i else 0)
        if i:
            d.line([(M + i * col_w, top), (M + i * col_w, top + 230)], fill=DIVIDER, width=2)
        d.text((x, top), sym["code"], font=sans("Bold", 24), fill=MUTED)
        price = fmt_price(data["price"], sym["digits"])
        size = 36 if len(price) <= 7 else 33
        d.text((x, top + 38), price, font=sans("ExtraBold", size), fill=INK)
        chg = data["change_pct"]
        d.text((x, top + 92), f"{'+' if chg >= 0 else ''}{chg:.2f}%", font=sans("Bold", 24),
               fill=UP if chg >= 0 else DOWN)
        spark_col = UP if data["spark"][-1] >= data["spark"][0] else DOWN
        sparkline(img, data["spark"], (x, top + 140, x + col_w - 40, top + 184), spark_col, width=3, dot=True)
        d = ImageDraw.Draw(img)
        res, sup = key_levels(data)
        d.text((x, top + 200), f"HT {fmt_price(sup, sym['digits'])}", font=sans("Medium", 18), fill=MUTED)

    # --- Tin đáng chú ý (ít dòng, chữ to)
    y = top + 262
    d.line([(M, y), (W - M, y)], fill=INK, width=3)
    d.text((M, y + 22), "TIN ĐÁNG CHÚ Ý HÔM NAY", font=sans("ExtraBold", 26), fill=INK)
    d.text((W - M, y + 26), "giờ Việt Nam", font=sans("Medium", 20), fill=MUTED, anchor="ra")
    y += 78
    footer = H - 70
    rows = pick_events(events, min(4, (footer - y) // 88))
    if not rows:
        d.text((M, y), "Hôm nay không có tin quan trọng.", font=sans("Bold", 30), fill=MUTED)
    for e in rows:
        d.text((M, y), e["time"], font=sans("ExtraBold", 36), fill=GREEN)
        d.text((M + 128, y + 2), fit(d, e["title"], sans("Bold", 30), W - 2 * M - 128), font=sans("Bold", 30), fill=INK)
        sub = f"{e['currency']}  ·  Dự báo {e['forecast'] or '-'}  ·  Kỳ trước {e['previous'] or '-'}"
        d.text((M + 128, y + 44), sub, font=sans("Medium", 21), fill=MUTED)
        y += 88

    # --- Footer
    d.text((M, H - 44), "Thông tin tham khảo, không phải khuyến nghị đầu tư.", font=sans("Regular", 19),
           fill=MUTED, anchor="lm")
    d.text((W - M, H - 44), CONFIG["brand"]["handle"], font=sans("Bold", 19), fill=GREEN, anchor="rm")
    save(img, path)
    return path
