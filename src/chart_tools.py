"""Tạo biểu đồ giao diện TradingView cho bài Kiến thức.

Hai chế độ (AI chọn trong trường "chart" của bài viết):

1) Dữ liệu thật - code tự dò trên giá thật:
   {"mode":"real", "symbol":"XAUUSD", "tf":"H4", "tools":[...], "scenario":"up|down|null"}
   tools: structure, bos_choch, order_blocks, fvg, sr_zones, fib, pivot, ema20, ema50, ema200, sma50,
          rsi, macd, bollinger, supertrend, ichimoku, volume,
          pattern:pinbar | pattern:engulfing | pattern:doji | pattern:inside_bar | pattern:star

2) Mô hình minh họa - khi khái niệm khó tìm đúng mẫu trên giá thật (Elliott, Harmonic, Wyckoff...):
   {"mode":"illustration", "path":[...], "points":[...], "zones":[...], "hlines":[...], "lines":[...],
    "arrows":[...], "fib":{...}, "indicators":[...]}   (cùng cú pháp với diagrams.DIAGRAM_SPEC)

build() trả về (TVChart, facts) - facts là các câu mô tả những gì code tìm được trên giá thật,
được gắn vào cuối bài để người đọc đối chiếu với hình.
"""
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from src.analysis import to_h4
from src.data.prices import Candle, get_intraday, get_series
from src.design.diagrams import synth_candles
from src.design.tvchart import TV, TVChart
from src.i18n import EN_MODE

DIGITS = {"XAUUSD": 2, "EURUSD": 5, "GBPUSD": 5, "DXY": 3, "AUDUSD": 5, "USDCAD": 5, "USDJPY": 3, "WTI": 2}
DIGITS.update({c: 3 if c.endswith("JPY") else 5 for c in ['USDCHF', 'EURGBP', 'EURJPY', 'GBPJPY', 'AUDJPY', 'EURCHF', 'CADJPY', 'CHFJPY', 'GBPCHF', 'EURAUD', 'AUDCAD', 'GBPCAD', 'EURCAD', 'GBPAUD']})
WINDOW = {"H1": 120, "H4": 110, "D1": 120}

CHART_SPEC = """Trường "chart" mô tả biểu đồ (giao diện TradingView) đi kèm bài, chọn 1 trong 2 chế độ:
A) Giá thật (ưu tiên): {"mode":"real","symbol":"XAUUSD|EURUSD|GBPUSD","tf":"H1|H4|D1","tools":[...],"scenario":null}
   tools (chọn 1-4 cái đúng nội dung bài): structure (đánh dấu HH/HL/LH/LL), bos_choch, order_blocks, fvg,
   sr_zones (vùng hỗ trợ/kháng cự), fib (Fibonacci con sóng gần nhất), pivot (chỉ dùng với H1), ema20, ema50,
   ema200, sma50, rsi, macd, bollinger, supertrend, ichimoku, volume (chỉ XAUUSD),
   pattern:pinbar, pattern:engulfing, pattern:doji, pattern:inside_bar, pattern:star (tự tìm mẫu nến gần nhất).
   scenario: "up" / "down" để vẽ mũi tên kịch bản, hoặc null.
B) Mô hình minh họa (chỉ khi khái niệm không tự dò được trên giá thật: sóng Elliott, Harmonic, sơ đồ Wyckoff,
   Quasimodo...): {"mode":"illustration","path":[4-9 điểm đỉnh/đáy quanh 100],"bars_per_leg":5,
   "points":[{"at":i,"label":"..."}],"zones":[{"from":p,"to":p,"label":"...","color":"red|green|gold|gray","start":i}],
   "hlines":[{"price":p,"label":"...","color":"..."}],"lines":[{"from":[i,p],"to":[j,p],"label":"..."}],
   "arrows":[{"from":[i,p],"to":[j,p],"color":"green|red"}],"fib":{"from":i,"to":j,"levels":[0.382,0.5,0.618]},
   "indicators":["ema20","rsi","volume"]}   (i = chỉ số điểm trong path)"""

COLOR = {"red": TV["down"], "green": TV["up"], "ink": TV["text"], "gold": TV["orange"],
         "gray": TV["gray"], "blue": TV["blue"]}


# ===================================================================== dữ liệu

@lru_cache(maxsize=None)
def load(symbol: str, tf: str) -> tuple:
    if tf == "D1":
        candles = get_series(symbol, "2y").candles
    else:
        h1 = get_intraday(symbol).candles
        candles = to_h4(h1) if tf == "H4" else h1
    return tuple(candles)


# ===================================================================== chỉ báo

def ema(v, p):
    out, e = [], None
    for x in v:
        e = x if e is None else x * 2 / (p + 1) + e * (1 - 2 / (p + 1))
        out.append(e)
    return out


def sma(v, p):
    return [sum(v[max(0, i - p + 1):i + 1]) / len(v[max(0, i - p + 1):i + 1]) for i in range(len(v))]


def rsi(v, p=14):
    out, ag, al = [None], 0.0, 0.0
    for i in range(1, len(v)):
        ch = v[i] - v[i - 1]
        n = min(i, p)
        ag += (max(ch, 0) - ag) / n
        al += (max(-ch, 0) - al) / n
        out.append(100 - 100 / (1 + ag / al) if al else 100.0)
    return out


def atr_series(c, p=14):
    out, a = [], None
    for i, x in enumerate(c):
        tr = x.high - x.low if i == 0 else max(x.high - x.low, abs(x.high - c[i - 1].close), abs(x.low - c[i - 1].close))
        a = tr if a is None else (a * (p - 1) + tr) / p
        out.append(a)
    return out


def bollinger(v, p=20, k=2.0):
    mid, up, lo = [], [], []
    for i in range(len(v)):
        w = v[max(0, i - p + 1):i + 1]
        m = sum(w) / len(w)
        sd = (sum((x - m) ** 2 for x in w) / len(w)) ** 0.5
        mid.append(m), up.append(m + k * sd), lo.append(m - k * sd)
    return mid, up, lo


def supertrend(c, p=10, mult=3.0):
    a = atr_series(c, p)
    line, trend, fu, fl = [], 1, None, None
    for i, x in enumerate(c):
        hl2 = (x.high + x.low) / 2
        bu, bl = hl2 + mult * a[i], hl2 - mult * a[i]
        fu = bu if fu is None or bu < fu or c[i - 1].close > fu else fu
        fl = bl if fl is None or bl > fl or c[i - 1].close < fl else fl
        if trend == 1 and x.close < fl:
            trend = -1
        elif trend == -1 and x.close > fu:
            trend = 1
        line.append((fl if trend == 1 else fu, trend))
    return line


def macd(v, f=12, s=26, sig=9):
    m = [a - b for a, b in zip(ema(v, f), ema(v, s))]
    sg = ema(m, sig)
    return m, sg, [a - b for a, b in zip(m, sg)]


def ichimoku(c):
    mid = lambda i, p: (max(x.high for x in c[max(0, i - p + 1):i + 1]) + min(x.low for x in c[max(0, i - p + 1):i + 1])) / 2
    tenkan = [mid(i, 9) for i in range(len(c))]
    kijun = [mid(i, 26) for i in range(len(c))]
    span_a = [(t + k) / 2 for t, k in zip(tenkan, kijun)]
    span_b = [mid(i, 52) for i in range(len(c))]
    return tenkan, kijun, span_a, span_b


# ===================================================================== dò cấu trúc giá

def swings(c, wing=3):
    out = []
    for i in range(wing, len(c) - wing):
        win = c[i - wing:i + wing + 1]
        if c[i].high == max(x.high for x in win):
            out.append((i, c[i].high, "H"))
        if c[i].low == min(x.low for x in win):
            out.append((i, c[i].low, "L"))
    return out


def structure_labels(sw):
    labels, last = [], {"H": None, "L": None}
    for i, p, k in sw:
        prev = last[k]
        if prev is not None:
            labels.append((i, p, k, ("HH" if p > prev else "LH") if k == "H" else ("HL" if p > prev else "LL")))
        last[k] = p
    return labels


def breaks(c, sw, wing=3):
    """BOS / CHoCH: giá đóng cửa vượt đỉnh/đáy swing gần nhất đã xác nhận."""
    events, trend = [], None
    last_h = last_l = None
    pending = sorted(sw)
    for j in range(len(c)):
        for s in [s for s in pending if s[0] + wing == j]:
            if s[2] == "H":
                last_h = [s[0], s[1], False]
            else:
                last_l = [s[0], s[1], False]
        if last_h and not last_h[2] and c[j].close > last_h[1]:
            events.append({"from": last_h[0], "to": j, "price": last_h[1], "dir": "up",
                           "kind": "BOS" if trend in (None, "up") else "CHoCH", "swing_low": last_l[0] if last_l else None})
            last_h[2], trend = True, "up"
        if last_l and not last_l[2] and c[j].close < last_l[1]:
            events.append({"from": last_l[0], "to": j, "price": last_l[1], "dir": "down",
                           "kind": "BOS" if trend in (None, "down") else "CHoCH", "swing_high": last_h[0] if last_h else None})
            last_l[2], trend = True, "down"
    return events


def order_blocks(c, evs):
    obs = []
    for e in evs:
        anchor = e.get("swing_low") if e["dir"] == "up" else e.get("swing_high")
        if anchor is None:
            continue
        want_bear = e["dir"] == "up"
        for k in range(anchor + 1, max(anchor - 4, -1), -1):
            if k < len(c) and ((c[k].close < c[k].open) == want_bear):
                mitigated = any((x.low <= c[k].high) if want_bear else (x.high >= c[k].low) for x in c[e["to"] + 1:])
                obs.append({"i": k, "hi": c[k].high, "lo": c[k].low, "dir": e["dir"], "mitigated": mitigated})
                break
    return obs


def fvgs(c, atr_v):
    out = []
    for i in range(2, len(c)):
        if c[i].low > c[i - 2].high and c[i].low - c[i - 2].high > 0.3 * atr_v:
            lo, hi = c[i - 2].high, c[i].low
            filled = any(x.low <= lo for x in c[i + 1:])
            out.append({"i": i - 1, "lo": lo, "hi": hi, "dir": "up", "filled": filled})
        if c[i].high < c[i - 2].low and c[i - 2].low - c[i].high > 0.3 * atr_v:
            lo, hi = c[i].high, c[i - 2].low
            filled = any(x.high >= hi for x in c[i + 1:])
            out.append({"i": i - 1, "lo": lo, "hi": hi, "dir": "down", "filled": filled})
    return out


def sr_zones(c, sw, atr_v, price):
    pts = sorted(p for _, p, _ in sw)
    clusters = []
    for p in pts:
        if clusters and p - clusters[-1][-1] < 0.4 * atr_v:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    zones = [(sum(cl) / len(cl), len(cl)) for cl in clusters if len(cl) >= 2]
    zones.sort(key=lambda z: abs(z[0] - price))
    return zones[:4]


def find_pattern(c, name, atr_v):
    def body(x): return abs(x.close - x.open)
    def rng(x): return x.high - x.low
    hits = []
    for i in range(2, len(c) - 2):
        x, p, pp = c[i], c[i - 1], c[i - 2]
        up_w, lo_w = x.high - max(x.open, x.close), min(x.open, x.close) - x.low
        ok, bull = False, True
        if name == "pinbar" and rng(x) >= atr_v:
            if lo_w >= 2 * body(x) and lo_w >= 0.6 * rng(x):
                ok, bull = True, True
            elif up_w >= 2 * body(x) and up_w >= 0.6 * rng(x):
                ok, bull = True, False
        elif name == "engulfing" and body(x) >= 0.8 * atr_v:
            if p.close < p.open and x.close > x.open and x.close >= p.open and x.open <= p.close:
                ok, bull = True, True
            elif p.close > p.open and x.close < x.open and x.close <= p.open and x.open >= p.close:
                ok, bull = True, False
        elif name == "doji":
            ok = rng(x) >= 0.8 * atr_v and body(x) <= 0.1 * rng(x)
        elif name == "inside_bar":
            ok = x.high < p.high and x.low > p.low and rng(p) >= 1.2 * atr_v
            bull = p.close > p.open
        elif name == "star":
            if pp.close < pp.open and body(pp) >= atr_v and body(p) <= 0.3 * body(pp) and x.close > x.open \
                    and x.close > (pp.open + pp.close) / 2:
                ok, bull = True, True
            elif pp.close > pp.open and body(pp) >= atr_v and body(p) <= 0.3 * body(pp) and x.close < x.open \
                    and x.close < (pp.open + pp.close) / 2:
                ok, bull = True, False
        if ok:
            hits.append((i, bull))
    return hits[-1] if hits else None


PATTERN_NAME = {"pinbar": "Pin Bar", "engulfing": "Engulfing", "doji": "Doji", "inside_bar": "Inside Bar",
                "star": "Morning/Evening Star"}


# ===================================================================== dựng biểu đồ thật

def fmt(v, d):
    return f"{v:,.{d}f}"


def build_real(spec: dict) -> tuple[TVChart, list[str]]:
    symbol = spec.get("symbol", "XAUUSD")
    tf = spec.get("tf", "H4")
    tools = [t.lower() for t in spec.get("tools") or []]
    d = DIGITS.get(symbol, 2)
    full = list(load(symbol, tf))
    n = WINDOW.get(tf, 110)
    facts: list[str] = []

    # Mẫu nến: dời cửa sổ tới vị trí mẫu nến gần nhất
    pattern = next((t.split(":", 1)[1] for t in tools if t.startswith("pattern:")), None)
    pat_hit = None
    start = max(0, len(full) - n)
    if pattern:
        a_full = atr_series(full)[-1]
        hit = find_pattern(full, pattern, a_full)
        if hit:
            k, bull = hit
            start = max(0, min(k - 45, len(full) - 60))
            end = min(len(full), k + 15)
            pat_hit = (k - start, bull)
            full_win = full[start:end]
        else:
            full_win = full[start:]
    else:
        full_win = full[start:]

    # Chỉ báo tính trên toàn bộ dữ liệu rồi cắt theo cửa sổ (tránh giai đoạn khởi động)
    s, e = start, start + len(full_win)
    closes_full = [x.close for x in full]
    c = full_win
    ch = TVChart(symbol, tf.replace("H", "") + "H" if tf.startswith("H") else "1D", c, d,
                 right_offset=8 if spec.get("scenario") else 4)
    a = atr_series(full)[e - 1]
    price = c[-1].close

    for key, col, label in (("ema20", TV["blue"], "EMA 20"), ("ema50", TV["orange"], "EMA 50"),
                            ("ema200", TV["pink"], "EMA 200"), ("sma50", TV["purple"], "SMA 50")):
        if key in tools:
            per = int(key[3:])
            vals = (ema if key.startswith("ema") else sma)(closes_full, per)[s:e]
            ch.line(vals, col, label)
    if "bollinger" in tools:
        mid, up, lo = (x[s:e] for x in bollinger(closes_full))
        ch.band(up, lo, 0, "rgba(41,98,255,0.06)", "rgba(41,98,255,0.06)")
        ch.line(mid, TV["orange"], "BB 20, 2", width=1)
        ch.line(up, TV["blue"], width=1)
        ch.line(lo, TV["blue"], width=1)
    if "supertrend" in tools:
        st = supertrend(full)[s:e]
        ch.colored_line([v for v, _ in st], [TV["up"] if t == 1 else TV["down"] for _, t in st],
                        "Supertrend 10, 3", TV["up"] if st[-1][1] == 1 else TV["down"])
        facts.append(f"Supertrend: {'xu hướng tăng' if st[-1][1] == 1 else 'xu hướng giảm'}")
    if "ichimoku" in tools:
        tk, kj, sa, sb = (x[s:e] for x in ichimoku(full))
        ch.band(sa, sb, 26, "rgba(8,153,129,0.15)", "rgba(242,54,69,0.15)")
        ch.line(tk, TV["blue"], "Tenkan 9", width=1)
        ch.line(kj, "#b71c1c", "Kijun 26", width=1)
        cloud_now = (ichimoku(full)[2][e - 27], ichimoku(full)[3][e - 27]) if e > 27 else None
        if cloud_now:
            pos = "trên" if price > max(cloud_now) else "dưới" if price < min(cloud_now) else "trong"
            facts.append(f"Giá so với mây Kumo: nằm {pos} mây")

    sw = swings(c)
    if "structure" in tools:
        for i, p, k, lab in structure_labels(sw)[-8:]:
            ch.marker(i, lab, k == "H", TV["text"], shape="circle")
    evs = breaks(c, sw)
    if "bos_choch" in tools:
        for ev in evs[-4:]:
            col = TV["up"] if ev["dir"] == "up" else TV["down"]
            ch.segment(ev["from"], ev["price"], ev["to"], ev["price"], col, ev["kind"], width=1, dash=[4, 3])
        if evs:
            last = evs[-1]
            facts.append(f"{last['kind']} {'tăng' if last['dir'] == 'up' else 'giảm'} gần nhất: {fmt(last['price'], d)}")
    if "order_blocks" in tools:
        obs = [o for o in order_blocks(c, evs) if not o["mitigated"]][-2:] or order_blocks(c, evs)[-2:]
        for o in obs:
            col = TV["up"] if o["dir"] == "up" else TV["down"]
            ch.rect(o["i"], None, o["lo"], o["hi"], col, "Bullish OB" if o["dir"] == "up" else "Bearish OB", 0.16)
        if obs:
            o = obs[-1]
            facts.append(f"{'Bullish' if o['dir'] == 'up' else 'Bearish'} Order Block: {fmt(o['lo'], d)} – {fmt(o['hi'], d)}")
    if "fvg" in tools:
        gaps = [g for g in fvgs(c, a) if not g["filled"]][-3:] or fvgs(c, a)[-2:]
        for g in gaps:
            col = TV["up"] if g["dir"] == "up" else TV["down"]
            ch.rect(g["i"], min(g["i"] + 25, len(c) + 3), g["lo"], g["hi"], col, "FVG", 0.14, "left")
        if gaps:
            g = gaps[-1]
            facts.append(f"FVG {'tăng' if g['dir'] == 'up' else 'giảm'}: {fmt(g['lo'], d)} – {fmt(g['hi'], d)}")
    zones = []
    if "sr_zones" in tools:
        zones = sr_zones(c, sw, a, price)
        for z, cnt in zones[:3]:
            col = TV["down"] if z > price else TV["up"]
            ch.rect(0, None, z - 0.15 * a, z + 0.15 * a, col, (f"{'Resistance' if z > price else 'Support'} ({cnt} touches)" if EN_MODE else
                 f"{'Kháng cự' if z > price else 'Hỗ trợ'} ({cnt} lần chạm)"), 0.15)
        res = [z for z, _ in zones if z > price]
        sup = [z for z, _ in zones if z < price]
        if res:
            facts.append(f"Kháng cự gần nhất: {fmt(min(res), d)}")
        if sup:
            facts.append(f"Hỗ trợ gần nhất: {fmt(max(sup), d)}")
    if "fib" in tools:
        seg = c[-70:]
        off = len(c) - len(seg)
        ih = max(range(len(seg)), key=lambda i: seg[i].high) + off
        il = min(range(len(seg)), key=lambda i: seg[i].low) + off
        hi, lo = c[ih].high, c[il].low
        up_leg = il < ih            # đáy trước, đỉnh sau = sóng tăng → thoái lui xuống
        a0, a1 = (il, ih) if up_leg else (ih, il)
        for lv, col in ((0, TV["gray"]), (0.236, TV["purple"]), (0.382, TV["blue"]), (0.5, TV["teal"]),
                        (0.618, TV["orange"]), (0.786, TV["down"]), (1, TV["gray"])):
            pv = hi - (hi - lo) * lv if up_leg else lo + (hi - lo) * lv
            ch.segment(a0, pv, len(c) + 6, pv, col, f"{lv:g} ({fmt(pv, d)})", width=1, label_align="left")
        ch.segment(a0, lo if up_leg else hi, a1, hi if up_leg else lo, TV["gray"], dash=[4, 4])
        gold = hi - (hi - lo) * 0.618 if up_leg else lo + (hi - lo) * 0.618
        facts.append(f"Fibonacci 0.618: {fmt(gold, d)}")
    if "pivot" in tools:
        daily = list(load(symbol, "D1"))
        prev = daily[-2] if datetime.now(timezone.utc) - daily[-1].date < timedelta(hours=20) else daily[-1]
        pv = (prev.high + prev.low + prev.close) / 3
        lv = {"P": pv, "R1": 2 * pv - prev.low, "S1": 2 * pv - prev.high,
              "R2": pv + prev.high - prev.low, "S2": pv - (prev.high - prev.low)}
        for name, v in lv.items():
            ch.price_line(v, TV["down"] if name.startswith("R") else TV["up"] if name.startswith("S") else TV["blue"], name)
        facts.append(f"Pivot ngày: {fmt(pv, d)} (R1 {fmt(lv['R1'], d)}, S1 {fmt(lv['S1'], d)})")
    if pat_hit:
        k, bull = pat_hit
        x = c[k]
        ch.rect(k - 1, k + 1, x.low, x.high, TV["orange"], "", 0.18)
        ch.marker(k, PATTERN_NAME[pattern], not bull, TV["orange"])
        facts.append(f"{PATTERN_NAME[pattern]} {'tăng' if bull else 'giảm'}: nến {(x.date + timedelta(hours=7)):%H:%M %d/%m}")

    # Panel phụ
    if "rsi" in tools:
        r = rsi(closes_full)[s:e]
        ch.pane([{"kind": "line", "values": r, "color": TV["purple"], "levels": [70, 30]}])
        facts.append(f"RSI 14: {r[-1]:.1f}")
    elif "macd" in tools:
        m, sg, h = (x[s:e] for x in macd(closes_full))
        ch.pane([{"kind": "histogram", "values": h, "colors": [("#26a69a" if v >= 0 else "#ef5350") for v in h]},
                 {"kind": "line", "values": m, "color": TV["blue"]},
                 {"kind": "line", "values": sg, "color": TV["orange"]}])
    elif "volume" in tools and any(x.volume for x in c):
        ch.pane([{"kind": "histogram", "values": [x.volume for x in c],
                  "colors": [("#26a69a80" if x.close >= x.open else "#ef535080") for x in c]}])

    # Mũi tên kịch bản
    sc = spec.get("scenario")
    if sc in ("up", "down"):
        targets = [z for z, _ in zones] or [x.high for x in c[-40:]] + [x.low for x in c[-40:]]
        tgt = (min([t for t in targets if t > price], default=price + 2 * a) if sc == "up"
               else max([t for t in targets if t < price], default=price - 2 * a))
        ch.segment(len(c) - 1, price, len(c) + 6, tgt, TV["up"] if sc == "up" else TV["down"], width=2, arrow=True)

    ts = c[-1].date + timedelta(hours=7)
    facts.insert(0, f"Biểu đồ {symbol} khung {tf}, dữ liệu thật tới {ts:%H:%M %d/%m/%Y} (giờ VN)")
    return ch, facts


# ===================================================================== mô hình minh họa

def build_illustration(spec: dict) -> tuple[TVChart, list[str]]:
    path = [float(p) for p in spec["path"]]
    bars = int(min(8, max(3, spec.get("bars_per_leg", 5))))
    raw = synth_candles(path, bars)
    t0 = datetime(2026, 1, 5, tzinfo=timezone.utc)
    c = [Candle(t0 + timedelta(hours=i), *x) for i, x in enumerate([[path[0]] * 4] + raw)]
    anchors = [k * bars for k in range(len(path))]
    idx = lambda i: anchors[i] if i < len(anchors) else anchors[-1] + (i - len(anchors) + 1) * bars

    ch = TVChart("Mô hình minh họa", "", c, 2, right_offset=6)
    closes = [x.close for x in c]
    inds = [i.lower() for i in spec.get("indicators") or []]
    if "ema20" in inds:
        ch.line(ema(closes, 20), TV["blue"], "EMA 20")
    for z in spec.get("zones") or []:
        start = idx(z["start"]) if z.get("start") is not None else 0
        ch.rect(start, None, z["from"], z["to"], COLOR.get(z.get("color"), TV["orange"]), z.get("label", ""), 0.18)
    for h in spec.get("hlines") or []:
        ch.price_line(h["price"], COLOR.get(h.get("color"), TV["text"]), h.get("label", ""),
                      style=0 if h.get("style") == "solid" else 2)
    for ln in spec.get("lines") or []:
        ch.segment(idx(ln["from"][0]), ln["from"][1], idx(ln["to"][0]), ln["to"][1],
                   COLOR.get(ln.get("color"), TV["blue"]), ln.get("label", ""), width=2)
    for ar in spec.get("arrows") or []:
        ch.segment(idx(ar["from"][0]), ar["from"][1], idx(ar["to"][0]), ar["to"][1],
                   COLOR.get(ar.get("color"), TV["text"]), width=2, arrow=True)
    if spec.get("fib"):
        f = spec["fib"]
        a, b = path[f["from"]], path[f["to"]]
        for lv in [0] + list(f.get("levels") or [0.382, 0.5, 0.618]) + [1]:
            pv = b - (b - a) * lv
            ch.segment(idx(f["from"]), pv, len(c) + 4, pv, TV["orange"], f"{lv:g}", label_align="left")
    for pt in spec.get("points") or []:
        i = pt["at"]
        if 0 <= i < len(path):
            prev = path[i - 1] if i else path[min(1, len(path) - 1)]
            ch.marker(idx(i), pt["label"][:10], path[i] >= prev, TV["text"], shape="circle")
    if "rsi" in inds:
        ch.pane([{"kind": "line", "values": rsi(closes), "color": TV["purple"], "levels": [70, 30]}])
    elif "volume" in inds:
        mult = spec.get("volume") or []
        vols = [(x.high - x.low) * (mult[min(len(mult) - 1, max(0, (i - 1) // bars))] if mult else 1)
                for i, x in enumerate(c)]
        ch.pane([{"kind": "histogram", "values": vols,
                  "colors": [("#26a69a80" if x.close >= x.open else "#ef535080") for x in c]}])
    ch.spec["timeAxis"] = False
    return ch, []


def build(spec: dict) -> tuple[TVChart, list[str]]:
    if spec.get("mode") == "illustration" and spec.get("path"):
        return build_illustration(spec)
    return build_real(spec)
