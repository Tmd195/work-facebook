"""Việc 'reel' cho bộ chạy bài: viết kịch bản → dựng video + thumbnail → caption."""
import json
from pathlib import Path

from src.config import CONFIG, IS_DEFAULT_JOB
from src.content import fbtext
from src.reels import build, script

BRAND_TAG = "#DuyThaiDang"


def _brand_job():
    """Page thương hiệu: reels.style = market (Page Global – khuôn biểu đồ thị trường) | edu (CWG VN – kiến thức)."""
    if (CONFIG.get("reels") or {}).get("style") == "market":
        from src.reels.mkt import job as mod
    else:
        from src.reels.edu import job as mod
    return mod


def folder(out_dir: Path) -> Path:
    return out_dir / "reel"


def generate(out_dir: Path) -> bool:
    if not IS_DEFAULT_JOB:                               # Page thương hiệu → mẫu video kiến thức có logo
        edu = _brand_job()
        return edu.generate(out_dir)
    from src.reels import qa
    brief = script.next_brief()
    f = folder(out_dir)
    st = {"s": script.write(brief)}

    def make(variant):
        from src.reels import marks
        marks.VARIANT = variant
        return build.make(st["s"], f)

    def check(res):
        return qa.run(res["video"], f, min_dur=10, max_dur=qa.FB_MAX, voices=res["voices"],
                      context="Video kiến thức vàng tiếng Việt của Page Duy Thái Đặng (có ảnh người thật).",
                      ui=False)                            # bố cục Thái giữ như cũ (anh duyệt) – không xét vùng nút Reels

    def fix(errors):                                   # AI sửa đúng chỗ lỗi, giữ nguyên nội dung/hiệu ứng
        st["s"] = qa.edit_spec(st["s"], errors)

    res = qa.produce("Reels Duy Thái Đặng", f, make, check, fix)
    s = json.loads((f / "script.json").read_text(encoding="utf-8"))
    tags = [BRAND_TAG] + [t if t.startswith("#") else "#" + t for t in s.get("hashtags") or []]
    tags = list(dict.fromkeys(t.replace(" ", "") for t in tags))
    caption = fbtext.render(s["caption"]).strip() + "\n\n" + " ".join(tags[:7])
    (folder(out_dir) / "caption.txt").write_text(caption, encoding="utf-8")
    (folder(out_dir) / "meta.json").write_text(json.dumps(
        {"topic": s["topic"], "pillar": s["pillar"], "system": s.get("system"),
         "duration": round(res["duration"], 1), "music": res["music"]}, ensure_ascii=False), encoding="utf-8")
    return True


def files(out_dir: Path) -> tuple[Path, Path, Path]:
    if not IS_DEFAULT_JOB:
        edu = _brand_job()
        return edu.files(out_dir)
    f = folder(out_dir)
    return f / "caption.txt", f / "reel.mp4", f / "thumbnail.jpg"


def meta(out_dir: Path) -> dict:
    if not IS_DEFAULT_JOB:
        edu = _brand_job()
        return edu.meta(out_dir)
    return json.loads((folder(out_dir) / "meta.json").read_text(encoding="utf-8"))


def mark_done(meta: dict):
    if not IS_DEFAULT_JOB:
        edu = _brand_job()
        return edu.mark_done(meta)
    script.mark_done(meta)
