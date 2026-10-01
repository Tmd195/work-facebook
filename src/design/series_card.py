"""Ảnh bài Kiến thức theo series - phong cách Block + biểu đồ giao diện TradingView."""
from PIL import Image, ImageDraw

from src.config import CONFIG
from src.design import diagrams
from src.design.common import SIZE_4X5, fit, sans, save, wrap
from src.design.palette import CARD as CARD_C, DIVIDER as DIVIDER_C, SUB, TRACK  # noqa: F401
from src.design.styles.block import CREAM, DIVIDER, GREEN, INK, LIME, MUTED

W, H = SIZE_4X5
M = 60


def header(img: Image.Image, series_name: str, level: str, part: int, total: int, title: str) -> None:
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 400], fill=GREEN)
    d.text((M, 46), CONFIG["brand"]["name"], font=sans("Bold", 24), fill=LIME)
    d.text((W - M, 48), f"SERIES KIẾN THỨC · {level.upper()}", font=sans("SemiBold", 20),
           fill=SUB, anchor="ra")
    pill = f"PHẦN {part}/{total}"
    pw = d.textlength(pill, font=sans("ExtraBold", 24)) + 40
    d.rounded_rectangle([M, 98, M + pw, 144], radius=23, fill=LIME)
    d.text((M + pw / 2, 121), pill, font=sans("ExtraBold", 24), fill=GREEN, anchor="mm")
    d.text((M + pw + 18, 121), fit(d, series_name.upper(), sans("Bold", 24), W - 2 * M - pw - 20),
           font=sans("Bold", 24), fill=CREAM, anchor="lm")
    d.rounded_rectangle([M, 168, W - M, 176], radius=4, fill=TRACK)
    d.rounded_rectangle([M, 168, M + (W - 2 * M) * part / total, 176], radius=4, fill=LIME)
    y = 204
    for line in wrap(d, title, sans("ExtraBold", 58), W - 2 * M, max_lines=3):
        d.text((M - 3, y), line, font=sans("ExtraBold", 58), fill=CREAM)
        y += 70


def points_block(img: Image.Image, points: list[str], y: int, row_h: int, size: int) -> None:
    d = ImageDraw.Draw(img)
    for i, point in enumerate(points[:3]):
        d.text((M, y - 6), f"{i + 1:02d}", font=sans("ExtraBold", 38), fill=GREEN)
        for j, line in enumerate(wrap(d, point, sans("Bold", size), W - 2 * M - 92, max_lines=2)):
            d.text((M + 92, y + j * (size + 10)), line, font=sans("Bold", size), fill=INK)
        y += row_h
        if i < 2:
            d.line([(M + 92, y - 18), (W - M, y - 18)], fill=DIVIDER, width=2)


def render(path, series_name: str, level: str, part: int, total: int, title: str, points: list[str],
           chart_img: Image.Image | None = None, chart_caption: str = "", diagram: dict | None = None):
    img = Image.new("RGBA", (W, H), CREAM)
    header(img, series_name, level, part, total, title)
    d = ImageDraw.Draw(img)
    kind = (diagram or {}).get("type")

    if chart_img is not None:
        # Biểu đồ TradingView, viền mảnh như ảnh chụp màn hình
        cw = W - 2 * M
        ch = int(chart_img.height * cw / chart_img.width)
        shot = chart_img.resize((cw, ch), Image.LANCZOS)
        d.rectangle([M - 2, 422, M + cw + 1, 424 + ch + 1], outline=DIVIDER, width=2)
        img.alpha_composite(shot, (M, 424))
        d = ImageDraw.Draw(img)
        d.text((M, 424 + ch + 12), fit(d, chart_caption, sans("Medium", 17), W - 2 * M), font=sans("Medium", 17), fill=MUTED)
        points_block(img, points, 424 + ch + 58, 100, 25)
    elif kind == "checklist":
        diagrams.draw(img, diagram, (M, 440, W - M, 1250))
    elif kind in ("compare", "formula"):
        diagrams.draw(img, diagram, (M, 440, W - M, 880))
        points_block(img, points, 920, 104, 26)
    else:
        points_block(img, points, 480, 220, 34)

    d = ImageDraw.Draw(img)
    nxt = "Phần tiếp theo: ngày mai" if part < total else "Hoàn thành series"
    d.text((M, H - 40), nxt, font=sans("Medium", 19), fill=MUTED, anchor="lm")
    d.text((W - M, H - 40), CONFIG["brand"]["handle"], font=sans("Bold", 19), fill=GREEN, anchor="rm")
    save(img, path)
    return path
