"""Việc 'reel' cho Page Global: Reels thị trường theo khuôn mẫu anh chọn (tiêu đề + cờ → biểu đồ giá thật
+ chỉ báo → câu hỏi → logo CWG), giọng nhân bản tiếng Anh."""
import json
from pathlib import Path

from src.reels import render as old
from src.reels.mkt import build


def folder(out_dir: Path) -> Path:
    return out_dir / "reel"


BANNED = ["India", "Japan", "Korea", "Indonesia", "Malaysia", "buy now", "sell now", "guaranteed", "risk-free",
          "entry at", "stop loss at", "take profit at"]


def generate(out_dir: Path) -> bool:
    from src.content import cwg_daily
    from src.reels import qa
    symbol = build.next_symbol()
    f = folder(out_dir)
    st = {"spec": build.write(symbol), "music": None}

    def make(variant):
        from src.reels.mkt import render as R
        R.VARIANT = variant
        st["music"] = st["music"] or old.pick_music()
        return build.make(st["spec"], f, music=st["music"])

    def check(res):
        sp = st["spec"]
        texts = ([sp.get("hook_text") or sp["hook"]] + [x.get("text") or x["say"] for x in sp["lines"]]
                 + [sp["title"], sp["question"], sp["caption"]])
        return qa.run(res["video"], f, min_dur=10, max_dur=qa.FB_MAX, texts=texts, facts=res["facts"], banned=BANNED,
                      voices=res["voices"], context=f"Video thị trường {symbol} của Page CWG Markets Global (tiếng Anh).")

    def fix(errors):                                   # AI sửa đúng câu lỗi, giữ nguyên phần còn lại
        st["spec"] = qa.edit_spec(st["spec"], errors, "Số liệu thật (chỉ được dùng các số này): "
                                  + json.dumps(build.D.load(symbol).facts, ensure_ascii=False))

    res = qa.produce(f"Reels CWG Global {symbol}", f, make, check, fix)
    spec = json.loads((f / "script.json").read_text(encoding="utf-8"))   # kịch bản của bản được đăng
    music = st["music"]
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
