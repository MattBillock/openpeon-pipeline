# Whiplash Sound Packs — Design Document

## Overview

3 CESP v1.0 sound packs from Whiplash (2014), splitting J.K. Simmons' Fletcher into two distinct energy levels and Miles Teller's Neiman as the battered student counterpart.

**Source:** `/Volumes/D-drive-music/Movies/Whiplash (2014)/Whiplash (2014) Remux-2160p.mkv` (MKV, 4K)

## CESP Category Reference

| Category | Event | Comedy mapping |
|---|---|---|
| `session.start` | Session opens | Entrance / greeting / "I'm here" |
| `task.acknowledge` | Agent accepts task | "On it" / agreement / bravado |
| `task.complete` | Task finished | Victory / "done" / satisfaction |
| `task.error` | Something broke | Frustration / confusion / disbelief |
| `input.required` | Needs user permission | "Hey, pay attention" / questions |
| `resource.limit` | Rate limited | Exhaustion / defeat / constraints |
| `user.spam` | Too many rapid prompts | Annoyance / "leave me alone" / anger |

---

## Pack 1: `whiplash_fletcher_classroom` — Fletcher: The Teacher

**Display name:** Fletcher - The Teacher
**Description:** Controlled menace. The calm before the storm.
**Tags:** movie-quotes, whiplash, drama, jk-simmons, fletcher, jazz, music

*The side of Fletcher that lures you in with a smile before the chair flies at your head.*

| Category | Quotes |
|---|---|
| `session.start` | "I'm looking for players who are beyond the best." / "The key is to just relax." / "There are no two words in the English language more harmful than 'good job'." |
| `task.acknowledge` | "Were you rushing or were you dragging?" / "Start counting." / "Now, are you a rusher or are you a dragger?" |
| `task.complete` | "Not bad." / "Good job. ...I'm just kidding." / "There are no two words more harmful than 'good job'." |
| `task.error` | "Not quite my tempo." / "Here's my concern with you." / "That is not your boyfriend's dick. Don't come too early." |
| `input.required` | "Were you rushing or were you dragging?" / "Answer!" / "Do I look like a double-fucking-rainbow to you?" |
| `resource.limit` | "I will stop being your friend." / "For the last time." / "The tempo is not negotiable." |
| `user.spam` | "Why do you suppose I just hurled a chair at your head, Neiman?" / "One more." / "Either you're deliberately playing out of tune, or you don't know you're out of tune." |

**Comedy highlight:** "Not quite my tempo" on task.error — your code is close but not right, and Fletcher is *not* pleased.

---

## Pack 2: `whiplash_fletcher_concert` — Fletcher: The Monster

**Display name:** Fletcher - The Monster
**Description:** Full unhinged rage. Maximum J.K. Simmons volume.
**Tags:** movie-quotes, whiplash, drama, jk-simmons, fletcher, jazz, rage

*When controlled menace wasn't enough. This is Fletcher at 11.*

| Category | Quotes |
|---|---|
| `session.start` | "I am here for a reason." / "Get the fuck out of my sight before I demolish you." / "Faster!" |
| `task.acknowledge` | "Louder! LOUDER!" / "FASTER!" / "Again!" |
| `task.complete` | "That's what I'm looking for." / "Okay." / "THERE it is." |
| `task.error` | "You are a worthless, friendless, faggot-lipped little piece of shit." / "Completely. Utterly. Wrong." / "Are you one of those single-tear people?" / "Oh my dear God." |
| `input.required` | "PLAY!" / "Why are you stopping?!" / "Did I say to stop?!" |
| `resource.limit` | "I will fuck you like a pig." / "You are done." / "Pack up your shit." |
| `user.spam` | "Not my fucking tempo!" / "AGAIN!" / "One, two, three..." (then slap) |

**Comedy highlight:** "AGAIN!" on user.spam — you keep spamming prompts and Fletcher keeps screaming AGAIN.

---

## Pack 3: `whiplash_neiman` — Andrew Neiman

**Display name:** Andrew Neiman
**Description:** The exhausted student who keeps getting back up.
**Tags:** movie-quotes, whiplash, drama, miles-teller, neiman, jazz, drums

*The coding agent as trauma victim.*

| Category | Quotes |
|---|---|
| `session.start` | "I'm Andrew Neiman." / "I'm here." / "I want to be one of the greats." |
| `task.acknowledge` | "Yes, sir." / "I'll be ready." / "I'm gonna work harder." |
| `task.complete` | "I did it." / "Thank you." / "I earned that." |
| `task.error` | "Fuck!" / "I'm sorry." / "I know it's wrong." / "I'm upset." |
| `input.required` | "What do you want from me?" / "What did I do wrong?" / "Is this right?" |
| `resource.limit` | "My hands are bleeding." / "I can't." / "I need a minute." |
| `user.spam` | "I'm trying!" / "I'm practicing!" / "What do you want?!" |

**Comedy highlight:** "My hands are bleeding" for resource.limit — you've hit the API rate limit and Neiman is literally bleeding from drumming too hard.

---

## Implementation Plan

### Audio Extraction

1. Identify English audio track in the MKV:
   ```bash
   ffprobe -v quiet -print_format json -show_streams "/Volumes/D-drive-music/Movies/Whiplash (2014)/Whiplash (2014) Remux-2160p.mkv"
   ```

2. Use Whisper (`small` model, word-level timestamps) to find exact quote positions:
   - Extract 60-second windows around approximate timestamps
   - Transcribe with word-level timestamps
   - Match quotes using fuzzy string matching (SequenceMatcher, min_score=0.4)
   - Extract final clips with 0.3s buffer on each side

3. Output clips to `~/Development/AIOutput/openpeon/extraction/whiplash/`

4. Submit clips for review via clip review web UI (port 8765)

### Approximate Timestamps (for Whisper search windows)

These will need verification against the actual film:

| Quote | Approx. Time | Notes |
|---|---|---|
| "Not quite my tempo" | ~20:00 | First rehearsal scene |
| "Were you rushing or were you dragging?" | ~20:30 | Same scene, Fletcher escalating |
| "Good job... I'm just kidding" | ~15:00 | First meeting in hallway |
| "I'm looking for players who are beyond the best" | ~14:00 | First classroom scene |
| Chair throw / "Why do you suppose..." | ~25:00 | Chair-hurling scene |
| "Not your boyfriend's dick" | ~22:00 | Rehearsal |
| "FASTER!" / "LOUDER!" | ~40:00-60:00 | Various rehearsal scenes |
| "Double-fucking-rainbow" | ~55:00 | Band room |
| "Worthless, friendless..." | ~50:00 | Full verbal abuse |
| "I will fuck you like a pig" | ~50:00 | Same scene |
| "There are no two words..." | ~90:00 | Bar scene with Neiman |
| "I am here for a reason" | ~90:00 | Bar scene |
| "My hands are bleeding" | ~65:00 | Practice montage |

### Pack Assembly

After clip review, run `organize_packs.py` (or equivalent) to:
- Copy approved clips to pack directories
- Generate `openpeon.json` manifests with SHA256 hashes
- Verify all categories have coverage

### Publishing

- Add 3 packs to `MattBillock/openpeon-movie-packs` repo
- Tag new release (v1.1.0 or v2.0.0)
- Submit registry update PR to PeonPing/registry
