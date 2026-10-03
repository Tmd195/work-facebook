"""Việc 'reel_story' (Page Decode Global & Partner, cách ngày): AI kể chuyện nghề IB → dựng → kiểm tra/sửa → caption."""
import json
from pathlib import Path

from src.reels import render as old
from src.reels.story import build, script


def folder(out_dir: Path) -> Path:
    return out_dir / "reel_story"


def generate(out_dir: Path) -> bool:
    from src.content import cwg_daily
    from src.reels import qa
    f = folder(out_dir)
    st = {"spec": script.write(), "music": None}

    def make(variant):
        build.SEED_SHIFT = variant * 7                 # bố cục khác = bộ video nền khác (rõ chữ hơn trên nền tối hơn…)
        st["music"] = st["music"] or old.pick_music()
        return build.make(st["spec"], f, st["music"])

    def check(res):
        sp = st["spec"]
        texts = [sp.get("title", ""), sp.get("caption", "")] + [b.get("text", "") for b in sp["beats"]]
        return qa.run(res["video"], f, min_dur=10, max_dur=qa.FB_MAX, texts=texts, banned=["18+"], voices=res["voices"],
                      context="Reels kể chuyện nghề IB tiếng Việt của Page Decode Global & Partner (video nền minh họa).")

    def fix(errors):
        st["spec"] = qa.edit_spec(st["spec"], errors)

    res = qa.produce("Reels storytelling Decode", f, make, check, fix)
    spec = json.loads((f / "script.json").read_text(encoding="utf-8"))
    caption = cwg_daily.caption(spec.get("caption", ""), [t.lstrip("#") for t in spec.get("hashtags") or []])
    (f / "caption.txt").write_text(caption, encoding="utf-8")
    (f / "meta.json").write_text(json.dumps({"topic": spec.get("topic"), "title": spec.get("title"),
                                             "duration": res["duration"]}, ensure_ascii=False), encoding="utf-8")
    return True


def files(out_dir: Path) -> tuple[Path, Path, Path]:
    f = folder(out_dir)
    return f / "caption.txt", f / "reel.mp4", f / "thumb.jpg"


def meta(out_dir: Path) -> dict:
    return json.loads((folder(out_dir) / "meta.json").read_text(encoding="utf-8"))


def mark_done(meta: dict):
    script.mark_done(meta.get("topic") or "", meta.get("title") or "")
