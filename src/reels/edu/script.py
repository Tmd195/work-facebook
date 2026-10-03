"""AI viết kịch bản Reels kiến thức (phong cách thẻ tối + biểu đồ minh họa) cho Page thương hiệu.

AI chỉ viết LỜI + mô tả HÌNH DẠNG giá (đoạn tích luỹ, quét đáy, đẩy mạnh…) + chú thích; hệ thống tự sinh nến.
Chủ đề xoay vòng theo danh sách TOPICS, không lặp lại tới khi hết vòng.
"""
import json
import random
import re

from src.config import STATE
from src.content.llm import generate_json

TOPICS = {
    "po3": "PO3 (Power of Three): Accumulation – Manipulation – Distribution, cách smart money bẫy trader nhỏ lẻ",
    "liquidity-sweep": "Liquidity sweep: vì sao stop loss hay bị quét ngay đáy/đỉnh rồi giá chạy đúng hướng",
    "fvg-strong": "FVG mạnh hay yếu: dấu hiệu xác nhận một FVG đáng tin (sau cú quét + phá cấu trúc)",
    "order-block": "Order Block thật và giả: chỉ OB tạo ra phá cấu trúc + để lại FVG mới đáng giao dịch",
    "bos-choch": "BOS và CHoCH: phân biệt tiếp diễn xu hướng với đảo chiều",
    "3-conditions": "3 điều kiện trước khi vào lệnh để không bị quét stop loss: thanh khoản – cấu trúc – FVG",
    "equal-lows": "Đáy bằng nhau (equal lows) là nam châm thanh khoản – đừng đặt stop loss ngay dưới",
    "equal-highs": "Đỉnh bằng nhau (equal highs) và cú phá giả trước khi giảm",
    "fake-breakout": "Phá vỡ giả (fakeout): nhận diện khi giá phá range rồi quay lại",
    "premium-discount": "Premium & Discount: chỉ mua ở vùng giảm giá, bán ở vùng đắt của con sóng",
    "inducement": "Inducement: đáy/đỉnh mồi nhử trước vùng vào lệnh thật",
    "retest-entry": "Vào lệnh khi retest thay vì đuổi theo cây nến lớn",
    "sl-placement": "Đặt stop loss ở đâu cho đúng: dưới đáy quét chứ không phải dưới đáy gần nhất",
    "rr": "Tỉ lệ rủi ro/lợi nhuận: vì sao thắng 40% vẫn có lãi với RR 1:3",
    "trend-pullback": "Giao dịch theo xu hướng: đợi nhịp hồi về vùng cân bằng rồi mới vào",
    "range-trading": "Giao dịch trong vùng đi ngang: mua đáy bán đỉnh và khi nào thì dừng",
    "mss": "MSS (Market Structure Shift) sau cú quét thanh khoản – tín hiệu đảo chiều sớm",
    "breaker": "Breaker block: OB bị phá biến thành vùng cản ngược chiều",
    "double-top": "Hai đỉnh: khi nào là mô hình đảo chiều, khi nào là bẫy thanh khoản",
    "fomo": "Đuổi theo giá (FOMO): vì sao vào lệnh ở cuối con sóng làm RR rất kém",
}

FILE = STATE / "edu_reels.json"

SPEC = """
ĐỊNH DẠNG JSON (chỉ trả JSON):
{
 "slug": "chu-de-ngan",
 "title": "Tiêu đề video ngắn (dòng đầu caption)",
 "thumb": {"title": "2-3 DÒNG IN HOA, cách dòng bằng \\n, có thể tô màu [y]từ[/y]", "kicker": "nhãn nhỏ"},
 "caption": "Caption Facebook: 1 câu mở gây tò mò + 3-4 ý chính dạng gạch đầu dòng có icon + 1 câu chốt. KHÔNG hashtag.",
 "hashtags": ["#..."],
 "charts": {"A": {"seed": 7, "segments": [ ...các đoạn giá... ]}},
 "scenes": [ ...8-11 cảnh... ]
}

ĐOẠN GIÁ (segments) – hệ thống tự sinh nến đúng hình dạng, đơn vị giá ~ quanh 110:
 {"id":"acc","kind":"range","bars":16,"height":4}          đi ngang trong biên độ height
 {"id":"x","kind":"up"|"down","bars":12,"move":8,"fvg":true} xu hướng tăng/giảm, fvg:true = chắc chắn có 1 FVG
 {"id":"x","kind":"spike_up"|"spike_down","bars":4,"move":5,"fvg":true}  đẩy mạnh vài nến lớn
 {"id":"x","kind":"sweep_low"|"sweep_high","ref":"acc","depth":1.3,"bars":3}  quét qua đáy/đỉnh của đoạn ref rồi rút râu quay lại
 {"id":"x","kind":"pullback_down"|"pullback_up","ref":"x","depth":0.5,"bars":5}  hồi lại 50% đoạn ref
 Tổng 25-50 nến. Có thể có biểu đồ thứ 2 "B" cho chương sau (vẽ lại từ đầu).

CẢNH (scenes) – mỗi cảnh = 1 câu thoại 12-28 từ, hiện chữ phía trên biểu đồ:
 {"tag":"NHÃN CHƯƠNG ngắn",   ← giống nhau cho các cảnh cùng chương, vd "GIAI ĐOẠN 2 — MANIPULATION"
  "text":"Câu hiển thị, tô màu từ khoá: [y]vàng[/y] [o]cam[/o] [r]đỏ[/r] [g]xanh lá[/g] [c]xanh ngọc[/c] [b]xanh dương[/b] [p]tím[/p]",
  "say":"Câu ĐỌC cho giọng AI tiếng Việt: viết y nghĩa như text nhưng thuật ngữ tiếng Anh giữ nguyên chữ (hệ thống tự phiên âm), số viết bằng chữ số",
  "chart":"A",               ← chỉ ghi khi bắt đầu dùng / đổi biểu đồ
  "reveal":"id đoạn",        ← nến hiện dần tới HẾT đoạn này (bỏ trống = giữ nguyên)
  "focus":["id",...],        ← tuỳ chọn: phóng to vào các đoạn này
  "clear":true,              ← tuỳ chọn: xoá chú thích cũ
  "marks":[...],             ← chú thích xuất hiện trong cảnh (giữ lại ở các cảnh sau)
  "card":{...}}              ← tuỳ chọn: thẻ phủ giữa màn hình
 CHÚ THÍCH (marks) – label ngắn ≤ 3 từ:
  {"type":"band","seg":"acc","label":"1. Accumulation","color":"b"}  dải màu dọc cả chiều cao (chia giai đoạn)
  {"type":"box","seg":"acc","label":"Range tích luỹ","color":"b","label_pos":"above"|"below"}  khung nét đứt quanh đoạn
  {"type":"level","seg":"acc","at":"low"|"high","label":"Thanh khoản","color":"y"}  đường ngang tại đáy/đỉnh đoạn
  {"type":"fvg","seg":"id đoạn tăng/giảm có fvg","label":"FVG"}    vùng FVG tự tìm
  {"type":"ob","seg":"id đoạn đẩy mạnh","label":"Order Block"}     nến ngược chiều cuối cùng trước đoạn đó
  {"type":"arrow"|"x"|"dot","seg":"id","at":"low"|"high","label":"...","color":"r"}  mũi tên / dấu X / chấm tại đáy hoặc đỉnh đoạn
  thêm "when":0-1 = thời điểm hiện theo câu đọc (0 = đầu câu).
 THẺ PHỦ (card):
  {"kind":"title","kicker":"QUY TẮC VÀO LỆNH","title":"3\\nĐIỀU KIỆN","sub":"Thiếu 1 – không vào"}   (cảnh mở đầu kiểu poster)
  {"kind":"check","title":"3 ô kiểm tra","items":["Thanh khoản|Liquidity sweep","Cấu trúc|BOS/CHoCH","FVG|Fair Value Gap"]}  (danh sách tự tích ✓)
  {"kind":"list","title":"...","items":["...|chú thích nhỏ", ...]}
"""

SYSTEM = """Bạn là biên kịch video Reels/TikTok kiến thức trading (Smart Money / ICT / price action) cho Page
"CWG Markets & Partner". Phong cách giống kênh TikTok kiến thức nổi: câu ngắn, nhịp nhanh, mỗi câu gắn với
một chuyển động trên biểu đồ minh họa, giọng thân thiện xưng "mình"/"bạn".

CẤU TRÚC 60-90 GIÂY (8-11 cảnh, tổng 170-240 từ phần say):
 1. MỞ ĐẦU (1-2 cảnh): câu hook đánh vào nỗi đau/tò mò ("Vì sao bạn vừa vào lệnh là bị quét stop loss?"),
    có thể dùng thẻ title kiểu poster.
 2. GIẢI THÍCH (5-7 cảnh): chia chương rõ ràng (tag), mỗi cảnh làm hiện thêm nến hoặc chú thích MINH HOẠ ĐÚNG lời nói.
 3. CHỐT (1-2 cảnh): tóm tắt bằng thẻ check/list + 1 lời khuyên quản lý rủi ro.
 (Hệ thống tự thêm cảnh kết thương hiệu CWG – KHÔNG tự viết cảnh kêu gọi theo dõi.)

QUY TẮC NỘI DUNG:
 - Kiến thức đúng chuẩn SMC/ICT/price action, nói đơn giản cho người mới.
 - Biểu đồ là MINH HOẠ – không nhắc tên cặp tiền, không nói giá cụ thể, không hứa lợi nhuận, không "chắc chắn thắng".
 - Không kêu gọi bình luận/inbox, không nhắc sàn, không 18+.
 - Chú thích phải khớp hình: quét đáy thì dùng sweep_low + arrow/x tại "low"; FVG/OB phải gắn vào đoạn tăng/giảm mạnh SAU cú quét.
 - Mỗi cảnh có reveal hoặc marks hoặc card – không để cảnh "đứng hình".
 - Từ khoá tô màu tối đa 2 cụm/câu; màu nhất quán (vd. Accumulation luôn [b], Manipulation luôn [r], Distribution luôn [g]).
""" + SPEC


def _state() -> dict:
    return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {"done": []}


def next_topic() -> str:
    st = _state()
    left = [k for k in TOPICS if k not in st["done"]]
    if not left:
        st["done"], left = [], list(TOPICS)
    return left[0]


def mark_done(topic: str, title: str = ""):
    st = _state()
    st["done"] = [t for t in st["done"] if t != topic] + [topic]
    if title:                                      # nhớ các góc đã làm để vòng sau mỗi chủ đề viết góc khác
        st.setdefault("titles", {}).setdefault(topic, []).append(title)
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def validate(spec: dict) -> dict:
    """Sửa lỗi nhỏ thường gặp của AI; báo lỗi nếu kịch bản không dựng được."""
    charts = spec.get("charts") or {}
    if not charts or not spec.get("scenes"):
        raise ValueError("kịch bản thiếu charts/scenes")
    ids = {cid: {s.get("id") for s in c.get("segments", [])} for cid, c in charts.items()}
    cur = None
    for sc in spec["scenes"]:
        if not sc.get("text"):
            raise ValueError("cảnh thiếu text")
        if sc.get("chart") in charts:
            cur = sc["chart"]
        known = ids.get(cur, set())
        if sc.get("reveal") and sc["reveal"] not in known:
            sc.pop("reveal")
        sc["focus"] = [f for f in sc.get("focus", []) if f in known]
        sc["marks"] = [m for m in sc.get("marks", []) if m.get("seg") in known]
        for m in sc["marks"]:
            if isinstance(m.get("at"), (int, float)):
                m["when"] = m.pop("at")
        sc["text"] = re.sub(r"\s+", " ", sc["text"]).strip()
    if spec["scenes"][0].get("chart") not in charts:
        spec["scenes"][0]["chart"] = next(iter(charts))
    return spec


def write(topic: str | None = None) -> dict:
    topic = topic or next_topic()
    brief = TOPICS.get(topic, topic)
    old = _state().get("titles", {}).get(topic, [])
    again = ("\nChủ đề này ĐÃ làm các video: " + " | ".join(old[-6:]) +
             "\n→ BẮT BUỘC chọn GÓC MỚI hoàn toàn (sai lầm hay gặp, so sánh đúng/sai, tình huống khác, "
             "chiều ngược lại mua/bán, mẹo nâng cao…): tiêu đề, hook và hình dạng giá khác hẳn.") if old else ""
    user = (f"Chủ đề: {brief}\nslug: {topic}{again}\nViết kịch bản theo đúng định dạng. Nhớ: phần say là lời đọc "
            "tự nhiên, text là chữ trên màn hình (có thể ngắn gọn hơn say).")
    spec = generate_json(SYSTEM, user, {"type": "object"})
    for c in (spec.get("charts") or {}).values():      # nến minh họa mỗi lần một khác
        c["seed"] = random.randint(1, 10_000)
    spec["slug"] = topic
    spec["topic"] = topic
    return validate(spec)
