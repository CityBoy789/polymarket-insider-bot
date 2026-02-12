#!/bin/bash
# ============================================================
# Polymarket Insider Tracker - Background Restart Script
# Usage: bash restart.sh [mode]
#   mode: continuous (default), scan, stats
# ============================================================

set -e

# ---- Configuration ----
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$PROJECT_DIR/.tracker.pid"
LOG_FILE="$PROJECT_DIR/tracker.log"
VENV_DIR="$PROJECT_DIR/venv"
MODE="${1:-continuous}"

# ---- Colors ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Polymarket Insider Tracker Restart${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# ---- Step 1: Kill previous process ----
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo -e "${YELLOW}⏹  Stopping previous process (PID: $OLD_PID)...${NC}"
        kill "$OLD_PID" 2>/dev/null
        # Wait up to 10 seconds for graceful shutdown
        for i in $(seq 1 10); do
            if ! kill -0 "$OLD_PID" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        # Force kill if still alive
        if kill -0 "$OLD_PID" 2>/dev/null; then
            echo -e "${RED}⚠  Force killing process (PID: $OLD_PID)...${NC}"
            kill -9 "$OLD_PID" 2>/dev/null || true
            sleep 1
        fi
        echo -e "${GREEN}✅ Previous process stopped.${NC}"
    else
        echo -e "${YELLOW}ℹ  Previous process (PID: $OLD_PID) is no longer running.${NC}"
    fi
    rm -f "$PID_FILE"
else
    echo -e "${YELLOW}ℹ  No previous PID file found.${NC}"
fi

# Also kill any orphaned run.py processes
ORPHANS=$(pgrep -f "python.*run\.py" 2>/dev/null || true)
if [ -n "$ORPHANS" ]; then
    echo -e "${YELLOW}⏹  Killing orphaned processes: $ORPHANS${NC}"
    echo "$ORPHANS" | xargs kill 2>/dev/null || true
    sleep 2
    # Force kill remaining
    ORPHANS=$(pgrep -f "python.*run\.py" 2>/dev/null || true)
    if [ -n "$ORPHANS" ]; then
        echo "$ORPHANS" | xargs kill -9 2>/dev/null || true
    fi
fi

# ---- Step 2: Activate venv ----
if [ -d "$VENV_DIR" ]; then
    echo -e "${CYAN}🔧 Activating virtual environment...${NC}"
    source "$VENV_DIR/bin/activate"
else
    echo -e "${RED}❌ Virtual environment not found at $VENV_DIR${NC}"
    echo -e "${RED}   Run install.sh first.${NC}"
    exit 1
fi

# ---- Step 3: Start in background ----
echo -e "${GREEN}🚀 Starting tracker in background (mode: $MODE)...${NC}"

nohup python "$PROJECT_DIR/run.py" --mode "$MODE" >> "$LOG_FILE" 2>&1 &
NEW_PID=$!

# Save PID
echo "$NEW_PID" > "$PID_FILE"

echo ""
echo -e "${GREEN}✅ Tracker started successfully!${NC}"
echo -e "   PID:      ${CYAN}$NEW_PID${NC}"
echo -e "   Mode:     ${CYAN}$MODE${NC}"
echo -e "   Log:      ${CYAN}$LOG_FILE${NC}"
echo -e "   PID File: ${CYAN}$PID_FILE${NC}"
echo ""
echo -e "${YELLOW}💡 Useful commands:${NC}"
echo -e "   tail -f $LOG_FILE          # Follow logs"
echo -e "   cat $PID_FILE              # Check PID"
echo -e "   bash stop.sh               # Stop tracker"
echo -e "   bash status.sh             # Check status"
echo ""
