"""Album post KIẾN THỨC – form C "Sổ tay Trader" (anh chốt 08/10/2026). Chủ đề mẫu: Order Block (7 ảnh 1080×1350).

1 bìa · 2 OB là gì · 3 cách vẽ · 4 OB hợp lệ cần FVG · 5 cách vào lệnh · 6 checklist · 7 ví dụ lệnh vàng THẬT (vẽ tay trên giá thật)

    python -m src.design.edu_album        # → output/decode-trading/<ngày>/album_ob/01..07.png
"""
import math
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

from src.config import OUTPUT, TZ
from src.design.edu_styles import (CANDLES, FVG_I, H, NB_INK, NB_RED, OB_I, RET_I, W, Plot, candles, highlight,
                                   jitter_line, lora, nb_base, notebook_cover, notebook_inner)

BLUE, GREEN = (40, 90, 200), (30, 130, 70)


def title(d, n, text):
    d.text((150, 100), f"{n}. {text}", font=lora(64, 700), fill=NB_INK)
    jitter_line(d, [(150, 190), (150 + d.textlength(f"{n}. {text}", font=lora(64, 700)), 190)], NB_RED, 4, 1.5, n)


def box(d, x0, y0, x1, y1, col, seed):
    jitter_line(d, [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], col, 4, 1.8, seed)


def note_lines(d, x, y, lines, size=38, step=58, col=NB_INK, italic=True):
    for j, t in enumerate(lines):
        d.text((x, y + j * step), t, font=lora(size, 600, italic), fill=col)


def slide_draw():
    img, d = nb_base(3)
    title(d, 2, "Cách vẽ Order Block")
    note_lines(d, 150, 225, ["B1: tìm cú phá cấu trúc mạnh (BOS).", "B2: chọn nến ngược màu CUỐI CÙNG trước cú đó.",
                             "B3: kẻ hộp từ đỉnh tới đáy cây nến đó,", "      kéo sang phải chờ giá quay lại."], 36, 54)
    P = Plot((170, 520, W - 90, 1080))
    candles(d, P, NB_INK, NB_INK, "notebook")
    o, h, l, c = CANDLES[OB_I]
    x0, x1 = P.X(OB_I) - P.bw, P.X(OB_I) + P.bw
    box(d, x0, P.Y(h), x1, P.Y(l), NB_RED, 31)
    jitter_line(d, [(x1, (P.Y(h) + P.Y(l)) / 2), (P.X(RET_I + 2), (P.Y(h) + P.Y(l)) / 2)], NB_RED, 4, 1.2, 33)
    xe = P.X(RET_I + 2)
    ym = (P.Y(h) + P.Y(l)) / 2
    jitter_line(d, [(xe - 22, ym - 16), (xe, ym), (xe - 22, ym + 16)], NB_RED, 4, 0.8, 34)
    d.text((x0 - 10, P.Y(l) + 18), "B2 + B3", font=lora(34, 700, True), fill=NB_RED)
    jitter_line(d, [(P.X(0), P.Y(53)), (P.X(6), P.Y(53))], BLUE, 4, 1.5, 35)
    d.text((P.X(1), P.Y(53) - 48), "B1: BOS", font=lora(34, 700, True), fill=BLUE)
    note_lines(d, 150, 1110, ["Mẹo: dùng cả râu nến (đỉnh – đáy), không chỉ thân."], 34, 50, NB_RED)
    return img


def slide_fvg():
    img, d = nb_base(4)
    title(d, 3, "OB hợp lệ phải có FVG")
    note_lines(d, 150, 225, ["FVG = khoảng trống giá giữa nến 1 và nến 3", "trong cú phá cấu trúc.",
                             "Có FVG => tổ chức vào lệnh mạnh, OB đáng tin.", "Không có FVG => BỎ QUA."], 36, 54)
    P = Plot((170, 520, W - 90, 1080))
    candles(d, P, NB_INK, NB_INK, "notebook")
    fl, fh = CANDLES[FVG_I - 1][1], CANDLES[FVG_I + 1][2]
    img = highlight(img, (P.X(FVG_I - 1), P.Y(fh), P.X(FVG_I + 3), P.Y(fl)))
    d = ImageDraw.Draw(img)
    for k, i in enumerate((FVG_I - 1, FVG_I, FVG_I + 1)):
        d.text((P.X(i), P.Y(CANDLES[i][2]) + 30 if k != 1 else P.Y(CANDLES[i][2]) + 30), str(k + 1), font=lora(34, 700, True),
               fill=BLUE, anchor="mm")
    d.text((P.X(FVG_I + 3) + 14, P.Y((fl + fh) / 2) - 22), "FVG", font=lora(40, 700, True), fill=NB_INK)
    o, h, l, c = CANDLES[OB_I]
    box(d, P.X(OB_I) - P.bw, P.Y(h), P.X(OB_I) + P.bw, P.Y(l), NB_RED, 41)
    d.text((P.X(OB_I) - P.bw, P.Y(l) + 18), "OB", font=lora(36, 700, True), fill=NB_RED)
    note_lines(d, 150, 1110, ["Khoảng trống càng rõ, OB càng mạnh."], 34, 50, NB_RED)
    return img


def slide_entry():
    img, d = nb_base(5)
    title(d, 4, "Cách vào lệnh với OB")
    note_lines(d, 150, 225, ["Chờ giá QUAY VỀ chạm OB – không đuổi giá.", "Có nến xác nhận đảo chiều => vào lệnh.",
                             "SL: dưới đáy OB · TP: đỉnh gần nhất (thanh khoản)."], 36, 54)
    P = Plot((170, 470, W - 90, 1060), lo=30, hi=80)
    candles(d, P, NB_INK, NB_INK, "notebook")
    o, h, l, c = CANDLES[OB_I]
    box(d, P.X(OB_I) - P.bw, P.Y(h), P.X(RET_I + 3), P.Y(l), NB_RED, 51)
    cx, cy = P.X(RET_I + 1), P.Y(CANDLES[RET_I + 1][2])
    jitter_line(d, [(cx + 44 * math.cos(a / 18 * 2 * math.pi), cy + 36 * math.sin(a / 18 * 2 * math.pi)) for a in range(20)],
                BLUE, 4, 2.0, 52)
    d.text((cx - 190, cy + 62), "nến xác nhận", font=lora(30, 700, True), fill=BLUE, anchor="mm")
    ysl = P.Y(l - 1.5)
    jitter_line(d, [(P.X(RET_I), ysl), (P.X(len(CANDLES) - 1), ysl)], NB_RED, 4, 1.2, 53)
    d.text((P.X(len(CANDLES) - 1) + 8, ysl), "SL", font=lora(34, 700, True), fill=NB_RED, anchor="lm")
    ytp = P.Y(CANDLES[7][1])
    jitter_line(d, [(P.X(7), ytp), (P.X(len(CANDLES) - 1), ytp)], GREEN, 4, 1.2, 54)
    d.text((P.X(len(CANDLES) - 1) + 8, ytp), "TP", font=lora(34, 700, True), fill=GREEN, anchor="lm")
    note_lines(d, 150, 1100, ["R:R tối thiểu 1:2 mới vào – không đủ thì bỏ."], 34, 50, NB_RED)
    return img


def slide_check():
    img, d = nb_base(6)
    title(d, 5, "Checklist trước khi vào lệnh")
    items = ["Có BOS – phá cấu trúc rõ ràng", "OB là nến ngược màu CUỐI CÙNG", "Có FVG phía sau OB",
             "Giá quay về chạm OB lần đầu", "Có nến xác nhận đảo chiều", "R:R ≥ 1:2"]
    for j, t in enumerate(items):
        y = 260 + j * 140
        jitter_line(d, [(160, y), (220, y), (220, y + 60), (160, y + 60), (160, y)], NB_INK, 4, 1.4, 60 + j)
        jitter_line(d, [(170, y + 30), (188, y + 52), (238, y - 8)], NB_RED, 6, 1.0, 70 + j)
        d.text((260, y + 30), t.replace("≥", ">="), font=lora(42, 600, True), fill=NB_INK, anchor="lm")
    img = highlight(img, (150, 1110, 900, 1160))
    d = ImageDraw.Draw(img)
    d.text((150, 1090), "Thiếu 1 ô => KHÔNG vào lệnh.", font=lora(44, 700), fill=NB_RED)
    return img


def slide_real(s):
    """Lệnh THẬT: vẽ tay nến vàng M15 quanh lệnh Order Block (dữ liệu giá thật)."""
    img, d = nb_base(7)
    title(d, 6, f"Ví dụ thật: {s.symbol} M15")
    ob, zlo, zhi = s.zone
    i0, i1 = max(0, ob - 12), min(len(s.d) - 1, s.hit + 2)
    seg = s.d.iloc[i0:i1 + 1]
    lo, hi = min(seg.low.min(), s.sl), max(seg.high.max(), s.tp)
    pad = (hi - lo) * 0.08
    n = i1 - i0 + 1
    P = Plot((170, 330, W - 140, 1010), lo=lo - pad, hi=hi + pad, n=n)
    O, Hh, L, C = (s.d[c].to_numpy() for c in ("open", "high", "low", "close"))
    for k, i in enumerate(range(i0, i1 + 1)):
        x = P.X(k)
        d.line([(x, P.Y(Hh[i])), (x, P.Y(L[i]))], fill=NB_INK, width=2)
        ya, yb = sorted((P.Y(O[i]), P.Y(C[i])))
        r = [x - P.bw / 2, ya, x + P.bw / 2, max(yb, ya + 2)]
        d.rectangle(r, fill=NB_INK if C[i] < O[i] else (250, 246, 234), outline=NB_INK, width=2)
    X = lambda i: P.X(i - i0)
    box(d, X(ob) - P.bw, P.Y(zhi), X(s.k) + P.bw, P.Y(zlo), NB_RED, 81)
    d.text((X(ob) - P.bw, P.Y(zlo) + 14), "OB", font=lora(34, 700, True), fill=NB_RED)
    if s.fvg:
        fi, flo, fhi = s.fvg
        img = highlight(img, (X(fi - 1), P.Y(fhi), X(fi + 1), P.Y(flo)))
        d = ImageDraw.Draw(img)
        d.text((X(fi + 1) + 8, P.Y(fhi) + 6), "FVG", font=lora(30, 700, True), fill=NB_INK)
    for p, name, col in ((s.sl, "SL", NB_RED), (s.tp, "TP", GREEN), (s.entry, "Entry", BLUE)):
        jitter_line(d, [(X(s.k), P.Y(p)), (P.X(n - 1) + 10, P.Y(p))], col, 3, 0.8, int(p) % 97)
        d.text((P.X(n - 1) + 18, P.Y(p)), name, font=lora(30, 700, True), fill=col, anchor="lm")
    dt = s.d.index[s.k].astimezone(TZ)
    note_lines(d, 150, 1040, [f"{'Mua' if s.side == 'buy' else 'Bán'} {dt:%d/%m} tại {s.entry:,.2f} · SL {s.sl:,.2f} · TP {s.tp:,.2f}",
                              f"Kết quả: chạm TP – lãi {s.rr:.1f}R (dữ liệu quá khứ)."], 34, 52)
    img = highlight(img, (150, 1150, 830, 1196))
    d = ImageDraw.Draw(img)
    d.text((150, 1130), "Lưu lại & theo dõi để nhận hệ thống mới!", font=lora(40, 700), fill=NB_RED)
    return img


def build(folder: Path, s) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    slides = [notebook_cover(), notebook_inner(), slide_draw(), slide_fvg(), slide_entry(), slide_check(), slide_real(s)]
    paths = []
    for k, im in enumerate(slides, 1):
        p = folder / f"{k:02d}.png"
        im.save(p)
        paths.append(p)
    return paths


if __name__ == "__main__":
    from src.reels.smc.setup import find
    obs = [x for x in find(system="ob") if x.symbol == "XAUUSD"]
    s = next((x for x in obs if x.d.index[x.k].isoformat() == "2026-08-10T01:30:00+00:00"), obs[0])   # cùng lệnh Reels OB
    out = OUTPUT / "decode-trading" / datetime.now(TZ).strftime("%Y-%m-%d") / "album_ob"
    for p in build(out, s):
        print(p)
