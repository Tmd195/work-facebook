"""Ngôn ngữ nội dung CÔNG KHAI của từng Page (chữ trên ảnh/video, caption do AI viết).

job.yaml: lang: en | vi (mặc định vi), tz_label: "GMT+8" (ghi chú giờ trên ảnh).
Chữ cố định viết bằng tiếng Việt trong code, bọc t("..."); bản tiếng Anh tra trong EN. Tin nhắn Telegram gửi anh
vẫn bằng tiếng Việt (không qua t()).
"""
from datetime import date

from src.config import CONFIG

LANG = (CONFIG.get("lang") or "vi").lower()
EN_MODE = LANG == "en"
TZ_LABEL = CONFIG.get("tz_label") or ("giờ Việt Nam" if not EN_MODE else "local time")

EN = {
    # --- giấy phép
    "GIẤY PHÉP {index}/{total}": "LICENSE {index}/{total}",
    "PHÁP LÝ TẬP ĐOÀN CWG MARKETS": "CWG MARKETS GROUP REGULATION",
    "Pháp nhân": "Entity", "Địa chỉ / thông tin": "Address / details", "Trạng thái": "Status",
    "TỰ TRA CỨU TRONG 30 GIÂY": "VERIFY IT YOURSELF IN 30 SECONDS",
    "Điểm WikiFX /10": "WikiFX score /10",
    "Mỗi pháp nhân được cấp phép tại khu vực tương ứng. Giao dịch CFD/Forex có rủi ro cao, bạn có thể mất toàn bộ vốn.":
        "Each entity is licensed in its respective jurisdiction. CFD/Forex trading carries high risk; you may lose all your capital.",
    # --- tin nóng
    "TIN NÓNG": "BREAKING NEWS", "Mức ảnh hưởng: {level}": "Impact: {level}",
    "DB": "F", "THỰC TẾ": "ACTUAL", "DỰ BÁO": "FORECAST", "KỲ TRƯỚC": "PREVIOUS",
    "TÁC ĐỘNG TỚI THỊ TRƯỜNG": "MARKET IMPACT",
    "Thông tin thị trường mang tính tham khảo, không phải khuyến nghị đầu tư. Giao dịch CFD/Forex có rủi ro cao.":
        "Market information for reference only, not investment advice. CFD/Forex trading carries high risk.",
    # --- bản tin sáng / bảng xu hướng
    "BẢN TIN ĐẦU NGÀY": "MORNING BRIEFING", "Cập nhật trước giờ giao dịch": "Before the trading day starts",
    "LỊCH TIN QUAN TRỌNG HÔM NAY": "KEY EVENTS TODAY",
    "Không có tin tác động mạnh trong ngày.": "No high-impact events today.",
    "BẢNG TIN XU HƯỚNG": "TREND BOARD", "Góc nhìn tổng quan trong ngày": "Today's market overview",
    "SẢN PHẨM": "MARKET", "XU HƯỚNG": "TREND", "VÙNG HỖ TRỢ": "SUPPORT ZONE", "VÙNG KHÁNG CỰ": "RESISTANCE ZONE",
    "TĂNG": "UP", "GIẢM": "DOWN", "ĐI NGANG": "SIDEWAYS",
    "Góc nhìn tổng quan, không phải tín hiệu giao dịch. Giao dịch CFD/Forex có rủi ro cao, bạn có thể mất toàn bộ vốn.":
        "General outlook, not a trading signal. CFD/Forex trading carries high risk; you may lose all your capital.",
    # --- vĩ mô
    "PHÂN TÍCH VĨ MÔ": "MACRO ANALYSIS", "NỘI DUNG CHÍNH": "KEY POINTS",
    "Phân tích mang tính tham khảo, không phải khuyến nghị đầu tư. Giao dịch CFD/Forex có rủi ro cao.":
        "Analysis for reference only, not investment advice. CFD/Forex trading carries high risk.",
    "So sánh biến động 3 tháng (%)": "3-month performance comparison (%)",
    # --- cuối tuần
    "TỔNG KẾT TUẦN": "WEEKLY RECAP", "8 sản phẩm chính": "8 key markets",
    "Mở {o} · Đóng {c}": "Open {o} · Close {c}", "ĐIỂM NHẤN TUẦN": "WEEK HIGHLIGHTS",
    "Số liệu giá đóng cửa tuần (tham khảo). Giao dịch CFD/Forex có rủi ro cao, bạn có thể mất toàn bộ vốn.":
        "Weekly closing prices (reference). CFD/Forex trading carries high risk; you may lose all your capital.",
    "TOP 5 TIN CỦA TUẦN": "TOP 5 STORIES OF THE WEEK", "Xếp theo mức tác động": "Ranked by market impact",
    "Tổng hợp tin từ nhiều nguồn, mang tính tham khảo. Giao dịch CFD/Forex có rủi ro cao.":
        "Compiled from multiple sources, for reference only. CFD/Forex trading carries high risk.",
    "DÒNG TIỀN LỚN · COT": "BIG MONEY FLOWS · COT", "CFTC · số liệu tới {d}": "CFTC · data as of {d}",
    "MUA RÒNG": "NET LONG", "BÁN RÒNG": "NET SHORT", "{side} {n} HĐ": "{side} {n} contracts",
    "so với tuần trước": "vs last week",
    "Nguồn: CFTC Commitments of Traders (nhóm quỹ đầu cơ non-commercial). Thông tin tham khảo, không phải khuyến nghị đầu tư.":
        "Source: CFTC Commitments of Traders (non-commercial speculators). For reference only, not investment advice.",
    "LỊCH TIN TUẦN MỚI": "NEXT WEEK'S CALENDAR", "Không có tin tác động mạnh": "No high-impact events",
    "Lịch có thể thay đổi theo thông báo của cơ quan công bố. Giao dịch CFD/Forex có rủi ro cao.":
        "Schedule may change per official announcements. CFD/Forex trading carries high risk.",
    "PHÂN TÍCH KHUNG TUẦN": "WEEKLY CHART ANALYSIS", "CHỦ ĐỀ VĨ MÔ TUẦN TỚI": "MACRO THEME FOR THE WEEK AHEAD",
    "Góc nhìn tuần": "Weekly outlook", "Tuần {a}–{b}": "Week {a}–{b}", "Tuần mới · {d}": "New week · {d}",
    "Chủ nhật · {d}": "Sunday · {d}",
    "Vàng": "Gold", "Dầu WTI": "WTI Oil",
    # --- Reels kiến thức
    "Dữ liệu minh họa — không phải giá thực": "Illustrative data — not real prices",
    "Kiến thức giao dịch mỗi ngày": "Daily trading education",
    "THEO DÕI PAGE": "FOLLOW THE PAGE",
}

_DAYS = {"vi": ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"],
         "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}

# quy tắc ngôn ngữ nối vào cuối lời nhắc của AI (lời nhắc gốc viết tiếng Việt)
LANG_RULE = "" if not EN_MODE else """

OUTPUT LANGUAGE – BẮT BUỘC: viết TOÀN BỘ nội dung trả về (title, caption, headline, slides, points, label, text, say…)
bằng TIẾNG ANH tự nhiên, chuyên nghiệp, dễ hiểu cho trader/đối tác IB ở Đông Nam Á (Philippines, Thái Lan…).
Các nhãn liệt kê trong yêu cầu (vd. RẤT CAO / CAO / TRUNG BÌNH, "Thứ X · dd/mm") đổi sang tiếng Anh tương đương
(VERY HIGH / HIGH / MEDIUM, "Mon · Oct 05"). Giờ ghi theo """ + TZ_LABEL + """. Không nhắc tới Việt Nam."""


def t(text: str, **kw) -> str:
    s = EN.get(text, text) if EN_MODE else text
    return s.format(**kw) if kw else s


def day(d: date) -> str:
    """03/10 (vi) – Oct 03 (en)."""
    return d.strftime("%b %d") if EN_MODE else d.strftime("%d/%m")


def weekday(d: date) -> str:
    return _DAYS["en" if EN_MODE else "vi"][d.weekday()]
