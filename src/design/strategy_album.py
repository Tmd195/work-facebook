"""Album ảnh bài Chiến lược XAUUSD: 1 banner + các biểu đồ phân tích khổ lớn (D1, H4, H1 tổng quan, H1 từng kịch bản).
Phần chữ phân tích nằm trong caption, nên ảnh chỉ tập trung vào biểu đồ."""
from datetime import datetime

from PIL import Image, ImageDraw

from src.chart_tools import build_real, ema, load
from src.config import CONFIG, TZ
from src.design import carousel
from src.design.common import SIZE_4X5, fit, sans, save, wrap
from src.design.styles.block import CREAM, DOWN, GREEN, LIME, MUTED, UP
from src.design.tvchart import TV, TVChart
from src.strategy_data import session_windows

W, H = SIZE_4X5
M = 60
SUB = (170, 200, 185)
CHART_CSS = (640, 420)          # khung ngang, chừa chỗ cho phần diễn giải bên dưới


def money(x: float) -> str:
    return f"{x:,.1f}".rstrip("0").rstrip(".") if x >= 1000 else f"{x:g}"


def zone_txt(z) -> str:
    lo, hi = min(z), max(z)
    return money(lo) if abs(hi - lo) < 0.5 else f"{money(lo)} – {money(hi)}"


# ===================================================================== biểu đồ

def _zone_rects(ch: TVChart, result: dict, start: int):
    lv = result["levels"]
    for key, col, label in (("resistance_strong", TV["down"], "Kháng cự mạnh"),
                            ("resistance_near", TV["down"], "Kháng cự gần"),
                            ("support_near", TV["up"], "Hỗ trợ gần"),
                            ("support_extended", TV["up"], "Hỗ trợ mở rộng")):
        ch.rect(start, None, min(lv[key]) - 0.5, max(lv[key]) + 0.5, col, label, 0.12)
        ch.include(min(lv[key]), max(lv[key]))
    ch.price_line(lv["pivot"]["price"], TV["orange"], "Then chốt", style=0, width=2)


def chart_d1(result: dict) -> Image.Image:
    ch, _ = build_real({"symbol": "XAUUSD", "tf": "D1", "tools": ["ichimoku", "structure"]})
    _zone_rects(ch, result, len(ch.times) - 30)
    return ch.render(*CHART_CSS, scale=3)


def chart_h4(result: dict) -> Image.Image:
    ch, _ = build_real({"symbol": "XAUUSD", "tf": "H4", "tools": ["fib", "bos_choch", "ema50"]})
    _zone_rects(ch, result, len(ch.times) - 40)
    return ch.render(*CHART_CSS, scale=3)


def _h1_base(now: datetime, bars: int = 80, right: int = 18):
    full = list(load("XAUUSD", "H1"))
    candles = full[-bars:]
    ch = TVChart("XAUUSD", "1H", candles, 2, right_offset=right)
    for name, (s, e) in session_windows(now).items():
        rows = [(i, c) for i, c in enumerate(candles) if s <= c.date.astimezone(TZ) < min(e, now)]
        if rows:
            hi, lo = max(c.high for _, c in rows), min(c.low for _, c in rows)
            ch.rect(rows[0][0], rows[-1][0], lo, hi, TV["blue"], f"Phiên {name}", 0.07, "left")
    return ch, candles, full


def chart_h1_overview(result: dict, now: datetime) -> Image.Image:
    ch, candles, full = _h1_base(now, right=8)
    _zone_rects(ch, result, 0)
    ch.line(ema([c.close for c in full], 50)[-len(candles):], TV["orange"], "EMA 50")
    return ch.render(*CHART_CSS, scale=3)


def chart_h1_scenario(s: dict, now: datetime) -> Image.Image:
    ch, candles, _ = _h1_base(now, bars=70, right=22)
    col = TV["down"] if s["side"] == "SELL" else TV["up"]
    last, price = len(candles) - 1, candles[-1].close
    e = sorted(s["entry"][:2])
    tag = "Kịch bản chính" if s["role"] == "chính" else "Kịch bản phụ"
    ch.rect(last + 1, last + 21, e[0], e[1], col, f"{tag} · {s['side']}", 0.25)
    ch.include(e[0], e[1], s["sl"], *s["tp"][:3])
    ch.price_line(s["sl"], TV["text"], "SL", style=2, width=2)
    for k, tp in enumerate(s["tp"][:3], 1):
        ch.price_line(tp, col, f"TP{k}", style=0 if k == 1 else 2)
    mid = (e[0] + e[1]) / 2
    ch.segment(last, price, last + 6, mid, col, width=2, dash=[5, 4])
    ch.segment(last + 6, mid, last + 12, s["tp"][0], col, width=2, arrow=True)
    ch.segment(last + 12, s["tp"][0], last + 20, s["tp"][2], col, width=2, dash=[5, 4], arrow=True)
    return ch.render(*CHART_CSS, scale=3)


def chart_page(path, header: str, title: str, chart_img: Image.Image):
    img = Image.new("RGBA", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 128], fill=GREEN)
    d.text((M, 26), header, font=sans("Bold", 19), fill=SUB)
    d.text((W - M, 26), CONFIG["brand"]["name"], font=sans("Bold", 19), fill=LIME, anchor="ra")
    d.text((M, 58), fit(d, title, sans("ExtraBold", 42), W - 2 * M), font=sans("ExtraBold", 42), fill=CREAM)
    shot = chart_img.resize((W, int(chart_img.height * W / chart_img.width)), Image.LANCZOS)
    img.alpha_composite(shot, (0, 128))
    d = ImageDraw.Draw(img)
    d.text((M, H - 22), "Dữ liệu giá thật · giờ Việt Nam", font=sans("Medium", 17), fill=MUTED, anchor="lm")
    d.text((W - M, H - 22), CONFIG["brand"]["handle"], font=sans("Bold", 17), fill=GREEN, anchor="rm")
    save(img, path)


# ===================================================================== banner

def banner(path, session_label: str, data: dict, result: dict, now: datetime):
    img = Image.new("RGBA", (W, H), GREEN)
    d = ImageDraw.Draw(img)
    d.text((M, 64), CONFIG["brand"]["name"], font=sans("Bold", 28), fill=LIME)
    d.text((W - M, 66), f"{now:%d/%m/%Y}", font=sans("SemiBold", 24), fill=SUB, anchor="ra")
    tag = f"CHIẾN LƯỢC XAUUSD · {session_label.upper()}"
    tw = d.textlength(tag, font=sans("ExtraBold", 30)) + 48
    d.rounded_rectangle([M, 170, M + tw, 228], radius=29, fill=LIME)
    d.text((M + 24, 199), tag, font=sans("ExtraBold", 30), fill=GREEN, anchor="lm")
    y = 290
    for line in wrap(d, result["title"], sans("ExtraBold", 84), W - 2 * M, max_lines=5):
        d.text((M - 4, y), line, font=sans("ExtraBold", 84), fill=CREAM)
        y += 104
    y = max(y + 40, 860)
    bias = result["bias"]
    bcol = DOWN if bias == "giảm" else UP if bias == "tăng" else MUTED
    for label, col in ((f"THIÊN HƯỚNG {bias.upper()}", bcol), (f"GIÁ {money(data['giá_hiện_tại'])}", (40, 90, 72))):
        bw = d.textlength(label, font=sans("ExtraBold", 32)) + 56
        d.rounded_rectangle([M, y, M + bw, y + 72], radius=14, fill=col)
        d.text((M + 28, y + 36), label, font=sans("ExtraBold", 32), fill=CREAM, anchor="lm")
        y += 92
    main = next(s for s in result["scenarios"] if s["role"] == "chính")
    d.text((M, y + 30), f"Kịch bản chính: {main['side']} vùng {zone_txt(main['entry'])}", font=sans("Bold", 34), fill=LIME)
    d.text((M, H - 60), "Lướt xem biểu đồ phân tích D1 · H4 · H1", font=sans("Medium", 24), fill=SUB)
    save(img, path)


# ===================================================================== ảnh bìa (mẫu anh chọn: tiêu đề + thiên hướng + ô vĩ mô)

CARD = (236, 231, 219)
INK = (20, 20, 20)
GOLD_HL = (230, 180, 80)
MACRO_NAMES = {"US10Y": ("Lợi suất 10 năm", "%"), "US3M": ("Lợi suất 3 tháng", "%"),
               "REAL_YIELD": ("Lợi suất thực", "%"), "DXY": ("Chỉ số USD", ""), "VIX": ("VIX", ""),
               "SPX_FUT": ("S&P 500 fut", ""), "SILVER": ("Bạc", ""), "OIL": ("Dầu WTI", "")}


def cover(path, session_label: str, data: dict, result: dict, now: datetime):
    from src.data.macro import top_drivers

    img = Image.new("RGBA", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 760], fill=GREEN)
    d.text((M, 56), CONFIG["brand"]["name"], font=sans("Bold", 26), fill=LIME)
    d.text((W - M, 58), f"{now:%d/%m/%Y}", font=sans("SemiBold", 22), fill=SUB, anchor="ra")
    tag = f"CHIẾN LƯỢC XAUUSD · {session_label.upper()}"
    tw = d.textlength(tag, font=sans("ExtraBold", 26)) + 44
    d.rounded_rectangle([M, 120, M + tw, 172], radius=26, fill=LIME)
    d.text((M + 22, 146), tag, font=sans("ExtraBold", 26), fill=GREEN, anchor="lm")
    y = 214
    for line in wrap(d, result["title"], sans("ExtraBold", 64), W - 2 * M, max_lines=4):
        d.text((M - 3, y), line, font=sans("ExtraBold", 64), fill=CREAM)
        y += 80
    bias = result["bias"]
    bcol = DOWN if bias == "giảm" else UP if bias == "tăng" else MUTED
    label = f"THIÊN HƯỚNG: {bias.upper()}"
    bw = d.textlength(label, font=sans("ExtraBold", 28)) + 48
    d.rounded_rectangle([M, 640, M + bw, 696], radius=12, fill=bcol)
    d.text((M + 24, 668), label, font=sans("ExtraBold", 28), fill=CREAM, anchor="lm")
    d.text((M + bw + 24, 668), f"Giá hiện tại {money(data['giá_hiện_tại'])}", font=sans("Bold", 28),
           fill=CREAM, anchor="lm")

    # 4 yếu tố vĩ mô đang tác động mạnh nhất (viền vàng = đáng chú ý, chữ xám = biến động bình thường)
    d.text((M, 800), "YẾU TỐ VĨ MÔ ĐANG TÁC ĐỘNG", font=sans("ExtraBold", 24), fill=GREEN)
    mac = data["vĩ_mô"]
    tw_ = (W - 2 * M - 3 * 16) / 4
    for k, key in enumerate(top_drivers(mac)):
        name, unit = MACRO_NAMES.get(key, (key, ""))
        v = mac[key]
        x = M + k * (tw_ + 16)
        d.rectangle([x, 846, x + tw_, 990], fill=CARD)
        if v.get("đáng_chú_ý"):
            d.rectangle([x, 846, x + tw_, 853], fill=GOLD_HL)
        d.text((x + 18, 866), name, font=sans("Medium", 19), fill=MUTED)
        d.text((x + 18, 900), f"{v['last']:.2f}{unit}", font=sans("ExtraBold", 34), fill=INK)
        ch = v["chg_1d"] if abs(v["z_1d"]) >= abs(v.get("z_hôm_trước", 0)) else v.get("chg_hôm_trước", 0)
        when = "hôm nay" if ch == v["chg_1d"] else "phiên trước"
        corr = v.get("corr_vàng_20d")
        # Đỏ = bất lợi cho vàng (chỉ số đi ngược vàng mà tăng, hoặc đi cùng vàng mà giảm); xanh = có lợi
        col = (DOWN if (ch > 0) == ((corr if corr is not None else -1) < 0) else UP) if v.get("đáng_chú_ý") else MUTED
        d.text((x + 18, 950), f"{'+' if ch >= 0 else ''}{ch:.2f} ({when})", font=sans("SemiBold", 17), fill=col)
    y = 1030
    for p in result["macro_points"][:3]:
        lines = wrap(d, p, sans("SemiBold", 24), W - 2 * M - 30, max_lines=2)
        d.ellipse([M, y + 10, M + 12, y + 22], fill=GREEN)
        for ln in lines:
            d.text((M + 26, y), ln, font=sans("SemiBold", 24), fill=INK)
            y += 34
        y += 12
    carousel._footer(d, "Lướt để xem phân tích chi tiết  →")
    save(img, path)


# ===================================================================== dựng cả album

def render_album(out_dir, session: str, data: dict, result: dict) -> list:
    now = datetime.now(TZ)
    label = "Phiên Á – Âu" if session == "ae" else "Phiên Mỹ"
    header = f"CHIẾN LƯỢC XAUUSD · {label.upper()} · {now:%d/%m/%Y}"
    p = lambda k: out_dir / f"strategy_{session}_{k:02d}.png"
    for old in out_dir.glob(f"strategy_{session}_*.png"):
        old.unlink()
    cover(p(0), label, data, result, now)
    pages = [("Khung D1: xu hướng trung hạn", result["mtf"]["d1"], chart_d1(result)),
             ("Khung H4: cấu trúc & vùng hợp lưu", result["mtf"]["h4"], chart_h4(result)),
             ("Khung H1: diễn biến các phiên", result["session_review"], chart_h1_overview(result, now))]
    for s in sorted(result["scenarios"], key=lambda x: x["role"] != "chính"):
        tps = " / ".join(money(t) for t in s["tp"][:3])
        body = (f"{s['side']} vùng {zone_txt(s['entry'])} · SL {money(s['sl'])} · TP {tps}\n"
                f"Kích hoạt: {s['trigger']}\nHủy khi: {s['invalidation']}")
        pages.append((f"Kịch bản {s['role']}: {s['side']}", body, chart_h1_scenario(s, now)))
    for k, (title, body, chart_img) in enumerate(pages, 1):
        carousel.render_slide(p(k), header, 0, 0, k, len(pages), title, body,
                              chart_img, "Biểu đồ XAUUSD · dữ liệu giá thật · giờ Việt Nam")
    return [p(k) for k in range(len(pages) + 1)]
