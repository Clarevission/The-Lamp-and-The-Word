"""End-to-end test with synthetic inputs (no real recordings needed).

Run: python -m pytest -q tests      (takes a few minutes; it really renders)
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from lampstudio import captions, metadata, qc, shorts, thumbnail
from lampstudio.audio import speech_intervals
from lampstudio.core import duration, has_audio, measure_loudness, probe
from lampstudio.timeline import Episode


def ff(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)], check=True)


def fake_speech(dst: Path, seconds: float):
    """Speech-like bursts: 1.6 s of modulated tone + noise, 0.5 s pauses, quiet room noise."""
    expr = ("if(lt(mod(t,2.1),1.6),0.25*sin(2*PI*180*t)*(0.6+0.4*sin(2*PI*3*t))+0.03*(random(0)-0.5),"
            "0.0008*(random(0)-0.5))")
    ff("-f", "lavfi", "-i", f"aevalsrc='{expr}':s=48000:d={seconds}", "-c:a", "pcm_s24le", dst)


@pytest.fixture(scope="module")
def episode(tmp_path_factory) -> Episode:
    root = tmp_path_factory.mktemp("ep")
    ep_dir = root / "episodes" / "test_ep"
    for d in ("inputs/narration", "inputs/clips", "inputs/stills", "script"):
        (ep_dir / d).mkdir(parents=True)
    music = root / "music"
    music.mkdir()
    fake_speech(ep_dir / "inputs/narration/1_Hook.wav", 14)
    fake_speech(ep_dir / "inputs/narration/2_Verse.wav", 22)
    for i, c in enumerate(("A1", "A2", "B1")):
        ff("-f", "lavfi", "-i", f"testsrc2=s=1920x1080:r=24:d=8", "-f", "lavfi", "-i",
           f"sine=f={300 + i * 100}:d=8", "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
           "-c:a", "aac", ep_dir / f"inputs/clips/{c}.mp4")
    ff("-f", "lavfi", "-i", "mandelbrot=s=1600x1200", "-frames:v", 1, ep_dir / "inputs/stills/B2.png")
    for i in range(4):
        ff("-f", "lavfi", "-i", f"sine=f={220 * (i + 1)}:d=25", "-ac", 2, music / f"s{i}.wav")
    (ep_dir / "verses.json").write_text(json.dumps({"Test 1:1": {"text": "Placeholder line for layout testing only, not scripture."}}))
    (ep_dir / "script/1_Hook.txt").write_text("Have you ever been far from home? Most of us have. Today we look at one moment that changed everything.")
    (ep_dir / "script/2_Verse.txt").write_text("Here is the verse. Read it slowly with me. Notice the words he used, and notice where he was standing when he said them. That is where hope starts.")
    cfg = {
        "id": "test_ep", "format": "faith_talk",
        "inputs": {"music": "../../music"},
        "title_card": {"title": "Test Title", "subtitle": "A test"},
        "sections": [
            {"id": "hook", "chapter": "The question", "narration": "1_Hook.wav", "shots": ["A1", "A2"]},
            {"id": "title", "card": "title", "seconds": 3},
            {"id": "verse", "chapter": "The verse", "narration": "2_Verse.wav",
             "shots": ["B1", {"id": "V", "card": "verse", "ref": "Test 1:1", "at": 7.0}, "B2"]},
            {"id": "end", "chapter": "Keep going", "card": "end_screen", "seconds": 12},
        ],
        "youtube": {"title": "Test Video | A Faith Talk", "hook": "A test.", "scripture": ["Test 1:1"],
                    "tags": ["bible", "faith talk"], "hashtags": ["#Bible"], "pinned_comment": "Hello"},
        "thumbnails": [{"id": "A", "lines": ["COME", "HOME"], "ref": "Test 1:1"},
                       {"id": "B", "lines": ["HE", "RAN"], "frame": "0:05", "side": "right"}],
    }
    (ep_dir / "episode.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    (ep_dir / "shorts.yaml").write_text(yaml.safe_dump({"shorts": [
        {"id": "S1", "title": "Far from home?", "start": "0:01", "end": "0:16", "mode": "fit"},
        {"id": "S2", "title": "The verse", "start": 20, "end": 34, "mode": "crop"}]}))
    return Episode(ep_dir)


def test_status_lists_nothing_missing(episode):
    assert episode.missing_inputs() == []


def test_verse_without_text_is_refused(tmp_path):
    from lampstudio import cards
    from lampstudio.core import StudioError
    (tmp_path / "v.json").write_text(json.dumps({"Luke 15:17": {"text": "PASTE EXACT NLT TEXT HERE"}}))
    with pytest.raises(StudioError):
        cards.load_verse(tmp_path / "v.json", "Luke 15:17")


def test_full_build(episode):
    master = episode.build()
    tl = json.loads((episode.out / "timeline.json").read_text())
    assert abs(duration(master) - tl["total_seconds"]) < 0.15
    v = next(s for s in probe(master)["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1920, 1080)
    loud = measure_loudness(master)
    assert abs(loud["lufs"] + 14) <= 1.0 and loud["true_peak"] <= -1.0
    # pinned verse card starts exactly where asked
    verse_sec = next(s for s in tl["sections"] if s["id"] == "verse")
    vshot = next(sh for sh in verse_sec["shots"] if sh["card"] == "verse")
    assert abs(vshot["start"] - 7.0) < 0.05
    # intermediate shots carry no Flow/source audio
    assert not any(has_audio(p) for p in (episode.work / "shots").glob("*.mp4"))


def test_captions_meta_thumbs_shorts_qc(episode):
    srt = captions.build(episode)
    cues = captions.read_srt(srt)
    assert len(cues) >= 6 and all(b > a for a, b, _ in cues)
    assert all(cues[i][0] >= cues[i - 1][1] - 1e-3 for i in range(1, len(cues)))
    meta = metadata.build(episode)
    assert meta["description"].count("Tyndale House Foundation") == 1
    assert meta["chapters"][0][0] == 0.0 and len(meta["chapters"]) >= 3
    thumbs = thumbnail.build(episode)
    assert len(thumbs) == 2
    made = shorts.build(episode)
    for p in made:
        s = next(x for x in probe(p)["streams"] if x["codec_type"] == "video")
        assert (s["width"], s["height"]) == (1080, 1920)
    rows, passed = qc.check(episode)
    assert passed, rows


def test_speech_intervals_find_pauses(episode):
    clean = next((episode.work / "narration").glob("1_Hook_clean.wav"))
    iv = speech_intervals(clean)
    assert len(iv) >= 4
