"""Kịch bản → giọng đọc (giọng mẫu AI) → video Reels kiến thức có thương hiệu CWG + ảnh bìa.

    JOB=cwg-vn python -m src.reels.edu.build --topic po3            # AI viết kịch bản + dựng
    JOB=cwg-vn python -m src.reels.edu.build --script x.json         # dựng lại từ kịch bản có sẵn
    JOB=cwg-vn python -m src.reels.edu.build --script x.json --fast  # không gọi giọng (ước lượng thời lượng) – xem hình nhanh
"""
import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from src.config import CONFIG, OUTPUT
from src.design.common import sans
from src.reels import render as old, sfx, voice
from src.reels.edu import render as R
from src.reels.edu.chart import Chart
from src.reels.phonetic import spoken

PAUSE = 0.35          # nghỉ sau mỗi câu
CTA_TEXT = "Theo dõi [r]CWG Markets & Partner[/r] để nhận thêm kiến thức giao dịch mỗi ngày."


def _est(text: str) -> float:
    return max(1.6, len(R.plain(text).split()) * 0.27 + 0.4)


def _voices(spec: dict, folder: Path, fast: bool) -> list[tuple[Path | None, float]]:
    says = [spoken(sc.get("say") or R.plain(sc["text"])) for sc in spec["scenes"]]
    if fast:
        return [(None, _est(s)) for s in says]
    idx = int((CONFIG.get("reels") or {}).get("voice_index", 1))
    paths = voice.synth(says, folder / "voice", voice_index=idx)
    return [(p, voice.duration(p)) for p in paths]


def timeline(spec: dict, voices: list) -> tuple[list[R.Scene], dict, list]:
    charts = {cid: Chart(c.get("segments", []), seed=int(c.get("seed", 7)))
              for cid, c in (spec.get("charts") or {}).items()}
    state = {cid: {"revealed": 0, "marks": []} for cid in charts}
    scenes, events, t = [], [], 0.0
    cur, prev_view = None, None
    font = sans("Bold", R.HEAD_FONT)
    for n, (sc, (vp, vd)) in enumerate(zip(spec["scenes"], voices)):
        dur = max(2.2, vd + PAUSE + 0.15)
        cid = sc.get("chart", cur) if sc.get("chart", cur) in charts else None
        toks = R.tokens(sc["text"])
        s = R.Scene(start=t, dur=dur, tag=sc.get("tag", ""), text=sc["text"], chart_id=cid, reveal=0,
                    reveal_from=0, view=prev_view or (0, 30, 95, 105), card=sc.get("card"), voice_dur=vd,
                    toks=toks, lay=R.layout(toks, font, R.HEAD_W), times=R.word_times(toks, vd))
        s.voice_path = vp
        if s.card:
            s.card = dict(s.card, _dur=vd)
        if cid:
            ch, st = charts[cid], state[cid]
            if sc.get("clear"):
                st["marks"] = []
            want = ch.end_of(sc["reveal"]) + 1 if sc.get("reveal") else (st["revealed"] or len(ch.bars))
            want = max(want, st["revealed"])
            s.reveal_from, s.reveal = st["revealed"], want
            count = want - st["revealed"]
            per = min(0.16, max(0.035, dur * 0.55 / max(1, count)))
            s.r_start, s.r_per = t + 0.1, per
            # khung nhìn: đoạn được nhấn mạnh hoặc toàn bộ phần đã hiện
            # mặc định nhìn cả biểu đồ (nến mọc dần lấp chỗ trống bên phải như video mẫu)
            focus = [f for f in sc.get("focus", []) if ch.seg(f)]
            i0, i1 = ch.span(focus) if focus else (0, len(ch.bars) - 1)
            new_marks = [m for m in sc.get("marks", []) if R.mark_geom(ch, m)]
            all_specs = [x.spec for x in st["marks"]] + new_marks
            right = 8 if any(m.get("type") in ("level", "fvg", "ob") for m in all_specs) else 3
            i0 = max(0, i0 - 2)
            i1 = i1 + right
            if i1 - i0 < 26:
                i0 = max(0, i1 - 26)
                i1 = max(i1, i0 + 26)
            vis = ch.bars[int(i0): int(i1) + 1] or ch.bars[:1]
            lo = min(b.l for b in vis)
            hi = max(b.h for b in vis)
            pad = (hi - lo) * 0.16 + 0.5
            bands = sum(1 for m in all_specs if m.get("type") == "band")
            s.view = (i0, i1, lo - pad, hi + pad * (1.4 + 0.45 * bands))
            # thời điểm hiện chú thích: rải theo câu đọc, không sớm hơn lúc nến liên quan hiện xong
            k = len(new_marks)
            for j, m in enumerate(new_marks):
                frac = float(m.get("when", 0.2 + 0.6 * j / max(1, k)))
                need = R.mark_needs(ch, m)
                t_need = s.r_start + max(0, need + 1 - s.reveal_from) * per + 0.1
                at = max(t + s.voice_at + frac * vd, t_need)
                key = json.dumps(m, sort_keys=True, ensure_ascii=False)
                if key in [x.key for x in st["marks"]]:
                    continue
                st["marks"].append(R.Mark(m, at, key))
                events.append((at, "pen" if m.get("type") in ("level", "band") else "pop", 0.45))
            s.marks = list(st["marks"])
            st["revealed"] = want
            prev_view = s.view
        if s.card and s.card.get("kind") == "check":
            items = s.card.get("items", [])[:5]
            step = max(0.35, vd * 0.7 / max(1, len(items)))
            events += [(t + 0.3 + i * step + 0.5, "ting", 0.35) for i in range(len(items))]
        if n == 0 or sc.get("tag") != spec["scenes"][n - 1].get("tag") or cid != cur:
            events.append((t, "whoosh", 0.35))
        cur = cid if cid else cur
        scenes.append(s)
        t += dur
    return scenes, charts, events


def frame(scenes, charts, base, t: float, total: float, i: int) -> Image.Image:
    sc = scenes[i]
    prev = scenes[i - 1] if i else None
    img = base.copy()
    d = ImageDraw.Draw(img, "RGBA")
    if sc.chart_id:
        ch = charts[sc.chart_id]
        same = prev is not None and prev.chart_id == sc.chart_id
        view = R.lerp_view(prev.view, sc.view, R.prog(t, sc.start, 0.7)) if same else sc.view
        alpha = 1.0 if same else R.prog(t, sc.start, 0.4)
        v = R.View(view)
        shown = sc.reveal_from + max(0.0, (t - sc.r_start) / sc.r_per)
        shown = min(float(sc.reveal), shown)
        R.draw_grid(d, v)
        R.draw_marks(d, ch, v, sc.marks, t, alpha, "back")
        R.draw_candles(d, ch, v, shown, alpha)
        R.draw_marks(d, ch, v, sc.marks, t, alpha, "front")
        # che phần tràn sang trục giá / đầu thẻ
    if sc.card:
        R.draw_card(img, sc.card, t, sc.start)
        d = ImageDraw.Draw(img, "RGBA")
    R.draw_head(d, sc, t, total, prev)
    # mở đầu sáng dần, kết thúc tối dần
    k = min(1.0, t / 0.3, max(0.0, (total - t) / 0.6))
    if k < 1:
        img = Image.blend(Image.new("RGB", img.size, (0, 0, 0)), img, k)
    return img


def encode(scenes, charts, events, out: Path, music: Path | None) -> Path:
    total = scenes[-1].start + scenes[-1].dur + 0.6
    base = R.base_frame()
    silent = out.with_suffix(".video.mp4")
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{R.W}x{R.H}", "-r", str(R.FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                             "-crf", "19", "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
    i = 0
    for f in range(int(total * R.FPS)):
        t = f / R.FPS
        while i + 1 < len(scenes) and t >= scenes[i + 1].start:
            i += 1
        proc.stdin.write(frame(scenes, charts, base, t, total, i).tobytes())
    proc.stdin.close()
    if proc.wait():
        raise RuntimeError("ffmpeg lỗi khi dựng hình")
    voices = [(s.voice_path, s.start + s.voice_at) for s in scenes if getattr(s, "voice_path", None)]
    mix(silent, voices, events, total, out, music)
    silent.unlink(missing_ok=True)
    return out


def mix(silent: Path, voices: list, events: list, total: float, out: Path, music: Path | None,
        music_ss: float | None = None, music_vol: float = 0.5, music_fade: float = 2.5, music_norm: bool = True):
    """music_ss: giây bắt đầu trong bài nhạc (âm = chèn im lặng trước) – để điểm drop rơi đúng khoảnh khắc mong muốn."""
    fx = sfx.render_track(events, total, out.with_suffix(".sfx.wav"))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent)]
    filters, labels = [], []
    for k, (p, at) in enumerate(voices):
        cmd += ["-i", str(p)]
        ms = int(at * 1000)
        filters.append(f"[{k + 1}:a]aresample=48000,adelay={ms}|{ms}[v{k}]")
        labels.append(f"[v{k}]")
    x = len(voices) + 1
    cmd += ["-i", str(fx)]
    filters.append(f"[{x}:a]aresample=48000,volume=0.8[fx]")
    if labels:
        filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,loudnorm=I=-15:TP=-1.5,"
                       f"apad,asplit=2[vo][sc]")
    else:
        filters.append("anullsrc=r=48000:cl=mono,atrim=0.1,apad,asplit=2[vo][sc]")
    if music:
        m = x + 1
        ss = old.music_offset(music) if music_ss is None else music_ss
        cmd += ["-stream_loop", "-1", "-ss", f"{max(0.0, ss):.2f}", "-i", str(music)]
        pre = f"adelay={int(-ss * 1000)}|{int(-ss * 1000)}," if ss < 0 else ""
        # nhạc nhỏ hơn bản Job 1: video kiến thức cần nghe rõ lời (video không lời: music_vol cao hơn)
        norm = "loudnorm=I=-14:TP=-1.5," if music_norm else ""          # nhạc đã dựng sẵn cao trào → giữ nguyên độ vênh
        filters.append(f"[{m}:a]aresample=48000,{pre}{norm}volume={music_vol},afade=t=in:d=0.6,"
                       f"afade=t=out:st={total - music_fade:.2f}:d={music_fade}[bgm]")
        filters.append("[bgm][sc]sidechaincompress=threshold=0.05:ratio=4:attack=20:release=400[duck]")
        filters.append("[vo][duck][fx]amix=inputs=3:normalize=0:duration=longest,"
                       "alimiter=limit=0.89:attack=5:release=50:level=disabled[a]")   # chặn vỡ tiếng (đỉnh ≤ -1 dB)
    else:
        filters.append("[sc]anullsink")
        filters.append("[vo][fx]amix=inputs=2:normalize=0:duration=longest,"
                       "alimiter=limit=0.89:attack=5:release=50:level=disabled[a]")
    cmd += ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[a]", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}", "-movflags", "+faststart", str(out)]
    if subprocess.run(cmd).returncode:
        raise RuntimeError("ffmpeg lỗi khi ghép âm thanh")


def thumbnail(spec: dict, scenes, charts, path: Path) -> Path:
    """Ảnh bìa: biểu đồ đầy đủ nhất (giữ nguyên chú thích) + tiêu đề lớn ở vùng chữ phía trên."""
    best = max((i for i, s in enumerate(scenes) if s.chart_id), key=lambda i: len(scenes[i].marks), default=0)
    s = scenes[best]
    img = frame(scenes, charts, R.base_frame(), s.start + s.dur - 0.05, 1e9, best)
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([R.CARD_BOX[0] + 4, 150, R.CARD_BOX[2] - 120, 590], fill=R.CARD + (255,))   # xoá nhãn + câu thoại
    d.rectangle([R.CARD_BOX[0] + 4, 590, R.CARD_BOX[2] - 4, 1560], fill=R.CARD + (60,))
    th = spec.get("thumb") or {}
    if th.get("kicker"):
        R._pill(d, 84, 196, th["kicker"].upper(), R.BRAND, anchor="lm", solid=True, size=30)
    lines = [ln for ln in str(th.get("title", R.plain(spec.get("title", "")))).split("\n") if ln][:4]
    size = 96 if len(lines) <= 3 else 80
    f = sans("ExtraBold", size)
    y = 262
    for ln in lines:
        x = 84
        for w, col, glue in R.tokens(ln.upper()):
            if glue:
                x -= d.textlength(" ", font=f)
            d.text((x + 4, y + 5), w, font=f, fill=(0, 0, 0, 160))
            d.text((x, y), w, font=f, fill=col)
            x += d.textlength(w + " ", font=f)
        y += int(size * 1.18)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=92)
    return path


def make(spec: dict, folder: Path, fast: bool = False, music: Path | None = None) -> dict:
    spec = dict(spec)
    spec["scenes"] = list(spec["scenes"]) + [{
        "tag": "CWG Markets & Partner", "text": spec.get("cta") or CTA_TEXT,
        "card": {"kind": "cta"}}]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "script.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    voices = _voices(spec, folder, fast)
    scenes, charts, events = timeline(spec, voices)
    total = scenes[-1].start + scenes[-1].dur
    events.append((scenes[-1].start + 0.6, "ting", 0.5))
    video = encode(scenes, charts, events, folder / "reel.mp4", music)
    thumb = thumbnail(spec, scenes, charts, folder / "thumb.jpg")
    says = [spoken(sc.get("say") or R.plain(sc["text"])) for sc in spec["scenes"]]
    return {"video": video, "thumb": thumb, "duration": round(total, 1),
            "voices": ([p for p, _ in voices], says)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script")
    ap.add_argument("--topic")
    ap.add_argument("--out")
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--no-music", action="store_true")
    a = ap.parse_args()
    if a.script:
        spec = json.loads(Path(a.script).read_text(encoding="utf-8"))
    else:
        from src.reels.edu import script
        spec = script.write(a.topic)
    folder = Path(a.out) if a.out else OUTPUT / "reels" / spec.get("slug", "demo")
    music = None if a.no_music else old.pick_music()
    r = make(spec, folder, a.fast, music)
    print(json.dumps({k: str(v) for k, v in r.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
