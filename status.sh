#!/bin/bash
# ============================================================
# Polymarket Insider Tracker - Status Check Script
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$PROJECT_DIR/.tracker.pid"
LOG_FILE="$PROJECT_DIR/tracker.log"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Polymarket Insider Tracker Status${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        # Get process uptime
        UPTIME=$(ps -p "$PID" -o etime= 2>/dev/null | xargs)
        MEM=$(ps -p "$PID" -o rss= 2>/dev/null | awk '{printf "%.1f MB", $1/1024}')
        echo -e "   Status:  ${GREEN}● RUNNING${NC}"
        echo -e "   PID:     ${CYAN}$PID${NC}"
        echo -e "   Uptime:  ${CYAN}$UPTIME${NC}"
        echo -e "   Memory:  ${CYAN}$MEM${NC}"
    else
        echo -e "   Status:  ${RED}● STOPPED${NC} (stale PID file)"
    fi
else
    echo -e "   Status:  ${RED}● STOPPED${NC}"
fi

echo ""

# Show last 5 log lines
if [ -f "$LOG_FILE" ]; then
    echo -e "${CYAN}📋 Last 5 log lines:${NC}"
    echo -e "${YELLOW}────────────────────────────────────────${NC}"
    tail -5 "$LOG_FILE"
    echo -e "${YELLOW}────────────────────────────────────────${NC}"
    LOG_SIZE=$(du -h "$LOG_FILE" | cut -f1)
    echo -e "   Log size: ${CYAN}$LOG_SIZE${NC}"
fi
echo ""
