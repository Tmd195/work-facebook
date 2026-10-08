"""Việc 'reel_indi' (Page DecodeFx Trading, 20:00 mỗi ngày): Reels "Signal Replay" quảng bá indicator Sniper AI V4 / V7.

Xoay vòng V7 / V4 theo ngày; chọn lệnh THẬT chạm TP3 trên vàng M5 (60 ngày gần nhất), lệnh đã đăng không dùng lại
(state/<job>/indi_reels.json). Dựng → kiểm tra (qa) → caption. Khuôn: src/reels/indi/build.py.
"""
import json
from datetime import datetime
from pathlib import Path

from src.config import STATE, TZ
from src.reels.indi import boss, build

FILE = STATE / "indi_reels.json"


def _state() -> dict:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"used": []}


def folder(out_dir: Path) -> Path:
    return out_dir / "reel_indi"


def _key(version, d, t) -> str:
    return f"{version}|{d.index[t.i0].isoformat()}"


def generate(out_dir: Path) -> bool:
    from src.content import cwg_daily
    from src.data.prices import get_m5
    from src.reels import qa
    f = folder(out_dir)
    day = datetime.now(TZ).date().toordinal()
    used = set(_state()["used"])
    raw = boss.frame(get_m5("XAUUSD", "60d"))
    versions = ["V7", "V4"] if day % 2 == 0 else ["V4", "V7"]
    pool = []                                            # ưu tiên bản của ngày, lệnh chưa đăng, diễn biến đẹp (≥ 4 nến)
    for v in versions:
        d, good = build.best_trades(v, raw=raw)
        pool += [(v, d, t) for t in good if _key(v, d, t) not in used]
    if not pool:
        raise RuntimeError("Hết lệnh Sniper AI đạt chuẩn chưa đăng trong 60 ngày gần nhất")
    st = {}

    def make(variant):
        v, d, t = pool[min(variant, len(pool) - 1)]       # bản lỗi → lệnh khác
        st["x"] = (v, d, t)
        return build.make(d, t, f)

    def check(res):
        return qa.run(res["video"], f, min_dur=8, max_dur=qa.FB_MAX, texts=[], banned=["18+"], voices=None, ui=False,
                      context="Reels quảng bá indicator Sniper AI: biểu đồ vàng M5 kiểu TradingView, nhãn lệnh BUY/SELL, "
                              "ENTRY/SL/TP1-3, bộ đếm pips, thẻ kết quả cuối video; video không lời, chỉ chữ và nhạc.")

    res = qa.produce("Reels Sniper AI", f, make, check, lambda errors: None)
    v, d, t = st["x"]
    info = res["info"]
    side = "BUY" if t.side == 1 else "SELL"
    body = (f"{build.NAME[v]} – {side} VÀNG +{info['pips']} PIPS\n"
            f"Tín hiệu {side} XAUUSD M5 lúc {info['time_vn']}, chạm {info['result']} sau {info['minutes']} phút.\n"
            f"Indicator Sniper AI tự lọc xu hướng đa khung, báo điểm vào, SL và 3 mức TP ngay trên biểu đồ.\n"
            f"1 chỉ báo miễn phí giúp anh chị em kiếm 100pip mỗi ngày.\n"
            f"📩 Liên hệ qua Page để sử dụng miễn phí.\n"
            f"Ví dụ trên dữ liệu quá khứ, tín hiệu chọn lọc, không phải lời khuyên đầu tư.")
    caption = cwg_daily.caption(body, ["SniperAI", "XAUUSD", "Indicator", "TradingView"])
    (f / "caption.txt").write_text(caption, encoding="utf-8")
    (f / "meta.json").write_text(json.dumps({"key": _key(v, d, t), "version": v, "side": side, "pips": info["pips"],
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
