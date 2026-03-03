#!/usr/bin/env bash
# Status line for tmux — shown in bottom-right of peon-swarm session
set -uo pipefail

PACKS_DIR="${OPENPEON_PACKS:-$(cd "$(dirname "$0")/../.." && pwd)/../openpeon-movie-packs}"

# Streamlit status
if pgrep -f 'streamlit run' >/dev/null 2>&1; then
    dash="Dashboard:ON"
else
    dash="Dashboard:OFF"
fi

# Running extractions count
extract_count=$(ps aux | grep 'extract_.*\.py' | grep -v grep | wc -l | tr -d ' ')

# Published pack count
pack_count=$(ls -1d "$PACKS_DIR"/*/ 2>/dev/null | wc -l | tr -d ' ')

echo "$dash │ ${extract_count} extracting │ ${pack_count} packs"
