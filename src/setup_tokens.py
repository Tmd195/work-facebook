"""Xử lý token anh dán vào .env (không in token ra màn hình):
- Telegram: tự lấy chat id từ tin nhắn anh gửi cho bot, gửi tin thử
- Facebook: đổi user token tạm thời → token dài hạn → token Page (không hết hạn), ghi FB_PAGE_ID / FB_PAGE_TOKEN
- Claude: kiểm tra token có đúng định dạng

    python -m src.setup_tokens
"""
import os
import re

import requests

from src.config import ROOT

ENV = ROOT / ".env"
GRAPH = "https://graph.facebook.com"


def read_env() -> dict:
    vals = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Z_]+)=(.*)$", line.strip())
        if m:
            vals[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return vals


def write_env(key: str, value: str):
    lines = ENV.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[key] = value


def setup_telegram(v: dict) -> bool:
    tok = v.get("TELEGRAM_BOT_TOKEN")
    if not tok:
        print("- Telegram: chưa có TELEGRAM_BOT_TOKEN")
        return False
    me = requests.get(f"https://api.telegram.org/bot{tok}/getMe", timeout=30).json()
    if not me.get("ok"):
        print("✗ Telegram: token bot không hợp lệ")
        return False
    chat = v.get("TELEGRAM_CHAT_ID")
    if not chat:
        upd = requests.get(f"https://api.telegram.org/bot{tok}/getUpdates", timeout=30).json().get("result", [])
        msgs = [u.get("message") for u in upd if u.get("message")]
        if not msgs:
            print(f"✗ Telegram: bot @{me['result']['username']} chưa nhận tin nào - anh mở bot, bấm Start và gửi 1 tin bất kỳ")
            return False
        chat = str(msgs[-1]["chat"]["id"])
        write_env("TELEGRAM_CHAT_ID", chat)
    r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", timeout=30,
                      data={"chat_id": chat, "text": "✅ Kết nối thành công! Từ giờ em sẽ báo cáo các bài đăng ở đây."}).json()
    print(f"✓ Telegram: bot @{me['result']['username']} đã gửi tin thử" if r.get("ok") else f"✗ Telegram: {r}")
    return bool(r.get("ok"))


def setup_facebook(v: dict) -> bool:
    if v.get("FB_PAGE_TOKEN") and v.get("FB_PAGE_ID"):
        page = requests.get(f"{GRAPH}/{v['FB_PAGE_ID']}", timeout=30,
                            params={"fields": "name", "access_token": v["FB_PAGE_TOKEN"]}).json()
        if "name" in page:
            print(f"✓ Facebook: token Page '{page['name']}' đang hoạt động")
            return True
    app_id, secret, user_tok = v.get("FB_APP_ID"), v.get("FB_APP_SECRET"), v.get("FB_USER_TOKEN")
    if not (app_id and secret and user_tok):
        print("- Facebook: cần đủ FB_APP_ID, FB_APP_SECRET, FB_USER_TOKEN")
        return False
    long = requests.get(f"{GRAPH}/oauth/access_token", timeout=30, params={
        "grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": secret,
        "fb_exchange_token": user_tok}).json()
    if "access_token" not in long:
        print(f"✗ Facebook: không đổi được token dài hạn - {long.get('error', {}).get('message')}")
        return False
    pages = requests.get(f"{GRAPH}/me/accounts", timeout=30,
                         params={"access_token": long["access_token"], "fields": "id,name,access_token,tasks"}).json()
    data = pages.get("data", [])
    if not data:
        print(f"✗ Facebook: không thấy Page nào - {pages.get('error', {}).get('message', 'kiểm tra lại quyền khi tạo token')}")
        return False
    want = v.get("FB_PAGE_NAME", "").lower()
    page = next((p for p in data if want and want in p["name"].lower()), None)
    if page is None:
        if len(data) > 1:
            print("! Facebook: tài khoản quản lý nhiều Page:")
            for p in data:
                print(f"   - {p['name']}")
            print("  → Thêm dòng FB_PAGE_NAME=<tên Page> vào .env rồi chạy lại")
            return False
        page = data[0]
    if "CREATE_CONTENT" not in (page.get("tasks") or ["CREATE_CONTENT"]):
        print(f"✗ Facebook: tài khoản không có quyền đăng bài trên Page '{page['name']}'")
        return False
    write_env("FB_PAGE_ID", page["id"])
    write_env("FB_PAGE_TOKEN", page["access_token"])
    dbg = requests.get(f"{GRAPH}/debug_token", timeout=30, params={
        "input_token": page["access_token"], "access_token": f"{app_id}|{secret}"}).json().get("data", {})
    exp = dbg.get("expires_at", 0)
    print(f"✓ Facebook: đã lấy token Page '{page['name']}' "
          f"({'không hết hạn' if exp == 0 else 'hết hạn ' + str(exp)}), quyền: {', '.join(dbg.get('scopes', []))}")
    return True


def check_claude(v: dict) -> bool:
    tok = v.get("CLAUDE_CODE_OAUTH_TOKEN", "")
    ok = tok.startswith("sk-ant-") and len(tok) > 40
    print("✓ Claude: token đúng định dạng" if ok else "- Claude: chưa có token (chạy: claude setup-token)")
    return ok


if __name__ == "__main__":
    v = read_env()
    results = {"Telegram": setup_telegram(v), "Facebook": setup_facebook(read_env()), "Claude": check_claude(v)}
    print("\nTóm tắt: " + " · ".join(f"{k} {'✓' if ok else '✗'}" for k, ok in results.items()))
