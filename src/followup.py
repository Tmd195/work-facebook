"""Comment theo dõi dưới các bài đã đăng.

    python -m src.followup examples [--check]   # Kiến thức: 2-3 ví dụ biểu đồ thật, 30 phút sau khi đăng
    python -m src.followup news [--check]       # Bản tin sáng: cập nhật số liệu tin đỏ ~5-15 phút sau khi ra
    python -m src.followup track [--check]      # Chiến lược: 22:00 kiểm tra khớp lệnh, TP/SL, pips, quản trị lệnh

--check: chỉ in DUE/NONE (để workflow bỏ qua bước cài đặt nặng khi không có việc).
Ở chế độ xem trước (config autopost.live = false) comment được gửi về Telegram thay vì Facebook.
"""
import argparse
import json
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from src.config import CONFIG, OUTPUT, ROOT, TZ
from src.content import llm
from src.publish import facebook, telegram

STATE = ROOT / "state" / "followups.json"
POSTED = ROOT / "state" / "posted.json"
PIP = 0.01                    # vàng: 1 pip = 0.01 → 4580.74 → 4580.84 = 10 pips
STRATEGY_DISCLAIMER = ("⚠️ Đây là góc nhìn cá nhân của Thái, không phải 1 lời khuyên đầu tư. Hãy tự chịu trách nhiệm "
                       "với mọi quyết định của bản thân tại thời điểm hiện tại cũng như tương lai.")
PAIR_OF = {"USD": "XAUUSD", "EUR": "EURUSD", "GBP": "GBPUSD"}


# ===================================================================== trạng thái

def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def done(key: str) -> bool:
    return key in _load(STATE)


def mark(key: str, info: dict):
    data = _load(STATE)
    data[key] = {"at": datetime.now(TZ).isoformat(), **info}
    keep = sorted(data, key=lambda k: data[k]["at"])[-500:]
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({k: data[k] for k in keep}, ensure_ascii=False, indent=1), encoding="utf-8")


def todays_posts(job_prefix: str) -> list[tuple[str, dict]]:
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    return [(slot, e) for slot, e in sorted(_load(POSTED).items())
            if slot.startswith(today) and isinstance(e, dict) and e.get("job", "").startswith(job_prefix)]


def publish_comment(entry: dict, text: str, image: Path | None, what: str) -> bool:
    """Comment lên Facebook (hoặc gửi bản xem trước về Telegram nếu bài gốc chỉ là bản xem trước)."""
    if entry.get("preview") or not entry.get("post_id"):
        telegram.send_preview(f"🧪 [XEM TRƯỚC COMMENT] {what}", text, [image] if image else [])
        return True
    try:
        facebook.comment(entry["post_id"], text, image)
    except facebook.FacebookError as exc:
        (telegram.need_fix if exc.needs_user else telegram.send)(f"❌ Comment thất bại: {what}\n{exc}")
        return False
    telegram.send(f"💬 Đã comment: {what}\n🔗 Bài viết: {entry['link']}\nAnh kiểm tra nếu cần sửa đổi.")
    return True


def out_dir() -> Path:
    d = OUTPUT / datetime.now(TZ).strftime("%Y-%m-%d") / "followup"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ===================================================================== 1. Kiến thức: ví dụ biểu đồ thật

PICK_PROMPT = """Bạn là người biên tập nội dung giáo dục forex. Một bài kiến thức vừa được đăng (ĐỀ CƯƠNG BÀI bên dưới).
Hãy chọn 2-3 VÍ DỤ trên biểu đồ GIÁ THẬT để comment dưới bài, giúp người đọc thấy cách áp dụng kiến thức vào chart.
Mỗi ví dụ là một biểu đồ "mode":"real" (theo đặc tả CHART), chọn symbol/tf/tools sao cho thể hiện ĐÚNG kiến thức của bài.
Các ví dụ nên khác nhau (khác mã hoặc khác khung thời gian). Không dùng mode "illustration".
Nếu kiến thức của bài không thể hiện được trên giá thật bằng các tools có sẵn, trả về danh sách rỗng."""

WRITE_PROMPT = """Bạn viết comment ví dụ dưới bài kiến thức forex trên Facebook Page (xưng "anh em").
Với MỖI ví dụ trong DỮ LIỆU (đã có biểu đồ giá thật + các điểm code tìm được trên chart), viết 1 comment 70-150 từ:
- Dòng đầu: "📌 Ví dụ <số>/<tổng>: <mã> khung <tf>"
- Chỉ cho người đọc thấy trên hình: vùng/điểm đánh dấu là gì, vì sao đúng với kiến thức của bài.
- Cách áp dụng: nếu gặp tình huống này thì làm gì (điều kiện vào lệnh / chờ xác nhận / đặt dừng lỗ ở đâu - nói theo nguyên tắc).
- 1 câu lưu ý rủi ro.
Chỉ dùng con số có trong "facts". Không dùng markdown (**, #). Tối đa 4 emoji mỗi comment."""


def examples(check: bool = False) -> bool:
    from src import chart_tools
    from src.content import knowledge

    now = datetime.now(TZ)
    due = [(slot, e) for slot, e in todays_posts("knowledge")
           if not done(f"{slot}|examples") and now - datetime.fromisoformat(e["posted_at"]) >= timedelta(minutes=25)]
    if check:
        print("DUE" if due else "NONE")
        return True
    ok = True
    for slot, entry in due:
        meta = entry["meta"]
        series = next(s for s in knowledge.load_series() if s["id"] == meta["series"])
        lesson = series["lessons"][meta["part"] - 1]
        what = f"Ví dụ thực tế cho {series['name']} – Phần {meta['part']}"
        ctx = json.dumps({"series": series["name"], "lesson": lesson}, ensure_ascii=False, indent=1)
        schema = {"type": "object", "properties": {"examples": {"type": "array", "items": {
            "type": "object", "properties": {"chart": {"type": "object"}, "why": {"type": "string"}},
            "required": ["chart", "why"]}}}, "required": ["examples"]}
        try:
            picks = llm.generate_json(PICK_PROMPT + "\n\n" + chart_tools.CHART_SPEC, "ĐỀ CƯƠNG BÀI:\n" + ctx, schema)
        except Exception as exc:
            telegram.send(f"⚠️ {what}: AI lỗi khi chọn ví dụ ({exc}). Sẽ thử lại ở lần chạy sau.")
            ok = False
            continue
        rendered = []
        for k, ex in enumerate((picks.get("examples") or [])[:3], 1):
            spec = {**ex["chart"], "mode": "real"}
            try:
                ch, facts = chart_tools.build_real(spec)
                path = out_dir() / f"{slot.replace(' ', '_').replace(':', '')}_ex{k}.png"
                ch.render(900, 600, scale=2).convert("RGB").save(path)
                rendered.append({"symbol": spec.get("symbol"), "tf": spec.get("tf"), "tools": spec.get("tools"),
                                 "why": ex["why"], "facts": facts, "image": path})
            except Exception as exc:
                print(f"  ! Ví dụ {k} không vẽ được: {exc}")
        if not rendered:
            mark(f"{slot}|examples", {"skipped": "không có ví dụ phù hợp trên giá thật"})
            telegram.send(f"ℹ️ {what}: hôm nay không tìm được ví dụ đạt chuẩn trên giá thật, bỏ qua (không bịa ví dụ).")
            continue
        data = [{k: v for k, v in r.items() if k != "image"} for r in rendered]
        wschema = {"type": "object", "properties": {"comments": {"type": "array", "items": {"type": "string"}}},
                   "required": ["comments"]}
        try:
            texts = llm.generate_json(WRITE_PROMPT, "BÀI: " + ctx + "\n\nDỮ LIỆU:\n" +
                                      json.dumps(data, ensure_ascii=False, indent=1), wschema)["comments"]
        except Exception as exc:
            telegram.send(f"⚠️ {what}: AI lỗi khi viết comment ({exc}). Sẽ thử lại ở lần chạy sau.")
            ok = False
            continue
        from src.content.fbtext import render as clean
        for r, text in zip(rendered, texts):
            publish_comment(entry, clean(text), r["image"], f"{what} ({r['symbol']} {r['tf']})")
        mark(f"{slot}|examples", {"count": len(rendered)})
    return ok


# ===================================================================== 2. Bản tin sáng: cập nhật tin đỏ

NEWS_PROMPT = """Bạn là biên tập viên tin tức kinh tế cho Facebook Page forex/vàng (xưng "anh em").
Nhiệm vụ: kiểm tra KẾT QUẢ THỰC TẾ (Actual) của các tin kinh tế vừa công bố trong DỮ LIỆU.
1. Dùng WebSearch tìm số liệu thực tế. CHỈ chấp nhận khi có ít nhất 2 nguồn uy tín (Reuters, Bloomberg, FXStreet,
   Investing, ForexFactory, Trading Economics, cơ quan thống kê chính thức...) khớp nhau. Ghi URL vào sources.
   Nếu chưa tìm thấy hoặc các nguồn lệch nhau → found = false (hệ thống sẽ thử lại sau, KHÔNG được đoán).
2. Nếu found: viết "comment" 70-150 từ, không markdown, tối đa 4 emoji:
   - Dòng đầu: "🔴 CẬP NHẬT TIN <giờ> | <tiền tệ>"
   - Mỗi tin: Thực tế / Dự báo / Kỳ trước và chênh lệch so với dự báo (tốt hơn / xấu hơn / đúng dự báo).
   - Ý nghĩa của thay đổi đó với nền kinh tế và chính sách lãi suất.
   - Dòng cuối bắt buộc: "👉 Kết luận: ... tác động TĂNG / GIẢM / TRUNG LẬP cho <tiền tệ>".
3. impact: tác động lên đồng tiền ra tin."""

NEWS_SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "results": {"type": "array", "items": {"type": "object", "properties": {
            "title": {"type": "string"}, "actual": {"type": "string"}, "forecast": {"type": "string"},
            "previous": {"type": "string"}, "vs_forecast": {"type": "string"}},
            "required": ["title", "actual", "forecast", "previous", "vs_forecast"]}},
        "impact": {"type": "string", "enum": ["TĂNG", "GIẢM", "TRUNG LẬP"]},
        "comment": {"type": "string"},
        "sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["found", "results", "impact", "comment", "sources"],
}


def _news_groups(entry: dict) -> list[tuple[str, list[dict]]]:
    """Gom các tin High theo (giờ, tiền tệ)."""
    groups: dict = {}
    for e in entry["meta"].get("events", []):
        if e["impact"] != "High" or e["currency"] not in PAIR_OF:
            continue
        groups.setdefault((e["datetime"], e["currency"]), []).append(e)
    return [(f"{dt}|{cur}", evs) for (dt, cur), evs in sorted(groups.items())]


def news_card(path: Path, cur: str, time_s: str, res: dict, chart_img: Image.Image | None):
    from src.design.common import fit, sans, wrap
    from src.design.styles.block import CREAM, DOWN, GREEN, INK, LIME, MUTED, UP
    W, H, M = 1080, 1350, 56
    img = Image.new("RGBA", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 170], fill=GREEN)
    d.text((M, 40), CONFIG["brand"]["name"], font=sans("Bold", 22), fill=LIME)
    d.text((M, 80), f"CẬP NHẬT TIN {time_s} · {cur}", font=sans("ExtraBold", 50), fill=CREAM)
    y = 200
    for r in res["results"][:3]:
        d.text((M, y), fit(d, r["title"], sans("Bold", 28), W - 2 * M), font=sans("Bold", 28), fill=INK)
        y += 46
        cols = [("Thực tế", r["actual"], INK), ("Dự báo", r["forecast"], MUTED), ("Kỳ trước", r["previous"], MUTED)]
        for k, (lab, val, col) in enumerate(cols):
            x = M + k * 330
            d.text((x, y), lab, font=sans("Medium", 20), fill=MUTED)
            d.text((x, y + 26), val or "-", font=sans("ExtraBold", 40 if k == 0 else 32), fill=col)
        d.text((M, y + 82), r["vs_forecast"], font=sans("SemiBold", 22), fill=GREEN)
        y += 130
    col = UP if res["impact"] == "TĂNG" else DOWN if res["impact"] == "GIẢM" else MUTED
    label = f"TÁC ĐỘNG {res['impact']} CHO {cur}"
    bw = d.textlength(label, font=sans("ExtraBold", 30)) + 50
    d.rounded_rectangle([M, y, M + bw, y + 64], radius=12, fill=col)
    d.text((M + 25, y + 32), label, font=sans("ExtraBold", 30), fill=CREAM, anchor="lm")
    y += 90
    if chart_img is not None:
        h = H - y - 20
        shot = chart_img.resize((W, int(chart_img.height * W / chart_img.width)), Image.LANCZOS)
        img.alpha_composite(shot.crop((0, 0, W, min(h, shot.height))), (0, y))
    img.convert("RGB").save(path)


def _reaction_chart(cur: str, release: datetime) -> Image.Image | None:
    from src.data.prices import get_m5
    from src.design.tvchart import TV, TVChart
    sym = PAIR_OF[cur]
    c = [x for x in get_m5(sym).candles if x.date >= release - timedelta(hours=3)]
    if len(c) < 10:
        return None
    ch = TVChart(sym, "5m", c, 2 if sym == "XAUUSD" else 5, right_offset=6)
    i0 = next((i for i, x in enumerate(c) if x.date >= release), len(c) - 1)
    hi, lo = max(x.high for x in c[i0:]), min(x.low for x in c[i0:])
    ch.rect(i0, len(c) - 1, lo, hi, TV["orange"], "Sau tin", 0.10, "left")
    ch.price_line(c[i0].open, TV["gray"], "Giá lúc ra tin")
    return ch.render(900, 520, scale=2)


def news(check: bool = False) -> bool:
    now = datetime.now(timezone.utc)
    work = []
    for slot, entry in todays_posts("morning"):
        for key, evs in _news_groups(entry):
            release = datetime.fromisoformat(evs[0]["datetime"]).astimezone(timezone.utc)
            k = f"{slot}|news|{key}"
            if done(k) or now < release + timedelta(minutes=4):
                continue
            if now > release + timedelta(hours=3):
                mark(k, {"skipped": "quá 3 giờ không có số liệu"})
                telegram.send(f"ℹ️ Không lấy được số liệu thực tế tin {evs[0]['currency']} "
                              f"{evs[0]['time']} sau 3 giờ, bỏ qua comment cập nhật.")
                continue
            work.append((slot, entry, k, release, evs))
    if check:
        print("DUE" if work else "NONE")
        return True
    for slot, entry, k, release, evs in work:
        cur, time_s = evs[0]["currency"], evs[0]["time"]
        data = {"thời_điểm_công_bố": f"{time_s} giờ VN, ngày {release.astimezone(TZ):%d/%m/%Y}", "tiền_tệ": cur,
                "tin": [{"title": e["title"], "forecast": e["forecast"], "previous": e["previous"]} for e in evs]}
        try:
            res = llm.generate_json(NEWS_PROMPT, "DỮ LIỆU:\n" + json.dumps(data, ensure_ascii=False, indent=1),
                                    NEWS_SCHEMA, web=True)
        except Exception as exc:
            print(f"  ! AI lỗi: {exc}")
            continue
        if not res.get("found") or len(res.get("sources", [])) < 2:
            print(f"  … Chưa có đủ 2 nguồn cho tin {cur} {time_s}, thử lại lần sau")
            continue
        path = out_dir() / f"news_{cur}_{time_s.replace(':', '')}.png"
        try:
            chart = _reaction_chart(cur, release)
        except Exception:
            chart = None
        news_card(path, cur, time_s, res, chart)
        from src.content.fbtext import render as clean
        if publish_comment(entry, clean(res["comment"]), path, f"Cập nhật tin {cur} {time_s} (Bản tin sáng)"):
            mark(k, {"impact": res["impact"], "sources": res["sources"]})
    return True


# ===================================================================== 3. Chiến lược: theo dõi lệnh 22:00

def _pips(diff: float) -> int:
    return round(diff / PIP)


def simulate(s: dict, candles: list) -> dict:
    """Mô phỏng lệnh chờ tại vùng entry trên nến M5 từ lúc đăng bài.
    SELL khớp khi giá chạm cạnh dưới vùng; BUY khớp khi giá chạm cạnh trên vùng.
    Sau TP1 dời SL về Entry. Cùng 1 nến vừa chạm SL vừa chạm TP → tính SL (thận trọng)."""
    sell = s["side"] == "SELL"
    lo, hi = sorted(s["entry"][:2])
    entry = lo if sell else hi
    sl, tps = s["sl"], s["tp"][:3]
    out = {"side": s["side"], "role": s["role"], "entry": entry, "sl": sl, "tp": tps,
           "filled": False, "tp_hit": 0, "closed": None, "pips_closed": None}
    fill_i = next((i for i, c in enumerate(candles) if (c.high >= lo if sell else c.low <= hi)), None)
    if fill_i is None:
        last = candles[-1].close
        out["distance_to_entry_pips"] = _pips(abs(entry - last))
        return out
    out["filled"] = True
    stop = sl
    for c in candles[fill_i:]:
        adverse = c.high >= stop if sell else c.low <= stop
        if adverse:
            out["closed"] = "BE" if stop == entry else "SL"
            out["pips_closed"] = _pips((entry - stop) if sell else (stop - entry))
            break
        while out["tp_hit"] < 3:
            t = tps[out["tp_hit"]]
            if (c.low <= t) if sell else (c.high >= t):
                out["tp_hit"] += 1
                if out["tp_hit"] == 1:
                    stop = entry                       # đạt TP1 → dời SL về Entry
            else:
                break
        if out["tp_hit"] == 3:
            out["closed"] = "TP3"
            out["pips_closed"] = _pips((entry - tps[2]) if sell else (tps[2] - entry))
            break
    out["sl_now"] = stop
    last = candles[-1].close
    out["floating_pips"] = None if out["closed"] else _pips((entry - last) if sell else (last - entry))
    out["tp_pips"] = [_pips(abs(t - entry)) for t in tps]
    out["sl_pips"] = _pips(abs(sl - entry))
    return out


TRACK_PROMPT = f"""Bạn là chuyên viên phân tích vàng của Facebook Page (xưng "anh em"), viết comment CẬP NHẬT LỆNH lúc 22:00
dưới bài chiến lược XAUUSD đã đăng. DỮ LIỆU là kết quả code đã tính chính xác cho từng kịch bản (không tự tính lại).
Quy ước pips vàng: 1 pip = 0.01 (4580.74 → 4580.84 = 10 pips).
Viết 90-180 từ, không markdown, tối đa 5 emoji, KHÔNG nêu giờ khớp lệnh:
- Dòng đầu: "📊 CẬP NHẬT LỆNH 22:00 | XAUUSD giá hiện tại <giá>"
- Từng kịch bản: chưa khớp (còn cách vùng vào bao nhiêu pips) / đã khớp và đang lời-lỗ bao nhiêu pips /
  đã đạt TP1-TP3 (+ bao nhiêu pips) / đã chạm SL (- bao nhiêu pips) / đóng hòa vốn sau khi dời SL.
- Quản trị lệnh: nếu đã đạt TP1 → nhắc đã dời SL về Entry, chốt một phần; nếu đang lời ≥ 50% quãng tới TP1 →
  khuyên cân nhắc dời SL về Entry; nếu đang âm → giữ nguyên SL, không gồng, không nhồi lệnh; rủi ro 1-2%/lệnh.
- Nếu cả 2 kịch bản chưa khớp: nhận định diễn biến tiếp theo dựa trên vị trí giá so với các vùng.
KHÔNG tự viết dòng miễn trừ trách nhiệm (hệ thống tự thêm)."""


def _track_template(price: float, sims: list[dict]) -> str:
    lines = [f"📊 CẬP NHẬT LỆNH 22:00 | XAUUSD giá hiện tại {price:.2f}"]
    for r in sims:
        tag = f"Kịch bản {r['role']} {r['side']} {r['entry']}"
        if not r["filled"]:
            lines.append(f"• {tag}: chưa khớp, giá còn cách vùng vào khoảng {r['distance_to_entry_pips']} pips.")
        elif r["closed"] == "SL":
            lines.append(f"• {tag}: đã chạm SL ({-r['sl_pips']} pips).")
        elif r["closed"] == "BE":
            lines.append(f"• {tag}: đạt TP1 rồi quay về Entry, đóng hòa vốn (0 pips).")
        elif r["closed"] == "TP3":
            lines.append(f"• {tag}: đã đạt TP3 (+{r['tp_pips'][2]} pips).")
        else:
            extra = f", đã đạt TP{r['tp_hit']} (+{r['tp_pips'][r['tp_hit'] - 1]} pips), SL đã dời về Entry" if r["tp_hit"] else ""
            lines.append(f"• {tag}: đã khớp, đang {'+' if r['floating_pips'] >= 0 else ''}{r['floating_pips']} pips{extra}.")
    lines.append("Quản trị: đạt TP1 thì chốt một phần và dời SL về Entry; lệnh đang âm giữ nguyên SL, không nhồi lệnh. "
                 "Rủi ro tối đa 1-2% tài khoản mỗi lệnh.")
    return "\n".join(lines)


def _track_chart(candles: list, sims: list[dict]) -> Image.Image:
    from src.analysis import to_h4  # noqa: F401  (giữ import nhẹ)
    from src.design.tvchart import TV, TVChart
    # gộp M5 → M15 cho gọn
    m15, cur = [], None
    from src.data.prices import Candle
    for c in candles:
        key = c.date.replace(minute=c.date.minute // 15 * 15, second=0, microsecond=0)
        if cur and cur.date == key:
            cur = Candle(key, cur.open, max(cur.high, c.high), min(cur.low, c.low), c.close, cur.volume + c.volume)
            m15[-1] = cur
        else:
            cur = Candle(key, c.open, c.high, c.low, c.close, c.volume)
            m15.append(cur)
    ch = TVChart("XAUUSD", "15m", m15, 2, right_offset=8)
    for r in sims:
        col = TV["down"] if r["side"] == "SELL" else TV["up"]
        ch.price_line(r["entry"], col, f"Entry {r['side']}", style=0, width=2)
        ch.price_line(r["sl_now"] if r.get("sl_now") else r["sl"], TV["text"], f"SL {r['side']}", style=2)
        for k, t in enumerate(r["tp"], 1):
            ch.price_line(t, col, f"TP{k} {r['side']}", style=2)
        ch.include(r["entry"], r["sl"], *r["tp"])
    return ch.render(900, 600, scale=2)


def track(check: bool = False) -> bool:
    from src.data.prices import get_m5
    if datetime.now(TZ).hour < 22 and not check_force_track():
        due = []
    else:
        due = [(slot, e) for slot, e in todays_posts("strategy") if not done(f"{slot}|track")]
    if check:
        print("DUE" if due else "NONE")
        return True
    m5 = get_m5("XAUUSD")
    for slot, entry in due:
        posted = datetime.fromisoformat(entry["posted_at"]).astimezone(timezone.utc)
        candles = [c for c in m5.candles if c.date >= posted]
        if len(candles) < 3:
            continue
        sims = [simulate(s, candles) for s in entry["meta"]["scenarios"]]
        price = m5.last
        data = {"giá_hiện_tại": round(price, 2), "bài": entry["meta"].get("title"), "kịch_bản": sims}
        try:
            text = llm.generate_json(TRACK_PROMPT, "DỮ LIỆU:\n" + json.dumps(data, ensure_ascii=False, indent=1),
                                     {"type": "object", "properties": {"comment": {"type": "string"}},
                                      "required": ["comment"]})["comment"]
        except Exception as exc:
            print(f"  ! AI lỗi ({exc}) - dùng bản template")
            text = _track_template(price, sims)
        from src.content.fbtext import render as clean
        text = f"{clean(text).rstrip()}\n\n{STRATEGY_DISCLAIMER}"
        path = out_dir() / f"track_{entry['meta']['session']}.png"
        _track_chart([c for c in m5.candles if c.date >= posted - timedelta(hours=3)], sims).convert("RGB").save(path)
        label = "phiên Á – Âu" if entry["meta"]["session"] == "ae" else "phiên Mỹ"
        if publish_comment(entry, text, path, f"Cập nhật lệnh 22:00 – Chiến lược {label}"):
            mark(f"{slot}|track", {"result": [{k: r.get(k) for k in ("side", "filled", "tp_hit", "closed",
                                                                      "floating_pips", "pips_closed")} for r in sims]})
    return True


def check_force_track() -> bool:
    """Chạy tay 'track' thì không chờ tới 22:00."""
    return "track" in sys.argv


def auto(check: bool = False) -> bool:
    """Chạy định kỳ 15 phút/lần: tin đỏ, ví dụ Kiến thức (đủ 30 phút sau khi đăng), cập nhật lệnh (từ 22:00)."""
    if check:
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            for fn in (news, examples, track):
                fn(True)
        print("DUE" if "DUE" in buf.getvalue() else "NONE")
        return True
    ok = True
    for fn in (news, examples, track):
        try:
            ok = fn(False) and ok
        except Exception as exc:
            traceback.print_exc()
            telegram.need_fix(f"❌ Lỗi khi chạy comment theo dõi '{fn.__name__}': {type(exc).__name__}: {exc}")
            ok = False
    return ok


JOBS = {"auto": auto, "examples": examples, "news": news, "track": track}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("job", choices=list(JOBS))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    try:
        sys.exit(0 if JOBS[a.job](a.check) else 1)
    except Exception as exc:
        traceback.print_exc()
        if not a.check:
            telegram.need_fix(f"❌ Lỗi khi chạy comment theo dõi '{a.job}': {type(exc).__name__}: {exc}")
        sys.exit(1)
