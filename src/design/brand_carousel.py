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

# Phương án màu cho thẻ chính sách: "red" (nền đỏ), "light" (nền trắng, đỏ chỉ ở điểm nhấn), "dark" (nền than, điểm đỏ)
CTA_THEMES = {
    "light": {"bg": (248, 248, 249), "title": INK, "kicker": PRIMARY, "brand": INK,
              "tile1": PRIMARY, "tile1_label": (255, 214, 218), "tile1_text": WHITE, "tile1_sub": WHITE,
              "tile2_line": PRIMARY, "tile2_label": PRIMARY, "tile2_sub": MUTED, "tile2_text": PRIMARY,
              "strip": (253, 234, 236), "strip_text": INK, "strip_strong": PRIMARY, "strip_tag": PRIMARY, "strip_tag_text": WHITE,
              "card": WHITE, "card_line": (232, 232, 235), "q": MUTED, "a": INK, "icon_bg": (253, 234, 236), "icon": PRIMARY,
              "legal": INK, "lic_card": WHITE, "lic_name": INK, "lic_num": PRIMARY, "score": (28, 28, 32), "score_sub": (200, 200, 205),
              "btn": PRIMARY, "btn_text": WHITE, "foot": MUTED, "deco": None},
    "dark": {"bg": (22, 22, 26), "title": WHITE, "kicker": (255, 90, 100), "brand": WHITE,
             "tile1": PRIMARY, "tile1_label": (255, 214, 218), "tile1_text": WHITE, "tile1_sub": WHITE,
             "tile2_line": (255, 90, 100), "tile2_label": (255, 90, 100), "tile2_sub": (170, 170, 178), "tile2_text": WHITE,
             "strip": (40, 40, 46), "strip_text": (230, 230, 235), "strip_strong": (255, 90, 100), "strip_tag": PRIMARY,
             "strip_tag_text": WHITE, "card": (36, 36, 42), "card_line": (52, 52, 60), "q": (160, 160, 170), "a": WHITE,
             "icon_bg": (60, 22, 28), "icon": (255, 90, 100), "legal": WHITE, "lic_card": (36, 36, 42), "lic_name": WHITE,
             "lic_num": (255, 90, 100), "score": PRIMARY, "score_sub": (255, 214, 218), "btn": PRIMARY, "btn_text": WHITE,
             "foot": (130, 130, 140), "deco": None},
}


def render_cta_theme(path, facts: dict, cta: str, theme: str = "light"):
    """Thẻ chính sách theo phương án màu dịu mắt (đỏ chỉ dùng cho 1 điểm nhấn chính + nút)."""
    T = CTA_THEMES[theme]
    img = Image.new("RGBA", (W, H), T["bg"])
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=PRIMARY)
    icon = _logo("icon", 56)
    if icon is not None:
        img.alpha_composite(icon, (M, 44))
    d.text((M + 78, 72), CONFIG["brand"]["name"], font=sans("ExtraBold", 28), fill=T["brand"], anchor="lm")
    d.text((M, 146), "CHÍNH SÁCH", font=sans("ExtraBold", 36), fill=T["kicker"])
    d.text((M - 3, 202), "ĐỐI TÁC IB", font=sans("ExtraBold", 88), fill=T["title"])

    top, th = 320, 210
    lw = int((W - 2 * M) * 0.58)
    d.rounded_rectangle([M, top, M + lw, top + th], radius=28, fill=T["tile1"])
    d.text((M + 34, top + 30), "HOA HỒNG", font=sans("ExtraBold", 26), fill=T["tile1_label"])
    big = sans("ExtraBold", 120)
    d.text((M + 28, top + 182), facts["spread"], font=big, fill=T["tile1_text"], anchor="ls")
    d.text((M + 40 + d.textlength(facts["spread"], font=big), top + 176), "spread", font=sans("ExtraBold", 40),
           fill=T["tile1_sub"], anchor="ls")
    rx = M + lw + 20
    d.rounded_rectangle([rx, top, W - M, top + th], radius=28, fill=T["card"], outline=T["tile2_line"], width=3)
    d.text((rx + 30, top + 30), "THƯỞNG DOANH SỐ", font=sans("ExtraBold", 22), fill=T["tile2_label"])
    d.text((rx + 30, top + 66), "tối thiểu", font=sans("SemiBold", 26), fill=T["tile2_sub"])
    d.text((rx + 26, top + 182), facts["bonus"], font=sans("ExtraBold", 92), fill=T["tile2_text"], anchor="ls")

    ey = top + th + 22
    d.rounded_rectangle([M, ey, W - M, ey + 74], radius=37, fill=T["strip"])
    lab = "VÍ DỤ"
    d.rounded_rectangle([M + 12, ey + 12, M + 48 + d.textlength(lab, font=sans("ExtraBold", 22)), ey + 62],
                        radius=25, fill=T["strip_tag"])
    d.text((M + 36, ey + 37), lab, font=sans("ExtraBold", 22), fill=T["strip_tag_text"], anchor="lm")
    left, right = facts["example"]
    f = sans("Bold", 30)
    x = M + 150
    d.text((x, ey + 37), left, font=f, fill=T["strip_text"], anchor="lm")
    x += d.textlength(left, font=f) + 22
    _arrow(d, x, ey + 37, T["strip_text"])
    d.text((x + 52, ey + 37), "IB nhận " + right, font=sans("ExtraBold", 30), fill=T["strip_strong"], anchor="lm")

    y = ey + 104
    icons = {"person": _icon_person, "clock": _icon_clock, "bars": _icon_bars}
    for icon_name, q, a in facts["terms"][:3]:
        d.rounded_rectangle([M, y, W - M, y + 104], radius=22, fill=T["card"], outline=T["card_line"], width=2)
        d.ellipse([M + 22, y + 20, M + 86, y + 84], fill=T["icon_bg"])
        icons.get(icon_name, _icon_person)(d, M + 36, y + 34, 36, T["icon"])
        size = 31
        while size > 22 and d.textlength(a, font=sans("ExtraBold", size)) > W - 2 * M - 140:
            size -= 1
        d.text((M + 110, y + 32), q, font=sans("Medium", 24), fill=T["q"], anchor="lm")
        d.text((M + 110, y + 70), a, font=sans("ExtraBold", size), fill=T["a"], anchor="lm")
        y += 118

    y += 6
    _icon_shield(d, M, y, 34, PRIMARY)
    d.text((M + 48, y + 17), "PHÁP LÝ TẬP ĐOÀN CWG MARKETS", font=sans("ExtraBold", 24), fill=T["legal"], anchor="lm")
    y += 50
    n = len(facts["licenses"]) + 1
    cw = (W - 2 * M - (n - 1) * 12) / n
    for k, (name, country, num) in enumerate(facts["licenses"]):
        x0 = M + k * (cw + 12)
        d.rounded_rectangle([x0, y, x0 + cw, y + 96], radius=18, fill=T["lic_card"], outline=T["card_line"], width=2)
        d.text((x0 + 20, y + 30), name, font=sans("ExtraBold", 30), fill=T["lic_name"], anchor="lm")
        d.text((x0 + 26 + d.textlength(name, font=sans("ExtraBold", 30)), y + 32), country, font=sans("Medium", 18),
               fill=T["q"], anchor="lm")
        d.text((x0 + 20, y + 70), num, font=sans("SemiBold", 21), fill=T["lic_num"], anchor="lm")
    x0 = M + (n - 1) * (cw + 12)
    d.rounded_rectangle([x0, y, x0 + cw, y + 96], radius=18, fill=T["score"])
    d.text((x0 + 20, y + 36), facts["score"], font=sans("ExtraBold", 38), fill=WHITE, anchor="lm")
    d.text((x0 + 26 + d.textlength(facts["score"], font=sans("ExtraBold", 38)), y + 42), "/10", font=sans("Bold", 20),
           fill=T["score_sub"], anchor="lm")
    d.text((x0 + 20, y + 74), "Điểm WikiFX", font=sans("SemiBold", 20), fill=T["score_sub"], anchor="lm")

    label = cta.replace("📩", "").strip().upper()
    f = sans("ExtraBold", 32)
    bw = d.textlength(label, font=f) + 96
    by = H - 166
    d.rounded_rectangle([(W - bw) / 2, by, (W + bw) / 2, by + 84], radius=42, fill=T["btn"])
    d.text((W / 2, by + 42), label, font=f, fill=T["btn_text"], anchor="mm")
    d.text((W / 2, H - 46), "Giao dịch CFD/Forex có rủi ro cao, bạn có thể mất toàn bộ vốn · Mỗi pháp nhân được cấp phép tại "
           "khu vực tương ứng", font=sans("Medium", 17), fill=T["foot"], anchor="mm")
    save(img, path)
    return path


def render_ad(path, person: Image.Image | None, hero: str = "$50", unit: str = "/lot",
              sub: str = "Vàng XAUUSD · rebate nảy ngay khi đóng lệnh",
              chips: tuple = ("85% spread", "Thưởng tối thiểu 5%"),
              legal: str = "Tập đoàn CWG Markets · FCA · FSCA · VFSC · WikiFX 8.25/10",
              button: str = "Nhắn tin nhận chính sách"):
    """Ảnh quảng cáo ít chữ: 1 thông điệp chính ($50/lot) + gương mặt minh họa. Chi tiết để ở caption / ảnh sau."""
    img = Image.new("RGBA", (W, H), (248, 248, 249))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=PRIMARY)
    icon = _logo("icon", 56)
    if icon is not None:
        img.alpha_composite(icon, (M, 44))
    d.text((M + 78, 72), CONFIG["brand"]["name"], font=sans("ExtraBold", 28), fill=INK, anchor="lm")

    # ảnh người minh họa bên phải: khung bo cong + khối đỏ lệch phía sau
    px0, py0, pw, ph = 560, 170, 456, 760
    d.rounded_rectangle([px0 + 26, py0 + 26, px0 + pw + 26, py0 + ph + 26], radius=60, fill=PRIMARY)
    if person is not None:
        from PIL import ImageOps
        ph_img = ImageOps.fit(person.convert("RGBA"), (pw, ph), Image.LANCZOS, centering=(0.5, 0.2))
        mask = Image.new("L", (pw, ph), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw - 1, ph - 1], radius=60, fill=255)
        img.paste(ph_img, (px0, py0), mask)
    else:
        d.rounded_rectangle([px0, py0, px0 + pw, py0 + ph], radius=60, fill=(225, 225, 230))
    d = ImageDraw.Draw(img)
    d.text((px0 + pw - 16, py0 + ph - 18), "Hình ảnh minh họa", font=sans("Medium", 16), fill=(235, 235, 240), anchor="rb")

    # thông điệp chính bên trái
    _pill(d, M, 200, "CWG TUYỂN ĐỐI TÁC IB", 22, PRIMARY, WHITE, pad=22)
    d.text((M, 300), "IB nhận", font=sans("ExtraBold", 64), fill=INK)
    big = sans("ExtraBold", 210)
    d.text((M - 10, 600), hero, font=big, fill=PRIMARY, anchor="ls")
    d.text((M + 6, 690), unit, font=sans("ExtraBold", 80), fill=PRIMARY, anchor="ls")
    y = 730
    for line in wrap(d, sub, sans("SemiBold", 32), 470, max_lines=3):
        d.text((M, y), line, font=sans("SemiBold", 32), fill=(70, 70, 76))
        y += 44

    # 2 chip phụ
    cy = 1000
    x = M
    for c in chips[:2]:
        f = sans("ExtraBold", 30)
        w = d.textlength(c, font=f) + 56
        d.rounded_rectangle([x, cy, x + w, cy + 66], radius=33, fill=WHITE, outline=(232, 232, 235), width=2)
        d.text((x + w / 2, cy + 33), c, font=f, fill=INK, anchor="mm")
        x += w + 16

    # nút + pháp lý + cảnh báo
    f = sans("ExtraBold", 34)
    label = button.upper()
    bw = d.textlength(label, font=f) + 110
    by = 1110
    d.rounded_rectangle([M, by, M + bw, by + 90], radius=45, fill=PRIMARY)
    d.text((M + bw / 2, by + 45), label, font=f, fill=WHITE, anchor="mm")
    _icon_shield(d, M, 1236, 28, PRIMARY)
    d.text((M + 40, 1250), legal, font=sans("SemiBold", 22), fill=INK, anchor="lm")
    d.text((M, H - 40), "Giao dịch CFD/Forex có rủi ro cao, bạn có thể mất toàn bộ vốn. Mỗi pháp nhân được cấp phép tại khu vực "
           "tương ứng.", font=sans("Medium", 16), fill=MUTED, anchor="lm")
    save(img, path)
    return path


# ------------------------------------------------------------------ ảnh quảng cáo có chiều sâu (bản 2)

def _shadow(img: Image.Image, box, radius: int, blur: int = 18, offset=(0, 14), alpha: int = 70):
    from PIL import ImageFilter
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    x0, y0, x1, y1 = box
    ImageDraw.Draw(layer).rounded_rectangle([x0 + offset[0], y0 + offset[1], x1 + offset[0], y1 + offset[1]],
                                            radius=radius, fill=(20, 10, 12, alpha))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def _glow(img: Image.Image, center, r: int, color, alpha: int = 90):
    from PIL import ImageFilter
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    cx, cy = center
    ImageDraw.Draw(layer).ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (alpha,))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(r // 2)))


def _bg_candles(img: Image.Image, box, color, alpha: int = 26, seed: int = 5):
    import random
    rnd = random.Random(seed)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = box
    p = (y0 + y1) / 2
    x = x0
    while x < x1:
        o = p
        p += rnd.uniform(-22, 26)
        p = min(y1 - 20, max(y0 + 20, p))
        hi, lo = min(o, p) - rnd.uniform(6, 20), max(o, p) + rnd.uniform(6, 20)
        d.line([(x + 7, hi), (x + 7, lo)], fill=color + (alpha,), width=2)
        d.rectangle([x, min(o, p), x + 14, max(o, p) + 2], fill=color + (alpha,))
        x += 24
    img.alpha_composite(layer)


def _arch_photo(img: Image.Image, photo: Image.Image, box, focus=(0.5, 0.25)):
    """Ảnh người trong khung vòm (bo tròn phía trên) + bóng đổ + viền đỏ lệch phía sau."""
    from PIL import ImageOps
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    _shadow(img, box, 40, blur=26, offset=(0, 22), alpha=90)
    pic = ImageOps.fit(photo.convert("RGBA"), (w, h), Image.LANCZOS, centering=focus)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([0, 0, w - 1, w - 1], fill=255)                      # vòm phía trên
    md.rounded_rectangle([0, w // 2, w - 1, h - 1], radius=40, fill=255)
    img.paste(pic, (x0, y0), mask)


def _float_card(img, x, y, title: str, sub: str, dot=(34, 176, 92), w: int | None = None):
    d = ImageDraw.Draw(img)
    ft, fs = sans("ExtraBold", 27), sans("Medium", 21)
    w = w or int(max(d.textlength(title, font=ft), d.textlength(sub, font=fs)) + 92)
    h = 96
    _shadow(img, (x, y, x + w, y + h), 22, blur=16, offset=(0, 10), alpha=60)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x, y, x + w, y + h], radius=22, fill=WHITE)
    d.ellipse([x + 26, y + 26, x + 46, y + 46], fill=dot)
    d.text((x + 62, y + 34), title, font=ft, fill=INK, anchor="lm")
    d.text((x + 28, y + 70), sub, font=fs, fill=MUTED, anchor="lm")


def _license_strip(img, y, licenses, score):
    d = ImageDraw.Draw(img)
    n = len(licenses) + 1
    cw = (W - 2 * M - (n - 1) * 10) / n
    _shadow(img, (M, y, W - M, y + 84), 20, blur=14, offset=(0, 8), alpha=35)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([M, y, W - M, y + 84], radius=20, fill=WHITE)
    for k, (name, country, num) in enumerate(licenses):
        x0 = M + k * (cw + 10)
        d.text((x0 + 22, y + 28), name, font=sans("ExtraBold", 26), fill=INK, anchor="lm")
        d.text((x0 + 28 + d.textlength(name, font=sans("ExtraBold", 26)), y + 30), country, font=sans("Medium", 16),
               fill=MUTED, anchor="lm")
        d.text((x0 + 22, y + 60), num, font=sans("SemiBold", 19), fill=PRIMARY, anchor="lm")
        if k:
            d.line([(x0 - 5, y + 18), (x0 - 5, y + 66)], fill=(232, 232, 236), width=2)
    x0 = M + (n - 1) * (cw + 10)
    d.rounded_rectangle([x0, y, W - M, y + 84], radius=20, fill=PRIMARY)
    d.text((x0 + 22, y + 32), score, font=sans("ExtraBold", 34), fill=WHITE, anchor="lm")
    d.text((x0 + 28 + d.textlength(score, font=sans("ExtraBold", 34)), y + 37), "/10", font=sans("Bold", 18),
           fill=ACCENT, anchor="lm")
    d.text((x0 + 22, y + 62), "Điểm WikiFX", font=sans("SemiBold", 18), fill=ACCENT, anchor="lm")


def render_ad2(path, photo: Image.Image, layout: str = "right", hook=("Mỗi lot khách đánh,", "bạn nhận bao nhiêu?"),
               hero="$50", unit="/lot", hero_sub="Vàng XAUUSD · spread 5.x pip",
               chips=("Thưởng doanh số ≥5%", "Không yêu cầu doanh số"),
               float1=("Rebate nảy ngay", "khi khách đóng lệnh"), float2="85% spread",
               licenses=(("FCA", "Anh", "FRN 785129"), ("FSCA", "Nam Phi", "FSP 54031"), ("VFSC", "Vanuatu", "Số ĐK 41694")),
               score="8.25", button="Nhắn tin nhận chính sách", focus=(0.5, 0.22)):
    """layout: right (ảnh vòm bên phải) | hero (ảnh phủ nền phía sau, chữ đè bên trái)."""
    img = Image.new("RGBA", (W, H), (250, 250, 251))
    d = ImageDraw.Draw(img)
    for yy in range(H):                                  # nền chuyển nhẹ trắng → xám ấm
        t = yy / H
        d.line([(0, yy), (W, yy)], fill=(int(252 - 10 * t), int(252 - 11 * t), int(253 - 9 * t), 255))

    if layout == "hero":
        from PIL import ImageOps
        pic = ImageOps.fit(photo.convert("RGBA"), (700, 1060), Image.LANCZOS, centering=focus)
        import numpy as np
        hw, hh = pic.size
        fx = np.clip(np.arange(hw) / 300, 0, 1) ** 1.6                  # mờ dần sang trái
        fy = np.minimum(np.clip(np.arange(hh) / 140, 0, 1), np.clip((hh - 1 - np.arange(hh)) / 220, 0, 1)) ** 1.4
        fade = Image.fromarray((np.outer(fy, fx) * 255).astype("uint8"), "L")
        pic.putalpha(Image.composite(fade, Image.new("L", pic.size, 0), pic.getchannel("A")))
        _glow(img, (820, 470), 300, PRIMARY, 60)
        img.alpha_composite(pic, (W - pic.width, 60))
        photo_box = (W - pic.width + 260, 60, W, 60 + pic.height)
    else:
        _glow(img, (800, 520), 330, PRIMARY, 70)
        _bg_candles(img, (40, 860, 560, 1020), PRIMARY, 22)
        photo_box = (548, 176, 1010, 940)
        _arch_photo(img, photo, photo_box, focus)

    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=PRIMARY)
    icon = _logo("icon", 56)
    if icon is not None:
        img.alpha_composite(icon, (M, 40))
    d.text((M + 76, 68), "CWG", font=sans("ExtraBold", 40), fill=PRIMARY, anchor="lm")
    sx = M + 92 + d.textlength("CWG", font=sans("ExtraBold", 40))
    d.line([(sx, 48), (sx, 88)], fill=(210, 210, 214), width=2)
    d.text((sx + 18, 56), "CHƯƠNG TRÌNH", font=sans("Bold", 20), fill=INK, anchor="lm")
    d.text((sx + 18, 82), "ĐỐI TÁC IB", font=sans("Bold", 20), fill=INK, anchor="lm")

    # tiêu đề câu hỏi
    y = 170
    for k, line in enumerate(hook):
        d.text((M, y), line, font=sans("ExtraBold", 50), fill=INK if k == 0 else PRIMARY)
        y += 64

    # thẻ $50/lot – điểm nhấn chính
    hx0, hy0, hx1, hy1 = M, 330, 520, 640
    _shadow(img, (hx0, hy0, hx1, hy1), 34, blur=24, offset=(0, 18), alpha=110)
    card = Image.new("RGBA", (hx1 - hx0, hy1 - hy0), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    for xx in range(card.width):                         # đỏ chuyển nhẹ
        t = xx / card.width
        cd.line([(xx, 0), (xx, card.height)], fill=(int(236 - 40 * t), int(16 - 10 * t), int(36 - 14 * t), 255))
    m = Image.new("L", card.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, card.width - 1, card.height - 1], radius=34, fill=255)
    img.paste(card, (hx0, hy0), m)
    d = ImageDraw.Draw(img)
    d.text((hx0 + 36, hy0 + 44), "IB NHẬN", font=sans("ExtraBold", 28), fill=(255, 210, 214), anchor="lm")
    big = sans("ExtraBold", 150)
    d.text((hx0 + 26, hy0 + 222), hero, font=big, fill=WHITE, anchor="ls")
    d.text((hx0 + 38 + d.textlength(hero, font=big), hy0 + 214), unit, font=sans("ExtraBold", 50), fill=WHITE,
           anchor="ls")
    d.line([(hx0 + 36, hy0 + 246), (hx1 - 36, hy0 + 246)], fill=(255, 255, 255, 90), width=2)
    d.text((hx0 + 36, hy0 + 278), hero_sub, font=sans("SemiBold", 25), fill=(255, 225, 228), anchor="lm")

    # chip phụ
    y = 676
    for c in chips[:2]:
        _check(d, M, y + 4, 36, PRIMARY)
        d.text((M + 54, y + 22), c, font=sans("Bold", 30), fill=INK, anchor="lm")
        y += 58

    # thẻ nổi trên ảnh
    px0, py0, px1, py1 = photo_box
    if layout == "right":
        _float_card(img, px1 - 290, py1 - 130, float1[0], float1[1])
    else:
        _float_card(img, W - 40 - 330, py1 - 300, float1[0], float1[1], w=320)
    d = ImageDraw.Draw(img)
    f = sans("ExtraBold", 30)
    pw = d.textlength(float2, font=f) + 60
    fx, fy = min(px1, W - 40) - pw - 10, py0 + 60 if layout == "right" else py0 + 120
    _shadow(img, (fx, fy, fx + pw, fy + 64), 32, blur=14, offset=(0, 8), alpha=70)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([fx, fy, fx + pw, fy + 64], radius=32, fill=PRIMARY)
    d.text((fx + pw / 2, fy + 32), float2, font=f, fill=WHITE, anchor="mm")

    # nút
    label = button.upper()
    f = sans("ExtraBold", 32)
    bw = d.textlength(label, font=f) + 150
    by = 1000
    _shadow(img, (M, by, M + bw, by + 92), 46, blur=18, offset=(0, 12), alpha=110)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([M, by, M + bw, by + 92], radius=46, fill=PRIMARY)
    cx, cy = M + 52, by + 46                              # biểu tượng bong bóng chat
    d.ellipse([cx - 18, cy - 16, cx + 18, cy + 16], outline=WHITE, width=4)
    d.polygon([(cx - 14, cy + 10), (cx - 20, cy + 22), (cx - 4, cy + 14)], fill=WHITE)
    d.text((M + 90, by + 46), label, font=f, fill=WHITE, anchor="lm")

    _license_strip(img, 1150, licenses, score)
    d = ImageDraw.Draw(img)
    d.text((M, H - 46), "Giao dịch CFD/Forex có rủi ro cao, bạn có thể mất toàn bộ vốn. Mỗi pháp nhân được cấp phép tại khu vực "
           "tương ứng. Hình ảnh minh họa.", font=sans("Medium", 15), fill=MUTED, anchor="lm")
    save(img, path)
    return path
