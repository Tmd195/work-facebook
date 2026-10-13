"""Giao diện riêng cho Reels Education Page Duy Thái Đặng – dùng lại bộ dựng src/reels/edu (thẻ tối + nến minh hoạ)
nhưng đổi màu, khung, chữ ký thương hiệu để KHÔNG giống Reels CWG.

    theme.apply("reu")    # rêu đêm + chanh (màu thương hiệu Page Thái)
    theme.apply("gold")   # than xanh + vàng gold
"""
from PIL import Image, ImageDraw, ImageFilter

from src.config import CONFIG
from src.design.common import sans
from src.reels.edu import render as R

THEMES = {
    "reu": dict(BG=(6, 17, 13), CARD=(12, 29, 23), CARD_LINE=(34, 66, 52), GRID=(24, 46, 38), AXIS=(116, 148, 132),
                TEXT=(238, 245, 238), MUTED=(138, 164, 150), BRAND=(214, 242, 92), ON_BRAND=(14, 36, 26),
                UP=(98, 214, 150), DN=(240, 96, 96), KEY=(214, 242, 92), GLOW=((26, 82, 52), (14, 48, 30))),
    "gold": dict(BG=(8, 10, 18), CARD=(15, 19, 32), CARD_LINE=(44, 52, 76), GRID=(29, 35, 54), AXIS=(122, 132, 156),
                 TEXT=(242, 242, 246), MUTED=(142, 150, 172), BRAND=(232, 184, 74), ON_BRAND=(26, 20, 6),
                 UP=(46, 204, 150), DN=(238, 84, 96), KEY=(240, 196, 84), GLOW=((70, 52, 14), (24, 30, 64))),
}

NAME = (CONFIG.get("brand") or {}).get("name", "DUY THÁI ĐẶNG")
HANDLE = (CONFIG.get("brand") or {}).get("handle", "facebook.com/Dangduythai9xx")
SERIES = "REELS EDUCATION"
EPISODE = {"no": 1, "level": "CƠ BẢN"}          # build gán trước khi dựng
_GLOW = THEMES["reu"]["GLOW"]


def apply(name: str):
    global _GLOW
    t = THEMES[name]
    for k in ("BG", "CARD", "CARD_LINE", "GRID", "AXIS", "TEXT", "MUTED", "BRAND", "ON_BRAND", "UP", "DN"):
        setattr(R, k, t[k])
    R.COLORS = dict(R.COLORS, y=t["KEY"], w=t["TEXT"])
    R.LINE_END = 790
    R.THUMB_CLEAR = (12, 4)
    _GLOW = t["GLOW"]
    R.base_frame = base_frame
    if not getattr(R, "_orig_draw_card", None):
        R._orig_draw_card = R.draw_card
    R.draw_card = draw_card


def _monogram(d, cx, cy, size, fill):
    d.text((cx, cy), "DTĐ", font=sans("ExtraBold", size), fill=fill, anchor="mm")


def base_frame() -> Image.Image:
    img = Image.new("RGB", (R.W, R.H), R.BG)
    glow = Image.new("RGB", (R.W, R.H), R.BG)
    g = ImageDraw.Draw(glow)
    g.ellipse([-260, -300, 620, 360], fill=_GLOW[0])
    g.ellipse([560, 1420, 1360, 2200], fill=_GLOW[1])
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(170)), 1.0)
    box = R.CARD_BOX
    sh = Image.new("L", (R.W, R.H), 0)
    ImageDraw.Draw(sh).rounded_rectangle([box[0] + 6, box[1] + 18, box[2] + 6, box[3] + 24], radius=30, fill=170)
    img.paste((0, 0, 0), mask=sh.filter(ImageFilter.GaussianBlur(26)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius=28, fill=R.CARD, outline=R.CARD_LINE, width=2)
    # khác CWG: thanh màu nhấn chạy dọc mép TRÁI thẻ (CWG là vạch đỏ ngắn ở mép trên)
    d.rounded_rectangle([box[0], box[1] + 60, box[0] + 7, box[3] - 60], radius=4, fill=R.BRAND)
    # góc phải trên: số tập (thay logo)
    no = f"TẬP {EPISODE['no']:02d}"
    f1, f2 = sans("ExtraBold", 34), sans("Bold", 18)
    w = max(d.textlength(no, font=f1), d.textlength(EPISODE["level"], font=f2)) + 40
    x1, y0 = box[2] - 40, 150
    d.rounded_rectangle([x1 - w, y0, x1, y0 + 86], radius=14, outline=R.BRAND, width=3)
    d.text((x1 - w / 2, y0 + 30), no, font=f1, fill=R.BRAND, anchor="mm")
    d.text((x1 - w / 2, y0 + 64), EPISODE["level"], font=f2, fill=R.MUTED, anchor="mm")
    # chữ chìm giữa màn hình: monogram DTĐ
    _monogram(d, R.W // 2, R.H // 2 - 20, 230, R.mix(R.CARD, R.TEXT, 0.035))
    d.text((R.W // 2, R.H // 2 + 110), SERIES, font=sans("ExtraBold", 34), fill=R.mix(R.CARD, R.TEXT, 0.045), anchor="mt")
    # chân thẻ
    y = 1598
    d.ellipse([84, y - 22, 128, y + 22], fill=R.BRAND)
    d.text((106, y), "D", font=sans("ExtraBold", 26), fill=R.ON_BRAND, anchor="mm")
    d.text((142, y), NAME, font=sans("ExtraBold", 26), fill=R.TEXT, anchor="lm")
    d.text((996, y), HANDLE, font=sans("Medium", 22), fill=R.MUTED, anchor="rm")
    d.text((84, 1646), f"{SERIES} · Từ cơ bản đến hệ thống · Biểu đồ minh hoạ", font=sans("Regular", 20),
           fill=R.mix(R.MUTED, R.CARD, 0.3), anchor="lm")
    return img


def draw_card(img, card: dict, t: float, t0: float):
    if card.get("kind") != "cta":
        return R._orig_draw_card(img, card, t, t0)
    k = R.prog(t, t0, 0.4)
    if k <= 0:
        return
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([R.PLOT[0] - 10, R.PLOT[1] - 20, R.AXIS_X + 72, R.VOL[3] + 10], fill=R.CARD + (int(200 * k),))
    cx, cy = (R.PLOT[0] + R.AXIS_X + 60) / 2, (R.PLOT[1] + R.VOL[3]) / 2
    y = cy - 320 + (1 - k) * 40
    a = int(255 * k)
    d.ellipse([cx - 95, y, cx + 95, y + 190], fill=R.BRAND + (a,))
    d.text((cx, y + 95), "DTĐ", font=sans("ExtraBold", 64), fill=R.ON_BRAND + (a,), anchor="mm")
    y += 236
    d.text((cx, y), NAME, font=sans("ExtraBold", 62), fill=R.TEXT + (a,), anchor="mt")
    y += 88
    nxt = card.get("next")
    d.text((cx, y), card.get("line", "Lộ trình trading từ cơ bản đến hệ thống"), font=sans("Medium", 32),
           fill=R.MUTED + (a,), anchor="mt")
    kb = R.prog(t, t0 + 0.6, 0.45)
    if nxt:
        y += 76
        d.text((cx, y), "TẬP SAU", font=sans("Bold", 24), fill=R.BRAND + (int(255 * kb),), anchor="mt")
        d.text((cx, y + 38), nxt, font=sans("ExtraBold", 40), fill=R.TEXT + (int(255 * kb),), anchor="mt")
        y += 80
    y += 70
    bt = card.get("button", "THEO DÕI ĐỂ XEM TẬP SAU")
    f = sans("ExtraBold", 38)
    bw = d.textlength(bt, font=f) + 100
    s = 0.85 + 0.15 * kb
    d.rounded_rectangle([cx - bw / 2 * s, y, cx + bw / 2 * s, y + 92 * s], radius=20 * s, fill=R.BRAND + (int(255 * kb),))
    d.text((cx, y + 46 * s), bt, font=f, fill=R.ON_BRAND + (int(255 * kb),), anchor="mm")
