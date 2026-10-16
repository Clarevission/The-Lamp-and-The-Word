"""Episode timeline: time every shot to Dominique's narration, render, mix and encode.

An episode is described by episode.yaml (see episodes/faith_talk_01/episode.yaml).
Each section is either narrated (her WAV plus a list of shots spread across it) or a card
interlude (title card, end screen) where the music comes up.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import audio, cards
from .core import StudioError, channel, duration, load_yaml, run

VIDEO_EXT = (".mp4", ".mov", ".m4v", ".webm", ".mkv")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
STILL_NATURAL = 7.0      # preferred length for a Ken Burns still
MAX_STRETCH = 1.25       # slow a clip by at most 25% before holding its last frame


@dataclass
class Shot:
    id: str
    kind: str                      # clip | still | card
    src: str = ""
    card: str = ""
    natural: float = 0.0           # usable source length (clips); 0 = flexible
    fixed: float = 0.0             # forced length (cards)
    at: float | None = None        # pin start, seconds from section start
    src_in: float = 0.0
    opts: dict = field(default_factory=dict)
    start: float = 0.0
    frames: int = 0
    seconds: float = 0.0
    speed: float = 1.0
    warnings: list = field(default_factory=list)


@dataclass
class Section:
    id: str
    chapter: str = ""
    narration: str = ""            # cleaned narration path
    narration_seconds: float = 0.0
    script: str = ""
    start: float = 0.0
    seconds: float = 0.0
    shots: list = field(default_factory=list)


class Episode:
    def __init__(self, folder: Path):
        self.dir = Path(folder).resolve()
        self.cfg = load_yaml(self.dir / "episode.yaml")
        self.id = self.cfg.get("id", self.dir.name)
        ins = self.cfg.get("inputs", {})
        p = lambda k, d: (self.dir / ins.get(k, d)).resolve()
        self.narration_dir = p("narration", "inputs/narration")
        self.clips_dir = p("clips", "inputs/clips")
        self.stills_dir = p("stills", "inputs/stills")
        self.music_dir = p("music", "../../music")
        self.verses = p("verses", "verses.json")
        self.scripts_dir = p("scripts", "script")
        self.out = self.dir / "out"
        self.work = self.dir / "work"

    # ---------------------------------------------------------- inputs

    def find_source(self, sid: str) -> tuple[str, Path | None]:
        for ext in VIDEO_EXT:
            for f in (self.clips_dir / f"{sid}{ext}", self.clips_dir / f"{sid}_parallax{ext}"):
                if f.exists():
                    return "clip", f
        for ext in IMAGE_EXT:
            f = self.stills_dir / f"{sid}{ext}"
            if f.exists():
                return "still", f
        return "missing", None

    def missing_inputs(self) -> list[str]:
        """Human-readable list of everything still needed before a full render."""
        need, shots = [], []
        for sec in self.cfg["sections"]:
            if sec.get("narration") and not (self.narration_dir / sec["narration"]).exists():
                need.append(f"narration recording {sec['narration']} (in {self.narration_dir})")
            for spec in self._shot_specs(sec):
                if spec.get("card") == "verse":
                    try:
                        cards.load_verse(self.verses, spec["ref"])
                    except StudioError as e:
                        need.append(str(e))
                elif not spec.get("card"):
                    kind, _ = self.find_source(spec["id"])
                    if kind == "missing":
                        shots.append(str(spec["id"]))
        if shots:
            need.append(f"{len(shots)} clips/stills (in inputs/clips or inputs/stills): {', '.join(shots)}")
        if not any(self.music_dir.glob("s0.*")):
            need.append(f"Suno music tracks s0..s3 (in {self.music_dir})")
        return need

    @staticmethod
    def _shot_specs(sec: dict) -> list[dict]:
        if sec.get("card"):
            return [{"id": sec["id"], "card": sec["card"], "seconds": sec.get("seconds"), **sec}]
        return [{"id": s} if isinstance(s, str) else dict(s) for s in sec.get("shots", [])]

    # ---------------------------------------------------------- planning

    def prepare_audio(self) -> None:
        """Clean every narration WAV (cached until the raw file changes)."""
        for sec in self.cfg["sections"]:
            if not sec.get("narration"):
                continue
            raw = self.narration_dir / sec["narration"]
            clean = self.work / "narration" / (Path(sec["narration"]).stem + "_clean.wav")
            if not clean.exists() or clean.stat().st_mtime < raw.stat().st_mtime:
                print(f"  cleaning {raw.name}")
                audio.clean_narration(raw, clean)

    def plan(self) -> list[Section]:
        v = channel()["video"]
        fps = v["fps"]
        pad = self.cfg.get("pad", {})
        before, after = pad.get("before", 0.4), pad.get("after", 0.6)
        sections, t = [], 0.0
        for sec in self.cfg["sections"]:
            s = Section(id=sec["id"], chapter=sec.get("chapter", ""), start=t,
                        script=sec.get("script", ""))
            if sec.get("narration"):
                clean = self.work / "narration" / (Path(sec["narration"]).stem + "_clean.wav")
                if not clean.exists():
                    raise StudioError(f"Narration {sec['narration']} not cleaned yet (run the build).")
                s.narration = str(clean)
                s.narration_seconds = duration(clean)
                s.seconds = before + s.narration_seconds + after
            else:
                s.seconds = float(sec.get("seconds", 5))
            s.shots = [self._make_shot(spec) for spec in self._shot_specs(sec)]
            self._time_section(s)
            sections.append(s)
            t += s.seconds

        # snap every boundary to the frame grid so the total is exact
        for s in sections:
            for sh in s.shots:
                a = round((s.start + sh.start) * fps)
                b = round((s.start + sh.start + sh.seconds) * fps)
                sh.frames = max(1, b - a)
        t = 0.0
        for s in sections:            # rebuild starts from whole frames
            s.start, local = t, 0
            for sh in s.shots:
                sh.start, sh.seconds = local / fps, sh.frames / fps
                local += sh.frames
            s.seconds = local / fps
            t += s.seconds
        return sections

    def _make_shot(self, spec: dict) -> Shot:
        sid = str(spec["id"])
        known = {"id", "card", "seconds", "at", "in", "narration", "chapter", "shots", "script"}
        opts = {k: v for k, v in spec.items() if k not in known}
        sh = Shot(id=sid, kind="card", card=spec.get("card", ""), at=spec.get("at"),
                  src_in=float(spec.get("in", 0)), opts=opts)
        if sh.card:
            if sh.card == "verse":
                text = cards.load_verse(self.verses, spec["ref"])
                sh.opts["text"] = text
                sh.fixed = float(spec.get("seconds") or cards.verse_seconds(text))
            elif sh.card == "label":
                sh.fixed = float(spec.get("seconds") or 2.5)
            else:
                sh.fixed = float(spec.get("seconds") or 0)
            return sh
        kind, src = self.find_source(sid)
        if kind == "missing":
            raise StudioError(f"No clip or still found for shot {sid}.")
        sh.kind, sh.src = kind, str(src)
        if kind == "clip":
            sh.natural = max(0.5, duration(src) - sh.src_in)
        if spec.get("seconds"):
            sh.fixed = float(spec["seconds"])
        return sh

    def _time_section(self, s: Section) -> None:
        """Spread the section's length over its shots. Pinned shots ('at') split it into groups."""
        if len(s.shots) == 1 and s.shots[0].kind == "card" and not s.shots[0].fixed:
            s.shots[0].fixed = s.seconds
        groups, cur = [], []
        for sh in s.shots:
            if sh.at is not None and cur:
                groups.append(cur)
                cur = []
            cur.append(sh)
        groups.append(cur)
        max_shot = channel()["video"]["max_shot_seconds"]
        for gi, g in enumerate(groups):
            g_start = g[0].at if g[0].at is not None else 0.0
            nxt = groups[gi + 1][0].at if gi + 1 < len(groups) else s.seconds
            span = nxt - g_start
            if span <= 0:
                raise StudioError(f"Section '{s.id}': pinned times overlap near shot {g[0].id}.")
            fixed = sum(sh.fixed for sh in g if sh.fixed)
            flex = [sh for sh in g if not sh.fixed]
            remaining = span - fixed
            if not flex:
                scale = span / fixed
                for sh in g:
                    sh.seconds = sh.fixed * scale
            elif remaining <= 0.5 * len(flex):
                raise StudioError(f"Section '{s.id}': cards need {fixed:.1f}s but only {span:.1f}s available.")
            else:
                weights = [sh.natural or STILL_NATURAL for sh in flex]
                for sh, w in zip(flex, weights):
                    sh.seconds = remaining * w / sum(weights)
                for sh in g:
                    if sh.fixed:
                        sh.seconds = sh.fixed
            t = g_start
            for sh in g:
                sh.start = t
                t += sh.seconds
                if sh.kind == "clip" and sh.seconds > sh.natural:
                    sh.speed = min(MAX_STRETCH, sh.seconds / sh.natural)
                    if sh.seconds > sh.natural * MAX_STRETCH + 0.05:
                        sh.warnings.append(
                            f"needs {sh.seconds:.1f}s but clip is {sh.natural:.1f}s: holds last frame "
                            f"{sh.seconds - sh.natural * MAX_STRETCH:.1f}s. Add a spare shot to section '{s.id}'.")
                if sh.seconds > max_shot:
                    sh.warnings.append(f"on screen {sh.seconds:.1f}s (> {max_shot}s retention rule). Add a shot.")

    # ---------------------------------------------------------- rendering

    def _shot_file(self, idx: int, sh: Shot) -> Path:
        key = json.dumps([sh.kind, sh.src, sh.card, sh.frames, sh.speed, sh.src_in, sh.opts,
                          Path(sh.src).stat().st_mtime if sh.src else 0,
                          channel()["video"]], sort_keys=True, default=str)
        h = hashlib.md5(key.encode()).hexdigest()[:8]
        return self.work / "shots" / f"{idx:03d}_{sh.id}_{h}.mp4"

    def render_shot(self, idx: int, sh: Shot, title: dict) -> Path:
        dst = self._shot_file(idx, sh)
        if dst.exists():
            return dst
        dst.parent.mkdir(parents=True, exist_ok=True)
        v = channel()["video"]
        W, H, fps = v["width"], v["height"], v["fps"]
        secs = sh.frames / fps
        if sh.kind == "clip":
            vf = (f"trim=start={sh.src_in},setpts=(PTS-STARTPTS)*{sh.speed:.4f},fps={fps},"
                  f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},setsar=1,"
                  f"tpad=stop_mode=clone:stop_duration=60,format=yuv420p")
            run(["ffmpeg", "-i", sh.src, "-an", "-vf", vf, "-frames:v", sh.frames, "-r", fps,
                 "-c:v", "libx264", "-crf", 14, "-preset", "veryfast", dst])
        elif sh.kind == "still":
            cards.ken_burns(Path(sh.src), dst, secs, zoom=tuple(sh.opts.get("zoom", (1.0, 1.12))),
                            pan=tuple(sh.opts.get("pan", (0.0, 0.0))))
        elif sh.card == "verse":
            cards.verse_card(dst, secs, sh.opts["ref"], sh.opts["text"])
        elif sh.card == "title":
            cards.title_card(dst, secs, sh.opts.get("title", title.get("title", "")),
                             sh.opts.get("subtitle", title.get("subtitle", "")))
        elif sh.card == "label":
            cards.label_card(dst, secs, sh.opts.get("kicker", ""), sh.opts.get("text", ""))
        elif sh.card == "end_screen":
            cards.end_screen(dst, secs, sh.opts.get("line", "Keep walking in the light"))
        else:
            raise StudioError(f"Unknown card type '{sh.card}' for shot {sh.id}")
        return dst

    def build_voice(self, sections: list[Section]) -> tuple[Path, list[tuple[float, float]]]:
        a = channel()["audio"]
        before = self.cfg.get("pad", {}).get("before", 0.4)
        parts, speech = [], []
        for i, s in enumerate(sections):
            part = self.work / "voice" / f"{i:02d}_{s.id}.wav"
            part.parent.mkdir(parents=True, exist_ok=True)
            if s.narration:
                ms = int(before * 1000)
                run(["ffmpeg", "-i", s.narration, "-af",
                     f"adelay={ms},apad=whole_dur={s.seconds:.6f},atrim=0:{s.seconds:.6f}",
                     "-ar", a["sample_rate"], "-ac", 1, "-c:a", "pcm_s24le", part])
                speech.append((s.start + before, s.start + before + s.narration_seconds))
            else:
                run(["ffmpeg", "-f", "lavfi", "-i", f"anullsrc=r={a['sample_rate']}:cl=mono",
                     "-t", f"{s.seconds:.6f}", "-c:a", "pcm_s24le", part])
            parts.append(part)
        lst = self.work / "voice" / "list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in parts))
        voice = self.work / "voice.wav"
        run(["ffmpeg", "-f", "concat", "-safe", 0, "-i", lst, "-c", "copy", voice])
        return voice, speech

    def build(self, no_music: bool = False) -> Path:
        v = channel()["video"]
        print(f"[{self.id}] preparing narration")
        self.prepare_audio()
        sections = self.plan()
        total = sum(s.seconds for s in sections)
        print(f"[{self.id}] timeline {total / 60:.1f} min, {sum(len(s.shots) for s in sections)} shots")
        for s in sections:
            for sh in s.shots:
                for w in sh.warnings:
                    print(f"  ! {sh.id}: {w}")

        title = self.cfg.get("title_card", {})
        files, idx = [], 0
        for s in sections:
            for sh in s.shots:
                print(f"  render {sh.id:<6} {sh.kind:<5} {sh.seconds:5.1f}s")
                files.append(self.render_shot(idx, sh, title))
                idx += 1
        lst = self.work / "shots_list.txt"
        lst.write_text("".join(f"file '{f}'\n" for f in files))
        silent = self.work / "video_only.mp4"
        run(["ffmpeg", "-f", "concat", "-safe", 0, "-i", lst, "-c", "copy", silent])

        print(f"[{self.id}] mixing audio")
        voice, speech = self.build_voice(sections)
        music = None
        if not no_music:
            music = audio.build_music_bed(self.music_dir, total, self.work / "music_bed.wav")
        mix = audio.master_mix(voice, music, speech, self.work / "master_audio.wav")

        print(f"[{self.id}] encoding master")
        self.out.mkdir(parents=True, exist_ok=True)
        master = self.out / f"{self.id}_1080p.mp4"
        vf = f"fade=t=in:st=0:d=0.5,fade=t=out:st={max(0, total - 1.0):.3f}:d=1.0"
        run(["ffmpeg", "-i", silent, "-i", mix, "-map", "0:v", "-map", "1:a", "-vf", vf,
             "-c:v", "libx264", "-crf", v["crf"], "-preset", v["preset"], "-profile:v", "high",
             "-pix_fmt", "yuv420p", "-r", v["fps"], "-c:a", "aac", "-b:a", "320k",
             "-movflags", "+faststart", "-shortest", master])

        report = {"id": self.id, "total_seconds": total, "fps": v["fps"], "speech": speech,
                  "sections": [{**asdict(s), "shots": [asdict(sh) for sh in s.shots]} for s in sections]}
        (self.out / "timeline.json").write_text(json.dumps(report, indent=2))
        print(f"[{self.id}] done: {master}")
        return master


def load_timeline(ep: Episode) -> dict:
    p = ep.out / "timeline.json"
    if not p.exists():
        raise StudioError(f"No timeline yet for {ep.id}. Run the build first.")
    return json.loads(p.read_text())
