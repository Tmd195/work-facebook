"""Mẫu 'Editorial' - phong cách báo tài chính in: nền giấy, chữ serif, đường kẻ mảnh, không bo góc."""
from PIL import Image, ImageDraw

from src.config import CONFIG, SYMBOLS
from src.design.common import (SIZE_4X5, fit, fmt_price, key_levels, pick_events, sans, save, serif,
                               sparkline, wrap)

PAPER = (243, 238, 227)
INK = (27, 27, 27)
MUTED = (107, 100, 90)
RULE = (190, 182, 168)
UP = (30, 122, 70)
DOWN = (179, 38, 30)
IMPACT = {"High": (179, 38, 30), "Medium": (196, 128, 20)}

W, H = SIZE_4X5
M = 64


def render(path, date_label: str, focus: str, markets: dict, events: list[dict]):
    img = Image.new("RGBA", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # --- Masthead
    d.text((M, 48), date_label, font=sans("Medium", 22), fill=MUTED)
    d.text((W - M, 48), "FOREX · VÀNG", font=sans("SemiBold", 22), fill=MUTED, anchor="ra")
    d.text((W // 2, 142), CONFIG["brand"]["name"].title(), font=serif(700, 80), fill=INK, anchor="mm")
    d.line([(M, 204), (W - M, 204)], fill=INK, width=4)
    d.line([(M, 212), (W - M, 212)], fill=INK, width=1)

    # --- Tiêu điểm
    d.text((M, 238), "BẢN TIN SÁNG  ·  TIÊU ĐIỂM", font=sans("Bold", 22), fill=DOWN)
    y = 276
    for line in wrap(d, focus, serif(700, 58), W - 2 * M, max_lines=2):
        d.text((M, y), line, font=serif(700, 58), fill=INK)
        y += 72
    top = max(y + 18, 430)
    d.line([(M, top), (W - M, top)], fill=INK, width=2)

    # --- 4 mã: lưới kẻ mảnh
    cell_w, cell_h = (W - 2 * M) // 2, 236
    d.line([(W // 2, top + 18), (W // 2, top + 2 * cell_h - 18)], fill=RULE, width=1)
    d.line([(M, top + cell_h), (W - M, top + cell_h)], fill=RULE, width=1)
    for i, sym in enumerate(SYMBOLS[:4]):
        data = markets[sym["code"]]
        x = M + (i % 2) * cell_w + (i % 2) * 24
        y = top + (i // 2) * cell_h + 24
        inner = cell_w - 24

        d.text((x, y), sym["code"], font=sans("Bold", 28), fill=INK)
        d.text((x + d.textlength(sym["code"], font=sans("Bold", 28)) + 12, y + 4), sym["name"],
               font=serif(400, 24, italic=True), fill=MUTED)
        price = fmt_price(data["price"], sym["digits"])
        d.text((x, y + 44), price, font=serif(700, 54), fill=INK)

        chg = data["change_pct"]
        col = UP if chg >= 0 else DOWN
        d.text((x, y + 116), f"{'+' if chg >= 0 else ''}{chg:.2f}%", font=sans("Bold", 24), fill=col)
        d.text((x + 110, y + 118), f"Xu hướng D1: {data['trend'].lower()}", font=sans("Regular", 21), fill=MUTED)

        spark_col = UP if data["spark"][-1] >= data["spark"][0] else DOWN
        sx = x + max(250, int(d.textlength(price, font=serif(700, 54))) + 30)
        sparkline(img, data["spark"], (sx, y + 54, x + inner - 8, y + 104), spark_col, width=2, dot=False)
        d = ImageDraw.Draw(img)

        res, sup = key_levels(data)
        lx = x
        for lbl, v in (("Kháng cự", res), ("Hỗ trợ", sup)):
            d.text((lx, y + 160), lbl, font=sans("Regular", 21), fill=MUTED)
            lx += d.textlength(lbl, font=sans("Regular", 21)) + 10
            d.text((lx, y + 158), fmt_price(v, sym["digits"]), font=sans("Bold", 23), fill=INK)
            lx = x + 236

    # --- Lịch kinh tế
    y = top + 2 * cell_h + 8
    d.line([(M, y), (W - M, y)], fill=INK, width=2)
    d.text((M, y + 20), "LỊCH KINH TẾ HÔM NAY", font=sans("Bold", 24), fill=INK)
    d.text((W - M, y + 22), "giờ Việt Nam", font=serif(400, 22, italic=True), fill=MUTED, anchor="ra")
    y += 70
    footer = H - 74
    rows = pick_events(events, min(CONFIG["calendar"]["max_events_on_banner"], (footer - y - 10) // 54))
    if not rows:
        d.text((M, y + 10), "Không có tin quan trọng của USD, EUR, GBP.", font=serif(400, 26, italic=True), fill=MUTED)
    for e in rows:
        cy = y + 24
        d.rectangle([M, cy - 7, M + 14, cy + 7], fill=IMPACT.get(e["impact"], MUTED))
        d.text((M + 30, cy), e["time"], font=serif(700, 28), fill=INK, anchor="lm")
        d.text((M + 128, cy), e["currency"], font=sans("Bold", 22), fill=MUTED, anchor="lm")
        right = f"DB {e['forecast'] or '-'}  ·  Trước {e['previous'] or '-'}"
        rw = d.textlength(right, font=sans("Regular", 21))
        d.text((W - M, cy), right, font=sans("Regular", 21), fill=MUTED, anchor="rm")
        d.text((M + 200, cy), fit(d, e["title"], sans("Medium", 24), W - M - rw - M - 230),
               font=sans("Medium", 24), fill=INK, anchor="lm")
        y += 54
        d.line([(M, y - 3), (W - M, y - 3)], fill=RULE, width=1)

    # --- Footer
    d.line([(M, footer), (W - M, footer)], fill=INK, width=1)
    d.text((M, footer + 20), "Thông tin tham khảo, không phải khuyến nghị đầu tư.",
           font=serif(400, 21, italic=True), fill=MUTED)
    d.text((W - M, footer + 20), CONFIG["brand"]["handle"], font=sans("SemiBold", 20), fill=INK, anchor="ra")
    save(img, path)
    return path
