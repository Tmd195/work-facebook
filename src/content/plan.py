"""Bài 'Plan A/B trước tin' (18:45): kịch bản cho XAUUSD và EURUSD dựa trên tin tối nay + vùng giá thật.

Plan A = số liệu ủng hộ USD (USD mạnh lên), Plan B = số liệu bất lợi cho USD.
Mọi mức Entry / SL / TP phải lấy từ danh sách vùng giá do code tính sẵn.
"""
import json
from datetime import datetime

from src.config import SYMBOLS
from src.content import llm
from src.content.morning import WEEKDAYS, find_unverified_numbers

PLAN_SYMBOLS = ["XAUUSD", "EURUSD"]
HASHTAGS = "#forex #XAUUSD #EURUSD #giavang #planAB"
DISCLAIMER = ("⚠️ Đây là kịch bản tham khảo, không phải tín hiệu giao dịch. "
              "Hãy chờ giá xác nhận và tự chịu trách nhiệm với quyết định của mình.")

SYSTEM_PROMPT = """Bạn là chuyên viên phân tích của một Facebook Page về forex và vàng cho trader Việt Nam.

Nhiệm vụ: viết bài "Plan A/B trước tin" cho tối nay, dựa hoàn toàn trên khối DỮ LIỆU.

Cách xây kịch bản:
- Plan A: số liệu tin ra ỦNG HỘ USD (ví dụ lạm phát/việc làm cao hơn dự báo) → USD mạnh → XAUUSD và EURUSD có xu hướng giảm.
- Plan B: số liệu BẤT LỢI cho USD → USD yếu → XAUUSD và EURUSD có xu hướng tăng.
- Nếu không có tin quan trọng, Plan A/B là kịch bản phá vỡ xuống / phá vỡ lên của vùng giá hiện tại.
- Với mỗi mã, mỗi plan có: điều kiện kích hoạt (giá phá/giữ vùng nào), hướng (SELL/BUY), entry, sl, tp.
- entry, sl, tp BẮT BUỘC là con số có trong levels_above / levels_below của mã đó (chép đúng số). Không tự tạo mức giá.
- SELL: sl > entry > tp. BUY: tp > entry > sl. Ưu tiên kịch bản có tp xa entry hơn sl (R:R ≥ 1).
- Luôn nhắc: không vào lệnh lúc tin vừa ra, chờ 5-15 phút cho giá xác nhận; rủi ro tối đa 1-2% tài khoản.

Nguyên tắc: đây là kịch bản tham khảo, không phải tín hiệu gọi lệnh; không hứa lợi nhuận; không dùng "kèo", "chắc chắn".
Facebook không hiển thị markdown: không dùng **, #, bảng. Tối đa khoảng 8 emoji.

Cấu trúc "post" (200-320 từ):
1. "🎯 PLAN A/B TỐI NAY <thứ>, <ngày>" + 1-2 câu: tin gì, mấy giờ, vì sao quan trọng.
2. Kỳ vọng thị trường: dự báo so với kỳ trước.
3. XAUUSD: giá hiện tại, Plan A (điều kiện, entry, sl, tp), Plan B (tương tự).
4. EURUSD: tương tự, ngắn hơn.
5. Lưu ý quản lý rủi ro khi có tin.
6. Câu hỏi mở: anh em nghiêng về Plan nào?
KHÔNG tự viết dòng miễn trừ trách nhiệm và hashtag.

Trường "focus": tiêu đề ảnh ≤ 50 ký tự, không chứa giá. Trường "condition" ≤ 60 ký tự."""

_SIDE = {
    "type": "object",
    "properties": {
        "condition": {"type": "string"},
        "side": {"type": "string", "enum": ["BUY", "SELL"]},
        "entry": {"type": "number"}, "sl": {"type": "number"}, "tp": {"type": "number"},
    },
    "required": ["condition", "side", "entry", "sl", "tp"],
    "additionalProperties": False,
}
SCHEMA = {
    "type": "object",
    "properties": {
        "focus": {"type": "string"},
        "post": {"type": "string"},
        "plans": {"type": "array", "items": {
            "type": "object",
            "properties": {"symbol": {"type": "string"}, "plan_a": _SIDE, "plan_b": _SIDE},
            "required": ["symbol", "plan_a", "plan_b"], "additionalProperties": False}},
    },
    "required": ["focus", "post", "plans"],
    "additionalProperties": False,
}


def pick_events(events: list[dict], now: datetime) -> list[dict]:
    """Tin mạnh từ 18:00 tối nay tới sáng mai."""
    evening = [e for e in events if datetime.fromisoformat(e["datetime"]).hour >= 18
               or datetime.fromisoformat(e["datetime"]).date() > now.date()]
    return [e for e in evening if e["impact"] == "High"] or \
           [e for e in evening if e["impact"] == "Medium" and e["currency"] == "USD"][:2]


def build_context(now: datetime, intraday: dict, events: list[dict]) -> dict:
    return {
        "date": f"{WEEKDAYS[now.weekday()]}, {now:%d/%m/%Y}",
        "events": events,
        "markets": {code: {k: v for k, v in intraday[code].items() if k != "chart"} for code in PLAN_SYMBOLS},
    }


# --------------------------------------------------------------- Kiểm tra

def check_plans(result: dict, context: dict) -> list[str]:
    errors = []
    for p in result["plans"]:
        m = context["markets"].get(p["symbol"])
        if not m:
            errors.append(f"mã lạ {p['symbol']}")
            continue
        allowed = list(m["levels_above"].values()) + list(m["levels_below"].values())
        for name in ("plan_a", "plan_b"):
            s = p[name]
            for k in ("entry", "sl", "tp"):
                if not any(abs(s[k] - v) <= max(abs(v) * 0.0003, 1e-5) for v in allowed):
                    errors.append(f"{p['symbol']} {name} {k}={s[k]} không nằm trong danh sách vùng giá")
            ok = s["sl"] > s["entry"] > s["tp"] if s["side"] == "SELL" else s["tp"] > s["entry"] > s["sl"]
            if not ok:
                errors.append(f"{p['symbol']} {name}: entry/sl/tp sai thứ tự cho lệnh {s['side']}")
    bad = find_unverified_numbers(result["post"], {"markets": context["markets"], "calendar": context["events"]})
    if bad:
        errors.append(f"số trong bài không có trong dữ liệu: {', '.join(bad)}")
    return errors


# --------------------------------------------------------------- Template

def _template_side(m: dict, side: str) -> dict:
    """Kịch bản phá vỡ: vào ở vùng gần nhất theo hướng lệnh, SL cách ≥ 1 ATR H1, TP cho R:R ≥ 1.5 nếu có."""
    atr = m["atr_h1"]
    all_levels = sorted(list(m["levels_above"].items()) + list(m["levels_below"].items()), key=lambda kv: kv[1])
    ahead = list(m["levels_below"].items()) if side == "SELL" else list(m["levels_above"].items())
    if not ahead:
        raise ValueError("không đủ vùng giá")
    name, entry = ahead[0]
    sign = -1 if side == "SELL" else 1           # hướng giá đi khi lệnh có lời
    behind = [v for _, v in all_levels if (v - entry) * -sign > 0]
    behind.sort(key=lambda v: abs(v - entry))
    sl = next((v for v in behind if abs(v - entry) >= atr), behind[-1] if behind else entry - sign * atr)
    risk = abs(entry - sl)
    targets = [v for _, v in ahead[1:]]
    tp = next((v for v in targets if abs(v - entry) >= 1.5 * risk), targets[-1] if targets else entry + sign * risk)
    verb = "phá xuống" if side == "SELL" else "vượt lên"
    return {"condition": f"Giá {verb} {name}", "side": side, "entry": entry, "sl": sl, "tp": tp}


def write_with_template(context: dict) -> dict:
    plans = [{"symbol": code, "plan_a": _template_side(context["markets"][code], "SELL"),
              "plan_b": _template_side(context["markets"][code], "BUY")} for code in PLAN_SYMBOLS]
    ev = context["events"]
    lines = [f"🎯 PLAN A/B TỐI NAY {context['date'].upper()}", ""]
    for e in ev:
        lines.append(f"📅 {e['time']} {e['currency']} - {e['title']} (dự báo {e['forecast'] or '-'}, trước {e['previous'] or '-'})")
    lines.append("")
    for p in plans:
        m = context["markets"][p["symbol"]]
        lines.append(f"🔸 {p['symbol']} - giá hiện tại {m['price']}")
        for tag, s in (("A (USD mạnh)", p["plan_a"]), ("B (USD yếu)", p["plan_b"])):
            lines.append(f"   Plan {tag}: {s['condition']} → {s['side']} {s['entry']} | SL {s['sl']} | TP {s['tp']}")
        lines.append("")
    lines += ["Không vào lệnh lúc tin vừa ra, chờ 5-15 phút cho giá xác nhận. Rủi ro tối đa 1-2% tài khoản.",
              "", "Anh em nghiêng về Plan nào tối nay? 👇"]
    focus = f"Chờ {ev[0]['title']}" if ev else "Kịch bản phá vỡ phiên Mỹ"
    return {"focus": focus[:50], "post": "\n".join(lines), "plans": plans}


def generate(context: dict) -> dict:
    if not llm.available():
        print("  ! Chưa cấu hình AI - dùng bản template")
        return {**write_with_template(context), "writer": "template"}
    user = "DỮ LIỆU:\n" + json.dumps(context, ensure_ascii=False, indent=2)
    for attempt in range(2):
        try:
            result = llm.generate_json(SYSTEM_PROMPT, user, SCHEMA)
        except (llm.LLMError, json.JSONDecodeError) as exc:
            print(f"  ! AI lỗi: {exc}")
            break
        errors = check_plans(result, context)
        if not errors:
            return {**result, "writer": "ai"}
        print(f"  ! Lần {attempt + 1}: {'; '.join(errors)}")
        user += "\n\nBản trước bị từ chối vì:\n- " + "\n- ".join(errors) + "\nHãy sửa lại."
    print("  ! Dùng bản template thay thế")
    return {**write_with_template(context), "writer": "template"}


def finalize(post: str) -> str:
    return f"{post.rstrip()}\n\n{DISCLAIMER}\n\n{HASHTAGS}"
