"""Bài 'Kiến thức' (12:00) theo SERIES: đăng hết series này mới sang series khác.

- Đề cương từng series: data/series/NN-<id>.yaml (đã nghiên cứu sẵn, xem data/series/README.md)
- Thứ tự series: config.yaml -> knowledge.series_order (series không có tên trong danh sách xếp sau, theo số file)
- Tiến độ: state/series_progress.json
- Ghi chú riêng của page trong knowledge/ được ưu tiên đưa vào bài
"""
import json
from datetime import date

import yaml

from src.chart_tools import CHART_SPEC
from src.config import CONFIG, ROOT
from src.content import llm
from src.design.diagrams import is_valid as diagram_valid

SERIES_DIR = ROOT / "data" / "series"
PROGRESS_FILE = ROOT / "state" / "series_progress.json"
NOTES_DIR = ROOT / "knowledge"
HASHTAGS = "#forex #kienthucforex #trading #giavang #XAUUSD"

NON_CHART_SPEC = """Trường "diagram" (chỉ dùng khi hình KHÔNG phải biểu đồ giá):
- {"type":"compare","left":{"title":"...","tone":"good|bad|neutral","items":["..."]},"right":{...}}  2-4 ý/cột, ≤ 45 ký tự/ý
- {"type":"formula","rows":[{"label":"...","value":"..."}],"result":{"label":"...","value":"..."},"note":"..."}  2-6 dòng
- {"type":"checklist","items":["..."]}  3-6 ý, ≤ 60 ký tự/ý"""

SYSTEM_PROMPT = f"""Bạn là người viết nội dung giáo dục cho một Facebook Page về forex và vàng dành cho trader Việt Nam.

Nhiệm vụ: viết MỘT bài trong một series kiến thức, dựa trên ĐỀ CƯƠNG BÀI được cung cấp (đề cương đã được nghiên cứu
và kiểm chứng - bám sát nội dung, không thêm kiến thức sai lệch).

Văn phong: dễ hiểu với người mới nhưng không hời hợt; câu ngắn; xưng "anh em" tự nhiên; không hô hào, không hứa lợi nhuận.
Diễn đạt bằng lời của page, không nhắc tên YouTuber/kênh/khóa học nào.
Facebook không hiển thị markdown: không dùng **, #, bảng. Tối đa khoảng 6 emoji.

Cấu trúc "post" (220-350 từ):
1. Dòng đầu: "📘 <TÊN SERIES> – PHẦN <x>/<tổng> | <tiêu đề>"
2. Nếu không phải phần 1: 1 câu nối với phần trước. Nếu là phần 1: 1-2 câu giới thiệu series sẽ giúp anh em làm được gì.
3. Nội dung chính theo key_points của đề cương, đánh số 1️⃣ 2️⃣ 3️⃣ khớp với các ảnh 01, 02, 03 trong album.
4. Ví dụ minh họa theo đề cương. Số trong ví dụ là giả định; nếu ví dụ dùng giá vàng/EURUSD thì đặt mức giá gần
   GIÁ THAM KHẢO HIỆN TẠI cho tự nhiên, và ghi rõ "ví dụ".
5. "⚠️ Sai lầm hay gặp:" theo mục mistakes.
6. Kết: câu hỏi mở + "Phần tiếp theo: <tiêu đề phần sau>" (nếu còn) hoặc lời tổng kết series (nếu là phần cuối).
KHÔNG tự viết hashtag. KHÔNG mô tả chi tiết các con số trên biểu đồ - hệ thống sẽ tự gắn phần đó.

Bài được đăng kèm ALBUM ẢNH: 1 ảnh bìa + 3-5 ảnh nội dung ("slides"), mỗi ảnh giải thích MỘT ý:
- "title": tiêu đề bài ≤ 55 ký tự (dùng cho ảnh bìa).
- "slides": 3-5 phần tử, theo đúng thứ tự trong bài, mỗi phần tử gồm:
    "heading": tiêu đề ý ≤ 45 ký tự,
    "body": diễn giải 2-4 câu (≤ 320 ký tự), cụ thể, chỉ vào điều người đọc thấy trên hình,
    "chart": biểu đồ cho ý này (theo đặc tả bên dưới) hoặc null,
    "diagram": hình không phải biểu đồ (so sánh/công thức/checklist) hoặc null.
  Mỗi slide nên có 1 hình (chart HOẶC diagram). Ưu tiên chart giá thật; slide "Sai lầm hay gặp" nên dùng diagram compare/checklist.
  Các slide có chart giá thật nên dùng cùng symbol/tf để người đọc theo dõi liền mạch.

{CHART_SPEC}

{NON_CHART_SPEC}"""

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "post": {"type": "string"},
        "slides": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "heading": {"type": "string"},
                "body": {"type": "string"},
                "chart": {"anyOf": [{"type": "null"}, {"type": "object"}]},
                "diagram": {"anyOf": [{"type": "null"}, {"type": "object"}]},
            },
            "required": ["heading", "body", "chart", "diagram"]}},
    },
    "required": ["title", "post", "slides"],
}


# ===================================================================== series & tiến độ

def load_series() -> list[dict]:
    files = sorted(SERIES_DIR.glob("[0-9][0-9]-*.yaml"))
    all_series = []
    for f in files:
        s = yaml.safe_load(f.read_text(encoding="utf-8"))
        s["lessons"] = sorted(s["lessons"], key=lambda l: l["part"])
        s["file"] = f.name
        all_series.append(s)
    order = (CONFIG.get("knowledge") or {}).get("series_order") or []
    rank = {sid: i for i, sid in enumerate(order)}
    return sorted(all_series, key=lambda s: (rank.get(s["id"], len(order)), s["file"]))


def _progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    return {"done": {}, "history": []}


def next_lesson(series_id: str | None = None, part: int | None = None) -> tuple[dict, dict] | None:
    """(series, lesson) tiếp theo; hoặc bài chỉ định bằng series_id/part."""
    all_series = load_series()
    if series_id:
        s = next(x for x in all_series if x["id"] == series_id)
        done = _progress()["done"].get(series_id, 0)
        return s, s["lessons"][(part or done + 1) - 1]
    done = _progress()["done"]
    for s in all_series:
        k = done.get(s["id"], 0)
        if k < len(s["lessons"]):
            return s, s["lessons"][k]
    return None


def mark_done(series: dict, lesson: dict) -> None:
    prog = _progress()
    prog["done"][series["id"]] = max(prog["done"].get(series["id"], 0), lesson["part"])
    prog["history"].append({"series": series["id"], "part": lesson["part"], "date": date.today().isoformat()})
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8")


def _notes(limit_chars: int = 12000) -> str:
    parts = []
    for f in sorted(NOTES_DIR.glob("*")):
        if f.suffix in (".md", ".txt") and f.name.lower() != "readme.md":
            parts.append(f"### {f.stem}\n{f.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts)[:limit_chars]


# ===================================================================== viết bài

def build_prompt(series: dict, lesson: dict, ref_prices: dict) -> str:
    lessons = series["lessons"]
    i = lessons.index(lesson)
    ctx = {
        "series": {"name": series["name"], "level": series["level"], "description": series["description"],
                   "total_parts": len(lessons)},
        "prev_title": lessons[i - 1]["title"] if i else None,
        "next_title": lessons[i + 1]["title"] if i + 1 < len(lessons) else None,
        "lesson": lesson,
        "reference_prices": ref_prices,
    }
    user = "ĐỀ CƯƠNG BÀI:\n" + json.dumps(ctx, ensure_ascii=False, indent=2)
    notes = _notes()
    if notes:
        user += f"\n\nGHI CHÚ RIÊNG CỦA PAGE (ưu tiên nếu liên quan):\n{notes}"
    return user


def generate(series: dict, lesson: dict, ref_prices: dict) -> dict | None:
    if not llm.available():
        print("  ! Chưa cấu hình AI - bỏ qua bài Kiến thức")
        return None
    try:
        result = llm.generate_json(SYSTEM_PROMPT, build_prompt(series, lesson, ref_prices), SCHEMA)
    except (llm.LLMError, json.JSONDecodeError) as exc:
        print(f"  ! AI lỗi: {exc}")
        return None
    result["slides"] = (result.get("slides") or [])[:5]
    for sl in result["slides"]:
        if sl.get("diagram") and not diagram_valid(sl["diagram"]):
            sl["diagram"] = None
    if len(result["slides"]) < 2:
        print("  ! AI trả về quá ít slide")
        return None
    return {**result, "writer": "ai"}


def finalize(post: str, facts: list[str], series_id: str = "") -> str:
    """Gắn các mốc giá thật tìm được trên biểu đồ, mỗi mốc một dòng ngắn: "📊 Kháng cự gần nhất: 4,258.58".
    Chỉ giữ các mốc giá; thông tin mô tả (RSI, Supertrend...) đã nằm trên ảnh."""
    levels = [f for f in facts if not f.startswith(("RSI", "Supertrend", "Giá so với"))]
    note = "\n\n" + "\n".join(f"📊 {f}" for f in levels) if levels else ""
    from src.content import hashtags
    from src.content.fbtext import render
    return f"{render(post).rstrip()}{note}\n\n{hashtags.knowledge(series_id)}"
