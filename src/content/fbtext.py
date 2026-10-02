"""Làm sạch chữ trước khi đăng Facebook (Facebook không hỗ trợ markdown / in đậm)."""
import re


def airy(text: str, max_len: int = 130) -> str:
    """Ngắt đoạn dài cho dễ đọc trên điện thoại: xuống dòng sau dấu kết câu (không cắt số thập phân 1.125),
    mỗi câu một dòng (2 câu rất ngắn thì ghép). Đoạn ngắn hoặc dòng liệt kê giữ nguyên."""
    out = []
    for para in text.split("\n"):
        if len(para) <= max_len:
            out.append(para)
            continue
        sents = re.split(r"(?<=[.!?…])\s+(?=[^\W\d_]|[\U0001F300-\U0001FAFF])", para)
        lines, cur = [], ""
        for s in sents:
            if cur and len(cur) + len(s) > 70:                # chỉ ghép khi 2 câu đều rất ngắn
                lines.append(cur)
                cur = s
            else:
                cur = f"{cur} {s}".strip()
        if cur:
            lines.append(cur)
        out.append("\n".join(lines))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))


def render(text: str) -> str:
    """Bỏ các dấu markdown AI lỡ dùng (**đậm**, __gạch__, # tiêu đề) nhưng giữ nguyên chữ."""
    text = re.sub(r"\*\*(.+?)\*\*", lambda m: m.group(1), text)
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    return text.replace("**", "").replace("__", "")
