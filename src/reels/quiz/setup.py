"""Tìm setup THẬT trong dữ liệu quá khứ cho Reels "BẠN SẼ BUY HAY SELL?" – nhiều hệ thống giao dịch (đa dạng như kênh mẫu):

  range    chạm biên vùng đi ngang + nến từ chối          → vào ngược biên
  double   đỉnh đôi / đáy đôi, phá neckline                → TP = chiều cao mô hình (measured move)
  fibo     sóng đẩy mạnh → hồi về vùng Fibo 0.5–0.618       → vào theo xu hướng, TP = đỉnh/đáy cũ
  retest   phá vỡ kháng cự/hỗ trợ → quay lại kiểm tra       → vào theo hướng phá vỡ
  abcd     mô hình ABCD (CD ≈ AB) tại điểm D đảo chiều      → vào đảo chiều

Lệnh phải THỰC SỰ chạm TP trước SL. Không phải tín hiệu; chỉ là ví dụ minh hoạ trên dữ liệu cũ.
Chú thích (ann) là danh sách hình vẽ chung để bộ dựng vẽ, toạ độ theo chỉ số nến trong cửa sổ:
  ("zone", i0, p0, p1, màu, nhãn)            dải ngang từ nến i0 tới mép phải
  ("line", i0, p0, i1, p1, màu, nhãn, nét_đứt)
  ("tag", i, p, chữ, màu, ở_trên)
  ("path", [(i, p), ...], màu)
"""
from dataclasses import dataclass, field

from src.analysis import to_h4
from src.chart_tools import DIGITS
from src.data.prices import get_intraday, get_m1, get_m5

CONTEXT = 46          # số nến trước điểm vào lệnh (ít nến → nến dày, nhìn rõ như mẫu)
LOOK = 40             # nến dùng để xác định vùng giao dịch
MAX_RUN = 60          # tối đa số nến theo dõi nhịp chạy sau khi vào lệnh
MIN_R = 3.5           # nhịp chạy tối thiểu (bội số rủi ro) – lệnh phải "ăn dài" như video mẫu
SYSTEMS = ["range", "double", "fibo", "retest", "abcd"]


@dataclass
class Setup:
    symbol: str
    tf: str
    digits: int
    o: list
    h: list
    l: list
    c: list
    k: int            # chỉ số nến vào lệnh (trong cửa sổ)
    hit: int          # chỉ số nến chạm TP
    side: str         # "sell" | "buy"
    entry: float
    sl: float
    tp: float
    system: str
    name: str         # tên mô hình hiện trên màn hình
    reason: str       # cụm đọc: "Nếu bạn hiểu hết {reason} và Sell thì…"
    ann: list = field(default_factory=list)


def _atr(h, l, c, i, n=14):
    trs = [max(h[j] - l[j], abs(h[j] - c[j - 1]), abs(l[j] - c[j - 1])) for j in range(max(1, i - n + 1), i + 1)]
    return sum(trs) / len(trs)


def _pivots(h, l, a, b, w=3):
    """Đỉnh/đáy xoay chiều đã xác nhận trong [a, b) – xen kẽ H/L (giữ điểm cực trị hơn khi trùng loại)."""
    out = []
    for i in range(max(a, w), min(b - w, len(h) - w)):    # chỉ đỉnh/đáy đã xác nhận TRƯỚC điểm b (không nhìn trước)
        hi, lo = h[i] == max(h[i - w: i + w + 1]), l[i] == min(l[i - w: i + w + 1])
        for kind, p in [x for x in (("H", h[i]) if hi else None, ("L", l[i]) if lo else None) if x]:
            if out and out[-1][2] == kind:
                if (kind == "H" and p > out[-1][1]) or (kind == "L" and p < out[-1][1]):
                    out[-1] = (i, p, kind)
                continue
            out.append((i, p, kind))
    return out


def _run(h, l, k, side, entry, sl):
    """Nhịp chạy THẬT sau khi vào lệnh: đỉnh/đáy xa nhất giá đạt được trước khi chạm SL (hoặc hết MAX_RUN nến).
    Trả về (chỉ số nến đỉnh, quãng chạy theo R)."""
    risk = abs(entry - sl)
    best, bi = 0.0, None
    for j in range(k + 1, min(len(h), k + 1 + MAX_RUN)):
        if (side == "sell" and h[j] >= sl) or (side == "buy" and l[j] <= sl):
            break
        fav = (entry - l[j]) if side == "sell" else (h[j] - entry)
        if fav > best:
            best, bi = fav, j
    return bi, best / risk if risk else 0.0


def _outcome(h, l, k, side, sl, tp):
    for j in range(k + 1, min(len(h), k + 1 + MAX_RUN)):
        if (side == "sell" and h[j] >= sl) or (side == "buy" and l[j] <= sl):
            return None                                  # chạm SL trước → bỏ
        if (side == "sell" and l[j] <= tp) or (side == "buy" and h[j] >= tp):
            return j
    return None


def _range(o, h, l, c, k, atr):
    hi, lo = max(h[k - LOOK: k]), min(l[k - LOOK: k])
    if hi - lo < 4 * atr:
        return None
    # phải THẬT SỰ đi ngang: đường xu hướng của 40 nến gần như nằm ngang (không Sell ở đỉnh một kênh tăng)
    xs = range(k - LOOK, k)
    mx, my = sum(xs) / LOOK, sum(c[i] for i in xs) / LOOK
    slope = sum((i - mx) * (c[i] - my) for i in xs) / sum((i - mx) ** 2 for i in xs)
    if abs(slope * LOOK) > 0.35 * (hi - lo):
        return None
    for side in ("sell", "buy"):
        if side == "sell" and not (h[k] >= hi - 0.25 * atr and c[k] < hi and c[k] < o[k]):
            continue
        if side == "buy" and not (l[k] <= lo + 0.25 * atr and c[k] > lo and c[k] > o[k]):
            continue
        entry = c[k]
        sl = max(h[k], hi) + 0.4 * atr if side == "sell" else min(l[k], lo) - 0.4 * atr
        tp = entry - 2 * (sl - entry) if side == "sell" else entry + 2 * (entry - sl)
        ann = [("zone", k - LOOK, hi - 0.15 * atr, hi + 0.15 * atr, "down", "Resistance"),
               ("zone", k - LOOK, lo - 0.15 * atr, lo + 0.15 * atr, "up", "Support")]
        last = {"H": None, "L": None}
        for i, p, kind in _pivots(h, l, k - LOOK, k):      # nhãn cấu trúc HH/LH/HL/LL như mẫu
            prev = last[kind]
            if prev is not None:
                t = ("HH" if p > prev else "LH") if kind == "H" else ("HL" if p > prev else "LL")
                ann.append(("tag", i, p, t, "down" if kind == "H" else "up", kind == "H"))
            last[kind] = p
        where = "kháng cự" if side == "sell" else "hỗ trợ"
        return side, entry, sl, tp, "Vùng đi ngang", f"giá chạm {where} của vùng đi ngang", ann
    return None


def _double(o, h, l, c, k, atr):
    pv = [x for x in _pivots(h, l, k - LOOK, k - 1)]
    if len(pv) < 3:
        return None
    (i1, p1, t1), (i2, p2, t2), (i3, p3, t3) = pv[-3:]
    if t1 != t3 or i3 - i1 < 6 or abs(p1 - p3) > 0.4 * atr:
        return None
    top = t1 == "H"
    height = abs(max(p1, p3) - p2) if top else abs(p2 - min(p1, p3))
    if height < 2.5 * atr:
        return None
    side = "sell" if top else "buy"
    if side == "sell" and not (c[k] < p2 and c[k - 1] >= p2):
        return None                                      # nến đầu tiên đóng dưới neckline
    if side == "buy" and not (c[k] > p2 and c[k - 1] <= p2):
        return None
    entry = c[k]
    ext = max(p1, p3) if top else min(p1, p3)
    sl = (p2 + ext) / 2 + (0.3 * atr if top else -0.3 * atr)
    tp = p2 - height if top else p2 + height
    if abs(tp - entry) < 1.3 * abs(entry - sl):
        return None
    name = "Đỉnh đôi" if top else "Đáy đôi"
    ann = [("zone", i1 - 2, ext - 0.12 * atr, ext + 0.12 * atr, "down" if top else "up",
            "Double Top" if top else "Double Bottom"),
           ("line", i1 - 4, p2, k + 2, p2, "gold", "Neckline", True),
           ("tag", i1, p1, "1", "down" if top else "up", top), ("tag", i3, p3, "2", "down" if top else "up", top),
           ]
    return side, entry, sl, tp, name, f"{name.lower()} rồi phá neckline", ann


def _fibo(o, h, l, c, k, atr):
    pv = _pivots(h, l, k - LOOK, k - 1)
    if len(pv) < 2:
        return None
    (ia, pa, ta), (ib, pb, tb) = pv[-2:]
    leg = abs(pa - pb)
    if leg < 6 * atr or ib - ia > 30 or k - ib > 18:
        return None
    down = ta == "H"                                     # sóng giảm A→B → hồi lên → Sell
    lvl = lambda r: pb + r * (pa - pb)
    lo5, hi6, l786 = lvl(0.5), lvl(0.618), lvl(0.786)
    seg = range(ib + 1, k + 1)
    if down:
        if max(h[j] for j in seg) > l786 or not (h[k] >= lo5 and c[k] < o[k] and c[k] < hi6 + 0.2 * atr):
            return None
        side, sl = "sell", l786 + 0.3 * atr
    else:
        if min(l[j] for j in seg) < l786 or not (l[k] <= lo5 and c[k] > o[k] and c[k] > hi6 - 0.2 * atr):
            return None
        side, sl = "buy", l786 - 0.3 * atr
    entry, tp = c[k], pb
    if abs(tp - entry) < 1.5 * abs(entry - sl):
        return None
    ann = [("line", ia, pa, ib, pb, "dim", "", True),
           ("tag", ia, pa, "HH" if down else "LL", "up" if down else "down", down),
           ("tag", ib, pb, "LL" if down else "HH", "down" if down else "up", not down),
           ("zone", ib, min(lo5, hi6), max(lo5, hi6), "gold", "Fibo 0.5 - 0.618"),
           ("line", ib, l786, k + 6, l786, "dim", "0.786", True)]
    trend = "giảm" if down else "tăng"
    return side, entry, sl, tp, "Hồi Fibonacci", f"nhịp hồi về Fibo 0 phẩy 618 của xu hướng {trend}", ann


def _retest(o, h, l, c, k, atr):
    for back in range(2, 13):
        j = k - back                                     # nến phá vỡ
        hi, lo = max(h[j - LOOK: j]), min(l[j - LOOK: j])
        if hi - lo < 4 * atr:
            continue
        mid = range(j + 1, k)
        if c[j] > hi + 0.15 * atr and c[j - 1] <= hi:
            if all(c[x] > hi for x in mid) and l[k] <= hi + 0.3 * atr and c[k] > hi and c[k] > o[k]:
                side, lvl = "buy", hi
            else:
                continue
        elif c[j] < lo - 0.15 * atr and c[j - 1] >= lo:
            if all(c[x] < lo for x in mid) and h[k] >= lo - 0.3 * atr and c[k] < lo and c[k] < o[k]:
                side, lvl = "sell", lo
            else:
                continue
        else:
            continue
        entry = c[k]
        sl = min(l[k], lvl) - 0.5 * atr if side == "buy" else max(h[k], lvl) + 0.5 * atr
        tp = entry + 2 * (entry - sl) if side == "buy" else entry - 2 * (sl - entry)
        old, new = ("Kháng cự", "Hỗ trợ") if side == "buy" else ("Hỗ trợ", "Kháng cự")
        ann = [("zone", j - LOOK, lvl - 0.15 * atr, lvl + 0.15 * atr, "up" if side == "buy" else "down",
                "Resistance → Support" if side == "buy" else "Support → Resistance"),
               ("tag", j, h[j] if side == "buy" else l[j], "Breakout", "gold", side == "buy"),
               ("tag", k, l[k] if side == "buy" else h[k], "Retest", "gold", side == "sell")]
        return side, entry, sl, tp, "Phá vỡ & Retest", f"cú phá vỡ rồi ri tét {old.lower()} cũ", ann
    return None


def _abcd(o, h, l, c, k, atr):
    pv = _pivots(h, l, k - LOOK - 10, k - 1)
    if len(pv) < 3:
        return None
    (ia, pa, ta), (ib, pb, tb), (ic, pc, tc) = pv[-3:]
    ab = abs(pa - pb)
    if ab <= 0 or ab < 4 * atr or not (0.5 <= abs(pc - pb) / ab <= 0.886):
        return None
    bull = ta == "H"                                     # A đỉnh, B đáy, C đỉnh → D đáy → Buy
    d = min(l[ic + 1: k + 1]) if bull else max(h[ic + 1: k + 1])
    cd = abs(pc - d)
    if not (0.95 <= cd / ab <= 1.4):
        return None
    if bull and not (l[k] == d and c[k] > o[k] and c[k] - l[k] > 0.4 * (h[k] - l[k])):
        return None
    if not bull and not (h[k] == d and c[k] < o[k] and h[k] - c[k] > 0.4 * (h[k] - l[k])):
        return None
    side = "buy" if bull else "sell"
    entry = c[k]
    sl = d - 0.4 * atr if bull else d + 0.4 * atr
    tp = entry + 2 * (entry - sl) if bull else entry - 2 * (sl - entry)
    pts = [(ia, pa), (ib, pb), (ic, pc), (k, d)]
    up = lambda p, q: p > q
    ann = [("path", pts, "gold"),
           ("tag", ia, pa, "A", "gold", not bull), ("tag", ib, pb, "B", "gold", bull),
           ("tag", ic, pc, "C", "gold", not bull), ("tag", k, d, "D", "gold", bull),
           ("tag", (ia + ic) // 2, (pa + pc) / 2, f"{abs(pc - pb) / ab:.3f}", "gold", not bull),
           ("tag", (ib + k) // 2, (pb + d) / 2, f"{cd / ab:.3f}", "gold", bull)]
    return side, entry, sl, tp, "Mô hình ABCD", "mô hình A B C D, sóng C D dài bằng sóng A B,", ann


_CACHE: dict = {}
ALL = None          # đặt = [] để đếm toàn bộ kho lệnh (báo cáo nguồn content)
SCAN = {"range": _range, "double": _double, "fibo": _fibo, "retest": _retest, "abcd": _abcd}


def find(symbol: str, tf: str = "M5", systems: list | None = None, min_run=4, max_run=30,
         skip: set | None = None, want: float | None = None) -> Setup | None:
    """Setup có nhịp chạy DÀI NHẤT (≥ MIN_R) trong dữ liệu, theo thứ tự hệ thống ưu tiên.
    Giá chạy tới đỉnh thật của nhịp (không cắt ở TP); TP vẽ ở 80% quãng chạy để giá vọt qua hộp TP như mẫu."""
    key = (symbol, tf)
    if key not in _CACHE:                                # M5 như video mẫu (biểu đồ M1–M5 cho cú chạy dài, SL mỏng)
        _CACHE[key] = (get_m5(symbol, "60d") if tf == "M5" else get_m1(symbol) if tf == "M1"
                       else get_intraday(symbol)).candles
    cs = _CACHE[key]
    if tf == "H4":
        cs = to_h4(cs)
    o, h, l, c = [x.open for x in cs], [x.high for x in cs], [x.low for x in cs], [x.close for x in cs]
    n = len(c)
    for sysname in systems or SYSTEMS:
        fn = SCAN[sysname]
        cands = []
        for k in range(n - 3, CONTEXT + 12, -1):
            atr = _atr(h, l, c, k)
            if atr <= 0:                                 # đoạn giá đứng yên (hay gặp ở M1) → bỏ
                continue
            r = fn(o, h, l, c, k, atr)
            if not r:
                continue
            side, entry, sl, tp, name, reason, ann = r
            # SL sát: ngay ngoài cực trị 3 nến gần nhất (kiểu đặt lệnh của mẫu) – vẫn kiểm tra THẬT là không bị quét
            tight = (min(l[k - 2: k + 1]) - 0.15 * atr) if side == "buy" else (max(h[k - 2: k + 1]) + 0.15 * atr)
            best = None
            for sl_ in (tight, sl):
                if (side == "buy" and sl_ >= entry) or (side == "sell" and sl_ <= entry):
                    continue
                hit, rr = _run(h, l, k, side, entry, sl_)
                # bỏ dữ liệu lỗi: nến mở cửa nhảy khoảng trống bất thường (forex M5 giữa phiên gần như không có)
                if hit is not None and any(abs(o[j] - c[j - 1]) > 1.2 * atr for j in range(k + 1, hit + 1)):
                    continue
                if hit is not None and rr >= MIN_R and min_run <= hit - k <= max_run and (best is None or rr > best[0]):
                    best = (rr, k, hit, (side, entry, sl_, tp, name, reason, ann))
            if want is not None and abs(entry - want) > 1e-6:   # dựng lại đúng 1 lệnh cũ (theo giá vào)
                continue
            if best and f"{symbol}|{entry:.5f}" not in (skip or set()):   # lệnh đã đăng → bỏ (không lặp)
                cands.append(best)
        if ALL is not None:
            ALL.extend((sysname, cs[x[1]].date, x[0], x[2] - x[1]) for x in cands)
            continue
        if not cands:
            continue
        # ưu tiên lệnh ăn 6–15R (dài như mẫu nhưng vẫn tin được); quá 15R nhìn thiếu thật
        # như mẫu: cú chạy BÙNG NỔ trong vài nến (≤ 8 nến) – nếu không có mới lấy nhịp dài hơn
        fast = [x for x in cands if x[2] - x[1] <= 8]
        rr, k, hit, r = max(fast or cands, key=lambda x: x[0] if x[0] <= 15 else 15 - (x[0] - 15))
        side, entry, sl, tp, name, reason, ann = r
        far = (entry - l[hit]) if side == "sell" else (h[hit] - entry)
        tp = entry - 0.8 * far if side == "sell" else entry + 0.8 * far
        if True:
            a, b = k - CONTEXT, hit + 1
            sh = lambda i: i - a

            def move(x):
                if x[0] == "zone":
                    return (x[0], max(0, sh(x[1]))) + x[2:]
                if x[0] == "line":
                    return (x[0], max(0, sh(x[1])), x[2], sh(x[3])) + x[4:]
                if x[0] == "tag":
                    return (x[0], sh(x[1])) + x[2:]
                return (x[0], [(sh(i), p) for i, p in x[1]], x[2])
            win = slice(a, b)
            return Setup(symbol, tf, DIGITS.get(symbol, 5), o[win], h[win], l[win], c[win], k - a, hit - a, side,
                         entry, sl, tp, sysname, name, reason, [move(x) for x in ann])
    return None


if __name__ == "__main__":
    import sys
    for sym in sys.argv[1:] or ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]:
        for s_ in SYSTEMS:
            r_ = find(sym, systems=[s_])
            print(sym, s_, None if r_ is None else (r_.side, r_.hit - r_.k, len(r_.c)))
