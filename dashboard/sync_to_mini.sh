#!/bin/bash
# Sync dashboard code to Mac Mini and restart Streamlit
set -e

REMOTE="mini"
REMOTE_DIR="~/dev/openpeon"
LOCAL_DIR="$(dirname "$0")/.."

echo "Syncing code to $REMOTE..."
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
    "$LOCAL_DIR/" "$REMOTE:$REMOTE_DIR/" 2>&1 | grep -v '/$' | tail -10

echo ""
echo "Restarting Streamlit on $REMOTE..."
ssh "$REMOTE" "pkill -f 'streamlit run' 2>/dev/null; sleep 1; \
    export PATH=/opt/homebrew/bin:\$PATH && \
    cd ~/dev/openpeon/dashboard && \
    source .venv/bin/activate && \
    nohup streamlit run app.py \
        --server.address 0.0.0.0 \
        --server.port 8501 \
        --server.fileWatcherType none \
        --server.runOnSave false \
        --server.headless true \
        > /tmp/streamlit.log 2>&1 &"

sleep 3
HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' http://192.168.1.155:8501)
if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Dashboard running at http://192.168.1.155:8501"
else
    echo "❌ Dashboard not responding (HTTP $HTTP_CODE)"
    ssh "$REMOTE" "tail -20 /tmp/streamlit.log"
fi
