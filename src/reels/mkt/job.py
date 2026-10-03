"""Việc 'reel' cho Page Global: Reels thị trường theo khuôn mẫu anh chọn (tiêu đề + cờ → biểu đồ giá thật
+ chỉ báo → câu hỏi → logo CWG), giọng nhân bản tiếng Anh."""
import json
from pathlib import Path

from src.reels import render as old
from src.reels.mkt import build


def folder(out_dir: Path) -> Path:
    return out_dir / "reel"


def generate(out_dir: Path) -> bool:
    from src.content import cwg_daily
    spec = build.write(build.next_symbol())
    music = old.pick_music()
    res = build.make(spec, folder(out_dir), music=music)
    caption = cwg_daily.caption(spec["caption"], [t.lstrip("#") for t in spec.get("hashtags") or []])
    (folder(out_dir) / "caption.txt").write_text(caption, encoding="utf-8")
    (folder(out_dir) / "meta.json").write_text(json.dumps(
        {"topic": spec["symbol"], "title": spec["title"], "duration": res["duration"],
         "music": music.name if music else None}, ensure_ascii=False), encoding="utf-8")
    return True


def files(out_dir: Path) -> tuple[Path, Path, Path]:
    f = folder(out_dir)
    return f / "caption.txt", f / "reel.mp4", f / "thumb.jpg"


def meta(out_dir: Path) -> dict:
    return json.loads((folder(out_dir) / "meta.json").read_text(encoding="utf-8"))


def mark_done(meta: dict):
    build.mark_done(meta["topic"], meta.get("title") or "")
