"""Command line: python -m lampstudio <command> [episode folder]

  status   EP        what's ready and what's still missing
  build    EP        clean narration, time shots, render, mix, encode the master
  captions EP        captions .srt + transcript (add --whisper for Whisper timing)
  meta     EP        title, description with chapters + NLT credit, tags, pinned comment
  thumbs   EP        thumbnail variants
  shorts   EP        vertical Shorts from shorts.yaml (add --only S1 for one)
  qc       EP        quality check -> out/qc_report.md
  package  EP        upload folder + Studio checklist (only if QC passes)
  all      EP        build -> captions -> meta -> thumbs -> qc -> package
  cards    EP        render just the brand cards that don't need recordings (title, end screen)
  split-script EP MD split a script.md into per-section caption files (by ## headings, in order)
  calendar           calendar.ics + CALENDAR.md from plan.yaml
  analytics CSV      48 h / 7 day check from a YouTube Studio CSV export
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import analytics, captions, metadata, package, qc, schedule, shorts, thumbnail
from .core import StudioError
from .timeline import Episode


def _status(ep: Episode) -> None:
    need = ep.missing_inputs()
    print(f"{ep.id}: {'READY to build' if not need else 'waiting for:'}")
    for n in need:
        print(f"  - {n}")


def _split_script(ep: Episode, md: Path) -> None:
    """Each '## heading' block of the script goes to the next narrated section's .txt file."""
    import re
    if not md.exists():
        raise StudioError(f"Script not found: {md}")
    blocks = [b.strip() for b in re.split(r"^##\s+.*$", md.read_text(encoding="utf-8"), flags=re.M)[1:]]
    narrated = [s for s in ep.cfg["sections"] if s.get("narration")]
    if len(blocks) != len(narrated):
        raise StudioError(f"{md.name} has {len(blocks)} '##' sections but the episode has "
                          f"{len(narrated)} narrated sections. Make them match.")
    ep.scripts_dir.mkdir(parents=True, exist_ok=True)
    for sec, text in zip(narrated, blocks):
        dst = ep.scripts_dir / (sec.get("script") or Path(sec["narration"]).stem + ".txt")
        dst.write_text(text + "\n", encoding="utf-8")
        print(f"  {dst.name}: {len(text.split())} words")


def _cards(ep: Episode) -> None:
    from . import cards
    title = ep.cfg.get("title_card", {})
    out = ep.out / "cards"
    for sec in ep.cfg["sections"]:
        kind = sec.get("card")
        if kind == "title":
            p = cards.title_card(out / f"{sec['id']}_title.mp4", float(sec.get("seconds", 4.5)),
                                 title.get("title", ""), title.get("subtitle", ""))
        elif kind == "end_screen":
            p = cards.end_screen(out / f"{sec['id']}_end_screen.mp4", float(sec.get("seconds", 20)),
                                 sec.get("line", "Keep walking in the light"))
        else:
            continue
        print(f"  {p}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="lampstudio", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command")
    ap.add_argument("target", nargs="?")
    ap.add_argument("extra", nargs="?")
    ap.add_argument("--whisper", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--dropoff", action="append", default=[], help="VIDEO=PCT gone by 0:30")
    a = ap.parse_args(argv)
    try:
        if a.command == "calendar":
            ics, md = schedule.build()
            print(f"wrote {ics} and {md}")
            return 0
        if a.command == "analytics":
            drop = {k: float(v) for k, v in (d.split("=", 1) for d in a.dropoff)}
            print(analytics.report(Path(a.target), drop))
            return 0
        if not a.target:
            ap.error("this command needs an episode folder, e.g. episodes/faith_talk_01")
        ep = Episode(Path(a.target))
        cmd = a.command
        if cmd == "status":
            _status(ep)
        elif cmd == "split-script":
            _split_script(ep, Path(a.extra) if a.extra else ep.dir / "script.md")
        elif cmd == "cards":
            _cards(ep)
        elif cmd == "build":
            ep.build(no_music=a.no_music)
        elif cmd == "captions":
            print(captions.build(ep, a.whisper))
        elif cmd == "meta":
            metadata.build(ep)
            print(f"wrote {ep.out / 'upload'}")
        elif cmd == "thumbs":
            thumbnail.build(ep)
        elif cmd == "shorts":
            for p in shorts.build(ep, a.only):
                print(f"  {p}")
        elif cmd in ("qc", "package", "all"):
            if cmd == "all":
                need = ep.missing_inputs()
                if need:
                    _status(ep)
                    return 1
                ep.build(no_music=a.no_music)
                try:
                    captions.build(ep, a.whisper)
                except StudioError as e:
                    print(f"  ! captions skipped: {e}")
                metadata.build(ep)
                if ep.cfg.get("thumbnails"):
                    thumbnail.build(ep)
            rows, passed = qc.check(ep)
            for status, msg in rows:
                print(f"  {status:4}  {msg}")
            print(f"QC: {'READY' if passed else 'NOT READY'}  ({ep.out / 'qc_report.md'})")
            if cmd in ("package", "all"):
                print(f"upload folder: {package.build(ep, passed)}")
        else:
            ap.error(f"unknown command {cmd}")
    except StudioError as e:
        print(f"\nStopped: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
