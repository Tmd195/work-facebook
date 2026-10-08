"""Việc 'reel_smc' (Page DecodeFx Trading, mỗi ngày): Reels KIẾN THỨC HỆ THỐNG trên lệnh THẬT.

Mỗi video = 1 hệ thống, cách dùng hiệu quả từng bước (anh chốt 08/10/2026). Xoay vòng hệ thống theo ngày,
lệnh đã đăng không dùng lại (state/<job>/smc_reels.json). Giọng nhân bản "voice 01" (assets/private/voice_ref_decode_trading.mp3).
Khuôn: src/reels/smc/build.py · thumbnail giật tít: src/reels/smc/cover.py.
"""
import json
from datetime import datetime
from pathlib import Path

from src.config import ROOT, STATE, TZ
from src.reels.smc import build
from src.reels.smc.setup import find

FILE = STATE / "smc_reels.json"
SYSTEMS = ["supply", "ob"]                               # thêm hệ thống mới vào đây khi anh duyệt
VOICE = ROOT / "assets" / "private" / "voice_ref_decode_trading.mp3"
NAMES = {"supply": "Vùng cung cầu + Premium/Discount", "ob": "Order Block + FVG"}


def _state() -> dict:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"used": []}


def folder(out_dir: Path) -> Path:
    return out_dir / "reel_smc"


def _key(s) -> str:
    return f"{s.system}|{s.symbol}|{s.d.index[s.k].isoformat()}"


def caption_body(s) -> str:
    sell = s.side == "sell"
    if s.system == "ob":
        head = "ORDER BLOCK – DÙNG SAI LÀ CHÁY TÀI KHOẢN"
        steps = ["Cú " + ("giảm" if sell else "tăng") + " mạnh phá cấu trúc (BOS)",
                 "Order Block = nến " + ("tăng" if sell else "giảm") + " cuối cùng trước cú " + ("giảm" if sell else "tăng"),
                 "Kéo vùng Order Block sang phải",
                 "OB mạnh phải để lại khoảng trống giá FVG – không có thì bỏ qua",
                 "Chờ giá quay về OB, có nến xác nhận mới vào lệnh"]
        risk = f"SL {'trên' if sell else 'dưới'} OB · TP tại thanh khoản · R:R 1:{s.rr:.1f}"
    else:
        head = f"MÔ HÌNH {'BÁN' if sell else 'MUA'} CỦA TỔ CHỨC – 5 BƯỚC SMC"
        steps = ["BOS xác nhận xu hướng " + ("giảm" if sell else "tăng"),
                 "Xác định vùng giao dịch đỉnh – đáy",
                 f"Vẽ vùng {'cung' if sell else 'cầu'} tại gốc cú {'giảm' if sell else 'tăng'}",
                 f"Chỉ {'bán ở vùng Premium (trên' if sell else 'mua ở vùng Discount (dưới'} 50%)",
                 f"Chờ giá hồi về vùng {'cung' if sell else 'cầu'} + nến xác nhận"]
        risk = f"SL {'trên' if sell else 'dưới'} vùng · TP tại thanh khoản · R:R 1:{s.rr:.1f}"
    nums = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    return (f"{head}\n"
            f"Ví dụ thật {s.symbol} {s.tf}:\n" + "\n".join(f"{n} {t}" for n, t in zip(nums, steps)) + "\n"
            f"🎯 {risk}\n"
            f"💾 Lưu lại để áp dụng · Follow DecodeFX Trading\n"
            f"Ví dụ trên dữ liệu quá khứ.")                    # cảnh báo rủi ro đầy đủ đã có ở chữ ký Page


def generate(out_dir: Path) -> bool:
    from src.content import cwg_daily
    from src.reels import qa
    f = folder(out_dir)
    day = datetime.now(TZ).date().toordinal()
    used = set(_state()["used"])
    order = SYSTEMS[day % len(SYSTEMS):] + SYSTEMS[: day % len(SYSTEMS)]
    pool = []
    for sysname in order:
        pool += [s for s in find(system=sysname) if _key(s) not in used]
    if not pool:
        raise RuntimeError("Hết setup hệ thống đạt chuẩn chưa đăng trong 60 ngày gần nhất")
    st = {}

    def make(variant):
        s = pool[min(variant, len(pool) - 1)]
        st["s"] = s
        r = build.make(s, f, voice_on=True, voice_ref=VOICE, seed=day)
        r["duration"] = round(build.T["total"], 1)
        return r

    def check(res):
        lines = list(build.narration(st["s"]).values())
        return qa.run(res["video"], f, min_dur=15, max_dur=qa.FB_MAX, texts=lines, banned=["18+"], voices=None, ui=False,
                      context="Reels kiến thức hệ thống giao dịch (SMC) của Page DecodeFx Trading: chart nến nền sáng kiểu "
                              "TradingView, chuột vẽ BOS / vùng / FVG, nhãn gõ chữ, phụ đề tiếng Việt dải xanh than, "
                              "giọng đọc tiếng Việt, kết thúc bằng lời mời thả tim – chia sẻ – theo dõi.")

    res = qa.produce("Reels kiến thức hệ thống", f, make, check, lambda errors: None)
    s = st["s"]
    caption = cwg_daily.caption(caption_body(s), ["SMC", "OrderBlock" if s.system == "ob" else "SupplyDemand",
                                                  s.symbol, "PriceAction"])
    (f / "caption.txt").write_text(caption, encoding="utf-8")
    (f / "meta.json").write_text(json.dumps({"key": _key(s), "system": s.system, "symbol": s.symbol, "side": s.side,
                                             "rr": s.rr, "duration": res["duration"]}, ensure_ascii=False),
                                 encoding="utf-8")
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
