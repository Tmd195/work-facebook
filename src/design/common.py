"""Hàm vẽ dùng chung cho mọi mẫu thiết kế."""
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from src.config import ASSETS

# 4:5 là tỉ lệ dọc lớn nhất Facebook hiển thị trọn vẹn trên feed mobile (ảnh cao hơn sẽ bị cắt).
SIZE_4X5 = (1080, 1350)
SIZE_1X1 = (1080, 1080)


@lru_cache(maxsize=None)
def sans(weight: str, size: int) -> ImageFont.FreeTypeFont:
    """Be Vietnam Pro: Regular / Medium / SemiBold / Bold / ExtraBold."""
    return ImageFont.truetype(str(ASSETS / "fonts" / f"BeVietnamPro-{weight}.ttf"), size)


@lru_cache(maxsize=None)
def serif(weight: int, size: int, italic: bool = False) -> ImageFont.FreeTypeFont:
    """Lora (có dấu tiếng Việt), weight 400-700."""
    name = "Lora-Italic-Variable.ttf" if italic else "Lora-Variable.ttf"
    f = ImageFont.truetype(str(ASSETS / "fonts" / name), size)
    f.set_variation_by_axes([weight])
    return f


def fmt_price(value: float, digits: int) -> str:
    return f"{value:,.{digits}f}" if value >= 1000 else f"{value:.{digits}f}"


def fit(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int) -> str:
    """Cắt chữ kèm '…' nếu dài quá max_w."""
    if draw.textlength(text, font=fnt) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=fnt) > max_w:
        text = text[:-1]
    return text.rstrip() + "…"


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int, max_lines: int = 3) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = fit(draw, lines[-1] + " …", fnt, max_w)
    return lines


def sparkline(img: Image.Image, values: list[float], box: tuple, color: tuple,
              width: int = 3, fill_alpha: int = 0, dot: bool = True):
    x0, y0, x1, y1 = box
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    pts = [(x0 + i * (x1 - x0) / (len(values) - 1), y1 - (v - lo) / span * (y1 - y0))
           for i, v in enumerate(values)]
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if fill_alpha:
        d.polygon(pts + [(x1, y1), (x0, y1)], fill=color[:3] + (fill_alpha,))
    d.line(pts, fill=color[:3] + (255,), width=width, joint="curve")
    if dot:
        lx, ly = pts[-1]
        d.ellipse([lx - 5, ly - 5, lx + 5, ly + 5], fill=color[:3] + (255,))
    img.alpha_composite(layer)


def key_levels(data: dict) -> tuple[float, float]:
    """Kháng cự / hỗ trợ gần nhất (swing), thiếu thì dùng R1 / S1."""
    res = data["resistance"][0] if data["resistance"] else data["r1"]
    sup = data["support"][0] if data["support"] else data["s1"]
    return res, sup


def pick_events(events: list[dict], limit: int) -> list[dict]:
    """Ưu tiên tin High, rồi xếp lại theo giờ."""
    ranked = sorted(events, key=lambda e: (e["impact"] != "High", e["datetime"]))[:limit]
    return sorted(ranked, key=lambda e: e["datetime"])


def save(img: Image.Image, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, "PNG", optimize=True)
