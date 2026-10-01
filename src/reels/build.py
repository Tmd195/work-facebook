"""Từ kịch bản → giọng đọc → thumbnail + video Reels hoàn chỉnh.

    python -m src.reels.build                 # viết kịch bản mới + dựng video vào output/reels/
    python -m src.reels.build --script x.json # dựng lại từ kịch bản có sẵn
    python -m src.reels.build --pillar sl-tp
"""
import argparse
import json
import random
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from src.config import ROOT, TZ
from src.design.common import sans, wrap
from src.design.palette import ACCENT, DOWN, PRIMARY
from src.reels import marks, render, script, voice
from src.reels.phonetic import spoken

OUT = ROOT / "output" / "reels"


def _photo_full(path: Path | None, dark: float = 0.3) -> Image.Image:
    """Ảnh Thái rõ nét phủ kín khung + gradient tối trên/dưới để chữ dễ đọc."""
    if path is None:
        return render.brand_bg(7)
    img = render.cover(Image.open(path), (render.W, render.H), render.center_x(path)).convert("RGBA")
    shade = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(shade)
    for y in range(render.H):
        t = y / render.H
        a = dark * 255 + max(0, (t - 0.42) / 0.58) * 200 + max(0, (0.22 - t) / 0.22) * 120
        d.line([(0, y), (render.W, y)], fill=(5, 8, 12, int(min(235, a))))
    img.alpha_composite(shade)
    return img


def thumbnail(s: dict, photo: Path | None, path: Path) -> Path:
    img = _photo_full(photo, 0.12)
    d = ImageDraw.Draw(img)
    W = render.W
    tag = render.brand_tag()
    img.alpha_composite(tag, ((W - tag.width) // 2, 96))

    f1, f2 = sans("ExtraBold", 124), sans("ExtraBold", 124)
    l1 = wrap(d, s["thumb"]["line1"].upper(), f1, W - 120, 2)
    l2 = wrap(d, s["thumb"]["line2"].upper(), f2, W - 160, 2)
    y = 1700 - 150 * (len(l1) + len(l2)) - 90
    # nhãn chủ đề
    tf = sans("Bold", 40)
    tw = d.textlength(s["thumb"]["tag"].upper(), font=tf) + 64
    d.rounded_rectangle([(W - tw) / 2, y, (W + tw) / 2, y + 72], radius=36, fill=DOWN)
    d.text((W / 2, y + 37), s["thumb"]["tag"].upper(), font=tf, fill=(255, 255, 255), anchor="mm")
    y += 108
    for ln in l1:
        d.text((W / 2 + 5, y + 75), ln, font=f1, fill=(0, 0, 0, 160), anchor="mm")
        d.text((W / 2, y + 70), ln, font=f1, fill=(255, 255, 255), anchor="mm")
        y += 150
    for ln in l2:
        w = d.textlength(ln, font=f2) + 60
        d.rounded_rectangle([(W - w) / 2, y + 2, (W + w) / 2, y + 142], radius=22, fill=ACCENT)
        d.text((W / 2, y + 72), ln, font=f2, fill=PRIMARY, anchor="mm")
        y += 156
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, "JPEG", quality=92)
    return path


def _diagram(dg: dict | None, w: int, h: int) -> dict | None:
    """Dựng sơ đồ minh họa + toạ độ các hiệu ứng. Lỗi thì bỏ sơ đồ (cảnh vẫn chạy với chữ)."""
    if not dg or not dg.get("path"):
        return None
    try:
        img, ms = marks.build(dg, w, h, 3)
        return {"img": img, "marks": ms}
    except Exception as exc:
        print(f"  ! sơ đồ lỗi ({exc}), bỏ qua", flush=True)
        return None


def _visual(sl: dict):
    kind = sl.get("type", "diagram")
    if kind == "compare" and sl.get("compare"):
        out = {}
        for side in ("left", "right"):
            c = sl["compare"].get(side) or {}
            v = _diagram(c.get("diagram"), 300, 360) or {}
            out[side] = {"name": c.get("name", ""), "points": c.get("points") or [], **v}
        return out
    return _diagram(sl.get("diagram"), 560, 470 if kind == "diagram" else 320)


def make(s: dict, folder: Path) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "script.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    pics = render.photos()
    random.shuffle(pics)
    thumb_photo = pics[0] if pics else None
    hook_photo = pics[1 % len(pics)] if pics else None
    bg_photo = pics[2 % len(pics)] if pics else None

    texts = [spoken(x) for x in [s["hook"]["voice"]] + [sl["voice"] for sl in s["slides"]] + [s["cta"]]]
    wavs = voice.synth(texts, folder / "voice")
    durs = [voice.duration(w) for w in wavs]

    base_bg = render.photo_bg(bg_photo) if bg_photo else render.brand_bg()
    scenes = [render.hook_scene(s["hook"]["screen"], durs[0] + 0.6, wavs[0], _photo_full(hook_photo))]
    for i, sl in enumerate(s["slides"]):
        scenes.append(render.content_scene(sl, i + 1, len(s["slides"]), max(4.5, durs[i + 1] + 0.6),
                                           wavs[i + 1], _visual(sl)))
    scenes.append(render.cta_scene(s["cta"], durs[-1] + 2.8, wavs[-1], _photo_full(bg_photo, 0.45)))

    music = render.pick_music()
    video = render.encode(scenes, base_bg, folder / "reel.mp4", music)
    thumb = thumbnail(s, thumb_photo, folder / "thumbnail.jpg")
    total = sum(x.duration for x in scenes)
    print(f"  ✓ video {total:.1f}s → {video}", flush=True)
    return {"video": video, "thumbnail": thumb, "duration": total, "music": music.name if music else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script")
    ap.add_argument("--pillar", choices=list(script.PILLARS))
    a = ap.parse_args()
    folder = OUT / datetime.now(TZ).strftime("%Y%m%d-%H%M")
    if a.script:                                   # dựng lại trong cùng thư mục → dùng lại giọng đã tạo
        s = json.loads(Path(a.script).read_text(encoding="utf-8"))
        folder = Path(a.script).parent
    else:
        s = script.write(script.next_brief(a.pillar))
    print(make(s, folder))


if __name__ == "__main__":
    main()
