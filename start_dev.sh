#!/bin/bash

# ══════════════════════════════════════════════════════
#  ELAF Dev Stack Launcher
#  Starts: Python backend → ADB port forwarding →
#          scrcpy mirroring → Flutter app
# ══════════════════════════════════════════════════════

set -e  # Exit on unhandled errors (before the trap is set)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
WHISPERX_PYTHON="/home/amjad/whisperx-env/bin/python"

# Load .env if present
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
    echo "[ENV] Loaded .env"
fi

# Disable unintended exits from now on — we handle cleanup ourselves
set +e

# ── Cleanup on exit ────────────────────────────────────
cleanup() {
    echo -e "\n\033[33m[Shutdown] Cleaning up...\033[0m"

    # Kill scrcpy
    [ -n "$SCRCPY_PID" ] && {
        pkill -9 -P "$SCRCPY_PID" 2>/dev/null
        kill -9 "$SCRCPY_PID" 2>/dev/null
    }

    # Kill any uvicorn / backend processes
    pkill -f "python main.py" 2>/dev/null
    pkill -f "uvicorn" 2>/dev/null

    echo -e "\033[32m[Shutdown] ELAF dev environment stopped.\033[0m"
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# ── Banner ─────────────────────────────────────────────
echo ""
echo -e "\033[1;34m╔══════════════════════════════════════════╗\033[0m"
echo -e "\033[1;34m║       ELAF — Dev Stack Launcher          ║\033[0m"
echo -e "\033[1;34m╚══════════════════════════════════════════╝\033[0m"
echo ""

# ── Step 1: Start the persistent PLP database ─────────
echo "[1/5] Starting PLP PostgreSQL..."
"$SCRIPT_DIR/scripts/plp_postgres.sh" start

# ── Step 2: ADB port forwarding ────────────────────────
echo "[2/5] ADB port forwarding (localhost:8000)..."
if adb reverse tcp:8000 tcp:8000 2>/dev/null; then
    echo "      ✅ Port forwarding active"
else
    echo "      ⚠ ADB not connected — backend will only work on host"
fi

# ── Step 3: Scrcpy ────────────────────────────────────
echo "[3/5] Launching scrcpy screen mirroring..."
if command -v scrcpy &>/dev/null; then
    scrcpy --stay-awake --turn-screen-off --show-touches --max-size 1024 -b 4M &>/dev/null &
    SCRCPY_PID=$!
    echo "      ✅ scrcpy PID=$SCRCPY_PID"
else
    echo "      ⚠ scrcpy not found — skipping"
fi

# ── Step 4: Python backend ────────────────────────────
echo "[4/5] Starting FastAPI backend..."
cd "$BACKEND_DIR"

if [ -x "$WHISPERX_PYTHON" ]; then
    echo "      Using whisperx-env Python: $WHISPERX_PYTHON"
    "$WHISPERX_PYTHON" main.py &
else
    echo "      Using system Python"
    python3 main.py &
fi
BACKEND_PID=$!
echo "      ✅ Backend PID=$BACKEND_PID"

# Wait for Uvicorn to spin up
echo "      Waiting for backend to start..."
sleep 3

# Health check
HEALTH=$(curl -sf http://localhost:8000/health 2>/dev/null)
if [ -n "$HEALTH" ]; then
    echo "      ✅ Backend healthy: $HEALTH"
else
    echo "      ⚠ Health check failed — backend may still be loading models"
fi

# ── Step 5: Flutter app (foreground) ──────────────────
echo ""
echo "[5/5] Launching Flutter app..."
echo -e "\033[1;32m      Press Ctrl+C to stop everything\033[0m"
echo ""
cd "$SCRIPT_DIR"
flutter run
