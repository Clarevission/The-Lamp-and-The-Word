"""Pre-upload quality check. Writes out/qc_report.md; anything marked FAIL blocks packaging."""
from __future__ import annotations

from PIL import Image

from .core import channel, duration, measure_loudness, probe
from .timeline import Episode, load_timeline


def check(ep: Episode) -> tuple[list[tuple[str, str]], bool]:
    rows: list[tuple[str, str]] = []
    ok = lambda m: rows.append(("PASS", m))
    warn = lambda m: rows.append(("WARN", m))
    fail = lambda m: rows.append(("FAIL", m))
    v, a = channel()["video"], channel()["audio"]

    master = ep.out / f"{ep.id}_1080p.mp4"
    if not master.exists():
        fail("Master video not rendered yet.")
        return rows, False
    info = probe(master)
    vs = next(s for s in info["streams"] if s["codec_type"] == "video")
    aus = [s for s in info["streams"] if s["codec_type"] == "audio"]
    (ok if (vs["width"], vs["height"]) == (v["width"], v["height"]) else fail)(
        f"Resolution {vs['width']}x{vs['height']}")
    (ok if vs["codec_name"] == "h264" else fail)(f"Video codec {vs['codec_name']}")
    if aus:
        (ok if aus[0]["codec_name"] == "aac" and int(aus[0]["channels"]) == 2 else warn)(
            f"Audio {aus[0]['codec_name']} {aus[0]['channels']}ch {aus[0]['sample_rate']} Hz")
    else:
        fail("Master has no audio")

    loud = measure_loudness(master)
    (ok if abs(loud["lufs"] - a["target_lufs"]) <= 1.0 else fail)(
        f"Loudness {loud['lufs']:.1f} LUFS (target {a['target_lufs']})")
    (ok if loud["true_peak"] <= a["true_peak"] + 0.5 else fail)(
        f"True peak {loud['true_peak']:.1f} dBTP (max {a['true_peak']})")

    mins = duration(master) / 60
    fmt = ep.cfg.get("format", "story")
    lo, hi = channel()["cadence"].get(fmt, {}).get("minutes", [0, 999])
    (ok if lo - 0.5 <= mins <= hi + 0.5 else warn)(f"Length {mins:.1f} min (plan {lo}-{hi} min for {fmt})")

    tl = load_timeline(ep)
    issues = [(sh["id"], w) for s in tl["sections"] for sh in s["shots"] for w in sh["warnings"]]
    if issues:
        for sid, w in issues:
            warn(f"Shot {sid}: {w}")
    else:
        ok(f"All shots under {v['max_shot_seconds']} s, no frozen frames")
    first = tl["sections"][0]
    (ok if not first["shots"][0]["card"] else warn)("Opens on a story shot (hook first, logo after)")

    up = ep.out / "upload"
    desc = up / "description.txt"
    if desc.exists():
        credit = " ".join(channel()["scripture"]["credit_line"].split())
        (ok if credit in " ".join(desc.read_text().split()) else fail)("Tyndale NLT credit line in description")
    else:
        fail("Description not generated (run meta)")
    srt = ep.out / f"{ep.id}.en.srt"
    (ok if srt.exists() else warn)("Captions file (.srt)" if srt.exists() else "No captions file yet")
    thumbs = sorted(up.glob("thumbnail_*.jpg"))
    if not thumbs:
        warn("No thumbnails yet")
    for t in thumbs:
        im = Image.open(t)
        good = im.size == (1280, 720) and t.stat().st_size < 2 * 1024 * 1024
        (ok if good else fail)(f"{t.name} {im.size[0]}x{im.size[1]}, {t.stat().st_size // 1024} KB")
    for s in sorted((ep.out / "shorts").glob("*.mp4")):
        st = next(x for x in probe(s)["streams"] if x["codec_type"] == "video")
        d = duration(s)
        good = (st["width"], st["height"]) == (1080, 1920) and d <= channel()["shorts"]["max_seconds"] + 0.5
        (ok if good else fail)(f"Short {s.stem}: {st['width']}x{st['height']}, {d:.0f}s")

    passed = not any(r[0] == "FAIL" for r in rows)
    lines = [f"# QC report: {ep.id}", "", f"**Result: {'READY' if passed else 'NOT READY'}**", ""]
    lines += [f"- {status}: {msg}" for status, msg in rows]
    (ep.out / "qc_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows, passed
