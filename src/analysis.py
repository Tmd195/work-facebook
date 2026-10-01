"""Tính các chỉ số kỹ thuật từ nến D1 - mọi con số trong bài đều xuất phát từ đây."""
from datetime import datetime, timedelta, timezone

from src.data.prices import Candle, Series


def ema(values: list[float], period: int) -> float:
    k = 2 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return e


def rsi(closes: list[float], period: int = 14) -> float:
    gains, losses = [], []
    for a, b in zip(closes[:-1], closes[1:]):
        gains.append(max(b - a, 0))
        losses.append(max(a - b, 0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for g, l in zip(gains[period:], losses[period:]):
        avg_g = (avg_g * (period - 1) + g) / period
        avg_l = (avg_l * (period - 1) + l) / period
    if avg_l == 0:
        return 100.0
    return 100 - 100 / (1 + avg_g / avg_l)


def atr(candles: list[Candle], period: int = 14) -> float:
    trs = [
        max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close))
        for p, c in zip(candles[:-1], candles[1:])
    ]
    a = sum(trs[:period]) / period
    for t in trs[period:]:
        a = (a * (period - 1) + t) / period
    return a


def swing_levels(candles: list[Candle], price: float, lookback: int = 90, wing: int = 3):
    """Đỉnh/đáy fractal gần nhất phía trên (kháng cự) và phía dưới (hỗ trợ) giá hiện tại."""
    cs = candles[-lookback:]
    highs, lows = [], []
    for i in range(wing, len(cs) - wing):
        window = cs[i - wing:i + wing + 1]
        if cs[i].high == max(c.high for c in window):
            highs.append(cs[i].high)
        if cs[i].low == min(c.low for c in window):
            lows.append(cs[i].low)
    levels = highs + lows
    above = sorted(l for l in levels if l > price)
    below = sorted((l for l in levels if l < price), reverse=True)
    return above[:2], below[:2]


def completed_candles(series: Series) -> list[Candle]:
    """Bỏ nến đang chạy để 'ngày trước' luôn là nến đã đóng.

    Mỗi nguồn đánh dấu thời gian nến khác nhau (00:00, 04:00, 23:00 UTC...), nên coi nến
    cuối là 'đang chạy' nếu nó mới mở chưa tới 20 giờ.
    """
    cs = series.candles
    if cs and datetime.now(timezone.utc) - cs[-1].date < timedelta(hours=20):
        return cs[:-1]
    return cs


def to_h4(candles: list[Candle]) -> list[Candle]:
    groups: dict = {}
    for c in candles:
        key = c.date.replace(hour=c.date.hour // 4 * 4, minute=0, second=0, microsecond=0)
        groups.setdefault(key, []).append(c)
    return [Candle(k, g[0].open, max(x.high for x in g), min(x.low for x in g), g[-1].close,
                   sum(x.volume for x in g))
            for k, g in sorted(groups.items())]


def intraday_levels(h1: Series, daily: dict, digits: int) -> dict:
    """Danh sách vùng giá có tên cho bài Plan A/B - AI chỉ được chọn số trong danh sách này."""
    now = datetime.now(timezone.utc)
    price = h1.last
    today = [c for c in h1.candles if now - c.date < timedelta(hours=12)]
    h4 = to_h4(h1.candles)
    res, sup = swing_levels(h4, price, lookback=80, wing=2)
    rnd = lambda x: round(x, digits)

    levels = {
        "Đỉnh 12 giờ qua": max(c.high for c in today) if today else None,
        "Đáy 12 giờ qua": min(c.low for c in today) if today else None,
        "Kháng cự H4 gần": res[0] if res else None,
        "Kháng cự H4 xa": res[1] if len(res) > 1 else None,
        "Hỗ trợ H4 gần": sup[0] if sup else None,
        "Hỗ trợ H4 xa": sup[1] if len(sup) > 1 else None,
        "Đỉnh ngày trước": daily["prev_high"],
        "Đáy ngày trước": daily["prev_low"],
        "Pivot ngày": daily["pivot"],
        "R1": daily["r1"], "S1": daily["s1"], "R2": daily["r2"], "S2": daily["s2"],
        "Kháng cự D1": daily["resistance"][0] if daily["resistance"] else None,
        "Hỗ trợ D1": daily["support"][0] if daily["support"] else None,
    }
    atr_h1 = atr(h1.candles[-60:])

    # Gộp các vùng nằm sát nhau (< 0.3 ATR H1) thành một vùng, giữ tên của cả hai
    merged: list[list] = []
    for name, v in sorted(((k, v) for k, v in levels.items() if v is not None), key=lambda kv: kv[1]):
        if merged and v - merged[-1][1] < 0.3 * atr_h1:
            merged[-1][0] += f" / {name}"
        else:
            merged.append([name, v])
    levels = {name: rnd(v) for name, v in merged}
    return {
        "price": rnd(price),
        "atr_h1": rnd(atr_h1),
        "levels_above": dict(sorted(((k, v) for k, v in levels.items() if v > price), key=lambda kv: kv[1])),
        "levels_below": dict(sorted(((k, v) for k, v in levels.items() if v < price), key=lambda kv: -kv[1])),
        "chart": [[c.date.isoformat(), rnd(c.open), rnd(c.high), rnd(c.low), rnd(c.close)]
                  for c in h1.candles[-60:]],
    }


def analyze(series: Series, digits: int) -> dict:
    cs = completed_candles(series)
    closes = [c.close for c in cs]
    prev = cs[-1]
    price = series.last

    pivot = (prev.high + prev.low + prev.close) / 3
    r1, s1 = 2 * pivot - prev.low, 2 * pivot - prev.high
    r2, s2 = pivot + (prev.high - prev.low), pivot - (prev.high - prev.low)

    e20, e50 = ema(closes, 20), ema(closes, 50)
    if price > e20 > e50:
        trend = "Tăng"
    elif price < e20 < e50:
        trend = "Giảm"
    else:
        trend = "Đi ngang"

    res, sup = swing_levels(cs, price)
    rnd = lambda x: round(x, digits)
    return {
        "price": rnd(price),
        "prev_close": rnd(prev.close),
        "change_pct": round((price - prev.close) / prev.close * 100, 2),
        "prev_high": rnd(prev.high),
        "prev_low": rnd(prev.low),
        "pivot": rnd(pivot), "r1": rnd(r1), "r2": rnd(r2), "s1": rnd(s1), "s2": rnd(s2),
        "ema20": rnd(e20), "ema50": rnd(e50),
        "rsi14": round(rsi(closes), 1),
        "atr14": rnd(atr(cs)),
        "trend": trend,
        "resistance": [rnd(x) for x in res],
        "support": [rnd(x) for x in sup],
        "spark": [rnd(c) for c in closes[-30:]] + [rnd(price)],
        "source": series.source,
        "notes": series.notes,
    }
