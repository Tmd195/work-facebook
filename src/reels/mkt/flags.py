"""Biểu tượng tròn của đồng tiền / hàng hoá, vẽ bằng code (không dùng ảnh/logo bên ngoài).

    icon("USD", 160) → ảnh RGBA tròn 160px
"""
import math
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

RED = (200, 16, 46)
BLUE = (1, 33, 105)
WHITE = (255, 255, 255)


def _star(d, cx, cy, r, col, n=5, inner=0.42, rot=-90):
    pts = []
    for k in range(n * 2):
        rr = r if k % 2 == 0 else r * inner
        a = math.radians(rot + k * 180 / n)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=col)


def _union_jack(d, x0, y0, w, h):
    d.rectangle([x0, y0, x0 + w, y0 + h], fill=BLUE)
    t = h * 0.2
    d.line([(x0, y0), (x0 + w, y0 + h)], fill=WHITE, width=int(t))
    d.line([(x0, y0 + h), (x0 + w, y0)], fill=WHITE, width=int(t))
    d.line([(x0, y0), (x0 + w, y0 + h)], fill=RED, width=int(t * 0.4))
    d.line([(x0, y0 + h), (x0 + w, y0)], fill=RED, width=int(t * 0.4))
    d.rectangle([x0 + w / 2 - t * 0.85, y0, x0 + w / 2 + t * 0.85, y0 + h], fill=WHITE)
    d.rectangle([x0, y0 + h / 2 - t * 0.85, x0 + w, y0 + h / 2 + t * 0.85], fill=WHITE)
    d.rectangle([x0 + w / 2 - t * 0.5, y0, x0 + w / 2 + t * 0.5, y0 + h], fill=RED)
    d.rectangle([x0, y0 + h / 2 - t * 0.5, x0 + w, y0 + h / 2 + t * 0.5], fill=RED)


def _draw(code: str, s: int) -> Image.Image:
    img = Image.new("RGB", (s, s), WHITE)
    d = ImageDraw.Draw(img)
    if code == "USD":
        for k in range(13):
            d.rectangle([0, k * s / 13, s, (k + 1) * s / 13], fill=RED if k % 2 == 0 else WHITE)
        d.rectangle([0, 0, s * 0.5, s * 7 / 13], fill=(10, 49, 97))
        for r in range(4):
            for c in range(4):
                d.ellipse([s * (0.06 + c * 0.11) - 3, s * (0.06 + r * 0.12) - 3,
                           s * (0.06 + c * 0.11) + 3, s * (0.06 + r * 0.12) + 3], fill=WHITE)
    elif code == "EUR":
        d.rectangle([0, 0, s, s], fill=(0, 51, 153))
        for k in range(12):
            a = math.radians(k * 30)
            _star(d, s / 2 + s * 0.3 * math.cos(a), s / 2 + s * 0.3 * math.sin(a), s * 0.055, (255, 204, 0))
    elif code == "GBP":
        _union_jack(d, -s * 0.25, 0, s * 1.5, s)
    elif code == "JPY":
        d.rectangle([0, 0, s, s], fill=WHITE)
        d.ellipse([s * 0.28, s * 0.28, s * 0.72, s * 0.72], fill=(188, 0, 45))
    elif code == "AUD":
        d.rectangle([0, 0, s, s], fill=BLUE)
        _union_jack(d, 0, 0, s * 0.55, s * 0.5)
        _star(d, s * 0.28, s * 0.74, s * 0.09, WHITE, n=7)
        for x, y in ((0.72, 0.3), (0.62, 0.52), (0.82, 0.48), (0.72, 0.78)):
            _star(d, s * x, s * y, s * 0.05, WHITE, n=7)
    elif code == "CAD":
        d.rectangle([0, 0, s, s], fill=WHITE)
        d.rectangle([0, 0, s * 0.25, s], fill=(216, 6, 33))
        d.rectangle([s * 0.75, 0, s, s], fill=(216, 6, 33))
        _star(d, s / 2, s * 0.5, s * 0.18, (216, 6, 33), n=11, inner=0.55)   # lá phong cách điệu
        d.rectangle([s * 0.485, s * 0.55, s * 0.515, s * 0.72], fill=(216, 6, 33))
    elif code == "CHF":
        d.rectangle([0, 0, s, s], fill=(218, 41, 28))
        d.rectangle([s * 0.42, s * 0.2, s * 0.58, s * 0.8], fill=WHITE)
        d.rectangle([s * 0.2, s * 0.42, s * 0.8, s * 0.58], fill=WHITE)
    elif code == "XAU":
        d.rectangle([0, 0, s, s], fill=(232, 205, 150))
        for (x, y) in ((0.24, 0.52), (0.5, 0.52), (0.37, 0.3)):
            bx, by, bw, bh = s * x, s * y, s * 0.26, s * 0.17
            d.polygon([(bx + bw * 0.12, by), (bx + bw * 0.88, by), (bx + bw, by + bh), (bx, by + bh)], fill=(170, 120, 40))
            d.polygon([(bx + bw * 0.2, by + bh * 0.15), (bx + bw * 0.8, by + bh * 0.15), (bx + bw * 0.88, by + bh * 0.85),
                       (bx + bw * 0.12, by + bh * 0.85)], fill=(214, 160, 60))
    elif code == "OIL":
        d.rectangle([0, 0, s, s], fill=(40, 44, 52))
        cx, cy = s / 2, s * 0.56
        d.ellipse([cx - s * 0.2, cy - s * 0.2, cx + s * 0.2, cy + s * 0.2], fill=(10, 10, 12))
        d.polygon([(cx, s * 0.14), (cx - s * 0.185, cy - s * 0.06), (cx + s * 0.185, cy - s * 0.06)], fill=(10, 10, 12))
        d.ellipse([cx - s * 0.11, cy - s * 0.02, cx - s * 0.04, cy + s * 0.1], fill=(90, 96, 110))
    elif code == "DXY":
        d.rectangle([0, 0, s, s], fill=(18, 60, 40))
        d.text((s / 2, s / 2), "$", fill=(120, 220, 150), anchor="mm",
               font=__import__("src.design.common", fromlist=["sans"]).sans("ExtraBold", int(s * 0.62)))
    else:
        d.rectangle([0, 0, s, s], fill=(60, 66, 80))
    return img


@lru_cache(maxsize=None)
def icon(code: str, size: int, ring: bool = True) -> Image.Image:
    """Biểu tượng tròn có viền trắng mảnh + bóng nhẹ."""
    big = size * 3
    face = _draw(code, big)
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, big - 1, big - 1], fill=255)
    out = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    out.paste(face, (0, 0), mask)
    if ring:
        ImageDraw.Draw(out).ellipse([2, 2, big - 3, big - 3], outline=(255, 255, 255, 220), width=max(3, big // 40))
    return out.resize((size, size), Image.LANCZOS)


def pair_codes(symbol: str) -> tuple[str, str]:
    """XAUUSD → (XAU, USD); WTI → (OIL, USD); DXY → (DXY, USD)."""
    if symbol == "WTI":
        return "OIL", "USD"
    if symbol == "DXY":
        return "DXY", "USD"
    return symbol[:3], symbol[3:6]
