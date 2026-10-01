"""Bài 'Bản tin sáng': dữ liệu thật -> Opus 5 viết bài -> kiểm tra số liệu."""
import json
import re
from datetime import datetime

from src.config import CONFIG, SYMBOLS
from src.content import llm

WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
HASHTAGS = "#forex #XAUUSD #EURUSD #GBPUSD #DXY #giavang #bantinsang"
DISCLAIMER = "⚠️ Nội dung mang tính tham khảo, không phải khuyến nghị đầu tư. Giao dịch forex/vàng có rủi ro cao."

SYSTEM_PROMPT = f"""Bạn là biên tập viên nội dung của một Facebook Page về forex và vàng dành cho trader Việt Nam.

Nhiệm vụ: viết bài "Bản tin sáng" từ khối DỮ LIỆU được cung cấp.

Nguyên tắc số liệu (bắt buộc):
- Chỉ dùng các con số có trong DỮ LIỆU (giá, vùng hỗ trợ/kháng cự, pivot, %, dự báo, kỳ trước, giờ tin). Không tự tạo thêm bất kỳ mức giá hay số liệu nào.
- Viết giá bằng dấu chấm thập phân, đúng số chữ số như trong dữ liệu (vàng có thể làm tròn đến 1 chữ số thập phân).
- Giờ tin là giờ Việt Nam, đã có sẵn trong dữ liệu.

Nguyên tắc nội dung:
- Đưa ra góc nhìn tham khảo, không phải tín hiệu gọi lệnh. Không hứa hẹn lợi nhuận, không dùng từ "kèo", "chắc chắn", "x2 tài khoản".
- Giọng văn: chuyên nghiệp, rõ ràng, gần gũi với trader Việt; câu ngắn; không sáo rỗng.
- Facebook không hiển thị markdown: không dùng **, #, bảng. Dùng xuống dòng và tối đa khoảng 8 emoji cho cả bài.
- Tên tin kinh tế: giữ tên gốc tiếng Anh, kèm giải thích ngắn tiếng Việt nếu là tin quan trọng.

Cấu trúc bài (180-300 từ):
1. Dòng mở đầu: "☀️ BẢN TIN SÁNG <thứ>, <ngày>" và 1 câu tóm tắt tâm điểm hôm nay.
2. Bức tranh chung: DXY và tâm lý thị trường (2-3 câu).
3. Lần lượt XAUUSD, EURUSD, GBPUSD: xu hướng, giá hiện tại, kháng cự/hỗ trợ gần, góc nhìn trong ngày (2-3 câu mỗi mã).
4. "📅 Lịch tin đáng chú ý (giờ VN)": liệt kê các tin High, nêu dự báo/kỳ trước và tin đó tác động thế nào tới USD/vàng. Nếu không có tin High thì nói rõ ngày ít tin.
5. Một câu nhắc quản lý rủi ro gắn với lịch tin hôm nay.
6. Một câu hỏi mở để người đọc bình luận.

KHÔNG tự viết dòng miễn trừ trách nhiệm và hashtag - hệ thống sẽ tự thêm.

Trường "focus": một câu tiêu điểm cho banner, tối đa 60 ký tự, không chứa con số giá."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "post": {"type": "string"},
        "focus": {"type": "string"},
    },
    "required": ["post", "focus"],
    "additionalProperties": False,
}


def build_context(now: datetime, markets: dict, events: list[dict]) -> dict:
    return {
        "date": f"{WEEKDAYS[now.weekday()]}, {now:%d/%m/%Y}",
        "markets": {
            s["code"]: {k: v for k, v in markets[s["code"]].items() if k not in ("spark", "source", "notes")}
            for s in SYMBOLS
        },
        "calendar": events,
    }


# ---------------------------------------------------------------- AI writer

def write_with_ai(context: dict, feedback: str = "") -> dict:
    user = "DỮ LIỆU:\n" + json.dumps(context, ensure_ascii=False, indent=2)
    if feedback:
        user += f"\n\nBản trước bị từ chối vì: {feedback}\nHãy viết lại, chỉ dùng số trong DỮ LIỆU."
    return llm.generate_json(SYSTEM_PROMPT, user, OUTPUT_SCHEMA)


# ---------------------------------------------------------- Template writer
# Dùng khi chưa có ANTHROPIC_API_KEY hoặc AI lỗi - để hệ thống không bao giờ "trắng" bài.

def write_with_template(context: dict) -> dict:
    m = context["markets"]
    lines = [f"☀️ BẢN TIN SÁNG {context['date'].upper()}", ""]
    dxy = m["DXY"]
    lines.append(f"💵 DXY đang ở {dxy['price']} ({dxy['change_pct']:+.2f}%), xu hướng D1: {dxy['trend'].lower()}.")
    lines.append("")
    for code in ("XAUUSD", "EURUSD", "GBPUSD"):
        d = m[code]
        res = d["resistance"][0] if d["resistance"] else d["r1"]
        sup = d["support"][0] if d["support"] else d["s1"]
        lines.append(f"🔸 {code}: {d['price']} ({d['change_pct']:+.2f}%) - xu hướng {d['trend'].lower()}")
        lines.append(f"   Kháng cự {res} | Hỗ trợ {sup} | Pivot {d['pivot']}")
    lines.append("")
    lines.append("📅 Lịch tin đáng chú ý (giờ VN):")
    highs = [e for e in context["calendar"] if e["impact"] == "High"] or context["calendar"][:4]
    for e in highs:
        extra = f" (dự báo {e['forecast']}, trước {e['previous']})" if e["forecast"] else ""
        lines.append(f"• {e['time']} {e['currency']} - {e['title']}{extra}")
    if not highs:
        lines.append("• Hôm nay ít tin quan trọng.")
    lines += ["", "Hạn chế vào lệnh sát giờ tin mạnh, luôn đặt dừng lỗ.",
              "", "Hôm nay anh em canh mã nào? Bình luận bên dưới nhé 👇"]
    focus = "Theo dõi tin " + highs[0]["currency"] if highs else "Ngày ít tin - chú ý vùng giá"
    return {"post": "\n".join(lines), "focus": focus}


# --------------------------------------------------------------- Validator

NUM_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(%?)")
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")


def _allowed_numbers(context: dict) -> list[float]:
    nums: list[float] = []

    def walk(x):
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            nums.append(abs(float(x)))  # dấu +/- được đọc riêng khỏi con số
        elif isinstance(x, str):
            for n, _ in NUM_RE.findall(x.replace(",", "")):
                nums.append(float(n))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(context["markets"])
    for e in context["calendar"]:
        walk([e["forecast"], e["previous"]])
    return nums


def find_unverified_numbers(post: str, context: dict) -> list[str]:
    """Trả về các con số trong bài KHÔNG khớp với dữ liệu (nghi AI tự bịa)."""
    allowed = _allowed_numbers(context)
    text = TIME_RE.sub(" ", DATE_RE.sub(" ", post))
    bad = []
    for raw, pct in NUM_RE.findall(text):
        value = float(raw.replace(",", ""))
        if "." not in raw and value <= 100 and not pct:
            continue  # số đếm thông thường: "3 mã", "14 ngày"...
        if pct and "." not in raw and value <= 5:
            continue  # lời khuyên rủi ro "1-2%"
        tol = lambda v: max(abs(v) * 0.0003, 1e-5)
        if not any(abs(value - v) <= tol(v) for v in allowed):
            bad.append(raw + pct)
    return bad


def generate(context: dict) -> dict:
    """Viết bài, kiểm tra số liệu; AI được sửa 1 lần, sau đó rơi về template."""
    if not llm.available():
        print("  ! Chưa cấu hình AI - dùng bản template")
        return {**write_with_template(context), "writer": "template"}

    feedback = ""
    for attempt in range(2):
        try:
            result = write_with_ai(context, feedback)
        except (llm.LLMError, json.JSONDecodeError, KeyError) as exc:
            print(f"  ! AI lỗi: {exc}")
            break
        bad = find_unverified_numbers(result["post"], context)
        if not bad:
            return {**result, "writer": CONFIG["ai"]["backend"]}
        feedback = f"các số không có trong dữ liệu: {', '.join(bad)}"
        print(f"  ! Lần {attempt + 1}: {feedback}")

    print("  ! Dùng bản template thay thế")
    return {**write_with_template(context), "writer": "template"}


def finalize(post: str) -> str:
    return f"{post.rstrip()}\n\n{DISCLAIMER}\n\n{HASHTAGS}"
