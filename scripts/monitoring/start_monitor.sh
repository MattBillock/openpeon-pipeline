#!/usr/bin/env bash
# OpenPeon Pipeline — TMUX Monitoring Dashboard
#
# Layout:
# ┌──────────────────────────────┬─────────────────────────┐
# │                              │  Streamlit Dashboard Log │
# │  Claude Code                 ├─────────────────────────┤
# │  (workspace)                 │  Extraction Jobs         │
# │                              ├─────────────────────────┤
# │                              │  Pack Status             │
# └──────────────────────────────┴─────────────────────────┘
#   Status bar: Dashboard:ON │ N extractions │ N packs published
#
# Navigation: prefix+0=Claude, prefix+d=dashboard, prefix+e=extraction, prefix+p=packs
# Menu: prefix+s

set -euo pipefail

SESSION_NAME="${OPENPEON_SESSION:-peon-swarm}"
PROJECT_ROOT="${OPENPEON_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXTRACTION_DIR="$PROJECT_ROOT/extraction"
PACKS_DIR="${OPENPEON_PACKS:-$PROJECT_ROOT/../openpeon-movie-packs}"
STREAMLIT_LOG="/tmp/streamlit.log"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[peon]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[peon]${NC} $1"; }
log_error() { echo -e "${RED}[peon]${NC} $1"; }

check_dependencies() {
    if ! command -v tmux &>/dev/null; then
        log_error "tmux is not installed. Install with: brew install tmux"
        exit 1
    fi
}

session_exists() {
    tmux has-session -t "$SESSION_NAME" 2>/dev/null
}

kill_existing_session() {
    if session_exists; then
        log_warn "Killing existing session '$SESSION_NAME'"
        tmux kill-session -t "$SESSION_NAME"
    fi
}

create_session() {
    log_info "Firing up the extraction swarm..."

    kill_existing_session

    # Create session first — guarantees tmux server is running
    tmux new-session -d -s "$SESSION_NAME" -c "$PROJECT_ROOT" -x 220 -y 55

    # Detect base-index settings
    local _W _P WIN T0 T1 T2 T3
    _W=$(tmux show-options -gv base-index 2>/dev/null || echo 0)
    _P=$(tmux show-option -wgv pane-base-index 2>/dev/null || echo 0)
    WIN="$SESSION_NAME:$_W"
    T0="$SESSION_NAME:$_W.$_P"
    T1="$SESSION_NAME:$_W.$((_P + 1))"
    T2="$SESSION_NAME:$_W.$((_P + 2))"
    T3="$SESSION_NAME:$_W.$((_P + 3))"

    tmux rename-window -t "$WIN" "monitor"

    # Split: right column (40%)
    tmux split-window -h -t "$T0" -c "$PROJECT_ROOT" -p 40

    # Split right column into 3 panes
    tmux split-window -v -t "$T1" -c "$PROJECT_ROOT" -p 40
    tmux split-window -v -t "$T2" -c "$PROJECT_ROOT" -p 50

    # --- Pane 0: Claude Code workspace (left, large) ---
    tmux send-keys -t "$T0" "cd '$PROJECT_ROOT' && clear" C-m
    if command -v claude &>/dev/null; then
        tmux send-keys -t "$T0" "claude" C-m
    fi

    # --- Pane 1: Streamlit Dashboard Log (top right) ---
    tmux send-keys -t "$T1" "touch '$STREAMLIT_LOG' && tail -f '$STREAMLIT_LOG'" C-m

    # --- Pane 2: Extraction Job Monitor (mid right) ---
    tmux send-keys -t "$T2" "while true; do clear; bash '$SCRIPT_DIR/extraction_status.sh'; sleep 5; done" C-m

    # --- Pane 3: Pack Status (bottom right) ---
    tmux send-keys -t "$T3" "while true; do clear; echo 'Published Packs:'; echo; ls -1 '$PACKS_DIR' | grep -v -E '(LICENSE|README)' | nl; echo; echo \"Total: \$(ls -1 '$PACKS_DIR' | grep -v -E '(LICENSE|README)' | wc -l | tr -d ' ') packs\"; sleep 30; done" C-m

    # Pane titles
    tmux set-option -t "$SESSION_NAME" pane-border-status top
    tmux set-option -t "$SESSION_NAME" pane-border-format " #[bold]#{pane_title} "
    tmux set-option -t "$SESSION_NAME" pane-border-style "fg=colour240"
    tmux set-option -t "$SESSION_NAME" pane-active-border-style "fg=colour214"

    tmux select-pane -t "$T0" -T "Claude Code"
    tmux select-pane -t "$T1" -T "Streamlit Log"
    tmux select-pane -t "$T2" -T "Extraction Jobs"
    tmux select-pane -t "$T3" -T "Pack Status"

    # ─── Navigation keybindings ──────────────────────────────────────
    tmux bind-key -T prefix 0 select-pane -t "$T0"
    tmux bind-key -T prefix d select-pane -t "$T1"
    tmux bind-key -T prefix e select-pane -t "$T2"
    tmux bind-key -T prefix p select-pane -t "$T3"

    # ─── Swarm menu (prefix+s) ────────────────────────────────────────
    tmux bind-key -T prefix s display-menu -T "#[bold]Peon Swarm" \
        "Start Extraction (all)"     a "display-popup -E -w 70 -h 25 'cd \"$PROJECT_ROOT/extraction\" && MAX_PARALLEL=4 bash run_extractions.sh; read -p \"Press enter...\"'" \
        "Start Extraction (pick)"    e "display-popup -E -w 70 -h 25 'cd \"$PROJECT_ROOT/extraction\" && echo \"Movies:\" && ls extract_*.py | sed \"s/extract_//;s/.py//\" && echo && read -p \"Movie name: \" m && MAX_PARALLEL=1 bash run_extractions.sh \$m; read -p \"Press enter...\"'" \
        "Restart Streamlit"          r "display-popup -E -w 60 -h 15 '$SCRIPT_DIR/actions.sh restart-streamlit'" \
        "Kill Extractions"           k "display-popup -E -w 60 -h 15 '$SCRIPT_DIR/actions.sh kill-extractions'" \
        "Open Dashboard (browser)"   o "run-shell 'open http://localhost:8501'" \
        "" \
        "Sync Packs to Git"          g "display-popup -E -w 60 -h 20 'cd \"$PACKS_DIR\" && git status && echo && read -p \"Push? (y/n) \" yn && [ \"\$yn\" = y ] && git add -A && git commit -m \"update packs\" && git push; read -p \"Press enter...\"'" \
        "Extraction Log (pick)"      l "display-popup -E -w 80 -h 35 'cd \"$EXTRACTION_DIR\" && echo \"Logs:\" && ls -1 */extraction.log 2>/dev/null | sed \"s|/extraction.log||\" && echo && read -p \"Movie: \" m && tail -100 \"\$m/extraction.log\"; read -p \"Press enter...\"'" \
        "" \
        "Stop Dashboard"             q "display-popup -E -w 60 -h 10 '$SCRIPT_DIR/actions.sh stop'"

    # ─── Status bar ──────────────────────────────────────────────────
    tmux set-option -t "$SESSION_NAME" status on
    tmux set-option -t "$SESSION_NAME" status-style "bg=colour235,fg=colour248"
    tmux set-option -t "$SESSION_NAME" status-left "#[bold,fg=colour214] PEON SWARM #[default]│ "
    tmux set-option -t "$SESSION_NAME" status-left-length 20
    tmux set-option -t "$SESSION_NAME" status-right "#(bash '$SCRIPT_DIR/status_line.sh') │ %H:%M"
    tmux set-option -t "$SESSION_NAME" status-right-length 80
    tmux set-option -t "$SESSION_NAME" status-interval 5

    # Focus Claude Code pane
    tmux select-pane -t "$T0"

    log_info "Swarm is hot. Attaching..."
}

attach_session() {
    if [ -n "${TMUX:-}" ]; then
        tmux switch-client -t "$SESSION_NAME"
    else
        tmux attach-session -t "$SESSION_NAME"
    fi
}

# --- Main ---

check_dependencies

case "${1:-start}" in
    start)
        create_session
        attach_session
        ;;
    stop)
        kill_existing_session
        log_info "Swarm dismissed."
        ;;
    restart)
        create_session
        attach_session
        ;;
    status)
        if session_exists; then
            log_info "Session '$SESSION_NAME' is running."
            tmux list-panes -t "$SESSION_NAME" -F "  #{pane_index}: #{pane_title} (#{pane_width}x#{pane_height})" 2>/dev/null
        else
            log_warn "Session '$SESSION_NAME' is not running."
        fi
        ;;
    attach)
        if session_exists; then
            attach_session
        else
            log_error "No session running. Use: $0 start"
            exit 1
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|attach}"
        exit 1
        ;;
esac
