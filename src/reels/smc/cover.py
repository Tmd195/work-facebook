"""Thumbnail Reels kiến thức – kiểu "gây tò mò": câu hỏi/cảnh báo to, chỉ thẳng chỗ ĐÚNG/SAI trên chart thật,
GIẤU kết quả (dấu ? sau điểm vào lệnh) để người xem phải bấm vào xem tiếp."""
from PIL import Image, ImageDraw

from src.design.common import sans
from src.reels.smc.build import CH, GREY, INK, NAVY, ROOT, S, W, YEL, H, Scene, _txt
from src.reels.smc.setup import SMC

RED, GREEN = (229, 57, 53), (16, 163, 98)
TITLES = {
    "A": [("TỔ CHỨC", (255, 255, 255)), ("BÁN Ở ĐÂU?", YEL)],
    "B": [("ĐỪNG BÁN VÀNG", (255, 255, 255)), ("KHI CHƯA XEM", YEL)],
}


def _tag(img, x, y, text, col, good: bool, anchor_xy):
    """Nhãn tròn có biểu tượng ✓/✗ tự vẽ + mũi tên chỉ vào điểm anchor_xy."""
    f = sans("ExtraBold", 46)
    d = ImageDraw.Draw(img)
    tw = d.textlength(text, font=f)
    w, h = tw + 120, 92
    x0, y0 = x - w / 2, y - h / 2
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(lay)
    ax, ay = anchor_xy
    sx = max(x0 + 40, min(x0 + w - 40, ax))                   # mũi tên đi từ cạnh nhãn gần điểm chỉ nhất
    sy = y0 + h if ay > y else y0
    dl.line([(sx, sy), (ax, ay)], fill=col + (255,), width=10)
    import math
    ang = math.atan2(ay - sy, ax - sx)
    for da in (2.6, -2.6):
        dl.line([(ax, ay), (ax + 34 * math.cos(ang + da), ay + 34 * math.sin(ang + da))], fill=col + (255,), width=10)
    dl.rounded_rectangle([x0 + 6, y0 + 8, x0 + w + 6, y0 + h + 8], radius=h // 2, fill=(0, 0, 0, 60))
    dl.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=h // 2, fill=col + (255,), outline=(255, 255, 255, 255), width=5)
    cx, cy = x0 + 50, y
    dl.ellipse([cx - 28, cy - 28, cx + 28, cy + 28], fill=(255, 255, 255, 255))
    if good:
        dl.line([(cx - 14, cy + 1), (cx - 4, cy + 12), (cx + 15, cy - 12)], fill=col + (255,), width=8, joint="curve")
    else:
        for a, b in (((cx - 12, cy - 12), (cx + 12, cy + 12)), ((cx - 12, cy + 12), (cx + 12, cy - 12))):
            dl.line([a, b], fill=col + (255,), width=8)
    img.alpha_composite(lay)
    _txt(img, (x0 + 90 + tw / 2, y), text, f, (255, 255, 255), 1)


def _outlined(img, xy, text, size, fill, stroke=(0, 0, 0), sw=8, anchor="mm"):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).text(xy, text, font=sans("ExtraBold", size), fill=fill + (255,), anchor=anchor,
                             stroke_width=sw, stroke_fill=stroke + (255,))
    img.alpha_composite(lay)


def _fit(text, size, max_w):
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    while size > 40 and d.textlength(text, font=sans("ExtraBold", size)) > max_w:
        size -= 4
    return size


def hook(s: SMC, frame: Image.Image, chip: str, system: str, line1: str, line2: str) -> Image.Image:
    """Thumbnail GIẬT TÍT theo hệ thống: chip số hệ thống · TÊN HỆ THỐNG khổng lồ · câu giật tít 2 dòng ·
    chart thật đủ hệ thống + tem kết quả lệnh thật xoay nghiêng. frame: khung cuối (đủ hộp lệnh, đã chạm TP)."""
    img = frame.convert("RGBA")
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rectangle([0, 0, W, 700], fill=(255, 255, 255, 255))
    for y in range(140, 680):                                 # nền đỏ đậm → đen (giật mắt, khác hẳn 2 kênh kia)
        k = (y - 140) / 540
        d.line([(30, y), (W - 30, y)], fill=(int(150 * (1 - k) + 12 * k), int(14 * (1 - k) + 12 * k), int(24 * (1 - k) + 20 * k), 255))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([30, 140, W - 30, 680], radius=36, fill=255)
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    band.paste(lay, (0, 0), mask)
    white = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(white).rectangle([0, 0, W, 140], fill=(255, 255, 255, 255))
    ImageDraw.Draw(white).rectangle([0, 680, W, 700], fill=(255, 255, 255, 255))
    img.alpha_composite(white)
    img.alpha_composite(band)
    mark = Image.open(ROOT / "assets" / "brands" / "decode" / "official" / "decode_mark_1024.png").convert("RGBA")
    img.alpha_composite(mark.resize((60, 60), Image.LANCZOS), (40, 62))
    _txt(img, (114, 92), "DecodeFx Trading", sans("ExtraBold", 34), INK, 1, "lm")
    _txt(img, (W - 40, 92), f"{s.symbol} · {s.tf}", sans("Bold", 30), GREY, 1, "rm")
    chip_l = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cw = ImageDraw.Draw(chip_l).textlength(chip, font=sans("ExtraBold", 34)) + 60
    ImageDraw.Draw(chip_l).rounded_rectangle([W / 2 - cw / 2, 168, W / 2 + cw / 2, 222], radius=27, fill=YEL + (255,))
    img.alpha_composite(chip_l)
    _txt(img, (W / 2, 195), chip, sans("ExtraBold", 34), (20, 20, 20), 1)
    _outlined(img, (W / 2, 325), system, _fit(system, 150, W - 100), YEL, sw=7)
    _outlined(img, (W / 2, 485), line1, _fit(line1, 84, W - 110), (255, 255, 255), sw=5)
    _outlined(img, (W / 2, 590), line2, _fit(line2, 84, W - 110), (255, 255, 255), sw=5)
    # tem kết quả xoay nghiêng
    st = Image.new("RGBA", (520, 220), (0, 0, 0, 0))
    ds = ImageDraw.Draw(st)
    ds.rounded_rectangle([10, 10, 510, 210], radius=30, fill=(16, 163, 98, 255), outline=(255, 255, 255, 255), width=8)
    ds.text((260, 88), f"+{s.rr:.1f}R", font=sans("ExtraBold", 104), fill=(255, 255, 255), anchor="mm")
    ds.text((260, 172), "LỆNH THẬT", font=sans("ExtraBold", 40), fill=(255, 240, 160), anchor="mm")
    st = st.rotate(-8, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(st, (W - st.width - 20, CH[3] - st.height + 30))
    return img.convert("RGB")


def bait(s: SMC, frame: Image.Image, system: str, line1: str, line2: str) -> Image.Image:
    """Thumbnail giật tít: CÂU GIẬT TÍT là chữ to nhất (2 dòng: trắng → vàng), tên hệ thống làm nhãn nhỏ; không tem kết quả."""
    img = frame.convert("RGBA")
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for y in range(140, 720):
        k = (y - 140) / 580
        d.line([(30, y), (W - 30, y)], fill=(int(150 * (1 - k) + 12 * k), int(14 * (1 - k) + 12 * k), int(24 * (1 - k) + 20 * k), 255))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([30, 140, W - 30, 720], radius=36, fill=255)
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    band.paste(lay, (0, 0), mask)
    white = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(white).rectangle([0, 0, W, 740], fill=(255, 255, 255, 255))
    img.alpha_composite(white)
    img.alpha_composite(band)
    mark = Image.open(ROOT / "assets" / "brands" / "decode" / "official" / "decode_mark_1024.png").convert("RGBA")
    img.alpha_composite(mark.resize((60, 60), Image.LANCZOS), (40, 62))
    _txt(img, (114, 92), "DecodeFx Trading", sans("ExtraBold", 34), INK, 1, "lm")
    _txt(img, (W - 40, 92), f"{s.symbol} · {s.tf}", sans("Bold", 30), GREY, 1, "rm")
    chip_l = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cw = ImageDraw.Draw(chip_l).textlength(system, font=sans("ExtraBold", 36)) + 64
    ImageDraw.Draw(chip_l).rounded_rectangle([W / 2 - cw / 2, 172, W / 2 + cw / 2, 232], radius=30, fill=YEL + (255,))
    img.alpha_composite(chip_l)
    _txt(img, (W / 2, 202), system, sans("ExtraBold", 36), (20, 20, 20), 1)
    _outlined(img, (W / 2, 365), line1, _fit(line1, 140, W - 100), (255, 255, 255), sw=7)
    _outlined(img, (W / 2, 560), line2, _fit(line2, 150, W - 100), YEL, sw=8)
    return img.convert("RGB")


def make(s: SMC, frame: Image.Image, cam, variant: str = "A") -> Image.Image:
    """frame: khung hình lúc vừa khoanh nến xác nhận (chưa có hộp lệnh); cam: camera của khung đó."""
    sc = Scene(s)
    X = lambda i: sc.X(cam, i) / S
    Y = lambda p: sc.Y(cam, p) / S
    img = frame.convert("RGBA")
    sell = s.side == "sell"
    ob, z_lo, z_hi = s.zone
    # che phụ đề cũ + nền tiêu đề
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(top)
    d.rectangle([0, 0, W, 560], fill=(255, 255, 255, 255))
    d.rounded_rectangle([30, 140, W - 30, 540], radius=34, fill=NAVY + (255,))
    # vùng sau điểm vào lệnh: phủ trắng mờ + dấu ? (giấu kết quả)
    xk = X(s.k) + 26
    d.rectangle([xk, 600, CH[2], CH[3]], fill=(255, 255, 255, 215))
    img.alpha_composite(top)
    mark = Image.open(ROOT / "assets" / "brands" / "decode" / "official" / "decode_mark_1024.png").convert("RGBA")
    img.alpha_composite(mark.resize((60, 60), Image.LANCZOS), (40, 62))
    _txt(img, (114, 92), "DecodeFx Trading", sans("ExtraBold", 34), INK, 1, "lm")
    _txt(img, (W - 40, 92), f"{s.symbol} · {s.tf}", sans("Bold", 30), GREY, 1, "rm")
    (l1, c1), (l2, c2) = TITLES[variant]
    f = sans("ExtraBold", 132)
    for txt, y in ((l1, 270), (l2, 415)):
        size = 132
        while ImageDraw.Draw(img).textlength(txt, font=sans("ExtraBold", size)) > W - 110:
            size -= 4
        _txt(img, (W / 2, y), txt, sans("ExtraBold", size), c1 if txt == l1 else c2, 1)
    q = (xk + CH[2]) / 2
    _txt(img, (q, (CH[1] + CH[3]) / 2 + 40), "?", sans("ExtraBold", 330), (41, 98, 255), 1)
    _txt(img, (q, (CH[1] + CH[3]) / 2 + 250), "Giá đi đâu?", sans("ExtraBold", 44), INK, 1)
    # chỉ chỗ đúng / sai
    zy = (Y(z_lo) + Y(z_hi)) / 2
    good_xy = ((X(ob) + X(s.k)) / 2, zy)
    p_bad = s.p_end + (s.p_ext - s.p_end) * 0.15
    bad_i = s.swl - 6
    bad_xy = (X(bad_i), Y(p_bad))
    _tag(img, W * 0.36, Y(s.p_ext) - 130, "BÁN Ở ĐÂY" if sell else "MUA Ở ĐÂY", GREEN, True, good_xy)
    _tag(img, W * 0.36, min(CH[3] - 60, Y(s.p_end) + 120), "KHÔNG BÁN Ở ĐÂY" if sell else "KHÔNG MUA Ở ĐÂY",
         RED, False, bad_xy)
    return img.convert("RGB")
