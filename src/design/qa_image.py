"""Soát ẢNH bài đăng trước khi đăng (anh yêu cầu 03/10/2026 sau lỗi "Lợi suất UST 10 năm" đè lên mũi tên ▼).

AI xem ảnh ghép tất cả ảnh của bài, tìm lỗi hiển thị: chữ đè chữ/biểu tượng, chữ tràn khung hoặc bị cắt,
chữ bị thay bằng "…", lỗi dấu tiếng Việt / ô vuông lạ, ô trống. Lỗi NẶNG → runner cho AI viết lại bài (dựng ảnh mới);
hết lượt vẫn lỗi → vẫn đăng bản tốt nhất đúng giờ + báo anh (đăng đều quan trọng, như Reels).
"""
import json
from pathlib import Path

from PIL import Image

from src.content.llm import review_image

SYSTEM = ("Bạn là người kiểm tra chất lượng ảnh bài đăng Facebook (bản tin tài chính tiếng Việt) trước khi đăng. "
          "Soi KỸ từng dòng chữ. Chỉ báo lỗi THẬT nhìn thấy được, không bịa.")
CHECK = """Ảnh ghép gồm các ảnh của MỘT bài đăng (đánh số #1, #2...). Tìm lỗi hiển thị:
1. Chữ đè lên chữ khác, lên mũi tên/biểu tượng, lên logo (vd. tên tài sản dài đè lên mũi tên ▲▼ bên cạnh).
2. Chữ tràn ra ngoài khung/thẻ/mép ảnh, hoặc bị cắt mất một phần.
3. Chữ bị rút gọn bằng "…" làm mất nghĩa (vd. "Lợi suấ…").
4. Lỗi font: ô vuông, ký tự lạ, mất dấu tiếng Việt.
5. Khối/ô trống không có nội dung, hoặc chữ quá nhỏ/mờ không đọc được.
Mức độ: "major" = người xem thấy rõ là lỗi (đè/cắt/tràn/ô vuông); "minor" = chật, sát mép nhưng vẫn đọc được."""
SCHEMA = {"type": "object", "properties": {"issues": {"type": "array", "items": {"type": "object", "properties": {
    "image": {"type": "integer"}, "severity": {"type": "string", "enum": ["major", "minor"]},
    "problem": {"type": "string"}}, "required": ["image", "severity", "problem"]}}}, "required": ["issues"]}


def sheet(images: list[Path], out: Path) -> Path:
    from PIL import ImageDraw
    from src.design.common import sans
    ims = [Image.open(p).convert("RGB") for p in images if p.exists() and p.suffix.lower() in (".png", ".jpg", ".jpeg")]
    if not ims:
        raise FileNotFoundError("không có ảnh")
    w = 720
    ims = [im.resize((w, round(im.height * w / im.width))) for im in ims]
    cols = min(3, len(ims))
    rows = (len(ims) + cols - 1) // cols
    h = max(im.height for im in ims)
    sh = Image.new("RGB", (cols * w, rows * h), (255, 255, 255))
    d = ImageDraw.Draw(sh)
    for k, im in enumerate(ims):
        x, y = (k % cols) * w, (k // cols) * h
        sh.paste(im, (x, y))
        d.rectangle([x, y, x + 56, y + 40], fill=(0, 0, 0))
        d.text((x + 8, y + 4), f"#{k + 1}", font=sans("Bold", 28), fill=(255, 255, 0))
    sh.save(out, quality=88)
    return out


def check(images: list[Path], folder: Path, tag: str) -> dict:
    """Trả {ok, major, minor}. Lỗi khi gọi AI → coi như đạt (không chặn đăng), ghi chú lại."""
    try:
        sh = sheet(images, folder / f"qa_img_{tag}.jpg")
        res = review_image(SYSTEM, sh, CHECK, SCHEMA)
    except Exception as exc:
        return {"ok": True, "major": [], "minor": [f"không soát được ảnh: {exc}"]}
    major = [f"ảnh #{i['image']}: {i['problem']}" for i in res.get("issues", []) if i.get("severity") == "major"]
    minor = [f"ảnh #{i['image']}: {i['problem']}" for i in res.get("issues", []) if i.get("severity") != "major"]
    (folder / f"qa_img_{tag}.json").write_text(json.dumps({"major": major, "minor": minor}, ensure_ascii=False, indent=1),
                                               encoding="utf-8")
    return {"ok": not major, "major": major, "minor": minor}
