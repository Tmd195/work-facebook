"""Biểu đồ nến MINH HỌA (không phải giá thực) dựng từ các "đoạn giá" do kịch bản mô tả.

AI chỉ viết hình dạng: [{"id": "acc", "kind": "range", "bars": 18}, {"id": "man", "kind": "sweep_low"},
{"id": "dist", "kind": "up", "bars": 14, "fvg": true}] → hệ thống sinh nến đúng hình mẫu kiến thức
(quét thanh khoản, FVG, order block…) và tính sẵn toạ độ cho các khung chú thích.

Đơn vị giá: quanh 100, 1 "u" ≈ chiều cao 1 nến thường ×3 – trục giá hiện các số tròn như ảnh mẫu.
"""
import math
import random
from dataclasses import dataclass, field

KINDS = ("range", "up", "down", "sweep_low", "sweep_high", "pullback_down", "pullback_up", "spike_up", "spike_down")


@dataclass
class Bar:
    o: float
    h: float
    l: float
    c: float
    v: float


@dataclass
class Seg:
    id: str
    kind: str
    i0: int          # nến đầu (gồm)
    i1: int          # nến cuối (gồm)
    hi: float = 0.0
    lo: float = 0.0
    hi_i: int = 0
    lo_i: int = 0
    spec: dict = field(default_factory=dict)


class Chart:
    def __init__(self, segments: list[dict], seed: int = 1):
        self.rng = random.Random(seed)
        self.bars: list[Bar] = []
        self.segs: dict[str, Seg] = {}
        self.order: list[str] = []
        price = 110.0
        for n, sp in enumerate(segments):
            kind = sp.get("kind", "range")
            if kind not in KINDS:
                kind = "range"
            sid = str(sp.get("id") or f"s{n}")
            i0 = len(self.bars)
            getattr(self, "_" + kind)(price, sp)
            seg = Seg(sid, kind, i0, len(self.bars) - 1, spec=sp)
            self._measure(seg)
            self.segs[sid] = seg
            self.order.append(sid)
            price = self.bars[-1].c
        for sid in self.order:
            if self.segs[sid].spec.get("fvg"):
                self._force_fvg(self.segs[sid])
                self._measure(self.segs[sid])

    # ------------------------------------------------------------------ sinh nến
    def _bar(self, o: float, c: float, wick: float = 0.25, vol: float = 1.0):
        r = self.rng
        h = max(o, c) + abs(r.gauss(0, wick)) + 0.03
        l = min(o, c) - abs(r.gauss(0, wick)) - 0.03
        self.bars.append(Bar(o, h, l, c, max(0.15, vol * r.uniform(0.6, 1.3))))

    def _walk(self, p0: float, p1: float, n: int, noise: float, wick: float, vol: float, pull: float = 0.0):
        """Đi từ p0 tới p1 trong n nến, có nhiễu và nhịp hồi ngắn (pull = xác suất nến ngược chiều)."""
        r = self.rng
        prev = p0
        step = (p1 - p0) / max(1, n)
        for k in range(n):
            target = p0 + step * (k + 1)
            c = target + r.gauss(0, noise)
            if pull and k not in (0, n - 1) and r.random() < pull:
                c = prev - step * r.uniform(0.3, 0.8)
            if k == n - 1:
                c = p1
            self._bar(prev, c, wick, vol * (1 + abs(c - prev)))
            prev = c

    def _range(self, p: float, sp: dict):
        n = int(sp.get("bars", 16))
        h = float(sp.get("height", 3.2))
        mid = p
        lo, hi = mid - h / 2, mid + h / 2
        r = self.rng
        prev = p
        phase = r.uniform(0, 6.28)
        for k in range(n):
            c = mid + math.sin(phase + k * r.uniform(0.45, 0.8)) * h * 0.3 + r.gauss(0, h * 0.08)
            c = min(hi - 0.1, max(lo + 0.1, c))
            o = prev
            self._bar(o, c, 0.18, 0.8)
            b = self.bars[-1]
            b.h, b.l = min(b.h, hi), max(b.l, lo)          # râu không vượt biên vùng tích luỹ
            prev = c
        # chạm đủ 2 biên để vùng rõ ràng
        top = max(range(n), key=lambda j: self.bars[-n + j].h)
        bot = min(range(n), key=lambda j: self.bars[-n + j].l)
        self.bars[-n + top].h = hi
        self.bars[-n + bot].l = lo

    def _trend(self, p: float, sp: dict, sign: int, strong: bool = False):
        n = int(sp.get("bars", 12 if not strong else 5))
        move = float(sp.get("move", 7 if not strong else 5)) * sign
        self._walk(p, p + move, n, 0.15 if strong else 0.35, 0.12 if strong else 0.25,
                   2.2 if strong else 1.2, pull=0.0 if strong else 0.22)

    def _up(self, p, sp):
        self._trend(p, sp, 1)

    def _down(self, p, sp):
        self._trend(p, sp, -1)

    def _spike_up(self, p, sp):
        self._trend(p, sp, 1, True)

    def _spike_down(self, p, sp):
        self._trend(p, sp, -1, True)

    def _ref(self, sp: dict) -> Seg | None:
        ref = sp.get("ref")
        if ref and ref in self.segs:
            return self.segs[ref]
        return self.segs[self.order[-1]] if self.order else None

    def _sweep(self, p: float, sp: dict, sign: int):
        """Quét thanh khoản: đẩy qua đáy/đỉnh của đoạn tham chiếu rồi rút râu quay lại."""
        ref = self._ref(sp)
        level = (ref.lo if sign < 0 else ref.hi) if ref else p + sign * 2
        depth = float(sp.get("depth", 1.1))
        n = int(sp.get("bars", 4))
        lead = max(0, n - 2)
        if lead:
            near = level - sign * 0.5
            self._walk(p, near, lead, 0.1, 0.15, 1.3)
            p = near
        # nến quét: thân phá qua, râu dài vượt mức
        c1 = level + sign * depth * 0.55
        self._bar(p, c1, 0.05, 2.6)
        b = self.bars[-1]
        if sign < 0:
            b.l = level - depth
        else:
            b.h = level + depth
        # nến rút: đóng ngược vào trong vùng
        c2 = level - sign * 0.8
        self._bar(c1, c2, 0.05, 2.8)
        b = self.bars[-1]
        if sign < 0:
            b.l = min(b.l, c1 - 0.2)
        else:
            b.h = max(b.h, c1 + 0.2)

    def _sweep_low(self, p, sp):
        self._sweep(p, sp, -1)

    def _sweep_high(self, p, sp):
        self._sweep(p, sp, 1)

    def _pullback(self, p: float, sp: dict, sign: int):
        prev = self._ref(sp)
        size = (prev.hi - prev.lo) if prev else 4
        frac = float(sp.get("depth", 0.5))
        n = int(sp.get("bars", 5))
        self._walk(p, p + sign * size * frac, n, 0.15, 0.2, 0.9)

    def _pullback_down(self, p, sp):
        self._pullback(p, sp, -1)

    def _pullback_up(self, p, sp):
        self._pullback(p, sp, 1)

    def _force_fvg(self, seg: Seg):
        """Đảm bảo đoạn có 1 FVG rõ: nến giữa thân lớn, râu 2 nến kẹp không chạm nhau."""
        if seg.i1 - seg.i0 < 2:
            return
        up = self.bars[seg.i1].c >= self.bars[seg.i0].o
        k = seg.i0 + max(1, min(seg.i1 - seg.i0 - 1, (seg.i1 - seg.i0) // 3))
        a, m, b = self.bars[k - 1], self.bars[k], self.bars[k + 1]
        if up:
            gap_lo, gap_hi = a.h, b.l
            if gap_hi - gap_lo < 0.6:
                mid = (m.o + m.c) / 2
                a.h = min(a.h, mid - 0.45)
                a.c, a.o = min(a.c, a.h), min(a.o, a.h)
                b.l = max(b.l, mid + 0.45)
                b.c, b.o = max(b.c, b.l), max(b.o, b.l)
                m.o, m.c = min(m.o, a.c), max(m.c, b.o)
                m.l, m.h = min(m.l, m.o), max(m.h, m.c)
        else:
            gap_hi, gap_lo = a.l, b.h
            if gap_hi - gap_lo < 0.6:
                mid = (m.o + m.c) / 2
                a.l = max(a.l, mid + 0.45)
                a.c, a.o = max(a.c, a.l), max(a.o, a.l)
                b.h = min(b.h, mid - 0.45)
                b.c, b.o = min(b.c, b.h), min(b.o, b.h)
                m.o, m.c = max(m.o, a.c), min(m.c, b.o)
                m.l, m.h = min(m.l, m.c), max(m.h, m.o)
        m.v = max(m.v, 3.0)
        seg.spec["_fvg_i"] = k

    def _measure(self, seg: Seg):
        bs = self.bars[seg.i0: seg.i1 + 1]
        seg.hi = max(b.h for b in bs)
        seg.lo = min(b.l for b in bs)
        seg.hi_i = seg.i0 + max(range(len(bs)), key=lambda j: bs[j].h)
        seg.lo_i = seg.i0 + min(range(len(bs)), key=lambda j: bs[j].l)

    # ------------------------------------------------------------------ vùng kiến thức
    def seg(self, sid: str) -> Seg | None:
        return self.segs.get(sid)

    def fvg(self, sid: str) -> tuple[int, float, float] | None:
        """(chỉ số nến giữa, giá dưới, giá trên) của FVG đầu tiên trong đoạn."""
        s = self.segs.get(sid)
        if not s:
            return None
        cand = [s.spec["_fvg_i"]] if "_fvg_i" in s.spec else []
        cand += list(range(max(1, s.i0), min(len(self.bars) - 1, s.i1 + 1)))
        for k in cand:
            if not 1 <= k < len(self.bars) - 1:
                continue
            a, b = self.bars[k - 1], self.bars[k + 1]
            if b.l - a.h > 0.25:
                return k, a.h, b.l
            if a.l - b.h > 0.25:
                return k, b.h, a.l
        return None

    def order_block(self, sid: str) -> tuple[int, float, float] | None:
        """Nến ngược chiều cuối cùng ngay trước đoạn đẩy mạnh (OB). Trả (chỉ số, giá dưới, giá trên)."""
        s = self.segs.get(sid)
        if not s:
            return None
        up = self.bars[s.i1].c >= self.bars[s.i0].o
        for k in range(s.i0 - 1, max(-1, s.i0 - 8), -1):
            if not 0 <= k < len(self.bars):
                continue
            b = self.bars[k]
            if (up and b.c < b.o) or (not up and b.c > b.o):
                return k, b.l, b.h
        k = max(0, s.i0 - 1)
        return k, self.bars[k].l, self.bars[k].h

    def span(self, ids: list[str]) -> tuple[int, int]:
        ss = [self.segs[i] for i in ids if i in self.segs]
        if not ss:
            return 0, len(self.bars) - 1
        return min(s.i0 for s in ss), max(s.i1 for s in ss)

    def end_of(self, sid: str | None) -> int:
        if sid and sid in self.segs:
            return self.segs[sid].i1
        return len(self.bars) - 1
