#!/bin/bash
#
# Agent IAM System - Startup Script
#
# Starts the IAM authorization server in the background.
# Agents are CLI-based and invoked by demo scripts on demand.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env file if it exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
    echo "[config] Loaded environment from .env"
fi

# Activate Python virtual environment (if available)
if [ -n "$VIRTUAL_ENV" ]; then
    echo "[config] Using active virtualenv: $VIRTUAL_ENV"
elif [ -f "$SCRIPT_DIR/../myvenv/bin/activate" ]; then
    source "$SCRIPT_DIR/../myvenv/bin/activate"
    echo "[config] Activated virtualenv"
else
    echo "[config] No virtualenv found — using system Python"
fi

# Install dependencies
pip install -r requirements.txt -q 2>/dev/null || true

echo "============================================"
echo "  Agent IAM System - Starting..."
echo "============================================"
echo ""

# Kill any existing instance (using PID file or process name)
if [ -f .iam_server.pid ]; then
    kill $(cat .iam_server.pid) 2>/dev/null || true
    sleep 1
else
    pkill -f "python iam_server.py" 2>/dev/null || true
    sleep 1
fi

# Start IAM server
echo "[1/1] Starting IAM Authorization Server..."
python iam_server.py &
IAM_PID=$!
echo "       PID: $IAM_PID"

# Wait for server to be ready
for i in $(seq 1 15); do
    if curl -s http://127.0.0.1:8900/health > /dev/null 2>&1; then
        echo "       Status: READY"
        break
    fi
    sleep 1
done

echo ""
echo "============================================"
echo "  System started successfully!"
echo "  IAM Server: http://127.0.0.1:8900"
echo "  Health:     http://127.0.0.1:8900/health"
echo "  API Docs:   http://127.0.0.1:8900/docs"
echo "============================================"
echo ""
echo "Run demo:"
echo "  python demo.py              # Unified interactive demo"
echo "  python demo_normal.py       # Normal delegation flow"
echo "  python demo_unauthorized.py # Unauthorized interception"
echo ""
echo "Stop server:"
echo "  bash stop.sh"
echo ""

# Save PID for stop script
echo $IAM_PID > .iam_server.pid
