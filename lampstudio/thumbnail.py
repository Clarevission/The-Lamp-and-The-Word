"""Brand thumbnails (1280x720 JPG): big Cinzel words, gold accent, verse reference pill.

Make 2-3 variants per video and load them into YouTube's Test & Compare.
Spec (episode.yaml > thumbnails):
  - id: A
    lines: ["LOST", "FOUND"]
    accent: [1]                 # which lines are gold (0-based); others cream
    ref: "Luke 15:24"
    image: inputs/stills/X1.png # or frame: "4:31" (grab from the master), or omit for brand background
    side: left                  # which side the words sit on
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import cards
from .core import StudioError, color, run
from .shorts import parse_t
from .timeline import Episode

W, H = 1280, 720


def _cover(img: Image.Image) -> Image.Image:
    s = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def _shade(img: Image.Image, side: str) -> Image.Image:
    """Darken the text side with a navy gradient so the words always read."""
    arr = np.asarray(img).astype(np.float32)
    x = np.linspace(0, 1, W)[None, :, None]
    if side == "right":
        x = 1 - x
    if side == "center":
        k = np.full((1, W, 1), 0.55)
    else:
        k = np.clip(1.15 - x * 1.3, 0, 0.88)
    navy = np.array(color("navy_dark"), dtype=np.float32)
    arr = arr * (1 - k) + navy * k
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))


def render(spec: dict, bg: Image.Image | None, dst: Path) -> Path:
    side = spec.get("side", "left")
    img = _shade(_cover(bg.convert("RGB")), side) if bg else cards.background(W, H, glow_at=(0.72, 0.4), glow=0.9)
    img = img.convert("RGBA")
    lines = [str(x).upper() for x in spec["lines"]]
    accent = set(spec.get("accent", [len(lines) - 1]))
    # biggest size where the widest line fills ~58% of the width and the block ~64% of the height
    max_w = W * (0.80 if side == "center" else 0.58)
    probe_d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    size = 220
    while size > 60:
        fnt = cards.font("title", size)
        widest = max(probe_d.textlength(x, font=fnt) for x in lines)
        if widest <= max_w and size * len(lines) <= H * 0.64:
            break
        size -= 6
    lh = int(size * 1.0)
    block = lh * len(lines)
    y0 = (H - block) // 2 - (30 if spec.get("ref") else 0)
    x = {"left": 70, "right": W - 70, "center": W // 2}[side]
    anchor = {"left": "lt", "right": "rt", "center": "mt"}[side]

    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds, dt = ImageDraw.Draw(shadow), ImageDraw.Draw(txt)
    for i, ln in enumerate(lines):
        fill = color("gold") if i in accent else color("cream")
        ds.text((x + 6, y0 + i * lh + 8), ln, font=fnt, fill=(0, 0, 0, 220), anchor=anchor)
        dt.text((x, y0 + i * lh), ln, font=fnt, fill=fill + (255,), anchor=anchor,
                stroke_width=3, stroke_fill=color("navy_dark") + (255,))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10)))
    img.alpha_composite(cards.glow(txt, 26, 0.35))
    img.alpha_composite(txt)

    if spec.get("ref"):
        f = cards.font("label_bold", 38)
        d = ImageDraw.Draw(img)
        tw = d.textlength(spec["ref"].upper(), font=f)
        py = y0 + block + 24
        px = {"left": x, "right": x - tw - 44, "center": x - (tw + 44) / 2}[side]
        d.rounded_rectangle([px, py, px + tw + 44, py + 62], 31, fill=color("gold") + (255,))
        d.text((px + 22, py + 31), spec["ref"].upper(), font=f, fill=color("navy_dark") + (255,), anchor="lm")

    mark = cards.logo(84)
    mx = W - mark.width - 26 if side != "right" else 26
    img.alpha_composite(mark, (mx, H - mark.height - 22))
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(dst, "JPEG", quality=92, optimize=True)
    if dst.stat().st_size > 2 * 1024 * 1024:
        img.convert("RGB").save(dst, "JPEG", quality=82, optimize=True)
    return dst


def build(ep: Episode) -> list[Path]:
    specs = ep.cfg.get("thumbnails", [])
    if not specs:
        raise StudioError("episode.yaml has no thumbnails section.")
    made = []
    for spec in specs:
        bg = None
        if spec.get("image"):
            p = (ep.dir / spec["image"])
            if p.exists():
                bg = Image.open(p)
            else:
                print(f"  ! thumbnail {spec['id']}: {p.name} not found, using brand background")
        elif spec.get("frame"):
            master = ep.out / f"{ep.id}_1080p.mp4"
            if master.exists():
                grab = ep.work / f"thumb_frame_{spec['id']}.png"
                grab.parent.mkdir(parents=True, exist_ok=True)
                run(["ffmpeg", "-ss", parse_t(spec["frame"]), "-i", master, "-frames:v", 1, grab])
                bg = Image.open(grab)
        made.append(render(spec, bg, ep.out / "upload" / f"thumbnail_{spec['id']}.jpg"))
        print(f"  thumbnail {spec['id']}: {' / '.join(spec['lines'])}")
    return made
