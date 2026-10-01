"""Bộ nhận diện (bản đề xuất) - đổi màu/font tại đây là toàn bộ ảnh đổi theo."""
from functools import lru_cache

from PIL import ImageFont

from src.config import ASSETS

SIZE = (1080, 1350)          # 4:5 - tỉ lệ chiếm nhiều diện tích nhất trên feed mobile
PAD = 56

COLORS = {
    "bg_top": (8, 13, 26),
    "bg_bottom": (16, 25, 46),
    "card": (20, 29, 51),
    "card_border": (36, 48, 77),
    "gold": (230, 180, 80),
    "gold_soft": (230, 180, 80, 40),
    "green": (38, 194, 129),
    "red": (240, 84, 79),
    "orange": (245, 165, 36),
    "text": (238, 242, 248),
    "muted": (140, 154, 181),
    "divider": (36, 48, 77),
}

IMPACT_COLOR = {"High": COLORS["red"], "Medium": COLORS["orange"], "Low": COLORS["muted"]}
TREND_COLOR = {"Tăng": COLORS["green"], "Giảm": COLORS["red"], "Đi ngang": COLORS["muted"]}


@lru_cache(maxsize=None)
def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(ASSETS / "fonts" / f"BeVietnamPro-{weight}.ttf"), size)
