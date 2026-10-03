"""Việc 'reel_quiz' (Page Decode Global & Partner, MỖI NGÀY): Reels "BUY OR SELL?" trên lệnh THẬT.

Chọn setup: xoay hệ thống giao dịch theo ngày (range → double → fibo → retest → abcd) và xoay cặp tiền;
lệnh đã đăng không dùng lại (state/<job>/quiz_reels.json). Dựng → kiểm tra (qa) → caption.
Khuôn đã chốt với anh: xem src/reels/quiz/build.py và memory decode-quiz-reels.
"""
import json
from datetime import datetime
from pathlib import Path

from src.config import STATE, TZ
from src.reels.quiz import build
from src.reels.quiz.setup import SYSTEMS, find

FILE = STATE / "quiz_reels.json"
SYMBOLS = ["XAUUSD", "USDJPY", "GBPJPY", "EURJPY", "USDCHF", "USDCAD", "EURUSD", "GBPUSD", "AUDUSD"]


def _state() -> dict:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"used": []}


def folder(out_dir: Path) -> Path:
    return out_dir / "reel_quiz"


def pick(day: int, skip: set, nth: int = 0):
    """Setup thứ nth hợp lệ: ưu tiên hệ thống của ngày, cặp tiền xoay vòng; cú chạy bùng nổ ≤ 8 nến."""
    order = SYSTEMS[day % len(SYSTEMS):] + SYSTEMS[: day % len(SYSTEMS)]
    syms = SYMBOLS[day % len(SYMBOLS):] + SYMBOLS[: day % len(SYMBOLS)]
    found = 0
    for fast in (True, False):
        for sysname in order:
            for sym in syms:
                try:
                    s = find(sym, "M5", [sysname], skip=skip)
                except Exception as exc:                 # thiếu dữ liệu 1 cặp → thử cặp khác
                    print(f"  ! {sym}: {exc}", flush=True)
                    continue
                if s is None or (fast and s.hit - s.k > 8):
                    continue
                if found == nth:
                    return s
                found += 1
    return None


def generate(out_dir: Path) -> bool:
    from src.content import cwg_daily
    from src.reels import qa
    f = folder(out_dir)
    day = datetime.now(TZ).date().toordinal()
    skip = set(_state()["used"])
    st = {}

    def make(variant):
        s = pick(day, skip, variant)                     # bố cục khác = setup khác
        if s is None:
            raise RuntimeError("Không tìm được setup thật đạt chuẩn")
        st["s"] = s
        return build.make(s, f)

    def check(res):
        return qa.run(res["video"], f, min_dur=8, max_dur=qa.FB_MAX, texts=list(res["voices"][1]), banned=["18+"],
                      voices=None, ui=False,
                      context="Reels 'BUY OR SELL?' của Page Decode: biểu đồ nến M5 thật, câu đố rồi lộ đáp án; "
                              "chữ trên biểu đồ là tiếng Anh như Support, Resistance, LEG 1, LEG 2, TP1, SL.")

    def fix(errors):
        pass                                             # lỗi → make(variant) chọn setup khác

    res = qa.produce("Reels BUY OR SELL Decode", f, make, check, fix)
    s = st["s"]
    side = "SELL" if s.side == "sell" else "BUY"
    rr = ((s.entry - s.l[s.hit]) if s.side == "sell" else (s.h[s.hit] - s.entry)) / abs(s.entry - s.sl)
    body = (f"BUY OR SELL? {s.symbol}\n"
            f"Nhìn biểu đồ trước khi lộ đáp án, bạn sẽ vào lệnh nào?\n"
            f"Đáp án: {side} – {s.name.lower()}, giá chạy +{rr:.1f}R.\n"
            f"Ví dụ trên dữ liệu quá khứ, không phải tín hiệu giao dịch.")
    caption = cwg_daily.caption(body, ["BuyOrSell", "Forex", s.symbol, "PriceAction"])
    (f / "caption.txt").write_text(caption, encoding="utf-8")
    (f / "meta.json").write_text(json.dumps({"key": f"{s.symbol}|{s.entry:.5f}", "symbol": s.symbol,
                                             "system": s.system, "side": s.side, "rr": round(rr, 1),
                                             "duration": res["duration"]}, ensure_ascii=False), encoding="utf-8")
    return True


def files(out_dir: Path) -> tuple[Path, Path, Path]:
    f = folder(out_dir)
    return f / "caption.txt", f / "reel.mp4", f / "thumb.jpg"


def meta(out_dir: Path) -> dict:
    return json.loads((folder(out_dir) / "meta.json").read_text(encoding="utf-8"))


def mark_done(meta: dict):
    st = _state()
    st["used"] = (st["used"] + [meta.get("key", "")])[-500:]
    FILE.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
