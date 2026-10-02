"""Tuyến bài tin tức hằng ngày cho Page thương hiệu (CWG): bản tin đầu ngày, bảng tin xu hướng, phân tích vĩ mô,
tin nóng (săn tin fxtin), bài giấy phép. Số liệu do hệ thống lấy từ dữ liệu thật; AI chỉ viết lời và nhận định.

    JOB=cwg-vn python -m src.content.cwg_daily demo --date 2026-10-02      # dượt đủ bài của 1 ngày
"""
import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from src.config import CONFIG, OUTPUT, ROOT, TZ
from src.content import fbtext
from src.content.llm import generate_json

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
không ghi "18+", không kêu gọi comment. Chỉ dùng số liệu được cung cấp; không tự bịa số."""


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
    return sorted(out, key=lambda e: (e["impact"] != "High", e["time"]))[:8]


def fxtin(day: date, pages: int = 8) -> list[dict]:
    items = []
    for p in range(1, pages + 1):
        r = requests.post(FXTIN, json={"limit": 40, "page": p}, timeout=20, headers={
            "User-Agent": "Mozilla/5.0", "Origin": "https://fxtin.com", "Referer": "https://fxtin.com/"}).json()
        lst = (r.get("data") or {}).get("list") or []
        if not lst:
            break
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
    parts = [fbtext.airy(fbtext.render(body).strip()), BP.get("signature", "").strip(), BP.get("disclaimer", "").strip()]
    return "\n\n".join(p for p in parts if p) + "\n\n" + " ".join(tags)


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
Lịch tin trong ngày (giờ VN):
{ev}
Trả về: title (tiêu đề ảnh ≤ 14 từ, nêu trọng tâm ngày), note (1-2 câu: điều cần theo dõi nhất hôm nay),
caption (80-140 từ: tóm tắt phiên trước theo nhóm USD/kim loại/dầu, các tin cần chú ý trong ngày theo giờ, xuống dòng thoáng,
emoji đầu dòng vừa phải), hashtags (2-3).""",
                      {"type": "object", "properties": {"title": CAP, "note": CAP, "caption": CAP, "hashtags": TAGS},
                       "required": ["title", "note", "caption", "hashtags"]})
    img = cn.render_morning(folder / "01.png", f"07:30 · {day:%d/%m}", r["title"], tiles(snap), events, r["note"])
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
    img = cn.render_trend(folder / "01.png", f"08:30 · {day:%d/%m}", r["title"], rows)
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
    imgs = [cn.render_macro_cover(folder / "01.png", photo, f"10:00 · {day:%d/%m}", r["title"], r["subtitle"],
                                  [s["heading"] for s in r["slides"]])]
    colors = [(225, 0, 22), (28, 28, 32), (230, 140, 20)]
    for i, s in enumerate(r["slides"][:3], 1):
        chart = None
        codes = [c for c in s.get("compare") or [] if c in dict(PRODUCTS)][:3]
        if len(codes) >= 2:
            ser = {c: [x.close for x in get_series(c).candles[-63:]] for c in codes}
            chart = {"series": ser, "colors": colors, "title": "So sánh biến động 3 tháng (%)"}
        imgs.append(cn.render_macro_slide(folder / f"{i + 1:02d}.png", i, 3, s["heading"], s["body"], s["points"], chart))
    return {"slot": "10:00", "name": "Phân tích vĩ mô", "images": imgs, "caption": caption(r["caption"], r["hashtags"])}


def pick_breaking(items: list, n: int = 2) -> list:
    cand = [x for x in items if x["star"] >= 2 or x["important"]]
    lines = "\n".join(f"[{k}] {x['time']} sao={x['star']} {x['text']}"
                      + (f" | thực tế {x['actual']}, dự báo {x['forecast']}, trước {x['previous']}" if x["actual"] not in ("null", "") else "")
                      for k, x in enumerate(cand[:120]))
    r = generate_json(WRITER, f"""Đây là các tin trong ngày từ nguồn tin nhanh. Chấm điểm ảnh hưởng tới thị trường ngoại hối,
vàng, dầu (0-10) và chọn tối đa {n} tin quan trọng nhất (≥ 7 điểm), gom các tin cùng sự kiện lại.
{lines}
Trả về picks: [{{ids: [chỉ số tin liên quan], score}}] sắp xếp giảm dần.""",
                      {"type": "object", "properties": {"picks": {"type": "array", "items": {"type": "object", "properties": {
                          "ids": {"type": "array", "items": {"type": "integer"}}, "score": {"type": "number"}},
                          "required": ["ids", "score"]}}}, "required": ["picks"]})
    out = []
    for p in r["picks"][:n]:
        if p["score"] >= 7:
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
    img = cn.render_breaking_photo(folder / "01.png", photo, f"{t} · {day:%d/%m}", r["headline"], data,
                                   [(x["asset"], x["direction"], x["reason"]) for x in r["impacts"]], r["summary"],
                                   r["level"], tk)
    return {"slot": t, "name": "Tin nóng", "images": [img], "caption": caption(r["caption"], r["hashtags"])}


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
