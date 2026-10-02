"""Bộ màu thương hiệu dùng chung cho mọi ảnh.

Chọn trong config.yaml → design.palette (hoặc biến môi trường DESIGN_PALETTE khi xem trước).
Mỗi bộ màu chỉ cần 3 màu gốc; các màu phụ (chữ phụ trên nền đậm, thẻ, đường kẻ...) được tự tính.
"""
import os

from src.config import CONFIG

PRESETS = {
    "reu-chanh":  {"name": "Xanh rêu · Chanh",   "primary": (18, 61, 47),  "accent": (214, 242, 92),  "bg": (245, 241, 232)},
    "navy-vang":  {"name": "Navy · Vàng gold",   "primary": (17, 32, 64),  "accent": (232, 184, 74),  "bg": (245, 243, 238)},
    "than-cam":   {"name": "Than chì · Cam",     "primary": (28, 28, 32),  "accent": (255, 138, 48),  "bg": (246, 245, 242)},
    "do-ruou":    {"name": "Đỏ rượu · Kem vàng", "primary": (88, 22, 36),  "accent": (240, 196, 120), "bg": (247, 242, 236)},
    "xanh-duong": {"name": "Xanh dương · Cyan",  "primary": (12, 74, 140), "accent": (120, 220, 255), "bg": (243, 246, 250)},
    # Thương hiệu CWG Markets: đỏ #FF0012 (lấy từ logo), nhấn trắng hồng, nền trắng xám
    "do-cwg":     {"name": "Đỏ CWG · Trắng",     "primary": (225, 0, 22),  "accent": (255, 236, 238), "bg": (246, 246, 247)},
}


def _mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def current_name() -> str:
    return os.environ.get("DESIGN_PALETTE") or (CONFIG.get("design") or {}).get("palette", "reu-chanh")


_p = PRESETS.get(current_name(), PRESETS["reu-chanh"])

PRIMARY = _p["primary"]                    # màu khối tiêu đề
ACCENT = _p["accent"]                      # màu nhấn: nhãn, số thứ tự, thanh tiến độ
BG = _p["bg"]                              # nền ảnh
SUB = _mix(PRIMARY, (255, 255, 255), 0.62)  # chữ phụ trên nền PRIMARY
TRACK = _mix(PRIMARY, (255, 255, 255), 0.18)  # thanh nền / ô phụ trên nền PRIMARY
CARD = _mix(BG, (0, 0, 0), 0.04)           # thẻ nội dung trên nền BG
DIVIDER = _mix(BG, (0, 0, 0), 0.12)        # đường kẻ trên nền BG
INK = (20, 20, 20)
MUTED = (110, 108, 100)
UP = (26, 127, 75)
DOWN = (196, 52, 40)

# Giao diện biểu đồ TradingView: light | dark
CHART_THEME = os.environ.get("DESIGN_CHART_THEME") or (CONFIG.get("design") or {}).get("chart_theme", "light")
