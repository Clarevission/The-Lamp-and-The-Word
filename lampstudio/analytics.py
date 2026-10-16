"""48-hour and 7-day check against the channel's targets.

No API setup needed: in YouTube Studio > Analytics > Advanced mode, pick the videos and the date
range, click the download arrow > Comma-separated values, and pass the "Table data.csv" file here.
Retention at 0:30 is not in that export, so it can be added by hand with --dropoff VIDEO=PCT.
"""
from __future__ import annotations

import csv
from pathlib import Path

from .core import StudioError, channel


def _col(header: list[str], *needles: str) -> str | None:
    for h in header:
        low = h.lower()
        if all(n in low for n in needles):
            return h
    return None


def _num(v: str) -> float | None:
    try:
        return float(str(v).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None


def report(csv_path: Path, dropoff: dict[str, float] | None = None) -> str:
    t = channel()["targets"]
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise StudioError("The CSV has no rows.")
    hdr = list(rows[0].keys())
    c_title = _col(hdr, "title") or _col(hdr, "content")
    c_ctr = _col(hdr, "click-through")
    c_avp = _col(hdr, "average percentage viewed")
    c_views, c_impr = _col(hdr, "views"), _col(hdr, "impressions")
    out = ["# Channel check", "", f"Source: {Path(csv_path).name}", ""]
    for r in rows:
        title = (r.get(c_title) or "").strip()
        if not title or title.lower() == "total":
            continue
        out.append(f"## {title}")
        ctr = _num(r.get(c_ctr, "")) if c_ctr else None
        avp = _num(r.get(c_avp, "")) if c_avp else None
        views = r.get(c_views, "?") if c_views else "?"
        impr = r.get(c_impr, "?") if c_impr else "?"
        out.append(f"- Views {views}, impressions {impr}")
        if ctr is not None:
            if ctr < t["ctr_retest_below"]:
                out.append(f"- CTR {ctr:.1f}%: below {t['ctr_retest_below']}%. Start Test & Compare with the other thumbnails/titles.")
            elif ctr < t["ctr_min"]:
                out.append(f"- CTR {ctr:.1f}%: under the {t['ctr_min']}% target. Watch for 2 more days; test if it stays low.")
            else:
                out.append(f"- CTR {ctr:.1f}%: on target ({t['ctr_min']}-{t['ctr_good']}%).")
        if avp is not None:
            if avp >= t["avg_pct_viewed_min"]:
                out.append(f"- Average viewed {avp:.0f}%: on target.")
            else:
                out.append(f"- Average viewed {avp:.0f}%: under {t['avg_pct_viewed_min']:.0f}%. Open the retention graph and "
                           f"note where the biggest drop is; tighten that part next time.")
        if dropoff:
            for k, pct in dropoff.items():
                if k.lower() in title.lower():
                    good = pct <= t["max_dropoff_at_30s"]
                    out.append(f"- Gone by 0:30: {pct:.0f}% ({'on target' if good else 'hook needs to land faster'}).")
        out.append("")
    out.append(f"Reminder: answer every comment within {t['reply_within_hours']} hours. No bought views, bots or comment pods.")
    return "\n".join(out) + "\n"
