"""Tìm setup SMC thật trên dữ liệu (mô hình bán/mua của tổ chức) cho Reels kiến thức DecodeFx Trading.

Mô hình (bản SELL, BUY đối xứng):
  1. Xu hướng giảm: giá phá đáy cũ (BOS) – EMA50 dốc xuống
  2. Vùng giao dịch: đỉnh SWH (gốc cú giảm) → đáy SWL (đáy của nhịp giảm có BOS)
  3. Vùng cung: nến tăng cuối cùng trước cú giảm từ SWH (order block) → [đáy nến đó, đỉnh SWH]
  4. Chỉ bán ở vùng Premium: vùng cung phải nằm trên mức 50% của SWH–SWL
  5. Giá hồi lên chạm vùng cung (không phá SWH), nến giảm xác nhận → vào lệnh tại giá đóng cửa nến đó
  6. Mục tiêu: thanh khoản dưới SWL · SL trên vùng cung · R:R ≥ 2.5
  7. Kết quả thật: chạm TP trước SL.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.reels.indi.boss import frame, rma, true_range, ema


@dataclass
class SMC:
    symbol: str
    tf: str
    side: str                  # sell | buy
    d: pd.DataFrame = field(repr=False)
    bos: list                  # [(i_from, i_break, price)] các lần phá cấu trúc
    swh: int                   # SELL: đỉnh gốc; BUY: đáy gốc (điểm mở đầu nhịp)
    swl: int                   # SELL: đáy nhịp; BUY: đỉnh nhịp
    zone: tuple                # (i_ob, lo, hi)
    touch: int                 # nến chạm vùng
    k: int                     # nến xác nhận (vào lệnh tại close)
    entry: float
    sl: float
    tp: float
    hit: int                   # nến chạm TP
    rr: float
    system: str = "supply"     # supply: vùng cung/cầu + Premium/Discount · ob: Order Block + FVG
    fvg: tuple | None = None   # (i giữa, lo, hi) khoảng trống giá trong cú phá cấu trúc (hệ thống ob)

    @property
    def p_ext(self):
        return self.d.high.iat[self.swh] if self.side == "sell" else self.d.low.iat[self.swh]

    @property
    def p_end(self):
        return self.d.low.iat[self.swl] if self.side == "sell" else self.d.high.iat[self.swl]


def pivots(h: np.ndarray, l: np.ndarray, n: int = 3):
    ph = [i for i in range(n, len(h) - n) if h[i] == max(h[i - n:i + n + 1])]
    pl = [i for i in range(n, len(l) - n) if l[i] == min(l[i - n:i + n + 1])]
    return ph, pl


def _scan(d: pd.DataFrame, symbol: str, tf: str, side: str, system: str = "supply") -> list[SMC]:
    s = 1 if side == "sell" else -1
    # đưa bài toán BUY về SELL bằng cách lật giá
    H = d.high.to_numpy() if s == 1 else -d.low.to_numpy()
    L = d.low.to_numpy() if s == 1 else -d.high.to_numpy()
    O = d.open.to_numpy() * s
    C = d.close.to_numpy() * s
    atr = rma(true_range(d), 14).to_numpy()
    e50 = ema(d.close, 50).to_numpy() * s
    ph, pl = pivots(H, L, 3)
    out = []
    for h in ph:
        if h < 60 or h > len(d) - 30 or np.isnan(atr[h]):
            continue
        if not e50[h] < e50[h - 20]:                    # xu hướng giảm (bản lật: tăng)
            continue
        # đáy cũ gần nhất trước SWH – bị phá thì là BOS
        prior = [p for p in pl if h - 40 < p < h]
        if not prior:
            continue
        pl_old = prior[-1]
        lows_after = [p for p in pl if h < p < h + 60]
        if not lows_after:
            continue
        lo_i = min(lows_after, key=lambda p: L[p])
        if H[h] < max(H[h:lo_i + 1]):                   # SWH phải là đỉnh cao nhất của cả nhịp giảm
            continue
        brk = next((i for i in range(h + 1, lo_i + 1) if C[i] < L[pl_old]), None)
        if brk is None:
            continue
        rng = H[h] - L[lo_i]
        if rng < 4 * atr[h]:
            continue
        # BOS trước đó (xác nhận xu hướng lớn): 1 đáy cũ hơn bị phá trước SWH
        older = [p for p in pl if h - 120 < p < pl_old]
        bos = []
        for p in older[::-1]:
            b = next((i for i in range(p + 1, h) if C[i] < L[p]), None)
            if b is not None and b - p > 3:
                bos.append((p, b, L[p]))
                break
        bos.append((pl_old, brk, L[pl_old]))
        # vùng cung: nến tăng cuối cùng trong 6 nến trước khi giảm từ SWH
        ob = next((i for i in range(h, h - 7, -1) if C[i] > O[i]), None)
        if ob is None:
            continue
        fvg = None
        if system == "ob":
            # Order Block = đúng thân + râu của nến tăng cuối cùng; phải để lại khoảng trống giá (FVG) trong cú phá cấu trúc
            z_lo, z_hi = L[ob], H[ob]
            if not (0.3 * atr[h] <= z_hi - z_lo <= rng * 0.3):
                continue
            for i in range(ob + 1, min(brk + 1, len(d) - 1)):
                if L[i - 1] - H[i + 1] >= 0.15 * atr[h]:
                    fvg = (i, H[i + 1], L[i - 1])
                    break
            if fvg is None:
                continue
            ceiling = max(z_hi, H[h])
        else:
            z_lo, z_hi = min(L[ob], O[ob]), H[h]
            mid = (H[h] + L[lo_i]) / 2
            if z_lo < mid or z_hi - z_lo > rng * 0.35:
                continue
            ceiling = z_hi
        # hồi lên chạm vùng, không phá đỉnh, không phá đáy SWL trước đó
        touch = None
        for i in range(lo_i + 1, min(len(d) - 5, lo_i + 50)):
            if H[i] > ceiling or L[i] < L[lo_i]:
                break
            if H[i] >= z_lo:
                touch = i
                break
        if touch is None:
            continue
        k = next((i for i in range(touch, min(len(d) - 3, touch + 4)) if C[i] < O[i] and H[i] <= ceiling), None)
        if k is None:
            continue
        entry = C[k]
        sl = ceiling + 0.15 * atr[h]
        tp = L[lo_i] - 0.05 * atr[h]
        risk = sl - entry
        if risk <= 0:
            continue
        rr = (entry - tp) / risk
        if rr < 2.5 or rr > 8:
            continue
        hit = None
        for i in range(k + 1, min(len(d), k + 120)):
            if H[i] >= sl:
                break
            if L[i] <= tp:
                hit = i
                break
        if hit is None:
            continue
        f = (lambda x: x) if s == 1 else (lambda x: -x)
        lohi = (lambda a, b: (f(a), f(b))) if s == 1 else (lambda a, b: (f(b), f(a)))
        out.append(SMC(symbol, tf, side, d, [(a, b, f(p)) for a, b, p in bos], h, lo_i,
                       (ob, *lohi(z_lo, z_hi)), touch, k, f(entry), f(sl), f(tp), hit, round(rr, 2),
                       system, (fvg[0], *lohi(fvg[1], fvg[2])) if fvg else None))
    return out


def find(symbols=("XAUUSD", "EURUSD", "GBPUSD"), tf: str = "M15", system: str = "supply") -> list[SMC]:
    from src.data.prices import get_m5
    iv = {"M15": "15m", "M5": "5m", "H1": "60m"}[tf]
    out = []
    for sym in symbols:
        try:
            d = frame(get_m5(sym, "60d", interval=iv))
        except Exception as exc:
            print(f"! {sym}: {exc}")
            continue
        for side in ("sell", "buy"):
            out += _scan(d, sym, tf, side, system)
    # đẹp: R:R vừa phải, chạy tới TP không quá lâu
    seen, uniq = set(), []
    for x in out:
        key = (x.symbol, x.side, x.k)
        if key not in seen:
            seen.add(key)
            uniq.append(x)
    uniq.sort(key=lambda x: (abs(x.rr - 3.2), x.hit - x.k))
    return uniq


if __name__ == "__main__":
    import sys
    for x in find(system=sys.argv[1] if len(sys.argv) > 1 else "supply")[:15]:
        print(x.symbol, x.side, x.d.index[x.k], f"RR {x.rr}", f"tới TP {x.hit - x.k} nến", f"BOS {len(x.bos)}")
