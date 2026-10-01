"""Chạy hệ thống.

    python run.py morning                      # tạo bài + banner theo mẫu trong config (KHÔNG đăng)
    python run.py morning --all-styles         # vẽ banner ở tất cả các mẫu để so sánh
    python run.py morning --post my_post.json  # dùng bài tự viết {"post": "...", "focus": "..."} thay cho AI
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from src.analysis import analyze
from src.config import CONFIG, OUTPUT, SYMBOLS, TZ
from src.content import morning
from src.data.calendar import events_for_session
from src.data.prices import get_series
from src.design.styles import STYLES


def run_morning(all_styles: bool = False, post_file: str | None = None):
    now = datetime.now(TZ)
    out_dir = OUTPUT / now.strftime("%Y-%m-%d")
    print(f"[{now:%H:%M}] Bản tin sáng {now:%d/%m/%Y}")

    print("- Lấy dữ liệu giá...")
    markets = {}
    for s in SYMBOLS:
        markets[s["code"]] = analyze(get_series(s["code"]), s["digits"])
        m = markets[s["code"]]
        print(f"  {s['code']:7} {m['price']:>12} {m['change_pct']:+.2f}%  {m['trend']:9} ({m['source']})")

    print("- Lấy lịch kinh tế...")
    events = events_for_session(now)
    print(f"  {len(events)} tin USD/EUR/GBP (High: {sum(e['impact'] == 'High' for e in events)})")

    context = morning.build_context(now, markets, events)
    if post_file:
        print(f"- Dùng bài có sẵn: {post_file}")
        result = {**json.loads(Path(post_file).read_text(encoding="utf-8")), "writer": "manual"}
        bad = morning.find_unverified_numbers(result["post"], context)
        if bad:
            print(f"  ! Cảnh báo - số không khớp dữ liệu: {', '.join(bad)}")
    else:
        print("- Viết bài...")
        result = morning.generate(context)
    post = morning.finalize(result["post"], events)

    print("- Vẽ banner...")
    styles = list(STYLES) if all_styles else [CONFIG["design"]["style"]]
    images = []
    for style in styles:
        name = "morning.png" if not all_styles else f"morning_{style}.png"
        images.append(STYLES[style](out_dir / name, context["date"], result["focus"], markets, events))
        print(f"  {style}: {images[-1]}")

    (out_dir / "morning.txt").write_text(post, encoding="utf-8")
    (out_dir / "morning.json").write_text(json.dumps(
        {"context": context, "markets": markets, "result": result}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ Xong ({result['writer']})")
    return post, images


def run_knowledge(post_file: str | None = None, series_id: str | None = None, part: int | None = None):
    from src import chart_tools
    from src.content import knowledge

    now = datetime.now(TZ)
    out_dir = OUTPUT / now.strftime("%Y-%m-%d")
    picked = knowledge.next_lesson(series_id, part)
    if not picked:
        print("✓ Đã đăng hết tất cả series")
        return None
    series, lesson = picked
    total = len(series["lessons"])
    print(f"[{now:%H:%M}] {series['name']} – Phần {lesson['part']}/{total}: {lesson['title']}")

    if post_file:
        result = {**json.loads(Path(post_file).read_text(encoding="utf-8")), "writer": "manual"}
    else:
        ref = {code: analyze(get_series(code), d)["price"] for code, d in (("XAUUSD", 2), ("EURUSD", 5))}
        result = knowledge.generate(series, lesson, ref)
    if not result:
        print("✗ Không có bài Kiến thức hôm nay")
        return None

    from src.design import carousel

    slides = result["slides"]
    images = [carousel.render_cover(out_dir / "knowledge_00.png", series["name"], series["level"], lesson["part"],
                                    total, result["title"], [sl["heading"] for sl in slides])]
    facts: list[str] = []
    for k, sl in enumerate(slides, 1):
        chart_img, caption = None, ""
        if sl.get("chart"):
            try:
                chart, slide_facts = chart_tools.build(sl["chart"])
                chart_img = chart.render(640, 420, scale=3)
                caption = slide_facts[0] if slide_facts else "Mô hình minh họa, không phải giá thật"
                facts += [f for f in slide_facts[1:] if f not in facts]
            except Exception as exc:  # biểu đồ lỗi thì vẫn đăng, chỉ bỏ hình
                print(f"  ! Slide {k}: không vẽ được biểu đồ ({exc})")
        images.append(carousel.render_slide(out_dir / f"knowledge_{k:02d}.png", series["name"], lesson["part"], total,
                                            k, len(slides), sl["heading"], sl["body"], chart_img, caption,
                                            sl.get("diagram")))
    (out_dir / "knowledge.txt").write_text(knowledge.finalize(result["post"], facts, series["id"]), encoding="utf-8")
    (out_dir / "knowledge.json").write_text(json.dumps(
        {"series": series["id"], "part": lesson["part"], "result": result, "facts": facts},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ Xong ({result['writer']}): {len(images)} ảnh trong {out_dir}")
    return result, images


def run_plan(post_file: str | None = None):
    from src.analysis import intraday_levels
    from src.content import plan
    from src.data.prices import get_intraday
    from src.design import plan_card

    now = datetime.now(TZ)
    out_dir = OUTPUT / now.strftime("%Y-%m-%d")
    print(f"[{now:%H:%M}] Plan A/B {now:%d/%m/%Y}")

    digits = {s["code"]: s["digits"] for s in SYMBOLS}
    intraday = {}
    for code in plan.PLAN_SYMBOLS:
        daily = analyze(get_series(code), digits[code])
        intraday[code] = intraday_levels(get_intraday(code), daily, digits[code])
        print(f"  {code:7} {intraday[code]['price']:>12}  {len(intraday[code]['levels_above'])} vùng trên / "
              f"{len(intraday[code]['levels_below'])} vùng dưới")

    events = plan.pick_events(events_for_session(now), now)
    print(f"  Tin tối nay: {', '.join(e['time'] + ' ' + e['title'] for e in events) or 'không có'}")
    context = plan.build_context(now, intraday, events)

    if post_file:
        result = {**json.loads(Path(post_file).read_text(encoding="utf-8")), "writer": "manual"}
        for err in plan.check_plans(result, context):
            print(f"  ! Cảnh báo: {err}")
    else:
        result = plan.generate(context)

    gold = next(p for p in result["plans"] if p["symbol"] == "XAUUSD")
    image = plan_card.render(out_dir / "plan.png", context["date"], result["focus"], events,
                             intraday["XAUUSD"]["chart"], intraday["XAUUSD"]["price"], gold, digits["XAUUSD"])
    (out_dir / "plan.txt").write_text(plan.finalize(result["post"]), encoding="utf-8")
    (out_dir / "plan.json").write_text(json.dumps({"context": context, "result": result, "chart": intraday["XAUUSD"]["chart"]},
                                                  ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ Xong ({result['writer']}): {image}")
    return result, image


def run_strategy(session: str, post_file: str | None = None):
    """Bài chiến lược XAUUSD: session 'ae' (10:00, phiên Á-Âu) hoặc 'us' (trước phiên Mỹ)."""
    from src.content import strategy
    from src.design import strategy_album
    from src.strategy_data import gather

    now = datetime.now(TZ)
    out_dir = OUTPUT / now.strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[{now:%H:%M}] Chiến lược XAUUSD – {'phiên Á-Âu' if session == 'ae' else 'phiên Mỹ'}")

    data = gather(session)
    print(f"  Giá {data['giá_hiện_tại']} · {data['trạng_thái_thị_trường']['trạng_thái']} · {len(data['vùng_giá'])} vùng giá")
    if post_file:
        result = {**json.loads(Path(post_file).read_text(encoding="utf-8")), "writer": "manual"}
        for err in strategy.check(result, data):
            print(f"  ! Cảnh báo: {err}")
    else:
        print("- AI kiểm tra tin tức & lập chiến lược...")
        result = strategy.generate(data)
    if not result:
        print("✗ Không tạo được bài chiến lược")
        return None

    images = strategy_album.render_album(out_dir, session, data, result)
    (out_dir / f"strategy_{session}.txt").write_text(strategy.finalize(result["post"], session, result.get("bias", "")), encoding="utf-8")
    (out_dir / f"strategy_{session}.json").write_text(json.dumps({"data": data, "result": result},
                                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ Xong ({result['writer']}): {len(images)} ảnh")
    return result, images


def run_weekly():
    """Chủ nhật 22:00: tổng quan tuần mới (lịch tin cả tuần + xu hướng DXY/XAUUSD/EURUSD/GBPUSD)."""
    from src.content import weekly
    from src.design import weekly_album

    now = datetime.now(TZ)
    out_dir = OUTPUT / now.strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[{now:%H:%M}] Tổng quan tuần mới")
    ctx = weekly.build_context(now)
    print(f"  Tuần {ctx['tuần']} · {len(ctx['calendar'])} tin đỏ")
    result = weekly.generate(ctx)
    if not result:
        print("✗ Không tạo được bài tổng quan tuần")
        return None
    images = weekly_album.render_album(out_dir, ctx, result)
    (out_dir / "weekly.txt").write_text(weekly.finalize(result["post"]), encoding="utf-8")
    (out_dir / "weekly.json").write_text(json.dumps({"context": ctx, "result": result}, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    print(f"✓ Xong ({result['writer']}): {len(images)} ảnh")
    return result, images


def check_keys():
    """Kiểm tra các API key trong .env có dùng được không (không in key ra màn hình)."""
    import anthropic
    import requests

    from src.config import env

    if not env("ANTHROPIC_API_KEY"):
        print("✗ ANTHROPIC_API_KEY: chưa điền trong .env")
    else:
        try:
            model = anthropic.Anthropic().models.retrieve(CONFIG["ai"]["model"])
            print(f"✓ ANTHROPIC_API_KEY: hợp lệ, dùng được {model.display_name}")
        except anthropic.AuthenticationError:
            print("✗ ANTHROPIC_API_KEY: key sai hoặc đã bị xoá")
        except anthropic.APIError as exc:
            print(f"✗ ANTHROPIC_API_KEY: lỗi {exc}")

    key = env("TWELVEDATA_API_KEY")
    if not key:
        print("- TWELVEDATA_API_KEY: chưa điền (không bắt buộc, sẽ dùng Yahoo)")
    else:
        data = requests.get("https://api.twelvedata.com/api_usage", params={"apikey": key}, timeout=30).json()
        if "plan_limit" in data:
            print(f"✓ TWELVEDATA_API_KEY: hợp lệ (đã dùng {data.get('current_usage')}/{data['plan_limit']} lượt/phút)")
        else:
            print(f"✗ TWELVEDATA_API_KEY: {data.get('message', 'key không hợp lệ')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("job", choices=["morning", "knowledge", "plan", "strategy", "weekly", "check"])
    parser.add_argument("--all-styles", action="store_true")
    parser.add_argument("--post", help="file JSON chứa bài tự viết")
    parser.add_argument("--series", help="id series (mặc định: series đang đăng dở)")
    parser.add_argument("--part", type=int, help="phần số mấy trong series")
    parser.add_argument("--session", choices=["ae", "us"], default="us", help="bài chiến lược: ae (10:00) | us (trước phiên Mỹ)")
    args = parser.parse_args()
    if args.job == "morning":
        run_morning(args.all_styles, args.post)
    elif args.job == "weekly":
        run_weekly()
    elif args.job == "strategy":
        run_strategy(args.session, args.post)
    elif args.job == "plan":
        run_plan(args.post)
    elif args.job == "knowledge":
        run_knowledge(args.post, args.series, args.part)
    elif args.job == "check":
        check_keys()
