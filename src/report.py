"""Báo cáo đánh giá tuần - Chủ nhật 23:00 gửi riêng qua Telegram (không đăng lên Page).

    python -m src.report            # tạo & gửi báo cáo 7 ngày gần nhất
    python -m src.report --dry      # chỉ in ra màn hình

Điểm sức khỏe Page (100):
  Đều đặn 30   - bài đã đăng / bài theo lịch (30 bài/tuần)
  Tương tác 30 - tỷ lệ tương tác TB mỗi bài so với số người theo dõi (1% trở lên = đủ điểm)
  Tăng trưởng 25 - % người theo dõi tăng trong tuần (2%/tuần trở lên = đủ điểm)
  Kịch bản 15  - tỷ lệ kịch bản đã khớp mà đạt TP / đang lời (chưa có lệnh khớp = 7.5)
Điểm tương tác 1 bài = cảm xúc ×1 + bình luận ×2 + chia sẻ ×3 (bình luận của chính Page không tính).
"""
import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta

from PIL import Image, ImageDraw

from src.config import OUTPUT, ROOT, TZ
from src.content import llm
from src.publish import facebook, telegram

STATE = ROOT / "state"
EXPECTED_PER_WEEK = 30          # 5 ngày × 5 bài + 2 ngày × 2 bài + 1 bài tổng quan tuần
TYPE_NAME = {"morning": "Bản tin sáng", "strategy_ae": "Chiến lược Á–Âu", "strategy_us": "Chiến lược Mỹ",
             "knowledge": "Kiến thức", "weekly": "Tổng quan tuần"}


def _load(name: str) -> dict:
    p = STATE / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def expected_posts(start: datetime, now: datetime) -> int:
    """Số bài theo lịch trong khoảng [start, now] - chỉ tính từ khi hệ thống bắt đầu đăng thật."""
    from src.config import CONFIG
    days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    count, d = 0, start.replace(hour=0, minute=0, second=0, microsecond=0)
    while d <= now:
        wd = days[d.weekday()]
        for job, cfg in CONFIG["schedule"].items():
            if wd not in cfg.get("days", []):
                continue
            for t in cfg.get("times") or [cfg.get("time")]:
                slot = d.replace(hour=int(t[:2]), minute=int(t[3:]))
                if start <= slot <= now:
                    count += 1
        d += timedelta(days=1)
    return count


def collect(now: datetime) -> dict:
    start = now - timedelta(days=7)
    live = [datetime.fromisoformat(v["posted_at"]) for v in _load("posted.json").values()
            if isinstance(v, dict) and not v.get("preview") and v.get("post_id")]
    go_live = min(live) if live else now
    expected = max(1, expected_posts(max(start, go_live - timedelta(minutes=1)), now))
    posted = {k: v for k, v in _load("posted.json").items()
              if isinstance(v, dict) and not v.get("preview") and v.get("post_id")
              and datetime.fromisoformat(v["posted_at"]) >= start}
    posts = []
    for slot, e in sorted(posted.items()):
        try:
            st = facebook.post_stats(e["post_id"])
        except Exception as exc:
            st = {"error": str(exc)[:100]}
        score = st.get("reactions", 0) + 2 * st.get("comments", 0) + 3 * st.get("shares", 0)
        when = datetime.fromisoformat(e["posted_at"])
        meta = e.get("meta") or {}
        posts.append({"slot": slot, "type": e["job"], "type_name": TYPE_NAME.get(e["job"], e["job"]),
                      "weekday": when.strftime("%a"), "time": slot[-5:], "link": e["link"],
                      "series": meta.get("series"), "part": meta.get("part"), **st, "score": score})

    # Người theo dõi
    metrics = _load("metrics.json")
    try:
        followers_now = facebook.page_stats().get("followers_count")
    except Exception:
        followers_now = None
    hist = metrics.get("followers", {})
    older = [v for d, v in sorted(hist.items()) if d <= start.strftime("%Y-%m-%d")]
    in_week = [v for d, v in sorted(hist.items()) if d >= start.strftime("%Y-%m-%d")]
    followers_start = older[-1] if older else (in_week[0] if in_week else followers_now)

    # Kết quả kịch bản (comment cập nhật lệnh 22:00)
    trades = []
    for k, v in _load("followups.json").items():
        if k.endswith("|track") and datetime.fromisoformat(v["at"]) >= start:
            trades += v.get("result", [])
    filled = [t for t in trades if t.get("filled")]
    good = [t for t in filled if (t.get("tp_hit") or 0) > 0 or (t.get("floating_pips") or 0) > 0
            or (t.get("pips_closed") or 0) > 0]
    pips = sum((t.get("pips_closed") if t.get("closed") else t.get("floating_pips")) or 0 for t in filled)

    followups = [k for k, v in _load("followups.json").items() if datetime.fromisoformat(v["at"]) >= start]

    # Gom nhóm
    def group(key):
        g = defaultdict(list)
        for p in posts:
            g[p[key]].append(p["score"])
        return {k: {"bài": len(v), "điểm_TB": round(sum(v) / len(v), 1)} for k, v in g.items()}

    avg = sum(p["score"] for p in posts) / len(posts) if posts else 0
    er = (avg / followers_now * 100) if followers_now else 0
    growth = ((followers_now - followers_start) / followers_start * 100) if followers_now and followers_start else 0
    s_regular = min(30, len(posts) / expected * 30)
    s_engage = min(30, er * 30)
    s_growth = min(25, max(0, growth * 12.5))
    s_trade = 7.5 if not filled else 15 * len(good) / len(filled)
    views = [p["views"] for p in posts if p.get("views") is not None]

    prev = metrics.get("weekly", {})
    last_key = sorted(prev)[-1] if prev else None
    return {
        "tuần": f"{start:%d/%m} – {now:%d/%m/%Y}",
        "điểm": {"tổng": round(s_regular + s_engage + s_growth + s_trade), "đều_đặn": round(s_regular, 1),
                 "tương_tác": round(s_engage, 1), "tăng_trưởng": round(s_growth, 1), "kịch_bản": round(s_trade, 1)},
        "tuần_trước": prev.get(last_key) if last_key else None,
        "số_bài_đăng": len(posts), "số_bài_theo_lịch": expected,
        "ghi_chú": (f"Hệ thống bắt đầu đăng thật từ {go_live:%H:%M %d/%m}; số bài theo lịch chỉ tính từ thời điểm đó"
                    if go_live > start else ""), "comment_theo_dõi": len(followups),
        "người_theo_dõi": {"đầu_tuần": followers_start, "cuối_tuần": followers_now,
                           "tăng": (followers_now - followers_start) if followers_now and followers_start else None,
                           "tăng_%": round(growth, 2)},
        "tương_tác": {"tổng_cảm_xúc": sum(p.get("reactions", 0) for p in posts),
                      "tổng_bình_luận": sum(p.get("comments", 0) for p in posts),
                      "tổng_chia_sẻ": sum(p.get("shares", 0) for p in posts),
                      "điểm_TB_mỗi_bài": round(avg, 1), "tỷ_lệ_tương_tác_%": round(er, 2),
                      "lượt_xem_tổng": sum(views) if views else "chưa có quyền đọc lượt xem (read_insights)"},
        "theo_dạng_bài": group("type_name"), "theo_khung_giờ": group("time"), "theo_thứ": group("weekday"),
        "top_bài": sorted(posts, key=lambda p: -p["score"])[:3],
        "bài_yếu": sorted(posts, key=lambda p: p["score"])[:3],
        "kịch_bản": {"số_kịch_bản": len(trades), "đã_khớp": len(filled), "tốt": len(good), "tổng_pips": pips},
        "tiến_độ_series": _load("series_progress.json").get("done", {}),
    }


REPORT_PROMPT = """Bạn là trợ lý phát triển Facebook Page "Duy Thái Đặng" (forex/vàng, đăng tự động bằng hệ thống AI).
Viết BÁO CÁO ĐÁNH GIÁ TUẦN gửi riêng cho anh Thái qua Telegram (xưng "em", gọi "anh"), dựa trên DỮ LIỆU.
Không markdown (Telegram hiển thị chữ thường), dùng emoji làm đầu mục, tối đa ~3200 ký tự:
1. "📊 BÁO CÁO TUẦN <khoảng ngày>" + Điểm sức khỏe Page X/100 (so với tuần trước nếu có) + 1 câu nhận định chung.
2. 4 trụ cột (Đều đặn / Tương tác / Tăng trưởng / Kịch bản): số liệu chính + nhận xét ngắn.
3. 🏆 Bài tốt nhất & 📉 bài yếu nhất (dạng bài, khung giờ, điểm, link) và lý do có thể.
4. ⏰ Khung giờ / dạng bài / series hiệu quả nhất & kém nhất.
5. 🛠 ĐỀ XUẤT SỬA ĐỔI: 3-5 đề xuất cụ thể, mỗi đề xuất: [Ưu tiên cao/vừa/thấp] việc gì – vì sao (dẫn số liệu) –
   ai làm (hệ thống tự sửa được / anh Thái làm, ví dụ trả lời comment, quay Reels, livestream).
   Ví dụ loại đề xuất: đổi giờ đăng, giảm/tăng số bài, đổi dạng ảnh, chỉnh giọng văn, đổi thứ tự series, thêm Reels, bài tương tác.
6. ❓ Câu hỏi để anh quyết định tuần tới (1-2 câu).
Quan trọng: tuần đầu dữ liệu còn ít → nói rõ, không kết luận vội. Không bịa số; chỉ dùng số trong DỮ LIỆU.
Trả về JSON {"report": "..."}."""


def chart(data: dict, path) -> None:
    """Biểu đồ cột: điểm tương tác TB theo dạng bài và theo khung giờ."""
    from src.design.common import sans
    from src.design.palette import ACCENT, BG, PRIMARY
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 130], fill=PRIMARY)
    d.text((50, 40), f"Tương tác TB mỗi bài · {data['tuần']}", font=sans("ExtraBold", 40), fill=(255, 255, 255))
    sections = [("Theo dạng bài", data["theo_dạng_bài"]), ("Theo khung giờ", data["theo_khung_giờ"])]
    y = 170
    for title, g in sections:
        d.text((50, y), title.upper(), font=sans("ExtraBold", 26), fill=PRIMARY)
        y += 50
        mx = max([v["điểm_TB"] for v in g.values()] + [1])
        for name, v in sorted(g.items(), key=lambda kv: -kv[1]["điểm_TB"]):
            d.text((50, y + 16), str(name), font=sans("SemiBold", 24), fill=(20, 20, 20), anchor="lm")
            bw = int((W - 420) * v["điểm_TB"] / mx)
            d.rectangle([330, y, 330 + max(bw, 4), y + 32], fill=PRIMARY)
            d.rectangle([330, y, 330 + max(bw, 4), y + 6], fill=ACCENT)
            d.text((340 + bw, y + 16), f"{v['điểm_TB']} ({v['bài']} bài)", font=sans("Medium", 20),
                   fill=(110, 108, 100), anchor="lm")
            y += 46
        y += 30
    img.save(path)


def template(data: dict) -> str:
    s, f, t = data["điểm"], data["người_theo_dõi"], data["tương_tác"]
    return (f"📊 BÁO CÁO TUẦN {data['tuần']}\nĐiểm sức khỏe Page: {s['tổng']}/100\n\n"
            f"📅 Đều đặn {s['đều_đặn']}/30: đã đăng {data['số_bài_đăng']}/{data['số_bài_theo_lịch']} bài, "
            f"{data['comment_theo_dõi']} comment theo dõi.\n"
            f"💬 Tương tác {s['tương_tác']}/30: {t['tổng_cảm_xúc']} cảm xúc, {t['tổng_bình_luận']} bình luận, "
            f"{t['tổng_chia_sẻ']} chia sẻ, TB {t['điểm_TB_mỗi_bài']} điểm/bài ({t['tỷ_lệ_tương_tác_%']}%).\n"
            f"📈 Tăng trưởng {s['tăng_trưởng']}/25: người theo dõi {f['đầu_tuần']} → {f['cuối_tuần']}.\n"
            f"🎯 Kịch bản {s['kịch_bản']}/15: {data['kịch_bản']['đã_khớp']} lệnh khớp, tổng {data['kịch_bản']['tổng_pips']} pips.\n\n"
            "(Bản tóm tắt tự động - AI tạm thời không viết được phần đánh giá & đề xuất.)")


def run(dry: bool = False) -> bool:
    now = datetime.now(TZ)
    data = collect(now)
    out = OUTPUT / now.strftime("%Y-%m-%d")
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        text = llm.generate_json(REPORT_PROMPT, "DỮ LIỆU:\n" + json.dumps(data, ensure_ascii=False, indent=1),
                                 {"type": "object", "properties": {"report": {"type": "string"}},
                                  "required": ["report"]})["report"]
    except Exception as exc:
        print(f"  ! AI lỗi ({exc}) - dùng bản tóm tắt")
        text = template(data)
    from src.content.fbtext import render
    text = render(text)
    img = out / "report.png"
    chart(data, img)
    if dry:
        print(text)
        return True
    telegram.send_preview("📋 BÁO CÁO ĐÁNH GIÁ TUẦN (chỉ gửi anh, không đăng Page)", text, [img])
    metrics = _load("metrics.json") or {"followers": {}, "weekly": {}}
    metrics.setdefault("weekly", {})[now.strftime("%Y-%m-%d")] = {
        "điểm": data["điểm"], "người_theo_dõi": data["người_theo_dõi"]["cuối_tuần"],
        "điểm_TB_mỗi_bài": data["tương_tác"]["điểm_TB_mỗi_bài"], "số_bài": data["số_bài_đăng"]}
    if data["người_theo_dõi"]["cuối_tuần"]:
        metrics.setdefault("followers", {})[now.strftime("%Y-%m-%d")] = data["người_theo_dõi"]["cuối_tuần"]
    (STATE / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    try:
        run(a.dry)
    except Exception as exc:
        telegram.need_fix(f"❌ Báo cáo tuần lỗi: {type(exc).__name__}: {exc}")
        raise
