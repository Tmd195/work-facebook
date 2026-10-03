"""AI viết Reels STORYTELLING về nghề IB (Page Decode Global & Partner, Chủ nhật).

Cấu trúc: hook tình huống/nỗi đau → diễn biến → bước ngoặt → bài học. Mỗi câu kèm từ khoá tiếng Anh để hệ thống
tự tìm video nền (B-roll) khớp hình ảnh. Không số thu nhập, không hứa hẹn, không nêu chính sách hoa hồng.
"""
import json
import random

from src.config import STATE
from src.content.llm import generate_json

TOPICS = [
    "Đại lý có 200 khách năm đầu nhưng mất gần hết sau 3 tháng – vì không dạy khách quản lý vốn",
    "Từ một nhóm Zalo 30 người thành cộng đồng giao dịch bền vững – nhờ chia sẻ kiến thức đều đặn",
    "Đại lý chạy theo khách 'vào lệnh to' và bài học về khách hàng bền vững",
    "Ngày khách cháy tài khoản và cách một đại lý giữ được niềm tin",
    "Vì sao đại lý giỏi nhất thường nói 'không' với khách nhiều hơn",
    "Đại lý mới: 90 ngày đầu nên làm gì để không bỏ cuộc",
    "Chọn sàn cho khách: câu chuyện về pháp lý và sự an tâm",
    "Khi thị trường biến động mạnh: đại lý gọi cho khách trước hay im lặng",
    "Từ người giao dịch thua lỗ thành người hướng dẫn: hành trình của một đại lý",
    "Bài học từ đại lý hứa lợi nhuận với khách – và cái giá phải trả",
    "Xây kênh nội dung để khách tự tìm đến thay vì đi chào mời",
    "Đại lý làm một mình và đại lý xây đội: bước chuyển khó nhất",
    "Chăm sóc khách sau khi mở tài khoản: phần việc đa số đại lý bỏ quên",
    "Cuộc gọi lúc 2 giờ sáng: kỷ luật và giới hạn của nghề đại lý",
    "Vì sao minh bạch rủi ro lại giúp đại lý giữ khách lâu hơn",
    "Một buổi chia sẻ kiến thức miễn phí đã thay đổi cách đại lý tìm khách",
]
FILE = STATE / "story_reels.json"

SYSTEM = """Bạn là biên kịch Reels kể chuyện (storytelling) cho Page "Decode Global & Partner" – kênh dành cho người làm
đại lý IB forex/vàng tại Việt Nam. Giọng kể trầm, chậm, có cảm xúc, như kể chuyện nghề thật; xưng "anh ấy/chị ấy"
cho nhân vật (một đại lý giấu tên – KHÔNG phải người thật cụ thể, không gắn với sàn nào), nói với người xem là "bạn".
CẤU TRÚC 45-75 giây, 8-11 câu:
 1. HOOK (câu 1-2): tình huống/nỗi đau cụ thể, gây tò mò ngay 3 giây đầu.
 2. DIỄN BIẾN (3-4 câu): chuyện gì xảy ra, sai ở đâu.
 3. BƯỚC NGOẶT (2-3 câu): nhận ra điều gì, thay đổi thế nào.
 4. BÀI HỌC (1-2 câu): rút ra cho người làm IB, câu cuối đọng lại, dễ nhớ.
QUY TẮC: không nêu số thu nhập/hoa hồng/chính sách, không hứa hẹn, không "làm giàu", không 18+, không kêu gọi comment;
luôn tôn trọng rủi ro của khách. Mỗi câu 10-22 từ.
Mỗi câu kèm "queries": 2-3 từ khoá TIẾNG ANH mô tả HÌNH ẢNH video nền khớp câu đó (cảnh cụ thể, dễ tìm trên kho video:
"man looking at trading screen at night", "city lights night", "handshake office", "phone call worried", "notebook writing",
"team meeting", "sunrise city"…). Không dùng từ khoá logo/thương hiệu/chữ."""

SCHEMA = {"type": "object", "properties": {
    "title": {"type": "string"}, "kicker": {"type": "string"},
    "beats": {"type": "array", "items": {"type": "object", "properties": {
        "text": {"type": "string"}, "say": {"type": "string"},
        "queries": {"type": "array", "items": {"type": "string"}}}, "required": ["text", "say", "queries"]}},
    "caption": {"type": "string"}, "hashtags": {"type": "array", "items": {"type": "string"}}},
    "required": ["title", "kicker", "beats", "caption", "hashtags"]}


def _state() -> dict:
    return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {"done": [], "titles": []}


def next_topic() -> str:
    st = _state()
    left = [t for t in TOPICS if t not in st["done"]] or TOPICS
    return random.choice(left)


def mark_done(topic: str, title: str = ""):
    st = _state()
    st["done"] = [t for t in st["done"] if t != topic] + [topic]
    if len(st["done"]) >= len(TOPICS):
        st["done"] = [topic]
    st["titles"] = (st.get("titles", []) + [title])[-40:]
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def write(topic: str | None = None) -> dict:
    topic = topic or next_topic()
    recent = _state().get("titles", [])[-10:]
    user = (f"Chủ đề câu chuyện: {topic}\nCác video gần đây (không lặp lại ý/hook): {recent}\n"
            "Trả về: title (tiêu đề video ≤ 9 từ, IN HOA), kicker (nhãn nhỏ ≤ 4 từ, vd. 'CÂU CHUYỆN NGHỀ IB'), "
            "beats [{text: câu hiện phụ đề, tô 1-2 cụm quan trọng bằng [y]...[/y]; say: câu đọc (giống text, bỏ ký hiệu); "
            "queries: 2-3 từ khoá tiếng Anh}], caption (60-110 từ: dòng đầu là tiêu đề IN HOA, kể tóm tắt + bài học, "
            "xuống dòng thoáng, không hashtag), hashtags (3-4).")
    s = generate_json(SYSTEM, user, SCHEMA)
    s["topic"] = topic
    s["beats"] = [b for b in s["beats"] if b.get("text")][:11]
    return s
