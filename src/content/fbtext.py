"""Làm sạch chữ trước khi đăng Facebook (Facebook không hỗ trợ markdown / in đậm)."""
import re


def render(text: str) -> str:
    """Bỏ các dấu markdown AI lỡ dùng (**đậm**, __gạch__, # tiêu đề) nhưng giữ nguyên chữ."""
    text = re.sub(r"\*\*(.+?)\*\*", lambda m: m.group(1), text)
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    return text.replace("**", "").replace("__", "")
