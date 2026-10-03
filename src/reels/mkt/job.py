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
    spec, f = build.write(symbol), folder(out_dir)
    for attempt in range(1, 4):                       # dựng → kiểm tra → tự sửa tối đa 2 lần
        music = old.pick_music()
        res = build.make(spec, f, music=music)
        texts = ([spec.get("hook_text") or spec["hook"]] + [x.get("text") or x["say"] for x in spec["lines"]]
                 + [spec["title"], spec["question"], spec["caption"]])
        rep = qa.run(res["video"], f, min_dur=25, max_dur=62, texts=texts, facts=res["facts"], banned=BANNED,
                     voices=res["voices"], context=f"Video thị trường {symbol} của Page CWG Markets Global (tiếng Anh).")
        if rep["ok"]:
            break
        print(f"  ! kiểm tra lần {attempt} không đạt: {rep['errors']}", flush=True)
        if attempt == 3:
            qa.fail_alert(f"Reels CWG Global {symbol}", rep, attempt)
            raise qa.QAFail("; ".join(rep["errors"][:3]), Path(rep["sheet"]))
        if rep["fix"]:                                 # cùng kịch bản dựng lại sẽ ra đúng hình cũ → viết mới
            spec = build.write(symbol)
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
