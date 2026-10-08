"""Ảnh bài tin tức Page DecodeFx Trading – form "Tạp chí kinh doanh" (mẫu 12, anh chốt 08/10/2026).

Ảnh chủ đề cao hết cột trái (mờ dần sang nền kem) · cột phải: DECODEFX DAILY, kicker đỏ (loại bài · ngày), tiêu đề chữ có chân,
đoạn dẫn nghiêng, tin chính có gạch đỏ, 4 mã ▲▼■ + ghi chú, lịch tin. Dựng HTML → Playwright (font nhúng base64).
Ảnh: kho assets/photos/news/<chủ đề>-<n>.jpg (CC0 / phạm vi công cộng – licenses.json).
"""
import base64
import html
from pathlib import Path

from src.config import ROOT

PHOTOS = ROOT / "assets" / "photos" / "news"
TOPICS = ["fed", "gold", "oil", "euro", "uk", "usd", "china", "japan", "stocks", "jobs", "inflation"]


def photo_for(topic: str, day_ord: int) -> Path:
    """Ảnh theo chủ đề, xoay vòng theo ngày để không lặp; chủ đề lạ → Fed."""
    topic = topic if topic in TOPICS else "fed"
    files = sorted(PHOTOS.glob(f"{topic}-*.jpg")) or sorted(PHOTOS.glob("fed-*.jpg"))
    return files[day_ord % len(files)]


def _b64(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def _fonts() -> str:
    f = ROOT / "assets" / "fonts"
    css = ""
    for w, n in (("Regular", 400), ("Medium", 500), ("SemiBold", 600), ("Bold", 700), ("ExtraBold", 800)):
        css += f"@font-face {{ font-family: BVP; src: url('{_b64(f / f'BeVietnamPro-{w}.ttf', 'font/ttf')}'); font-weight: {n}; }}\n"
    css += f"@font-face {{ font-family: Lora; src: url('{_b64(f / 'Lora-Variable.ttf', 'font/ttf')}'); font-weight: 400 700; }}\n"
    css += f"@font-face {{ font-family: Lora; font-style: italic; src: url('{_b64(f / 'Lora-Italic-Variable.ttf', 'font/ttf')}'); font-weight: 400 700; }}\n"
    return css


def _arrow(d):
    return {"up": ("▲", "#16a34a"), "down": ("▼", "#dc2626")}.get(d, ("■", "#9ca3af"))


def page(kicker: str, title: str, lead: str, news: list, impacts: list, events: list, photo: Path,
         badge: str = "BẢN TIN 06:00", photo_note: str = "") -> str:
    e = html.escape
    news_html = "".join(f"<p>{e(n)}</p>" for n in news)
    imp = ""
    for it in impacts:
        a, c = _arrow(it.get("direction"))
        imp += f'<li><span style="color:{c}">{a}</span><b>{e(it["asset"])}</b> {e(it["note"])}</li>'
    cal = "".join(f'<div class="ev"><b>{e(x["time"])}</b> {e(x["title"])}</div>' for x in events[:4])
    cal_html = f'<div class="cal"><div class="ck">LỊCH HÔM NAY</div>{cal}</div>' if cal else ""
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><style>
{_fonts()}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ width: 1080px; height: 1350px; overflow: hidden; font-family: BVP; background: #f6f1e7; color: #111;
       display: grid; grid-template-columns: 430px 1fr; }}
.ph {{ background: url({_b64(photo, 'image/jpeg')}) 45% center/cover; position: relative; }}
.ph::after {{ content: ''; position: absolute; inset: 0; background: linear-gradient(90deg, rgba(246,241,231,0) 68%, rgba(246,241,231,1)); }}
.issue {{ position: absolute; left: 30px; top: 40px; background: #e11d48; color: #fff; padding: 10px 18px; font-weight: 800;
          font-size: 22px; letter-spacing: 2px; z-index: 2; }}
.pn {{ position: absolute; left: 30px; bottom: 34px; right: 60px; color: #fff; font-size: 17px; z-index: 2;
       text-shadow: 0 1px 6px rgba(0,0,0,.7); }}
.c {{ padding: 60px 56px 0 30px; position: relative; }}
.mast {{ font-family: Lora; font-weight: 700; font-size: 34px; letter-spacing: 6px; border-bottom: 3px solid #111; padding-bottom: 14px; }}
.kick {{ margin-top: 30px; color: #e11d48; font-weight: 800; font-size: 23px; letter-spacing: 3px; }}
h1 {{ font-family: Lora; font-weight: 700; font-size: 64px; line-height: 1.06; margin-top: 12px; }}
.lead {{ font-family: Lora; font-style: italic; font-size: 29px; color: #444; margin-top: 20px; line-height: 1.35; }}
.news p {{ font-size: 26px; font-weight: 600; margin-top: 13px; padding-left: 18px; border-left: 4px solid #e11d48; line-height: 1.3; }}
ul {{ list-style: none; margin-top: 28px; border-top: 1px solid #111; }}
li {{ font-size: 26px; padding: 13px 0; border-bottom: 1px solid #d6cfc0; line-height: 1.3; }}
li span {{ margin-right: 12px; }} li b {{ font-weight: 800; margin-right: 8px; }}
.cal {{ margin-top: 22px; }} .ck {{ color: #e11d48; font-weight: 800; font-size: 21px; letter-spacing: 3px; }}
.ev {{ font-size: 24px; font-weight: 600; margin-top: 8px; }} .ev b {{ font-weight: 800; margin-right: 10px; }}
.foot {{ position: absolute; right: 56px; bottom: 44px; font-family: Lora; font-style: italic; font-size: 28px; font-weight: 700; }}
</style></head><body>
<div class="ph"><div class="issue">{e(badge)}</div><div class="pn">{e(photo_note)}</div></div>
<div class="c"><div class="mast">DECODEFX DAILY</div><div class="kick">{e(kicker)}</div>
<h1>{e(title)}</h1><div class="lead">{e(lead)}</div><div class="news">{news_html}</div><ul>{imp}</ul>{cal_html}</div>
<div class="foot">Follow DecodeFX Trading</div></body></html>"""


def render(path: Path, **kw) -> Path:
    """Dựng 1 ảnh 1080×1350; tự thu chữ nếu nội dung dài (không cắt chữ)."""
    from playwright.sync_api import sync_playwright
    doc = page(**kw)
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome")
        except Exception:
            b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        pg.set_content(doc, wait_until="load")
        pg.wait_for_timeout(300)
        # tràn chiều cao → thu nhỏ dần cả cột chữ cho vừa (giữ đủ chữ)
        for _ in range(8):
            over = pg.evaluate("document.querySelector('.c').lastElementChild.getBoundingClientRect().bottom > 1350 - 110")
            if not over:
                break
            pg.evaluate("""() => { const c = document.querySelector('.c');
                const z = parseFloat(c.style.zoom || 1) - 0.05; c.style.zoom = z; }""")
        pg.screenshot(path=str(path))
        b.close()
    return path
