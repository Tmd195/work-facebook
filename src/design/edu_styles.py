"""3 phương án phong cách ảnh post kiến thức cho Page DecodeFx Trading (anh muốn form HOÀN TOÀN MỚI, 08/10/2026).

A "blueprint": bản vẽ kỹ thuật – nền xanh dương lưới ô ly, nét trắng/cyan
B "terminal":  màn hình giao dịch – nền đen, neon xanh lá / cam, số liệu
C "notebook":  sổ tay trader – giấy kem, nét mực vẽ tay, bút dạ quang vàng

    python -m src.design.edu_styles      # → _preview/edu_styles/*.png
"""
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from src.config import ROOT
from src.design.common import sans, serif

W, H = 1080, 1350
OUT = ROOT / "_preview" / "edu_styles"
FONTS = ROOT / "assets" / "fonts"


def exo(size, weight=700):
    from PIL import ImageFont
    f = ImageFont.truetype(str(FONTS / "Exo2-Variable.ttf"), size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def lora(size, weight=700, italic=False):
    from PIL import ImageFont
    f = ImageFont.truetype(str(FONTS / ("Lora-Italic-Variable.ttf" if italic else "Lora-Variable.ttf")), size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


# nến minh hoạ Order Block tăng: giảm dần → nến giảm cuối (OB) → cú tăng mạnh phá đỉnh (BOS, để lại FVG) → hồi về OB → tăng
CANDLES = [(50, 53, 47, 48), (48, 50, 44, 45), (45, 47, 41, 42), (42, 44, 38, 40), (40, 41, 35, 36),   # 4: OB (nến giảm)
           (36, 49, 35, 48), (48, 62, 47, 61), (61, 64, 58, 60), (60, 61, 54, 55), (55, 56, 47, 48),
           (48, 49, 38, 40), (40, 47, 37, 46), (46, 58, 45, 57), (57, 70, 56, 69), (69, 74, 66, 73)]
OB_I, BOS_FROM, FVG_I, RET_I = 4, 0, 6, 10


class Plot:
    def __init__(self, box, lo=30, hi=78, n=len(CANDLES)):
        self.box, self.lo, self.hi, self.n = box, lo, hi, n

    def X(self, i):
        x0, _, x1, _ = self.box
        return x0 + (i + 0.5) / self.n * (x1 - x0)

    def Y(self, p):
        _, y0, _, y1 = self.box
        return y1 - (p - self.lo) / (self.hi - self.lo) * (y1 - y0)

    @property
    def bw(self):
        return (self.box[2] - self.box[0]) / self.n * 0.55


def jitter_line(d, pts, fill, width, amp=1.6, seed=1):
    """Nét vẽ tay: chia nhỏ đoạn thẳng, lệch ngẫu nhiên nhẹ."""
    rnd = random.Random(seed)
    out = []
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        n = max(2, int(math.hypot(xb - xa, yb - ya) / 14))
        for k in range(n):
            t = k / n
            out.append((xa + (xb - xa) * t + rnd.uniform(-amp, amp), ya + (yb - ya) * t + rnd.uniform(-amp, amp)))
    out.append(pts[-1])
    d.line(out, fill=fill, width=width, joint="curve")


def candles(d, P: Plot, up, dn, style, outline=None):
    for i, (o, h, l, c) in enumerate(CANDLES):
        x = P.X(i)
        col = up if c >= o else dn
        ya, yb = sorted((P.Y(o), P.Y(c)))
        if style == "notebook":
            jitter_line(d, [(x, P.Y(h)), (x, P.Y(l))], (40, 40, 48), 3, 1.0, i)
            r = [x - P.bw / 2, ya, x + P.bw / 2, yb]
            if c < o:
                d.rectangle(r, fill=(40, 40, 48))
            else:
                d.rectangle(r, fill=(250, 246, 234))
            jitter_line(d, [(r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3]), (r[0], r[1])], (40, 40, 48), 3, 1.2, i + 50)
        else:
            d.line([(x, P.Y(h)), (x, P.Y(l))], fill=col, width=3)
            if style == "blueprint":
                d.rectangle([x - P.bw / 2, ya, x + P.bw / 2, yb], outline=col, width=3,
                            fill=(col if c < o else None))
            else:
                d.rectangle([x - P.bw / 2, ya, x + P.bw / 2, yb], fill=col)


# ------------------------------------------------------------------ A. BLUEPRINT

BP_BG, BP_GRID, BP_LINE, BP_CYAN, BP_YEL = (14, 52, 110), (40, 86, 150), (236, 244, 255), (110, 220, 255), (255, 210, 80)


def bp_base(n, title_small):
    img = Image.new("RGB", (W, H), BP_BG)
    d = ImageDraw.Draw(img)
    for x in range(0, W, 30):
        d.line([(x, 0), (x, H)], fill=BP_GRID if x % 150 else (60, 110, 180), width=1)
    for y in range(0, H, 30):
        d.line([(0, y), (W, y)], fill=BP_GRID if y % 150 else (60, 110, 180), width=1)
    d.rectangle([28, 28, W - 28, H - 28], outline=BP_LINE, width=3)
    d.rectangle([40, 40, W - 40, H - 40], outline=BP_LINE, width=1)
    # khung tên bản vẽ góc dưới phải
    d.rectangle([W - 430, H - 150, W - 40, H - 40], outline=BP_LINE, width=2)
    d.line([(W - 430, H - 95), (W - 40, H - 95)], fill=BP_LINE, width=1)
    d.text((W - 415, H - 122), "DECODEFX TRADING", font=exo(28, 800), fill=BP_LINE, anchor="lm")
    d.text((W - 55, H - 122), f"BV-{n:02d}", font=exo(26, 600), fill=BP_CYAN, anchor="rm")
    d.text((W - 415, H - 67), title_small, font=exo(22, 500), fill=BP_LINE, anchor="lm")
    d.text((70, H - 95), "Follow DecodeFX Trading", font=exo(28, 700), fill=BP_LINE, anchor="lm")
    d.text((70, H - 60), "Con đường ngắn nhất để trở thành 1 Protrader", font=sans("Medium", 20), fill=BP_CYAN, anchor="lm")
    return img, d


def bp_dim(d, x, y0, y1, label):
    """Đường kích thước kiểu bản vẽ."""
    d.line([(x, y0), (x, y1)], fill=BP_CYAN, width=2)
    for y in (y0, y1):
        d.line([(x - 12, y), (x + 12, y)], fill=BP_CYAN, width=2)
    d.text((x + 18, (y0 + y1) / 2), label, font=exo(24, 600), fill=BP_CYAN, anchor="lm")


def blueprint_cover():
    img, d = bp_base(1, "SMC · ORDER BLOCK")
    d.text((80, 120), "HỆ THỐNG #02 / SMC", font=exo(30, 600), fill=BP_CYAN)
    d.text((80, 175), "ORDER", font=exo(170, 900), fill=BP_LINE)
    d.text((80, 345), "BLOCK", font=exo(170, 900), fill=BP_YEL)
    d.text((84, 545), "Bản vẽ chi tiết: cách tổ chức đặt lệnh", font=sans("SemiBold", 34), fill=BP_LINE)
    P = Plot((110, 640, W - 110, 1140))
    candles(d, P, BP_LINE, BP_LINE, "blueprint")
    o, h, l, c = CANDLES[OB_I]
    d.rectangle([P.X(OB_I) - P.bw, P.Y(h), P.X(RET_I) + P.bw, P.Y(l)], outline=BP_YEL, width=3)
    d.text((P.X(OB_I) - P.bw, P.Y(l) + 14), "OB", font=exo(30, 800), fill=BP_YEL)
    bp_dim(d, P.X(OB_I) - P.bw - 30, P.Y(h), P.Y(l), "")
    return img


def blueprint_inner():
    img, d = bp_base(2, "ORDER BLOCK LÀ GÌ?")
    d.text((80, 100), "01 · ĐỊNH NGHĨA", font=exo(30, 600), fill=BP_CYAN)
    d.text((80, 150), "ORDER BLOCK LÀ GÌ?", font=exo(76, 900), fill=BP_LINE)
    for j, line in enumerate(["Cây nến NGƯỢC MÀU CUỐI CÙNG trước cú",
                              "phá cấu trúc mạnh – nơi tổ chức gom lệnh lớn."]):
        d.text((80, 270 + j * 48), line, font=sans("SemiBold", 34), fill=BP_LINE)
    P = Plot((110, 430, W - 110, 1040))
    candles(d, P, BP_LINE, BP_LINE, "blueprint")
    o, h, l, c = CANDLES[OB_I]
    d.rectangle([P.X(OB_I) - P.bw, P.Y(h), P.X(RET_I) + P.bw, P.Y(l)], outline=BP_YEL, width=3)
    d.text((P.X(OB_I), P.Y(l) + 30), "A · ORDER BLOCK", font=exo(26, 800), fill=BP_YEL, anchor="mm")
    pk = max(CANDLES[0][1], CANDLES[1][1])
    d.line([(P.X(0), P.Y(53)), (P.X(6), P.Y(53))], fill=BP_CYAN, width=2)
    d.text((P.X(3), P.Y(53) - 22), "B · BOS", font=exo(24, 700), fill=BP_CYAN, anchor="mm")
    fl, fh = CANDLES[FVG_I - 1][1], CANDLES[FVG_I + 1][2]
    d.rectangle([P.X(FVG_I - 1), P.Y(fh), P.X(FVG_I + 4), P.Y(fl)], outline=BP_CYAN, width=2)
    d.text((P.X(FVG_I + 4) + 10, P.Y((fl + fh) / 2)), "C · FVG", font=exo(24, 700), fill=BP_CYAN, anchor="lm")
    for j, t in enumerate(["A – vùng đặt lệnh của tổ chức", "B – xác nhận phá cấu trúc", "C – dấu vết lệnh lớn (khoảng trống giá)"]):
        d.text((80, 1080 + j * 40), t, font=sans("Medium", 28), fill=BP_LINE)
    return img


# ------------------------------------------------------------------ B. TERMINAL

TM_BG, TM_PANEL, TM_GRN, TM_RED, TM_AMB, TM_TXT, TM_DIM = (6, 9, 12), (14, 20, 26), (0, 230, 118), (255, 64, 96), (255, 176, 32), (220, 230, 235), (90, 110, 120)


def tm_base(n, path):
    img = Image.new("RGB", (W, H), TM_BG)
    d = ImageDraw.Draw(img)
    for y in range(0, H, 4):                                   # vạch quét màn hình
        d.line([(0, y), (W, y)], fill=(9, 13, 17))
    d.rectangle([0, 0, W, 64], fill=TM_PANEL)
    for k, c in enumerate((TM_RED, TM_AMB, TM_GRN)):
        d.ellipse([28 + k * 30, 22, 46 + k * 30, 40], fill=c)
    d.text((140, 32), f"decodefx-trading ~ /{path}", font=exo(26, 500), fill=TM_DIM, anchor="lm")
    d.text((W - 30, 32), f"[{n:02d}/07]", font=exo(26, 700), fill=TM_AMB, anchor="rm")
    d.rectangle([0, H - 90, W, H], fill=TM_PANEL)
    d.text((40, H - 45), "> Follow DecodeFX Trading", font=exo(30, 800), fill=TM_GRN, anchor="lm")
    d.text((W - 40, H - 45), "con đường ngắn nhất → Protrader", font=sans("Medium", 22), fill=TM_DIM, anchor="rm")
    return img, d


def glow_text(img, xy, text, font, col, anchor="la"):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).text(xy, text, font=font, fill=col + (255,), anchor=anchor)
    blur = lay.filter(ImageFilter.GaussianBlur(10))
    base = img.convert("RGBA")
    base.alpha_composite(blur)
    base.alpha_composite(lay)
    return base.convert("RGB")


def terminal_cover():
    img, d = tm_base(1, "systems/smc/order_block")
    d.text((60, 120), "$ run system --id 02", font=exo(34, 600), fill=TM_DIM)
    img = glow_text(img, (60, 180), "ORDER", exo(190, 900), TM_TXT)
    img = glow_text(img, (60, 370), "BLOCK_", exo(190, 900), TM_GRN)
    d = ImageDraw.Draw(img)
    rows = [("STATUS", "ĐANG HOẠT ĐỘNG", TM_GRN), ("TYPE", "SMC · INSTITUTIONAL", TM_TXT),
            ("TÁC DỤNG", "BẮT ĐIỂM VÀO CỦA TỔ CHỨC", TM_AMB)]
    for j, (k, v, c) in enumerate(rows):
        d.text((64, 600 + j * 52), f"{k:<9}", font=exo(30, 600), fill=TM_DIM)
        d.text((300, 600 + j * 52), v, font=sans("Bold", 30), fill=c)
    P = Plot((80, 790, W - 80, 1200))
    d.rectangle([60, 770, W - 60, 1220], outline=(30, 44, 52), width=2)
    o, h, l, c = CANDLES[OB_I]
    d.rectangle([P.X(OB_I) - P.bw, P.Y(h), P.X(RET_I) + P.bw, P.Y(l)], fill=(40, 30, 10), outline=TM_AMB, width=2)
    candles(d, P, TM_GRN, TM_RED, "terminal")
    d.text((P.X(OB_I) - P.bw, P.Y(l) + 12), "OB", font=exo(26, 800), fill=TM_AMB)
    return img


def terminal_inner():
    img, d = tm_base(2, "systems/smc/order_block/what_is")
    d.text((60, 110), "// 01. ĐỊNH NGHĨA", font=exo(32, 600), fill=TM_DIM)
    img = glow_text(img, (60, 160), "ORDER BLOCK LÀ GÌ?", exo(78, 900), TM_TXT)
    d = ImageDraw.Draw(img)
    d.text((60, 280), "=", font=exo(40, 700), fill=TM_AMB)
    for j, line in enumerate(["Cây nến ngược màu CUỐI CÙNG", "trước cú phá cấu trúc mạnh.", "Nơi tổ chức gom lệnh lớn."]):
        d.text((110, 282 + j * 50), line, font=sans("SemiBold", 36), fill=TM_TXT if j < 2 else TM_AMB)
    P = Plot((90, 470, W - 90, 1000))
    d.rectangle([60, 450, W - 60, 1020], outline=(30, 44, 52), width=2)
    o, h, l, c = CANDLES[OB_I]
    d.rectangle([P.X(OB_I) - P.bw, P.Y(h), P.X(RET_I) + P.bw, P.Y(l)], fill=(40, 30, 10), outline=TM_AMB, width=2)
    fl, fh = CANDLES[FVG_I - 1][1], CANDLES[FVG_I + 1][2]
    d.rectangle([P.X(FVG_I - 1), P.Y(fh), P.X(FVG_I + 4), P.Y(fl)], fill=(0, 40, 24), outline=TM_GRN, width=2)
    d.line([(P.X(0), P.Y(53)), (P.X(6), P.Y(53))], fill=TM_TXT, width=2)
    candles(d, P, TM_GRN, TM_RED, "terminal")
    d.text((P.X(OB_I), P.Y(l) + 26), "[OB]", font=exo(26, 800), fill=TM_AMB, anchor="mm")
    d.text((P.X(FVG_I + 4) + 10, P.Y((fl + fh) / 2)), "[FVG]", font=exo(26, 800), fill=TM_GRN, anchor="lm")
    d.text((P.X(3), P.Y(53) - 22), "[BOS]", font=exo(24, 800), fill=TM_TXT, anchor="mm")
    log = [("> OB", "vùng đặt lệnh của tổ chức", TM_AMB), ("> BOS", "xác nhận phá cấu trúc", TM_TXT),
           ("> FVG", "dấu vết lệnh lớn để lại", TM_GRN)]
    for j, (k, v, c) in enumerate(log):
        d.text((64, 1060 + j * 50), k, font=exo(30, 800), fill=c)
        d.text((220, 1060 + j * 50), v, font=sans("Medium", 30), fill=TM_TXT)
    return img


# ------------------------------------------------------------------ C. NOTEBOOK

NB_BG, NB_LINE, NB_INK, NB_RED, NB_HL = (250, 246, 234), (205, 220, 236), (34, 34, 44), (205, 40, 40), (255, 228, 92)


def nb_base(n):
    img = Image.new("RGB", (W, H), NB_BG)
    d = ImageDraw.Draw(img)
    for y in range(150, H - 80, 44):
        d.line([(0, y), (W, y)], fill=NB_LINE, width=2)
    d.line([(120, 0), (120, H)], fill=(240, 170, 170), width=3)          # lề đỏ
    for y in range(90, H, 160):                                           # lỗ bấm sổ
        d.ellipse([34, y, 66, y + 32], fill=(228, 222, 206))
    d.text((W - 50, 70), f"Trang {n}", font=lora(30, 500, True), fill=(120, 120, 130), anchor="rm")
    d.text((150, H - 60), "Follow DecodeFX Trading", font=lora(32, 700), fill=NB_INK, anchor="lm")
    d.text((W - 50, H - 60), "– con đường ngắn nhất để thành Protrader", font=lora(24, 400, True), fill=(110, 110, 120), anchor="rm")
    return img, d


def highlight(img, box):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).rectangle(box, fill=NB_HL + (150,))
    base = img.convert("RGBA")
    base.alpha_composite(lay)
    return base.convert("RGB")


def notebook_cover():
    img, d = nb_base(1)
    d.text((150, 110), "Sổ tay hệ thống #02", font=lora(36, 500, True), fill=(110, 110, 120))
    f = lora(170, 700)
    img = highlight(img, (150, 330, 150 + ImageDraw.Draw(img).textlength("BLOCK", font=f) + 10, 390))
    d = ImageDraw.Draw(img)
    d.text((145, 160), "ORDER", font=f, fill=NB_INK)
    d.text((145, 330), "BLOCK", font=f, fill=NB_INK)
    d.text((150, 545), "Ghi chép thật của trader:", font=lora(40, 500, True), fill=NB_INK)
    d.text((150, 600), "dùng đúng thì ăn, dùng sai thì cháy.", font=lora(40, 700), fill=NB_RED)
    P = Plot((170, 720, W - 80, 1160))
    candles(d, P, NB_INK, NB_INK, "notebook")
    o, h, l, c = CANDLES[OB_I]
    cx, cy = P.X(OB_I), (P.Y(h) + P.Y(l)) / 2
    pts = [(cx + 70 * math.cos(a / 20 * 2 * math.pi), cy + 60 * math.sin(a / 20 * 2 * math.pi)) for a in range(22)]
    jitter_line(d, pts, NB_RED, 5, 2.5, 7)
    d.text((cx + 90, cy + 70), "<-- OB ở đây!", font=lora(40, 700, True), fill=NB_RED)
    return img


def notebook_inner():
    img, d = nb_base(2)
    d.text((150, 100), "1. Order Block là gì?", font=lora(66, 700), fill=NB_INK)
    jitter_line(d, [(150, 190), (760, 190)], NB_RED, 4, 1.5, 3)
    lines = ["Là cây nến ngược màu CUỐI CÙNG", "trước cú phá cấu trúc mạnh.", "=> nơi tổ chức gom lệnh lớn."]
    img = highlight(img, (150, 245, 820, 290))
    d = ImageDraw.Draw(img)
    for j, t in enumerate(lines):
        d.text((150, 222 + j * 66), t, font=lora(42, 600 if j < 2 else 700, j == 2), fill=NB_INK if j < 2 else NB_RED)
    P = Plot((170, 460, W - 90, 1000))
    candles(d, P, NB_INK, NB_INK, "notebook")
    o, h, l, c = CANDLES[OB_I]
    jitter_line(d, [(P.X(OB_I) - P.bw, P.Y(h)), (P.X(RET_I) + P.bw, P.Y(h)), (P.X(RET_I) + P.bw, P.Y(l)),
                    (P.X(OB_I) - P.bw, P.Y(l)), (P.X(OB_I) - P.bw, P.Y(h))], NB_RED, 4, 1.8, 11)
    d.text((P.X(OB_I) - P.bw, P.Y(l) + 16), "OB", font=lora(40, 700, True), fill=NB_RED)
    jitter_line(d, [(P.X(0), P.Y(53)), (P.X(6), P.Y(53))], (40, 90, 200), 4, 1.5, 21)
    d.text((P.X(2), P.Y(53) - 46), "BOS", font=lora(36, 700, True), fill=(40, 90, 200))
    fl, fh = CANDLES[FVG_I - 1][1], CANDLES[FVG_I + 1][2]
    img = highlight(img, (P.X(FVG_I) - 20, P.Y(fh), P.X(FVG_I + 4), P.Y(fl)))
    d = ImageDraw.Draw(img)
    d.text((P.X(FVG_I + 4) + 10, P.Y((fl + fh) / 2) - 20), "FVG", font=lora(36, 700, True), fill=NB_INK)
    notes = ["✓ OB = vùng tổ chức đặt lệnh", "✓ BOS = xác nhận cú phá", "✓ FVG = dấu vết lệnh lớn"]
    for j, t in enumerate(notes):
        d.text((150, 1040 + j * 54), t.replace("✓", "–"), font=lora(38, 600, True), fill=NB_INK)
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in (("A_blueprint_1", blueprint_cover), ("A_blueprint_2", blueprint_inner),
                     ("B_terminal_1", terminal_cover), ("B_terminal_2", terminal_inner),
                     ("C_notebook_1", notebook_cover), ("C_notebook_2", notebook_inner)):
        fn().save(OUT / f"{name}.png")
        print("ok", name)


if __name__ == "__main__":
    main()
