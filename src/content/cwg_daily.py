"""Tuyến bài tin tức hằng ngày cho Page thương hiệu (CWG): bản tin đầu ngày, bảng tin xu hướng, phân tích vĩ mô,
tin nóng (săn tin fxtin), bài giấy phép. Số liệu do hệ thống lấy từ dữ liệu thật; AI chỉ viết lời và nhận định.

    JOB=cwg-vn python -m src.content.cwg_daily demo --date 2026-10-02      # dượt đủ bài của 1 ngày
"""
import argparse
import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from src.config import CONFIG, OUTPUT, ROOT, STATE, TZ
from src.content import fbtext
from src.content.llm import generate_json as _llm_json
from src.i18n import LANG_RULE, TZ_LABEL
from src.i18n import t as tr
from src.i18n import day as dlabel

PRODUCTS = [("XAUUSD", 2), ("EURUSD", 5), ("GBPUSD", 5), ("USDJPY", 3), ("AUDUSD", 5), ("USDCAD", 5), ("WTI", 2),
            ("DXY", 3)]
CCYS = {"USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CNY", "CHF"}
BG = ROOT / "assets" / "brands" / "cwg" / "news_bg"
BP = CONFIG.get("brandpost") or {}
FXTIN = "https://www.fxtin.com/page/finance/information"

WRITER = """Bạn là biên tập viên tin tài chính của Page "CWG Markets & Partner" – kênh cập nhật thị trường nhanh cho
đối tác IB lâu năm (họ dùng thông tin để chia sẻ lại cho khách). Giọng chuyên nghiệp, ngắn gọn, đi thẳng vào tác động
lên thị trường.
CAPTION PHẢI THOÁNG, DỄ ĐỌC TRÊN ĐIỆN THOẠI: mỗi đoạn tối đa 1-2 câu, xuống dòng giữa các ý; khi nói nhiều sản phẩm thì
mỗi sản phẩm (hoặc mỗi nhóm nhỏ) một dòng riêng, có emoji đầu dòng; không viết thành một khối chữ dài. Không hô hào, không hứa lợi nhuận, không đưa điểm vào lệnh / SL / TP. Không dùng markdown, không in đậm,
không ghi "18+", không kêu gọi comment. Chỉ dùng số liệu được cung cấp; không tự bịa số.""" + LANG_RULE


# ------------------------------------------------------------------ dữ liệu

def snapshot() -> dict:
    from src.analysis import analyze
    from src.data.prices import get_series
    out = {}
    for code, dg in PRODUCTS:
        try:
            a = analyze(get_series(code), dg)
            a["digits"] = dg
            out[code] = a
        except Exception as exc:
            print(f"  ! {code}: {exc}")
    return out


def zones(a: dict) -> tuple[str, str]:
    """Vùng hỗ trợ / kháng cự từ đỉnh đáy swing; thiếu thì dùng pivot S1/R1 – nới ±0.15 ATR thành vùng."""
    dg, w = a["digits"], a["atr14"] * 0.15
    sup = sorted(a["support"])[-1] if a["support"] else a["s1"]
    res = sorted(a["resistance"])[0] if a["resistance"] else a["r1"]
    f = lambda v: f"{v:,.{dg}f}"
    return f"{f(sup - w)} – {f(sup + w)}", f"{f(res - w)} – {f(res + w)}"


def calendar(day: date) -> list[dict]:
    from src.data.calendar import fetch_week
    out = []
    for e in fetch_week():
        t = datetime.fromisoformat(e["date"]).astimezone(TZ)
        if t.date() == day and e["impact"] in ("High", "Medium") and e["country"] in CCYS:
            out.append({"time": t.strftime("%H:%M"), "ccy": e["country"], "title": e["title"], "impact": e["impact"],
                        "forecast": e.get("forecast", ""), "previous": e.get("previous", "")})
    top = sorted(out, key=lambda e: (e["impact"] != "High", e["time"]))[:8]     # giữ 8 tin quan trọng nhất
    from src.i18n import EN_MODE
    if EN_MODE:                                          # Page Global: hiển thị theo thứ tự thời gian (anh chốt 03/10/2026)
        top.sort(key=lambda e: e["time"])
    return top


def fxtin(day: date, pages: int = 8) -> list[dict]:
    items = []
    for p in range(1, pages + 1):
        r = requests.post(FXTIN, json={"limit": 40, "page": p}, timeout=20, headers={
            "User-Agent": "Mozilla/5.0", "Origin": "https://fxtin.com", "Referer": "https://fxtin.com/"}).json()
        lst = (r.get("data") or {}).get("list") or []
        if not lst:
            break
        time.sleep(1.5)
        for x in lst:
            t = datetime.fromisoformat(x["pub_time_tz"]).replace(tzinfo=ZoneInfo("Asia/Bangkok")).astimezone(TZ)
            if t.date() == day:
                items.append({"time": t.strftime("%H:%M"), "text": x["translate"], "important": x["important"] != "0",
                              "star": int(x["star"] or 0), "actual": x["actual"], "forecast": x["consensus"],
                              "previous": x["previous"]})
        if datetime.fromisoformat(lst[-1]["pub_time_tz"]).date() < day:
            break
    return items


def tiles(snap: dict) -> list[dict]:
    return [{"code": c, "price": a["price"], "digits": a["digits"], "chg": a["change_pct"], "spark": a["spark"]}
            for c, a in snap.items()]


def facts_text(snap: dict) -> str:
    rows = []
    for c, a in snap.items():
        s, r = zones(a)
        rows.append(f"{c}: giá {a['price']}, thay đổi {a['change_pct']:+.2f}%, xu hướng kỹ thuật D1 {a['trend']}, "
                    f"EMA20 {a['ema20']}, RSI {a['rsi14']}, vùng hỗ trợ {s}, vùng kháng cự {r}")
    return "\n".join(rows)


def caption(body: str, tags: list[str]) -> str:
    brand = (CONFIG.get("hashtags") or {}).get("brand") or []
    tags = list(dict.fromkeys(t.replace(" ", "") for t in brand + [t if t.startswith("#") else "#" + t for t in tags]))[:6]
    body = fbtext.render(body).strip()
    if UPPER and body:                                   # dòng tiêu đề đầu caption in hoa
        first, _, rest = body.partition("\n")
        body = first.upper() + ("\n" + rest if rest else "")
    parts = [fbtext.airy(body), BP.get("signature", "").strip(), BP.get("disclaimer", "").strip()]
    return "\n\n".join(p for p in parts if p) + "\n\n" + " ".join(tags)


def slot_label(job: str, default: str, day: date) -> str:
    """Nhãn giờ góc phải ảnh: VN "07:30 · 02/10"; Global (giờ UTC) "06:00 UTC · Oct 02"."""
    from src.i18n import EN_MODE
    tm = (CONFIG["schedule"].get(job) or {}).get("time", default)
    return f"{tm} {TZ_LABEL} · {dlabel(day)}" if EN_MODE else f"{tm} · {dlabel(day)}"


# design.titles_upper (Page Global – anh chốt 03/10/2026): mọi tiêu đề bài viết IN HOA (ảnh + dòng đầu caption)
UPPER = bool((CONFIG.get("design") or {}).get("titles_upper"))
TITLE_KEYS = ("title", "headline", "trend_title", "pairs_title", "gold_note")


def generate_json(system: str, user: str, schema: dict, web: bool = False) -> dict:
    r = _llm_json(system, user, schema, web)
    if UPPER and isinstance(r, dict):
        for k in TITLE_KEYS:
            if isinstance(r.get(k), str):
                r[k] = r[k].upper()
    return r


CAP = {"type": "string"}
TAGS = {"type": "array", "items": {"type": "string"}}


# ------------------------------------------------------------------ từng loại bài

def post_morning(day: date, snap: dict, events: list, folder: Path) -> dict:
    from src.design import cwg_news as cn
    ev = "\n".join(f"{e['time']} {e['ccy']} {e['title']} ({e['impact']}, dự báo {e['forecast'] or '-'}, trước {e['previous'] or '-'})"
                   for e in events) or "Không có tin tác động mạnh."
    r = generate_json(WRITER, f"""Viết BẢN TIN ĐẦU NGÀY {day:%d/%m}.
Dữ liệu 8 sản phẩm (giá & % thay đổi phiên trước):
{facts_text(snap)}
Lịch tin trong ngày ({TZ_LABEL}):
{ev}
Trả về: title (tiêu đề ảnh ≤ 14 từ, nêu trọng tâm ngày), note (1-2 câu, TỐI ĐA 24 từ: điều cần theo dõi nhất hôm nay),
caption (80-140 từ: tóm tắt phiên trước theo nhóm USD/kim loại/dầu, các tin cần chú ý trong ngày theo giờ, xuống dòng thoáng,
emoji đầu dòng vừa phải), hashtags (2-3).""",
                      {"type": "object", "properties": {"title": CAP, "note": CAP, "caption": CAP, "hashtags": TAGS},
                       "required": ["title", "note", "caption", "hashtags"]})
    img = cn.render_morning(folder / "01.png", slot_label("cwg_morning", "07:30", day), r["title"], tiles(snap), events, r["note"])
    return {"slot": "07:30", "name": "Bản tin đầu ngày", "images": [img], "caption": caption(r["caption"], r["hashtags"])}


def post_trend(day: date, snap: dict, events: list, folder: Path) -> dict:
    from src.design import cwg_news as cn
    ev = "; ".join(f"{e['time']} {e['ccy']} {e['title']}" for e in events) or "không có tin lớn"
    r = generate_json(WRITER, f"""Viết BẢNG TIN XU HƯỚNG trong ngày {day:%d/%m} (góc nhìn tổng quan, KHÔNG tín hiệu vào lệnh).
Dữ liệu kỹ thuật (vùng giá do hệ thống tính, giữ nguyên):
{facts_text(snap)}
Tin trong ngày: {ev}
Với mỗi sản phẩm chọn bias up/down/flat dựa trên xu hướng D1, EMA20, RSI và tin trong ngày; reason ≤ 12 từ.
Trả về: title (≤ 12 từ), rows [{{code, bias, reason}}] đủ 8 sản phẩm theo đúng thứ tự trên,
caption (70-120 từ: điểm nhấn của bảng, sản phẩm đáng chú ý nhất và vì sao, nhắc đây là góc nhìn tổng quan), hashtags (2-3).""",
                      {"type": "object", "properties": {
                          "title": CAP, "caption": CAP, "hashtags": TAGS,
                          "rows": {"type": "array", "items": {"type": "object", "properties": {
                              "code": CAP, "bias": {"type": "string", "enum": ["up", "down", "flat"]}, "reason": CAP},
                              "required": ["code", "bias", "reason"]}}},
                       "required": ["title", "rows", "caption", "hashtags"]})
    bias = {x["code"]: x for x in r["rows"]}
    rows = []
    for c, a in snap.items():
        s, rz = zones(a)
        b = bias.get(c, {"bias": "flat", "reason": ""})
        rows.append({"code": c, "bias": b["bias"], "support": s, "resistance": rz, "reason": b["reason"]})
    img = cn.render_trend(folder / "01.png", slot_label("cwg_trend", "08:30", day), r["title"], rows)
    return {"slot": "08:30", "name": "Bảng tin xu hướng", "images": [img], "caption": caption(r["caption"], r["hashtags"])}


def post_license(code: str, idx: int, folder: Path) -> dict:
    from src.design import cwg_news as cn
    lic = next(x for x in BP["licenses_detail"] if x["code"] == code)
    all_l = [(x["code"], x["short"]) for x in BP["licenses_detail"]]
    img = cn.render_license(folder / "01.png", lic, idx, len(all_l), all_l, BP["policy_card"]["score"])
    return {"slot": "09:00", "name": f"Giấy phép {code}", "images": [img], "caption": lic["caption"]}


def post_macro(day: date, snap: dict, folder: Path) -> dict:
    from src.design import cwg_news as cn
    from src.data.prices import get_series
    r = generate_json(WRITER + "\nĐược phép dùng WebSearch để nắm bối cảnh vĩ mô mới nhất (ngân hàng trung ương, lợi suất, dầu, địa chính trị).", f"""
Viết bài PHÂN TÍCH VĨ MÔ ngày {day:%d/%m}: chọn 1 chủ đề vĩ mô đang chi phối thị trường nhất.
Dữ liệu thị trường hiện tại:
{facts_text(snap)}
Trả về: topic, photo (1 trong: fed, gold, oil, japan – ảnh nền hợp chủ đề nhất), title (≤ 12 từ), subtitle (≤ 18 từ),
slides: đúng 3 ảnh {{heading ≤ 8 từ, body 2-3 câu ≤ 60 từ, points 2-3 ý ≤ 10 từ,
compare: 2-3 mã trong [XAUUSD, EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, WTI, DXY] để vẽ biểu đồ so sánh 3 tháng, hoặc []}},
caption (100-160 từ), hashtags (2-3). Mọi con số trong bài phải lấy từ dữ liệu trên hoặc nguồn tin tìm được (ghi rõ thời điểm).""",
                      {"type": "object", "properties": {
                          "topic": CAP, "photo": CAP, "title": CAP, "subtitle": CAP, "caption": CAP, "hashtags": TAGS,
                          "slides": {"type": "array", "items": {"type": "object", "properties": {
                              "heading": CAP, "body": CAP, "points": TAGS, "compare": TAGS},
                              "required": ["heading", "body", "points", "compare"]}}},
                       "required": ["topic", "photo", "title", "subtitle", "slides", "caption", "hashtags"]}, web=True)
    photo = BG / f"{r['photo'] if (BG / (r['photo'] + '-1.jpg')).exists() else 'fed'}-1.jpg"
    imgs = [cn.render_macro_cover(folder / "01.png", photo, slot_label("cwg_macro", "10:00", day), r["title"], r["subtitle"],
                                  [s["heading"] for s in r["slides"]])]
    colors = [(225, 0, 22), (28, 28, 32), (230, 140, 20)]
    for i, s in enumerate(r["slides"][:3], 1):
        chart = None
        codes = [c for c in s.get("compare") or [] if c in dict(PRODUCTS)][:3]
        if len(codes) >= 2:
            ser = {c: [x.close for x in get_series(c).candles[-63:]] for c in codes}
            chart = {"series": ser, "colors": colors, "title": tr("So sánh biến động 3 tháng (%)")}
        imgs.append(cn.render_macro_slide(folder / f"{i + 1:02d}.png", i, 3, s["heading"], s["body"], s["points"], chart))
    return {"slot": "10:00", "name": "Phân tích vĩ mô", "images": imgs, "caption": caption(r["caption"], r["hashtags"])}


def pick_breaking(items: list, n: int = 2, min_score: int = 7) -> list:
    cand = [x for x in items if x["star"] >= 2 or x["important"]]
    lines = "\n".join(f"[{k}] {x['time']} sao={x['star']} {x['text']}"
                      + (f" | thực tế {x['actual']}, dự báo {x['forecast']}, trước {x['previous']}" if x["actual"] not in ("null", "") else "")
                      for k, x in enumerate(cand[:120]))
    r = generate_json(WRITER, f"""Đây là các tin trong ngày từ nguồn tin nhanh. Chấm điểm ảnh hưởng tới thị trường ngoại hối,
vàng, dầu (0-10) và chọn tối đa {n} tin quan trọng nhất (≥ {min_score} điểm), gom các tin cùng sự kiện lại.
{lines}
Trả về picks: [{{ids: [chỉ số tin liên quan], score}}] sắp xếp giảm dần.""",
                      {"type": "object", "properties": {"picks": {"type": "array", "items": {"type": "object", "properties": {
                          "ids": {"type": "array", "items": {"type": "integer"}}, "score": {"type": "number"}},
                          "required": ["ids", "score"]}}}, "required": ["picks"]})
    out = []
    for p in r["picks"][:n]:
        if p["score"] >= min_score:
            out.append([cand[i] for i in p["ids"] if 0 <= i < len(cand)])
    return out


def post_breaking(day: date, group: list, snap: dict, folder: Path) -> dict:
    from src.design import cwg_news as cn
    src = "\n".join(f"{x['time']} {x['text']}" + (f" | thực tế {x['actual']}, dự báo {x['forecast']}, trước {x['previous']}"
                                                   if x["actual"] not in ("null", "") else "") for x in group)
    r = generate_json(WRITER, f"""Viết bài TIN NÓNG từ tin sau (viết lại bằng lời của Page, không chép nguyên văn):
{src}
Bối cảnh giá hiện tại:
{facts_text(snap)}
Trả về: headline (≤ 16 từ, nêu sự kiện + điểm chính), level (RẤT CAO / CAO / TRUNG BÌNH),
data (nếu là tin số liệu: {{actual, forecast, previous – mỗi ô CHỈ con số + đơn vị ≤ 7 ký tự như 29K, 4.2%, 0.1%; better: true nếu tốt hơn dự báo cho đồng tiền đó / false / null}}; tin sự kiện: null),
impacts: 3-4 sản phẩm bị ảnh hưởng {{asset, direction up/down/flat, reason ≤ 9 từ}},
summary (1 câu nhận định ≤ 25 từ), photo (fed/gold/oil/japan), caption (60-110 từ), hashtags (2-3).""",
                      {"type": "object", "properties": {
                          "headline": CAP, "level": CAP, "summary": CAP, "photo": CAP, "caption": CAP, "hashtags": TAGS,
                          "data": {"type": ["object", "null"]},
                          "impacts": {"type": "array", "items": {"type": "object", "properties": {
                              "asset": CAP, "direction": {"type": "string", "enum": ["up", "down", "flat"]}, "reason": CAP},
                              "required": ["asset", "direction", "reason"]}}},
                       "required": ["headline", "level", "impacts", "summary", "photo", "caption", "hashtags"]})
    photo = BG / f"{r['photo'] if (BG / (r['photo'] + '-1.jpg')).exists() else 'fed'}-1.jpg"
    tk = [(c, f"{a['price']:,.{a['digits']}f}", a["change_pct"]) for c, a in snap.items() if c != "DXY"]
    data = r.get("data")
    if data and not all(k in data for k in ("actual", "forecast", "previous")):
        data = None
    if data:                                            # ô số chỉ giữ con số + đơn vị, bỏ chú thích AI lỡ thêm
        import re
        for k in ("actual", "forecast", "previous"):
            m = re.search(r"[-+]?\d[\d.,]*\s?(%|K|M|B|nghìn|triệu)?", str(data[k]))
            data[k] = (m.group(0).replace(" ", "") if m else str(data[k]))[:8]
    t = group[0]["time"]
    img = cn.render_breaking_photo(folder / "01.png", photo, f"{t} · {dlabel(day)}", r["headline"], data,
                                   [(x["asset"], x["direction"], x["reason"]) for x in r["impacts"]], r["summary"],
                                   r["level"], tk)
    return {"slot": t, "name": "Tin nóng", "images": [img], "caption": caption(r["caption"], r["hashtags"])}


# Page Global (anh chốt 03/10/2026): DXY (kèm vàng) + OIL cố định mỗi ngày; 6 đồng EUR/GBP/CAD/AUD/JPY/CHF lên bài
# theo lịch tin: đồng nào có tin ĐỎ thì lên đủ; không có tin đỏ → tối thiểu 2 đồng có tin VÀNG đáng chú ý nhất.
FX_POSTS = {
    "cwg_fx_dxy": {"code": "DXY", "ccy": ["USD"], "kicker": "DXY · IMPACT ON GOLD", "also": "XAUUSD",
                   "brief": "Phân tích chỉ số USD (DXY) và tác động của nó lên vàng XAUUSD (tương quan ngược)."},
    "cwg_fx_oil": {"code": "WTI", "ccy": ["USD", "CAD"], "kicker": "OIL OUTLOOK",
                   "brief": "Phân tích dầu thô WTI (cung cầu, OPEC+, tồn kho, địa chính trị nếu có trong tin)."},
}
CURRENCIES = {   # đồng tiền → (cặp chính, các cặp liên quan)
    "EUR": ("EURUSD", ["EURUSD", "EURGBP", "EURJPY", "EURCHF", "EURAUD"]),
    "GBP": ("GBPUSD", ["GBPUSD", "EURGBP", "GBPJPY", "GBPCHF", "GBPAUD"]),
    "CAD": ("USDCAD", ["USDCAD", "CADJPY", "EURCAD", "GBPCAD", "AUDCAD"]),
    "AUD": ("AUDUSD", ["AUDUSD", "AUDJPY", "EURAUD", "GBPAUD", "AUDCAD"]),
    "JPY": ("USDJPY", ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"]),
    "CHF": ("USDCHF", ["USDCHF", "EURCHF", "GBPCHF", "CHFJPY"]),
}
FX_SLOTS = [f"cwg_fx_{k}" for k in range(1, 7)]       # ô lịch cho các đồng được chọn trong ngày (cách 15')
FX_PICK = STATE / "fx_pick.json"


def fx_pick(day: date) -> list[str]:
    """Đồng tiền lên bài trong ngày – lưu lại để mọi ô lịch dùng chung 1 kết quả.
    Có tin đỏ → đủ các đồng có tin đỏ; không có → 2-3 đồng nhiều tin vàng nhất (thiếu thì lấy đồng biến động mạnh)."""
    cache = json.loads(FX_PICK.read_text(encoding="utf-8")) if FX_PICK.exists() else {}
    if day.isoformat() in cache:
        return cache[day.isoformat()]
    from src.data.calendar import fetch_week
    hi, med = {}, {}
    for e in fetch_week():
        t = datetime.fromisoformat(e["date"]).astimezone(TZ)
        if t.date() != day or e["country"] not in CURRENCIES:
            continue
        if e["impact"] == "High":
            hi.setdefault(e["country"], []).append(e["title"])
        elif e["impact"] == "Medium":
            med.setdefault(e["country"], []).append(e["title"])
    if hi:
        pick = sorted(hi, key=lambda c: -len(hi[c]))
    else:
        pick = sorted(med, key=lambda c: -len(med[c]))[:3]
        if len(pick) < 2:
            from src.analysis import analyze
            from src.data.prices import get_series
            moves = []
            for c, (main, _) in CURRENCIES.items():
                try:
                    moves.append((abs(analyze(get_series(main), 5)["change_pct"]), c))
                except Exception:
                    pass
            for _, c in sorted(moves, reverse=True):
                if len(pick) >= 2:
                    break
                if c not in pick:
                    pick.append(c)
    pick = pick[:len(FX_SLOTS)]
    cache = {k: v for k, v in cache.items() if k >= (day - timedelta(days=7)).isoformat()}
    cache[day.isoformat()] = pick
    FX_PICK.parent.mkdir(parents=True, exist_ok=True)
    FX_PICK.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return pick


def fx_slot_ccy(job: str, day: date) -> str | None:
    """cwg_fx_3 → đồng thứ 3 được chọn hôm nay; None nếu hôm nay ô này trống (bỏ qua)."""
    if job not in FX_SLOTS:
        return None
    pick = fx_pick(day)
    k = int(job.rsplit("_", 1)[1]) - 1
    return pick[k] if k < len(pick) else None


def skip_today(job: str, now: datetime) -> bool:
    return job in FX_SLOTS and fx_slot_ccy(job, now.date()) is None


def macro_after_fx(now: datetime) -> datetime | None:
    """Giờ vĩ mô = bài đồng tiền cuối cùng trong ngày + after_fx phút (Page Global)."""
    cfg = CONFIG["schedule"].get("cwg_macro") or {}
    if not cfg.get("after_fx"):
        return None
    n = len(fx_pick(now.date()))
    last = CONFIG["schedule"].get(FX_SLOTS[n - 1]) if n else None
    last = last or CONFIG["schedule"]["cwg_fx_oil"]
    t = now.replace(hour=int(last["time"][:2]), minute=int(last["time"][3:]), second=0, microsecond=0)
    return t + timedelta(minutes=int(cfg["after_fx"]))


def _chart(code: str):
    from src.chart_tools import build
    ch, _ = build({"mode": "real", "symbol": code, "tf": "H4", "tools": ["structure", "sr_zones", "ema20", "ema50"]})
    return ch.render(width=640, height=400, scale=3)


def post_asset(day: date, job: str, snap: dict, events: list, folder: Path) -> dict:
    from src.design import cwg_news as cn
    cfg = FX_POSTS[job]
    code = cfg["code"]
    slot = (CONFIG["schedule"].get(job) or {}).get("time", "")
    codes = [code] + ([cfg["also"]] if cfg.get("also") else [])
    ev = "\n".join(f"{e['time']} {e['ccy']} {e['title']} ({e['impact']}, dự báo {e['forecast'] or '-'}, trước {e['previous'] or '-'})"
                   for e in events if e["ccy"] in cfg["ccy"]) or "Không có tin tác động mạnh liên quan."
    r = generate_json(WRITER, f"""Viết bài XU HƯỚNG RIÊNG cho {code} ngày {day:%d/%m} – {cfg['brief']}
Góc nhìn tổng quan, KHÔNG tín hiệu vào lệnh, KHÔNG điểm SL/TP. Dữ liệu (vùng giá do hệ thống tính, giữ nguyên):
{facts_text({c: snap[c] for c in codes if c in snap})}
Lịch tin liên quan hôm nay ({TZ_LABEL}):
{ev}
Trả về: title (≤ 12 từ), bias (up/down/flat cho {code}), body (2-3 câu ≤ 45 từ: cấu trúc giá khung H4/D1, động lực chính),
points (3 ý ≤ 10 từ, có nhắc vùng hỗ trợ/kháng cự{' và tác động lên XAUUSD' if cfg.get('also') else ''}),
{'gold_bias (up/down/flat cho XAUUSD), gold_note (tiêu đề ảnh vàng ≤ 10 từ, không ghi số), gold_body (2-3 câu ≤ 45 từ: USD đang tác động lên vàng thế nào), gold_points (3 ý ≤ 10 từ), ' if cfg.get('also') else ''}caption (70-120 từ), hashtags (2-3).""",
                      {"type": "object", "properties": {
                          "title": CAP, "bias": {"type": "string", "enum": ["up", "down", "flat"]}, "body": CAP,
                          "points": TAGS, "caption": CAP, "hashtags": TAGS, "gold_bias": CAP, "gold_note": CAP,
                          "gold_body": CAP, "gold_points": TAGS},
                       "required": ["title", "bias", "body", "points", "caption", "hashtags"]})
    sup, res = zones(snap[code])
    label = slot_label(job, slot, day)
    imgs = [cn.render_asset(folder / "01.png", label, cfg["kicker"], code, r["title"], r["bias"], _chart(code),
                            sup, res, r["body"], r["points"])]
    if cfg.get("also") and cfg["also"] in snap:
        g = cfg["also"]
        gs, gr = zones(snap[g])
        gb = r.get("gold_bias") if r.get("gold_bias") in ("up", "down", "flat") else "flat"
        imgs.append(cn.render_asset(folder / "02.png", label, "XAUUSD · GOLD", g, r.get("gold_note") or "Gold vs the dollar",
                                    gb, _chart(g), gs, gr, r.get("gold_body") or "", r.get("gold_points") or []))
    return {"slot": slot, "name": f"Xu hướng {code}", "images": imgs, "caption": caption(r["caption"], r["hashtags"])}


def _snap_of(codes: list[str], snap: dict) -> dict:
    from src.analysis import analyze
    from src.chart_tools import DIGITS
    from src.data.prices import get_series
    out = {}
    for c in codes:
        if c in snap:
            out[c] = snap[c]
            continue
        try:
            a = analyze(get_series(c), DIGITS.get(c, 5))
            a["digits"] = DIGITS.get(c, 5)
            out[c] = a
        except Exception as exc:
            print(f"  ! {c}: {exc}")
    return out


def post_currency(day: date, job: str, ccy: str, snap: dict, events: list, folder: Path) -> dict:
    """Bài 1 đồng tiền: ảnh 1 cặp chính (biểu đồ H4 thật + vùng giá), ảnh 2 bảng các cặp liên quan."""
    from src.design import cwg_news as cn
    main, pairs = CURRENCIES[ccy]
    data = _snap_of(pairs, snap)
    if main not in data:
        raise RuntimeError(f"Thiếu dữ liệu {main}")
    slot = (CONFIG["schedule"].get(job) or {}).get("time", "")
    ev = "\n".join(f"{e['time']} {e['ccy']} {e['title']} ({'TIN ĐỎ' if e['impact'] == 'High' else 'tin vàng'}, "
                   f"dự báo {e['forecast'] or '-'}, trước {e['previous'] or '-'})"
                   for e in events if e["ccy"] in (ccy, "USD")) or "Không có tin lớn."
    others = ", ".join(p for p in pairs if p != main)
    r = generate_json(WRITER, f"""Viết bài XU HƯỚNG ĐỒNG {ccy} ngày {day:%d/%m}: đồng {ccy} hôm nay có tin đáng chú ý, phân tích
tác động lên cặp chính {main} và các cặp liên quan {others}.
Góc nhìn tổng quan, KHÔNG tín hiệu vào lệnh, KHÔNG điểm SL/TP. Dữ liệu (vùng giá do hệ thống tính, giữ nguyên):
{facts_text(data)}
Lịch tin {ccy} (và USD) hôm nay ({TZ_LABEL}):
{ev}
Trả về: title (≤ 12 từ, nêu tin {ccy} + điểm chính), bias (up/down/flat cho {main}),
body (2-3 câu ≤ 45 từ: tin hôm nay có thể tác động thế nào, cấu trúc giá H4/D1),
points (3 ý ≤ 10 từ, có giờ tin và vùng giá), pairs_title (≤ 10 từ),
rows: mỗi cặp trong {list(data)} {{code, bias up/down/flat, reason ≤ 12 từ}}, caption (80-130 từ), hashtags (2-3).""",
                      {"type": "object", "properties": {
                          "title": CAP, "bias": {"type": "string", "enum": ["up", "down", "flat"]}, "body": CAP,
                          "points": TAGS, "pairs_title": CAP, "caption": CAP, "hashtags": TAGS,
                          "rows": {"type": "array", "items": {"type": "object", "properties": {
                              "code": CAP, "bias": {"type": "string", "enum": ["up", "down", "flat"]}, "reason": CAP},
                              "required": ["code", "bias", "reason"]}}},
                       "required": ["title", "bias", "body", "points", "pairs_title", "rows", "caption", "hashtags"]})
    label = slot_label(job, slot, day)
    sup, res = zones(data[main])
    imgs = [cn.render_asset(folder / "01.png", label, f"{ccy} OUTLOOK", main, r["title"], r["bias"], _chart(main),
                            sup, res, r["body"], r["points"])]
    bias = {x["code"]: x for x in r["rows"]}
    rows = []
    for c, a in data.items():
        s_, rz = zones(a)
        b = bias.get(c, {"bias": "flat", "reason": ""})
        rows.append({"code": c, "bias": b["bias"], "support": s_, "resistance": rz, "reason": b["reason"]})
    imgs.append(cn.render_trend(folder / "02.png", label, r["pairs_title"], rows, kicker=f"{ccy} PAIRS",
                                sub="Related crosses"))
    return {"slot": slot, "name": f"Xu hướng {ccy}", "images": imgs, "caption": caption(r["caption"], r["hashtags"])}


# ------------------------------------------------------------------ chạy theo lịch (runner gọi)

JOB_NAMES = {"cwg_morning": "Bản tin đầu ngày", "cwg_trend": "Bảng tin xu hướng", "cwg_macro": "Phân tích vĩ mô",
             "cwg_license": "Bài giấy phép", "cwg_fx_dxy": "Xu hướng DXY & vàng", "cwg_fx_oil": "Xu hướng dầu",
             **{f"cwg_fx_{k}": f"Xu hướng đồng tiền #{k}" for k in range(1, 7)}}


def license_for_today(now: datetime) -> tuple[str, int]:
    """Giấy phép theo ngày trong lịch (dates thứ 1 → FCA, thứ 2 → FSCA, thứ 3 → VFSC)."""
    dates = (CONFIG["schedule"].get("cwg_license") or {}).get("dates") or []
    codes = [x["code"] for x in BP["licenses_detail"]]
    today = now.strftime("%Y-%m-%d")
    k = dates.index(today) if today in dates else 0
    return codes[min(k, len(codes) - 1)], min(k, len(codes) - 1) + 1


def generate(job: str, out_dir: Path) -> bool:
    now = datetime.now(TZ)
    folder = out_dir / job
    if folder.exists():
        for old in folder.glob("*.png"):
            old.unlink()
    folder.mkdir(parents=True, exist_ok=True)
    if job == "cwg_license":
        code, idx = license_for_today(now)
        p = post_license(code, idx, folder)
    else:
        snap = snapshot()
        if len(snap) < 6:
            raise RuntimeError(f"Thiếu dữ liệu giá ({len(snap)}/8 sản phẩm)")
        if job == "cwg_morning":
            p = post_morning(now.date(), snap, calendar(now.date()), folder)
        elif job == "cwg_trend":
            p = post_trend(now.date(), snap, calendar(now.date()), folder)
        elif job in FX_POSTS:
            p = post_asset(now.date(), job, snap, calendar(now.date()), folder)
        elif job in FX_SLOTS:
            ccy = fx_slot_ccy(job, now.date())
            if not ccy:
                raise RuntimeError("Hôm nay không có đồng tiền cho ô lịch này")
            p = post_currency(now.date(), job, ccy, snap, calendar(now.date()), folder)
        else:
            p = post_macro(now.date(), snap, folder)
    (folder / "caption.txt").write_text(p["caption"], encoding="utf-8")
    (folder / "images.json").write_text(json.dumps([str(i) for i in p["images"]]), encoding="utf-8")
    return True


def files(job: str, out_dir: Path) -> tuple[Path, list[Path]]:
    folder = out_dir / job
    return folder / "caption.txt", [Path(x) for x in json.loads((folder / "images.json").read_text(encoding="utf-8"))]


# ------------------------------------------------------------------ dượt cả ngày

def demo(day: date) -> list[dict]:
    root = OUTPUT / "demo" / day.isoformat()
    snap = snapshot()
    events = calendar(day)
    posts = []

    def run(name, fn):
        f = root / name
        f.mkdir(parents=True, exist_ok=True)
        try:
            p = fn(f)
            (f / "caption.txt").write_text(p["caption"], encoding="utf-8")
            posts.append(p)
            print(f"✓ {p['slot']} {p['name']} – {len(p['images'])} ảnh")
        except Exception as exc:
            import traceback
            traceback.print_exc()
            print(f"✗ {name}: {exc}")

    run("1-morning", lambda f: post_morning(day, snap, events, f))
    run("2-trend", lambda f: post_trend(day, snap, events, f))
    run("3-license", lambda f: post_license("FCA", 1, f))
    run("4-macro", lambda f: post_macro(day, snap, f))
    for k, g in enumerate(pick_breaking(fxtin(day)), 1):
        run(f"5-breaking-{k}", lambda f, g=g: post_breaking(day, g, snap, f))
    (root / "posts.json").write_text(json.dumps([{**p, "images": [str(i) for i in p["images"]]} for p in posts],
                                                ensure_ascii=False, indent=1), encoding="utf-8")
    return posts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["demo"])
    ap.add_argument("--date", default=(datetime.now(TZ) - timedelta(days=1)).date().isoformat())
    a = ap.parse_args()
    demo(date.fromisoformat(a.date))
