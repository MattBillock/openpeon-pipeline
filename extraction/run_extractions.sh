#!/bin/bash
# Run extraction scripts sequentially using the Whisper Python environment.
# This loads the model ONCE per movie (in-process) instead of per-transcription.
#
# Usage:
#   ./run_extractions.sh                    # Run all movies sequentially
#   ./run_extractions.sh spaceballs diehard  # Run specific movies
#   MAX_PARALLEL=2 ./run_extractions.sh     # Run 2 at a time
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_PYTHON="$PROJECT_ROOT/.venv/bin/python3"
MAX_PARALLEL="${MAX_PARALLEL:-1}"  # Keep at 1 to avoid SMB I/O contention on network-mounted MKVs

# Ensure homebrew binaries (ffmpeg, ffprobe) are in PATH
export PATH="/opt/homebrew/bin:$PATH"

# Auto-discover movies from extraction scripts
ALL_MOVIES=()
for script in "$SCRIPT_DIR"/extract_*.py; do
    [ -f "$script" ] || continue
    name=$(basename "$script" | sed 's/extract_//;s/\.py//')
    ALL_MOVIES+=("$name")
done

# Filter to requested movies if specified
if [ $# -gt 0 ]; then
  MOVIES=("$@")
else
  MOVIES=("${ALL_MOVIES[@]}")
fi

echo "============================================"
echo "  OpenPeon Extraction Runner"
echo "  Movies: ${#MOVIES[@]}"
echo "  Parallel: $MAX_PARALLEL"
echo "  Python: $PROJECT_PYTHON"
echo "============================================"

running=0
pids=()
names=()

for movie in "${MOVIES[@]}"; do
  script="$SCRIPT_DIR/extract_${movie}.py"
  if [ ! -f "$script" ]; then
    echo "SKIP: $script not found"
    continue
  fi

  logfile="$SCRIPT_DIR/${movie}/extraction.log"
  mkdir -p "$SCRIPT_DIR/${movie}"

  echo "[$(date +%H:%M:%S)] START: $movie"
  "$PROJECT_PYTHON" -u "$script" > "$logfile" 2>&1 &
  pids+=($!)
  names+=("$movie")
  running=$((running + 1))

  # Wait if at max parallel
  if [ "$running" -ge "$MAX_PARALLEL" ]; then
    wait "${pids[0]}"
    exit_code=$?
    echo "[$(date +%H:%M:%S)] DONE: ${names[0]} (exit=$exit_code)"
    pids=("${pids[@]:1}")
    names=("${names[@]:1}")
    running=$((running - 1))
  fi
done

# Wait for remaining
for i in "${!pids[@]}"; do
  wait "${pids[$i]}"
  exit_code=$?
  echo "[$(date +%H:%M:%S)] DONE: ${names[$i]} (exit=$exit_code)"
done

echo "============================================"
echo "  All extractions complete."
echo "============================================"
