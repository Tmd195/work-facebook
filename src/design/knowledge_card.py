"""Ảnh bài Kiến thức - phong cách Block: tiêu đề trên khối xanh, hình minh họa nến + 3 ý chính."""
from PIL import Image, ImageDraw

from src.config import CONFIG
from src.design.common import SIZE_4X5, fit, sans, save, wrap
from src.design.styles.block import CREAM, DIVIDER, DOWN, GREEN, INK, LIME, MUTED, UP

W, H = SIZE_4X5
M = 64


def dashed(d: ImageDraw.ImageDraw, x0: int, x1: int, y: float, color, dash: int = 12, gap: int = 8, width: int = 2):
    x = x0
    while x < x1:
        d.line([(x, y), (min(x + dash, x1), y)], fill=color, width=width)
        x += dash + gap


def draw_diagram(img: Image.Image, diagram: dict, box: tuple):
    x0, y0, x1, y1 = box
    candles, lines, hl = diagram["candles"], diagram.get("lines") or [], diagram.get("highlight")
    label_w = 170 if lines else 0
    cx1 = x1 - label_w
    lo = min(min(c[2] for c in candles), *(l["price"] for l in lines)) if lines else min(c[2] for c in candles)
    hi = max(max(c[1] for c in candles), *(l["price"] for l in lines)) if lines else max(c[1] for c in candles)
    pad = (hi - lo) * 0.08 or 1
    lo, hi = lo - pad, hi + pad
    py = lambda p: y1 - (p - lo) / (hi - lo) * (y1 - y0)
    step = (cx1 - x0) / len(candles)
    body = max(6, step * 0.6)

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if hl and 0 <= hl["from"] <= hl["to"] < len(candles):
        hx0, hx1 = x0 + hl["from"] * step, x0 + (hl["to"] + 1) * step
        d.rounded_rectangle([hx0, y0 + 30, hx1, y1], radius=10, fill=LIME + (110,))
        d.text(((hx0 + hx1) / 2, y0 + 4), hl["label"], font=sans("Bold", 20), fill=GREEN, anchor="ma")
    img.alpha_composite(layer)

    d = ImageDraw.Draw(img)
    for i, (o, h, l, c) in enumerate(candles):
        cx = x0 + i * step + step / 2
        col = UP if c >= o else DOWN
        d.line([(cx, py(h)), (cx, py(l))], fill=col, width=3)
        top, bot = py(max(o, c)), py(min(o, c))
        d.rectangle([cx - body / 2, top, cx + body / 2, max(bot, top + 2)], fill=col)

    for ln in lines[:3]:
        y = py(ln["price"])
        dashed(d, x0, cx1 + 10, y, INK)
        text = fit(d, ln["label"], sans("Bold", 19), label_w - 30)
        tw = d.textlength(text, font=sans("Bold", 19))
        d.rounded_rectangle([cx1 + 16, y - 16, cx1 + 16 + tw + 20, y + 16], radius=8, fill=INK)
        d.text((cx1 + 26, y), text, font=sans("Bold", 19), fill=CREAM, anchor="lm")


def render(path, number: int, category: str, title: str, points: list[str], diagram: dict | None):
    img = Image.new("RGBA", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    block_h = 500 if diagram else 560

    # --- Khối tiêu đề
    d.rectangle([0, 0, W, block_h], fill=GREEN)
    d.text((M, 56), CONFIG["brand"]["name"], font=sans("Bold", 24), fill=LIME)
    d.text((W - M, 58), "KIẾN THỨC FOREX", font=sans("SemiBold", 22), fill=(170, 200, 185), anchor="ra")
    tag = f"KIẾN THỨC #{number:02d}  ·  {category.upper()}"
    tw = d.textlength(tag, font=sans("Bold", 24))
    d.rounded_rectangle([M, 118, M + tw + 44, 166], radius=24, fill=LIME)
    d.text((M + 22, 142), tag, font=sans("Bold", 24), fill=GREEN, anchor="lm")
    y = 200
    for line in wrap(d, title, sans("ExtraBold", 66), W - 2 * M, max_lines=3):
        d.text((M - 3, y), line, font=sans("ExtraBold", 66), fill=CREAM)
        y += 82

    # --- Minh họa
    if diagram:
        draw_diagram(img, diagram, (M, block_h + 36, W - M, block_h + 380))
        d = ImageDraw.Draw(img)
        d.text((W - M, block_h + 392), "Hình minh họa, không phải giá thật", font=sans("Regular", 17),
               fill=MUTED, anchor="ra")
        y, row_h, size = block_h + 430, 116, 28
    else:
        y, row_h, size = block_h + 70, 190, 34

    # --- 3 ý chính
    for i, point in enumerate(points[:3]):
        d.text((M, y - 4), f"{i + 1:02d}", font=sans("ExtraBold", 44), fill=GREEN)
        for j, line in enumerate(wrap(d, point, sans("Bold", size), W - 2 * M - 100, max_lines=2)):
            d.text((M + 100, y + j * (size + 12)), line, font=sans("Bold", size), fill=INK)
        y += row_h
        if i < 2:
            d.line([(M + 100, y - 22), (W - M, y - 22)], fill=DIVIDER, width=2)

    # --- Footer
    d.text((M, H - 44), "Lưu bài để xem lại khi cần", font=sans("Medium", 19),
           fill=MUTED, anchor="lm")
    d.text((W - M, H - 44), CONFIG["brand"]["handle"], font=sans("Bold", 19), fill=GREEN, anchor="rm")
    save(img, path)
    return path
