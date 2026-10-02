"""Album ảnh cho Page thương hiệu (vd. CWG Markets & Partner): bìa + các ảnh nội dung + ảnh kêu gọi cuối.

Khổ 1080×1350 (4:5). Màu theo bộ màu của Job (design.palette), logo theo brand.logo / brand.icon.
"""
from functools import lru_cache

from PIL import Image, ImageDraw

from src.config import CONFIG, ROOT
from src.design.common import SIZE_4X5, fit, sans, save, wrap
from src.design.palette import ACCENT, BG, DIVIDER, INK, MUTED, PRIMARY, SUB

W, H = SIZE_4X5
M = 64
WHITE = (255, 255, 255)
SOFT = tuple(min(255, int(c * 0.08 + 255 * 0.92)) for c in PRIMARY)      # nền hồng rất nhạt cho ô nhấn


@lru_cache(maxsize=None)
def _logo(kind: str, height: int) -> Image.Image | None:
    rel = (CONFIG.get("brand") or {}).get(kind)
    if not rel or not (ROOT / rel).exists():
        return None
    im = Image.open(ROOT / rel).convert("RGBA")
    return im.resize((int(im.width * height / im.height), height), Image.LANCZOS)


def _arcs(img: Image.Image, box: tuple, center: tuple, radii: tuple):
    """Họa tiết vòng cung (gợi chữ C trong logo), chỉ vẽ trong vùng box."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    cx, cy = center
    for r in radii:
        ld.arc([cx - r, cy - r, cx + r, cy + r], 0, 360, fill=(255, 255, 255, 34), width=24)
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rectangle(box, fill=255)
    layer.putalpha(Image.composite(layer.getchannel("A"), Image.new("L", img.size, 0), mask))
    img.alpha_composite(layer)


def _header(img: Image.Image, d: ImageDraw.ImageDraw, on_red: bool):
    """Logo + tên thương hiệu ở góc trên."""
    icon = _logo("icon", 56)
    x = M
    if icon is not None:
        if on_red:                                   # icon đỏ trên nền đỏ → đặt trong ô trắng bo góc
            d.rounded_rectangle([M - 6, 38, M + icon.width + 6, 38 + 68], radius=16, fill=WHITE)
        img.alpha_composite(icon, (M, 44))
        x += icon.width + 22
    d.text((x, 72), CONFIG["brand"]["name"], font=sans("ExtraBold", 28), fill=WHITE if on_red else INK, anchor="lm")


def _footer(d: ImageDraw.ImageDraw, left: str, on_red: bool = False):
    col = SUB if on_red else MUTED
    d.text((M, H - 44), left, font=sans("SemiBold", 22), fill=col, anchor="lm")
    d.text((W - M, H - 44), CONFIG["brand"]["handle"], font=sans("Bold", 22), fill=WHITE if on_red else PRIMARY,
           anchor="rm")


def _arrow(d: ImageDraw.ImageDraw, x: float, y: float, color):
    d.line([(x, y), (x + 26, y)], fill=color, width=3)
    d.polygon([(x + 34, y), (x + 22, y - 8), (x + 22, y + 8)], fill=color)


def _pill(d, x, y, text, size, fill, color, pad=26) -> float:
    f = sans("ExtraBold", size)
    w = d.textlength(text, font=f) + pad * 2
    h = size * 1.9
    d.rounded_rectangle([x, y, x + w, y + h], radius=h / 2, fill=fill)
    d.text((x + w / 2, y + h / 2), text, font=f, fill=color, anchor="mm")
    return w


def render_cover(path, tag: str, title: str, subtitle: str, headings: list[str]):
    img = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 760], fill=PRIMARY)
    _arcs(img, (0, 0, W, 760), (W + 80, 420), (560, 470, 380))
    _header(img, d, True)
    d = ImageDraw.Draw(img)
    f = sans("ExtraBold", 92 if len(title) <= 40 else 76)
    tl = wrap(d, title.upper(), f, W - 2 * M - 40, max_lines=4)
    sl = wrap(d, subtitle, sans("Medium", 34), W - 2 * M - 80, max_lines=2)
    block = 70 + len(tl) * int(f.size * 1.1) + 24 + len(sl) * 46
    y = max(150, 150 + (700 - 150 - block) // 2)                  # canh giữa khối chữ trong vùng đỏ
    _pill(d, M, y, tag.upper(), 26, WHITE, PRIMARY)
    y += 82
    for line in tl:
        d.text((M - 3, y), line, font=f, fill=WHITE)
        y += int(f.size * 1.1)
    y += 24
    for line in sl:
        d.text((M, y), line, font=sans("Medium", 34), fill=ACCENT)
        y += 46

    d.text((M, 806), "TRONG BÀI NÀY", font=sans("ExtraBold", 24), fill=PRIMARY)
    y = 858
    for i, h in enumerate(headings[:4]):
        d.text((M, y), f"{i + 1:02d}", font=sans("ExtraBold", 40), fill=PRIMARY)
        d.text((M + 90, y + 6), fit(d, h, sans("Bold", 32), W - 2 * M - 90), font=sans("Bold", 32), fill=INK)
        y += 92
        d.line([(M + 90, y - 22), (W - M, y - 22)], fill=DIVIDER, width=2)
    _footer(d, "Lướt sang để xem chi tiết")
    _arrow(d, M + d.textlength("Lướt sang để xem chi tiết", font=sans("SemiBold", 22)) + 14, H - 44, MUTED)
    save(img, path)
    return path


def _check(d, x, y, size, color):
    d.ellipse([x, y, x + size, y + size], fill=color)
    d.line([(x + size * 0.27, y + size * 0.52), (x + size * 0.44, y + size * 0.69), (x + size * 0.74, y + size * 0.33)],
           fill=WHITE, width=max(3, size // 9))


def render_slide(path, idx: int, total: int, heading: str, body: str, points: list[str] | None = None,
                 highlight: str = ""):
    img = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 300], fill=PRIMARY)
    _header(img, d, True)
    d = ImageDraw.Draw(img)
    d.text((W - M, 72), f"{idx:02d}/{total:02d}", font=sans("Bold", 24), fill=ACCENT, anchor="rm")
    d.text((M - 4, 128), f"{idx:02d}", font=sans("ExtraBold", 120), fill=WHITE)
    lines = wrap(d, heading, sans("ExtraBold", 46), W - 2 * M - 190, max_lines=3)
    ty = 190 - len(lines) * 28
    for line in lines:
        d.text((M + 190, ty), line, font=sans("ExtraBold", 46), fill=WHITE)
        ty += 56

    # thân bài: tự thu chữ nếu dài
    y = 350
    bottom = H - 110
    pts = [p for p in (points or []) if p.strip()][:5]
    for size in (42, 39, 36, 33, 30, 28):
        f = sans("Medium", size)
        body_lines = wrap(d, body, f, W - 2 * M, max_lines=12) if body else []
        need = len(body_lines) * size * 1.5 + len(pts) * size * 2.6 + (220 if highlight else 0)
        if y + need < bottom:
            break
    y += max(0, int((bottom - y - need) * 0.35))                  # còn trống thì đẩy nội dung xuống cho cân
    for line in body_lines:
        d.text((M, y), line, font=f, fill=INK)
        y += int(size * 1.5)
    if pts:
        y += 18
        for p in pts:
            pl = wrap(d, p, sans("SemiBold", size), W - 2 * M - 70, max_lines=2)
            _check(d, M, y + 4, int(size * 1.15), PRIMARY)
            for k, line in enumerate(pl):
                d.text((M + 70, y + k * size * 1.35), line, font=sans("SemiBold", size), fill=INK)
            y += int(len(pl) * size * 1.35 + size * 0.9)
    if highlight:
        y += 20
        hl = wrap(d, highlight, sans("Bold", 34), W - 2 * M - 80, max_lines=3)
        bh = len(hl) * 48 + 56
        d.rounded_rectangle([M, y, W - M, y + bh], radius=22, fill=SOFT)
        d.rectangle([M, y, M + 10, y + bh], fill=PRIMARY)
        for k, line in enumerate(hl):
            d.text((M + 44, y + 28 + k * 48), line, font=sans("Bold", 34), fill=PRIMARY)
    if idx < total:
        _footer(d, "Lướt tiếp")
        _arrow(d, M + d.textlength("Lướt tiếp", font=sans("SemiBold", 22)) + 14, H - 44, MUTED)
    else:
        _footer(d, "")
    save(img, path)
    return path


def _icon_clock(d, x, y, s, col):
    d.ellipse([x, y, x + s, y + s], outline=col, width=max(3, s // 10))
    c = (x + s / 2, y + s / 2)
    d.line([c, (c[0], y + s * 0.22)], fill=col, width=max(3, s // 10))
    d.line([c, (x + s * 0.74, c[1])], fill=col, width=max(3, s // 10))


def _icon_person(d, x, y, s, col):
    d.ellipse([x + s * 0.3, y, x + s * 0.7, y + s * 0.4], fill=col)
    d.pieslice([x + s * 0.08, y + s * 0.46, x + s * 0.92, y + s * 1.3], 180, 360, fill=col)


def _icon_bars(d, x, y, s, col):
    for k, hh in enumerate((0.45, 0.7, 1.0)):
        bx = x + k * s * 0.36
        d.rectangle([bx, y + s * (1 - hh), bx + s * 0.24, y + s], fill=col)


def _icon_shield(d, x, y, s, col):
    d.polygon([(x + s / 2, y), (x + s, y + s * 0.18), (x + s * 0.92, y + s * 0.62), (x + s / 2, y + s),
               (x + s * 0.08, y + s * 0.62), (x, y + s * 0.18)], fill=col)
    d.line([(x + s * 0.3, y + s * 0.5), (x + s * 0.45, y + s * 0.65), (x + s * 0.72, y + s * 0.35)],
           fill=WHITE, width=max(3, s // 9))


def render_cta(path, facts: dict, cta: str):
    """Ảnh cuối mỗi album: thẻ 'Chính sách đối tác IB' – nền đỏ, các thẻ trắng.

    facts: {"spread": "85%", "bonus": "5%", "example": ("XAUUSD spread 5.x pip", "$50/lot"),
            "terms": [(icon, câu hỏi, trả lời)], "licenses": [(tên, nước, số)], "score": "8.25"}
    """
    img = Image.new("RGBA", (W, H), PRIMARY)
    _arcs(img, (0, 0, W, H), (W + 40, 260), (520, 430, 340))
    d = ImageDraw.Draw(img)
    _header(img, d, True)
    d = ImageDraw.Draw(img)
    d.text((M, 146), "CHÍNH SÁCH", font=sans("ExtraBold", 38), fill=ACCENT)
    d.text((M - 3, 206), "ĐỐI TÁC IB", font=sans("ExtraBold", 90), fill=WHITE)

    # 2 thẻ số liệu
    top, th = 322, 210
    lw = int((W - 2 * M) * 0.58)
    d.rounded_rectangle([M, top, M + lw, top + th], radius=28, fill=WHITE)
    d.text((M + 34, top + 30), "HOA HỒNG", font=sans("ExtraBold", 26), fill=MUTED)
    big = sans("ExtraBold", 120)
    d.text((M + 28, top + 182), facts["spread"], font=big, fill=PRIMARY, anchor="ls")
    d.text((M + 40 + d.textlength(facts["spread"], font=big), top + 176), "spread", font=sans("ExtraBold", 40),
           fill=PRIMARY, anchor="ls")
    rx = M + lw + 20
    d.rounded_rectangle([rx, top, W - M, top + th], radius=28, outline=WHITE, width=4)
    d.text((rx + 30, top + 30), "THƯỞNG DOANH SỐ", font=sans("ExtraBold", 22), fill=ACCENT)
    d.text((rx + 30, top + 66), "tối thiểu", font=sans("SemiBold", 26), fill=WHITE)
    d.text((rx + 26, top + 182), facts["bonus"], font=sans("ExtraBold", 92), fill=WHITE, anchor="ls")

    # dải ví dụ
    ey = top + th + 22
    d.rounded_rectangle([M, ey, W - M, ey + 74], radius=37, fill=(150, 0, 14))
    lab = "VÍ DỤ"
    d.rounded_rectangle([M + 12, ey + 12, M + 24 + d.textlength(lab, font=sans("ExtraBold", 22)) + 24, ey + 62],
                        radius=25, fill=WHITE)
    d.text((M + 36, ey + 37), lab, font=sans("ExtraBold", 22), fill=PRIMARY, anchor="lm")
    left, right = facts["example"]
    f = sans("Bold", 30)
    x = M + 150
    d.text((x, ey + 37), left, font=f, fill=WHITE, anchor="lm")
    x += d.textlength(left, font=f) + 22
    _arrow(d, x, ey + 37, WHITE)
    d.text((x + 52, ey + 37), "IB nhận " + right, font=sans("ExtraBold", 30), fill=WHITE, anchor="lm")

    # 3 điều kiện
    y = ey + 104
    icons = {"person": _icon_person, "clock": _icon_clock, "bars": _icon_bars}
    for icon, q, a in facts["terms"][:3]:
        d.rounded_rectangle([M, y, W - M, y + 104], radius=22, fill=WHITE)
        d.ellipse([M + 22, y + 20, M + 86, y + 84], fill=SOFT)
        icons.get(icon, _icon_person)(d, M + 36, y + 34, 36, PRIMARY)
        size = 31                                          # câu dài thì thu chữ cho vừa thẻ
        while size > 22 and d.textlength(a, font=sans("ExtraBold", size)) > W - 2 * M - 140:
            size -= 1
        if q:
            d.text((M + 110, y + 32), q, font=sans("Medium", 24), fill=MUTED, anchor="lm")
            d.text((M + 110, y + 70), a, font=sans("ExtraBold", size), fill=INK, anchor="lm")
        else:                                              # không có câu hỏi: 1 dòng giữa thẻ
            d.text((M + 110, y + 52), a, font=sans("ExtraBold", size), fill=INK, anchor="lm")
        y += 118

    # pháp lý
    y += 6
    _icon_shield(d, M, y, 34, WHITE)
    d.text((M + 48, y + 17), "PHÁP LÝ TẬP ĐOÀN CWG MARKETS", font=sans("ExtraBold", 24), fill=WHITE, anchor="lm")
    y += 50
    n = len(facts["licenses"]) + 1
    cw = (W - 2 * M - (n - 1) * 12) / n
    for k, (name, country, num) in enumerate(facts["licenses"]):
        x0 = M + k * (cw + 12)
        d.rounded_rectangle([x0, y, x0 + cw, y + 96], radius=18, fill=WHITE)
        d.text((x0 + 20, y + 30), name, font=sans("ExtraBold", 30), fill=INK, anchor="lm")
        d.text((x0 + 26 + d.textlength(name, font=sans("ExtraBold", 30)), y + 32), country, font=sans("Medium", 18),
               fill=MUTED, anchor="lm")
        d.text((x0 + 20, y + 70), num, font=sans("SemiBold", 21), fill=PRIMARY, anchor="lm")
    x0 = M + (n - 1) * (cw + 12)
    d.rounded_rectangle([x0, y, x0 + cw, y + 96], radius=18, fill=(150, 0, 14))
    d.text((x0 + 20, y + 36), facts["score"], font=sans("ExtraBold", 38), fill=WHITE, anchor="lm")
    d.text((x0 + 26 + d.textlength(facts["score"], font=sans("ExtraBold", 38)), y + 42), "/10", font=sans("Bold", 20),
           fill=ACCENT, anchor="lm")
    d.text((x0 + 20, y + 74), "Điểm WikiFX", font=sans("SemiBold", 20), fill=ACCENT, anchor="lm")

    # nút
    label = cta.replace("📩", "").strip().upper()
    f = sans("ExtraBold", 32)
    bw = d.textlength(label, font=f) + 96
    by = H - 166
    d.rounded_rectangle([(W - bw) / 2, by, (W + bw) / 2, by + 84], radius=42, fill=WHITE)
    d.text((W / 2, by + 42), label, font=f, fill=PRIMARY, anchor="mm")
    d.text((W / 2, H - 46), "Giao dịch CFD/Forex có rủi ro cao, bạn có thể mất toàn bộ vốn · Mỗi pháp nhân được cấp phép tại "
           "khu vực tương ứng", font=sans("Medium", 17), fill=SUB, anchor="mm")
    save(img, path)
    return path
