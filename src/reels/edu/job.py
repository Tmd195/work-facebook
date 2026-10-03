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
    from src.reels import qa
    f = folder(out_dir)
    st = {"spec": script.write(), "music": None}

    def make(variant):
        from src.reels.edu import render as R
        R.VARIANT = variant
        st["music"] = st["music"] or pick_music()
        return build.make(st["spec"], f, music=st["music"])

    def check(res):
        sp = st["spec"]
        texts = [sp.get("title", ""), sp.get("caption", "")] + [sc.get("text", "") for sc in sp["scenes"]]
        return qa.run(res["video"], f, min_dur=10, max_dur=qa.FB_MAX, texts=texts, banned=["18+"], voices=res["voices"],
                      context="Video kiến thức tiếng Việt của Page CWG Markets & Partner (biểu đồ là dữ liệu minh họa).")

    def fix(errors):                                   # AI sửa đúng chỗ lỗi, giữ nguyên nội dung/chú thích
        st["spec"] = script.validate(qa.edit_spec(st["spec"], errors))

    res = qa.produce("Reels CWG VN", f, make, check, fix)
    spec = json.loads((f / "script.json").read_text(encoding="utf-8"))
    music = st["music"]
    body = (spec.get("title", "").strip() + "\n\n" + spec.get("caption", "").strip()).strip()
    caption = cwg_daily.caption(body, [t.lstrip("#") for t in spec.get("hashtags") or []])
    (folder(out_dir) / "caption.txt").write_text(caption, encoding="utf-8")
    (folder(out_dir) / "meta.json").write_text(json.dumps(
        {"topic": spec["topic"], "title": spec.get("title"), "duration": res["duration"],
         "music": music.name if music else None}, ensure_ascii=False), encoding="utf-8")
    return True


def pick_music() -> Path | None:
    """Kho nhạc của Page: reels.music_dirs = các thư mục con trong assets/music ("." = 14 bài EDM chung,
    "cwg" = 9 bài trap/hip-hop). Mỗi video chọn ngẫu nhiên 1 bài trong tất cả."""
    dirs = (CONFIG.get("reels") or {}).get("music_dirs")
    if not dirs or os.environ.get("REEL_MUSIC"):
        return old.pick_music()
    tracks = sorted(t for d in dirs for t in (old.MUSIC / d).glob("*.mp3"))
    return random.choice(tracks) if tracks else old.pick_music()


def files(out_dir: Path) -> tuple[Path, Path, Path]:
    f = folder(out_dir)
    return f / "caption.txt", f / "reel.mp4", f / "thumb.jpg"


def meta(out_dir: Path) -> dict:
    return json.loads((folder(out_dir) / "meta.json").read_text(encoding="utf-8"))


def mark_done(meta: dict):
    script.mark_done(meta["topic"], meta.get("title") or "")
