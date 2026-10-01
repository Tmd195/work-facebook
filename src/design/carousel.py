"""Album ảnh cho bài Kiến thức: ảnh bìa + mỗi ý một ảnh riêng (01, 02, 03...) kèm biểu đồ TradingView và diễn giải."""
from PIL import Image, ImageDraw

from src.config import CONFIG
from src.design import diagrams
from src.design.common import SIZE_4X5, fit, sans, save, wrap
from src.design.palette import CARD as CARD_C, DIVIDER as DIVIDER_C, SUB, TRACK  # noqa: F401
from src.design.styles.block import CREAM, DIVIDER, GREEN, INK, LIME, MUTED

W, H = SIZE_4X5
M = 60


def _footer(d: ImageDraw.ImageDraw, left: str, right: str | None = None):
    arrow = left.endswith("→")
    left = left.rstrip("→ ").strip()
    d.text((M, H - 40), left, font=sans("Medium", 19), fill=MUTED, anchor="lm")
    if arrow:  # font không có ký tự →, vẽ bằng nét
        x = M + d.textlength(left, font=sans("Medium", 19)) + 14
        d.line([(x, H - 40), (x + 26, H - 40)], fill=MUTED, width=3)
        d.polygon([(x + 32, H - 40), (x + 22, H - 47), (x + 22, H - 33)], fill=MUTED)
    d.text((W - M, H - 40), right or CONFIG["brand"]["handle"], font=sans("Bold", 19), fill=GREEN, anchor="rm")


def render_cover(path, series_name: str, level: str, part: int, total: int, title: str, headings: list[str]):
    img = Image.new("RGBA", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 700], fill=GREEN)
    d.text((M, 56), CONFIG["brand"]["name"], font=sans("Bold", 26), fill=LIME)
    d.text((W - M, 58), f"SERIES KIẾN THỨC · {level.upper()}", font=sans("SemiBold", 21), fill=SUB, anchor="ra")

    d.text((M, 150), series_name.upper(), font=sans("Bold", 30), fill=CREAM)
    pill = f"PHẦN {part}/{total}"
    pw = d.textlength(pill, font=sans("ExtraBold", 28)) + 44
    d.rounded_rectangle([M, 204, M + pw, 256], radius=26, fill=LIME)
    d.text((M + pw / 2, 230), pill, font=sans("ExtraBold", 28), fill=GREEN, anchor="mm")
    d.rounded_rectangle([M + pw + 24, 226, W - M, 234], radius=4, fill=TRACK)
    d.rounded_rectangle([M + pw + 24, 226, M + pw + 24 + (W - 2 * M - pw - 24) * part / total, 234], radius=4, fill=LIME)

    y = 300
    for line in wrap(d, title, sans("ExtraBold", 74), W - 2 * M, max_lines=4):
        d.text((M - 4, y), line, font=sans("ExtraBold", 74), fill=CREAM)
        y += 90

    # Mục lục các ảnh
    d.text((M, 744), "TRONG BÀI NÀY", font=sans("ExtraBold", 24), fill=GREEN)
    y = 800
    for i, h in enumerate(headings[:5]):
        d.text((M, y), f"{i + 1:02d}", font=sans("ExtraBold", 40), fill=GREEN)
        d.text((M + 90, y + 6), fit(d, h, sans("Bold", 32), W - 2 * M - 90), font=sans("Bold", 32), fill=INK)
        y += 100
        d.line([(M + 90, y - 24), (W - M, y - 24)], fill=DIVIDER, width=2)
    _footer(d, "Lướt sang để xem chi tiết  →")
    save(img, path)
    return path


def render_slide(path, series_name: str, part: int, total: int, idx: int, count: int, heading: str, body: str,
                 chart_img: Image.Image | None = None, caption: str = "", diagram: dict | None = None):
    img = Image.new("RGBA", (W, H), CREAM)
    d = ImageDraw.Draw(img)

    # --- Dải tiêu đề: số thứ tự to + tiêu đề ý
    d.rectangle([0, 0, W, 290], fill=GREEN)
    top = f"{series_name.upper()}  ·  PHẦN {part}/{total}" if total else series_name.upper()
    d.text((M, 40), top, font=sans("Bold", 21), fill=SUB)
    d.text((W - M, 40), CONFIG["brand"]["name"], font=sans("Bold", 21), fill=LIME, anchor="ra")
    d.text((M - 4, 84), f"{idx:02d}", font=sans("ExtraBold", 120), fill=LIME)
    lines = wrap(d, heading, sans("ExtraBold", 44), W - 2 * M - 200, max_lines=3)
    ty = 145 - (len(lines) - 1) * 27
    for line in lines:
        d.text((M + 200, ty), line, font=sans("ExtraBold", 44), fill=CREAM)
        ty += 54

    # --- Hình
    y = 320
    if chart_img is not None:
        cw = W - 2 * M
        ch = int(chart_img.height * cw / chart_img.width)
        d.rectangle([M - 2, y - 2, M + cw + 1, y + ch + 1], outline=DIVIDER, width=2)
        img.alpha_composite(chart_img.resize((cw, ch), Image.LANCZOS), (M, y))
        d = ImageDraw.Draw(img)
        if caption:
            d.text((M, y + ch + 12), fit(d, caption, sans("Medium", 17), W - 2 * M), font=sans("Medium", 17), fill=MUTED)
        y += ch + 56
    elif diagram:
        if diagram.get("type") == "checklist":
            bottom = 1250
        elif diagram.get("type") == "compare":
            n_items = max(len(diagram["left"].get("items", [])), len(diagram["right"].get("items", [])))
            bottom = y + 150 + min(4, n_items) * 76
        else:
            bottom = 960
        diagrams.draw(img, diagram, (M, y, W - M, bottom))
        d = ImageDraw.Draw(img)
        y = bottom + 36

    # --- Diễn giải: tự giảm cỡ chữ nếu nội dung dài để không bị cắt
    avail = H - 90 - y
    for size in ((28, 25, 23, 21) if (chart_img is not None or diagram) else (36, 32, 28)):
        lines = []
        for para in body.split("\n"):
            lines += wrap(d, para, sans("SemiBold", size), W - 2 * M - 24, max_lines=20) if para.strip() else []
        if len(lines) * (size + 14) <= avail:
            break
    lines = lines[:max(0, int(avail // (size + 14)))]
    if lines:
        d.rectangle([M, y + 4, M + 6, y + len(lines) * (size + 14) - 10], fill=GREEN)
        for line in lines:
            d.text((M + 26, y), line, font=sans("SemiBold", size), fill=INK)
            y += size + 14

    _footer(d, "Lướt tiếp  →" if idx < count else "Lưu bài để xem lại khi cần", f"{idx:02d} / {count:02d}")
    save(img, path)
    return path
