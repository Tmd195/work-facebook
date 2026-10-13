"""Việc 'reel_edu' – Page Duy Thái Đặng: mỗi ngày 1 tập REELS EDUCATION (giao diện gold anh chốt 13/10/2026)."""
import json
from pathlib import Path

from src.reels import render as old
from src.reels.thai_edu import build, script

THEME = "gold"
TAGS = "#DuyThaiDang #ReelsEducation #XAUUSD #HocTrading #KienThucForex"


def folder(out_dir: Path) -> Path:
    return out_dir / "reel_edu"


def generate(out_dir: Path) -> bool:
    from src.reels import qa
    ep = script.next_episode()
    if ep is None:
        raise RuntimeError("Đã hết lộ trình Reels Education (knowledge/edu_reels.yaml) – cần thêm tập mới")
    eps = script.episodes()
    nxt = eps[ep["no"]] if ep["no"] < len(eps) else None
    f = folder(out_dir)
    st = {"spec": script.write(ep, nxt), "music": old.pick_music()}

    def make(variant):
        from src.reels.edu import render as R
        R.VARIANT = variant
        return build.make(st["spec"], f, THEME, music=st["music"])

    def check(res):
        sp = st["spec"]
        texts = [sp.get("title", ""), sp.get("caption", "")] + [sc.get("text", "") for sc in sp["scenes"]]
        return qa.run(res["video"], f, min_dur=10, max_dur=qa.FB_MAX, texts=texts, banned=["18+"], voices=res["voices"],
                      context="Reels Education tiếng Việt của Page Duy Thái Đặng (biểu đồ minh hoạ, bài học đánh số tập).")

    def fix(errors):
        from src.reels.edu import script as edu
        st["spec"] = edu.validate(qa.edit_spec(st["spec"], errors))

    res = qa.produce("Reels Education", f, make, check, fix)
    spec = json.loads((f / "script.json").read_text(encoding="utf-8"))
    from src.content import fbtext
    caption = fbtext.render(spec.get("caption") or spec["title"]).strip() + "\n\n" + TAGS
    (f / "caption.txt").write_text(caption, encoding="utf-8")
    (f / "meta.json").write_text(json.dumps(
        {"episode": ep["no"], "topic": spec["topic"], "title": ep["title"], "duration": res["duration"],
         "music": st["music"].name if st["music"] else None}, ensure_ascii=False), encoding="utf-8")
    return True


def files(out_dir: Path) -> tuple[Path, Path, Path]:
    f = folder(out_dir)
    return f / "caption.txt", f / "reel.mp4", f / "thumb.jpg"


def meta(out_dir: Path) -> dict:
    return json.loads((folder(out_dir) / "meta.json").read_text(encoding="utf-8"))


def mark_done(meta: dict):
    script.mark_done(meta["episode"], meta.get("title") or "")
