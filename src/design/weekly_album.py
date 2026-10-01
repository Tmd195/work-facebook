"""Album bài Tổng quan tuần mới: bìa (thiên hướng 4 mã) → lịch tin cả tuần → 4 biểu đồ D1 kèm diễn giải."""
from PIL import Image, ImageDraw

from src.chart_tools import build_real
from src.config import CONFIG
from src.design import carousel
from src.design.common import SIZE_4X5, fit, sans, save, wrap
from src.design.palette import CARD, DIVIDER, SUB, TRACK
from src.design.styles.block import CREAM, DOWN, GREEN, INK, LIME, MUTED, UP

W, H = SIZE_4X5
M = 60
BIAS_COL = {"tăng": UP, "giảm": DOWN, "đi ngang": MUTED}
NAMES = {"DXY": "Chỉ số USD", "XAUUSD": "Vàng", "EURUSD": "Euro", "GBPUSD": "Bảng Anh"}


def cover(path, ctx: dict, res: dict):
    img = Image.new("RGBA", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 640], fill=GREEN)
    d.text((M, 56), CONFIG["brand"]["name"], font=sans("Bold", 26), fill=LIME)
    d.text((W - M, 58), "FOREX · VÀNG", font=sans("SemiBold", 22), fill=SUB, anchor="ra")
    tag = "TỔNG QUAN TUẦN MỚI"
    tw = d.textlength(tag, font=sans("ExtraBold", 30)) + 48
    d.rounded_rectangle([M, 120, M + tw, 178], radius=29, fill=LIME)
    d.text((M + 24, 149), tag, font=sans("ExtraBold", 30), fill=GREEN, anchor="lm")
    d.text((M, 206), ctx["tuần"], font=sans("Bold", 34), fill=SUB)
    y = 270
    for line in wrap(d, res["title"], sans("ExtraBold", 66), W - 2 * M, max_lines=4):
        d.text((M - 3, y), line, font=sans("ExtraBold", 66), fill=CREAM)
        y += 82

    d.text((M, 680), "THIÊN HƯỚNG TUẦN MỚI", font=sans("ExtraBold", 24), fill=GREEN)
    outlook = {o["symbol"]: o for o in res["outlook"]}
    y = 730
    for code in ("DXY", "XAUUSD", "EURUSD", "GBPUSD"):
        m = ctx["markets"][code]
        o = outlook.get(code, {"bias": "đi ngang"})
        d.rectangle([M, y, W - M, y + 118], fill=CARD)
        d.text((M + 28, y + 30), code, font=sans("ExtraBold", 34), fill=INK)
        d.text((M + 28, y + 76), NAMES[code], font=sans("Medium", 20), fill=MUTED)
        chg = m["thay_đổi_tuần_%"]
        d.text((M + 300, y + 30), f"{m['giá_đóng_cửa_tuần']}", font=sans("Bold", 32), fill=INK)
        d.text((M + 300, y + 76), f"Tuần qua {'+' if chg >= 0 else ''}{chg:.2f}%", font=sans("SemiBold", 20),
               fill=UP if chg >= 0 else DOWN)
        col = BIAS_COL[o["bias"]]
        label = o["bias"].upper()
        bw = d.textlength(label, font=sans("ExtraBold", 26)) + 44
        d.rounded_rectangle([W - M - 28 - bw, y + 34, W - M - 28, y + 84], radius=12, fill=col)
        d.text((W - M - 28 - bw / 2, y + 59), label, font=sans("ExtraBold", 26), fill=CREAM, anchor="mm")
        y += 132
    carousel._footer(d, "Lướt xem lịch tin & biểu đồ  →")
    save(img, path)


def calendar_card(path, ctx: dict):
    img = Image.new("RGBA", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 200], fill=GREEN)
    d.text((M, 40), f"TỔNG QUAN TUẦN MỚI · {ctx['tuần']}", font=sans("Bold", 21), fill=SUB)
    d.text((M - 3, 80), "Lịch tin quan trọng", font=sans("ExtraBold", 60), fill=CREAM)
    events = ctx["calendar"]
    y = 230
    if not events:
        d.text((M, y + 20), "Tuần này không có tin đỏ của USD / EUR / GBP.", font=sans("Bold", 30), fill=MUTED)
    day = None
    for e in events:
        if y > H - 120:
            d.text((M, y), f"+ {len(events) - events.index(e)} tin khác – xem trong bài viết", font=sans("Medium", 20), fill=MUTED)
            break
        if e["day"] != day:
            day = e["day"]
            d.rectangle([M, y, W - M, y + 44], fill=TRACK)
            d.text((M + 20, y + 22), day.upper(), font=sans("ExtraBold", 22), fill=CREAM, anchor="lm")
            y += 54
        d.text((M + 20, y + 20), e["time"], font=sans("ExtraBold", 26), fill=GREEN, anchor="lm")
        d.text((M + 120, y + 20), e["currency"], font=sans("Bold", 22), fill=DOWN, anchor="lm")
        d.text((M + 200, y + 20), fit(d, e["title"], sans("SemiBold", 24), W - 2 * M - 420), font=sans("SemiBold", 24),
               fill=INK, anchor="lm")
        right = f"{e['forecast'] or '-'} / {e['previous'] or '-'}"
        d.text((W - M - 10, y + 20), right, font=sans("Medium", 21), fill=MUTED, anchor="rm")
        y += 46
        d.line([(M + 120, y - 4), (W - M, y - 4)], fill=DIVIDER, width=1)
    d.text((W - M, H - 40), "Dự báo / Kỳ trước · giờ Việt Nam", font=sans("Medium", 18), fill=MUTED, anchor="rm")
    d.text((M, H - 40), CONFIG["brand"]["handle"], font=sans("Bold", 18), fill=GREEN, anchor="lm")
    save(img, path)


def render_album(out_dir, ctx: dict, res: dict) -> list:
    p = lambda k: out_dir / f"weekly_{k:02d}.png"
    for old in out_dir.glob("weekly_*.png"):
        old.unlink()
    cover(p(0), ctx, res)
    calendar_card(p(1), ctx)
    outlook = {o["symbol"]: o for o in res["outlook"]}
    header = f"TỔNG QUAN TUẦN MỚI · {ctx['tuần']}"
    for k, code in enumerate(("DXY", "XAUUSD", "EURUSD", "GBPUSD"), 2):
        ch, facts = build_real({"symbol": code, "tf": "D1", "tools": ["structure", "sr_zones", "ema50"]})
        o = outlook.get(code, {"bias": "đi ngang", "note": ""})
        carousel.render_slide(p(k), header, 0, 0, k - 1, 4, f"{code}: thiên hướng {o['bias']}", o["note"],
                              ch.render(640, 420, scale=3), facts[0] if facts else "")
    return [p(k) for k in range(6)]
