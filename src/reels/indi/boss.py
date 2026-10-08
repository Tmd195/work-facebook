"""Chạy lại indicator "BOSS M5 SNIPER AI" bản V7 và V4 (Pine Script của anh) trên nến M5 thật – tìm lệnh làm video.

V7 – bám sát từng điều kiện trong file Pine (Desktop/Broker/DecodeFx Trader/Bot M5 Sniper AI V7):
EMA20/50 M5, SuperTrend(2.2,10), DMI/ADX 14, RSI 14, MACD 12/26/9, ATR 14 + bộ lọc sideway/đuổi giá/nến sốc,
M15 bắt buộc cùng xu hướng, H1 chỉ chặn khi trend mạnh ngược lại (close[1] + lookahead_on = nến khung lớn đã đóng),
5 setup SWEEP/BREAKOUT/RECLAIM/MOMENTUM/PULLBACK, điểm xác nhận phụ ≥ 3/5.
Quản lý lệnh: SL 6 giá, TP 5/10/15, chạm TP1 dời SL về hoà, chạm TP2 khoá SL tại TP1, chạm TP3 đóng lệnh.

V4 – chấm điểm 9 tiêu chí (EMA, độ dốc EMA, SuperTrend 2.5, ADX≥18, RSI, MACD, VWAP ngày, H1 EMA50/200, volume),
chế độ "Cân bằng" cần ≥ 6/9 + nến kích hoạt (pullback EMA20 / phá đỉnh-đáy 5 nến / nhấn chìm) + không đuổi giá (≤1.5 ATR).
Quản lý lệnh: SL 5 giá, TP 5/10/15; SL KHÔNG dời – chỉ đóng khi chạm SL hoặc TP3 (TP1/TP2 chỉ đánh dấu).

Khác biệt có thể có so với TradingView: nguồn giá (Yahoo GC=F quy đổi spot, volume hợp đồng tương lai thay cho
tick volume của sàn) và mốc ngày giao dịch → trước khi đăng nên đối chiếu lệnh trên TradingView.

    python -m src.reels.indi.boss            # backtest 60 ngày XAUUSD, in thống kê + lệnh đẹp nhất
"""
from dataclasses import dataclass, field
from datetime import timedelta

import numpy as np
import pandas as pd

TP = (5.0, 10.0, 15.0)
RULES = {"V7": dict(sl=6.0, max_day=10, cooldown=1, trail=True),     # cooldown tính từ nến đóng lệnh
         "V4": dict(sl=5.0, max_day=20, cooldown=2, trail=False)}    # cooldown tính từ nến vào lệnh
MIN_CONFIRM = 3


# ------------------------------------------------------------------ hàm chỉ báo giống Pine

def ema(s: pd.Series, n: int) -> pd.Series:
    """ta.ema: khởi tạo bằng SMA n nến đầu."""
    a, v = 2 / (n + 1), s.to_numpy(float)
    out = np.full(len(v), np.nan)
    if len(v) >= n:
        out[n - 1] = v[:n].mean()
        for i in range(n, len(v)):
            out[i] = a * v[i] + (1 - a) * out[i - 1]
    return pd.Series(out, s.index)


def rma(s: pd.Series, n: int) -> pd.Series:
    v = s.to_numpy(float)
    out = np.full(len(v), np.nan)
    start = np.argmax(~np.isnan(v))
    if len(v) - start >= n:
        out[start + n - 1] = np.nanmean(v[start:start + n])
        for i in range(start + n, len(v)):
            out[i] = (v[i] + (n - 1) * out[i - 1]) / n
    return pd.Series(out, s.index)


def true_range(d: pd.DataFrame) -> pd.Series:
    pc = d.close.shift()
    tr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1)
    tr.iloc[0] = d.high.iloc[0] - d.low.iloc[0]
    return tr


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    ch = s.diff()
    up, dn = rma(ch.clip(lower=0), n), rma((-ch).clip(lower=0), n)
    return 100 - 100 / (1 + up / dn.replace(0, np.nan)).fillna(100)


def supertrend(d: pd.DataFrame, factor: float, n: int) -> pd.Series:
    """Trả về direction (-1 = tăng, 1 = giảm) như ta.supertrend."""
    atr = rma(true_range(d), n).to_numpy()
    hl2 = ((d.high + d.low) / 2).to_numpy()
    close = d.close.to_numpy()
    up, lo = hl2 + factor * atr, hl2 - factor * atr
    dirn = np.ones(len(d))
    st = np.full(len(d), np.nan)
    for i in range(len(d)):
        if i > 0:
            pl, pu = (lo[i - 1] if not np.isnan(lo[i - 1]) else 0), (up[i - 1] if not np.isnan(up[i - 1]) else 0)
            lo[i] = lo[i] if (lo[i] > pl or close[i - 1] < pl) else pl
            up[i] = up[i] if (up[i] < pu or close[i - 1] > pu) else pu
        if i == 0 or np.isnan(atr[i - 1]):
            dirn[i] = 1
        elif st[i - 1] == up[i - 1]:
            dirn[i] = -1 if close[i] > up[i] else 1
        else:
            dirn[i] = 1 if close[i] < lo[i] else -1
        st[i] = lo[i] if dirn[i] == -1 else up[i]
    return pd.Series(dirn, d.index)


def dmi(d: pd.DataFrame, n: int = 14, smooth: int = 14):
    upm, dnm = d.high.diff(), -d.low.diff()
    plus_dm = np.where((upm > dnm) & (upm > 0), upm, 0.0)
    minus_dm = np.where((dnm > upm) & (dnm > 0), dnm, 0.0)
    tr = rma(true_range(d), n)
    p = 100 * rma(pd.Series(plus_dm, d.index), n) / tr
    m = 100 * rma(pd.Series(minus_dm, d.index), n) / tr
    s = (p + m).replace(0, 1)
    adx = 100 * rma((p - m).abs() / s, smooth)
    return p, m, adx


def htf(d: pd.DataFrame, rule: str) -> pd.DataFrame:
    """request.security(tf, x[1], lookahead_on): giá trị của nến khung lớn ĐÃ ĐÓNG ngay trước nến hiện tại."""
    g = d.resample(rule, label="left", closed="left").agg({"close": "last"}).dropna()
    g["e20"], g["e50"], g["e200"] = ema(g.close, 20), ema(g.close, 50), ema(g.close, 200)
    g = g.shift(1)
    key = d.index.floor(rule)
    return g.reindex(key).set_axis(d.index)


# ------------------------------------------------------------------ tín hiệu

def vwap_daily(d: pd.DataFrame, tday) -> pd.Series:
    """ta.vwap(hlc3) – neo lại mỗi ngày giao dịch."""
    tp = (d.high + d.low + d.close) / 3
    v = d.volume.fillna(0)
    g = pd.Series(tday, d.index)
    pv, vv = (tp * v).groupby(g).cumsum(), v.groupby(g).cumsum()
    return (pv / vv.replace(0, np.nan)).fillna(tp)


def trading_day(idx: pd.DatetimeIndex):
    """Ngày giao dịch vàng trên TradingView bắt đầu 17:00 New York."""
    return (idx.tz_convert("America/New_York") + timedelta(hours=7)).date


def signals_v4(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    c, o, h, l = d.close, d.open, d.high, d.low
    ef, es = ema(c, 20), ema(c, 50)
    d["e20"], d["e50"], d["e200"] = ef, es, ema(c, 200)
    sd = supertrend(d, 2.5, 10)
    r = rsi(c, 14)
    d["rsi"] = r
    macd = ema(c, 12) - ema(c, 26)
    sig = ema(macd.dropna(), 9).reindex(d.index)
    hist = macd - sig
    pdi, mdi, adx = dmi(d, 14, 14)
    atr = rma(true_range(d), 14)
    vw = vwap_daily(d, trading_day(d.index))
    vma = d.volume.rolling(20).mean()
    volOK = vma.isna() | (d.volume >= vma * 0.8)
    h1 = htf(d, "60min")
    rng = (h - l).clip(lower=0.01)
    br = (c - o).abs() / rng
    bullC, bearC = (c > o) & (br >= .3), (c < o) & (br >= .3)
    engL = (c > o) & (c.shift() < o.shift()) & (o <= c.shift()) & (c >= o.shift())
    engS = (c < o) & (c.shift() > o.shift()) & (o >= c.shift()) & (c <= o.shift())
    pbL, pbS = (l <= ef) & (c > ef) & bullC, (h >= ef) & (c < ef) & bearC
    hp, lp = h.rolling(5).max().shift(), l.rolling(5).min().shift()
    boL, boS = (c > hp) & bullC & (br >= .45), (c < lp) & bearC & (br >= .45)
    trigL, trigS = pbL | boL | engL, pbS | boS | engS
    distL, distS = (c - ef >= 0) & (c - ef <= atr * 1.5), (ef - c >= 0) & (ef - c <= atr * 1.5)

    def i(x):
        return x.fillna(False).astype(int)
    scL = (i((ef > es) & (c > ef)) + i(ef > ef.shift(2)) + i(sd < 0) + i((pdi > mdi) & (adx >= 18))
           + i((r >= 50) & (r <= 75)) + i((macd > sig) & (hist > 0)) + i(c >= vw)
           + i((h1.close > h1.e50) & (h1.e50 > h1.e200)) + i(volOK))
    scS = (i((ef < es) & (c < ef)) + i(ef < ef.shift(2)) + i(sd > 0) + i((mdi > pdi) & (adx >= 18))
           + i((r <= 50) & (r >= 25)) + i((macd < sig) & (hist < 0)) + i(c <= vw)
           + i((h1.close < h1.e50) & (h1.e50 < h1.e200)) + i(volOK))
    rawL, rawS = (scL >= 6) & trigL & distL, (scS >= 6) & trigS & distS
    buy = rawL & (~rawS | (scL > scS))
    sell = rawS & ~buy
    d["setL"] = np.where(buy, np.select([boL, pbL], ["BREAKOUT", "PULLBACK"], "ENGULFING"), "")
    d["setS"] = np.where(sell, np.select([boS, pbS], ["BREAKOUT", "PULLBACK"], "ENGULFING"), "")
    d["scL"], d["scS"] = scL, scS
    return d


def signals(d: pd.DataFrame, version: str = "V7") -> pd.DataFrame:
    return signals_v4(d) if version == "V4" else signals_v7(d)


def signals_v7(d: pd.DataFrame) -> pd.DataFrame:
    """d: index thời gian UTC, cột open high low close volume (M5). Trả về d kèm cột buy/sell/setup/score."""
    d = d.copy()
    c, o, h, l = d.close, d.open, d.high, d.low
    e20, e50 = ema(c, 20), ema(c, 50)
    d["e20"], d["e50"], d["e200"] = e20, e50, ema(c, 200)
    m5L, m5S = (c > e20) & (e20 > e50), (c < e20) & (e20 < e50)
    slL, slS = e20 > e20.shift(2), e20 < e20.shift(2)
    sd = supertrend(d, 2.2, 10)
    stL, stS = sd < 0, sd > 0
    pdi, mdi, adx = dmi(d, 14, 14)
    diL, diS, adxOK = pdi > mdi, mdi > pdi, adx >= 14
    r = rsi(c, 14)
    d["rsi"] = r
    rL, rS = (r >= 50) & (r <= 72), (r <= 50) & (r >= 28)
    macd = ema(c, 12) - ema(c, 26)
    sig = ema(macd.dropna(), 9).reindex(d.index)
    hist = macd - sig
    mL = (macd > sig) | (hist > hist.shift())
    mS = (macd < sig) | (hist < hist.shift())
    atr = rma(true_range(d), 14)
    atrma = atr.rolling(50).mean()
    ratio = (atr / atrma).where(atrma > 0, 1.0)
    atrOK = (ratio >= 0.5) & (ratio <= 2.2)
    gapOK = (e20 - e50).abs() >= atr * 0.05
    notChase = (c - e20).abs() <= atr * 1.15
    shockOK = (h - l) <= atr * 2.2
    vma = d.volume.rolling(20).mean()
    volOK = d.volume.isna() | vma.isna() | (d.volume >= vma * 0.55)
    m15, h1 = htf(d, "15min"), htf(d, "60min")
    m15L, m15S = (m15.close > m15.e20) & (m15.e20 > m15.e50), (m15.close < m15.e20) & (m15.e20 < m15.e50)
    h1L, h1S = h1.close > h1.e50, h1.close < h1.e50
    h1SL, h1SS = h1L & (h1.e50 > h1.e200), h1S & (h1.e50 < h1.e200)
    macroL, macroS = m15L & ~h1SS, m15S & ~h1SL
    pH, pL = h.shift().rolling(6).max(), l.shift().rolling(6).min()
    bull, bear = c > o, c < o
    body = (c - o).abs()
    lw, uw = pd.concat([o, c], axis=1).min(axis=1) - l, h - pd.concat([o, c], axis=1).max(axis=1)
    sb = body.clip(lower=0.01)
    engL = bull & (c.shift() < o.shift()) & (c >= o.shift())
    engS = bear & (c.shift() > o.shift()) & (c <= o.shift())
    rejL, rejS = bull & (lw >= sb), bear & (uw >= sb)
    pbL = (l <= e20 + atr * .35) & (l >= e50 - atr * .55) & (c > e20) & bull
    pbS = (h >= e20 - atr * .35) & (h <= e50 + atr * .55) & (c < e20) & bear
    swL, swS = (l < pL) & (c > pL) & bull, (h > pH) & (c < pH) & bear
    boL, boS = (c > pH) & bull & (body >= atr * .15), (c < pL) & bear & (body >= atr * .15)
    rcL = (c > e20) & (c.shift() <= e20.shift()) & (e20 > e50) & bull
    rcS = (c < e20) & (c.shift() >= e20.shift()) & (e20 < e50) & bear
    moL = bull & (c > h.shift()) & (body >= atr * .12) & (r > 51)
    moS = bear & (c < l.shift()) & (body >= atr * .12) & (r < 49)
    pcL, pcS = engL | rejL | (c > h.shift()), engS | rejS | (c < l.shift())
    rL3, rS3 = c - (l.rolling(3).min() - .2), (h.rolling(3).max() + .2) - c
    stcL, stcS = (rL3 > .2) & (rL3 <= 5.8), (rS3 > .2) & (rS3 <= 5.8)
    scL = adxOK.astype(int) + rL.astype(int) + mL.astype(int) + h1L.astype(int) + volOK.astype(int)
    scS = adxOK.astype(int) + rS.astype(int) + mS.astype(int) + h1S.astype(int) + volOK.astype(int)
    coreL = macroL & m5L & slL & stL & diL & atrOK & gapOK & notChase & shockOK & stcL
    coreS = macroS & m5S & slS & stS & diS & atrOK & gapOK & notChase & shockOK & stcS
    okL, okS = coreL & (scL >= MIN_CONFIRM), coreS & (scS >= MIN_CONFIRM)
    # thứ tự đặt tên setup giống Pine: SWEEP > BREAKOUT > RECLAIM > MOMENTUM > PULLBACK
    setL = np.select([okL & swL, okL & boL, okL & rcL, okL & moL & volOK, okL & pbL & pcL],
                     ["SWEEP", "BREAKOUT", "RECLAIM", "MOMENTUM", "PULLBACK"], "")
    setS = np.select([okS & swS, okS & boS, okS & rcS, okS & moS & volOK, okS & pbS & pcS],
                     ["SWEEP", "BREAKOUT", "RECLAIM", "MOMENTUM", "PULLBACK"], "")
    d["setL"], d["setS"], d["scL"], d["scS"] = setL, setS, scL, scS
    return d


@dataclass
class Trade:
    version: str
    side: int                      # 1 BUY, -1 SELL
    setup: str
    score: int
    i0: int                        # nến vào lệnh (đóng nến)
    entry: float
    hits: list = field(default_factory=list)      # [(i, "TP1", giá), ...]
    i1: int | None = None          # nến đóng lệnh
    result: str = "OPEN"           # TP3 | LOCK TP1 | BE | SL | OPEN
    pnl: float = 0.0               # giá (USD/oz) – kết quả cả lệnh tính theo mức đóng lệnh

    @property
    def sl(self):
        return self.entry - self.side * RULES[self.version]["sl"]

    @property
    def score_max(self):
        return 9 if self.version == "V4" else 5

    def tp(self, k):
        return self.entry + self.side * TP[k]


def trades(d: pd.DataFrame, version: str = "V7") -> list[Trade]:
    """Mô phỏng đúng thứ tự xử lý trong Pine trên từng nến M5 đã đóng.
    V7: quản lý lệnh trước rồi mới xét vào lệnh; V4: vào lệnh trước, quản lý từ nến sau nến vào lệnh."""
    R = RULES[version]
    out = []
    st = dict(cur=None, stop=0.0, tp1=False, tp2=False, last=None, today=0)
    H, L, C = d.high.to_numpy(), d.low.to_numpy(), d.close.to_numpy()
    tday = trading_day(d.index)

    def close_at(i, result, price):
        cur = st["cur"]
        cur.result, cur.pnl, cur.i1 = result, cur.side * (price - cur.entry), i
        cur.hits.append((i, result, price))
        if R["trail"]:
            st["last"] = i
        st["cur"] = None

    def entry(i):
        if st["cur"] is not None or st["today"] >= R["max_day"]:
            return
        if st["last"] is not None and i - st["last"] < R["cooldown"]:
            return
        side = 1 if d.setL.iat[i] else (-1 if d.setS.iat[i] else 0)
        if not side:
            return
        cur = Trade(version, side, d.setL.iat[i] or d.setS.iat[i],
                    int(d.scL.iat[i] if side == 1 else d.scS.iat[i]), i, float(C[i]))
        st.update(cur=cur, stop=cur.sl, tp1=False, tp2=False, today=st["today"] + 1)
        if not R["trail"]:
            st["last"] = i
        out.append(cur)

    def manage(i):
        cur = st["cur"]
        if cur is None or i <= cur.i0:
            return
        s = cur.side

        def hit(p):
            return H[i] >= p if s == 1 else L[i] <= p
        if (L[i] <= st["stop"]) if s == 1 else (H[i] >= st["stop"]):
            res = ("LOCK TP1" if st["tp2"] else ("BE" if st["tp1"] else "SL")) if R["trail"] else "SL"
            close_at(i, res, st["stop"])
        elif version == "V4":
            if hit(cur.tp(2)):
                close_at(i, "TP3", cur.tp(2))
            elif not st["tp2"] and hit(cur.tp(1)):
                st.update(tp1=True, tp2=True)
                cur.hits.append((i, "TP2", cur.tp(1)))
            elif not st["tp1"] and hit(cur.tp(0)):
                st["tp1"] = True
                cur.hits.append((i, "TP1", cur.tp(0)))
        else:
            if not st["tp1"] and hit(cur.tp(0)):
                st.update(tp1=True, stop=cur.entry)
                cur.hits.append((i, "TP1", cur.tp(0)))
            if not st["tp2"] and hit(cur.tp(1)):
                st.update(tp2=True, stop=cur.tp(0))
                cur.hits.append((i, "TP2", cur.tp(1)))
            if hit(cur.tp(2)):
                close_at(i, "TP3", cur.tp(2))

    day = None
    for i in range(len(d)):
        if tday[i] != day:
            day, st["today"] = tday[i], 0
        if version == "V4":
            entry(i)
            manage(i)
        else:
            manage(i)
            entry(i)
    return out


def frame(series) -> pd.DataFrame:
    """Series (src.data.prices) → DataFrame M5."""
    return pd.DataFrame([dict(t=c.date, open=c.open, high=c.high, low=c.low, close=c.close, volume=c.volume)
                         for c in series.candles]).set_index("t")


def run(version: str = "V7", code: str = "XAUUSD", rng: str = "60d", raw: pd.DataFrame | None = None):
    from src.data.prices import get_m5
    raw = frame(get_m5(code, rng)) if raw is None else raw
    d = signals(raw, version)
    return d, trades(d, version)


if __name__ == "__main__":
    import collections
    from src.data.prices import get_m5
    raw = frame(get_m5("XAUUSD", "60d"))
    for ver in ("V7", "V4"):
        d, tr = run(ver, raw=raw)
        done = [t for t in tr if t.result != "OPEN"]
        print(f"\n== {ver}: {len(d)} nến M5 {d.index[0]:%d/%m}→{d.index[-1]:%d/%m} – {len(tr)} lệnh")
        print("Kết quả:", dict(collections.Counter(t.result for t in done)), f"| tổng {sum(t.pnl for t in done):+.1f} giá")
        print("Theo setup:", dict(collections.Counter(t.setup for t in tr)))
        best = sorted((t for t in done if t.result == "TP3"), key=lambda t: t.i1 - t.i0)
        for t in best[:6]:
            print(f"  {'BUY ' if t.side == 1 else 'SELL'} {t.setup:9} {d.index[t.i0]:%d/%m %H:%M} UTC  entry {t.entry:.2f}"
                  f"  → TP3 sau {t.i1 - t.i0} nến  ({t.score}/{t.score_max})")
