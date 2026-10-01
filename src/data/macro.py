"""Yếu tố vĩ mô ảnh hưởng giá vàng - chỉ đánh dấu những yếu tố THỰC SỰ đáng chú ý ở thời điểm phân tích.

Với mỗi chỉ số:
- z_1d: biến động hôm nay so với biến động bình thường 20 ngày (|z| ≥ 1 = lớn hơn thường ngày)
- corr_vàng_20d: tương quan 20 ngày giữa thay đổi của chỉ số và thay đổi giá vàng
- đáng_chú_ý: |z| ≥ 1 và |tương quan| ≥ 0.3 (vừa biến động bất thường, vừa đang gắn với vàng)
"""
import statistics

import requests

UA = {"User-Agent": "Mozilla/5.0"}

# Vai trò: "tác nhân" = yếu tố có thể làm vàng biến động; "đồng pha" = tài sản thường chạy cùng vàng (chỉ để xác nhận)
ROLE = {"SILVER": "đồng pha", "SPX_FUT": "khẩu vị rủi ro", "VIX": "khẩu vị rủi ro"}

YAHOO = {
    "US10Y": ("^TNX", "Lợi suất trái phiếu Mỹ 10 năm (%)"),
    "US3M": ("^IRX", "Lợi suất tín phiếu Mỹ 13 tuần (%)"),
    "DXY": ("DX-Y.NYB", "Chỉ số USD (DXY)"),
    "VIX": ("^VIX", "Chỉ số sợ hãi VIX"),
    "SPX_FUT": ("ES=F", "Hợp đồng tương lai S&P 500"),
    "SILVER": ("SI=F", "Bạc (USD/oz)"),
    "OIL": ("CL=F", "Dầu WTI (USD/thùng)"),
}
Z_NOTABLE, CORR_NOTABLE = 1.0, 0.3


def _yahoo_closes(symbol: str) -> tuple[list[tuple[int, float]], float]:
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                     params={"interval": "1d", "range": "3mo"}, headers=UA, timeout=30)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    pts = [(t // 86400, c) for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"]) if c is not None]
    return pts, res["meta"].get("regularMarketPrice") or pts[-1][1]


def _fred(series: str) -> list[tuple[str, float]]:
    r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": series}, timeout=30)
    r.raise_for_status()
    rows = [ln.split(",") for ln in r.text.strip().splitlines()[1:]]
    return [(d, float(v)) for d, v in rows if v not in (".", "")][-70:]


def _stats(closes: list[float], last: float, gold_by_day: dict | None = None, days: list[int] | None = None) -> dict:
    series = closes[:-1] + [last]
    ch = [b - a for a, b in zip(series, series[1:])]
    today = ch[-1]
    sd = statistics.pstdev(ch[-22:-2]) or 1e-9
    out = {"last": round(last, 3), "chg_1d": round(today, 3),
           "chg_5d": round(last - series[-6], 3) if len(series) > 5 else None,
           "z_1d": round(today / sd, 2),
           "chg_hôm_trước": round(ch[-2], 3), "z_hôm_trước": round(ch[-2] / sd, 2)}
    if gold_by_day and days:
        pairs = []
        for (d0, d1), c in zip(zip(days, days[1:]), ch):
            if d0 in gold_by_day and d1 in gold_by_day:
                pairs.append((c, gold_by_day[d1] - gold_by_day[d0]))
        pairs = pairs[-20:]
        if len(pairs) >= 10:
            out["corr_vàng_20d"] = round(statistics.correlation([a for a, _ in pairs], [b for _, b in pairs]), 2)
    return out


def snapshot() -> dict:
    try:
        gold_pts, _ = _yahoo_closes("GC=F")
        gold_by_day = dict(gold_pts)
    except Exception:
        gold_by_day = None
    out = {}
    for key, (sym, label) in YAHOO.items():
        try:
            pts, last = _yahoo_closes(sym)
            st = _stats([c for _, c in pts], last, gold_by_day, [d for d, _ in pts])
            out[key] = {"label": label, **st}
        except Exception as exc:
            print(f"  ! Không lấy được {key}: {exc}")
    try:
        rows = _fred("DFII10")
        st = _stats([v for _, v in rows], rows[-1][1])
        out["REAL_YIELD"] = {"label": "Lợi suất thực 10 năm - TIPS (%)", "ngày_dữ_liệu": rows[-1][0], **st}
    except Exception as exc:
        print(f"  ! Không lấy được lợi suất thực: {exc}")

    for k, v in out.items():
        corr = v.get("corr_vàng_20d")
        big = max(abs(v["z_1d"]), abs(v.get("z_hôm_trước", 0))) >= Z_NOTABLE
        v["vai_trò"] = ROLE.get(k, "tác nhân")
        v["đáng_chú_ý"] = big and (corr is None or abs(corr) >= CORR_NOTABLE)
    return out


def top_drivers(snap: dict, n: int = 4) -> list[str]:
    """Các yếu tố tác động mạnh nhất lúc này: ưu tiên 'đáng chú ý', rồi theo |z| × |tương quan|."""
    z = lambda k: max(abs(snap[k].get("z_1d", 0)), abs(snap[k].get("z_hôm_trước", 0)))
    score = lambda k: (snap[k].get("đáng_chú_ý", False), snap[k].get("vai_trò", "tác nhân") == "tác nhân",
                       z(k) * abs(snap[k].get("corr_vàng_20d") or 0.5))
    return sorted(snap, key=score, reverse=True)[:n]
