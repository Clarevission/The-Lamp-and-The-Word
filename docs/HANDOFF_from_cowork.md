# The Lamp & The Word — Project Handoff

Everything needed to continue this YouTube channel project in Claude Code. Read this file first.

## 1. Who and what

- **Owner:** Dominique (working on her husband Clarence's Claude account). Address her as Dominique.
- **Channel:** The Lamp & The Word — https://www.youtube.com/@thelampandtheword (Studio channel ID `UCk4cg9rs4mmNeHFYI2oC6aw`).
- **Concept:** faceless Bible-story channel. Stories told from the text and explained as faith talks / evangelism, inspired by BibleProject. A second income stream, so monetization rules matter.
- **Narration:** Dominique's own voice (Shure MV6 mic, WAV 48 kHz). Never replace her voice with AI voice.
- **Bible translation:** NLT (New Living Translation). Only put NLT verse text on screen when Dominique has supplied the exact passage (see `ep01/verses.json`). Every description must carry the Tyndale credit line:
  > Scripture quotations are taken from the Holy Bible, New Living Translation, copyright © 1996, 2004, 2015 by Tyndale House Foundation. Used by permission of Tyndale House Publishers, Carol Stream, Illinois 60188. All rights reserved.
- **Brand:** navy `#1F3A63` (dark bg `#142642`), gold `#F4C24F`, cream `#FFF9EE`. Fonts: Cormorant Garamond (serif), Cinzel Black (bold titles), Source Sans 3 (labels), all in `fonts/`. Logo: open book with a flame (lamp).

## 2. Rules that don't bend

- No fake engagement: no bought views, bots, sub-for-sub, comment pods.
- Nothing goes public or gets posted without Dominique's explicit OK each time.
- Claude can't create accounts or type passwords or payment details; she does those.
- Music must come from a paid Suno plan (Pro/Premier) for a monetized channel. Remove the sound from Google Flow clips; our own music and her voice only.
- YouTube "altered or synthetic content": answered **No**. The visuals are clearly cartoon and the voice is hers.

## 3. Cadence and calendar

- Sunday 8:00 AM Mountain: full story episode (10–12 min). Wednesday 6:00 PM Mountain: faith talk (5–6 min). Plus 2–3 Shorts a week (YouTube Shorts, Instagram Reels, TikTok).
- Month 1 plan: Prodigal Son + "Coming to your senses"; Lost Sheep + "Does God really come looking for me?"; Good Samaritan + "Who is my neighbour?"; Two Builders + "Building on what lasts".

## 4. Status (as of Oct 16, 2026)

**Episode 1, "The Prodigal Son Explained | Animated Bible Story (Luke 15)"**
- Live: scheduled Oct 14, 2026, 8:00 AM MT. URL https://youtu.be/jwXsV3k3Vmw
- 1080p, 12:02, -14 LUFS. Built with the Python pipeline in `ep01/` (cartoon scenes + 3D cards + her narration + Suno music bed).
- Metadata set: description and chapters (`ep01/meta/description.txt`), 20 tags, Education category, English, not made for kids, playlist "Stories Jesus Told | Parables Explained" (oldest first), end screen (Subscribe + playlist).
- Thumbnail chosen: **C2** (`thumbs/Lost_Found_Luke15_thumbnail.jpg`, LOST / FOUND, Cinzel, "Luke 15:24"). Dominique uploads it herself.
- To do: check that the thumbnail is uploaded, pin the comment ("Which son do you relate to more right now? If you'd like prayer, tell me below and I'll pray for you."), and review the auto-captions.

**Episode 1 Shorts:** 5 vertical cuts made with `ep01/shorts.py` (S1 He Ran, S2 Came to his senses, S3 Too far gone, S4 Not tolerance, S5 Other son). Captions, hashtags and schedule (Oct 15–23, 6 PM MT) are in `shorts/Shorts_captions_and_schedule.txt`. Not posted yet. Auto-posting needs Postiz (or each platform's own scheduler), with accounts that Dominique connects.

**Faith Talk 01, "Coming to Your Senses" (Luke 15:17)** — next to build
- Script: `faith_talk_01/script.md`. Visual plan and shot list: `faith_talk_01/shot_list.md`.
- New visual style: Pixar-like 3D cartoon, made by Dominique in **Google Flow** (Veo). Her clips: H1, H2, V1, V2, V3, V4, V5, V7, T1, T2, T4, T5, T6, T7, T8, P1, P3, P5 (1080p, 8–10 s, 24 fps, with Flow audio that must be removed). Stills for T3 (hands), P2 (church pew) and P4 (prayer), plus spares X1 (feast) and X2 (glowing Bible), are animated with `faith_talk_01/parallax.py` (rembg cut-out + inpainted background, 2.5D camera move).
- Claude makes: V6 verse card (Luke 15:17–18 NLT, text in `verses.json`), H3 title card, P6 end screen.
- **Blocked on:** Dominique's 4 narration recordings — `1_Hook.wav`, `2_The_verse.wav`, `3_Three_things.wav`, `4_For_you_and_prayer.wav`.
- Once they arrive: clean the audio (chain below), time the shots to her words, music bed under the voice (about 0.15 gain, louder on intro/end), loudnorm -14 LUFS / -1.5 dBTP, 1080p H.264. Then a thumbnail and 2–3 Shorts.

## 5. Pipeline notes

- **Audio clean chain** (ffmpeg): `highpass=f=75,afftdn=nr=8:nf=-60,deesser=i=0.3,acompressor=threshold=-24dB:ratio=2.5:attack=8:release=120:makeup=2`, then trim silences.
- **Final mix:** voice + music via `amix` (normalize=0), `alimiter`, stereo, `loudnorm=I=-14:TP=-1.5:LRA=11`.
- **Music bed:** the 4 Suno songs in `music/` (s0–s3), each normalized to -23 LUFS and crossfaded 5 s (order s0, s1, s2, s3, s0, s1).
- **Retention rules** used for Ep 1: hook first, then the logo; no shot longer than about 29 s; NLT verse text on screen; split long teaching into labelled parts.
- **Episode 1 render order:** `render_stills.py`, `layers.py`, `timeline.py`, `assemble.py clips-only`, `stitch.py`. Cartoon scenes are in `cartoon.py`; the scene list is in `scenes.py`. The episode-specific audio and large renders are not in this bundle.
- **Python deps:** pillow, numpy, cairosvg, cairocffi, opencv-python-headless, rembg, onnxruntime, fonttools. Also ffmpeg with libx264.

## 6. Where things live outside this folder

- Full Episode 1 master: on YouTube, plus Dominique's Downloads (`Prodigal_Son_Ep01_1080p.mp4`).
- Her narration WAVs and Flow clips: on her computer and Google Drive.
- Claude docs (claude.ai): Episode 1 script, Ep 1 launch plan (SEO, retention, tracking targets), Faith Talk 01 script, Faith Talk 01 cartoon visual plan. Their key content is copied into this bundle.

## 7. Tracking targets (check at 48 h and 7 days)

- Click-through rate 4–10%. Below 3% means test thumbnail B or A.
- Average percentage viewed 40%+.
- Under 30% of viewers gone by 0:30.
- Every comment answered within 24 h.
