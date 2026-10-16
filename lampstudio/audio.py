"""Narration cleanup, music bed, and the final voice + music master."""
from __future__ import annotations

from pathlib import Path

from .core import StudioError, channel, duration, loudnorm_two_pass_filter, require, run

NARRATION_LUFS = -18.0  # cleaned narration sits here before the final master


def clean_narration(src: Path, dst: Path) -> Path:
    """Dominique's chain: highpass, denoise, de-ess, gentle compression; then shorten long pauses.

    Pauses longer than keep_pause_seconds are shortened to that length (not removed), so the
    delivery keeps its breathing room. Leading/trailing silence is trimmed.
    """
    a = channel()["audio"]
    require(src, "narration recording")
    dst.parent.mkdir(parents=True, exist_ok=True)
    thr = f"{a['trim_silence_db']}dB"
    keep = a["keep_pause_seconds"]
    trim = (f"silenceremove=start_periods=1:start_threshold={thr}:start_silence=0.08"
            f":stop_periods=-1:stop_threshold={thr}:stop_duration={keep}:stop_silence={keep}")
    tmp = dst.with_suffix(".stage1.wav")
    run(["ffmpeg", "-i", src, "-af", f"{a['clean_chain']},{trim}",
         "-ar", a["sample_rate"], "-ac", 1, "-c:a", "pcm_s24le", tmp])
    norm = loudnorm_two_pass_filter(tmp, NARRATION_LUFS, -3.0, 11)
    run(["ffmpeg", "-i", tmp, "-af", norm, "-ar", a["sample_rate"], "-ac", 1,
         "-c:a", "pcm_s24le", dst])
    tmp.unlink(missing_ok=True)
    return dst


def speech_intervals(path: Path, threshold_db: float = -40, min_silence: float = 0.25) -> list[tuple[float, float]]:
    """(start, end) of spoken stretches, found with silencedetect. Used for caption timing."""
    proc = run(["ffmpeg", "-i", path, "-af",
                f"silencedetect=noise={threshold_db}dB:d={min_silence}", "-f", "null", "-"], quiet=False)
    total = duration(path)
    silences, start = [], None
    for line in proc.stderr.splitlines():
        if "silence_start:" in line:
            start = float(line.split("silence_start:")[1].split()[0])
        elif "silence_end:" in line and start is not None:
            end = float(line.split("silence_end:")[1].split("|")[0])
            silences.append((max(0.0, start), end))
            start = None
    if start is not None:
        silences.append((start, total))
    speech, cursor = [], 0.0
    for s, e in silences:
        if s > cursor + 0.05:
            speech.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < total - 0.05:
        speech.append((cursor, total))
    return speech or [(0.0, total)]


def build_music_bed(music_dir: Path, length: float, dst: Path) -> Path:
    """Suno tracks normalized to -23 LUFS, crossfaded in the configured order, looped to length."""
    a = channel()["audio"]
    order = list(a["music_order"])
    tracks = {}
    for name in set(order):
        found = sorted(music_dir.glob(f"{name}.*")) + sorted(music_dir.glob(f"{name}_*.*"))
        if not found:
            raise StudioError(f"Music track '{name}' not found in {music_dir} (expected e.g. {name}.wav)")
        tracks[name] = found[0]

    work = dst.parent / "music_norm"
    work.mkdir(parents=True, exist_ok=True)
    normed = {}
    for name, src in tracks.items():
        out = work / f"{name}.wav"
        if not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
            f = loudnorm_two_pass_filter(src, a["music_track_lufs"], -2.0, 20)
            run(["ffmpeg", "-i", src, "-af", f, "-ar", a["sample_rate"], "-ac", 2, out])
        normed[name] = out

    xf = a["music_crossfade"]
    seq, total = [], 0.0
    while total < length + 2 or len(seq) < 2:          # repeat the order until it covers the episode
        for name in order:
            seq.append(normed[name])
            total += duration(normed[name]) - xf
            if total >= length + 2 and len(seq) >= 2:
                break
    if len(seq) == 1:
        seq.append(seq[0])

    inputs, graph, prev = [], [], "0:a"
    for p in seq:
        inputs += ["-i", p]
    for i in range(1, len(seq)):
        out = f"x{i}"
        graph.append(f"[{prev}][{i}:a]acrossfade=d={xf}:c1=tri:c2=tri[{out}]")
        prev = out
    graph.append(f"[{prev}]atrim=0:{length:.3f},afade=t=out:st={max(0, length - 4):.3f}:d=4[bed]")
    run(["ffmpeg", *inputs, "-filter_complex", ";".join(graph), "-map", "[bed]",
         "-ar", a["sample_rate"], "-ac", 2, dst])
    return dst


def _gain_expression(speech: list[tuple[float, float]], open_gain: float, under_gain: float,
                     ramp: float = 0.8) -> str:
    """Music volume envelope: open_gain everywhere, dipping to under_gain while she speaks."""
    if not speech:
        return f"{open_gain}"
    terms = []
    for s, e in speech:
        # trapezoid window: ramps down before speech starts, back up after it ends
        terms.append(f"clip((t-{s - ramp:.3f})/{ramp},0,1)*clip(({e + ramp:.3f}-t)/{ramp},0,1)")
    window = "min(1," + "+".join(terms) + ")"
    return f"{open_gain}-({open_gain - under_gain})*{window}"


def merge_intervals(iv: list[tuple[float, float]], gap: float) -> list[tuple[float, float]]:
    out = []
    for s, e in sorted(iv):
        if out and s - out[-1][1] <= gap:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def master_mix(voice: Path, music: Path | None, speech: list[tuple[float, float]], dst: Path) -> Path:
    """Voice + ducked music -> limiter -> two-pass loudnorm (-14 LUFS / -1.5 dBTP by default)."""
    a = channel()["audio"]
    pre = dst.with_suffix(".premaster.wav")
    if music is not None:
        expr = _gain_expression(merge_intervals(speech, 1.5), a["music_open"], a["music_under_voice"])
        graph = (f"[0:a]aformat=channel_layouts=stereo[v];"
                 f"[1:a]volume=volume='{expr}':eval=frame[m];"
                 f"[v][m]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89:level=false[o]")
        run(["ffmpeg", "-i", voice, "-i", music, "-filter_complex", graph, "-map", "[o]",
             "-ar", a["sample_rate"], "-ac", 2, "-c:a", "pcm_s24le", pre])
    else:
        run(["ffmpeg", "-i", voice, "-ac", 2, "-ar", a["sample_rate"], "-c:a", "pcm_s24le", pre])
    norm = loudnorm_two_pass_filter(pre, a["target_lufs"], a["true_peak"], a["lra"])
    run(["ffmpeg", "-i", pre, "-af", norm, "-ar", a["sample_rate"], "-ac", 2, "-c:a", "pcm_s24le", dst])
    pre.unlink(missing_ok=True)
    return dst
