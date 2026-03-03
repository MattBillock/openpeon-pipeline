#!/usr/bin/env bash
# Actions for the peon-swarm tmux menu popups
set -euo pipefail

PROJECT_ROOT="${OPENPEON_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

case "${1:-help}" in
    restart-streamlit)
        echo -e "${YELLOW}Restarting Streamlit...${NC}"
        pkill -f 'streamlit run' 2>/dev/null || true
        sleep 1
        cd "$PROJECT_ROOT/dashboard"
        export PATH="/opt/homebrew/bin:$PATH"
        nohup "$PROJECT_ROOT/.venv/bin/streamlit" run app.py \
            --server.address 0.0.0.0 \
            --server.port 8501 \
            --server.fileWatcherType none \
            --server.runOnSave false \
            --server.headless true \
            --theme.base dark \
            > /tmp/streamlit.log 2>&1 &
        sleep 2
        if pgrep -f 'streamlit run' >/dev/null; then
            echo -e "${GREEN}Streamlit restarted on :8501${NC}"
        else
            echo -e "${RED}Failed to start. Check /tmp/streamlit.log${NC}"
        fi
        read -p "Press enter..."
        ;;

    kill-extractions)
        echo -e "${YELLOW}Killing all extraction jobs...${NC}"
        pkill -f 'extract_.*\.py' 2>/dev/null || true
        sleep 1
        remaining=$(ps aux | grep 'extract_.*\.py' | grep -v grep | wc -l | tr -d ' ')
        if [ "$remaining" -eq 0 ]; then
            echo -e "${GREEN}All extraction jobs stopped.${NC}"
        else
            echo -e "${RED}$remaining jobs still running. Try: pkill -9 -f 'extract_.*\.py'${NC}"
        fi
        read -p "Press enter..."
        ;;

    stop)
        echo -e "${YELLOW}Stopping peon-swarm...${NC}"
        pkill -f 'streamlit run' 2>/dev/null || true
        pkill -f 'extract_.*\.py' 2>/dev/null || true
        tmux kill-session -t "${OPENPEON_SESSION:-peon-swarm}" 2>/dev/null || true
        echo -e "${GREEN}Done.${NC}"
        ;;

    help)
        echo "Actions: restart-streamlit, kill-extractions, stop"
        ;;
esac
