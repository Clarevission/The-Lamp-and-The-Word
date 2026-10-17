"""Content calendar: publish slots plus the production steps before each one, as .ics and Markdown.

Reads plan.yaml at the project root. Import calendar.ics into Google Calendar or Apple Calendar.
"""
from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo

from .core import ROOT, channel, load_yaml

# days before publish -> step
STEPS = {
    "story": [(6, "Record narration (all sections, one session)"), (5, "Make Google Flow clips + stills"),
              (3, "Build + review rough render"), (2, "Fix notes, final render, thumbnails"),
              (1, "Upload + schedule in Studio (private -> scheduled)")],
    "faith_talk": [(5, "Record narration"), (4, "Make Google Flow clips + stills"),
                   (2, "Build + review render"), (1, "Upload + schedule in Studio")],
    "short": [(1, "Schedule Short on YouTube, Instagram, TikTok")],
}


def _ics_event(start: dt.datetime, minutes: int, title: str, desc: str = "") -> str:
    utc = start.astimezone(dt.timezone.utc)
    end = utc + dt.timedelta(minutes=minutes)
    f = "%Y%m%dT%H%M%SZ"
    desc = desc.replace("\n", "\\n").replace(",", "\\,")
    return (f"BEGIN:VEVENT\nUID:{uuid.uuid5(uuid.NAMESPACE_URL, title + utc.isoformat())}\n"
            f"DTSTAMP:{dt.datetime.now(dt.timezone.utc).strftime(f)}\nDTSTART:{utc.strftime(f)}\n"
            f"DTEND:{end.strftime(f)}\nSUMMARY:{title.replace(',', chr(92) + ',')}\nDESCRIPTION:{desc}\nEND:VEVENT\n")


def build(plan_path: Path | None = None) -> tuple[Path, Path]:
    plan = load_yaml(plan_path or ROOT / "plan.yaml")
    tz = ZoneInfo(channel()["channel"]["timezone"])
    events, md = [], ["# Content calendar", "", "All times Mountain Time.", "",
                      "| Date | Time | Type | Series | Title | Status |", "|---|---|---|---|---|---|"]
    for item in sorted(plan["items"], key=lambda x: (str(x["date"]), x.get("time", ""))):
        kind = item["type"]
        date = dt.date.fromisoformat(str(item["date"]))
        default = channel()["cadence"].get(kind, channel()["cadence"]["shorts"])["time"]
        hh, mm = map(int, item.get("time", default).split(":"))
        when = dt.datetime.combine(date, dt.time(hh, mm), tz)
        label = {"story": "Story", "faith_talk": "Faith Talk", "short": "Short"}[kind]
        series = plan.get("series", {}).get(item.get("series", ""), "")
        md.append(f"| {date:%a %b %d} | {when.strftime('%I:%M %p').lstrip('0')} | {label} | {series} | "
                  f"{item['title']} | {item.get('status', 'planned')} |")
        events.append(_ics_event(when, 30, f"PUBLISH {label}: {item['title']}",
                                 (f"Series: {series}. " if series else "") + "Goes live only with Dominique's OK."))
        if item.get("status") in ("published", "scheduled", "finished"):
            continue
        for days, step in STEPS[kind]:
            day = when - dt.timedelta(days=days)
            if day.date() < dt.date.today():
                continue
            start = dt.datetime.combine(day.date(), dt.time(19, 0), tz)
            events.append(_ics_event(start, 60, f"{step} - {item['title']}"))
    ics = ROOT / "calendar.ics"
    ics.write_text("BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Lamp and the Word//Studio//EN\n"
                   + "".join(events) + "END:VCALENDAR\n", encoding="utf-8")
    mdp = ROOT / "CALENDAR.md"
    mdp.write_text("\n".join(md) + "\n", encoding="utf-8")
    return ics, mdp
