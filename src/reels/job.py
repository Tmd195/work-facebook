"""Việc 'reel' cho bộ chạy bài: viết kịch bản → dựng video + thumbnail → caption."""
import json
from pathlib import Path

from src.content import fbtext
from src.reels import build, script

BRAND_TAG = "#DuyThaiDang"


def folder(out_dir: Path) -> Path:
    return out_dir / "reel"


def generate(out_dir: Path) -> bool:
    s = script.write(script.next_brief())
    res = build.make(s, folder(out_dir))
    tags = [BRAND_TAG] + [t if t.startswith("#") else "#" + t for t in s.get("hashtags") or []]
    tags = list(dict.fromkeys(t.replace(" ", "") for t in tags))
    caption = fbtext.render(s["caption"]).strip() + "\n\n" + " ".join(tags[:7])
    (folder(out_dir) / "caption.txt").write_text(caption, encoding="utf-8")
    (folder(out_dir) / "meta.json").write_text(json.dumps(
        {"topic": s["topic"], "pillar": s["pillar"], "system": s.get("system"),
         "duration": round(res["duration"], 1), "music": res["music"]}, ensure_ascii=False), encoding="utf-8")
    return True


def files(out_dir: Path) -> tuple[Path, Path, Path]:
    f = folder(out_dir)
    return f / "caption.txt", f / "reel.mp4", f / "thumbnail.jpg"


def meta(out_dir: Path) -> dict:
    return json.loads((folder(out_dir) / "meta.json").read_text(encoding="utf-8"))
