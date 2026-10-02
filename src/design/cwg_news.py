"""Mẫu ảnh tin tức / giấy phép cho Page thương hiệu (CWG) – nền trắng, điểm đỏ, luôn đủ thương hiệu Page.

- render_license: thẻ giấy phép (FCA / FSCA / VFSC)
- render_breaking: thẻ tin nóng (tin số liệu: Thực tế / Dự báo / Kỳ trước + bảng tác động từng sản phẩm)
"""
from PIL import Image, ImageDraw

from src.config import CONFIG
from src.design.brand_carousel import (M, WHITE, _bg_candles, _glow, _icon_shield, _logo, _pill, _shadow)
from src.design.common import SIZE_4X5, fit, sans, save, wrap
from src.design.palette import INK, MUTED, PRIMARY

W, H = SIZE_4X5
UP = (22, 150, 90)
DOWN = PRIMARY
FLAT = (120, 120, 128)
LINE = (232, 232, 236)
PAPER_TOP, PAPER_BOT = (252, 252, 253), (241, 241, 244)


def _paper() -> Image.Image:
    img = Image.new("RGBA", (W, H), PAPER_TOP)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(PAPER_TOP, PAPER_BOT)) + (255,))
    return img


def _brand_header(img: Image.Image, right: str = ""):
    """Thanh đỏ trên cùng + logo + tên Page; bên phải nhãn nhỏ (vd. giờ tin)."""
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=PRIMARY)
    icon = _logo("icon", 56)
    if icon is not None:
        img.alpha_composite(icon, (M, 40))
    d.text((M + 76, 68), CONFIG["brand"]["name"], font=sans("ExtraBold", 28), fill=INK, anchor="lm")
    if right:
        f = sans("Bold", 22)
        w = d.textlength(right, font=f) + 36
        d.rounded_rectangle([W - M - w, 48, W - M, 88], radius=20, fill=(244, 244, 247))
        d.text((W - M - w / 2, 68), right, font=f, fill=MUTED, anchor="mm")


def _brand_footer(img: Image.Image, note: str):
    d = ImageDraw.Draw(img)
    d.line([(M, H - 92), (W - M, H - 92)], fill=LINE, width=2)
    d.text((M, H - 62), CONFIG["brand"]["handle"], font=sans("Bold", 22), fill=PRIMARY, anchor="lm")
    d.text((W - M, H - 62), "CWG Partner · Cập nhật thị trường cho đối tác", font=sans("SemiBold", 20), fill=MUTED,
           anchor="rm")
    d.text((M, H - 30), note, font=sans("Medium", 15), fill=MUTED, anchor="lm")


def _tri(d, x, y, s, up: bool, col):
    if up:
        d.polygon([(x, y + s), (x + s, y + s), (x + s / 2, y)], fill=col)
    else:
        d.polygon([(x, y), (x + s, y), (x + s / 2, y + s)], fill=col)


# ------------------------------------------------------------------ thẻ giấy phép

def render_license(path, lic: dict, index: int, total: int, all_licenses: list, score: str):
    """lic: {code, name, country, entity, number_label, number, address, status, verify_url, verify_steps:[..], note}"""
    img = _paper()
    _glow(img, (W - 140, 430), 300, PRIMARY, 45)
    _brand_header(img, f"GIẤY PHÉP {index}/{total}")
    d = ImageDraw.Draw(img)

    # khiên lớn mờ phía sau (dấu ấn pháp lý)
    shield = Image.new("RGBA", (420, 420), (0, 0, 0, 0))
    _icon_shield(ImageDraw.Draw(shield), 0, 0, 420, PRIMARY + (26,))
    img.alpha_composite(shield, (W - 470, 150))
    d = ImageDraw.Draw(img)

    _pill(d, M, 140, "PHÁP LÝ TẬP ĐOÀN CWG MARKETS", 22, PRIMARY, WHITE, pad=22)
    d.text((M - 6, 340), lic["code"], font=sans("ExtraBold", 170), fill=PRIMARY, anchor="ls")
    d.text((M, 385), lic["name"], font=sans("Bold", 32), fill=INK, anchor="lm")
    d.text((M, 425), lic["country"], font=sans("SemiBold", 28), fill=MUTED, anchor="lm")

    # thẻ thông tin giấy phép
    top = 470
    rows = [("Pháp nhân", lic["entity"]), (lic["number_label"], lic["number"]), ("Địa chỉ / thông tin", lic["address"]),
            ("Trạng thái", lic["status"])]
    ch = 50 + len(rows) * 82
    _shadow(img, (M, top, W - M, top + ch), 28, blur=20, offset=(0, 14), alpha=60)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([M, top, W - M, top + ch], radius=28, fill=WHITE)
    d.rectangle([M, top + 24, M + 8, top + ch - 24], fill=PRIMARY)
    y = top + 26
    for i, (k, v) in enumerate(rows):
        d.text((M + 44, y + 16), k.upper(), font=sans("Bold", 19), fill=MUTED, anchor="lm")
        strong = i == 1
        f = sans("ExtraBold", 40 if strong else 28)
        d.text((M + 44, y + 52), fit(d, v, f, W - 2 * M - 90), font=f, fill=PRIMARY if strong else INK, anchor="lm")
        y += 82
        if i < len(rows) - 1:
            d.line([(M + 44, y - 6), (W - M - 40, y - 6)], fill=LINE, width=2)

    # tự tra cứu
    y = top + ch + 34
    d.text((M, y), "TỰ TRA CỨU TRONG 30 GIÂY", font=sans("ExtraBold", 26), fill=INK)
    y += 50
    for k, step in enumerate(lic["verify_steps"][:3], 1):
        d.ellipse([M, y, M + 44, y + 44], fill=PRIMARY)
        d.text((M + 22, y + 22), str(k), font=sans("ExtraBold", 24), fill=WHITE, anchor="mm")
        d.text((M + 62, y + 22), fit(d, step, sans("SemiBold", 27), W - 2 * M - 70), font=sans("SemiBold", 27),
               fill=INK, anchor="lm")
        y += 56

    # dải 3 giấy phép – đánh dấu giấy phép đang nói
    y = H - 210
    n = len(all_licenses) + 1
    cw = (W - 2 * M - (n - 1) * 10) / n
    for k, (code, num) in enumerate(all_licenses):
        x0 = M + k * (cw + 10)
        active = code == lic["code"]
        d.rounded_rectangle([x0, y, x0 + cw, y + 80], radius=18, fill=PRIMARY if active else WHITE,
                            outline=None if active else LINE, width=2)
        d.text((x0 + 20, y + 28), code, font=sans("ExtraBold", 26), fill=WHITE if active else INK, anchor="lm")
        d.text((x0 + 20, y + 58), num, font=sans("SemiBold", 18), fill=(255, 220, 224) if active else MUTED, anchor="lm")
    x0 = M + (n - 1) * (cw + 10)
    d.rounded_rectangle([x0, y, x0 + cw, y + 80], radius=18, fill=(28, 28, 32))
    d.text((x0 + 20, y + 30), score, font=sans("ExtraBold", 30), fill=WHITE, anchor="lm")
    d.text((x0 + 20, y + 60), "Điểm WikiFX /10", font=sans("SemiBold", 18), fill=(200, 200, 206), anchor="lm")

    _brand_footer(img, "Mỗi pháp nhân được cấp phép tại khu vực tương ứng. Giao dịch CFD/Forex có rủi ro cao, bạn có thể mất toàn bộ vốn.")
    save(img, path)
    return path


# ------------------------------------------------------------------ thẻ tin nóng

def render_breaking(path, time_label: str, headline: str, data: dict | None, impacts: list, summary: str,
                    level: str = "CAO"):
    """data: {"actual","forecast","previous","better": True/False/None} cho tin số liệu, None cho tin sự kiện.
    impacts: [(sản phẩm, "up"|"down"|"flat", lý do ngắn)]"""
    img = _paper()
    _bg_candles(img, (40, 300, W - 40, 420), PRIMARY, 14, seed=11)
    _brand_header(img, time_label)
    d = ImageDraw.Draw(img)

    # nhãn TIN NÓNG + mức ảnh hưởng
    x = M
    f = sans("ExtraBold", 26)
    w = d.textlength("TIN NÓNG", font=f) + 92
    d.rounded_rectangle([x, 132, x + w, 132 + 50], radius=25, fill=PRIMARY)
    d.polygon([(x + 30, 141), (x + 42, 141), (x + 36, 154), (x + 46, 154), (x + 28, 174), (x + 33, 159), (x + 23, 159)],
              fill=WHITE)
    d.text((x + 58, 157), "TIN NÓNG", font=f, fill=WHITE, anchor="lm")
    _pill(d, x + w + 14, 132, f"Mức ảnh hưởng: {level}", 22, (253, 234, 236), PRIMARY, pad=22)

    y = 232
    hl = wrap(d, headline, sans("ExtraBold", 54), W - 2 * M, max_lines=4)
    for line in hl:
        d.text((M, y), line, font=sans("ExtraBold", 54), fill=INK)
        y += 68
    y += 18

    if data:
        bw = (W - 2 * M - 2 * 16) / 3
        cols = [("THỰC TẾ", data["actual"]), ("DỰ BÁO", data["forecast"]), ("KỲ TRƯỚC", data["previous"])]
        for k, (lab, val) in enumerate(cols):
            x0 = M + k * (bw + 16)
            main = k == 0
            col = UP if data.get("better") is True else DOWN if data.get("better") is False else INK
            _shadow(img, (x0, y, x0 + bw, y + 150), 24, blur=14, offset=(0, 10), alpha=45 if main else 25)
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([x0, y, x0 + bw, y + 150], radius=24, fill=WHITE,
                                outline=col if main else LINE, width=4 if main else 2)
            d.text((x0 + bw / 2, y + 40), lab, font=sans("Bold", 22), fill=MUTED, anchor="mm")
            d.text((x0 + bw / 2, y + 100), str(val), font=sans("ExtraBold", 56 if main else 46),
                   fill=col if main else INK, anchor="mm")
        y += 186

    # bảng tác động
    d.text((M, y), "TÁC ĐỘNG TỚI THỊ TRƯỜNG", font=sans("ExtraBold", 26), fill=INK)
    y += 50
    rows = impacts[:5]
    rh = 78
    _shadow(img, (M, y, W - M, y + rh * len(rows) + 16), 24, blur=16, offset=(0, 10), alpha=40)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([M, y, W - M, y + rh * len(rows) + 16], radius=24, fill=WHITE)
    yy = y + 8
    for k, (asset, direction, why) in enumerate(rows):
        col = UP if direction == "up" else DOWN if direction == "down" else FLAT
        d.text((M + 30, yy + rh / 2), asset, font=sans("ExtraBold", 32), fill=INK, anchor="lm")
        if direction == "flat":
            d.rectangle([M + 230, yy + rh / 2 - 4, M + 262, yy + rh / 2 + 4], fill=col)
        else:
            _tri(d, M + 230, yy + rh / 2 - 15, 30, direction == "up", col)
        d.text((M + 290, yy + rh / 2), fit(d, why, sans("SemiBold", 26), W - 2 * M - 320), font=sans("SemiBold", 26),
               fill=(60, 60, 66), anchor="lm")
        if k < len(rows) - 1:
            d.line([(M + 30, yy + rh), (W - M - 30, yy + rh)], fill=LINE, width=2)
        yy += rh
    y = yy + 40

    # nhận định ngắn
    if summary and y < H - 220:
        sl = wrap(d, summary, sans("SemiBold", 28), W - 2 * M - 70, max_lines=3)
        bh = len(sl) * 40 + 44
        d.rounded_rectangle([M, y, W - M, y + bh], radius=22, fill=(253, 234, 236))
        d.rectangle([M, y + 16, M + 8, y + bh - 16], fill=PRIMARY)
        for k, line in enumerate(sl):
            d.text((M + 40, y + 24 + k * 40), line, font=sans("SemiBold", 28), fill=INK)

    _brand_footer(img, "Thông tin thị trường mang tính tham khảo, không phải khuyến nghị đầu tư. Giao dịch CFD/Forex có rủi ro cao.")
    save(img, path)
    return path
