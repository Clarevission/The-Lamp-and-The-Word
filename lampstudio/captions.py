"""Captions: an accurate SRT aligned to Dominique's script, plus a plain transcript.

Two ways to get timing:
  * script alignment (default, no extra installs): her script text is spread across the
    spoken stretches of each cleaned narration file, snapping sentence ends to pauses.
  * Whisper (optional, more precise): `pip install faster-whisper`, then use --whisper.

YouTube tip: in Studio > Subtitles you can also upload transcript.txt with "Without timing"
and YouTube auto-syncs it to her voice.
"""
from __future__ import annotations

import re
from pathlib import Path

from .audio import speech_intervals
from .core import StudioError, channel
from .timeline import Episode, load_timeline

MAX_CHARS = 42


def _srt_time(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(int(t * 1000), 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(cues: list[tuple[float, float, str]], dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("".join(f"{i}\n{_srt_time(a)} --> {_srt_time(b)}\n{t}\n\n"
                           for i, (a, b, t) in enumerate(cues, 1)), encoding="utf-8")
    return dst


def read_srt(path: Path) -> list[tuple[float, float, str]]:
    def secs(ts):
        h, m, rest = ts.split(":")
        s, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    cues = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8").strip()):
        lines = block.strip().splitlines()
        if len(lines) >= 3 and "-->" in lines[1]:
            a, b = [x.strip() for x in lines[1].split("-->")]
            cues.append((secs(a), secs(b), " ".join(lines[2:])))
    return cues


def clean_script(text: str) -> str:
    """Strip markdown, stage directions [like this] and (pauses) from a script."""
    text = re.sub(r"^#.*$", "", text, flags=re.M)
    text = re.sub(r"\[[^\]]*\]|\([^)]*pause[^)]*\)", "", text, flags=re.I)
    text = re.sub(r"[*_>`]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def chunk(text: str, max_chars: int = MAX_CHARS) -> list[tuple[str, bool]]:
    """Caption-sized pieces. Returns (piece, ends_sentence)."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", text):
        words = sent.split()
        if not words:
            continue
        pieces = _balanced(words, max_chars)
        out += [(p, i == len(pieces) - 1) for i, p in enumerate(pieces)]
    return out


def _balanced(words: list[str], max_chars: int) -> list[str]:
    """Fewest lines that fit, then the most even lengths, preferring breaks after commas."""
    n = len(words)
    lines_needed = max(1, -(-len(" ".join(words)) // max_chars))
    target = len(" ".join(words)) / lines_needed
    best = [(0.0, 0)] + [(float("inf"), 0)] * n       # (cost, previous break)
    count = [0] + [10 ** 6] * n
    for j in range(1, n + 1):
        for i in range(j - 1, -1, -1):
            line = " ".join(words[i:j])
            if len(line) > max_chars and j - i > 1:
                break
            cost = (len(line) - target) ** 2
            if j < n and line.endswith((",", ";", ":")):
                cost -= target * 2
            c = best[i][0] + cost
            if (count[i] + 1, c) < (count[j], best[j][0]):
                best[j], count[j] = (c, i), count[i] + 1
    out, j = [], n
    while j > 0:
        i = best[j][1]
        out.append(" ".join(words[i:j]))
        j = i
    return out[::-1]


def align(text: str, speech: list[tuple[float, float]]) -> list[tuple[float, float, str]]:
    """Spread caption chunks over spoken stretches in proportion to their length."""
    pieces = chunk(text)
    if not pieces:
        return []
    talk = sum(e - s for s, e in speech)
    total_chars = sum(len(p) for p, _ in pieces)

    def at(frac: float) -> float:          # fraction of speech time -> real time
        target, acc = frac * talk, 0.0
        for s, e in speech:
            if acc + (e - s) >= target:
                return s + (target - acc)
            acc += e - s
        return speech[-1][1]

    pauses = [e for _, e in speech[:-1]]   # ends of speech stretches = pause starts
    cues, done = [], 0
    for piece, sentence_end in pieces:
        a = at(done / total_chars)
        done += len(piece)
        b = at(done / total_chars)
        if sentence_end and pauses:
            near = min(pauses, key=lambda p: abs(p - b))
            if abs(near - b) < 0.6 and near > a + 0.4:
                b = near
        cues.append([a, b, piece])
    for i in range(1, len(cues)):          # no overlaps, no gaps under 80 ms
        cues[i][0] = max(cues[i][0], cues[i - 1][1])
        if cues[i][0] - cues[i - 1][1] < 0.08:
            cues[i - 1][1] = cues[i][0]
    return [(a, max(b, a + 0.5), t) for a, b, t in cues]


def whisper_cues(audio_path: Path) -> list[tuple[float, float, str]]:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise StudioError("Whisper not installed. Run: pip install faster-whisper (or drop --whisper).")
    model = WhisperModel("small.en", compute_type="int8")
    segments, _ = model.transcribe(str(audio_path), word_timestamps=True, vad_filter=True)
    cues, cur, start = [], "", None
    for seg in segments:
        for w in seg.words:
            word = w.word.strip()
            if start is None:
                start = w.start
            if len(cur) + len(word) + 1 > MAX_CHARS and cur:
                cues.append((start, w.start, cur))
                cur, start = word, w.start
            else:
                cur = f"{cur} {word}".strip()
            if cur.endswith((".", "?", "!")):
                cues.append((start, w.end, cur))
                cur, start = "", None
    if cur:
        cues.append((start, seg.end, cur))
    return cues


def build(ep: Episode, use_whisper: bool = False) -> Path:
    tl = load_timeline(ep)
    before = ep.cfg.get("pad", {}).get("before", 0.4)
    cues, transcript = [], []
    if use_whisper:
        cues = whisper_cues(ep.work / "master_audio.wav")
    for sec in tl["sections"]:
        if not sec["narration"]:
            continue
        script = ep.scripts_dir / (sec["script"] or Path(sec["narration"]).stem.replace("_clean", "") + ".txt")
        if not script.exists():
            print(f"  ! no script text for section '{sec['id']}' ({script.name}); skipped in captions")
            continue
        text = clean_script(script.read_text(encoding="utf-8"))
        transcript.append(text)
        if not use_whisper:
            offset = sec["start"] + before
            for a, b, t in align(text, speech_intervals(Path(sec["narration"]))):
                cues.append((a + offset, b + offset, t))
    if not cues:
        raise StudioError(f"No captions made: add script text files to {ep.scripts_dir}")
    (ep.out / "transcript.txt").write_text("\n\n".join(transcript) + "\n", encoding="utf-8")
    return write_srt(cues, ep.out / f"{ep.id}.en.srt")
