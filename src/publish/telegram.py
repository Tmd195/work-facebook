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


def find_chat_id() -> str | None:
    """Lấy chat id từ tin nhắn gần nhất anh gửi cho bot."""
    r = requests.get(f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/getUpdates", timeout=30).json()
    for upd in reversed(r.get("result", [])):
        msg = upd.get("message") or upd.get("edited_message")
        if msg:
            return str(msg["chat"]["id"])
    return None
