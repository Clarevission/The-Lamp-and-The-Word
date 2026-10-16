"""Animated brand cards (title, verse, label, end screen) and Ken Burns moves for stills.

Every card is drawn with Pillow and piped frame-by-frame into ffmpeg, so the look is exact
and there is no dependency on a desktop editor.
"""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .core import ROOT, StudioError, channel, color, font_path

# ------------------------------------------------------------------ primitives


def font(role: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_path(role)), size)


def ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def background(w: int, h: int, glow_at=(0.5, 0.42), glow=0.55) -> Image.Image:
    """Navy radial gradient with a soft lamp-light glow."""
    dark, navy, gold = np.array(color("navy_dark")), np.array(color("navy")), np.array(color("gold"))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - glow_at[0] * w) / w) ** 2 + ((yy - glow_at[1] * h) / h) ** 2)
    base = np.clip(1 - d / 0.75, 0, 1)[..., None]
    img = dark + (navy - dark) * base
    halo = (np.clip(1 - d / 0.35, 0, 1) ** 2)[..., None] * glow * 0.18
    img = img + (gold - img) * halo
    # gentle vignette
    vig = np.clip(1 - (d - 0.45) * 0.9, 0.55, 1)[..., None]
    img = img * vig + np.random.default_rng(7).uniform(-1.5, 1.5, img.shape)  # dither: no banding
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def text_layer(size, items) -> Image.Image:
    """items: (text, font, fill, (cx, y), anchor) drawn on a transparent layer."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for text, fnt, fill, xy, anchor in items:
        d.text(xy, text, font=fnt, fill=fill, anchor=anchor)
    return layer


def faded(layer: Image.Image, a: float) -> Image.Image:
    """Copy of an RGBA layer with its alpha multiplied by a (0..1)."""
    if a >= 0.999:
        return layer
    out = layer.copy()
    alpha = np.asarray(layer.getchannel("A"), dtype=np.float32) * a
    out.putalpha(Image.fromarray(alpha.astype(np.uint8), "L"))
    return out


def glow(layer: Image.Image, radius: int = 18, strength: float = 0.8) -> Image.Image:
    """Soft gold bloom behind a text layer."""
    a = layer.getchannel("A").filter(ImageFilter.GaussianBlur(radius))
    a = a.point(lambda v: int(v * strength))
    g = Image.new("RGBA", layer.size, color("gold") + (0,))
    g.putalpha(a)
    return g


def emblem(size: int) -> Image.Image:
    """Fallback logo: open book with a flame. Used only if brand/logo.png is missing."""
    s = size
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    gold, cream = color("gold") + (255,), color("cream") + (255,)
    w = max(2, s // 40)
    # pages
    for side in (-1, 1):
        pts = [(s * 0.5, s * 0.78)]
        for i in range(21):
            t = i / 20
            x = s * 0.5 + side * s * 0.40 * t
            y = s * 0.70 - math.sin(t * math.pi) * s * 0.06 + t * s * 0.02
            pts.append((x, y))
        pts.append((s * 0.5 + side * s * 0.40, s * 0.86))
        pts.append((s * 0.5, s * 0.92))
        d.polygon(pts, fill=cream, outline=gold, width=w)
    d.line([(s * 0.5, s * 0.66), (s * 0.5, s * 0.92)], fill=gold, width=w)
    # flame
    flame = []
    for i in range(41):
        t = i / 40 * 2 * math.pi
        r = 0.13 * s
        x = s * 0.5 + math.sin(t) * r * 0.75
        y = s * 0.42 - math.cos(t) * r * (1.9 if math.cos(t) > 0 else 1.0)
        flame.append((x, y))
    d.polygon(flame, fill=gold)
    inner = [(s * 0.5 + (x - s * 0.5) * 0.45, s * 0.50 + (y - s * 0.42) * 0.45) for x, y in flame]
    d.polygon(inner, fill=cream)
    return im


def logo(size: int) -> Image.Image:
    p = ROOT / channel()["brand"]["logo"]
    if p.exists():
        im = Image.open(p).convert("RGBA")
        im.thumbnail((size, size), Image.LANCZOS)
        return im
    return emblem(size)


# ------------------------------------------------------------------ rendering


def _encoder(dst: Path, w: int, h: int, fps: int) -> subprocess.Popen:
    dst.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "14",
         "-preset", "veryfast", "-pix_fmt", "yuv420p", str(dst)],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE)


def render_frames(dst: Path, seconds: float, frame_fn, size=None, fps=None) -> Path:
    v = channel()["video"]
    w, h = size or (v["width"], v["height"])
    fps = fps or v["fps"]
    n = max(1, round(seconds * fps))
    enc = _encoder(dst, w, h, fps)
    try:
        for i in range(n):
            frame = frame_fn(i / fps, i, n)
            enc.stdin.write(frame.convert("RGB").tobytes())
        enc.stdin.close()
        if enc.wait() != 0:
            raise StudioError(f"Encoding {dst.name} failed: {enc.stderr.read().decode()[-400:]}")
    except BrokenPipeError:
        raise StudioError(f"Encoding {dst.name} failed: {enc.stderr.read().decode()[-400:]}")
    return dst


def _scale_center(img: Image.Image, scale: float, size) -> Image.Image:
    """Scale an image about its centre with sub-pixel precision (no jitter)."""
    w, h = size
    cx, cy = img.width / 2, img.height / 2
    a = 1 / scale
    return img.transform(size, Image.AFFINE, (a, 0, cx - a * w / 2, 0, a, cy - a * h / 2),
                         resample=Image.BICUBIC)


def title_card(dst: Path, seconds: float, title: str, subtitle: str = "") -> Path:
    v = channel()["video"]
    W, H = v["width"], v["height"]
    bg = background(W, H, glow_at=(0.5, 0.36))
    mark = logo(int(H * 0.26))
    tf = font("title", 104)
    d = ImageDraw.Draw(bg)
    lines = wrap(d, title.upper(), tf, int(W * 0.8))
    y0 = int(H * 0.60) - (len(lines) - 1) * 60
    items = [(ln, tf, color("gold") + (255,), (W // 2, y0 + i * 120), "mm") for i, ln in enumerate(lines)]
    if subtitle:
        items.append((subtitle, font("serif_italic", 54), color("cream") + (255,),
                      (W // 2, y0 + len(lines) * 120 + 10), "mm"))
    txt = text_layer((W, H), items)
    halo = glow(txt, 22, 0.55)

    def frame(t, i, n):
        im = _scale_center(bg, 1.0 + 0.035 * (i / n), (W, H)).convert("RGBA")
        a_logo = ease(t / 1.0)
        a_txt = ease((t - 0.5) / 1.0)
        out = seconds - t
        fade_out = ease(out / 0.6)
        m = faded(mark, a_logo * fade_out)
        im.alpha_composite(m, (W // 2 - m.width // 2, int(H * 0.30) - m.height // 2))
        for layer in (halo, txt):
            im.alpha_composite(faded(layer, a_txt * fade_out))
        return im

    return render_frames(dst, seconds, frame)


def load_verse(verses_file: Path, ref: str) -> str:
    """Exact NLT text supplied by Dominique. Refuses to guess."""
    if not verses_file.exists():
        raise StudioError(f"Verse card '{ref}' needs {verses_file} with the exact NLT text Dominique supplied.")
    data = json.loads(verses_file.read_text(encoding="utf-8"))
    if isinstance(data, list):                      # [{"ref": ..., "text": ...}, ...]
        data = {d.get("ref") or d.get("reference"): d for d in data if isinstance(d, dict)}
    norm = lambda r: "".join(str(r).lower().replace("\u2013", "-").replace("\u2014", "-").split())
    entry = next((v for k, v in data.items() if norm(k) == norm(ref)), None)
    text = (entry.get("text") or entry.get("nlt")) if isinstance(entry, dict) else entry
    if not text or "PASTE" in text.upper():
        raise StudioError(f"verses.json has no text for '{ref}' yet. Paste the exact NLT wording first.")
    return text.strip()


def verse_seconds(text: str) -> float:
    """Long enough to read comfortably: ~2.6 words/s plus lead-in and hold."""
    return round(max(6.0, len(text.split()) / 2.6 + 3.0), 1)


def verse_card(dst: Path, seconds: float, ref: str, text: str) -> Path:
    v = channel()["video"]
    W, H = v["width"], v["height"]
    bg = background(W, H, glow_at=(0.5, 0.5), glow=0.35)
    size = 66 if len(text) < 220 else 56 if len(text) < 380 else 48
    vf = font("serif", size)
    d = ImageDraw.Draw(bg)
    lines = wrap(d, f"“{text}”", vf, int(W * 0.72))
    lh = int(size * 1.32)
    block = lh * len(lines)
    top = (H - block) // 2 - 40
    line_layers = [text_layer((W, H), [(ln, vf, color("cream") + (255,), (W // 2, top + i * lh), "mt")])
                   for i, ln in enumerate(lines)]
    ref_layer = text_layer((W, H), [
        (ref.upper(), font("title_alt", 46), color("gold") + (255,), (W // 2, top + block + 50), "mt"),
        (channel()["scripture"]["translation"], font("label", 26), color("gold") + (200,),
         (W // 2, top + block + 112), "mt")])
    rule_y = top - 50
    reveal = max(1.5, seconds * 0.55)  # all lines visible by 55% of the card

    def frame(t, i, n):
        im = _scale_center(bg, 1.0 + 0.03 * (i / n), (W, H)).convert("RGBA")
        dd = ImageDraw.Draw(im)
        rw = int(W * 0.10 * ease(t / 0.8))
        dd.line([(W // 2 - rw, rule_y), (W // 2 + rw, rule_y)], fill=color("gold") + (255,), width=3)
        fade_out = ease((seconds - t) / 0.6)
        for k, layer in enumerate(line_layers):
            start = 0.4 + k * (reveal / max(1, len(line_layers)))
            a = ease((t - start) / 0.7) * fade_out
            if a > 0:
                im.alpha_composite(faded(layer, a))
        a = ease((t - reveal - 0.3) / 0.8) * fade_out
        if a > 0:
            im.alpha_composite(faded(ref_layer, a))
        return im

    return render_frames(dst, seconds, frame)


def label_card(dst: Path, seconds: float, kicker: str, text: str) -> Path:
    """'PART 2' style divider for splitting long teaching into labelled parts."""
    v = channel()["video"]
    W, H = v["width"], v["height"]
    bg = background(W, H, glow=0.3)
    layer = text_layer((W, H), [
        (kicker.upper(), font("label_bold", 36), color("gold") + (255,), (W // 2, H // 2 - 70), "mm"),
        (text, font("serif", 84), color("cream") + (255,), (W // 2, H // 2 + 20), "mm")])

    def frame(t, i, n):
        im = bg.copy().convert("RGBA")
        a = ease(t / 0.5) * ease((seconds - t) / 0.5)
        im.alpha_composite(faded(layer, a))
        return im

    return render_frames(dst, seconds, frame)


def end_screen(dst: Path, seconds: float = 20.0, line: str = "Keep walking in the light",
               guides: bool = False) -> Path:
    """Background for YouTube's end screen (5-20 s). Leaves clean space for:
    a Subscribe element (left circle) and a playlist / best-for-viewer element (right box).
    guides=True draws the zones so placement can be checked; keep False for the real render."""
    v = channel()["video"]
    W, H = v["width"], v["height"]
    bg = background(W, H, glow_at=(0.5, 0.2), glow=0.4)
    mark = logo(150)
    top = text_layer((W, H), [
        (line, font("serif_italic", 64), color("cream") + (255,), (W // 2, 210), "mm"),
        (channel()["channel"]["name"].upper(), font("title_alt", 34), color("gold") + (255,), (W // 2, 290), "mm")])
    # YouTube element zones (approx.): subscribe circle and a 16:9 video/playlist card.
    sub_c, sub_r = (int(W * 0.30), int(H * 0.64)), 150
    box = (int(W * 0.47), int(H * 0.47), int(W * 0.47) + 640, int(H * 0.47) + 360)
    zones = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    z = ImageDraw.Draw(zones)
    z.ellipse([sub_c[0] - sub_r - 14, sub_c[1] - sub_r - 14, sub_c[0] + sub_r + 14, sub_c[1] + sub_r + 14],
              outline=color("gold") + (110,), width=3)
    z.rounded_rectangle([box[0] - 14, box[1] - 14, box[2] + 14, box[3] + 14], 18,
                        outline=color("gold") + (110,), width=3)
    if guides:
        z.ellipse([sub_c[0] - sub_r, sub_c[1] - sub_r, sub_c[0] + sub_r, sub_c[1] + sub_r], fill=(255, 0, 0, 90))
        z.rectangle(box, fill=(255, 0, 0, 90))
    labels = text_layer((W, H), [
        ("SUBSCRIBE", font("label_bold", 30), color("gold") + (230,), (sub_c[0], sub_c[1] + sub_r + 50), "mm"),
        ("WATCH NEXT", font("label_bold", 30), color("gold") + (230,), ((box[0] + box[2]) // 2, box[3] + 50), "mm")])

    def frame(t, i, n):
        im = bg.copy().convert("RGBA")
        a = ease(t / 0.8) * ease((seconds - t) / 1.0)
        for layer in (top, zones, labels):
            im.alpha_composite(faded(layer, a))
        m = faded(mark, a)
        im.alpha_composite(m, (W // 2 - m.width // 2, 20))
        return im

    return render_frames(dst, seconds, frame)


def ken_burns(src: Path, dst: Path, seconds: float, zoom=(1.0, 1.12), pan=(0.0, 0.0)) -> Path:
    """Smooth push-in on a still (fallback when parallax.py has not produced a clip)."""
    v = channel()["video"]
    W, H = v["width"], v["height"]
    img = Image.open(src).convert("RGB")
    s = max(W * 1.25 / img.width, H * 1.25 / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)

    def frame(t, i, n):
        p = ease(i / max(1, n - 1))
        z = zoom[0] + (zoom[1] - zoom[0]) * p
        sc = z / 1.25
        a = 1 / sc
        cx = img.width / 2 + pan[0] * img.width * 0.08 * p
        cy = img.height / 2 + pan[1] * img.height * 0.08 * p
        return img.transform((W, H), Image.AFFINE, (a, 0, cx - a * W / 2, 0, a, cy - a * H / 2),
                             resample=Image.BICUBIC)

    return render_frames(dst, seconds, frame)
