"""Reels Education – Page Duy Thái Đặng: kịch bản → giọng Thái (nhân bản) → video thẻ tối + nến minh hoạ.

    python -m src.reels.thai_edu.build --script ep.json --theme reu            # dựng đủ giọng
    python -m src.reels.thai_edu.build --script ep.json --theme gold --fast    # ước lượng thời lượng, xem hình nhanh
"""
import argparse
import json
from pathlib import Path

from src.config import OUTPUT
from src.reels import render as old, voice
from src.reels.edu import build as B, render as R
from src.reels.phonetic import spoken
from src.reels.thai_edu import theme


def _voices(spec: dict, folder: Path, fast: bool):
    says = [spoken(sc.get("say") or R.plain(sc["text"])) for sc in spec["scenes"]]
    if fast:
        return [(None, B._est(s)) for s in says]
    paths = voice.synth(says, folder / "voice")             # giọng Thái (VOICE_REF) như Reels 19:15
    return [(p, voice.duration(p)) for p in paths]


def make(spec: dict, folder: Path, theme_name: str = "reu", fast: bool = False, music: Path | None = None) -> dict:
    ep = spec.get("episode") or {}
    theme.EPISODE.update(no=int(ep.get("no", 1)), level=str(ep.get("level", "CƠ BẢN")).upper())
    theme.apply(theme_name)
    spec = dict(spec)
    spec["scenes"] = list(spec["scenes"]) + [{
        "tag": "THEO DÕI", "text": spec.get("cta") or f"Theo dõi [y]{theme.NAME.title()}[/y] để học đủ lộ trình.",
        "say": spec.get("cta_say"), "card": {"kind": "cta", "next": ep.get("next")}}]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "script.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    voices = _voices(spec, folder, fast)
    scenes, charts, events = B.timeline(spec, voices)
    total = scenes[-1].start + scenes[-1].dur
    events.append((scenes[-1].start + 0.6, "ting", 0.5))
    video = B.encode(scenes, charts, events, folder / "reel.mp4", music)
    thumb = B.thumbnail(spec, scenes, charts, folder / "thumb.jpg")
    says = [spoken(sc.get("say") or R.plain(sc["text"])) for sc in spec["scenes"]]
    return {"video": video, "thumb": thumb, "duration": round(total, 1), "voices": ([p for p, _ in voices], says)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--theme", default="reu", choices=list(theme.THEMES))
    ap.add_argument("--out")
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--no-music", action="store_true")
    a = ap.parse_args()
    spec = json.loads(Path(a.script).read_text(encoding="utf-8"))
    folder = Path(a.out) if a.out else OUTPUT / "reels_edu" / f"{spec.get('slug', 'demo')}_{a.theme}"
    r = make(spec, folder, a.theme, a.fast, None if a.no_music else old.pick_music())
    print(json.dumps({k: str(v) for k, v in r.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
