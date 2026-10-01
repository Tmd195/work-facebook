"""Bài Chủ nhật 22:00 - Tổng quan tuần mới: lịch tin quan trọng cả tuần + xu hướng DXY / XAUUSD / EURUSD / GBPUSD."""
import json
from datetime import datetime, timedelta

from src.analysis import analyze
from src.chart_tools import ema, load, rsi
from src.config import CONFIG, SYMBOLS, TZ
from src.content import llm
from src.content.morning import find_unverified_numbers
from src.data.calendar import fetch_week
from src.data.prices import get_series

ORDER = ["DXY", "XAUUSD", "EURUSD", "GBPUSD"]
WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
DISCLAIMER = ("⚠️ Đây là góc nhìn cá nhân của Thái, không phải 1 lời khuyên đầu tư. Hãy tự chịu trách nhiệm "
              "với mọi quyết định của bản thân tại thời điểm hiện tại cũng như tương lai.")

SYSTEM_PROMPT = """Bạn là chuyên viên phân tích forex & vàng của Facebook Page cho trader Việt Nam (xưng "anh em").
Viết bài "TỔNG QUAN TUẦN MỚI" đăng tối Chủ nhật, dựa trên DỮ LIỆU (giá thật, xu hướng D1/tuần, lịch tin cả tuần).

BƯỚC 1: dùng WebSearch tìm tin vĩ mô cuối tuần qua & chủ đề chính tuần tới (Fed/ECB/BoE, lạm phát, việc làm, địa chính trị...),
chỉ dùng nguồn uy tín, ghi URL vào sources.
BƯỚC 2: viết bài 450-650 từ, không markdown (**, #), emoji vừa phải làm tiêu đề mục:
1. "🗓 TỔNG QUAN TUẦN MỚI <khoảng ngày>" + 1-2 câu chủ đề chính của tuần.
2. 🌍 Tuần qua thị trường đã làm gì (USD, vàng) và vì sao.
3. 📅 Lịch tin đáng chú ý theo từng ngày (giờ VN): chỉ tin quan trọng, nói tin đó ảnh hưởng gì.
4. 📊 Góc nhìn xu hướng lần lượt DXY, XAUUSD, EURUSD, GBPUSD: tuần qua tăng/giảm bao nhiêu %, xu hướng D1,
   vùng kháng cự/hỗ trợ quan trọng, thiên hướng tuần mới (tăng / giảm / đi ngang) và điều kiện thay đổi thiên hướng.
5. ⚠️ Lưu ý quản lý rủi ro cho tuần (ngày nhiều tin, khoảng trống giá đầu tuần...).
6. Câu hỏi mở cho anh em.
QUY TẮC SỐ: mọi mức giá / % phải lấy từ DỮ LIỆU, không tự tạo. Giá dùng dấu chấm thập phân.
QUY TẮC SỰ KIỆN: chỉ nói một tin "đã ra" khi nguồn tin xác nhận rõ ngày công bố và kết quả; tin chưa diễn ra thì nói là sắp diễn ra.
Mục lịch tin dùng "calendar" trong DỮ LIỆU; nếu calendar trống thì ghi rõ "lịch chính thức chưa cập nhật" và chỉ nhắc sự kiện
đã được nguồn uy tín xác nhận ngày giờ (kèm giờ VN).
KHÔNG tự viết dòng miễn trừ trách nhiệm và hashtag.
Các trường ảnh: title ≤ 70 ký tự (chủ đề tuần); outlook: với mỗi mã {symbol, bias (tăng|giảm|đi ngang), note ≤ 260 ký tự
gồm xu hướng + vùng giá chính + điều kiện}."""

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "post": {"type": "string"},
        "outlook": {"type": "array", "items": {"type": "object", "properties": {
            "symbol": {"type": "string"}, "bias": {"type": "string", "enum": ["tăng", "giảm", "đi ngang"]},
            "note": {"type": "string"}}, "required": ["symbol", "bias", "note"]}},
        "sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "post", "outlook", "sources"],
}


def week_range(now: datetime) -> tuple[datetime, datetime]:
    monday = (now + timedelta(days=(7 - now.weekday()) % 7 or 7)).replace(hour=0, minute=0, second=0, microsecond=0)
    if now.weekday() == 0:                                   # chạy thử vào thứ Hai → tuần hiện tại
        monday = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return monday, monday + timedelta(days=5)


def week_events(now: datetime) -> list[dict]:
    start, end = week_range(now)
    cfg = CONFIG["calendar"]
    out = []
    feed = fetch_week("thisweek")   # tuần ForexFactory bắt đầu từ Chủ nhật → 22:00 Chủ nhật đã là lịch tuần mới
    seen = set()
    for e in feed:
        key = (e.get("date"), e.get("title"), e.get("country"))
        if key in seen:
            continue
        seen.add(key)
        if e.get("country") not in cfg["currencies"] or e.get("impact") != "High":
            continue
        try:
            when = datetime.fromisoformat(e["date"]).astimezone(TZ)
        except (KeyError, ValueError):
            continue
        if start - timedelta(hours=8) <= when < end + timedelta(hours=8):
            out.append({"day": f"{WEEKDAYS[when.weekday()]} {when:%d/%m}", "time": f"{when:%H:%M}",
                        "datetime": when.isoformat(), "currency": e["country"], "title": e["title"],
                        "forecast": e.get("forecast") or "", "previous": e.get("previous") or ""})
    return sorted(out, key=lambda x: x["datetime"])


def weekly_stats(code: str, digits: int) -> dict:
    d1 = list(load(code, "D1"))
    closes = [c.close for c in d1]
    # tuần trước = 5 phiên gần nhất
    wk = d1[-5:]
    prev_close = d1[-6].close
    a = analyze(get_series(code), digits)
    rnd = lambda x: round(x, digits)
    return {
        "giá_đóng_cửa_tuần": rnd(closes[-1]),
        "thay_đổi_tuần_%": round((closes[-1] - prev_close) / prev_close * 100, 2),
        "đỉnh_tuần": rnd(max(c.high for c in wk)), "đáy_tuần": rnd(min(c.low for c in wk)),
        "EMA20_D1": rnd(ema(closes, 20)[-1]), "EMA50_D1": rnd(ema(closes, 50)[-1]),
        "EMA200_D1": rnd(ema(closes, 200)[-1]), "RSI14_D1": round(rsi(closes)[-1], 1),
        "xu_hướng_D1": a["trend"], "kháng_cự": a["resistance"], "hỗ_trợ": a["support"],
        "pivot_tuần": rnd((max(c.high for c in wk) + min(c.low for c in wk) + closes[-1]) / 3),
    }


def build_context(now: datetime) -> dict:
    start, end = week_range(now)
    digits = {s["code"]: s["digits"] for s in SYMBOLS}
    return {
        "tuần": f"{start:%d/%m} – {end - timedelta(days=1):%d/%m/%Y}",
        "markets": {code: weekly_stats(code, digits[code]) for code in ORDER},
        "calendar": week_events(now),
    }


def generate(context: dict) -> dict | None:
    if not llm.available():
        print("  ! Chưa cấu hình AI - bỏ qua bài tổng quan tuần")
        return None
    user = "DỮ LIỆU:\n" + json.dumps(context, ensure_ascii=False, indent=1)
    for attempt in range(2):
        try:
            res = llm.generate_json(SYSTEM_PROMPT, user, SCHEMA, web=True)
        except (llm.LLMError, json.JSONDecodeError) as exc:
            print(f"  ! AI lỗi: {exc}")
            return None
        bad = find_unverified_numbers(res["post"], {"markets": context["markets"], "calendar": context["calendar"]})
        if not bad:
            return {**res, "writer": "ai"}
        print(f"  ! Lần {attempt + 1}: số không có trong dữ liệu: {', '.join(bad[:8])}")
        user += f"\n\nBản trước bị từ chối vì các số không có trong dữ liệu: {', '.join(bad)}. Chỉ dùng số trong DỮ LIỆU."
    return None


def finalize(post: str) -> str:
    from src.content.fbtext import render
    from src.content import hashtags
    return f"{render(post).rstrip()}\n\n{DISCLAIMER}\n\n{hashtags.weekly()}"
