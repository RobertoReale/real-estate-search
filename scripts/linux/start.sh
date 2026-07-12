#!/bin/bash
# Startup script for Linux / Raspberry Pi

# Navigate to the script's directory
cd "$(dirname "$0")"

echo "============================================"
echo "  Real Estate Search - Linux Startup Script "
echo "============================================"

# Ensure node and python3 are available
if ! command -v node &> /dev/null; then
    echo "[ERROR] Node.js is required but not installed."
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is required but not installed."
    exit 1
fi

# 1. Setup Backend Virtual Environment
if [ ! -d "backend/.venv" ]; then
    echo "[SETUP] Creating Python virtual environment..."
    python3 -m venv backend/.venv
    echo "[SETUP] Installing Python dependencies..."
    backend/.venv/bin/pip install --upgrade pip
    backend/.venv/bin/pip install -r backend/requirements.txt
fi

# 2. Setup Frontend Node Modules
if [ ! -d "frontend/node_modules" ]; then
    echo "[SETUP] Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

# 3. Start Services
echo "[1/2] Starting backend on http://localhost:8000 ..."
cd backend
./.venv/bin/python run.py &
BACKEND_PID=$!
cd ..

echo "[2/2] Starting frontend on http://localhost:5173 ..."
cd frontend
npm run dev -- --host &
FRONTEND_PID=$!
cd ..

# Keep script running and handle shutdown gracefully
trap "echo 'Stopping services...'; kill $BACKEND_PID; kill $FRONTEND_PID; exit" INT TERM
echo "Platform started! Press CTRL+C to stop both servers."
wait
