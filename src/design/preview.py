"""Xem trước phong cách thiết kế: vẽ cùng 1 bộ ảnh mẫu cho từng bộ màu × giao diện biểu đồ.

    python -m src.design.preview                     # tất cả bộ màu, biểu đồ sáng
    python -m src.design.preview --theme dark        # tất cả bộ màu, biểu đồ tối
    python -m src.design.preview --palette navy-vang --theme dark

Kết quả: output/design_preview/<bộ màu>_<giao diện>.png (mỗi tấm gồm 3 ảnh mẫu) + tong_quan.png
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from src.config import OUTPUT, ROOT

OUT = OUTPUT / "design_preview"
SAMPLES = ROOT / "samples"


def render_one(palette: str, theme: str) -> Path:
    """Chạy trong tiến trình riêng (màu được nạp lúc import)."""
    from datetime import datetime

    from src.chart_tools import build
    from src.config import TZ
    from src.design import carousel, strategy_album
    from src.design.styles import STYLES

    d = OUT / f"_{palette}_{theme}"
    d.mkdir(parents=True, exist_ok=True)
    # 1. Ảnh bìa bài chiến lược
    st = json.loads((SAMPLES / "strategy_sample.json").read_text(encoding="utf-8"))
    strategy_album.cover(d / "1.png", "Phiên Mỹ", st["data"], st["result"], datetime.now(TZ))
    # 2. Ảnh kiến thức có biểu đồ TradingView
    kn = json.loads((SAMPLES / "series_pa_01.json").read_text(encoding="utf-8"))
    sl = kn["slides"][2]
    ch, facts = build(sl["chart"])
    carousel.render_slide(d / "2.png", "Price Action nhập môn", 1, 15, 3, 4, sl["heading"], sl["body"],
                          ch.render(640, 420, scale=3), facts[0] if facts else "")
    # 3. Bản tin sáng
    mo = json.loads((SAMPLES / "morning_sample.json").read_text(encoding="utf-8"))
    STYLES["block"](d / "3.png", mo["context"]["date"], mo["result"]["focus"], mo["markets"], mo["context"]["calendar"])

    from src.design.common import sans
    from src.design.palette import PRESETS
    ims = [Image.open(d / f"{k}.png").convert("RGB") for k in (1, 2, 3)]
    sheet = Image.new("RGB", (1080 * 3 + 80, 1350 + 140), (255, 255, 255))
    dr = ImageDraw.Draw(sheet)
    dr.text((40, 40), f"{PRESETS[palette]['name']}  ·  biểu đồ {'tối' if theme == 'dark' else 'sáng'}  "
                      f"(palette: {palette}, chart_theme: {theme})", font=sans("Bold", 48), fill=(20, 20, 20))
    for i, im in enumerate(ims):
        sheet.paste(im, (20 + i * 1100, 120))
    path = OUT / f"{palette}_{theme}.png"
    sheet.resize((sheet.width // 2, sheet.height // 2)).save(path)
    return path


def main():
    from src.design.palette import PRESETS
    ap = argparse.ArgumentParser()
    ap.add_argument("--palette", choices=list(PRESETS))
    ap.add_argument("--theme", choices=["light", "dark"], default="light")
    ap.add_argument("--_one", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a._one:
        print(render_one(a.palette, a.theme))
        return
    OUT.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in ([a.palette] if a.palette else list(PRESETS)):
        env = {**os.environ, "DESIGN_PALETTE": name, "DESIGN_CHART_THEME": a.theme, "PYTHONIOENCODING": "utf-8"}
        r = subprocess.run([sys.executable, "-m", "src.design.preview", "--_one", "--palette", name, "--theme", a.theme],
                           env=env, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            print(f"✗ {name}: {r.stderr[-400:]}")
            continue
        paths.append(Path(r.stdout.strip().splitlines()[-1]))
        print(f"✓ {paths[-1]}")
    if len(paths) > 1:
        ims = [Image.open(p) for p in paths]
        w = max(i.width for i in ims)
        sheet = Image.new("RGB", (w, sum(i.height for i in ims)), "white")
        y = 0
        for im in ims:
            sheet.paste(im, (0, y))
            y += im.height
        sheet.save(OUT / f"tong_quan_{a.theme}.png")
        print(f"✓ Tổng quan: {OUT / f'tong_quan_{a.theme}.png'}")


if __name__ == "__main__":
    main()
