"""Việc 'reel' cho Page thương hiệu (CWG…): AI viết kịch bản kiến thức → dựng video thẻ tối + biểu đồ minh họa
có logo CWG → caption có chữ ký thương hiệu."""
import json
import os
import random
from pathlib import Path

from src.config import CONFIG

from src.reels import render as old
from src.reels.edu import build, script


def folder(out_dir: Path) -> Path:
    return out_dir / "reel"


def generate(out_dir: Path) -> bool:
    from src.content import cwg_daily
    spec = script.write()
    music = pick_music()
    res = build.make(spec, folder(out_dir), music=music)
    body = (spec.get("title", "").strip() + "\n\n" + spec.get("caption", "").strip()).strip()
    caption = cwg_daily.caption(body, [t.lstrip("#") for t in spec.get("hashtags") or []])
    (folder(out_dir) / "caption.txt").write_text(caption, encoding="utf-8")
    (folder(out_dir) / "meta.json").write_text(json.dumps(
        {"topic": spec["topic"], "title": spec.get("title"), "duration": res["duration"],
         "music": music.name if music else None}, ensure_ascii=False), encoding="utf-8")
    return True


def pick_music() -> Path | None:
    """Kho nhạc riêng của Page (reels.music_dir, vd. assets/music/cwg – nhạc Mixkit trap/hip-hop bass nặng)."""
    sub = (CONFIG.get("reels") or {}).get("music_dir")
    if not sub or os.environ.get("REEL_MUSIC"):
        return old.pick_music()
    tracks = sorted((old.MUSIC / sub).glob("*.mp3"))
    return random.choice(tracks) if tracks else old.pick_music()


def files(out_dir: Path) -> tuple[Path, Path, Path]:
    f = folder(out_dir)
    return f / "caption.txt", f / "reel.mp4", f / "thumb.jpg"


def meta(out_dir: Path) -> dict:
    return json.loads((folder(out_dir) / "meta.json").read_text(encoding="utf-8"))


def mark_done(meta: dict):
    script.mark_done(meta["topic"], meta.get("title") or "")
