#!/usr/bin/env bash
# Show status of all extraction jobs — designed for `watch` inside tmux
set -uo pipefail

EXTRACTION_DIR="${OPENPEON_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}/extraction"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BOLD}Extraction Pipeline${NC}"
echo "─────────────────────────────────────"

# Running extractions
running=$(ps aux | grep 'extract_.*\.py' | grep -v grep | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
running_count=$(ps aux | grep 'extract_.*\.py' | grep -v grep | wc -l | tr -d ' ')

if [ "$running_count" -gt 0 ]; then
    echo -e "${GREEN}Running ($running_count):${NC}"
    ps aux | grep 'extract_.*\.py' | grep -v grep | while read -r line; do
        script=$(echo "$line" | grep -oE 'extract_[a-z]+\.py' | sed 's/extract_//;s/\.py//')
        pid=$(echo "$line" | awk '{print $2}')
        cpu=$(echo "$line" | awk '{print $3}')
        echo -e "  ${GREEN}●${NC} $script ${DIM}(PID $pid, CPU ${cpu}%)${NC}"
    done
else
    echo -e "${DIM}No extractions running${NC}"
fi

echo ""
echo -e "${BOLD}Movie Status${NC}"
echo "─────────────────────────────────────"

# Auto-discover movies from extraction scripts
ALL_MOVIES=()
for script in "$EXTRACTION_DIR"/extract_*.py; do
    [ -f "$script" ] || continue
    name=$(basename "$script" | sed 's/extract_//;s/\.py//')
    ALL_MOVIES+=("$name")
done
# Also include any movie dirs that have output but no script
for dir in "$EXTRACTION_DIR"/*/; do
    [ -d "$dir" ] || continue
    name=$(basename "$dir")
    [[ " ${ALL_MOVIES[*]:-} " == *" $name "* ]] && continue
    [ -f "$dir/extraction_log.json" ] || [ "$(find "$dir" -name '*.mp3' 2>/dev/null | head -1)" ] && ALL_MOVIES+=("$name")
done

for movie in "${ALL_MOVIES[@]}"; do
    dir="$EXTRACTION_DIR/$movie"
    log="$dir/extraction.log"

    if [ ! -d "$dir" ]; then
        echo -e "  ${DIM}○${NC} $movie ${DIM}(no output dir)${NC}"
        continue
    fi

    # Count extracted clips
    clips=$(find "$dir" -name '*.mp3' 2>/dev/null | wc -l | tr -d ' ')

    # Check if currently running
    is_running=$(ps aux | grep "extract_${movie}.py" | grep -v grep | wc -l | tr -d ' ')

    if [ "$is_running" -gt 0 ]; then
        last_line=""
        if [ -f "$log" ]; then
            last_line=$(tail -1 "$log" 2>/dev/null | cut -c1-50)
        fi
        echo -e "  ${GREEN}●${NC} $movie ${DIM}($clips clips)${NC} ${YELLOW}$last_line${NC}"
    elif [ "$clips" -gt 0 ]; then
        echo -e "  ${GREEN}✓${NC} $movie ${DIM}($clips clips)${NC}"
    else
        echo -e "  ${DIM}○${NC} $movie"
    fi
done
