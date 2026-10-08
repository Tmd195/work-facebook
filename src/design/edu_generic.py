"""Khuôn album kiến thức DÙNG CHUNG (form "Sổ tay Trader") – vẽ từ bản mô tả JSON do AI viết cho từng chủ đề.

spec = {
  "cover": {"kicker", "title_lines": [2 dòng ngắn IN HOA], "hook_1", "hook_2"},
  "slides": [ {"title", "text": [≤3 dòng], "diagram": DIAG, "note"} ×5 ],
  "checklist": [≤6 mục], "verdict": "câu chốt dưới checklist"
}
DIAG = {"kind": "candles" | "line",
        "candles": [[o,h,l,c] … ≤18]  (giá thang 0–100)   |   "points": [[x,y] … ≤14] (x 0–100, y 0–100),
        "marks": [ {"t": "box"|"hline"|"label"|"circle"|"arrow"|"highlight", …toạ độ cùng thang…, "text", "color"} ]}
  - candles: toạ độ x = số thứ tự nến (0…n-1); line: x 0–100.  color: red | blue | green | ink
"""
import math
import textwrap
from pathlib import Path

from PIL import ImageDraw

from src.design.edu_styles import H, NB_INK, NB_RED, W, highlight, jitter_line, lora, nb_base

COL = {"red": NB_RED, "blue": (40, 90, 200), "green": (30, 130, 70), "ink": NB_INK}
AREA = (190, 520, W - 120, 1050)


class Space:
    def __init__(self, diag, box=AREA):
        self.box = box
        self.kind = diag.get("kind", "line")
        if self.kind == "candles":
            cs = diag.get("candles") or []
            self.n = max(1, len(cs))
            vals = [v for c in cs for v in c[1:3]]
        else:
            pts = diag.get("points") or []
            self.n = None
            vals = [p[1] for p in pts]
        for m in diag.get("marks") or []:
            for k in ("y", "y0", "y1"):
                if isinstance(m.get(k), (int, float)):
                    vals.append(m[k])
        lo, hi = (min(vals), max(vals)) if vals else (0, 100)
        pad = (hi - lo) * 0.08 or 5
        self.lo, self.hi = lo - pad, hi + pad

    def X(self, x):
        x0, _, x1, _ = self.box
        if self.kind == "candles":
            return x0 + (x + 0.5) / self.n * (x1 - x0)
        return x0 + x / 100 * (x1 - x0)

    def Y(self, y):
        _, y0, _, y1 = self.box
        return y1 - (y - self.lo) / ((self.hi - self.lo) or 1) * (y1 - y0)

    @property
    def bw(self):
        return (self.box[2] - self.box[0]) / (self.n or 10) * 0.55


def draw_diag(img, diag, box=AREA, seed=0):
    d = ImageDraw.Draw(img)
    S = Space(diag, box)
    # highlight trước (nằm dưới nét vẽ)
    for m in diag.get("marks") or []:
        if m.get("t") == "highlight":
            img = highlight(img, (S.X(m["x0"]), S.Y(max(m["y0"], m["y1"])), S.X(m["x1"]), S.Y(min(m["y0"], m["y1"]))))
    d = ImageDraw.Draw(img)
    if S.kind == "candles":
        for i, c in enumerate(diag.get("candles") or []):
            o, h, l, cl = c
            x = S.X(i)
            jitter_line(d, [(x, S.Y(h)), (x, S.Y(l))], NB_INK, 3, 1.0, seed + i)
            ya, yb = sorted((S.Y(o), S.Y(cl)))
            r = [x - S.bw / 2, ya, x + S.bw / 2, max(yb, ya + 3)]
            if cl < o:
                d.rectangle(r, fill=NB_INK)
            else:
                d.rectangle(r, fill=(250, 246, 234))
            jitter_line(d, [(r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3]), (r[0], r[1])], NB_INK, 3, 1.1, seed + 50 + i)
    else:
        pts = [(S.X(x), S.Y(y)) for x, y in diag.get("points") or []]
        if len(pts) > 1:
            jitter_line(d, pts, NB_INK, 5, 1.6, seed + 3)
    f = lora(32, 700, True)
    for k, m in enumerate(diag.get("marks") or []):
        t, col = m.get("t"), COL.get(m.get("color", "red"), NB_RED)
        txt = (m.get("text") or "").strip()
        try:
            if t == "box":
                x0, x1, y0, y1 = S.X(m["x0"]), S.X(m["x1"]), S.Y(m["y0"]), S.Y(m["y1"])
                jitter_line(d, [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], col, 4, 1.8, seed + 100 + k)
                if txt:
                    d.text((x0, max(y0, y1) + 12), txt, font=f, fill=col)
            elif t == "hline":
                y = S.Y(m["y"])
                jitter_line(d, [(S.X(m.get("x0", 0)), y), (S.X(m.get("x1", 100 if S.kind == "line" else S.n - 1)), y)],
                            col, 4, 1.2, seed + 120 + k)
                if txt:                                    # nhãn cuối đường; sát mép phải → đặt phía trên, căn phải
                    xe = S.X(m.get("x1", 100 if S.kind == "line" else S.n - 1))
                    if xe + 10 + d.textlength(txt, font=f) > W - 40:
                        d.text((min(xe, W - 50), y - 8), txt, font=f, fill=col, anchor="rb")
                    else:
                        d.text((xe + 10, y), txt, font=f, fill=col, anchor="lm")
            elif t == "label":
                d.text((S.X(m["x"]), S.Y(m["y"])), txt, font=f, fill=col, anchor="mm")
            elif t == "circle":
                cx, cy = S.X(m["x"]), S.Y(m["y"])
                jitter_line(d, [(cx + 46 * math.cos(a / 18 * 2 * math.pi), cy + 38 * math.sin(a / 18 * 2 * math.pi))
                                for a in range(20)], col, 4, 2.0, seed + 140 + k)
                if txt:
                    d.text((cx, cy + 62), txt, font=f, fill=col, anchor="mm")
            elif t == "arrow":
                xa, ya, xb, yb = S.X(m["x0"]), S.Y(m["y0"]), S.X(m["x1"]), S.Y(m["y1"])
                jitter_line(d, [(xa, ya), (xb, yb)], col, 4, 1.2, seed + 160 + k)
                ang = math.atan2(yb - ya, xb - xa)
                for da in (2.6, -2.6):
                    d.line([(xb, yb), (xb + 26 * math.cos(ang + da), yb + 26 * math.sin(ang + da))], fill=col, width=4)
                if txt:
                    d.text(((xa + xb) / 2, (ya + yb) / 2 - 30), txt, font=f, fill=col, anchor="mm")
        except (KeyError, TypeError, ValueError):
            continue                                       # mark thiếu toạ độ → bỏ qua, không làm hỏng ảnh
    return img


def _wrap(text, width):
    out = []
    for line in text if isinstance(text, list) else [text]:
        out += textwrap.wrap(str(line), width) or [""]
    return out


def cover(spec, number):
    c = spec["cover"]
    img, d = nb_base(1)
    d.text((150, 110), c.get("kicker") or f"Sổ tay hệ thống #{number:02d}", font=lora(36, 500, True), fill=(110, 110, 120))
    lines = c["title_lines"][:2]
    size = 170
    while any(d.textlength(t, font=lora(size, 700)) > W - 220 for t in lines) and size > 90:
        size -= 6
    y = 160
    for j, t in enumerate(lines):
        if j == len(lines) - 1:
            img = highlight(img, (150, y + size * 0.62, 150 + ImageDraw.Draw(img).textlength(t, font=lora(size, 700)) + 10,
                                  y + size * 0.95))
            d = ImageDraw.Draw(img)
        d.text((145, y), t, font=lora(size, 700), fill=NB_INK)
        y += int(size * 1.0)
    y += 60                                               # chừa khoảng dưới tiêu đề – câu phụ không đè chữ to
    d.text((150, y), c.get("hook_1", ""), font=lora(40, 500, True), fill=NB_INK)
    d.text((150, y + 56), c.get("hook_2", ""), font=lora(40, 700), fill=NB_RED)
    if spec["slides"]:
        img = draw_diag(img, spec["slides"][0]["diagram"], (190, max(720, y + 150), W - 120, 1160), seed=7)
    return img


def slide(sp, page, idx):
    img, d = nb_base(page)
    t = f"{idx}. {sp['title']}"
    size = 64
    while d.textlength(t, font=lora(size, 700)) > W - 230 and size > 40:
        size -= 3
    d.text((150, 100), t, font=lora(size, 700), fill=NB_INK)
    jitter_line(d, [(150, 190), (150 + d.textlength(t, font=lora(size, 700)), 190)], NB_RED, 4, 1.5, page)
    lines = _wrap(sp.get("text") or [], 44)[:5]
    for j, ln in enumerate(lines):
        d.text((150, 222 + j * 54), ln, font=lora(36, 600, True), fill=NB_INK)
    top = 222 + len(lines) * 54 + 40
    img = draw_diag(img, sp["diagram"], (190, max(top, 470), W - 140, 1060), seed=page * 13)
    d = ImageDraw.Draw(img)
    for j, ln in enumerate(_wrap(sp.get("note") or "", 46)[:2]):
        d.text((150, 1090 + j * 50), ln, font=lora(34, 700, True), fill=NB_RED)
    return img


def checklist(spec, page, idx):
    img, d = nb_base(page)
    d.text((150, 100), f"{idx}. Checklist trước khi vào lệnh", font=lora(60, 700), fill=NB_INK)
    jitter_line(d, [(150, 190), (900, 190)], NB_RED, 4, 1.5, page)
    items = spec["checklist"][:6]
    for j, t in enumerate(items):
        y = 260 + j * 135
        jitter_line(d, [(160, y), (220, y), (220, y + 60), (160, y + 60), (160, y)], NB_INK, 4, 1.4, 60 + j)
        jitter_line(d, [(170, y + 30), (188, y + 52), (238, y - 8)], NB_RED, 6, 1.0, 70 + j)
        for k, ln in enumerate(_wrap(t, 36)[:2]):
            d.text((260, y + 30 + (k - 0.5 * (len(_wrap(t, 36)[:2]) - 1)) * 44), ln, font=lora(40, 600, True), fill=NB_INK,
                   anchor="lm")
    verdict = spec.get("verdict") or "Thiếu 1 ô => KHÔNG vào lệnh."
    img = highlight(img, (150, 1110, 150 + ImageDraw.Draw(img).textlength(verdict, font=lora(44, 700)) + 10, 1160))
    d = ImageDraw.Draw(img)
    d.text((150, 1090), verdict, font=lora(44, 700), fill=NB_RED)
    return img


def build(spec, folder: Path, number: int) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    imgs = [cover(spec, number)]
    for k, sp in enumerate(spec["slides"][:5], 1):
        imgs.append(slide(sp, k + 1, k))
    imgs.append(checklist(spec, len(imgs) + 1, len(imgs)))
    out = []
    for k, im in enumerate(imgs, 1):
        p = folder / f"{k:02d}.png"
        im.save(p)
        out.append(p)
    return out
