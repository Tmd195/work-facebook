"""Bài đăng cho Page thương hiệu (vd. CWG Markets & Partner): album bìa + ảnh nội dung + thẻ chính sách, caption.

Mọi thứ riêng của Page nằm trong jobs/<job>/job.yaml → brandpost (persona, tệp khách, dữ kiện được phép dùng,
quy tắc, chữ ký, cảnh báo, nhóm chủ đề + thứ tự xoay vòng) và jobs/<job>/series/*.yaml (series bài học).
AI chỉ viết phần nội dung; chữ ký, cảnh báo, hashtag thương hiệu do hệ thống tự gắn (luôn đúng, không bị viết lại).

    JOB=cwg-vn python -m src.content.brandpost            # viết thử 1 bài, lưu vào output/<job>/<ngày>/brandpost
    JOB=cwg-vn python -m src.content.brandpost --pillar ve-cwg
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

import yaml

from src.config import CONFIG, JOB_DIR, OUTPUT, STATE, TZ
from src.content import fbtext
from src.content.llm import generate_json

BP = CONFIG.get("brandpost") or {}
PROGRESS = STATE / "brand_progress.json"

SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "cover": {"type": "object", "properties": {"tag": {"type": "string"}, "title": {"type": "string"},
                                                   "subtitle": {"type": "string"}},
                  "required": ["tag", "title", "subtitle"]},
        "slides": {"type": "array", "minItems": 3, "maxItems": 4, "items": {
            "type": "object",
            "properties": {"heading": {"type": "string"}, "body": {"type": "string"},
                           "points": {"type": "array", "items": {"type": "string"}},
                           "highlight": {"type": "string"}},
            "required": ["heading", "body", "points", "highlight"]}},
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["topic", "cover", "slides", "caption", "hashtags"],
}


def _progress() -> dict:
    return json.loads(PROGRESS.read_text(encoding="utf-8")) if PROGRESS.exists() else {"count": 0, "series": {}, "topics": []}


def _series() -> dict:
    out = {}
    for f in sorted((JOB_DIR / "series").glob("*.yaml")):
        s = yaml.safe_load(f.read_text(encoding="utf-8"))
        out[s["id"]] = s
    return out


def next_brief(pillar: str | None = None) -> dict:
    p = _progress()
    order = BP.get("order") or list(BP["pillars"])
    pillar = pillar or order[p["count"] % len(order)]
    brief = {"pillar": pillar, "name": BP["pillars"][pillar]["name"], "brief": BP["pillars"][pillar]["brief"],
             "recent": p["topics"][-20:]}
    series = _series().get(pillar)
    if series:
        done = p["series"].get(pillar, 0)
        lesson = series["lessons"][done % len(series["lessons"])]
        brief.update({"series": pillar, "part": lesson["part"], "total": len(series["lessons"]),
                      "lesson": lesson, "series_name": series["name"]})
    return brief


def mark_done(meta: dict):
    p = _progress()
    p["count"] += 1
    if meta.get("series"):
        p["series"][meta["series"]] = p["series"].get(meta["series"], 0) + 1
    p["topics"] = (p["topics"] + [meta.get("topic", "")])[-60:]
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")


def _system() -> str:
    facts = "\n".join(f"- {x}" for x in BP.get("facts", []))
    rules = "\n".join(f"- {x}" for x in BP.get("rules", []))
    style = "\n".join(f"- {x}" for x in BP.get("style_examples", []))
    return f"""Bạn viết bài cho Facebook Page "{CONFIG['brand']['name']}".
Người viết: {BP.get('persona', '')}
Tệp người đọc: {BP.get('audience', '')}

DỮ KIỆN DUY NHẤT ĐƯỢC PHÉP NÊU về sàn / chương trình đối tác (không thêm, không suy diễn con số khác):
{facts}

QUY TẮC:
{rules}
- Không ghi "18+", không kêu gọi comment; lời mời cuối bài là nhắn tin cho Page.
- Mỗi bài có góc nhìn riêng, KHÔNG lặp lại câu chữ hay cấu trúc của các ví dụ dưới (chỉ học tinh thần: cụ thể, thực tế).

Tinh thần cách viết anh chủ Page thích (học ý, không chép):
{style}

ĐỊNH DẠNG BÀI (album ảnh + caption):
- cover: tag (nhãn chủ đề ngắn, vd "Học nghề IB · Phần 3"), title (tiêu đề ≤ 12 từ, cụ thể, gây tò mò),
  subtitle (1 câu ≤ 16 từ nói người đọc nhận được gì).
- slides: 3-4 ảnh nội dung. heading ≤ 8 từ; body 2-3 câu (≤ 55 từ) giải thích rõ; points 2-3 ý ngắn (≤ 10 từ),
  highlight 1 câu chốt (≤ 15 từ). Thông tin thực dụng, có ví dụ, đọc xong làm theo được.
- caption: 60-130 từ. Dòng đầu là câu mở thu hút (không phải câu hỏi lặp lại tiêu đề). Thân bài ngắn, xuống dòng
  thoáng, có thể dùng emoji đầu dòng vừa phải. Kết bằng 1 câu dẫn nhẹ tới việc nhắn tin cho Page.
  KHÔNG viết chữ ký, cảnh báo rủi ro hay hashtag trong caption (hệ thống tự gắn).
- hashtags: 2-3 hashtag theo nội dung bài (tiếng Việt không dấu hoặc tiếng Anh), không lặp hashtag thương hiệu.
Không dùng markdown, không in đậm."""


def write(brief: dict) -> dict:
    lines = [f"Nhóm nội dung: {brief['name']} – {brief['brief']}"]
    if brief.get("lesson"):
        les = brief["lesson"]
        lines.append(f"Bài trong series \"{brief['series_name']}\" – Phần {brief['part']}/{brief['total']}: "
                     f"{les['title']}. Trọng tâm: {les['focus']}. Tag bìa: \"{brief['name']} · Phần {brief['part']}\".")
    else:
        lines.append("Tự chọn 1 chủ đề cụ thể, thực dụng trong nhóm này.")
    if brief["recent"]:
        lines.append("Tránh trùng các chủ đề gần đây: " + "; ".join(t for t in brief["recent"] if t))
    post = generate_json(_system(), "\n".join(lines), SCHEMA)
    post["slides"] = post["slides"][:4]
    post.update({k: brief.get(k) for k in ("pillar", "series", "part", "total")})
    return post


def caption(post: dict) -> str:
    brand_tags = (CONFIG.get("hashtags") or {}).get("brand") or []
    tags = brand_tags + [t if t.startswith("#") else "#" + t for t in post.get("hashtags") or []]
    tags = list(dict.fromkeys(t.replace(" ", "") for t in tags))[:6]
    parts = [fbtext.airy(fbtext.render(post["caption"]).strip()), BP.get("signature", "").strip(),
             BP.get("disclaimer", "").strip()]
    return "\n\n".join(p for p in parts if p) + "\n\n" + " ".join(tags)


def render(post: dict, folder: Path) -> list[Path]:
    from src.design import brand_carousel as bc
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("brandpost_*.png"):
        old.unlink()
    n = len(post["slides"])
    imgs = [bc.render_cover(folder / "brandpost_00.png", post["cover"]["tag"], post["cover"]["title"],
                            post["cover"]["subtitle"], [s["heading"] for s in post["slides"]])]
    for i, s in enumerate(post["slides"], 1):
        imgs.append(bc.render_slide(folder / f"brandpost_{i:02d}.png", i, n, s["heading"], s["body"],
                                    s.get("points"), s.get("highlight", "")))
    pc = BP.get("policy_card")
    if pc:
        facts = {**pc, "example": tuple(pc["example"]), "terms": [tuple(t) for t in pc["terms"]],
                 "licenses": [tuple(x) for x in pc["licenses"]]}
        imgs.append(bc.render_cta_theme(folder / f"brandpost_{n + 1:02d}.png", facts, pc["button"],
                                        BP.get("policy_theme", "light")))
    return imgs


def folder(out_dir: Path) -> Path:
    return out_dir / "brandpost"


def generate(out_dir: Path, pillar: str | None = None) -> bool:
    post = write(next_brief(pillar))
    f = folder(out_dir)
    render(post, f)
    (f / "caption.txt").write_text(caption(post), encoding="utf-8")
    (f / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


def files(out_dir: Path) -> tuple[Path, list[Path]]:
    f = folder(out_dir)
    return f / "caption.txt", sorted(f.glob("brandpost_[0-9][0-9].png"))


def meta(out_dir: Path) -> dict:
    p = json.loads((folder(out_dir) / "post.json").read_text(encoding="utf-8"))
    return {k: p.get(k) for k in ("pillar", "series", "part", "topic")}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pillar")
    a = ap.parse_args()
    out = OUTPUT / datetime.now(TZ).strftime("%Y-%m-%d")
    generate(out, a.pillar)
    cap, imgs = files(out)
    print(cap.read_text(encoding="utf-8"))
    print("\n".join(str(i) for i in imgs))
