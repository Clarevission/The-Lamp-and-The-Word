"""Collect everything for upload into out/upload/ with a Studio checklist.

Uploading stays a manual step in YouTube Studio on purpose:
  * nothing goes public without Dominique's OK, and
  * videos uploaded through an unaudited YouTube API project are locked to private,
    and pinned comments / end screens cannot be set through the API anyway.
"""
from __future__ import annotations

import datetime as dt
import shutil
from zoneinfo import ZoneInfo

from .core import StudioError, channel
from .timeline import Episode


def build(ep: Episode, passed_qc: bool) -> str:
    if not passed_qc:
        raise StudioError("QC has FAIL items (see out/qc_report.md). Fix those before packaging.")
    up = ep.out / "upload"
    up.mkdir(parents=True, exist_ok=True)
    master = ep.out / f"{ep.id}_1080p.mp4"
    shutil.copy2(master, up / master.name)
    for extra in (ep.out / f"{ep.id}.en.srt", ep.out / "transcript.txt"):
        if extra.exists():
            shutil.copy2(extra, up / extra.name)

    yt = ep.cfg.get("youtube", {})
    fmt = ep.cfg.get("format", "story")
    cad = channel()["cadence"][fmt]
    when = yt.get("publish_at")
    if when:
        tz = ZoneInfo(channel()["channel"]["timezone"])
        when = dt.datetime.fromisoformat(str(when)).replace(tzinfo=tz).strftime("%A %B %d, %Y at %I:%M %p MT")
    else:
        when = f"next {cad['weekday']} at {cad['time']} MT"
    playlist = channel()["channel"]["playlists"].get(yt.get("playlist", ""), yt.get("playlist", ""))
    rules = "\n".join(f"- {r}" for r in channel()["rules"])
    checklist = f"""# Studio checklist: {ep.id}

Everything you need is in this folder.

## Upload (YouTube Studio > Create > Upload video)
1. Video file: `{master.name}`
2. Title: paste `title.txt`
3. Description: paste `description.txt` (chapters and the NLT credit line are already in it)
4. Thumbnail: upload `thumbnail_A.jpg`
5. Playlist: **{playlist or 'choose'}**
6. Audience: **No, it's not made for kids**
7. Show more > Tags: paste `tags.txt`
8. Altered or synthetic content: **No** (cartoon visuals, your own voice)
9. Language: English. Category: Education.
10. Captions: Subtitles > Add > Upload file > `{ep.id}.en.srt` (with timing).
    Or upload `transcript.txt` "Without timing" and let YouTube sync it.
11. End screen: Import from video (Episode 1), or add Subscribe + Playlist, lined up with the gold outlines.
12. Visibility: **Schedule** for {when}. Leave it private until then.

## After it is live
- Pin the comment from `pinned_comment.txt`.
- If there are title/thumbnail variants: Studio > the video > Test & Compare, add thumbnails A/B/C
  (and the titles in `title_variants_for_test_and_compare.txt`).
- Check at 48 hours and 7 days: `python -m lampstudio analytics "Table data.csv"`.

## House rules
{rules}
"""
    (up / "STUDIO_CHECKLIST.md").write_text(checklist, encoding="utf-8")
    return str(up)
