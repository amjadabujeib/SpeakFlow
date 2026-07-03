#!/bin/bash

# Load environment variables (like GROQ_API_KEY) from .env file if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Function to safely kill background processes when you close the script
cleanup() {
    echo -e "\n[Shutdown] Cleaning up background processes..."
    
    # Force kill child processes (like Uvicorn's reload worker) and the parent
    pkill -9 -P $SCRCPY_PID 2>/dev/null
    kill -9 $SCRCPY_PID 2>/dev/null
    
    # Uvicorn with reload=True spawns child workers that can evade standard parent kills.
    # We forcefully kill anything matching 'python main.py' to ensure port 8000 is freed.
    pkill -f "python main.py" 2>/dev/null
    
    echo "ELAF Development environment successfully shut down!"
    exit 0
}

# Trap Ctrl+C (SIGINT) and script exit to automatically trigger the cleanup
trap cleanup SIGINT EXIT

echo "=========================================="
echo "      Starting ELAF Dev Stack             "
echo "=========================================="

# 1. Port Forwarding
echo "[1/4] Setting up ADB port forwarding for localhost access..."
adb reverse tcp:8000 tcp:8000

# 2. Launch Scrcpy in the background
echo "[2/4] Launching scrcpy screen mirroring..."
scrcpy --stay-awake --turn-screen-off --show-touches --max-size 1024 -b 4M &
SCRCPY_PID=$!

# 3. Launch the Backend in the background
echo "[3/4] Starting FastAPI Python Backend..."
cd /home/amjad/Desktop/ELAF/backend
# Assuming the same virtual environment is needed for ML models (whisperx, etc.)
# If not using whisperx-env, this can just be `python main.py`
if [ -f /home/amjad/whisperx-env/bin/python ]; then
    /home/amjad/whisperx-env/bin/python main.py &
else
    python main.py &
fi
BACKEND_PID=$!

# Give Uvicorn a couple of seconds to spin up completely
sleep 2

# 4. Launch the Flutter Frontend in the foreground
echo "[4/4] Launching Flutter App..."
cd /home/amjad/Desktop/ELAF
flutter run
