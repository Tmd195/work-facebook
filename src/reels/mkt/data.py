"""Dữ liệu giá THẬT + chỉ báo cho Reels thị trường (Page Global): nến H4, EMA, Bollinger, RSI, Stochastic,
kênh hồi quy, hỗ trợ/kháng cự, đáy/đỉnh lặp lại. Mọi con số trong lời đọc lấy từ đây (AI không tự bịa)."""
from dataclasses import dataclass, field

from src.chart_tools import DIGITS

BARS = 110


@dataclass
class Market:
    symbol: str
    digits: int
    o: list
    h: list
    l: list
    c: list
    ind: dict = field(default_factory=dict)
    facts: dict = field(default_factory=dict)


def _ema(v, n):
    k, out, e = 2 / (n + 1), [], v[0]
    for x in v:
        e = x * k + e * (1 - k)
        out.append(e)
    return out


def _sma(v, n):
    return [sum(v[max(0, i - n + 1): i + 1]) / len(v[max(0, i - n + 1): i + 1]) for i in range(len(v))]


def _std(v, n):
    out = []
    for i in range(len(v)):
        w = v[max(0, i - n + 1): i + 1]
        m = sum(w) / len(w)
        out.append((sum((x - m) ** 2 for x in w) / len(w)) ** 0.5)
    return out


def _rsi(c, n=14):
    out, ag, al = [50.0], 0.0, 0.0
    for i in range(1, len(c)):
        ch = c[i] - c[i - 1]
        g, lo = max(ch, 0), max(-ch, 0)
        ag = (ag * (n - 1) + g) / n if i > 1 else g
        al = (al * (n - 1) + lo) / n if i > 1 else lo
        out.append(100 - 100 / (1 + ag / al) if al else 100.0)
    return out


def _stoch(h, l, c, n=14, d=3):
    k = []
    for i in range(len(c)):
        hh, ll = max(h[max(0, i - n + 1): i + 1]), min(l[max(0, i - n + 1): i + 1])
        k.append(100 * (c[i] - ll) / (hh - ll) if hh > ll else 50)
    return _sma(k, d), _sma(_sma(k, d), d)


def _channel(h, l, c, n=60):
    """Kênh hồi quy tuyến tính trên n nến cuối: (i0, a, b, off_hi, off_lo, r2) với giá giữa = a + b*i."""
    i0 = len(c) - n
    xs = list(range(i0, len(c)))
    ys = c[i0:]
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    hi = max(h[i] - (a + b * i) for i in xs)
    lo = min(l[i] - (a + b * i) for i in xs)
    ss = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    st = sum((y - my) ** 2 for y in ys) or 1
    return {"i0": i0, "a": a, "b": b, "hi": hi, "lo": lo, "r2": 1 - ss / st}


def _equal_lows(l, digits, look=60):
    """Đáy lặp lại (double/triple bottom): các đáy swing trong `look` nến cuối nằm cùng 1 vùng ±0.6%."""
    n = len(l)
    swings = [i for i in range(n - look, n - 2) if l[i] == min(l[max(0, i - 4): i + 5])]
    best = []
    for i in swings:
        grp = [j for j in swings if abs(l[j] - l[i]) / l[i] < 0.006]
        if len(grp) > len(best):
            best = grp
    return {"count": len(best), "level": round(min(l[j] for j in best), digits), "idx": best} if len(best) >= 2 else None


def _swing_levels(h, l, price, look=60):
    """Hỗ trợ = đáy swing gần nhất dưới giá; kháng cự = đỉnh swing gần nhất trên giá (trong `look` nến)."""
    n = len(h)
    lows = [l[i] for i in range(n - look, n - 2) if l[i] == min(l[max(0, i - 3): i + 4]) and l[i] < price]
    highs = [h[i] for i in range(n - look, n - 2) if h[i] == max(h[max(0, i - 3): i + 4]) and h[i] > price]
    sup = max(lows) if lows else min(l[-look:])
    res = min(highs) if highs else max(h[-look:])
    return sup, res


def load(symbol: str) -> Market:
    """Nến H4 thật (gộp từ H1 ~1 tháng) – thân nến rõ như biểu đồ trên điện thoại."""
    from src.analysis import to_h4
    from src.data.prices import get_intraday
    cs = to_h4(get_intraday(symbol).candles)[-BARS:]
    dg = DIGITS.get(symbol, 5)
    o, h, l, c = [x.open for x in cs], [x.high for x in cs], [x.low for x in cs], [x.close for x in cs]
    m = Market(symbol, dg, o, h, l, c)
    mid, sd = _sma(c, 20), _std(c, 20)
    k, d = _stoch(h, l, c)
    m.ind = {"ema20": _ema(c, 20), "ema50": _ema(c, 50), "bb_up": [x + 2 * y for x, y in zip(mid, sd)],
             "bb_mid": mid, "bb_lo": [x - 2 * y for x, y in zip(mid, sd)], "rsi": _rsi(c), "stoch_k": k, "stoch_d": d,
             "channel": _channel(h, l, c), "lows": _equal_lows(l, dg)}
    if m.ind["lows"] and m.ind["lows"]["level"] > c[-1]:      # đáy lặp lại nằm trên giá hiện tại → không còn là hỗ trợ
        m.ind["lows"] = None
    ch = m.ind["channel"]
    r = lambda v: round(v, dg)
    e20, e50 = m.ind["ema20"][-1], m.ind["ema50"][-1]
    trend = "up" if c[-1] > e20 > e50 else "down" if c[-1] < e20 < e50 else "sideways"
    sup, res = _swing_levels(h, l, c[-1])
    m.facts = {
        "symbol": symbol, "timeframe": "H4 (4-hour candles)", "price": r(c[-1]),
        "change_last_5_days_pct": round((c[-1] / c[-31] - 1) * 100, 2),
        "change_last_10_days_pct": round((c[-1] / c[-61] - 1) * 100, 2), "trend_h4": trend,
        "ema20": r(e20), "ema50": r(e50), "rsi14": round(m.ind["rsi"][-1], 1),
        "stoch_k": round(k[-1], 1), "bollinger_upper": r(m.ind["bb_up"][-1]), "bollinger_lower": r(m.ind["bb_lo"][-1]),
        "channel_60_bars": {"direction": "rising" if ch["b"] > 0 else "falling", "fit_r2": round(ch["r2"], 2)},
        "support": r(sup), "resistance": r(res),
        "repeated_lows": ({"times": m.ind["lows"]["count"], "level": m.ind["lows"]["level"]}
                          if m.ind["lows"] else None),
    }
    return m
