"""Bài Chiến lược XAUUSD chuyên sâu - 2 bài/ngày:
- 'ae' (10:00): kế hoạch cho phiên Á - Âu
- 'us' (trước phiên Mỹ): kế hoạch phiên Mỹ, dựa trên diễn biến thực tế phiên Á & Âu

Cấu trúc 8 phần: luận điểm → bối cảnh vĩ mô & tin tức → đa khung D1/H4/H1 → diễn biến phiên → bản đồ vùng giá
→ 2 kịch bản (chính/phụ, vùng vào, SL, TP1-3, điều kiện kích hoạt, điều kiện vô hiệu) → quản lý rủi ro → kết luận.
"""
import json
import re

from src.content import llm

HASHTAGS = "#XAUUSD #giavang #gold #forex #chienluocvang"
DISCLAIMER = ("⚠️ Đây là góc nhìn cá nhân của Thái, không phải 1 lời khuyên đầu tư. Hãy tự chịu trách nhiệm "
              "với mọi quyết định của bản thân tại thời điểm hiện tại cũng như tương lai.")

SYSTEM_PROMPT = """Bạn là chuyên viên phân tích vàng (XAUUSD) của một Facebook Page cho trader Việt Nam.
Nhiệm vụ: viết BÀI CHIẾN LƯỢC CHUYÊN SÂU cho phiên giao dịch được giao, dựa trên khối DỮ LIỆU (giá thật, đa khung,
diễn biến các phiên, vùng giá hợp lưu, vĩ mô, lịch kinh tế) và tin tức bạn tự kiểm tra.

BƯỚC 1 - KIỂM TRA TIN TỨC (bắt buộc): dùng WebSearch tìm tin trong ~24 giờ qua THỰC SỰ làm giá vàng biến động: Fed và
phát biểu quan chức, số liệu kinh tế vừa ra, địa chính trị, dòng tiền ETF, ngân hàng trung ương... Chỉ dùng tin có nguồn
uy tín và đúng thời gian; ghi URL vào "sources". Số liệu từ tin tức phải đúng như nguồn.

CHỌN YẾU TỐ VĨ MÔ - không liệt kê mặc định:
- Trong DỮ LIỆU "vĩ_mô", mỗi chỉ số có z_1d / z_hôm_trước (biến động hôm nay / phiên trước so với bình thường 20 ngày;
  |z| ≥ 1 là bất thường), corr_vàng_20d (tương quan với vàng 20 ngày), vai_trò và đáng_chú_ý.
  vai_trò "đồng pha" (bạc) chỉ dùng để xác nhận xu hướng của vàng, KHÔNG phải nguyên nhân. CHỈ phân tích chỉ số có đáng_chú_ý = true, hoặc chỉ số gắn trực tiếp với tin trong ngày.
- Với mỗi yếu tố được chọn, giải thích cơ chế tác động lên vàng và dẫn tương quan thực tế (ví dụ "20 ngày qua vàng đi
  ngược lợi suất, tương quan -0.6"). Yếu tố bình thường thì bỏ qua, hoặc gộp 1 câu "các yếu tố khác ổn định".
- Nếu hôm nay không có yếu tố vĩ mô nào đáng chú ý, nói rõ: giá đang chủ yếu chạy theo kỹ thuật / dòng tiền trong phiên.
- KHÔNG đưa so sánh lịch sử ("cao nhất kể từ năm...") trừ khi ít nhất 2 nguồn uy tín cùng xác nhận.

BƯỚC 2 - PHÂN TÍCH theo trạng_thái_thị_trường và hệ_thống_áp_dụng trong DỮ LIỆU:
- Đi từ khung lớn xuống khung nhỏ: D1 (xu hướng trung hạn) → H4 (cấu trúc, nhịp hồi/điều chỉnh) → H1 (động lượng, điểm vào).
- Với bài phiên Mỹ: đánh giá phiên Á và Âu đã làm gì (biên độ, hướng, có quét đỉnh/đáy phiên Á không, đóng cửa ở đâu)
  và điều đó gợi ý gì cho phiên Mỹ. Với bài phiên Á-Âu: tóm tắt phiên Mỹ hôm qua và phần đầu phiên Á.
- Kịch bản chính đi THUẬN trạng thái thị trường; kịch bản phụ là kịch bản ngược lại, chỉ khi có điều kiện rõ.

QUY TẮC GIÁ (bắt buộc, code sẽ kiểm tra):
- Mọi mức giá vàng trong scenarios, levels và trong bài viết phải nằm trong (hoặc là biên của) một vùng trong "vùng_giá",
  hoặc là số có sẵn trong DỮ LIỆU. Không tự tạo mức giá.
- Vùng vào lệnh "entry" = [lo, hi] lấy từ 1 vùng (hoặc 2 vùng liền kề). SELL: sl > entry_hi ≥ entry_lo > tp1 > tp2 > tp3.
  BUY: sl < entry_lo ≤ entry_hi < tp1 < tp2 < tp3. SL đặt ngoài vùng hợp lưu tiếp theo (không quá sát).
- Ưu tiên vùng có "hợp_lưu" cao. Viết giá vàng dạng 4,178 hoặc 4178.5 (dấu chấm thập phân).

VĂN PHONG: chuyên nghiệp, mạch lạc, có lập luận "vì sao"; xưng "anh em"; không hô hào, không hứa lợi nhuận,
không dùng "kèo", "chắc chắn". Không dùng #, bảng. Emoji vừa phải làm tiêu đề mục. Facebook không hiển thị markdown: KHÔNG dùng ** hay chữ in đậm.

"post" (450-700 từ) theo đúng 8 mục:
1. Dòng đầu "🟡 CHIẾN LƯỢC XAUUSD | <PHIÊN> <thứ, ngày>" + dòng luận điểm chính (thiên hướng + điều kiện).
2. 🌍 Bối cảnh vĩ mô & tin tức: lợi suất, USD, tin vừa ra và sắp ra, tác động lên vàng.
3. 📊 Phân tích đa khung: D1 / H4 / H1.
4. ⏱ Diễn biến phiên (Á, Âu hoặc Mỹ hôm qua) và hàm ý.
5. 🗺 Bản đồ vùng giá: kháng cự gần, kháng cự mạnh, hỗ trợ gần, hỗ trợ mở rộng, mốc then chốt (thủng/vượt thì đổi kịch bản).
6. 🎯 Kịch bản: trình bày ĐÚNG mẫu sau, mỗi thông tin một dòng, 2 kịch bản ngăn bằng 1 dòng gạch:
Kịch bản chính
SELL Entry 4221.55 - 4225.3
SL 4247.5
TP1 4182.0
TP2 4152.4
TP3 4117.3
Kích hoạt: <điều kiện xác nhận>
Hủy kịch bản: <điều kiện vô hiệu>
---------------------------------------------------
Kịch bản phụ
BUY Entry ... (tương tự)
(Số trong mẫu chỉ để minh họa định dạng - dùng số thật từ vùng_giá.)
7. ⚠️ Quản lý rủi ro: 3-4 lưu ý cụ thể cho phiên này (giờ tin, không đuổi giá...).
8. ✅ Kết luận: thiên hướng chính + vùng quan sát then chốt, kết thúc bằng 1 câu hỏi mở cho anh em.
KHÔNG tự viết dòng miễn trừ trách nhiệm và hashtag.

Các trường khác dùng cho ảnh (ngắn gọn): title ≤ 70 ký tự (luận điểm), bias, macro_points (2-4 ý ≤ 90 ký tự, chỉ yếu tố
đang thực sự tác động),
mtf.d1/h4/h1 (mỗi khung 2-3 câu ≤ 260 ký tự), session_review (≤ 300 ký tự), levels, scenarios (đúng 2: 1 "chính", 1 "phụ";
trigger/invalidation ≤ 110 ký tự), risk (3-4 ý ≤ 90 ký tự), conclusion (≤ 220 ký tự)."""

_ZONE = {"type": "array", "items": {"type": "number"}}
SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "bias": {"type": "string", "enum": ["giảm", "tăng", "trung lập"]},
        "macro_points": {"type": "array", "items": {"type": "string"}},
        "mtf": {"type": "object", "properties": {"d1": {"type": "string"}, "h4": {"type": "string"},
                                                 "h1": {"type": "string"}}, "required": ["d1", "h4", "h1"]},
        "session_review": {"type": "string"},
        "levels": {"type": "object", "properties": {
            "resistance_near": _ZONE, "resistance_strong": _ZONE, "support_near": _ZONE, "support_extended": _ZONE,
            "pivot": {"type": "object", "properties": {"price": {"type": "number"}, "note": {"type": "string"}},
                      "required": ["price", "note"]}},
            "required": ["resistance_near", "resistance_strong", "support_near", "support_extended", "pivot"]},
        "scenarios": {"type": "array", "items": {"type": "object", "properties": {
            "side": {"type": "string", "enum": ["BUY", "SELL"]}, "role": {"type": "string", "enum": ["chính", "phụ"]},
            "entry": _ZONE, "sl": {"type": "number"}, "tp": _ZONE,
            "trigger": {"type": "string"}, "invalidation": {"type": "string"}},
            "required": ["side", "role", "entry", "sl", "tp", "trigger", "invalidation"]}},
        "risk": {"type": "array", "items": {"type": "string"}},
        "conclusion": {"type": "string"},
        "post": {"type": "string"},
        "sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "bias", "macro_points", "mtf", "session_review", "levels", "scenarios", "risk",
                 "conclusion", "post", "sources"],
}


# ===================================================================== kiểm tra số liệu

def _numbers(obj) -> list[float]:
    out = []
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, str):
        out += [float(x.replace(",", "")) for x in re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", obj)]
    elif isinstance(obj, dict):
        for v in obj.values():
            out += _numbers(v)
    elif isinstance(obj, list):
        for v in obj:
            out += _numbers(v)
    return out


def check(result: dict, data: dict) -> list[str]:
    zones = data["vùng_giá"]
    tol = max(1.0, 0.08 * data["ATR_H1"])
    in_zone = lambda x: any(z["lo"] - tol <= x <= z["hi"] + tol for z in zones)
    known = [v for v in _numbers({k: data[k] for k in ("đa_khung", "phiên_hôm_nay", "phiên_Mỹ_hôm_qua",
                                                       "giá_hiện_tại", "vĩ_mô")}) if v > 1000]
    grounded = lambda x: in_zone(x) or any(abs(x - k) <= tol for k in known)
    errors = []

    sc = result.get("scenarios") or []
    if len(sc) != 2 or {s["role"] for s in sc} != {"chính", "phụ"}:
        errors.append("cần đúng 2 kịch bản: 1 chính, 1 phụ")
    for s in sc:
        e, tp = sorted(s["entry"][:2]), s["tp"][:3]
        if len(e) != 2 or len(tp) != 3:
            errors.append(f"{s['side']}: entry cần [lo, hi], tp cần 3 mức")
            continue
        for name, x in [("entry", e[0]), ("entry", e[1]), ("sl", s["sl"])] + [(f"tp{i + 1}", t) for i, t in enumerate(tp)]:
            if not grounded(x):
                errors.append(f"{s['side']} {name}={x} không thuộc vùng giá nào")
        ok = (s["sl"] > e[1] >= e[0] > tp[0] > tp[1] > tp[2]) if s["side"] == "SELL" else \
             (s["sl"] < e[0] <= e[1] < tp[0] < tp[1] < tp[2])
        if not ok:
            errors.append(f"{s['side']}: thứ tự SL/entry/TP sai")
    for x in _numbers(result.get("levels")):
        if x > 1000 and not grounded(x):
            errors.append(f"mức {x} trong bản đồ vùng giá không có căn cứ")
    is_year = lambda x: x == int(x) and 1900 <= x <= 2100
    bad_post = sorted({x for x in _numbers(result.get("post", ""))
                       if 3000 < x < 10000 and not is_year(x) and not grounded(x)})
    if bad_post:
        errors.append(f"giá vàng trong bài không có căn cứ: {', '.join(f'{x:g}' for x in bad_post[:8])}")
    return errors


def generate(data: dict) -> dict | None:
    if not llm.available():
        print("  ! Chưa cấu hình AI - bỏ qua bài chiến lược")
        return None
    user = "DỮ LIỆU:\n" + json.dumps(data, ensure_ascii=False, indent=1)
    for attempt in range(2):
        try:
            result = llm.generate_json(SYSTEM_PROMPT, user, SCHEMA, web=True)
        except (llm.LLMError, json.JSONDecodeError) as exc:
            print(f"  ! AI lỗi: {exc}")
            return None
        errors = check(result, data)
        if not errors:
            return {**result, "writer": "ai"}
        print(f"  ! Lần {attempt + 1}: " + "; ".join(errors[:6]))
        user += ("\n\nBẢN TRƯỚC BỊ TỪ CHỐI vì:\n- " + "\n- ".join(errors) +
                 "\nGiữ nguyên phân tích, chỉ sửa các mức giá cho khớp vùng_giá.")
    return None


def finalize(post: str) -> str:
    from src.content.fbtext import render
    return f"{render(post).rstrip()}\n\n{DISCLAIMER}\n\n{HASHTAGS}"
