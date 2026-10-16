"""Vertical Shorts / Reels / TikToks cut from the finished master, with brand captions burned in.

Each Short is listed in the episode's shorts.yaml:

  - id: S1
    title: "He ran."              # hook band at the top
    start: "3:12"                 # in the master
    end: "3:49"
    mode: fit                     # fit (blurred fill) or crop (fills the screen; good for close shots)
    crop_x: 0.5                   # crop mode only: 0 = left edge, 1 = right edge
    caption: "Platform caption text"
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from . import cards
from .captions import read_srt
from .core import StudioError, channel, color, duration, load_yaml, run
from .timeline import Episode


def parse_t(v) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    parts = [float(p) for p in str(v).split(":")]
    sec = 0.0
    for p in parts:
        sec = sec * 60 + p
    return sec


def _caption_png(text: str, w: int, dst: Path) -> Path:
    fnt = cards.font("label_bold", 64)
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    lines = cards.wrap(tmp, text, fnt, int(w * 0.84))
    lh = 78
    im = Image.new("RGBA", (w, lh * len(lines) + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, ln in enumerate(lines):
        d.text((w // 2, 20 + i * lh), ln, font=fnt, fill=color("cream") + (255,), anchor="mt",
               stroke_width=6, stroke_fill=color("navy_dark") + (235,))
    im.save(dst)
    return dst


def _title_png(text: str, w: int, dst: Path) -> Path:
    fnt = cards.font("title", 76)
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    lines = cards.wrap(tmp, text.upper(), fnt, int(w * 0.86))
    lh = 92
    h = lh * len(lines) + 70
    im = Image.new("RGBA", (w, h), color("navy_dark") + (205,))
    d = ImageDraw.Draw(im)
    for i, ln in enumerate(lines):
        d.text((w // 2, 35 + i * lh), ln, font=fnt, fill=color("gold") + (255,), anchor="mt")
    d.line([(w * 0.35, h - 8), (w * 0.65, h - 8)], fill=color("gold") + (255,), width=4)
    im.save(dst)
    return dst


def _end_tag_png(w: int, dst: Path) -> Path:
    im = Image.new("RGBA", (w, 150), color("navy_dark") + (215,))
    d = ImageDraw.Draw(im)
    d.text((w // 2, 40), "FULL STORY ON THE CHANNEL", font=cards.font("label_bold", 44),
           fill=color("gold") + (255,), anchor="mt")
    d.text((w // 2, 95), channel()["channel"]["handle"], font=cards.font("label", 36),
           fill=color("cream") + (255,), anchor="mt")
    im.save(dst)
    return dst


def render_short(ep: Episode, spec: dict, master: Path, srt: Path | None) -> Path:
    cfg = channel()["shorts"]
    W, H = cfg["width"], cfg["height"]
    a, b = parse_t(spec["start"]), parse_t(spec["end"])
    if b - a > cfg["max_seconds"]:
        raise StudioError(f"Short {spec['id']} is {b - a:.0f}s; keep it under {cfg['max_seconds']}s.")
    if b > duration(master) + 0.1:
        raise StudioError(f"Short {spec['id']} ends after the master does.")
    L = b - a
    work = ep.work / "shorts" / spec["id"]
    work.mkdir(parents=True, exist_ok=True)

    inputs = ["-ss", f"{a:.3f}", "-t", f"{L:.3f}", "-i", master]
    overlays = []                                   # (png, x, y, t0, t1)
    title_h = 0
    if spec.get("title"):
        p = _title_png(spec["title"], W, work / "title.png")
        title_h = Image.open(p).height
        overlays.append((p, 0, 160, 0, L))
    if srt and srt.exists():
        for i, (s, e, text) in enumerate(read_srt(srt)):
            if e <= a or s >= b:
                continue
            p = _caption_png(text, W, work / f"cap_{i:03d}.png")
            overlays.append((p, 0, int(H * 0.70), max(0, s - a), min(L, e - a)))
    overlays.append((_end_tag_png(W, work / "end.png"), 0, int(H * 0.86), max(0, L - 2.5), L))

    mode = spec.get("mode", "fit")
    if mode == "crop":
        cx = float(spec.get("crop_x", 0.5))
        base = (f"[0:v]scale=-2:{H}:flags=lanczos,crop={W}:{H}:(in_w-{W})*{cx}:0,setsar=1[base]")
    else:
        base = (f"[0:v]split[a][b];"
                f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                f"boxblur=30:3,eq=brightness=-0.12[bg];"
                f"[b]scale={W}:-2:flags=lanczos[fg];"
                f"[bg][fg]overlay=0:(H-h)/2-40,setsar=1[base]")
    graph, prev = [base], "base"
    for i, (png, x, y, t0, t1) in enumerate(overlays, start=1):
        inputs += ["-i", png]
        nxt = f"o{i}"
        graph.append(f"[{prev}][{i}:v]overlay={x}:{y}:enable='between(t,{t0:.3f},{t1:.3f})'[{nxt}]")
        prev = nxt
    graph.append(f"[{prev}]fade=t=in:st=0:d=0.2,fade=t=out:st={L - 0.3:.3f}:d=0.3,format=yuv420p[v]")
    graph.append(f"[0:a]afade=t=in:st=0:d=0.15,afade=t=out:st={L - 0.4:.3f}:d=0.4[aud]")
    dst = ep.out / "shorts" / f"{ep.id}_{spec['id']}.mp4"
    dst.parent.mkdir(parents=True, exist_ok=True)
    script = work / "graph.txt"
    script.write_text(";\n".join(graph))
    run(["ffmpeg", *inputs, "-filter_complex_script", script, "-map", "[v]", "-map", "[aud]",
         "-c:v", "libx264", "-crf", 19, "-preset", "medium", "-c:a", "aac", "-b:a", "256k",
         "-movflags", "+faststart", dst])

    # caption file for posting
    tags = " ".join(spec.get("hashtags", cfg["hashtags"]))
    txt = (f"{spec.get('caption', spec.get('title', ''))}\n\n"
           f"Full story: {channel()['channel']['url']}\n\n{tags}\n")
    dst.with_suffix(".txt").write_text(txt, encoding="utf-8")
    return dst


def build(ep: Episode, only: str | None = None) -> list[Path]:
    path = ep.dir / "shorts.yaml"
    if not path.exists():
        raise StudioError(f"No shorts.yaml in {ep.dir}. List the moments to cut first.")
    master = ep.out / f"{ep.id}_1080p.mp4"
    if not master.exists():
        raise StudioError("Render the master first.")
    srt = ep.out / f"{ep.id}.en.srt"
    made = []
    for spec in load_yaml(path).get("shorts", []):
        if only and spec["id"] != only:
            continue
        print(f"  short {spec['id']}: {spec.get('title', '')}")
        made.append(render_short(ep, spec, master, srt if srt.exists() else None))
    return made
