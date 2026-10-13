"""AI viết kịch bản 1 tập REELS EDUCATION (Page Duy Thái Đặng) theo lộ trình knowledge/edu_reels.yaml."""
import json

import yaml

from src.config import ROOT, STATE
from src.content.llm import generate_json
from src.reels.edu import script as edu

PLAN = ROOT / "knowledge" / "edu_reels.yaml"
FILE = STATE / "edu_thai.json"


def episodes() -> list[dict]:
    data = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    out = []
    for lv in data["levels"]:
        for ep in lv["episodes"]:
            out.append({"no": len(out) + 1, "level": lv["name"], **ep})
    return out


def _state() -> dict:
    return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {"done": 0, "titles": []}


def next_episode() -> dict | None:
    eps = episodes()
    k = _state()["done"]
    return eps[k] if k < len(eps) else None


def mark_done(no: int, title: str = ""):
    st = _state()
    st["done"] = max(st["done"], int(no))
    if title:
        st["titles"] = (st.get("titles") or []) + [title]
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


SYSTEM = """Bạn là biên kịch REELS EDUCATION cho Page "Duy Thái Đặng" (trader vàng XAUUSD, Việt Nam).
Đây là CHUỖI BÀI HỌC đánh số tập, đi từ cơ bản → nâng cao → chuyên sâu → hệ thống → logic lệnh.
Giọng thân thiện xưng "mình"/"bạn", câu ngắn, nhịp nhanh, mỗi câu gắn với 1 chuyển động trên biểu đồ minh hoạ hoặc 1 thẻ.

CẤU TRÚC 50-75 GIÂY (7-9 cảnh, tổng phần say TỐI ĐA 190 từ – dài hơn người xem lướt qua):
 1. MỞ ĐẦU (1 cảnh): câu hook đánh vào nỗi đau/tò mò của trader vàng + thẻ title kiểu poster
    (kicker "Tập NN · <cấp độ>", title 2 dòng NGẮN ≤ 12 ký tự mỗi dòng, sub = tên khái niệm).
 2. GIẢI THÍCH (4-6 cảnh): chia chương rõ (tag), ví dụ cụ thể trên VÀNG (giá, lot, đô).
 3. CHỐT (1-2 cảnh): thẻ check "Nhớ 3 điều" + 1 lời khuyên quản lý rủi ro.
 (Hệ thống tự thêm cảnh kết "Theo dõi + tập sau" – KHÔNG tự viết cảnh kêu gọi theo dõi.)

QUY TẮC NỘI DUNG:
 - Kiến thức ĐÚNG chuẩn, nói đơn giản đúng cấp độ của tập; không nhồi kiến thức của tập sau.
 - Vàng: 1 giá = 1 đô = 10 pip; 1 lot = 100 ounce = 100 đô mỗi giá. Biểu đồ là MINH HOẠ – không nói giá thật hiện tại.
 - Không hứa lợi nhuận, không "chắc thắng", không kêu gọi bình luận/inbox, không nhắc sàn, không 18+.
 - Chú thích phải khớp hình (quét đáy dùng sweep_low + arrow/x tại "low"; FVG/OB gắn vào đoạn đẩy mạnh SAU cú quét).
 - Mỗi cảnh có reveal hoặc marks hoặc card – không để cảnh "đứng hình". Tối đa 2 cụm tô màu/câu.
 - Phần "say": số viết bằng CHỮ SỐ (0,1 lot; RR 1:2; 2.7R; giá 4185,64) – hệ thống tự đổi sang cách đọc chuẩn.
   Dùng "nhá" thay "nhé". Thuật ngữ tiếng Anh giữ nguyên chữ.
""" + edu.SPEC.replace("đơn vị giá ~ quanh 110", "đơn vị giá ~ quanh 110 (minh hoạ)")


def write(ep: dict, nxt: dict | None) -> dict:
    done = _state().get("titles", [])[-30:]
    user = (f"TẬP {ep['no']:02d} – cấp độ {ep['level']}: {ep['title']}\nÝ chính phải dạy: {ep['points']}\n"
            + (f"Các tập trước (không lặp lại): {' | '.join(done)}\n" if done else "")
            + "Viết kịch bản đúng định dạng JSON. Thêm trường \"caption\": caption Facebook gồm dòng tiêu đề "
              f"\"📚 REELS EDUCATION · Tập {ep['no']:02d}: <tên tập>\", 1 câu mở, 3-4 gạch đầu dòng 🔹, 1 ví dụ 📌, "
              "1 dòng ✅ chốt" + (f", dòng cuối \"▶️ Tập {nxt['no']:02d}: {nxt['title']}\"" if nxt else "") + ". KHÔNG hashtag.")
    spec = generate_json(SYSTEM, user, {"type": "object"})
    for c in (spec.get("charts") or {}).values():
        c["seed"] = 7 + ep["no"] * 13
    spec["slug"] = f"ep{ep['no']:02d}"
    spec["topic"] = f"Tập {ep['no']:02d}: {ep['title']}"
    spec["title"] = spec["topic"]
    spec["episode"] = {"no": ep["no"], "level": ep["level"], "next": nxt["title"] if nxt else None}
    spec["thumb"] = spec.get("thumb") or {"kicker": f"Tập {ep['no']:02d} · {ep['level']}", "title": ep["title"].upper()}
    if nxt:
        spec["cta"] = f"Theo dõi [y]Duy Thái Đặng[/y]: tập sau nói về [y]{nxt['title']}[/y]."
        spec["cta_say"] = f"Theo dõi Duy Thái Đặng nhá. Tập sau mình nói về {nxt['title']}."
    return edu.validate(spec)
