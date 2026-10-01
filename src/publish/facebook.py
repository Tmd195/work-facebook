"""Đăng bài lên Facebook Page qua Graph API chính thức.

- 1 ảnh:    POST /{page_id}/photos (caption = nội dung bài)
- Album:    upload từng ảnh ở chế độ ẩn (published=false) → POST /{page_id}/feed kèm attached_media
URL không ghi phiên bản Graph API → dùng phiên bản mặc định của App.
"""
import json
import time
from pathlib import Path

import requests

from src.config import env

GRAPH = "https://graph.facebook.com"


class FacebookError(RuntimeError):
    def __init__(self, message: str, code: int | None = None, needs_user: bool = False):
        super().__init__(message)
        self.code = code
        self.needs_user = needs_user      # lỗi anh phải tự xử lý (token hết hạn, thiếu quyền...)


def _call(method: str, path: str, **kwargs) -> dict:
    token = env("FB_PAGE_TOKEN")
    if not token:
        raise FacebookError("Chưa có FB_PAGE_TOKEN", needs_user=True)
    if method == "POST":
        kwargs["data"] = {**kwargs.get("data", {}), "access_token": token}
    else:
        kwargs["params"] = {**kwargs.get("params", {}), "access_token": token}
    r = requests.request(method, f"{GRAPH}/{path}", timeout=120, **kwargs)
    data = r.json() if r.content else {}
    if "error" in data:
        err = data["error"]
        code = err.get("code")
        # 190 = token hết hạn/không hợp lệ; 10/200/= thiếu quyền; 368 = bị chặn tạm thời
        needs_user = code in (190, 10, 200, 368) or err.get("type") == "OAuthException"
        raise FacebookError(f"{err.get('message')} (code {code})", code, needs_user)
    return data


def _upload_photo(image: Path, published: bool, caption: str = "") -> str:
    with open(image, "rb") as f:
        data = {"published": "true" if published else "false"}
        if caption:
            data["caption"] = caption
        res = _call("POST", f"{env('FB_PAGE_ID')}/photos", data=data, files={"source": f})
    return res.get("post_id") or res["id"]


def publish(caption: str, images: list[Path], retries: int = 3) -> tuple[str, str]:
    """Đăng bài, trả về (link, post_id). Tự thử lại khi lỗi mạng / lỗi tạm thời của Facebook."""
    last_exc = None
    for attempt in range(retries):
        try:
            if len(images) == 1:
                post_id = _upload_photo(images[0], True, caption)
            else:
                media = [{"media_fbid": _upload_photo(img, False)} for img in images]
                data = {"message": caption}
                for i, m in enumerate(media):
                    data[f"attached_media[{i}]"] = json.dumps(m)
                post_id = _call("POST", f"{env('FB_PAGE_ID')}/feed", data=data)["id"]
            return permalink(post_id), post_id
        except FacebookError as exc:
            if exc.needs_user:
                raise
            last_exc = exc
        except requests.RequestException as exc:
            last_exc = exc
        time.sleep(20 * (attempt + 1))
    raise FacebookError(f"Đăng bài thất bại sau {retries} lần: {last_exc}")


def comment(post_id: str, message: str, image: Path | None = None, retries: int = 3) -> str:
    """Comment với tư cách Page dưới bài viết (kèm 1 ảnh nếu có). Trả về id comment."""
    last_exc = None
    for attempt in range(retries):
        try:
            if image:
                with open(image, "rb") as f:
                    res = _call("POST", f"{post_id}/comments", data={"message": message}, files={"source": f})
            else:
                res = _call("POST", f"{post_id}/comments", data={"message": message})
            return res["id"]
        except FacebookError as exc:
            if exc.needs_user:
                raise
            last_exc = exc
        except requests.RequestException as exc:
            last_exc = exc
        time.sleep(15 * (attempt + 1))
    raise FacebookError(f"Comment thất bại sau {retries} lần: {last_exc}")


def permalink(post_id: str) -> str:
    try:
        return _call("GET", post_id, params={"fields": "permalink_url"})["permalink_url"]
    except Exception:
        page, _, pid = post_id.partition("_")
        return f"https://www.facebook.com/{page}/posts/{pid or post_id}"


def check() -> str:
    """Kiểm tra token còn dùng được, trả về tên Page."""
    return _call("GET", env("FB_PAGE_ID"), params={"fields": "name"})["name"]


def page_stats() -> dict:
    """Số người theo dõi hiện tại của Page."""
    return _call("GET", env("FB_PAGE_ID"), params={"fields": "followers_count,fan_count"})


def post_stats(post_id: str) -> dict:
    """Cảm xúc, bình luận (không tính comment của chính Page), chia sẻ; lượt xem nếu token có quyền read_insights."""
    d = _call("GET", post_id, params={"fields": "created_time,reactions.summary(true).limit(0),"
                                                "comments.summary(true).limit(0),shares"})
    reactions = d.get("reactions", {}).get("summary", {}).get("total_count", 0)
    comments_total = d.get("comments", {}).get("summary", {}).get("total_count", 0)
    page_id = env("FB_PAGE_ID")
    own, users = 0, set()
    try:
        cm = _call("GET", f"{post_id}/comments", params={"fields": "from", "limit": 100, "filter": "stream"})
        for c in cm.get("data", []):
            who = (c.get("from") or {}).get("id")
            if who == page_id:
                own += 1
            elif who:
                users.add(who)
    except FacebookError:
        pass
    out = {"reactions": reactions, "comments": max(0, comments_total - own), "commenters": len(users),
           "shares": d.get("shares", {}).get("count", 0), "views": None}
    try:
        ins = _call("GET", f"{post_id}/insights", params={"metric": "post_media_view,post_total_media_view_unique"})
        vals = {m["name"]: (m.get("values") or [{}])[0].get("value") for m in ins.get("data", [])}
        out["views"] = vals.get("post_media_view")
        out["reach"] = vals.get("post_total_media_view_unique")
    except FacebookError:
        pass
    return out
