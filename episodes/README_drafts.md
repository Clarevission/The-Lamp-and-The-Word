# Drafts to review: Episode 2 and Faith Talk 02

Claude drafted these for Dominique on Oct 16, 2026. Nothing has been recorded, rendered or posted.

| Folder | Publish | Length |
|---|---|---|
| `ep02_lost_sheep/` The Lost Sheep Explained (Luke 15) | Sun Oct 25, 8:00 AM MT | ~1,500 words + ~180 words of verses, about 12 min |
| `faith_talk_02/` Does God Really Come Looking for Me? | Wed Oct 28, 6:00 PM MT | ~745 words + ~35 words of verse, about 6 min |

Each folder has `script.md`, `episode.yaml`, `verses.json`, `shot_list.md` and `shorts.yaml`.

## 1. Verse text to paste (NLT, from your Bible or the NLT site, never retyped from memory)

Paste each passage in two places: in `script.md` (replacing the whole `[NLT ...]` placeholder,
**without** the square brackets, or the captions will drop it) and in that folder's `verses.json`.

- **Episode 2:** Luke 15:1-2, Luke 15:4, Luke 15:5-6 (read aloud only, no card), Luke 15:7,
  Ezekiel 34:11, Luke 19:10
- **Faith Talk 02:** Luke 15:4 (same wording as in Episode 2)

## 2. Theology checks (does this say what you want it to say?)

- **"Ninety-nine righteous people who don't need to repent" (Ep 2, part two).** The script reads it
  as gentle irony aimed at the Pharisees, which is a common reading but not the only one.
- **Sheep vs. son (Ep 2, section 5; FT02 point one).** The script says the sheep and the coin do
  nothing to be found, while the son turns around, so together they show God seeking first and
  us responding. Check that this balance fits how you teach repentance.
- **The shepherd = God (Ezekiel 34), and Jesus = the good shepherd (John 10:11).** The script says
  Jesus was "doing exactly what God said he himself would do". That quietly points to Jesus'
  divinity. Make sure you're comfortable saying it that way.
- **The older brother stands where the Pharisees stood.** This is the standard reading. Check that
  it matches what you said in Episode 1.
- **"The shoulders that carry the lost sheep home are the same shoulders that carried a cross."**
  This is a picture, not a claim about the text. John 19:17 has Jesus carrying his cross, and the
  other Gospels add that Simon of Cyrene carried it too. Soften the line if you'd like.
- **The prayers (both scripts).** They are short invitations, not a formula. Check the wording fits
  your church tradition.
- **Pharisees on screen.** The script calls them "serious, devout men" and the prompts ask for
  dignified men, not villains. When you review the Flow clips, reject any that slip into ethnic
  caricature or make Jesus look comic.

## 3. Claims to check

- Tax collectors "collected taxes for Rome" (Ep 2, the scene). This is simplified: in Galilee they
  worked under Herod Antipas, Rome's client ruler. If you want it exact, say "for Rome and its
  client kings".
- Sharing a meal meant acceptance and friendship in that culture. This is widely taught and safe.
- The Ezekiel 34 summary ("didn't care for the weak... didn't go looking for the lost") paraphrases
  Ezekiel 34:2-6. Check it against the text.
- "The Lord is my shepherd," David wrote: Psalm 23:1, which the heading attributes to David.
- Luke 19:10 was said at Zacchaeus' house (Luke 19:1-10). The script now says "as a guest in the
  home of", not "after a meal".
- FT02 paraphrases Romans 5:8 ("while we were still sinners") and uses the short phrase "seek and
  save the lost" (Luke 19:10). Both are only a few words, but check that you're happy with them.
- "Eight billion people" (FT02) is the current world population, rounded.
- The counting at the sheep pen (Ep 2 hook) is an imagined scene to open the story, not a detail
  from Luke. The script doesn't present it as one.

## 4. Before the build

- Record each `##` section as its own WAV, using the names in `episode.yaml`. Then run
  `python -m lampstudio split-script episodes/<folder>`.
- After the first rough render, set `at:` on each verse card (and uncomment the part labels) so
  they land where you start reading.
- The Episode 2 link in Faith Talk 02's description is commented out in `episode.yaml`. Add it once
  Episode 2 is live on Oct 25.
- Shot plans: Episode 2 has 73 shots (62 clips + 11 stills). Faith Talk 02 has 33, and 11 of them
  can be copied from Episode 2.
- Times in `shorts.yaml` are guesses marked "set me". Set them from the finished master.
