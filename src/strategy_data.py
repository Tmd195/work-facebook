"""Thu thập & tính toán toàn bộ dữ liệu cho bài Chiến lược XAUUSD (đa khung + phiên + vùng giá + vĩ mô).

Mọi mức giá AI được dùng đều nằm trong "zones" (vùng giá đã gộp) - code kiểm tra lại sau khi AI viết.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from src.chart_tools import (atr_series, breaks, ema, ichimoku, load, rsi, swings)
from src.config import TZ
from src.data import macro
from src.data.calendar import events_for_session

SYMBOL = "XAUUSD"
LONDON, NEWYORK = ZoneInfo("Europe/London"), ZoneInfo("America/New_York")


# ===================================================================== phiên giao dịch (giờ VN)

def session_windows(day: datetime) -> dict:
    """Mốc phiên trong ngày theo giờ VN, tự tính theo giờ mùa hè/đông của London & New York."""
    d = day.astimezone(TZ).date()
    vn = lambda tz, h, m=0: datetime(d.year, d.month, d.day, h, m, tzinfo=tz).astimezone(TZ)
    return {
        "Á": (datetime(d.year, d.month, d.day, 6, 0, tzinfo=TZ), vn(LONDON, 8)),
        "Âu": (vn(LONDON, 8), vn(NEWYORK, 8, 30)),
        "Mỹ": (vn(NEWYORK, 8, 30), vn(NEWYORK, 17)),
    }


def session_stats(h1: list, windows: dict, now: datetime) -> dict:
    out = {}
    for name, (s, e) in windows.items():
        bars = [c for c in h1 if s <= c.date.astimezone(TZ) < min(e, now)]
        if not bars:
            out[name] = {"status": "chưa mở", "from": f"{s:%H:%M}", "to": f"{e:%H:%M}"}
            continue
        hi, lo = max(c.high for c in bars), min(c.low for c in bars)
        out[name] = {
            "status": "đã kết thúc" if now >= e else "đang diễn ra",
            "from": f"{s:%H:%M}", "to": f"{e:%H:%M}",
            "open": round(bars[0].open, 2), "high": round(hi, 2), "low": round(lo, 2),
            "close": round(bars[-1].close, 2), "range": round(hi - lo, 2),
            "change": round(bars[-1].close - bars[0].open, 2),
            "volume": int(sum(c.volume for c in bars)),
        }
    a, e = out.get("Á", {}), out.get("Âu", {})
    if "high" in a and "high" in e:
        out["Âu"]["quét_đỉnh_phiên_Á"] = e["high"] > a["high"]
        out["Âu"]["quét_đáy_phiên_Á"] = e["low"] < a["low"]
    return out


# ===================================================================== phân tích từng khung

def frame_summary(c: list, name: str) -> dict:
    closes = [x.close for x in c]
    price = closes[-1]
    e20, e50, e200 = ema(closes, 20)[-1], ema(closes, 50)[-1], ema(closes, 200)[-1]
    tk, kj, sa, sb = ichimoku(c)
    cloud_now = (sa[-27], sb[-27]) if len(c) > 27 else (sa[-1], sb[-1])
    cloud_fut = (sa[-1], sb[-1])
    pos = "trên" if price > max(cloud_now) else "dưới" if price < min(cloud_now) else "trong"
    a = atr_series(c)[-1]
    sw = swings(c)
    evs = breaks(c, sw)
    last_ev = evs[-1] if evs else None
    highs = [p for i, p, k in sw if k == "H"][-4:]
    lows = [p for i, p, k in sw if k == "L"][-4:]
    seg = c[-80:]
    hi_i = max(range(len(seg)), key=lambda i: seg[i].high)
    lo_i = min(range(len(seg)), key=lambda i: seg[i].low)
    hi, lo = seg[hi_i].high, seg[lo_i].low
    leg_down = hi_i < lo_i
    fib = {f"{lv:g}": round(lo + (hi - lo) * lv, 2) if leg_down else round(hi - (hi - lo) * lv, 2)
           for lv in (0.236, 0.382, 0.5, 0.618, 0.786)}
    if price > e20 > e50:
        trend = "tăng"
    elif price < e20 < e50:
        trend = "giảm"
    else:
        trend = "đi ngang/giằng co"
    return {
        "khung": name, "giá": round(price, 2), "xu_hướng_EMA": trend,
        "EMA20": round(e20, 2), "EMA50": round(e50, 2), "EMA200": round(e200, 2),
        "RSI14": round(rsi(closes)[-1], 1), "ATR14": round(a, 2),
        "Ichimoku": {"vị_trí_giá_so_với_mây": pos, "Tenkan": round(tk[-1], 2), "Kijun": round(kj[-1], 2),
                     "mây_hiện_tại": [round(min(cloud_now), 2), round(max(cloud_now), 2)],
                     "mây_tương_lai": "tăng (xanh)" if cloud_fut[0] >= cloud_fut[1] else "giảm (đỏ)"},
        "cấu_trúc_gần_nhất": ({"loại": last_ev["kind"], "hướng": "tăng" if last_ev["dir"] == "up" else "giảm",
                               "mức": round(last_ev["price"], 2),
                               "cách_đây_số_nến": len(c) - 1 - last_ev["to"]} if last_ev else None),
        "đỉnh_swing_gần": [round(x, 2) for x in highs], "đáy_swing_gần": [round(x, 2) for x in lows],
        "sóng_lớn_gần_nhất": {"từ": round(hi if leg_down else lo, 2), "đến": round(lo if leg_down else hi, 2),
                             "hướng": "giảm" if leg_down else "tăng", "fibonacci_hồi": fib},
    }


def regime(d1: dict, h4: dict, events: list) -> dict:
    """Trạng thái thị trường → hệ thống giao dịch phù hợp (lấy từ thư viện series của page)."""
    high_news = [e for e in events if e["impact"] == "High" and e["currency"] == "USD"]
    h4_ev = h4["cấu_trúc_gần_nhất"]
    if h4_ev and h4_ev["loại"] == "CHoCH" and h4_ev["cách_đây_số_nến"] <= 12:
        state = "có dấu hiệu đảo chiều (CHoCH gần đây trên H4)"
        systems = ["SMC: CHoCH/BOS, Order Block, FVG, thanh khoản", "Fibonacci vùng hồi", "Ichimoku xác nhận"]
    elif d1["xu_hướng_EMA"] == h4["xu_hướng_EMA"] and d1["xu_hướng_EMA"] in ("tăng", "giảm"):
        state = f"xu hướng {d1['xu_hướng_EMA']} rõ (D1 và H4 đồng thuận)"
        systems = ["Dow & cấu trúc thị trường", "EMA 20/50 + Fibonacci hồi để vào thuận xu hướng",
                   "Ichimoku (Kijun/mây làm kháng cự/hỗ trợ động)"]
    else:
        state = "giằng co / đi ngang (D1 và H4 chưa đồng thuận)"
        systems = ["Hỗ trợ - kháng cự & cung cầu", "Pivot Point", "CRT / quét thanh khoản biên phiên"]
    if high_news:
        systems.append("Kịch bản theo tin: chờ nến xác nhận sau tin, không vào lệnh lúc tin ra")
    return {"trạng_thái": state, "hệ_thống_áp_dụng": systems}


# ===================================================================== vùng giá

def build_zones(d1c, h4c, h1c, frames: dict, sessions: dict, price: float) -> list[dict]:
    a_h1 = atr_series(h1c)[-1]
    a_d1 = atr_series(d1c)[-1]
    cands: list[tuple[str, float]] = []
    prev = d1c[-2] if datetime.now(timezone.utc) - d1c[-1].date < timedelta(hours=20) else d1c[-1]
    pv = (prev.high + prev.low + prev.close) / 3
    cands += [("Pivot ngày", pv), ("R1", 2 * pv - prev.low), ("S1", 2 * pv - prev.high),
              ("R2", pv + prev.high - prev.low), ("S2", pv - (prev.high - prev.low)),
              ("Đỉnh ngày trước", prev.high), ("Đáy ngày trước", prev.low)]
    for tf, f in frames.items():
        cands += [(f"Kijun {tf}", f["Ichimoku"]["Kijun"]), (f"EMA50 {tf}", f["EMA50"]),
                  (f"Mây {tf} (cạnh dưới)", f["Ichimoku"]["mây_hiện_tại"][0]),
                  (f"Mây {tf} (cạnh trên)", f["Ichimoku"]["mây_hiện_tại"][1])]
        cands += [(f"Đỉnh swing {tf}", x) for x in f["đỉnh_swing_gần"]]
        cands += [(f"Đáy swing {tf}", x) for x in f["đáy_swing_gần"]]
        if tf in ("H4", "D1"):
            cands += [(f"Fibo {k} {tf}", v) for k, v in f["sóng_lớn_gần_nhất"]["fibonacci_hồi"].items()]
    for name, s in sessions.items():
        if "high" in s:
            cands += [(f"Đỉnh phiên {name}", s["high"]), (f"Đáy phiên {name}", s["low"])]
    base = round(price / 50) * 50
    cands += [(f"Số tròn {base + k * 50:g}", base + k * 50) for k in range(-4, 5)]

    # Chỉ giữ trong tầm ±2.5 ATR D1, gộp các mức sát nhau thành vùng
    cands = sorted((n, v) for n, v in cands if abs(v - price) <= 2.5 * a_d1)
    cands.sort(key=lambda x: x[1])
    zones: list[dict] = []
    tol = 0.35 * a_h1
    for name, v in cands:
        if zones and v - zones[-1]["hi"] <= tol:
            z = zones[-1]
            z["hi"] = max(z["hi"], v)
            z["sources"].append(name)
        else:
            zones.append({"lo": v, "hi": v, "sources": [name]})
    out = []
    for z in zones:
        lo, hi = round(z["lo"], 2), round(z["hi"], 2)
        if hi - lo < 0.15 * a_h1:              # vùng quá mỏng → nới nhẹ cho dễ dùng
            mid = (lo + hi) / 2
            lo, hi = round(mid - 0.1 * a_h1, 2), round(mid + 0.1 * a_h1, 2)
        out.append({"id": f"Z{len(out) + 1}", "lo": lo, "hi": hi,
                    "vị_trí": "trên giá" if lo > price else "dưới giá" if hi < price else "chứa giá hiện tại",
                    "hợp_lưu": len(z["sources"]), "thành_phần": z["sources"]})
    return out


# ===================================================================== tổng hợp

def gather(session: str) -> dict:
    """session: 'ae' (bài 10:00 cho phiên Á-Âu) hoặc 'us' (bài trước phiên Mỹ)."""
    now = datetime.now(TZ)
    d1c, h4c, h1c = list(load(SYMBOL, "D1")), list(load(SYMBOL, "H4")), list(load(SYMBOL, "H1"))
    price = h1c[-1].close
    frames = {"D1": frame_summary(d1c, "D1"), "H4": frame_summary(h4c, "H4"), "H1": frame_summary(h1c[-200:], "H1")}
    windows = session_windows(now)
    sessions = session_stats(h1c, windows, now)
    yesterday = session_stats(h1c, session_windows(now - timedelta(days=1)), now)
    events = events_for_session(now)
    zones = build_zones(d1c, h4c, h1c, frames, sessions, price)
    return {
        "loại_bài": "Kế hoạch phiên Á - Âu" if session == "ae" else "Kế hoạch phiên Mỹ",
        "thời_điểm": f"{now:%H:%M %d/%m/%Y} (giờ VN)",
        "mã": SYMBOL, "giá_hiện_tại": round(price, 2),
        "ATR_H1": round(atr_series(h1c)[-1], 2), "ATR_D1": round(atr_series(d1c)[-1], 2),
        "vĩ_mô": macro.snapshot(),
        "lịch_kinh_tế_hôm_nay": events,
        "phiên_hôm_nay": sessions,
        "phiên_Mỹ_hôm_qua": yesterday.get("Mỹ"),
        "đa_khung": frames,
        "trạng_thái_thị_trường": regime(frames["D1"], frames["H4"], events),
        "vùng_giá": zones,
    }
