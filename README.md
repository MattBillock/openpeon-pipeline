# OpenPeon

Extract movie quotes into categorized sound packs for [peon-ping](https://github.com/MattBillock/peon-ping) — a Claude Code notification system that plays movie quotes as sound effects for different coding events.

## Architecture

```
extraction/          Movie quote extraction pipeline (Whisper STT + ffmpeg)
  extractor.py       Shared extraction engine (full-movie transcription + clip search)
  extract_*.py       Per-movie extraction scripts (user-specific, gitignored)
  <movie>/           Per-movie output: .mp3 clips, transcripts, logs

dashboard/           Streamlit management UI
  app.py             Main dashboard app
  extraction.py      Extraction control (run, retry, monitor via SSH)
  pack_builder.py    Build sound packs from reviewed clips
  icon_generator.py  Generate pack icons (poster/Wikipedia/fallback)
  verifier.py        STT verification and clip review
  quote_generator.py AI-powered quote descriptions
  radarr_client.py   Radarr API integration (movie library)
  media_client.py    Multi-service media client (Radarr/Sonarr/Lidarr)
  health.py          Service health monitoring

scripts/             Utility scripts
```

## How It Works

1. **Extract**: Point an extraction script at a movie file. The engine transcribes the full movie audio with Whisper, searches for your target quotes, extracts matching clips, and verifies them with a second STT pass.

2. **Review**: The dashboard shows all extracted clips with verification scores. Approve, reject, or re-extract clips. Assign each clip to a CESP notification category.

3. **Build**: The pack builder assembles approved clips into a sound pack with an `openpeon.json` manifest, auto-generated icons, and proper directory structure.

4. **Publish**: Push packs to the [openpeon-movie-packs](https://github.com/MattBillock/openpeon-movie-packs) registry. peon-ping pulls packs from this registry.

## Prerequisites

- Python 3.13+
- ffmpeg and ffprobe (via Homebrew: `brew install ffmpeg`)
- Movie files (MKV/MP4) accessible on disk or network mount
- Optional: Radarr for movie library integration

## Installation

```bash
git clone https://github.com/MattBillock/openpeon.git
cd openpeon
python3 -m venv .venv
source .venv/bin/activate
pip install openai-whisper streamlit requests pillow
```

## Quick Start

### 1. Create an extraction script

Copy the template and fill in your movie details:

```bash
cp extraction/extract_example.py.template extraction/extract_mymovie.py
```

Edit the script with your movie path, audio stream, and target quotes. See the template for format details.

### 2. Run extraction

```bash
# Single movie
.venv/bin/python3 extraction/extract_mymovie.py

# All movies
./extraction/run_extractions.sh

# Specific clip
.venv/bin/python3 extraction/extract_mymovie.py clip_name
```

### 3. Review clips in the dashboard

```bash
cd dashboard
streamlit run app.py
```

Review extracted clips, approve/reject, assign categories, then build packs.

## Extraction Script Format

Each extraction script defines a movie's clips as a list of tuples:

```python
CLIPS = [
    # (filename, approx_timestamp_seconds, "expected quote text", duration_seconds),
    ("greeting", 600, "Hello there", 2),
    ("farewell", 3600, "I'll be back", 1.5),
]
```

The extractor searches the full movie transcript for each quote, so timestamps are approximate. See `extraction/extract_example.py.template` for a complete example.

## CESP Categories

Sound packs organize clips into notification categories:

| Category | Triggered When |
|---|---|
| `session.start` | Claude Code session begins |
| `task.acknowledge` | Task accepted / work starting |
| `task.complete` | Task finished successfully |
| `task.error` | Error encountered |
| `input.required` | Waiting for user input |
| `resource.limit` | Rate limit or resource constraint |
| `user.spam` | Rapid repeated actions |

## Dashboard Pages

- **Extraction** — Run extractions, monitor progress, view logs
- **Clip Review** — Listen to clips, verify STT accuracy, approve/reject
- **Pack Builder** — Assemble clips into packs, assign categories, generate manifests
- **Pack Status** — Overview of all published packs and their review status
- **Icons** — Generate and manage pack icons (poster, headshot, or drawn fallback)
- **Media Library** — Browse your Radarr/Sonarr/Lidarr libraries, quick-add movies
- **Health** — Service connectivity and system status

## Configuration

The dashboard reads API keys and paths from environment variables or `.openpeon_settings.json`:

- `RADARR_URL` / `RADARR_API_KEY` — Radarr server for movie library
- `SONARR_URL` / `SONARR_API_KEY` — Sonarr server for TV library
- `LIDARR_URL` / `LIDARR_API_KEY` — Lidarr server for music library

## Pack Manifest Format

Each pack contains an `openpeon.json` manifest:

```json
{
  "name": "my_pack",
  "display_name": "My Pack",
  "version": "1.0.0",
  "description": "Movie quotes for notifications",
  "author": { "name": "Your Name", "github": "yourgithub" },
  "tags": ["movie-quotes"],
  "categories": {
    "session.start": { "sounds": [{ "file": "sounds/greeting.mp3", "sha256": "..." }] },
    "task.complete": { "sounds": [{ "file": "sounds/farewell.mp3", "sha256": "..." }] }
  }
}
```
