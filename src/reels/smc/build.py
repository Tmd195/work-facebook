"""Reels kiến thức thực chiến – khuôn "từng bước trên chart" (theo video SAPP Academy anh gửi), phụ đề tiếng Việt.

- Chart kiểu TradingView NỀN SÁNG, nến mảnh đỏ/xanh, camera kéo/zoom mượt giữa các bước
- Mở đầu: khung kết quả (đủ hệ thống + hộp lệnh) làm "mồi"; sau đó xoá trắng, đi lại từng BƯỚC
- Mỗi bước: vẽ dần đối tượng như người đang vẽ trên TradingView (đường kéo dài, có chấm tay cầm, vùng nở ra)
- Phụ đề: dải xanh than đậm phía trên chart, chữ trắng + từ khoá vàng (Be Vietnam Pro – không dùng font như mẫu)
- Bước cuối: nến chạy thật tới TP. Dữ liệu và kết quả lệnh là THẬT (dữ liệu quá khứ).

    python -m src.reels.smc.build --pick 0
"""
import argparse
import json
import random
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

from src.config import OUTPUT, ROOT
from src.design.common import sans
from src.reels.edu.build import mix
from src.reels.quiz.build import ease
from src.reels.smc.setup import SMC, find

W, H, FPS, S = 1080, 1920, 30, 2                    # S: vẽ chart ở 2x rồi thu nhỏ cho nét
VN = ZoneInfo("Asia/Ho_Chi_Minh")
CH = (0, 300, 985, 1690)                            # vùng chart; trục giá bên phải
UP, DN = (8, 153, 129), (242, 54, 69)               # màu nến TradingView
INK, GREY, GRID = (19, 23, 34), (120, 123, 134), (240, 243, 250)
NAVY, YEL = (12, 27, 77), (255, 214, 64)
PURPLE, LAV = (126, 87, 194), (179, 157, 219)
MUSIC_DIRS = [ROOT / "assets" / "music" / "cwg", ROOT / "assets" / "music"]


def lerp(a, b, k):
    return a + (b - a) * k


class Cam:
    def __init__(self, x0, x1, p0, p1):
        self.x0, self.x1, self.p0, self.p1 = x0, x1, p0, p1

    def mix(self, o, k):
        return Cam(*(lerp(a, b, k) for a, b in zip((self.x0, self.x1, self.p0, self.p1), (o.x0, o.x1, o.p0, o.p1))))


class Scene:
    def __init__(self, s: SMC):
        self.s = s
        d = s.d
        self.O, self.Hh, self.L, self.C = (d[c].to_numpy() for c in ("open", "high", "low", "close"))
        self.sell = s.side == "sell"
        self.digits = 2 if s.symbol == "XAUUSD" else 5
        self.start = max(0, min(b[0] for b in s.bos) - 12)
        self.x_end = min(len(d) - 1, s.hit + 6)

    # ---------- camera
    def fit(self, x0, x1, extra=()) -> Cam:
        i0, i1 = max(0, int(x0)), min(len(self.C) - 1, int(x1))
        lo = min(self.L[i0:i1 + 1].min(), *extra) if extra else self.L[i0:i1 + 1].min()
        hi = max(self.Hh[i0:i1 + 1].max(), *extra) if extra else self.Hh[i0:i1 + 1].max()
        pad = (hi - lo) * 0.12
        return Cam(x0, x1, lo - pad, hi + pad)

    def X(self, cam, i):
        return (CH[0] + (i - cam.x0 + 0.5) / (cam.x1 - cam.x0) * (CH[2] - CH[0])) * S

    def Y(self, cam, p):
        return (CH[1] + (cam.p1 - p) / (cam.p1 - cam.p0) * (CH[3] - CH[1])) * S

    # ---------- vẽ
    def candles(self, d, cam, shown: float):
        slot = (CH[2] - CH[0]) / (cam.x1 - cam.x0) * S
        bw = max(2.0, slot * 0.62)
        last = int(shown)
        for i in range(max(0, int(cam.x0) - 1), min(last, int(cam.x1) + 1) + 1):
            o, h, l, c = self.O[i], self.Hh[i], self.L[i], self.C[i]
            if i == last:
                part = shown - last
                if part <= 0.01:
                    continue
                c = o + (c - o) * part
                h, l = max(o, c, o + (h - o) * min(1, part * 1.3)), min(o, c, o + (l - o) * min(1, part * 1.3))
            col = UP if c >= o else DN
            x = self.X(cam, i)
            d.line([(x, self.Y(cam, h)), (x, self.Y(cam, l))], fill=col, width=max(2, int(slot * 0.09)))
            ya, yb = sorted((self.Y(cam, o), self.Y(cam, c)))
            d.rectangle([x - bw / 2, ya, x + bw / 2, max(yb, ya + 2)], fill=col)

    def axis(self, img, cam):
        d = ImageDraw.Draw(img)
        span = cam.p1 - cam.p0
        step = _nice(span / 8)
        p = (cam.p0 // step + 1) * step
        f = sans("Medium", 21)
        while p < cam.p1:
            y = self.Y(cam, p) / S
            if CH[1] + 10 < y < CH[3] - 10:
                d.line([(CH[0], y), (CH[2], y)], fill=GRID, width=1)
                d.text((CH[2] + 8, y), f"{p:.{self.digits if step < 1 else 0}f}"[:9], font=f, fill=GREY, anchor="lm")
            p += step
        d.line([(CH[2], CH[1]), (CH[2], CH[3])], fill=(224, 227, 235), width=1)

    def handles(self, d, pts, a=255):
        for x, y in pts:
            d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=(255, 255, 255, a), outline=(41, 98, 255, a), width=4)

    def typed(self, d, x, y, text, col, size, t, t0, a=255, anchor="mm"):
        """Công cụ Text TradingView: click → ô nhập (viền xanh + con trỏ nhấp nháy) → gõ từng ký tự.
        t0 < 0: hiện đủ chữ (đoạn mồi)."""
        f = sans("Bold", size * S)
        if t0 < 0:
            d.text((x, y), text, font=f, fill=col + (a,), anchor=anchor)
            return
        if t < t0:
            return
        n = min(len(text), int((t - t0) * LABEL_CPS))
        l, tp, r, b = d.textbbox((x, y), text, font=f, anchor=anchor)
        part = text[:n]
        if part:
            d.text((l, y), part, font=f, fill=col + (a,), anchor="lm")
        if t < t0 + len(text) / LABEL_CPS + 0.45:                  # đang ở chế độ gõ
            pad = 7 * S
            d.rectangle([l - pad, tp - pad, r + pad, b + pad], outline=(41, 98, 255, 230), width=S)
            if int(t * 4) % 2 == 0 or n < len(text):
                cx = l + (d.textlength(part, font=f) if part else 0) + 2 * S
                d.line([(cx, tp - 2 * S), (cx, b + 2 * S)], fill=INK + (255,), width=S + 1)

    def label(self, d, x, y, text, col=INK, size=22, box=False, a=255, anchor="mm"):
        f = sans("Bold", size * S)
        if box:
            l, t, r, b = d.textbbox((x, y), text, font=f, anchor=anchor)
            d.rounded_rectangle([l - 10, t - 7, r + 10, b + 7], radius=8, fill=(255, 255, 255, int(a * 0.9)),
                                outline=col + (a,), width=2)
        d.text((x, y), text, font=f, fill=col + (a,), anchor=anchor)


def _nice(x):
    import math
    e = 10 ** math.floor(math.log10(x))
    for m in (1, 2, 2.5, 5, 10):
        if x <= m * e:
            return m * e
    return 10 * e


def _txt(img, xy, text, font, col, a=1.0, anchor="mm"):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).text(xy, text, font=font, fill=col + (int(255 * max(0, min(1, a))),), anchor=anchor)
    img.alpha_composite(lay)


def rich(img, cx, y, parts, size, a=1.0, max_w=960, chars=None, caret=False):
    """Một dòng phụ đề nhiều màu: parts = [(chữ, màu)]; tự xuống dòng theo từ.
    chars: số ký tự đã "gõ" (hiệu ứng đánh máy – bố cục dòng giữ cố định theo cả câu); caret: con trỏ nhấp nháy."""
    f = sans("ExtraBold", size)
    d = ImageDraw.Draw(img)
    words = []
    for t, c in parts:
        for w in t.split(" "):
            if w:
                words.append((w, c))
    lines, cur, cw = [], [], 0
    sp = d.textlength(" ", font=f)
    for w, c in words:
        ww = d.textlength(w, font=f)
        if cur and cw + sp + ww > max_w:
            lines.append((cur, cw))
            cur, cw = [], 0
        cur.append((w, c, ww))
        cw += (sp if len(cur) > 1 else 0) + ww
    if cur:
        lines.append((cur, cw))
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dl = ImageDraw.Draw(lay)
    lh = int(size * 1.28)
    left = 10 ** 9 if chars is None else int(chars)
    end = None
    for j, (ws, lw) in enumerate(lines):
        x = cx - lw / 2
        for w, c, ww in ws:
            if left <= 0:
                break
            part = w[:left]
            left -= len(w) + 1
            dl.text((x, y + j * lh), part, font=f, fill=c + (int(255 * a),), anchor="lm")
            end = (x + d.textlength(part, font=f), y + j * lh)
            x += ww + sp
    if caret and end is not None:
        dl.rectangle([end[0] + 4, end[1] - size * 0.45, end[0] + 9, end[1] + size * 0.45], fill=YEL + (int(255 * a),))
    img.alpha_composite(lay)
    return len(lines) * lh


def n_chars(parts) -> int:
    return len(" ".join(t for t, _ in parts))


LABEL_CPS = 12                                      # tốc độ gõ nhãn trên chart (ký tự/giây)


def cursor_icon(pressed: bool) -> Image.Image:
    """Con trỏ chuột mũi tên trắng viền đen (như Windows) – vẽ 3x rồi thu nhỏ cho mịn."""
    k = 3 * (0.88 if pressed else 1.0)
    pts = [(0, 0), (0, 34), (9, 26), (15, 40), (21, 37), (15, 24), (27, 24)]
    im = Image.new("RGBA", (130, 140), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(6 + x * k, 6 + y * k) for x, y in pts], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=6)
    return im.resize((43, 47), Image.LANCZOS)


# ------------------------------------------------------------------ kịch bản

def script(s: SMC):
    if s.system == "ob":
        return script_ob(s)
    return script_supply(s)


def script_ob(s: SMC):
    """Hệ thống #02 – Order Block + FVG."""
    sell = s.side == "sell"
    W_, Y_ = (255, 255, 255), YEL
    up, dn = ("tăng", "giảm") if sell else ("giảm", "tăng")
    return {
        "hook": [("Dùng", W_), ("Order Block", Y_), ("sai cách là", W_), ("cháy tài khoản.", Y_), ("Đây là cách dùng đúng", W_)],
        1: [("BƯỚC 1:", Y_), (f"Cú {dn} mạnh", W_), ("phá cấu trúc (BOS)", Y_)],
        2: [("BƯỚC 2:", Y_), ("Order Block", Y_), (f"= nến {up} cuối cùng trước cú {dn}", W_)],
        3: [("BƯỚC 3:", Y_), ("Kéo vùng", W_), ("Order Block", Y_), ("sang phải", W_)],
        4: [("BƯỚC 4:", Y_), ("OB mạnh phải để lại", W_), ("khoảng trống giá FVG", Y_)],
        5: [("BƯỚC 5:", Y_), ("Chờ giá", W_), ("quay về Order Block", Y_)],
        "5b": [(f"Nến {dn} đóng cửa", Y_), ("= xác nhận vào lệnh", W_)],
        6: [("MỤC TIÊU:", Y_), ("thanh khoản ở", W_), ("đáy gần nhất" if sell else "đỉnh gần nhất", Y_)],
        7: [("SL", Y_), ("trên Order Block ·" if sell else "dưới Order Block ·", W_), ("TP", Y_),
            (f"tại thanh khoản · R:R 1:{s.rr:.1f}", W_)],
        8: [("KẾT QUẢ:", Y_), (f"chạm TP · +{s.rr:.1f}R", W_)],
    }


def script_supply(s: SMC):
    sell = s.side == "sell"
    W_, Y_ = (255, 255, 255), YEL
    if sell:
        return {
            "hook": [("Bán ngược xu hướng là cách nhanh nhất để", W_), ("cháy tài khoản.", Y_),
                     ("Đây là mô hình BÁN của tổ chức", W_)],
            1: [("BƯỚC 1:", Y_), ("BOS xác nhận", W_), ("xu hướng giảm", Y_)],
            2: [("BƯỚC 2:", Y_), ("Xác định vùng giao dịch", W_), ("SWH – SWL", Y_)],
            3: [("BƯỚC 3:", Y_), ("Vẽ", W_), ("vùng cung", Y_), ("tại gốc cú giảm", W_)],
            4: [("BƯỚC 4:", Y_), ("Chỉ bán ở vùng", W_), ("Premium", Y_), ("– trên mức 50%", W_)],
            5: [("BƯỚC 5:", Y_), ("Chờ giá", W_), ("hồi về vùng cung", Y_)],
            "5b": [("Nến giảm đóng cửa", Y_), ("= tổ chức đang bán", W_)],
            6: [("MỤC TIÊU:", Y_), ("thanh khoản nằm dưới đáy", W_), ("SWL", Y_)],
            7: [("SL", Y_), ("trên vùng cung ·", W_), ("TP", Y_), (f"tại thanh khoản · R:R 1:{s.rr:.1f}", W_)],
            8: [("KẾT QUẢ:", Y_), (f"chạm TP · +{s.rr:.1f}R", W_)],
        }
    return {
        "hook": [("Mua ngược xu hướng là cách nhanh nhất để", W_), ("cháy tài khoản.", Y_),
                 ("Đây là mô hình MUA của tổ chức", W_)],
        1: [("BƯỚC 1:", Y_), ("BOS xác nhận", W_), ("xu hướng tăng", Y_)],
        2: [("BƯỚC 2:", Y_), ("Xác định vùng giao dịch", W_), ("SWL – SWH", Y_)],
        3: [("BƯỚC 3:", Y_), ("Vẽ", W_), ("vùng cầu", Y_), ("tại gốc cú tăng", W_)],
        4: [("BƯỚC 4:", Y_), ("Chỉ mua ở vùng", W_), ("Discount", Y_), ("– dưới mức 50%", W_)],
        5: [("BƯỚC 5:", Y_), ("Chờ giá", W_), ("hồi về vùng cầu", Y_)],
        "5b": [("Nến tăng đóng cửa", Y_), ("= tổ chức đang mua", W_)],
        6: [("MỤC TIÊU:", Y_), ("thanh khoản nằm trên đỉnh", W_), ("SWH", Y_)],
        7: [("SL", Y_), ("dưới vùng cầu ·", W_), ("TP", Y_), (f"tại thanh khoản · R:R 1:{s.rr:.1f}", W_)],
        8: [("KẾT QUẢ:", Y_), (f"chạm TP · +{s.rr:.1f}R", W_)],
    }


def label_times(s: SMC) -> dict:
    """Giây bắt đầu gõ từng nhãn trên chart (sau khi nét vẽ tương ứng xong)."""
    return {"bos": [T[1] + 1.35 + 0.45 * j for j in range(len(s.bos))], "sw": [T[2] + 0.45, T[2] + 0.9],
            "zone": T[3] + 1.35, "liq": T[6] + 1.35, "ob": T[2] + 1.0, "fvg": T[4] + 1.35}


def label_words(s: SMC) -> list:
    """(giây bắt đầu gõ, chữ) của mọi nhãn – dùng cho tiếng gõ phím."""
    lt = label_times(s)
    liq = "THANH KHOẢN (SSL)" if s.side == "sell" else "THANH KHOẢN (BSL)"
    out = [(t0, "BOS") for t0 in lt["bos"]]
    if s.system == "ob":
        return out + [(lt["ob"], "ORDER BLOCK"), (lt["fvg"], "FVG"), (lt["liq"], liq)]
    sw = ("SWH", "SWL") if s.side == "sell" else ("SWL", "SWH")
    zone = "VÙNG CUNG" if s.side == "sell" else "VÙNG CẦU"
    return out + [(lt["sw"][0], sw[0]), (lt["sw"][1], sw[1]), (lt["zone"], zone), (lt["liq"], liq)]


CTA_LINE = "Nếu thấy hữu ích, hãy thả tim, chia sẻ và theo dõi Pết, để nhận thêm những hệ thống giao dịch chọn lọc mỗi ngày nhé."


def narration(s: SMC) -> dict:
    """Lời đọc từng bước (viết theo cách nói, tránh viết tắt khó đọc)."""
    rr = f"{s.rr:.1f}".replace(".", " chấm ")                    # 2.7 → "2 chấm 7" cho giọng đọc rõ
    if s.system == "ob":
        sell = s.side == "sell"
        up, dn = ("tăng", "giảm") if sell else ("giảm", "tăng")
        return {"hook": "Dùng Order Block sai cách là cháy tài khoản. Đây là cách dùng đúng.",
                1: f"Bước một. Tìm cú {dn} mạnh, phá vỡ cấu trúc.",
                2: f"Bước hai. Order Block chính là cây nến {up} cuối cùng, ngay trước cú {dn} đó.",
                3: "Bước ba. Kéo vùng Order Block sang phải.",
                4: "Bước bốn. Order Block mạnh luôn để lại khoảng trống giá phía sau. Không có khoảng trống, bỏ qua.",
                5: "Bước năm. Kiên nhẫn chờ giá quay về Order Block.",
                "5b": f"Nến {dn} đóng cửa. Đây là tín hiệu vào lệnh.",
                6: "Mục tiêu là thanh khoản ở " + ("đáy gần nhất." if sell else "đỉnh gần nhất."),
                7: f"Cắt lỗ {'trên' if sell else 'dưới'} Order Block, chốt lời tại thanh khoản. Tỷ lệ một ăn {rr}.",
                8: f"Và giá chạy thẳng về mục tiêu. Lãi {rr} rờ.",
                "end": CTA_LINE}
    if s.side == "sell":
        return {"hook": "Bán ngược xu hướng là cách nhanh nhất để cháy tài khoản. Đây là mô hình bán của tổ chức.",
                1: "Bước một. Giá phá cấu trúc đáy cũ, xác nhận xu hướng giảm.",
                2: "Bước hai. Xác định vùng giao dịch, từ đỉnh xuống đáy của nhịp giảm.",
                3: "Bước ba. Vẽ vùng cung tại gốc của cú giảm.",
                4: "Bước bốn. Chỉ bán ở vùng giá đắt, phía trên mức năm mươi phần trăm.",
                5: "Bước năm. Kiên nhẫn chờ giá hồi về vùng cung.",
                "5b": "Nến giảm đóng cửa. Tổ chức đang bán.",
                6: "Mục tiêu là thanh khoản nằm dưới đáy.",
                7: f"Cắt lỗ trên vùng cung, chốt lời tại thanh khoản. Tỷ lệ một ăn {rr}.",
                8: f"Và giá chạy thẳng về mục tiêu. Lãi {rr} rờ.",
                "end": "Nếu thấy hữu ích, hãy thả tim, chia sẻ và theo dõi Pết, để nhận thêm những hệ thống giao dịch chọn lọc mỗi ngày nhé."}
    return {"hook": "Mua ngược xu hướng là cách nhanh nhất để cháy tài khoản. Đây là mô hình mua của tổ chức.",
            1: "Bước một. Giá phá cấu trúc đỉnh cũ, xác nhận xu hướng tăng.",
            2: "Bước hai. Xác định vùng giao dịch, từ đáy lên đỉnh của nhịp tăng.",
            3: "Bước ba. Vẽ vùng cầu tại gốc của cú tăng.",
            4: "Bước bốn. Chỉ mua ở vùng giá rẻ, phía dưới mức năm mươi phần trăm.",
            5: "Bước năm. Kiên nhẫn chờ giá hồi về vùng cầu.",
            "5b": "Nến tăng đóng cửa. Tổ chức đang mua.",
            6: "Mục tiêu là thanh khoản nằm trên đỉnh.",
            7: f"Cắt lỗ dưới vùng cầu, chốt lời tại thanh khoản. Tỷ lệ một ăn {rr}.",
            8: f"Và giá chạy thẳng về mục tiêu. Lãi {rr} rờ.",
            "end": "Nếu thấy hữu ích, hãy thả tim, chia sẻ và theo dõi Pết, để nhận thêm những hệ thống giao dịch chọn lọc mỗi ngày nhé."}


ORDER = ["hook", "reset", 1, 2, 3, 4, 5, "5b", 6, 7, 8, "end"]
MIN_DUR = {"hook": 3.4, "reset": 0.8, 1: 3.4, 2: 3.2, 3: 3.2, 4: 3.6, 5: 3.0, "5b": 2.6, 6: 3.0, 7: 3.4, 8: 4.4,
           "end": 4.5}
SPEED = 1.08                                        # tăng tốc giọng nhẹ cho khớp nhịp video


def retime(durs: dict):
    """Giãn mốc từng bước theo độ dài lời đọc (mỗi bước ≥ thời lượng tối thiểu của hình)."""
    t = 0.0
    for k in ORDER:
        T[k] = t
        lead = 0.15 if k == "hook" else 0.1
        t += max(MIN_DUR[k], lead + durs.get(k, 0) + 0.35)
    T["total"] = t


# mốc thời gian (giây)
T = {"hook": 0.0, "reset": 3.4, 1: 4.2, 2: 7.6, 3: 10.8, 4: 14.0, 5: 17.6, "5b": 20.6, 6: 23.2, 7: 26.2, 8: 29.6,
     "end": 34.0, "total": 36.5}


def footer(img):
    """Chân video (anh chốt 07/10/2026): lời mời theo dõi kênh."""
    _txt(img, (W / 2, 1765), "Follow DecodeFX Trading", sans("ExtraBold", 40), NAVY, 1)
    _txt(img, (W / 2, 1822), "Con đường ngắn nhất để trở thành 1 Protrader", sans("SemiBold", 30), GREY, 1)


def frames(s: SMC, cursor: bool = True):
    sc = Scene(s)
    sell = sc.sell
    txt = script(s)
    ob, z_lo, z_hi = s.zone
    swl_i = s.swl
    pre_end = swl_i + 4                                          # bước 1-4: nến tới ngay sau đáy nhịp
    lv = (s.sl, s.tp)
    cam_hook0 = sc.fit(s.swh - 18, s.hit + 5, lv)
    cam_hook1 = sc.fit(s.swh - 24, s.hit + 8, lv)
    cam_struct = sc.fit(sc.start, pre_end + 10, (z_hi, z_lo))
    cam_zone = sc.fit(s.swh - 22, s.k + 14, (z_hi, z_lo))
    cam_trade = sc.fit(s.swh - 18, s.k + 26, lv)
    cam_end = sc.fit(s.swh - 18, s.hit + 6, lv)
    keys = [(T["hook"], cam_hook0), (T["reset"], cam_hook1), (T[1] - 0.1, cam_struct), (T[5], cam_struct),
            (T[5] + 0.8, cam_zone), (T[6], cam_zone), (T[6] + 0.8, cam_trade), (T[8], cam_trade),
            (T[8] + 1.2, cam_end), (T["total"], cam_end)]

    def cam_at(t):
        for (ta, ca), (tb, cb) in zip(keys, keys[1:]):
            if t <= tb:
                return ca.mix(cb, ease((t - ta) / max(1e-6, tb - ta)))
        return keys[-1][1]

    def shown_at(t):
        if t < T["reset"]:
            return s.hit + 0.999
        if t < T[5] + 0.6:
            return pre_end + 0.999
        if t < T["5b"]:
            return lerp(pre_end + 1, s.k + 0.999, ease((t - T[5] - 0.6) / (T["5b"] - T[5] - 0.9)))
        if t < T[8] + 0.3:
            return s.k + 0.999
        return min(s.hit + 0.999, lerp(s.k + 1, s.hit + 0.999, (t - T[8] - 0.3) / 3.4))

    def on(step, t):
        """tiến độ vẽ của 1 bước (0..1); ở đoạn mồi mọi thứ đã vẽ xong."""
        if t < T["reset"]:
            return 1.0
        return max(0.0, min(1.0, (t - T[step] - 0.35) / 0.9))

    mark = Image.open(ROOT / "assets" / "brands" / "decode" / "official" / "decode_mark_1024.png").convert("RGBA")
    logo = mark.resize((60, 60), Image.LANCZOS)
    wm = mark.resize((440, 440), Image.LANCZOS)
    wm.putalpha(wm.getchannel("A").point(lambda a: int(a * 0.06)))
    total = T["total"]
    cur_up, cur_dn = cursor_icon(False), cursor_icon(True)
    LT = label_times(s)
    n_bos = len(s.bos)

    def strokes(X, Y, xr):
        out = _strokes(X, Y, xr)
        P = lambda x, y: (x / S, y / S)
        pts = [(LT["bos"][j], P((X(a) + X(b)) / 2, Y(p) + (20 if sell else -20) * S)) for j, (a, b, p) in enumerate(s.bos)]
        if s.system == "ob":
            pts.append((LT["ob"], P(*ob_label(X, Y))))
            fi, flo, fhi = s.fvg
            pts.append((LT["fvg"], P((X(fi - 1) + X(s.touch)) / 2, (Y(flo) + Y(fhi)) / 2)))
            widths = [3] * len(s.bos) + [0, 3, 17]
        else:
            pts.append((LT["zone"], P((X(ob) + xr - 20 * S) / 2, (Y(z_lo) + Y(z_hi)) / 2)))
            widths = [3] * len(s.bos) + [9, 17]                 # số ký tự nhãn → click ở ĐẦU ô chữ, không che chữ đang gõ
        pts.append((LT["liq"], P((X(swl_i) + X(s.k)) / 2 + 30 * S, Y(s.p_end) + (26 if sell else -26) * S)))
        pts = [(tc, (x - n * 7.5 - 12, y)) for (tc, (x, y)), n in zip(pts, widths)]
        out += [(tc - 0.08, tc, pt, pt) for tc, pt in pts]
        return sorted(out, key=lambda x: x[0])

    def _strokes(X, Y, xr):
        """Các nét vẽ (giây bắt đầu, giây kết thúc, điểm đầu, điểm cuối) – theo đúng nhịp on()."""
        P = lambda x, y: (x / S, y / S)
        out = []
        a0, dur = T[1] + 0.35, 0.9
        for j, (a, b, p) in enumerate(s.bos):
            out.append((a0 + dur * j / n_bos, a0 + dur * (j + 1) / n_bos, P(X(a), Y(p)), P(X(b), Y(p))))
        if s.system == "ob":
            hw = half_slot()
            out.append((T[2] + 0.35, T[2] + 0.9, P(X(ob) - hw, Y(z_hi)), P(X(ob) + hw, Y(z_lo))))
            out.append((T[3] + 0.35, T[3] + 1.25, P(X(ob) + hw, Y(z_lo)), P(xr - 20 * S, Y(z_lo))))
            fi, flo, fhi = s.fvg
            out.append((T[4] + 0.35, T[4] + 1.25, P(X(fi - 1), Y(fhi)), P(X(s.touch), Y(flo))))
        else:
            swh_pt = P(X(s.swh), Y(s.p_ext) + (-30 if sell else 30) * S)
            swl_pt = P(X(swl_i) - 40 * S, Y(s.p_end))
            out.append((T[2] + 0.35, T[2] + 0.7, swh_pt, swh_pt))
            out.append((T[2] + 0.8, T[2] + 1.15, swl_pt, swl_pt))
            out.append((T[3] + 0.35, T[3] + 1.25, P(X(ob), Y(z_hi)), P(xr - 20 * S, Y(z_lo))))
            out.append((T[4] + 0.35, T[4] + 1.25, P(X(s.swh), Y(s.p_ext)), P(X(swl_i), Y(s.p_end))))
        kc = P(X(s.k) + 34 * S, (Y(sc.Hh[s.k]) + Y(sc.L[s.k])) / 2)
        out.append((T["5b"] + 0.2, T["5b"] + 0.8, kc, kc))
        out.append((T[6] + 0.35, T[6] + 1.25, P(X(swl_i), Y(s.p_end)), P(xr - 20 * S, Y(s.p_end))))
        out.append((T[7] + 0.35, T[7] + 1.25, P(X(s.k) + 6 * S, Y(s.entry)), P(X(s.hit + 4), Y(s.tp))))
        return out

    cam_box = [None]

    def half_slot():
        c = cam_box[0]
        return (CH[2] - CH[0]) / (c.x1 - c.x0) * S * 0.45

    def ob_label(X, Y):
        """Vị trí nhãn ORDER BLOCK: sát cạnh trên (SELL) / dưới (BUY) của nến OB, căn trái."""
        return X(ob) - half_slot(), (Y(z_hi) - 24 * S) if sell else (Y(z_lo) + 24 * S)

    def cursor_at(t, segs):
        clicks = [(a, p0) for a, b, p0, p1 in segs]
        prev = (W * 0.72, H * 0.62)
        for a, b, p0, p1 in segs:
            if t < a:                                      # đang di chuyển tới điểm đầu nét kế tiếp
                k = ease((t - (a - 0.45)) / 0.45) if t > a - 0.45 else 0.0
                return lerp(prev[0], p0[0], k), lerp(prev[1], p0[1], k), False, clicks
            if t <= b:                                     # đang giữ chuột kéo nét
                k = ease((t - a) / max(1e-6, b - a))
                return lerp(p0[0], p1[0], k), lerp(p0[1], p1[1], k), True, clicks
            prev = p1
        return prev[0], prev[1], False, clicks

    for fno in range(int(total * FPS)):
        t = fno / FPS
        cam = cam_at(t)
        cam_box[0] = cam
        shown = shown_at(t)
        img = Image.new("RGBA", (W, H), (255, 255, 255, 255))
        img.alpha_composite(wm, (CH[2] // 2 - 220, (CH[1] + CH[3]) // 2 - 220))
        sc.axis(img, cam)
        lay = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        fade = 1.0 if t < T["reset"] - 0.35 else (max(0.0, (T["reset"] - t) / 0.35) if t < T["reset"] else 1.0)
        A = lambda k: int(255 * k * (fade if t < T["reset"] else 1))
        X, Y = (lambda i: sc.X(cam, i)), (lambda p: sc.Y(cam, p))
        xr = X(cam.x1)
        # --- vùng premium/discount (bước 4)
        k4 = on(4, t)
        if s.system == "ob" and k4 > 0 and (t < T["reset"] or t >= T[4]):
            fi, flo, fhi = s.fvg
            x0 = X(fi - 1)
            x1 = lerp(x0, X(s.touch), ease(k4))                 # FVG kéo tới khi giá quay về lấp vào
            fb = Image.new("RGBA", lay.size, (0, 0, 0, 0))
            ImageDraw.Draw(fb).rectangle([x0, min(Y(flo), Y(fhi)), x1, max(Y(flo), Y(fhi))],
                                         fill=(255, 152, 0, A(k4) // 9), outline=(239, 108, 0, A(k4)), width=3)
            lay.alpha_composite(fb)
            sc.typed(d, (x0 + x1) / 2, (Y(flo) + Y(fhi)) / 2, "FVG", (230, 81, 0), 28,
                     t, -1 if t < T["reset"] else LT["fvg"], a=A(1))
            if t >= T["reset"] and k4 < 1:
                sc.handles(d, [(x0, Y(fhi)), (x1, Y(flo))])
        if s.system != "ob" and k4 > 0 and (t < T["reset"] - 0.0 or t >= T[4]):
            mid = (s.p_ext + s.p_end) / 2
            x0 = X(s.swh)
            x1 = lerp(x0, xr, ease(k4))
            d.rectangle([x0, min(Y(s.p_ext), Y(mid)), x1, max(Y(s.p_ext), Y(mid))], fill=(242, 54, 69, A(k4) // 16))
            d.rectangle([x0, min(Y(mid), Y(s.p_end)), x1, max(Y(mid), Y(s.p_end))], fill=(8, 153, 129, A(k4) // 20))
            for p, name, wdt in ((s.p_ext, "100%", 2), (mid, "50% · CÂN BẰNG", 4), (s.p_end, "0%", 2)):
                col = (41, 98, 255) if wdt == 4 else (120, 123, 134)
                d.line([(x0, Y(p)), (x1, Y(p))], fill=col + (A(k4),), width=wdt * S // 2 + 1)
                if k4 > 0.7:
                    sc.label(d, x1 - 12 * S, Y(p) - 18 * S, name, col, 24, a=A(min(1, (k4 - 0.7) / 0.3)), anchor="rm")
            # đường chéo của công cụ Fibo
            for j in range(0, 40):
                a0, b0 = j / 40, (j + 0.5) / 40
                if b0 > ease(k4):
                    break
                d.line([(lerp(X(s.swh), X(swl_i), a0), lerp(Y(s.p_ext), Y(s.p_end), a0)),
                        (lerp(X(s.swh), X(swl_i), b0), lerp(Y(s.p_ext), Y(s.p_end), b0))],
                       fill=(120, 123, 134, A(k4) // 2), width=3)
        # --- vùng cung/cầu (bước 3)
        k3 = on(3, t)
        k2o = on(2, t)
        if s.system == "ob" and k2o > 0 and (t < T["reset"] or t >= T[2]):
            hw = half_slot()
            x0 = X(ob) - hw
            x1 = lerp(x0, X(ob) + hw, ease(min(1.0, k2o * 1.6)))
            if k3 > 0 and (t < T["reset"] or t >= T[3]):
                x1 = lerp(X(ob) + hw, xr - 20 * S, ease(k3))
            ob_l = Image.new("RGBA", lay.size, (0, 0, 0, 0))
            ImageDraw.Draw(ob_l).rectangle([x0, min(Y(z_lo), Y(z_hi)), x1, max(Y(z_lo), Y(z_hi))],
                                           fill=LAV + (A(1) // 2,), outline=PURPLE + (A(1),), width=3)
            lay.alpha_composite(ob_l)
            lx, ly = ob_label(X, Y)
            sc.typed(d, lx, ly, "ORDER BLOCK", PURPLE, 28, t, -1 if t < T["reset"] else LT["ob"], a=A(1), anchor="lm")
            if t >= T["reset"] and (k2o < 0.65 or 0 < k3 < 1):
                sc.handles(d, [(x0, Y(z_hi)), (x1, Y(z_lo))])
        if s.system != "ob" and k3 > 0 and (t < T["reset"] or t >= T[3]):
            x0 = X(ob)
            x1 = lerp(x0, xr - 20 * S, ease(k3))
            d.rectangle([x0, min(Y(z_lo), Y(z_hi)), x1, max(Y(z_lo), Y(z_hi))], fill=LAV + (A(k3) // 2,),
                        outline=PURPLE + (A(k3),), width=3)
            sc.typed(d, (x0 + x1) / 2, (Y(z_lo) + Y(z_hi)) / 2, "VÙNG CUNG" if sell else "VÙNG CẦU", PURPLE, 28,
                     t, -1 if t < T["reset"] else LT["zone"], a=A(1))
            if t >= T["reset"] and k3 < 1:
                sc.handles(d, [(x0, Y(z_hi)), (x1, Y(z_lo))])
        # --- BOS (bước 1)
        k1 = on(1, t)
        if k1 > 0:
            for j, (a, b, p) in enumerate(s.bos):
                kk = max(0.0, min(1.0, k1 * len(s.bos) - j))
                if kk <= 0:
                    continue
                x1 = lerp(X(a), X(b), ease(kk))
                d.line([(X(a), Y(p)), (x1, Y(p))], fill=PURPLE + (A(1),), width=3 * S // 2 + 1)
                sc.typed(d, (X(a) + X(b)) / 2, Y(p) + (20 if sell else -20) * S, "BOS", PURPLE, 26,
                         t, -1 if t < T["reset"] else LT["bos"][j], a=A(1))
                if t >= T["reset"] and kk < 1:
                    sc.handles(d, [(X(a), Y(p)), (x1, Y(p))])
        # --- SWH / SWL (bước 2)
        k2 = on(2, t)
        if k2 > 0 and s.system != "ob":
            for j, (i, p, name, up) in enumerate(((s.swh, s.p_ext, "SWH" if sell else "SWL", sell),
                                                  (swl_i, s.p_end, "SWL" if sell else "SWH", not sell))):
                t0 = -1 if t < T["reset"] else LT["sw"][j]
                if j == 0:
                    sc.typed(d, X(i), Y(p) + (-30 if up else 30) * S, name, INK, 28, t, t0, a=A(1))
                else:                                        # đáy/đỉnh nhịp: ghi bên trái nến, chừa chỗ nhãn thanh khoản
                    sc.typed(d, X(i) - 16 * S, Y(p), name, INK, 28, t, t0, a=A(1), anchor="rm")
        # --- hộp lệnh (bước 7) + vùng lời sáng dần khi chạy (bước 8): nằm DƯỚI nến như công cụ Long/Short TradingView
        k7 = on(7, t)
        if k7 > 0:
            x0 = X(s.k) + 6 * S
            x1 = lerp(x0, X(s.hit + 4), ease(k7))
            box = Image.new("RGBA", lay.size, (0, 0, 0, 0))
            db = ImageDraw.Draw(box)
            db.rectangle([x0, min(Y(s.entry), Y(s.sl)), x1, max(Y(s.entry), Y(s.sl))], fill=(242, 54, 69, A(k7) // 4))
            db.rectangle([x0, min(Y(s.entry), Y(s.tp)), x1, max(Y(s.entry), Y(s.tp))], fill=(8, 153, 129, A(k7) // 6))
            if shown > s.k + 1:
                ext = min(sc.L[s.k + 1:int(shown) + 1].min(), s.entry) if sell else max(sc.Hh[s.k + 1:int(shown) + 1].max(), s.entry)
                ext = max(ext, s.tp) if sell else min(ext, s.tp)
                db.rectangle([x0, min(Y(s.entry), Y(ext)), x1, max(Y(s.entry), Y(ext))], fill=(8, 153, 129, A(1) // 4))
            lay.alpha_composite(box)
        # --- nến
        sc.candles(d, cam, shown)
        # --- nến xác nhận (bước 5b)
        k5 = 1.0 if t < T["reset"] else max(0.0, min(1.0, (t - T["5b"] - 0.2) / 0.6))
        if k5 > 0 and shown >= s.k + 0.9:
            x = X(s.k)
            yc = (Y(sc.Hh[s.k]) + Y(sc.L[s.k])) / 2
            rx, ry = 34 * S, abs(Y(sc.Hh[s.k]) - Y(sc.L[s.k])) / 2 + 26 * S
            d.arc([x - rx, yc - ry, x + rx, yc + ry], -90, -90 + 360 * ease(k5), fill=(242, 54, 69, A(1)), width=4 * S)
        # --- thanh khoản (bước 6)
        k6 = on(6, t)
        if k6 > 0:
            x0 = X(swl_i)
            x1 = lerp(x0, xr - 20 * S, ease(k6))
            yv = Y(s.p_end)
            for xx in range(int(x0), int(x1), 26):
                d.line([(xx, yv), (min(xx + 14, x1), yv)], fill=(41, 98, 255, A(1)), width=3 * S // 2 + 1)
            sc.typed(d, (x0 + X(s.k)) / 2 + 30 * S, yv + (26 if sell else -26) * S,
                     "THANH KHOẢN (SSL)" if sell else "THANH KHOẢN (BSL)",       # giữa SWL và hộp lệnh: không đè nhãn TP
                     (41, 98, 255), 24, t, -1 if t < T["reset"] else LT["liq"], a=A(1))
        # --- nhãn hộp lệnh (vẽ sau nến)
        if k7 > 0:
            x0 = X(s.k) + 6 * S
            x1 = lerp(x0, X(s.hit + 4), ease(k7))
            if k7 > 0.6:
                a = A(min(1, (k7 - 0.6) / 0.4))
                f = sans("Bold", 23 * S)
                for p, name, col in ((s.sl, f"SL  {s.sl:.{sc.digits}f}", DN), (s.tp, f"TP  {s.tp:.{sc.digits}f}", UP),
                                     (s.entry, f"ENTRY  {s.entry:.{sc.digits}f}", INK)):
                    l_, t_, r_, b_ = d.textbbox((x1 - 8 * S, Y(p)), name, font=f, anchor="rm")
                    yy = Y(p) + (-(b_ - t_) if (p == s.sl) == sell else (b_ - t_)) * 0.9
                    d.rounded_rectangle([l_ - 8, yy - (b_ - t_) / 2 - 6, r_ + 8, yy + (b_ - t_) / 2 + 6], radius=6,
                                        fill=col + (a,))
                    d.text((x1 - 8 * S, yy), name, font=f, fill=(255, 255, 255, a), anchor="rm")
        img.alpha_composite(lay.resize((W, H), Image.LANCZOS))
        # ---- con chuột: tới điểm đầu → click → kéo theo nét đang vẽ (tọa độ 1x)
        if cursor and T[1] - 0.3 <= t < T[8]:
            segs = strokes(X, Y, xr)
            cx, cy, pressed, clicks = cursor_at(t, segs)
            for tc, (px, py) in clicks:
                if 0 <= t - tc < 0.35:
                    kr = (t - tc) / 0.35
                    rl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                    r = 10 + 34 * kr
                    ImageDraw.Draw(rl).ellipse([px - r, py - r, px + r, py + r], outline=(41, 98, 255, int(200 * (1 - kr))), width=4)
                    img.alpha_composite(rl)
            img.alpha_composite(cur_up if not pressed else cur_dn, (int(cx) - 3, int(cy) - 3))
        # ---- đầu trang
        img.alpha_composite(logo, (40, 70))
        _txt(img, (114, 100), "DecodeFx Trading", sans("ExtraBold", 34), INK, 1, "lm")
        _txt(img, (W - 40, 100), f"{s.symbol} · {s.tf}", sans("Bold", 30), GREY, 1, "rm")
        # ---- phụ đề bước hiện tại (dải xanh than)
        steps = ["hook", 1, 2, 3, 4, 5, "5b", 6, 7, 8]
        cur = None
        for st in steps:
            if t >= T[st] and (st != "hook" or t < T["reset"]):
                cur = st
        if t >= T["reset"] and t < T[1]:
            cur = None
        if cur is not None and t < T["end"]:
            k = min(1.0, (t - T[cur]) / 0.25)
            parts = txt[cur]
            band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            hgt = rich(Image.new("RGBA", (W, H)), W / 2, 0, parts, 50)
            y0 = 180
            ImageDraw.Draw(band).rounded_rectangle([40, y0 - 10, W - 40, y0 + hgt + 30], radius=22, fill=NAVY + (int(238 * k),))
            img.alpha_composite(band)
            rich(img, W / 2, y0 + 10 + 32, parts, 50, a=k)
        # ---- kết: thẻ kết quả + lời kêu gọi
        if t >= T["end"]:
            k = min(1.0, (t - T["end"]) / 0.4)
            band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(band).rounded_rectangle([40, 170, W - 40, 600], radius=26, fill=NAVY + (int(242 * k),))
            img.alpha_composite(band)
            _txt(img, (W / 2, 255), f"+{s.rr:.1f}R", sans("ExtraBold", 110), YEL, k)
            # 3 nút hành động bật lần lượt theo lời kêu gọi
            for j, (name, col) in enumerate((("THẢ TIM", (242, 54, 69)), ("CHIA SẺ", (41, 98, 255)),
                                              ("THEO DÕI", (8, 153, 129)))):
                kj = max(0.0, min(1.0, (t - T["end"] - 0.5 - 0.45 * j) / 0.3))
                if kj <= 0:
                    continue
                cx = W / 2 + (j - 1) * 320
                pill = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                sc_ = 0.7 + 0.3 * kj
                wd, ht = 140 * sc_, 38 * sc_
                ImageDraw.Draw(pill).rounded_rectangle([cx - wd, 375 - ht, cx + wd, 375 + ht], radius=int(ht),
                                                       fill=col + (int(255 * kj),))
                img.alpha_composite(pill)
                _txt(img, (cx, 375), name, sans("ExtraBold", int(36 * sc_)), (255, 255, 255), kj)
            _txt(img, (W / 2, 470), "để nhận thêm những hệ thống giao dịch", sans("Bold", 38), (255, 255, 255), k)
            _txt(img, (W / 2, 528), "CHỌN LỌC mỗi ngày từ DecodeFx Trading", sans("Bold", 38), YEL, k)
        footer(img)
        if 0 <= t - T["reset"] < 0.1:                                  # chớp nhẹ khi xoá trắng để bắt đầu
            img = Image.blend(img, Image.new("RGBA", (W, H), (255, 255, 255, 255)), 0.6)
        yield img.convert("RGB"), t


def cover(s: SMC, frame: Image.Image) -> Image.Image:
    """Thumbnail Reels: khung chart đủ hệ thống + kết quả, tiêu đề lớn, nhãn +R, thương hiệu.
    Chữ chính nằm trong vùng giữa (Facebook cắt 1:1 / 4:5 ở lưới Page vẫn đọc được)."""
    img = frame.convert("RGBA")
    sell = s.side == "sell"
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(top)
    d.rectangle([0, 0, W, 640], fill=(255, 255, 255, 255))           # che phụ đề cũ, nền sạch cho tiêu đề
    d.rounded_rectangle([40, 150, W - 40, 600], radius=30, fill=NAVY + (255,))
    img.alpha_composite(top)
    mark = Image.open(ROOT / "assets" / "brands" / "decode" / "official" / "decode_mark_1024.png").convert("RGBA")
    img.alpha_composite(mark.resize((60, 60), Image.LANCZOS), (40, 70))
    _txt(img, (114, 100), "DecodeFx Trading", sans("ExtraBold", 34), INK, 1, "lm")
    _txt(img, (W - 40, 100), f"{s.symbol} · {s.tf}", sans("Bold", 30), GREY, 1, "rm")
    chip = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(chip).rounded_rectangle([W / 2 - 170, 190, W / 2 + 170, 250], radius=30, fill=YEL + (255,))
    img.alpha_composite(chip)
    _txt(img, (W / 2, 220), "SMC · 5 BƯỚC", sans("ExtraBold", 34), NAVY, 1)
    _txt(img, (W / 2, 340), "MÔ HÌNH BÁN" if sell else "MÔ HÌNH MUA", sans("ExtraBold", 118), YEL, 1)
    _txt(img, (W / 2, 470), "CỦA TỔ CHỨC", sans("ExtraBold", 118), (255, 255, 255), 1)
    _txt(img, (W / 2, 555), f"Lệnh thật · R:R 1:{s.rr:.1f}", sans("Bold", 36), (200, 210, 235), 1)
    badge = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    db = ImageDraw.Draw(badge)
    db.rectangle([0, CH[3] + 2, W, 1835], fill=(255, 255, 255, 255))     # dưới chart: không che nhãn trên chart
    db.rounded_rectangle([W / 2 - 230, 1700, W / 2 + 230, 1830], radius=40, fill=(8, 153, 129, 255))
    img.alpha_composite(badge)
    _txt(img, (W / 2, 1765), f"+{s.rr:.1f}R", sans("ExtraBold", 110), (255, 255, 255), 1)
    return img.convert("RGB")


# Câu giật tít thumbnail – 2 kiểu anh chốt 08/10/2026:
#   kiểu 3 "cảnh báo": ĐỪNG VÀO LỆNH / KHI CHƯA BIẾT CÁI NÀY
#   kiểu 4 "như cá mập": BÁN ĐÚNG ĐỈNH / NHƯ CÁ MẬP
# Không dùng câu hứa chắc thắng; không nói xấu sàn (Page mang thương hiệu sàn).
BAIT = {
    "sell": [("ĐỪNG VÀO LỆNH", "KHI CHƯA BIẾT CÁI NÀY"), ("BÁN ĐÚNG ĐỈNH", "NHƯ CÁ MẬP"),
             ("ĐỪNG BÁN VÀNG", "KHI CHƯA BIẾT CÁI NÀY"), ("BÁN ĐÚNG ĐỈNH", "NHƯ TỔ CHỨC")],
    "buy": [("ĐỪNG VÀO LỆNH", "KHI CHƯA BIẾT CÁI NÀY"), ("MUA ĐÚNG ĐÁY", "NHƯ CÁ MẬP"),
            ("ĐỪNG MUA VÀNG", "KHI CHƯA BIẾT CÁI NÀY"), ("MUA ĐÚNG ĐÁY", "NHƯ TỔ CHỨC")],
}


def bait_text(s: SMC, seed=None) -> tuple[str, str, str]:
    """(nhãn hệ thống, dòng 1, dòng 2) – xoay vòng 2 kiểu câu theo ngày; câu "ĐỪNG BÁN/MUA VÀNG" chỉ dùng cho XAUUSD."""
    opts = [o for o in BAIT[s.side] if s.symbol == "XAUUSD" or "VÀNG" not in o[0]]
    i = (seed if isinstance(seed, int) else s.d.index[s.k].toordinal()) % len(opts)
    zone = "ORDER BLOCK" if s.system == "ob" else ("VÙNG CUNG" if s.side == "sell" else "VÙNG CẦU")
    return f"SMC · {zone}", *opts[i]


def pick_music(seed=None):
    tracks = [p for d in MUSIC_DIRS for p in d.glob("*.mp3")]
    random.Random(seed).shuffle(tracks)
    return tracks[0] if tracks else None


def make(s: SMC, folder: Path, music: Path | None = None, seed=None, voice_on: bool = False,
         voice_ref: Path | None = None) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    voices = []
    if voice_on:                                  # giọng Thái (nhân bản) – đọc từng bước, thời lượng bước theo giọng
        from src.reels import voice
        lines = narration(s)
        keys = list(lines)
        wavs = voice.synth([lines[k] for k in keys], folder / "voice", ref=voice_ref)
        durs = {}
        for k, w in zip(keys, wavs):
            fast = w.with_name(w.stem + "_fast.wav")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(w), "-af", f"atempo={SPEED}", str(fast)], check=True)
            durs[k] = voice.duration(fast)
            voices.append((fast, k))
        retime(durs)
        voices = [(f, T[k] + (0.15 if k == "hook" else 0.1)) for f, k in voices]
    total = T["total"]
    silent = folder / "reel.video.mp4"
    wr = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                           "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
    thumb = None
    for img, t in frames(s):
        wr.stdin.write(img.tobytes())
        if thumb is None and t >= 1.0:
            thumb = img
        if t < T["end"] - 0.1:
            base_frame = img                                # khung cuối trước thẻ kết: đủ hệ thống + kết quả
    wr.stdin.close()
    if wr.wait():
        raise RuntimeError("ffmpeg lỗi khi dựng hình")
    music = music or pick_music(seed)
    events = [(T["reset"], "whoosh", 0.6)] + [(T[k] + 0.35, "click", 0.9) for k in (1, 2, 3, 4, 6, 7)]
    events += [(T[2] + 0.8, "click", 0.9), (T["5b"] + 0.2, "click", 0.9)]
    events += [(T[k] + 0.4, "pen", 0.35) for k in (1, 3, 4, 6, 7)]
    events += [(T[8] + 3.2, "ting", 0.8), (T["end"], "whoosh", 0.5)]
    rnd = random.Random(7)
    words = label_words(s)
    for t0, w in words:                                       # tiếng gõ phím theo từng ký tự nhãn
        events.append((t0 - 0.08, "click", 0.8))
        for c, ch in enumerate(w):
            if ch != " ":
                events.append((t0 + c / LABEL_CPS, "key", rnd.uniform(0.35, 0.5)))
    mix(silent, voices, events, total, folder / "reel.mp4", music, music_ss=8.0,
        music_vol=0.6, music_fade=1.5)                       # kênh này: nhạc nền to, sôi động
    silent.unlink(missing_ok=True)
    from src.reels.smc import cover as _cv                # thumbnail giật tít (anh chốt 08/10/2026: kiểu 3 + kiểu 4)
    system, l1, l2 = bait_text(s, seed)
    _cv.bait(s, base_frame, system, l1, l2).save(folder / "thumb.jpg", quality=92)
    info = {"symbol": s.symbol, "tf": s.tf, "side": s.side, "time": s.d.index[s.k].isoformat(), "entry": s.entry,
            "sl": s.sl, "tp": s.tp, "rr": s.rr, "bars_to_tp": s.hit - s.k, "music": music.name if music else None}
    (folder / "setup.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"video": folder / "reel.mp4", "thumb": folder / "thumb.jpg", "info": info}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick", type=int, default=0)
    ap.add_argument("--out")
    ap.add_argument("--system", default="supply", choices=["supply", "ob"])
    ap.add_argument("--voice", action="store_true", help="lồng giọng nhân bản")
    ap.add_argument("--voice-ref", help="file giọng mẫu (mặc định giọng Thái)")
    a = ap.parse_args()
    setups = find(system=a.system)
    s = setups[a.pick]
    r = make(s, Path(a.out) if a.out else OUTPUT / "decode-trading" / "reels" / f"smc_{a.pick}", voice_on=a.voice,
             voice_ref=Path(a.voice_ref) if a.voice_ref else None)
    print(json.dumps({k: str(v) for k, v in r.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
