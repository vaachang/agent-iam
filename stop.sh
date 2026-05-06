#!/bin/bash
#
# Agent IAM System - Stop Script
#

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping Agent IAM System..."

if [ -f .iam_server.pid ]; then
    PID=$(cat .iam_server.pid)
    kill $PID 2>/dev/null && echo "Stopped IAM server (PID: $PID)"
    rm -f .iam_server.pid
else
    pkill -f "python iam_server.py" 2>/dev/null && echo "Stopped IAM server"
fi

echo "Done."
