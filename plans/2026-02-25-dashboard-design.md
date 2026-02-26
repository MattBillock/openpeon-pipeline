# OpenPeon Pipeline Dashboard Design

**Date:** 2026-02-25
**Stack:** Streamlit + Python
**Location:** `~/Development/AIOutput/openpeon/dashboard/`

## Pages

1. **Pipeline Overview** — summary cards, progress bars, Radarr queue, quick actions
2. **Extraction Monitor** — per-movie extraction status, start/stop/retry actions
3. **Clip Review** — audio playback, approve/reject, category assignment
4. **Radarr Integration** — movie availability, add/search actions
5. **Pack Builder** — build manifests from reviewed clips, publish to registry

## Data Sources

- File system: `~/Development/AIOutput/openpeon/extraction/*/` for clips and results
- Radarr API: `http://htpc.local:7878/api/v3/` for movie status
- Review state: `review.json` per movie in extraction output dirs
- Credentials: `~/.openpeon/.env`
- Published packs: `~/Development/openpeon-movie-packs/`
- Extraction scripts: `~/Development/AIOutput/openpeon/extraction/extract_*.py`

## Files

```
dashboard/
├── app.py              # Main Streamlit app with page routing
├── radarr_client.py    # Radarr API wrapper
├── extraction.py       # Scan dirs, launch/stop scripts, parse results
├── pack_builder.py     # Build openpeon.json from reviewed clips
└── registry.py         # Publish to GitHub/registry via gh CLI
```
