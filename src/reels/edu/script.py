"""AI viết kịch bản Reels kiến thức (phong cách thẻ tối + biểu đồ minh họa) cho Page thương hiệu.

AI chỉ viết LỜI + mô tả HÌNH DẠNG giá (đoạn tích luỹ, quét đáy, đẩy mạnh…) + chú thích; hệ thống tự sinh nến.
Chủ đề xoay vòng theo danh sách TOPICS (64 chủ đề ≈ 64 ngày/vòng), không lặp lại tới khi hết vòng;
sang vòng sau mỗi chủ đề bắt buộc viết góc mới, và mọi video đều né ý của các video đã làm (lưu tiêu đề).
"""
import json
import random
import re

from src.config import STATE
from src.content.llm import generate_json

TOPICS = {
    # --- Smart Money / ICT (24)
    "po3": "PO3 (Power of Three): Accumulation – Manipulation – Distribution, cách smart money bẫy trader nhỏ lẻ",
    "liquidity-sweep": "Liquidity sweep: vì sao stop loss hay bị quét ngay đáy/đỉnh rồi giá chạy đúng hướng",
    "fvg-strong": "FVG mạnh hay yếu: dấu hiệu xác nhận một FVG đáng tin (sau cú quét + phá cấu trúc)",
    "order-block": "Order Block thật và giả: chỉ OB tạo ra phá cấu trúc + để lại FVG mới đáng giao dịch",
    "bos-choch": "BOS và CHoCH: phân biệt tiếp diễn xu hướng với đảo chiều",
    "3-conditions": "3 điều kiện trước khi vào lệnh để không bị quét stop loss: thanh khoản – cấu trúc – FVG",
    "equal-lows": "Đáy bằng nhau (equal lows) là nam châm thanh khoản – đừng đặt stop loss ngay dưới",
    "equal-highs": "Đỉnh bằng nhau (equal highs) và cú phá giả trước khi giảm",
    "premium-discount": "Premium & Discount: chỉ mua ở vùng giảm giá, bán ở vùng đắt của con sóng",
    "inducement": "Inducement: đáy/đỉnh mồi nhử trước vùng vào lệnh thật",
    "mss": "MSS (Market Structure Shift) sau cú quét thanh khoản – tín hiệu đảo chiều sớm",
    "breaker": "Breaker block: OB bị phá biến thành vùng cản ngược chiều",
    "mitigation": "Mitigation block: vùng giá quay lại 'xử lý' lệnh còn treo của tổ chức",
    "ifvg": "Inverse FVG: FVG bị phá thủng đổi vai thành vùng cản/hỗ trợ",
    "ote": "OTE – vùng vào lệnh tối ưu 62-79% Fibonacci của con sóng sau phá cấu trúc",
    "internal-external": "Thanh khoản nội bộ và thanh khoản bên ngoài: giá đi từ đâu tới đâu",
    "swing-structure": "Cấu trúc swing và cấu trúc nội bộ: vì sao 2 trader nhìn cùng biểu đồ lại thấy ngược nhau",
    "displacement": "Displacement: cú đẩy giá mạnh để lại FVG – dấu chân thật của tổ chức",
    "sell-side-buy-side": "Buy-side và sell-side liquidity: giá luôn tìm tới nơi có nhiều lệnh dừng",
    "judas-swing": "Judas swing: cú chạy giả đầu phiên trước khi giá đi hướng thật",
    "turtle-soup": "Turtle soup: giao dịch ngược cú phá vỡ đỉnh/đáy cũ thất bại",
    "smt": "Phân kỳ SMT: hai thị trường tương quan không cùng tạo đỉnh/đáy mới – dấu hiệu bẫy",
    "rejection-block": "Rejection block: râu nến dài tại vùng thanh khoản nói lên điều gì",
    "trendline-liquidity": "Trendline liquidity: đường xu hướng chạm 3 lần là nơi chứa đầy stop loss",
    # --- Price action (14)
    "fake-breakout": "Phá vỡ giả (fakeout): nhận diện khi giá phá range rồi quay lại",
    "retest-entry": "Vào lệnh khi retest thay vì đuổi theo cây nến lớn",
    "trend-pullback": "Giao dịch theo xu hướng: đợi nhịp hồi về vùng cân bằng rồi mới vào",
    "range-trading": "Giao dịch trong vùng đi ngang: mua đáy bán đỉnh và khi nào thì dừng",
    "double-top": "Hai đỉnh: khi nào là mô hình đảo chiều, khi nào là bẫy thanh khoản",
    "double-bottom": "Hai đáy: xác nhận đảo chiều đúng cách thay vì bắt đáy sớm",
    "sr-flip": "Hỗ trợ thành kháng cự (S/R flip): vùng giá đổi vai sau khi bị phá",
    "pinbar": "Nến pin bar: chỉ có giá trị khi xuất hiện đúng vùng thanh khoản",
    "engulfing": "Nến nhấn chìm: tín hiệu mạnh hay bẫy tuỳ vị trí xuất hiện",
    "inside-bar": "Inside bar: nén giá trước cú bùng nổ – vào theo hướng nào",
    "consolidation-breakout": "Nén giá (tích luỹ hẹp dần) trước cú breakout thật",
    "higher-low": "Đáy cao dần – đỉnh cao dần: đọc xu hướng chỉ bằng mắt thường",
    "exhaustion": "Dấu hiệu cạn lực của xu hướng: nến nhỏ dần, râu dài, không phá được đỉnh",
    "momentum-candle": "Nến động lượng lớn: đuổi theo hay chờ hồi",
    # --- Đa khung thời gian & thời điểm (8)
    "mtf": "Phân tích đa khung: khung lớn cho hướng, khung nhỏ cho điểm vào",
    "htf-poi": "Vùng quan tâm khung lớn (POI): chỉ tìm lệnh khi giá chạm vùng khung lớn",
    "killzone-london": "Phiên London: vì sao cú quét thanh khoản phiên Á hay xảy ra đầu phiên Âu",
    "killzone-ny": "Phiên New York: cú đảo chiều sau khi quét đỉnh/đáy phiên London",
    "asian-range": "Biên độ phiên Á: vùng thanh khoản cho cả ngày giao dịch",
    "news-spike": "Giao dịch quanh tin mạnh (NFP, CPI): cú giật 2 chiều quét cả 2 phe",
    "daily-bias": "Xác định thiên hướng ngày (daily bias) trước khi mở biểu đồ khung nhỏ",
    "weekly-open": "Giá mở cửa tuần/ngày làm mốc cân bằng – trên mốc ưu tiên mua, dưới ưu tiên bán",
    # --- Quản lý rủi ro & vốn (10)
    "sl-placement": "Đặt stop loss ở đâu cho đúng: dưới đáy quét chứ không phải dưới đáy gần nhất",
    "rr": "Tỉ lệ rủi ro/lợi nhuận: vì sao thắng 40% vẫn có lãi với RR 1:3",
    "position-size": "Tính khối lượng lệnh theo % rủi ro thay vì theo cảm tính",
    "partial-tp": "Chốt lời từng phần: TP1 tại thanh khoản gần, phần còn lại chạy theo cấu trúc",
    "breakeven": "Dời stop loss về hoà vốn: sớm quá thì bị quét, muộn quá thì mất lãi",
    "trailing-structure": "Trailing stop theo cấu trúc: dời SL dưới mỗi đáy cao dần mới",
    "drawdown": "Chuỗi thua liên tiếp là bình thường: rủi ro 1% giúp sống sót qua 10 lệnh thua",
    "tp-liquidity": "Đặt chốt lời tại vùng thanh khoản đối diện thay vì số pip cố định",
    "overleverage": "Đòn bẩy cao và khối lượng lớn: một cú quét đủ cháy tài khoản",
    "no-trade": "Không vào lệnh cũng là một vị thế: khi nào nên đứng ngoài",
    # --- Tâm lý & sai lầm thường gặp (8)
    "fomo": "Đuổi theo giá (FOMO): vì sao vào lệnh ở cuối con sóng làm RR rất kém",
    "revenge-trade": "Gỡ lệnh (revenge trading) sau khi bị quét stop loss",
    "early-entry": "Vào lệnh quá sớm khi chưa có xác nhận – lỗi kinh điển của người mới",
    "moving-sl": "Nới stop loss khi giá chạy ngược – thói quen phá tài khoản",
    "counter-trend": "Bắt đỉnh bắt đáy ngược xu hướng mạnh",
    "overtrading": "Giao dịch quá nhiều: ít setup đẹp hơn nhiều lệnh tạm được",
    "cut-winners": "Chốt lời quá sớm, gồng lỗ quá lâu – bất đối xứng giết tài khoản",
    "journal": "Nhật ký giao dịch: cách đơn giản để thấy mình sai ở đâu",
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
    return random.choice(left)                 # xen kẽ các mảng; trong 1 vòng không chủ đề nào lặp lại


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
    titles = _state().get("titles", {})
    old = titles.get(topic, [])
    recent = [t for k, v in titles.items() if k != topic for t in v][-70:]
    again = ("\nChủ đề này ĐÃ làm các video: " + " | ".join(old[-6:]) +
             "\n→ BẮT BUỘC chọn GÓC MỚI hoàn toàn (sai lầm hay gặp, so sánh đúng/sai, tình huống khác, "
             "chiều ngược lại mua/bán, mẹo nâng cao…): tiêu đề, hook và hình dạng giá khác hẳn.") if old else ""
    avoid = ("\nCác video gần đây của kênh (KHÔNG lặp lại ý chính, hook, ví dụ của các video này): "
             + " | ".join(recent)) if recent else ""
    user = (f"Chủ đề: {brief}\nslug: {topic}{again}{avoid}\nViết kịch bản theo đúng định dạng. Nhớ: phần say là lời đọc "
            "tự nhiên, text là chữ trên màn hình (có thể ngắn gọn hơn say).")
    spec = generate_json(SYSTEM, user, {"type": "object"})
    for c in (spec.get("charts") or {}).values():      # nến minh họa mỗi lần một khác
        c["seed"] = random.randint(1, 10_000)
    spec["slug"] = topic
    spec["topic"] = topic
    return validate(spec)
