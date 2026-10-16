"""Shared helpers: config, paths, ffmpeg/ffprobe wrappers, fonts."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


class StudioError(RuntimeError):
    """A problem Dominique can fix (missing file, bad setting). Printed without a traceback."""


@lru_cache(maxsize=None)
def channel() -> dict:
    with open(ROOT / "channel.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def color(name: str) -> tuple[int, int, int]:
    return hex_rgb(channel()["brand"][name])


def font_path(role: str) -> Path:
    p = ROOT / "fonts" / channel()["brand"]["fonts"][role]
    if not p.exists():
        raise StudioError(f"Font for '{role}' not found at {p}")
    return p


def require(path: Path, what: str) -> Path:
    if not Path(path).exists():
        raise StudioError(f"Missing {what}: {path}")
    return Path(path)


# ---------------------------------------------------------------- ffmpeg

def _check_tools() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise StudioError(f"{tool} is not installed. Install ffmpeg (with libx264) first.")


def run(args: list, quiet: bool = True) -> subprocess.CompletedProcess:
    """Run ffmpeg/ffprobe; raise StudioError with the tail of stderr on failure."""
    _check_tools()
    args = [str(a) for a in args]
    if args[0] == "ffmpeg":
        args[1:1] = ["-hide_banner", "-nostdin", "-y"] + (["-loglevel", "error"] if quiet else [])
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        raise StudioError(f"{args[0]} failed:\n{tail}")
    return proc


def probe(path: Path) -> dict:
    out = run(["ffprobe", "-v", "error", "-print_format", "json",
               "-show_format", "-show_streams", path]).stdout
    return json.loads(out)


def duration(path: Path) -> float:
    return float(probe(path)["format"]["duration"])


def has_audio(path: Path) -> bool:
    return any(s["codec_type"] == "audio" for s in probe(path)["streams"])


def video_stream(path: Path) -> dict | None:
    return next((s for s in probe(path)["streams"] if s["codec_type"] == "video"), None)


def measure_loudness(path: Path) -> dict:
    """Integrated loudness, true peak and LRA via loudnorm's analysis pass."""
    proc = run(["ffmpeg", "-i", path, "-af", "loudnorm=print_format=json", "-f", "null", "-"],
               quiet=False)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", proc.stderr, re.S)
    if not m:
        raise StudioError(f"Could not measure loudness of {path}")
    d = json.loads(m.group(0))
    return {"lufs": float(d["input_i"]), "true_peak": float(d["input_tp"]),
            "lra": float(d["input_lra"]), "thresh": float(d["input_thresh"]),
            "offset": float(d["target_offset"])}


def loudnorm_two_pass_filter(src: Path, i: float, tp: float, lra: float) -> str:
    """Measured (two-pass) loudnorm. Single-pass loudnorm can miss the target by 1-2 LU."""
    m = measure_loudness(src)
    return (f"loudnorm=I={i}:TP={tp}:LRA={lra}:measured_I={m['lufs']}:measured_TP={m['true_peak']}"
            f":measured_LRA={m['lra']}:measured_thresh={m['thresh']}:offset={m['offset']}"
            f":linear=true:print_format=summary")


def fmt_ts(seconds: float) -> str:
    """0:00 style timestamp for YouTube chapters."""
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
