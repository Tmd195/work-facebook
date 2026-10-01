"""Báo cáo về Telegram cho anh sau mỗi thao tác."""
import requests

from src.config import env


def send(text: str) -> bool:
    token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print(f"[Telegram chưa cấu hình] {text}")
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          data={"chat_id": chat, "text": text, "disable_web_page_preview": "false"}, timeout=30)
        return r.ok
    except requests.RequestException as exc:
        print(f"[Telegram lỗi] {exc}")
        return False


def need_fix(text: str) -> bool:
    """Lỗi hệ thống không tự sửa được - cần anh mở máy để em xử lý."""
    return send(f"{text}\n\n🖥 Bật Máy để sửa đổi")


def send_preview(title: str, caption: str, images: list) -> bool:
    """Gửi bản xem trước đầy đủ: album ảnh (tối đa 10) + toàn bộ caption (tách nhiều tin nếu dài)."""
    import json
    token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print(f"[Telegram chưa cấu hình] {title}")
        return False
    ok = send(title)
    try:
        imgs = list(images)[:10]
        if len(imgs) == 1:
            with open(imgs[0], "rb") as f:
                requests.post(f"https://api.telegram.org/bot{token}/sendPhoto", data={"chat_id": chat},
                              files={"photo": f}, timeout=120)
        elif imgs:
            files = {f"p{i}": open(p, "rb") for i, p in enumerate(imgs)}
            media = [{"type": "photo", "media": f"attach://p{i}"} for i in range(len(imgs))]
            requests.post(f"https://api.telegram.org/bot{token}/sendMediaGroup",
                          data={"chat_id": chat, "media": json.dumps(media)}, files=files, timeout=180)
            for f in files.values():
                f.close()
    except requests.RequestException as exc:
        print(f"[Telegram lỗi gửi ảnh] {exc}")
        ok = False
    for i in range(0, len(caption), 4000):          # Telegram giới hạn 4096 ký tự/tin
        ok = send(caption[i:i + 4000]) and ok
    return ok


def find_chat_id() -> str | None:
    """Lấy chat id từ tin nhắn gần nhất anh gửi cho bot."""
    r = requests.get(f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/getUpdates", timeout=30).json()
    for upd in reversed(r.get("result", [])):
        msg = upd.get("message") or upd.get("edited_message")
        if msg:
            return str(msg["chat"]["id"])
    return None
