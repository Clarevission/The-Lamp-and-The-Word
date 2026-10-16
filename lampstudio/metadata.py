"""Title, description (with chapters and the Tyndale credit line), tags and pinned comment.

Validates against YouTube's limits so nothing gets rejected or silently ignored in Studio.
"""
from __future__ import annotations

from .core import StudioError, channel, fmt_ts
from .timeline import Episode, load_timeline


def chapters(tl: dict, min_len: float = 10.0) -> list[tuple[float, str]]:
    marks: list[list] = []
    for s in tl["sections"]:
        if s["chapter"]:
            marks.append([s["start"], s["chapter"]])
    if not marks or marks[0][0] > 0.01:
        marks.insert(0, [0.0, "Intro"])
    marks[0][0] = 0.0
    total = tl["total_seconds"]
    cleaned: list[list] = []
    for i, (t, name) in enumerate(marks):           # merge chapters shorter than 10 s
        end = marks[i + 1][0] if i + 1 < len(marks) else total
        if cleaned and end - t < min_len:
            continue
        cleaned.append([t, name])
    return [(t, n) for t, n in cleaned]


def validate(title: str, description: str, tags: list[str], hashtags: list[str],
             chaps: list[tuple[float, str]]) -> list[str]:
    problems = []
    credit = " ".join(channel()["scripture"]["credit_line"].split())
    if credit not in " ".join(description.split()):
        problems.append("Description is missing the full Tyndale NLT credit line.")
    if len(title) > 100:
        problems.append(f"Title is {len(title)} characters (YouTube max 100).")
    for field, text in (("Title", title), ("Description", description)):
        if "<" in text or ">" in text:
            problems.append(f"{field} contains < or > (YouTube rejects these).")
    if len(description.encode("utf-8")) > 5000:
        problems.append(f"Description is {len(description.encode())} bytes (max 5000).")
    tag_chars = sum(len(t) + (2 if " " in t else 0) for t in tags) + max(0, len(tags) - 1)
    if tag_chars > 500:
        problems.append(f"Tags use {tag_chars} characters (max 500).")
    if len(hashtags) > 15:
        problems.append("More than 15 hashtags: YouTube would ignore all of them.")
    if len(chaps) < 3:
        problems.append("Fewer than 3 chapters: YouTube will not show chapters.")
    return problems


def warnings(title: str) -> list[str]:
    w = []
    if len(title) > 70:
        w.append(f"Title is {len(title)} characters; search results cut off around 70.")
    return w


def build(ep: Episode) -> dict:
    yt = ep.cfg.get("youtube", {})
    if not yt.get("title"):
        raise StudioError("episode.yaml needs youtube.title")
    tl = load_timeline(ep)
    chaps = chapters(tl)
    hashtags = yt.get("hashtags", [])
    parts = [yt.get("hook", "").strip()]
    if yt.get("body"):
        parts.append(yt["body"].strip())
    if yt.get("scripture"):
        parts.append("Scripture: " + "; ".join(yt["scripture"]) + f" ({channel()['scripture']['translation']})")
    parts.append("Chapters\n" + "\n".join(f"{fmt_ts(t)} {name}" for t, name in chaps))
    links = yt.get("links", {})
    if links:
        parts.append("\n".join(f"{k}: {v}" for k, v in links.items()))
    parts.append(f"Subscribe for a new Bible story every Sunday and a faith talk every Wednesday: "
                 f"{channel()['channel']['url']}?sub_confirmation=1")
    parts.append(" ".join(channel()["scripture"]["credit_line"].split()))
    if hashtags:
        parts.append(" ".join(hashtags))
    description = "\n\n".join(p for p in parts if p)
    tags = yt.get("tags", [])
    problems = validate(yt["title"], description, tags, hashtags, chaps)
    if problems:
        raise StudioError("Metadata problems:\n  - " + "\n  - ".join(problems))

    out = ep.out / "upload"
    out.mkdir(parents=True, exist_ok=True)
    (out / "title.txt").write_text(yt["title"] + "\n", encoding="utf-8")
    variants = yt.get("title_variants", [])
    if variants:
        (out / "title_variants_for_test_and_compare.txt").write_text(
            "\n".join([yt["title"], *variants][:3]) + "\n", encoding="utf-8")
    (out / "description.txt").write_text(description + "\n", encoding="utf-8")
    (out / "tags.txt").write_text(", ".join(tags) + "\n", encoding="utf-8")
    if yt.get("pinned_comment"):
        (out / "pinned_comment.txt").write_text(yt["pinned_comment"].strip() + "\n", encoding="utf-8")
    for w in warnings(yt["title"]):
        print(f"  ! {w}")
    return {"title": yt["title"], "description": description, "tags": tags, "chapters": chaps}
