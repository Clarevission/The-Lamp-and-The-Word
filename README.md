# The Lamp & The Word: Studio

Production toolkit for [The Lamp & The Word](https://www.youtube.com/@thelampandtheword).
It turns Dominique's narration and Google Flow clips into a finished, checked, upload-ready
episode with one command, using the same brand and rules every time.

**Dominique records and approves. The toolkit does the rest.** Nothing is ever uploaded or
made public by these tools. Every publish is a manual "Schedule" click in YouTube Studio.

## What it does

| Step | Command | What you get |
|---|---|---|
| See what's missing | `status` | A list like "waiting for 2_The_verse.wav, clips V1-V5" |
| Build the episode | `build` | Cleaned narration, every shot timed to her voice, title/verse/end cards, music ducked under her voice, -14 LUFS master, 1080p MP4 |
| Captions | `captions` | `.srt` timed to her voice + plain transcript |
| Description etc. | `meta` | Title, description with chapters, the NLT credit line, tags, pinned comment (checked against YouTube's limits) |
| Thumbnails | `thumbs` | 2-3 variants for Test & Compare |
| Shorts | `shorts` | 1080x1920 Shorts/Reels/TikToks with brand captions + "full story" end tag, and a caption .txt for each |
| Quality check | `qc` | Loudness, peaks, resolution, shot lengths, credit line, thumbnails, Shorts |
| Upload folder | `package` | Everything for Studio + a step-by-step checklist |
| Everything | `all` | build, then captions, meta, thumbs, qc, package |
| Calendar | `calendar` | `calendar.ics` (publish slots + recording/clip deadlines) and `CALENDAR.md` |
| 48 h / 7 day check | `analytics` | Plain-English verdicts against the channel targets from a Studio CSV export |

Run any of them as:

```bash
python -m lampstudio status episodes/faith_talk_01
python -m lampstudio all episodes/faith_talk_01
```

## Weekly routine (about 2 hours of Dominique's time per episode)

1. **Record**: one session per episode, one WAV per section, named as in `episode.yaml`
   (e.g. `1_Hook.wav`). Drop them in `episodes/<ep>/inputs/narration/`.
2. **Make clips** in Google Flow from the episode's `shot_list.md`. Save each as its shot ID
   (`H1.mp4`, `V3.mp4` ...) in `inputs/clips/`. Stills go in `inputs/stills/`. Flow audio is
   removed automatically.
3. **Run** `python -m lampstudio all episodes/<ep>` and watch `out/<ep>_1080p.mp4`.
   - Want the verse card exactly when she reads it? Add `at: 14.5` (seconds into that
     section) to the verse card in `episode.yaml` and run again. Only changed shots re-render.
4. **Upload**: follow `out/upload/STUDIO_CHECKLIST.md` and choose *Schedule*.
5. **Shorts**: set start/end times in `shorts.yaml`, run `shorts`, then schedule each in
   YouTube Studio (desktop), Instagram (Schedule this Reel) and TikTok Studio (web, up to 10 days ahead).

## Setting up on a computer (once)

1. Install Python 3.10+ and ffmpeg (Mac: `brew install python ffmpeg`).
2. In this folder: `pip install -r requirements.txt`
3. Put the 4 Suno tracks in `music/` as `s0.wav s1.wav s2.wav s3.wav` (any audio format works).
4. Put the real logo (open book + flame, transparent PNG) at `brand/logo.png`.
   Until then a drawn stand-in emblem is used.
5. Optional, more precise captions: `pip install faster-whisper`, then `captions --whisper`.

Test that everything works (renders a short fake episode; takes a few minutes):
`python -m pytest -q tests`

## Folder map

```
channel.yaml            brand, cadence, audio settings, NLT credit line, targets, house rules
plan.yaml               the content plan -> calendar
lampstudio/             the toolkit
episodes/<ep>/
  episode.yaml          sections, shots, YouTube text, thumbnails
  verses.json           exact NLT text Dominique supplies (never typed from memory)
  script.md / script/   narration script (split-script makes the per-section caption files)
  shot_list.md          Google Flow prompts
  shorts.yaml           Shorts to cut
  inputs/               her recordings, Flow clips, stills (not stored in git)
  out/                  master, captions, thumbnails, shorts, upload folder
fonts/                  Cinzel, Cormorant Garamond, Source Sans 3 (SIL Open Font License)
docs/                   handoff, audit and plan
```

## House rules (built into the tools)

- Nothing goes public without Dominique's explicit OK, every time.
- Her own voice only. Never AI voice.
- No fake engagement: no bought views, bots, sub-for-sub or comment pods.
- Music only from a paid Suno plan. Google Flow audio is always stripped.
- NLT text on screen only from `verses.json`, and every description carries the Tyndale credit line
  (the `meta` step refuses to finish without it).

Media files (WAV, MP4, Flow clips, music) stay out of git (see `.gitignore`). Keep them in Google Drive.
