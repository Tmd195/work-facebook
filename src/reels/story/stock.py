"""Video nền (B-roll) cho Reels storytelling: Pixabay (PIXABAY_API_KEY) → Pexels (PEXELS_API_KEY, đang tạm dừng
cấp key mới) → dự phòng Mixkit (không cần key).

Cả hai đều cho dùng thương mại miễn phí, không bắt ghi nguồn. Không ám chỉ người trong video là khách/đại lý thật.
Tải về thư mục cache để dùng lại, không tải trùng.
"""
import hashlib
import json
import random
import re
from pathlib import Path

import requests

from src.config import ROOT, env

CACHE = ROOT / "output" / "_stock"
UA = {"User-Agent": "Mozilla/5.0"}


def _pexels(query: str, n: int = 6) -> list[dict]:
    key = env("PEXELS_API_KEY")
    if not key:
        return []
    r = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": key, **UA}, timeout=30,
                     params={"query": query, "orientation": "portrait", "size": "medium", "per_page": n})
    r.raise_for_status()
    out = []
    for v in r.json().get("videos", []):
        files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("height")]
        files.sort(key=lambda f: abs((f.get("height") or 0) - 1920))
        if files:
            out.append({"id": f"pexels-{v['id']}", "url": files[0]["link"], "duration": v.get("duration", 0),
                        "source": "Pexels", "page": v.get("url")})
    return out


def _pixabay(query: str, n: int = 8) -> list[dict]:
    key = env("PIXABAY_API_KEY")
    if not key:
        return []
    r = requests.get("https://pixabay.com/api/videos/", headers=UA, timeout=30,
                     params={"key": key, "q": query[:100], "per_page": max(3, n), "safesearch": "true"})
    r.raise_for_status()
    out = []
    for h in r.json().get("hits", []):
        vids = h.get("videos") or {}
        v = next((vids[k] for k in ("large", "medium", "small") if (vids.get(k) or {}).get("url")), None)
        if v:
            out.append({"id": f"pixabay-{h['id']}", "url": v["url"], "duration": h.get("duration", 0),
                        "source": "Pixabay", "page": h.get("pageURL"), "vertical": v.get("height", 0) > v.get("width", 1)})
    out.sort(key=lambda c: not c["vertical"])               # ưu tiên video dọc
    return out[:n]


def _mixkit(query: str, n: int = 6) -> list[dict]:
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
    html = requests.get(f"https://mixkit.co/free-stock-video/{slug}/", headers=UA, timeout=30).text
    ids = list(dict.fromkeys(re.findall(r"https://assets\.mixkit\.co/videos/(\d+)/\1-\d+\.mp4", html)))
    return [{"id": f"mixkit-{i}", "url": f"https://assets.mixkit.co/videos/{i}/{i}-720.mp4", "duration": 0,
             "source": "Mixkit", "page": f"https://mixkit.co/free-stock-video/{slug}/"} for i in ids[:n]]


def search(query: str, n: int = 6) -> list[dict]:
    for fn in (_pixabay, _pexels, _mixkit):
        try:
            res = fn(query, n)
        except Exception as exc:
            print(f"  ! {fn.__name__} '{query}': {exc}", flush=True)
            res = []
        if res:
            return res
    return []


def fetch(queries: list[str], used: set, seed: int = 0) -> Path | None:
    """Tìm theo lần lượt các từ khoá, tải 1 video chưa dùng trong video này. Trả về đường dẫn file mp4."""
    rnd = random.Random(seed)
    CACHE.mkdir(parents=True, exist_ok=True)
    for q in queries:
        cands = [c for c in search(q) if c["id"] not in used]
        rnd.shuffle(cands)
        for c in cands[:3]:
            f = CACHE / f"{c['id']}.mp4"
            if not f.exists() or f.stat().st_size < 50_000:
                try:
                    r = requests.get(c["url"], headers=UA, timeout=120)
                    r.raise_for_status()
                    if len(r.content) < 50_000:
                        continue
                    f.write_bytes(r.content)
                except Exception as exc:
                    print(f"  ! tải {c['id']}: {exc}", flush=True)
                    continue
            used.add(c["id"])
            (CACHE / "sources.json").open("a", encoding="utf-8").write(json.dumps(c, ensure_ascii=False) + "\n")
            return f
    return None
