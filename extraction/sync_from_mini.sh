#!/bin/bash
# Sync extraction results from tiny-but-mighty back to local machine.
# Copies extraction_log.json and .mp3 files for each movie.
#
# Usage:
#   ./sync_from_mini.sh              # Sync all movies
#   ./sync_from_mini.sh spaceballs   # Sync specific movie
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_DIR="$HOME/dev/openpeon/extraction"
REMOTE="mini:~/dev/openpeon/extraction"

# Auto-discover movies from extraction scripts
ALL_MOVIES=()
for script in "$SCRIPT_DIR"/extract_*.py; do
    [ -f "$script" ] || continue
    name=$(basename "$script" | sed 's/extract_//;s/\.py//')
    ALL_MOVIES+=("$name")
done

if [ $# -gt 0 ]; then
  MOVIES=("$@")
else
  MOVIES=("${ALL_MOVIES[@]}")
fi

echo "Syncing extraction results from tiny-but-mighty..."

for movie in "${MOVIES[@]}"; do
  remote_dir="$REMOTE/$movie"
  local_dir="$LOCAL_DIR/$movie"
  mkdir -p "$local_dir"

  # Sync extraction_log.json and mp3 files
  echo "  $movie..."
  rsync -avz --include='extraction_log.json' --include='*.mp3' --include='review.json' --exclude='*' \
    "$remote_dir/" "$local_dir/" 2>/dev/null

  # Check results
  if [ -f "$local_dir/extraction_log.json" ]; then
    verified=$(python3 -c "import json; d=json.load(open('$local_dir/extraction_log.json')); print(sum(1 for v in d.values() if v.get('final_status')=='verified'))" 2>/dev/null)
    total=$(python3 -c "import json; d=json.load(open('$local_dir/extraction_log.json')); print(len(d))" 2>/dev/null)
    echo "    -> $verified/$total verified"
  fi
done

echo "Sync complete."
