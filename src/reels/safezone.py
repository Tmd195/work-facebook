"""Vùng giao diện Facebook Reels che lên video 1080×1920 (đo theo app điện thoại):
- thanh trên: chữ "Reels" + nút camera
- cột phải: Like / Comment / Share / ⋯ (+ ảnh nhạc)
- đáy: ảnh đại diện + tên Page + nút Theo dõi, 1-2 dòng caption + "Xem thêm", dòng nhạc
Nội dung quan trọng (chữ, nhãn giá, biểu đồ, logo) phải nằm NGOÀI các vùng này. Dùng cho bộ dựng + bộ kiểm tra (qa).
"""
from PIL import Image, ImageDraw

W, H = 1080, 1920
TOP = (0, 0, W, 150)
RIGHT = (930, 1000, W, 1640)
BOTTOM = (0, 1560, W, H)
ZONES = [TOP, RIGHT, BOTTOM]

# vùng an toàn cho nội dung chính
SAFE_TOP, SAFE_BOTTOM, SAFE_RIGHT_LOW = 160, 1545, 915     # dưới y=1000 nội dung không vượt quá x=915


def mock(img: Image.Image, alpha: int = 150) -> Image.Image:
    """Phủ mô phỏng giao diện Reels (xám mờ + biểu tượng) để xem/AI kiểm tra phần nào bị che."""
    out = img.convert("RGBA").resize((W, H)) if img.size != (W, H) else img.convert("RGBA")
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for z in ZONES:
        d.rectangle(z, fill=(120, 120, 120, alpha))
    for k, y in enumerate((1090, 1230, 1370, 1500)):          # nút like/comment/share/⋯
        d.ellipse([975, y, 1045, y + 70], fill=(255, 255, 255, 230))
    d.ellipse([30, 1590, 110, 1670], fill=(255, 255, 255, 230))   # ảnh đại diện Page
    d.rectangle([130, 1610, 520, 1650], fill=(255, 255, 255, 230))  # tên Page
    d.rectangle([30, 1700, 900, 1735], fill=(255, 255, 255, 200))   # caption
    d.rectangle([30, 1750, 600, 1785], fill=(255, 255, 255, 200))
    out.alpha_composite(lay)
    return out
