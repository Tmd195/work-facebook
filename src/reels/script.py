"""Kịch bản Reels 30-45 giây: chọn chủ đề (xoay vòng 4 nhóm) → AI viết lời đọc + nội dung từng cảnh."""
import csv
import json
import random

from src.config import ROOT, STATE
from src.content.llm import generate_json
from src.reels.marks import MARKS_SPEC

PROGRESS = STATE / "reels_progress.json"
CATALOG = ROOT / "data" / "reels" / "he-thong.csv"
CTA = "Hãy comment điều mà bạn muốn biết về thị trường - Thái sẽ mổ xẻ nó ra cho bạn dễ hiểu nhất có thể"

PILLARS = {
    "he-thong": "Giới thiệu 1 hệ thống/chỉ báo giao dịch cụ thể: nó đo cái gì, tín hiệu vào lệnh, bộ lọc, đặt SL/TP",
    "quan-ly-von": "Mẹo quản lý vốn / rủi ro: % rủi ro mỗi lệnh, khối lượng, chuỗi thua, giới hạn ngày, tâm lý",
    "sl-tp": "Mẹo đặt dừng lỗ (SL) và chốt lời (TP): vị trí, theo ATR/cấu trúc, dời SL về entry, chốt từng phần",
    "setup": "Cách dựng/thiết lập một hệ thống giao dịch: khung thời gian, điều kiện vào, checklist, nhật ký, backtest",
}
# Độ dài theo nhóm: video hệ thống dài hơn (6 cảnh ~60-80s), video mẹo 4 cảnh ~40-50s
LENGTH = {
    "he-thong": {"n": 6, "words": "20-26", "total": "140-170",
                 "flow": "Hook đặt vấn đề → cảnh 1 hệ thống đo cái gì/nhìn thế nào → cảnh 2 điều kiện vào lệnh Buy → "
                         "cảnh 3 điều kiện Sell hoặc bộ lọc tránh tín hiệu nhiễu → cảnh 4 đặt SL/TP cụ thể → "
                         "cảnh 5 so sánh tín hiệu đẹp và tín hiệu nên bỏ (compare) → cảnh 6 checklist 3 bước vào lệnh (steps)."},
    "_": {"n": 4, "words": "20-26", "total": "95-120",
          "flow": "Hook đặt vấn đề → cảnh 1 nguyên nhân/khái niệm → cảnh 2-3 cách làm cụ thể → cảnh 4 lưu ý/chốt lại."},
}
LENGTH.update({k: LENGTH["_"] for k in ("quan-ly-von", "sl-tp", "setup")})

ORDER = ["he-thong", "quan-ly-von", "he-thong", "sl-tp", "he-thong", "setup"]

SYSTEM = """Bạn là Thái (Duy Thái Đặng), trader vàng XAUUSD, viết kịch bản video ngắn (Reels/TikTok) 30-45 giây.
Giọng: xưng "Thái", gọi người xem là "anh em"; nói như người thật đang chia sẻ, câu ngắn, dễ hiểu, có số liệu cụ thể.
Không phô trương, không hứa lợi nhuận, không nhắc nguồn tham khảo hay tên nhà cung cấp chỉ báo.
Không dùng markdown, không in đậm, không emoji trong lời đọc.

Cấu trúc video (40-45 giây, MẬT ĐỘ KIẾN THỨC CAO như các kênh dạy trade trên TikTok: mỗi cảnh phải có quy tắc
cụ thể, con số, điều kiện rõ ràng để người xem học được và áp dụng ngay; không nói chung chung):
- hook: 1 câu mở đầu đánh trúng nỗi đau (tối đa 12 từ). "screen": chữ trên màn hình (tối đa 7 từ).
- slides: đúng [N] cảnh nội dung, mỗi cảnh chọn 1 kiểu:
  * "diagram": sơ đồ nến minh họa + hiệu ứng khoanh tròn/kẻ đường/dời SL vẽ dần khớp với từng ý.
      bullets: đúng 3 ý (mỗi ý tối đa 10 từ, có số liệu/điều kiện cụ thể), diagram: {...} (bắt buộc).
  * "compare": so sánh 2 thứ đặt cạnh nhau (đúng/sai, BOS/CHoCH, SL sát/SL theo cấu trúc...).
      compare: {"left": {"name": ≤2 từ, "diagram": {...}, "points": [2-3 ý ≤6 từ]}, "right": {...}}
      (left = cách đúng/thứ nhất, màu xanh; right = cách sai/thứ hai, màu đỏ)
  * "steps": quy trình/checklist 3 bước. steps: [{"title": ≤4 từ, "text": ≤8 từ}] x3, diagram: {...} (nên có, minh họa các bước trên sơ đồ).
  Bắt buộc: ít nhất 2 cảnh "diagram", và có 1 cảnh "compare" hoặc "steps".
  Mỗi cảnh còn có: title (tối đa 3 từ), pill (1 dòng tối đa 6 từ), warning (câu chốt tối đa 9 từ),
  voice: lời đọc [WORDS] từ (không vượt quá), nói theo đúng thứ tự các ý/hiệu ứng trên màn hình (ý 1 → ý 2 → ý 3) để hình khớp lời.
- Cảnh cuối (kêu gọi bình luận) hệ thống tự thêm, KHÔNG viết.
Tổng lời đọc hook + [N] cảnh: [TOTAL] từ. Kiến thức dồn vào chữ trên màn hình và sơ đồ; lời đọc ngắn gọn, đi thẳng ý.

{MARKS_SPEC}
  Mỗi sơ đồ 3-5 mark. Với cảnh "diagram", step của mark khớp với ý tương ứng trong bullets.
  Ví dụ dời SL lệnh Buy: path [100,94,99,96,104,100,108]; circle at 1 "Đáy cũ"; hline 97 "Entry";
  arrow [3,97]→[4,104.5] "Phá đỉnh"; circle at 5 "Đáy mới"; move at 1 từ 93 lên 99 "SL cũ"→"SL mới".

LỜI ĐỌC PHẢI LÀ MỘT MẠCH KỂ LIỀN, như Thái đang nói một hơi với anh em, không phải các câu rời rạc:
- Viết toàn bộ lời đọc như một đoạn văn trước, rồi mới cắt ra hook và [N] cảnh.
- [FLOW]
- Câu đầu mỗi cảnh phải nối từ ý cảnh trước bằng từ chuyển: "Vì sao vậy?", "Lý do là...", "Vậy làm sao...?",
  "Cách Thái làm là...", "Nhưng nhớ là...", "Và quan trọng nhất...". Không mở cảnh bằng câu định nghĩa trống không.
- Câu cuối cảnh cuối dẫn sang lời mời comment (ví dụ: "Còn anh em đang gặp khó ở đâu?").
- Viết số và ký hiệu như văn nói: "1 phần trăm" (không viết 1%), "1 ăn 2" (không viết 1:2).

Thumbnail (ảnh bìa, thiết kế riêng): line1 (tối đa 4 từ), line2 (tối đa 4 từ, phần được tô nổi bật), tag (tối đa 3 từ).
caption: bản tóm tắt để người xem LƯU LẠI, trình bày thoáng, dễ đọc lướt trên điện thoại (KHÔNG viết thành 1 đoạn liền):
  - Dòng 1: tiêu đề VIẾT HOA có 1 emoji đầu dòng + lợi ích/con số (ví dụ "🔨 HỆ THỐNG NẾN BÚA NGƯỢC – 3 BƯỚC VÀO LỆNH VÀNG").
    Dòng 2: 1 câu gợi tò mò để người xem bấm "Xem thêm".
  - Sau đó 2-4 nhóm, mỗi nhóm: 1 dòng tiêu đề nhóm có emoji (📌 Nhận diện / ✅ Điều kiện vào lệnh / 🎯 Quản lý lệnh / ⚠️ Lưu ý...),
    rồi 2-3 dòng gạch đầu dòng "• " ngắn gọn (tối đa ~12 từ/dòng). Giữa các nhóm cách 1 dòng trống.
  - Viết tắt chuẩn trader được dùng (SL, TP1, R:R, H4, Entry) và ký hiệu ngắn (1R, 50%, ≥, →) cho gọn.
  - Dòng cuối: "💬 " + câu hỏi mời anh em comment điều muốn Thái mổ xẻ tiếp.
  - Không in đậm, không markdown (#, **). Không ghi hashtag trong caption (hệ thống tự thêm).
hashtags: 3-5 thẻ liên quan (không cần #DuyThaiDang).
"""

SYSTEM = SYSTEM.replace("{MARKS_SPEC}", MARKS_SPEC)

_DIAGRAM = {"type": ["object", "null"]}
_SIDE = {"type": "object", "properties": {"name": {"type": "string"}, "diagram": _DIAGRAM,
                                          "points": {"type": "array", "items": {"type": "string"}}},
         "required": ["name", "diagram", "points"]}
SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "thumb": {"type": "object", "properties": {"line1": {"type": "string"}, "line2": {"type": "string"},
                                                   "tag": {"type": "string"}},
                  "required": ["line1", "line2", "tag"]},
        "hook": {"type": "object", "properties": {"screen": {"type": "string"}, "voice": {"type": "string"}},
                 "required": ["screen", "voice"]},
        "slides": {"type": "array", "minItems": 4, "maxItems": 6, "items": {
            "type": "object",
            "properties": {"type": {"type": "string", "enum": ["diagram", "compare", "steps"]},
                           "title": {"type": "string"}, "pill": {"type": "string"},
                           "bullets": {"type": "array", "items": {"type": "string"}},
                           "diagram": _DIAGRAM,
                           "compare": {"type": ["object", "null"], "properties": {"left": _SIDE, "right": _SIDE}},
                           "steps": {"type": ["array", "null"], "items": {
                               "type": "object", "properties": {"title": {"type": "string"}, "text": {"type": "string"}}}},
                           "warning": {"type": "string"}, "voice": {"type": "string"}},
            "required": ["type", "title", "pill", "warning", "voice"]}},
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["topic", "thumb", "hook", "slides", "caption", "hashtags"],
}


def _progress() -> dict:
    return json.loads(PROGRESS.read_text(encoding="utf-8")) if PROGRESS.exists() else {"count": 0, "used": [], "topics": []}


def mark_done(meta: dict):
    p = _progress()
    p["count"] += 1
    if meta.get("system"):
        p["used"].append(meta["system"])
    p["topics"] = (p["topics"] + [meta["topic"]])[-60:]
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")


def _pick_system(used: list[str]) -> dict:
    rows = list(csv.DictReader(open(CATALOG, encoding="utf-8")))
    fresh = [r for r in rows if r["slug"] not in used and r["tin_hieu"] in ("RO", "Rõ", "MOT_PHAN")] or rows
    top = [r for r in fresh if r["diem"] == "5"] or fresh
    return random.choice(top[:60])


def next_brief(pillar: str | None = None) -> dict:
    p = _progress()
    pillar = pillar or ORDER[p["count"] % len(ORDER)]
    brief = {"pillar": pillar, "system": None}
    if pillar == "he-thong":
        s = _pick_system(p["used"])
        brief["system"] = s["slug"]
        brief["detail"] = (f"Hệ thống/chỉ báo: {s['ten']}\nMô tả: {s['mo_ta_vn']}\nKhung: {s['khung_tg']}\n"
                           f"Gợi ý ghép thành hệ thống: {s['to_hop_goi_y']}")
    brief["recent"] = p["topics"][-15:]
    return brief


def _system(pillar: str) -> str:
    L = LENGTH[pillar]
    return (SYSTEM.replace("[N]", str(L["n"])).replace("[WORDS]", L["words"]).replace("[TOTAL]", L["total"])
            .replace("[FLOW]", L["flow"]))


def write(brief: dict) -> dict:
    user = (f"Nhóm chủ đề: {PILLARS[brief['pillar']]}\n"
            + (f"\n{brief['detail']}\nHãy trình bày như một hệ thống áp dụng cho XAUUSD: điều kiện vào, bộ lọc, SL/TP.\n"
               if brief.get("detail") else "\nTự chọn 1 chủ đề cụ thể, thực dụng trong nhóm này.\n")
            + ("\nTránh trùng các chủ đề gần đây: " + "; ".join(brief["recent"]) if brief["recent"] else ""))
    s = generate_json(_system(brief["pillar"]), user, SCHEMA)
    s["slides"] = s["slides"][:LENGTH[brief["pillar"]]["n"]]
    for sl in s["slides"]:
        sl["bullets"] = [b for b in sl.get("bullets") or [] if b.strip()][:3]
    s["cta"] = CTA
    s["pillar"] = brief["pillar"]
    s["system"] = brief.get("system")
    return s
