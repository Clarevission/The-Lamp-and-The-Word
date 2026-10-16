# The Lamp & The Word: notes for Claude

Faceless Bible-story YouTube channel run by **Dominique** (address her as Dominique; Clarence,
her husband, owns the Claude and GitHub accounts). Read `docs/HANDOFF_from_cowork.md` for the
history and `README.md` for how the toolkit works.

## Rules that don't bend
- Nothing is uploaded, posted or made public without Dominique's explicit OK each time.
  The toolkit only prepares an upload folder; publishing is a manual Studio step.
- Narration is Dominique's own voice. Never generate or suggest AI voice.
- NLT is the translation. Never type verse text from memory, in scripts, cards, descriptions or
  docs. Use placeholders like `[NLT Luke 15:4: Dominique pastes exact text]` and read on-screen
  text only from the episode's `verses.json`.
- Every description carries the Tyndale credit line from `channel.yaml` (enforced by `meta`).
- No fake engagement of any kind.
- Music only from paid-plan Suno tracks; Google Flow audio is always stripped.
- Altered/synthetic content is answered "No" only while visuals stay clearly cartoon.
- Claude can't create accounts or enter passwords or payment details.

## Working on an episode
- `python -m lampstudio status episodes/<ep>` first: it lists exactly what's missing.
- `python -m lampstudio all episodes/<ep>` builds, captions, writes metadata and thumbnails,
  runs QC and packages `out/upload/` with `STUDIO_CHECKLIST.md`.
- Pin a card to narration with `at:` (seconds into the section) in `episode.yaml`.
- Shorts: set times in `shorts.yaml`, then `shorts`.
- Media (WAV/MP4/music) never goes in git; it lives in the shared Google Drive folder.
- Tests: `python -m pytest -q tests` renders a small synthetic episode (a few minutes).

## Style
- Audience is adults (keep the channel clearly "not made for kids").
- Retention rules: hook before the logo, no shot over ~29 s, NLT text on screen for key verses,
  long teaching split into labelled parts.
- Brand: navy #1F3A63 / #142642, gold #F4C24F, cream #FFF9EE; Cinzel (titles),
  Cormorant Garamond (serif), Source Sans 3 (labels).
