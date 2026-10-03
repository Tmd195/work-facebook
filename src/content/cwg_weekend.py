"""6 bài cuối tuần cho Page CWG (chạy tự động mỗi tuần):

Thứ 7: 09:00 Tổng kết tuần · 14:00 Top 5 tin của tuần · 20:00 Phân tích khung tuần (biểu đồ TradingView)
Chủ nhật: 10:00 Dòng tiền lớn (COT – CFTC) · 15:00 Chủ đề vĩ mô tuần tới · 20:00 Lịch tin & góc nhìn tuần mới

Số liệu do hệ thống lấy (giá D1, lịch ForexFactory, file COT chính thức của CFTC, tin đã bắt trong tuần);
AI chỉ viết lời + nhận định.

    JOB=cwg-vn python -m src.content.cwg_weekend demo
"""
import argparse
import csv
import io
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from src.config import OUTPUT, STATE, TZ
from src.content.cwg_daily import (BG, CAP, PRODUCTS, TAGS, WRITER, caption, facts_text, fxtin, snapshot, zones)
from src.content.llm import generate_json
from src.i18n import TZ_LABEL, weekday
from src.i18n import t as tr
from src.i18n import day as dlabel

JOB_NAMES = {"cwg_wk_recap": "Tổng kết tuần", "cwg_wk_top5": "Top 5 tin của tuần", "cwg_wk_tech": "Phân tích khung tuần",
             "cwg_wk_cot": "Dòng tiền lớn (COT)", "cwg_wk_macro": "Chủ đề vĩ mô tuần tới",
             "cwg_wk_ahead": "Lịch tin & góc nhìn tuần mới"}
COT_URL = "https://www.cftc.gov/dea/newcot/deafut.txt"
COT_MARKETS = [("099741", "EUR"), ("096742", "GBP"), ("097741", "JPY"), ("232741", "AUD"), ("090741", "CAD"),
               ("098662", "USD Index"), ("088691", tr("Vàng")), ("067651", tr("Dầu WTI"))]
ARCHIVE = STATE / "hunter_archive.json"


def last_week(today: date) -> tuple[date, date]:
    """Thứ 2 → thứ 6 của tuần giao dịch vừa xong (tính từ thứ 7/CN), hoặc tuần hiện tại nếu chạy giữa tuần."""
    monday = today - timedelta(days=today.weekday())
    if today.weekday() < 5:
        monday -= timedelta(days=7)
    return monday, monday + timedelta(days=4)


def week_rows(mon: date, fri: date) -> list[dict]:
    from src.data.prices import get_series
    rows = []
    for code, dg in PRODUCTS:
        try:
            cs = [c for c in get_series(code).candles if mon <= c.date.astimezone(TZ).date() <= fri + timedelta(days=1)]
            cs = [c for c in cs if c.date.astimezone(TZ).weekday() < 6] or cs
            if len(cs) < 2:
                continue
            op, cl = cs[0].open, cs[-1].close
            rows.append({"code": code, "digits": dg, "open": op, "close": cl, "chg": round((cl / op - 1) * 100, 2),
                         "high": max(c.high for c in cs), "low": min(c.low for c in cs)})
        except Exception as exc:
            print(f"  ! {code}: {exc}")
    return rows


def week_news(mon: date, fri: date) -> list[dict]:
    """Tin quan trọng trong tuần: lưu trữ của bộ săn tin; thiếu thì quét lại fxtin."""
    items = []
    if ARCHIVE.exists():
        arch = json.loads(ARCHIVE.read_text(encoding="utf-8"))
        items = [x for x in arch if mon.isoformat() <= x["at"][:10] <= (fri + timedelta(days=1)).isoformat()]
    if len(items) < 15:                                 # kho chưa đủ → quét lùi fxtin 1 lượt tới đầu tuần (~10 trang/ngày)
        from zoneinfo import ZoneInfo
        from src.content.cwg_daily import FXTIN
        items = []
        head = {"User-Agent": "Mozilla/5.0", "Origin": "https://fxtin.com", "Referer": "https://fxtin.com/"}
        import time
        for page in range(1, 90):
            j = requests.post(FXTIN, json={"limit": 40, "page": page}, headers=head, timeout=20).json()
            if j.get("code") != 200:              # bị giới hạn tần suất → nghỉ rồi thử lại trang này
                time.sleep(60)
                j = requests.post(FXTIN, json={"limit": 40, "page": page}, headers=head, timeout=20).json()
            lst = (j.get("data") or {}).get("list") or []
            if not lst:
                break
            time.sleep(3)                         # giãn nhịp, tránh bị nguồn tin chặn
            for x in lst:
                t = datetime.fromisoformat(x["pub_time_tz"]).replace(tzinfo=ZoneInfo("Asia/Bangkok")).astimezone(TZ)
                star, imp = int(x["star"] or 0), x["important"] != "0"
                if mon <= t.date() <= fri + timedelta(days=1) and (star >= 2 or imp):
                    items.append({"day": t.date().isoformat(), "time": t.strftime("%H:%M"), "text": x["translate"],
                                  "star": star, "important": imp, "actual": x["actual"], "forecast": x["consensus"]})
            if datetime.fromisoformat(lst[-1]["pub_time_tz"]).date() < mon:
                break
    return items


def _photo(name: str) -> Path:
    return BG / f"{name if (BG / (name + '-1.jpg')).exists() else 'fed'}-1.jpg"


# ------------------------------------------------------------------ thứ 7

def post_recap(today: date, folder: Path) -> dict:
    from src.design import cwg_news as cn
    mon, fri = last_week(today)
    rows = week_rows(mon, fri)
    data = "\n".join(f"{r['code']}: mở {r['open']:.{r['digits']}f}, đóng {r['close']:.{r['digits']}f}, {r['chg']:+.2f}%, "
                     f"cao nhất {r['high']:.{r['digits']}f}, thấp nhất {r['low']:.{r['digits']}f}" for r in rows)
    r = generate_json(WRITER, f"""Viết bài TỔNG KẾT TUẦN {mon:%d/%m}–{fri:%d/%m}. Dữ liệu cả tuần:
{data}
Trả về: title (≤ 13 từ, nêu bức tranh chung của tuần), highlights (3 ý ≤ 14 từ: sản phẩm/biến động đáng chú ý nhất),
caption (90-140 từ, nhóm USD / kim loại / dầu, mỗi nhóm 1 đoạn ngắn), hashtags (2-3).""",
                      {"type": "object", "properties": {"title": CAP, "highlights": TAGS, "caption": CAP, "hashtags": TAGS},
                       "required": ["title", "highlights", "caption", "hashtags"]})
    img = cn.render_week_recap(folder / "01.png", tr("Tuần {a}–{b}", a=dlabel(mon), b=dlabel(fri)), r["title"], rows, r["highlights"])
    return {"slot": "09:00", "name": JOB_NAMES["cwg_wk_recap"], "images": [img], "caption": caption(r["caption"], r["hashtags"])}


def post_top5(today: date, folder: Path) -> dict:
    from src.design import cwg_news as cn
    mon, fri = last_week(today)
    news = week_news(mon, fri)
    rows = week_rows(mon, fri)
    seen, uniq = set(), []
    for x in sorted(news, key=lambda x: -x["star"]):          # ưu tiên tin nhiều sao, bỏ tin trùng
        key = x["text"][:40]
        if key not in seen:
            seen.add(key)
            uniq.append(x)
    uniq = sorted(uniq[:150], key=lambda x: (x.get("day", x.get("at", "")[:10]), x["time"]))
    lines = "\n".join(f"[{x.get('day', x.get('at', '')[:10])} {x['time']}] sao={x['star']} {x['text'][:160]}"
                      + (f" | thực tế {x['actual']}, dự báo {x['forecast']}" if x.get("actual") not in (None, "null", "") else "")
                      for x in uniq)
    print(f"  tin tuần: {len(news)} → {len(uniq)} tin dùng cho Top 5", flush=True)
    if len(uniq) < 5:
        raise RuntimeError(f"Thiếu tin trong tuần ({len(uniq)}) – nguồn tin có thể đang chặn, thử lại sau")
    moves = ", ".join(f"{r['code']} {r['chg']:+.2f}%" for r in rows)
    r = generate_json(WRITER, f"""Từ các tin trong tuần {mon:%d/%m}–{fri:%d/%m} dưới đây, chọn TOP 5 sự kiện tác động mạnh nhất
tới thị trường NGOẠI HỐI, VÀNG, DẦU, LỢI SUẤT (gom các tin cùng sự kiện), xếp từ mạnh nhất. Chỉ chọn tin vĩ mô/chính sách/địa chính trị/hàng hoá; KHÔNG chọn tin cổ phiếu hay doanh nghiệp riêng lẻ (Tesla, Apple...). Biến động cả tuần: {moves}.
{lines}
Trả về: title (≤ 12 từ), items: 5 mục {{when ("Thứ X · dd/mm"), headline (≤ 14 từ, viết lại bằng lời của Page),
asset (sản phẩm bị ảnh hưởng rõ nhất), direction up/down/flat, impact (≤ 9 từ: phản ứng của thị trường)}},
caption (90-150 từ: 5 sự kiện mỗi sự kiện 1 dòng có số thứ tự emoji, kết bằng 1 câu về điều cần theo dõi tuần tới),
hashtags (2-3). Chỉ dùng thông tin có trong danh sách tin.""",
                      {"type": "object", "properties": {
                          "title": CAP, "caption": CAP, "hashtags": TAGS,
                          "items": {"type": "array", "items": {"type": "object", "properties": {
                              "when": CAP, "headline": CAP, "asset": CAP, "impact": CAP,
                              "direction": {"type": "string", "enum": ["up", "down", "flat"]}},
                              "required": ["when", "headline", "asset", "impact", "direction"]}}},
                       "required": ["title", "items", "caption", "hashtags"]})
    img = cn.render_top5(folder / "01.png", tr("Tuần {a}–{b}", a=dlabel(mon), b=dlabel(fri)), r["title"], r["items"])
    return {"slot": "14:00", "name": JOB_NAMES["cwg_wk_top5"], "images": [img], "caption": caption(r["caption"], r["hashtags"])}


def post_tech(today: date, folder: Path) -> dict:
    from src.chart_tools import build
    from src.design import cwg_news as cn
    mon, fri = last_week(today)
    rows = {r["code"]: r for r in week_rows(mon, fri)}
    snap = snapshot()
    others = [c for c in ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD") if c in rows]
    second = max(others, key=lambda c: abs(rows[c]["chg"])) if others else "EURUSD"
    picks = ["XAUUSD", second]
    info = "\n".join(f"{c}: {facts_text({c: snap[c]})}; cả tuần {rows[c]['chg']:+.2f}%" for c in picks if c in snap and c in rows)
    r = generate_json(WRITER, f"""Viết bài PHÂN TÍCH KHUNG TUẦN cho {picks[0]} và {picks[1]} (góc nhìn cấu trúc xu hướng và vùng giá
cho tuần tới, KHÔNG điểm vào lệnh). Dữ liệu (vùng giá do hệ thống tính, giữ nguyên):
{info}
Trả về: title (≤ 12 từ), subtitle (≤ 18 từ), slides: đúng 2 mục theo thứ tự {picks} {{heading ≤ 8 từ, body 2-3 câu ≤ 55 từ,
points 2-3 ý ≤ 10 từ (có nhắc vùng hỗ trợ/kháng cự)}}, caption (90-140 từ), hashtags (2-3).""",
                      {"type": "object", "properties": {
                          "title": CAP, "subtitle": CAP, "caption": CAP, "hashtags": TAGS,
                          "slides": {"type": "array", "items": {"type": "object", "properties": {
                              "heading": CAP, "body": CAP, "points": TAGS}, "required": ["heading", "body", "points"]}}},
                       "required": ["title", "subtitle", "slides", "caption", "hashtags"]})
    imgs = [cn.render_macro_cover(folder / "01.png", _photo("gold"), tr("Tuần {a}–{b}", a=dlabel(mon), b=dlabel(fri)), r["title"],
                                  r["subtitle"], [s["heading"] for s in r["slides"]], kicker=tr("PHÂN TÍCH KHUNG TUẦN"))]
    for i, (code, s) in enumerate(zip(picks, r["slides"][:2]), 1):
        ch, _ = build({"mode": "real", "symbol": code, "tf": "D1", "tools": ["structure", "sr_zones", "ema20", "ema50"]})
        chart = ch.render(width=640, height=420, scale=3)
        imgs.append(cn.render_chart_slide(folder / f"{i + 1:02d}.png", i, 2, s["heading"], s["body"], chart, s["points"]))
    return {"slot": "20:00", "name": JOB_NAMES["cwg_wk_tech"], "images": imgs, "caption": caption(r["caption"], r["hashtags"])}


# ------------------------------------------------------------------ chủ nhật

def cot_rows() -> tuple[str, list[dict]]:
    r = requests.get(COT_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=40)
    r.raise_for_status()
    by = {}
    for x in csv.reader(io.StringIO(r.text)):
        x = [c.strip() for c in x]
        if len(x) > 40:
            by[x[3]] = x
    rows, rep = [], ""
    for code, name in COT_MARKETS:
        x = by.get(code)
        if not x:
            continue
        rep = x[2]
        lo, sh, dl, ds = int(x[8]), int(x[9]), int(x[38]), int(x[39])
        rows.append({"name": name, "long": lo, "short": sh, "net": lo - sh, "d_net": dl - ds})
    return rep, rows


def post_cot(today: date, folder: Path) -> dict:
    from src.design import cwg_news as cn
    rep, rows = cot_rows()
    data = "\n".join(f"{r['name']}: mua {r['long']:,}, bán {r['short']:,}, ròng {r['net']:+,} HĐ, thay đổi ròng {r['d_net']:+,}"
                     for r in rows)
    r = generate_json(WRITER, f"""Viết bài DÒNG TIỀN LỚN theo báo cáo COT của CFTC (nhóm quỹ đầu cơ non-commercial),
số liệu tính tới {rep}:
{data}
Giải thích ngắn gọn ý nghĩa: quỹ đang nghiêng mua hay bán ở đâu, thay đổi đáng chú ý nhất so với tuần trước.
Trả về: title (≤ 13 từ), note (1 câu ≤ 25 từ: điểm đáng chú ý nhất), caption (90-140 từ, nhắc COT là dữ liệu có độ trễ
vài ngày, dùng để nhìn xu hướng dòng tiền chứ không phải tín hiệu), hashtags (2-3).""",
                      {"type": "object", "properties": {"title": CAP, "note": CAP, "caption": CAP, "hashtags": TAGS},
                       "required": ["title", "note", "caption", "hashtags"]})
    from src.i18n import EN_MODE
    rd = datetime.fromisoformat(rep).strftime("%b %d, %Y" if EN_MODE else "%d/%m/%Y") if rep else ""
    img = cn.render_cot(folder / "01.png", tr("Chủ nhật · {d}", d=dlabel(today)), r["title"], rd, rows, r["note"])
    return {"slot": "10:00", "name": JOB_NAMES["cwg_wk_cot"], "images": [img], "caption": caption(r["caption"], r["hashtags"])}


def week_events(today: date) -> list[dict]:
    """Tin High/Medium của tuần mới (feed ForexFactory 'thisweek' từ Chủ nhật đã là tuần mới)."""
    from src.content.cwg_daily import CCYS
    from src.data.calendar import fetch_week
    out = []
    for e in fetch_week():
        t = datetime.fromisoformat(e["date"]).astimezone(TZ)
        if t.date() > today and e["impact"] in ("High", "Medium") and e["country"] in CCYS:
            out.append({"day": t.date(), "time": t.strftime("%H:%M"), "ccy": e["country"], "title": e["title"],
                        "impact": e["impact"], "forecast": e.get("forecast", "")})
    return sorted(out, key=lambda e: (e["day"], e["time"]))


def post_macro_week(today: date, folder: Path) -> dict:
    from src.design import cwg_news as cn
    evs = week_events(today)
    cal = "\n".join(f"{weekday(e['day'])} {dlabel(e['day'])} {e['time']} {e['ccy']} {e['title']} ({e['impact']}, dự báo {e['forecast'] or '-'})"
                    for e in evs if e["impact"] == "High") or "(lịch tuần mới chưa có – tự tìm trên mạng)"
    snap = snapshot()
    r = generate_json(WRITER + "\nĐược phép dùng WebSearch để nắm bối cảnh.", f"""Viết bài CHỦ ĐỀ VĨ MÔ TUẦN TỚI: chọn sự kiện/chủ đề
lớn nhất tuần mới và phân tích TRƯỚC SỰ KIỆN với kịch bản.
Lịch tin quan trọng tuần mới ({TZ_LABEL}):
{cal}
Thị trường hiện tại:
{facts_text(snap)}
Trả về: photo (fed/gold/oil/japan), title (≤ 12 từ), subtitle (≤ 18 từ), slides đúng 3 mục:
1) bối cảnh: vì sao sự kiện này quan trọng; 2) kịch bản cao hơn dự báo → thị trường phản ứng thế nào;
3) kịch bản thấp hơn dự báo → phản ứng thế nào. Mỗi slide {{heading ≤ 8 từ, body 2-3 câu ≤ 60 từ, points 2-3 ý ≤ 10 từ}}.
caption (100-150 từ), hashtags (2-3).""",
                      {"type": "object", "properties": {
                          "photo": CAP, "title": CAP, "subtitle": CAP, "caption": CAP, "hashtags": TAGS,
                          "slides": {"type": "array", "items": {"type": "object", "properties": {
                              "heading": CAP, "body": CAP, "points": TAGS}, "required": ["heading", "body", "points"]}}},
                       "required": ["photo", "title", "subtitle", "slides", "caption", "hashtags"]}, web=True)
    imgs = [cn.render_macro_cover(folder / "01.png", _photo(r["photo"]), tr("Tuần mới · {d}", d=dlabel(today)), r["title"],
                                  r["subtitle"], [s["heading"] for s in r["slides"]], kicker=tr("CHỦ ĐỀ VĨ MÔ TUẦN TỚI"))]
    for i, s in enumerate(r["slides"][:3], 1):
        imgs.append(cn.render_macro_slide(folder / f"{i + 1:02d}.png", i, 3, s["heading"], s["body"], s["points"], None))
    return {"slot": "15:00", "name": JOB_NAMES["cwg_wk_macro"], "images": imgs, "caption": caption(r["caption"], r["hashtags"])}


def post_ahead(today: date, folder: Path) -> dict:
    from src.design import cwg_news as cn
    evs = week_events(today)
    days = []
    start = today + timedelta(days=(7 - today.weekday()) % 7 or 7) if today.weekday() >= 5 else today
    for k in range(5):
        dd = start + timedelta(days=k)
        dev = sorted([e for e in evs if e["day"] == dd], key=lambda e: (e["impact"] != "High", e["time"]))
        days.append({"label": f"{weekday(dd)} · {dlabel(dd)}", "events": sorted(dev[:3], key=lambda e: e["time"])})
    snap = snapshot()
    cal = "\n".join(f"{d['label']}: " + "; ".join(f"{e['time']} {e['ccy']} {e['title']}" for e in d["events"]) for d in days)
    r = generate_json(WRITER, f"""Viết bài LỊCH TIN & GÓC NHÌN TUẦN MỚI.
Lịch tin chính ({TZ_LABEL}):
{cal}
Dữ liệu kỹ thuật (vùng giá do hệ thống tính, giữ nguyên):
{facts_text(snap)}
Trả về: title (≤ 12 từ, nêu ngày/tin nóng nhất tuần), trend_title (≤ 10 từ), rows: 8 sản phẩm {{code, bias up/down/flat,
reason ≤ 12 từ}} cho cả tuần, caption (110-160 từ: các ngày có tin lớn, mỗi ngày 1 dòng; rồi 2-3 dòng góc nhìn sản phẩm chính;
nhắc là góc nhìn tổng quan), hashtags (2-3).""",
                      {"type": "object", "properties": {
                          "title": CAP, "trend_title": CAP, "caption": CAP, "hashtags": TAGS,
                          "rows": {"type": "array", "items": {"type": "object", "properties": {
                              "code": CAP, "bias": {"type": "string", "enum": ["up", "down", "flat"]}, "reason": CAP},
                              "required": ["code", "bias", "reason"]}}},
                       "required": ["title", "trend_title", "rows", "caption", "hashtags"]})
    imgs = [cn.render_week_ahead(folder / "01.png", tr("Tuần {a}–{b}", a=dlabel(start), b=dlabel(start + timedelta(days=4))), r["title"], days)]
    bias = {x["code"]: x for x in r["rows"]}
    rows = []
    for c, a in snap.items():
        s, rz = zones(a)
        b = bias.get(c, {"bias": "flat", "reason": ""})
        rows.append({"code": c, "bias": b["bias"], "support": s, "resistance": rz, "reason": b["reason"]})
    imgs.append(cn.render_trend(folder / "02.png", tr("Góc nhìn tuần"), r["trend_title"], rows))
    return {"slot": "20:00", "name": JOB_NAMES["cwg_wk_ahead"], "images": imgs, "caption": caption(r["caption"], r["hashtags"])}


FUNCS = {"cwg_wk_recap": post_recap, "cwg_wk_top5": post_top5, "cwg_wk_tech": post_tech,
         "cwg_wk_cot": post_cot, "cwg_wk_macro": post_macro_week, "cwg_wk_ahead": post_ahead}


def generate(job: str, out_dir: Path) -> bool:
    folder = out_dir / job
    if folder.exists():
        for old in folder.glob("*.png"):
            old.unlink()
    folder.mkdir(parents=True, exist_ok=True)
    p = FUNCS[job](datetime.now(TZ).date(), folder)
    (folder / "caption.txt").write_text(p["caption"], encoding="utf-8")
    (folder / "images.json").write_text(json.dumps([str(i) for i in p["images"]]), encoding="utf-8")
    return True


def files(job: str, out_dir: Path) -> tuple[Path, list[Path]]:
    folder = out_dir / job
    return folder / "caption.txt", [Path(x) for x in json.loads((folder / "images.json").read_text(encoding="utf-8"))]


def demo(sat: date, sun: date) -> list[dict]:
    root = OUTPUT / "demo" / f"weekend-{sat.isoformat()}"
    posts = []
    for job, day in [("cwg_wk_recap", sat), ("cwg_wk_top5", sat), ("cwg_wk_tech", sat),
                     ("cwg_wk_cot", sun), ("cwg_wk_macro", sun), ("cwg_wk_ahead", sun)]:
        f = root / job
        f.mkdir(parents=True, exist_ok=True)
        try:
            p = FUNCS[job](day, f)
            p["day"] = day.isoformat()
            (f / "caption.txt").write_text(p["caption"], encoding="utf-8")
            posts.append(p)
            print(f"✓ {day:%a} {p['slot']} {p['name']} – {len(p['images'])} ảnh", flush=True)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            print(f"✗ {job}: {exc}", flush=True)
    (root / "posts.json").write_text(json.dumps([{**p, "images": [str(i) for i in p["images"]]} for p in posts],
                                                ensure_ascii=False, indent=1), encoding="utf-8")
    return posts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["demo"])
    a = ap.parse_args()
    today = datetime.now(TZ).date()
    sat = today - timedelta(days=(today.weekday() - 5) % 7)
    demo(sat, sat + timedelta(days=1))
