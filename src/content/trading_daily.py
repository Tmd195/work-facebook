"""Bài tin tức Page DecodeFx Trading – form "Tạp chí kinh doanh" (mẫu 12).

post_bulletin: BẢN TIN 06:00 – tin chính qua đêm + tác động lên Vàng / Dầu / EU / GU + lịch tin trong ngày.
Nguồn dữ liệu dùng chung hệ thống (giá thật, lịch ForexFactory, tin fxtin); AI chỉ viết từ dữ liệu được đưa vào.

    JOB=decode-trading python -m src.content.trading_daily bulletin
"""
import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from src.config import OUTPUT, TZ
from src.content import cwg_daily as cd
from src.content.llm import generate_json   # giữ chữ thường như mẫu duyệt (không IN HOA tiêu đề)
from src.design import daily_editorial as ed

FOUR = [("XAUUSD", "Vàng"), ("WTI", "Dầu"), ("EURUSD", "EU"), ("GBPUSD", "GU")]
WEEKDAY = ["THỨ HAI", "THỨ BA", "THỨ TƯ", "THỨ NĂM", "THỨ SÁU", "THỨ BẢY", "CHỦ NHẬT"]
WRITER = """Bạn là biên tập viên bản tin thị trường của Page "DecodeFx Trading" – kênh hỗ trợ nhà đầu tư Việt Nam
(vàng, dầu, EURUSD, GBPUSD). Văn phong báo kinh doanh: ngắn, chính xác, có trọng tâm, không giật gân.
CHỈ dùng dữ kiện trong dữ liệu được cung cấp; không bịa số, không bịa sự kiện, không dự đoán chắc chắn.
Không khuyến nghị mua/bán. Viết tiếng Việt có dấu, tên riêng giữ chuẩn (Fed, FOMC, ECB, BoE, CPI…)."""
OBJ, CAP = "object", {"type": "string"}


def post_bulletin(day: date, folder: Path) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    snap = {c: a for c, a in cd.snapshot().items() if c in dict(FOUR)}
    events = cd.calendar(day)
    news = []
    for d, since in ((day - timedelta(days=1), "17:00"), (day, "00:00")):   # tin qua đêm từ 17:00 hôm trước + sáng nay
        try:
            news += [x for x in reversed(cd.fxtin(d, pages=6)) if x["time"] >= since]   # fxtin trả mới → cũ
        except Exception as exc:
            print("! fxtin", exc)
    # ưu tiên tin quan trọng / có sao, rồi tới tin còn lại – tối đa 70 dòng cho AI chọn
    news = sorted(news, key=lambda x: (not (x["important"] or x["star"] >= 2)))[:70]
    facts = "\n".join(f"{name} ({c}): giá {snap[c]['price']:,.{snap[c]['digits']}f}, phiên trước {snap[c]['change_pct']:+.2f}%"
                      for c, name in FOUR if c in snap)
    ev = "\n".join(f"{e['time']} {e['ccy']} {e['title']} ({e['impact']})" for e in events) or "Không có tin tác động mạnh."
    nw = "\n".join(f"{x['time']} {x['text']}" for x in news) or "Không có tin nổi bật."
    imp = {"type": OBJ, "properties": {"asset": CAP, "direction": {"type": "string", "enum": ["up", "down", "flat"]},
                                       "note": CAP}, "required": ["asset", "direction", "note"]}
    r = generate_json(WRITER, f"""Viết BẢN TIN 06:00 ngày {day:%d/%m/%Y}.
Giá & thay đổi phiên trước:
{facts}
Tin tức qua đêm (giờ VN):
{nw}
Lịch tin hôm nay (giờ VN):
{ev}
Trả về JSON:
- title: tiêu đề tạp chí 6–11 từ, viết hoa chữ đầu câu, nêu trọng tâm của ngày (có thể nhắc tài sản + sự kiện).
- lead: 1 câu dẫn ≤ 22 từ, giọng biên tập.
- news: đúng 3 tin chính, mỗi tin ≤ 14 từ, lấy từ dữ liệu tin/lịch ở trên.
- impacts: đúng 4 mục theo thứ tự Vàng, Dầu, EU, GU – direction (up/down/flat theo dữ liệu & tin), note ≤ 8 từ nêu lý do.
- calendar: tối đa 3 tin quan trọng nhất của lịch hôm nay, mỗi tin {{time, title}} – title dịch sang tiếng Việt ≤ 7 từ
  (vd. "Biên bản họp FOMC", "Thống đốc BoE Bailey phát biểu").
- photo: 1 chủ đề ảnh hợp tin chính nhất trong {ed.TOPICS}.
- caption: 90–150 từ, thoáng, xuống dòng giữa các ý, emoji đầu dòng vừa phải; cuối có 1 dòng "Theo dõi DecodeFx Trading
  để nhận bản tin mỗi sáng."
- hashtags: 2–3.""",
                           {"type": OBJ, "properties": {"title": CAP, "lead": CAP, "news": {"type": "array", "items": CAP},
                                                        "impacts": {"type": "array", "items": imp}, "photo": CAP,
                                                        "calendar": {"type": "array", "items": {"type": OBJ, "properties": {
                                                            "time": CAP, "title": CAP}, "required": ["time", "title"]}},
                                                        "caption": CAP, "hashtags": {"type": "array", "items": CAP}},
                            "required": ["title", "lead", "news", "impacts", "calendar", "photo", "caption", "hashtags"]})
    photo = ed.photo_for(r["photo"], day.toordinal())
    img = ed.render(folder / "01.png", kicker=f"{WEEKDAY[day.weekday()]} · {day:%d.%m.%Y}", title=r["title"],
                    lead=r["lead"], news=r["news"][:3], impacts=r["impacts"][:4],
                    events=r.get("calendar", [])[:3],
                    photo=photo, badge="BẢN TIN 06:00")
    out = {"slot": "06:00", "name": "Bản tin 06:00", "images": [img], "caption": cd.caption(r["caption"], r["hashtags"]),
           "photo": photo.name, "raw": r}
    (folder / "bulletin.json").write_text(json.dumps({k: (str(v) if isinstance(v, Path) else v) for k, v in out.items()
                                                     if k != "images"}, ensure_ascii=False, indent=1), encoding="utf-8")
    (folder / "caption.txt").write_text(out["caption"], encoding="utf-8")
    return out


def post_breaking(day: date, group: list, snap: dict, folder: Path) -> dict:
    """TIN NÓNG (bộ săn tin gọi khi Page dùng hunter.style: editorial) – khuôn mẫu 12, nhãn đỏ TIN NÓNG."""
    folder.mkdir(parents=True, exist_ok=True)
    src = "\n".join(f"{x['time']} {x['text']}" + (f" | thực tế {x['actual']}, dự báo {x['forecast']}, trước {x['previous']}"
                                                  if x.get("actual") not in (None, "null", "") else "") for x in group)
    facts = "\n".join(f"{name} ({c}): {snap[c]['price']:,.{snap[c]['digits']}f} ({snap[c]['change_pct']:+.2f}%)"
                      for c, name in FOUR if c in snap)
    imp = {"type": OBJ, "properties": {"asset": CAP, "direction": {"type": "string", "enum": ["up", "down", "flat"]},
                                       "note": CAP}, "required": ["asset", "direction", "note"]}
    r = generate_json(WRITER, f"""Viết bài TIN NÓNG từ tin sau (viết lại bằng lời của Page, không chép nguyên văn):
{src}
Giá hiện tại: {facts}
QUY TẮC SỐ LIỆU: points chỉ dùng số trong TIN; impacts chỉ dùng hướng đi + lý do, KHÔNG nhắc lại % hay giá
(tránh 2 nguồn lệch nhau gây mâu thuẫn). Không viết cùng một chỉ số với 2 con số khác nhau.
Trả về JSON: title (tiêu đề tạp chí 6–12 từ, chữ thường viết hoa đầu câu, nêu sự kiện + điểm chính),
lead (1 câu nhận định ≤ 22 từ), points (2–3 ý chính, mỗi ý ≤ 14 từ; tin số liệu thì có 1 ý "Thực tế … · dự báo … · kỳ trước …"),
impacts (đúng 4 mục Vàng, Dầu, EU, GU – direction up/down/flat theo tin, note ≤ 8 từ),
photo (1 chủ đề trong {ed.TOPICS}), caption (60–110 từ, thoáng, emoji đầu dòng vừa phải), hashtags (2–3).""",
                      {"type": OBJ, "properties": {"title": CAP, "lead": CAP, "points": {"type": "array", "items": CAP},
                                                   "impacts": {"type": "array", "items": imp}, "photo": CAP,
                                                   "caption": CAP, "hashtags": {"type": "array", "items": CAP}},
                       "required": ["title", "lead", "points", "impacts", "photo", "caption", "hashtags"]})
    t = group[0]["time"]
    photo = ed.photo_for(r["photo"], day.toordinal() + len(t))
    img = ed.render(folder / "01.png", kicker=f"TIN NÓNG · {t} · {day:%d.%m.%Y}", title=r["title"], lead=r["lead"],
                    news=r["points"][:3], impacts=r["impacts"][:4], events=[], photo=photo, badge=f"TIN NÓNG {t}")
    return {"slot": t, "name": "Tin nóng", "images": [img], "caption": cd.caption(r["caption"], r["hashtags"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["bulletin", "breaking"])
    ap.add_argument("--day")
    a = ap.parse_args()
    day = date.fromisoformat(a.day) if a.day else datetime.now(TZ).date()
    if a.kind == "breaking":                              # thử: lấy tin quan trọng nhất hôm nay
        items = cd.fxtin(day, pages=4)
        g = cd.pick_breaking(items, n=1, min_score=0) or [[items[0]]]
        snap = {c: x for c, x in cd.snapshot().items() if c in dict(FOUR)}
        r = post_breaking(day, g[0], snap, OUTPUT / day.isoformat() / "breaking")
        print(r["images"][0]); print(r["caption"]); return
    r = post_bulletin(day, OUTPUT / day.isoformat() / "bulletin")
    print(r["images"][0], r["photo"])
    print(r["caption"])


if __name__ == "__main__":
    main()


# ------------------------------------------------------------------ bộ chạy bài (runner gọi các hàm dưới với job "td_…")
# td_bulletin – bản tin 06:00 · td_album / td_album_wk1 / td_album_wk2 – album kiến thức (form Sổ tay)
ALBUMS = ["ob"]                                     # chủ đề album đã có khuôn – thêm dần (supply, fvg, …)
ALBUM_STATE = None


def _album_state_file():
    from src.config import STATE
    return STATE / "albums.json"


def _albums_done() -> list:
    try:
        return json.loads(_album_state_file().read_text(encoding="utf-8"))["done"]
    except Exception:
        return []


def next_album():
    done = _albums_done()
    return next((a for a in ALBUMS if a not in done), None)


def skip_today(job: str, now) -> bool:
    return job.startswith("td_album") and next_album() is None   # hết chủ đề album chưa đăng → bỏ ô lịch


def _album_caption(topic: str, s) -> str:
    if topic == "ob":
        body = ("ORDER BLOCK – SỔ TAY THỰC CHIẾN\n"
                "Lưu lại 7 trang này trước khi vào lệnh tiếp theo:\n"
                "📒 Order Block là gì\n✏️ Cách vẽ OB đúng\n🔍 OB hợp lệ phải có FVG\n🎯 Cách vào lệnh – SL – TP\n"
                "✅ Checklist 6 điều kiện\n📈 Ví dụ thật trên vàng M15\n"
                "Bạn muốn sổ tay hệ thống nào tiếp theo? Comment để DecodeFx Trading làm cho bạn.")
        return cd.caption(body, ["SMC", "OrderBlock", "XAUUSD"])
    raise ValueError(topic)


def generate(job: str, out_dir: Path) -> bool:
    if job == "td_bulletin":
        post_bulletin(datetime.now(TZ).date(), out_dir / job)
        return True
    if job.startswith("td_album"):
        topic = next_album()
        if topic is None:
            raise RuntimeError("Hết chủ đề album kiến thức chưa đăng")
        from src.design import edu_album
        from src.reels.smc.setup import find
        f = out_dir / job
        if topic == "ob":
            obs = [x for x in find(system="ob") if x.symbol == "XAUUSD"] or find(system="ob")
            s = obs[0]
            edu_album.build(f, s)
        (f / "caption.txt").write_text(_album_caption(topic, s), encoding="utf-8")
        (f / "meta.json").write_text(json.dumps({"album": topic}, ensure_ascii=False), encoding="utf-8")
        return True
    raise ValueError(job)


def files(job: str, out_dir: Path):
    f = out_dir / job
    if job == "td_bulletin":
        return f / "caption.txt", [f / "01.png"]
    return f / "caption.txt", sorted(f.glob("[0-9][0-9].png"))


def meta(job: str, out_dir: Path) -> dict:
    p = out_dir / job / "meta.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def mark_done(job: str, meta: dict):
    if job.startswith("td_album") and meta.get("album"):
        done = _albums_done() + [meta["album"]]
        _album_state_file().write_text(json.dumps({"done": done}, ensure_ascii=False), encoding="utf-8")


JOB_NAMES = {"td_bulletin": "Bản tin 06:00", "td_album": "Album kiến thức", "td_album_wk1": "Album kiến thức",
             "td_album_wk2": "Album kiến thức"}
