"""Báo cáo về Telegram cho anh sau mỗi thao tác."""
import requests

from src.config import CONFIG, IS_DEFAULT_JOB, env

# Job khác Page Thái: thêm nhãn tên Page ở đầu mỗi tin để anh biết tin của Page nào
PREFIX = "" if IS_DEFAULT_JOB else f"[{CONFIG['job'].get('name', CONFIG['job']['id'])}] "


def send(text: str) -> bool:
    text = PREFIX + text
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


def share(text: str) -> bool:
    """Kênh chia sẻ cho quản trị đối tác (chỉ tin đã đăng xong + link; KHÔNG gửi lỗi/xem trước).
    Bật cho Page nào thì đặt TELEGRAM_SHARE_CHAT_ID trong workflow của Page đó."""
    token = env("TELEGRAM_SHARE_BOT_TOKEN") or env("TELEGRAM_BOT_TOKEN")      # bot riêng cho đối tác (nếu có)
    chat = env("TELEGRAM_SHARE_CHAT_ID")
    if not token or not chat:
        print(f"[Telegram chia sẻ] bỏ qua – thiếu {'token' if not token else 'chat id'}", flush=True)
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          data={"chat_id": chat, "text": PREFIX + text, "disable_web_page_preview": "false"}, timeout=30)
        new = (r.json().get("parameters") or {}).get("migrate_to_chat_id") if not r.ok else None
        if new:                                    # nhóm được Telegram nâng lên siêu nhóm → đổi mã nhóm, gửi lại mã mới
            print(f"[Telegram chia sẻ] nhóm đã đổi mã → {new} (cần cập nhật secret TELEGRAM_SHARE_CHAT_ID_…)", flush=True)
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                              data={"chat_id": new, "text": PREFIX + text, "disable_web_page_preview": "false"}, timeout=30)
        if not r.ok:
            print(f"[Telegram chia sẻ lỗi] {r.status_code} {r.text[:200]}", flush=True)
        return r.ok
    except requests.RequestException as exc:
        print(f"[Telegram chia sẻ lỗi] {exc}", flush=True)
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


def send_video(text: str, video, thumbnail=None) -> bool:
    """Gửi video (Reels) + thumbnail kèm chú thích ngắn. Telegram bot giới hạn 50 MB/file."""
    token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print(f"[Telegram chưa cấu hình] {text}")
        return False
    try:
        if thumbnail:
            with open(thumbnail, "rb") as f:
                requests.post(f"https://api.telegram.org/bot{token}/sendPhoto", data={"chat_id": chat},
                              files={"photo": f}, timeout=120)
        with open(video, "rb") as f:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendVideo",
                              data={"chat_id": chat, "caption": text[:1000], "supports_streaming": "true"},
                              files={"video": f}, timeout=600)
        return r.ok
    except requests.RequestException as exc:
        print(f"[Telegram lỗi gửi video] {exc}")
        return send(text)


def find_chat_id(token_var: str = "TELEGRAM_BOT_TOKEN") -> str | None:
    """Lấy chat id từ tin nhắn gần nhất gửi cho bot (token_var: biến môi trường chứa token bot)."""
    r = requests.get(f"https://api.telegram.org/bot{env(token_var)}/getUpdates", timeout=30).json()
    for upd in reversed(r.get("result", [])):
        msg = upd.get("message") or upd.get("edited_message") or upd.get("channel_post") or upd.get("my_chat_member")
        if msg:
            return str(msg["chat"]["id"])
    return None
