#!/bin/bash
# ============================================================
# Polymarket Insider Tracker - Stop Script
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$PROJECT_DIR/.tracker.pid"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo -e "${YELLOW}⏹  Stopping tracker (PID: $PID)...${NC}"
        kill "$PID" 2>/dev/null
        for i in $(seq 1 10); do
            if ! kill -0 "$PID" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        if kill -0 "$PID" 2>/dev/null; then
            echo -e "${RED}⚠  Force killing...${NC}"
            kill -9 "$PID" 2>/dev/null || true
        fi
        echo -e "${GREEN}✅ Tracker stopped.${NC}"
    else
        echo -e "${YELLOW}ℹ  Process (PID: $PID) is not running.${NC}"
    fi
    rm -f "$PID_FILE"
else
    echo -e "${YELLOW}ℹ  No PID file found. Tracker may not be running.${NC}"
fi

# Clean up any orphaned processes
ORPHANS=$(pgrep -f "python.*run\.py" 2>/dev/null || true)
if [ -n "$ORPHANS" ]; then
    echo -e "${YELLOW}⏹  Killing orphaned processes: $ORPHANS${NC}"
    echo "$ORPHANS" | xargs kill 2>/dev/null || true
fi
