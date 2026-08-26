#!/bin/bash
# Startup script for Linux / Raspberry Pi
#
# `set -e` is deliberately NOT used: it would abort with no explanation at all,
# and the whole point here is that a failed setup step says what to do about it.
# Every step is checked explicitly instead, the same way the .bat scripts do it.

# Repository root, not the script's own directory: every path below is relative
# to the root, and `cd $(dirname $0)` used to leave us in scripts/linux, where
# "backend/" does not exist. The venv was then built under scripts/linux and the
# dependency install failed on a requirements.txt that was not there - silently,
# because nothing checked its exit code.
cd "$(dirname "$0")/../.." || exit 1

echo "============================================"
echo "  Real Estate Search - Linux Startup Script "
echo "============================================"

fail() {
    echo
    echo "[ERROR] $1"
    shift
    for line in "$@"; do
        echo "        $line"
    done
    echo
    echo "Setup stopped - nothing was started."
    exit 1
}

# Ensure node and python3 are available
if ! command -v node &> /dev/null; then
    fail "Node.js is required but not installed."
fi

if ! command -v python3 &> /dev/null; then
    fail "Python 3 is required but not installed."
fi

# 1. Setup Backend Virtual Environment
if [ ! -x "backend/.venv/bin/python" ]; then
    # backend/pyproject.toml declares requires-python = ">=3.11,<3.15". Check it
    # before building the venv: an unsupported interpreter otherwise surfaces as
    # a wheel that will not build, midway through installing dependencies.
    if ! python3 -c 'import sys; raise SystemExit(0 if (3,11) <= sys.version_info < (3,15) else 1)'; then
        fail "This project needs Python 3.11 to 3.14 (3.12 is the tested pick)." \
             "Found: $(python3 --version 2>&1)" \
             "Install a supported version, then run this script again."
    fi
    echo "[SETUP] Creating Python virtual environment..."
    python3 -m venv backend/.venv || fail \
        "Could not create the virtual environment in backend/.venv." \
        "On Debian/Raspberry Pi OS the venv module ships separately:" \
        "  sudo apt install python3-venv"
    echo "[SETUP] Installing Python dependencies..."
    backend/.venv/bin/pip install --upgrade pip || fail \
        "Could not upgrade pip inside the virtual environment." \
        "This is almost always no internet connection."
    backend/.venv/bin/pip install -r backend/requirements.txt || fail \
        "Installing the backend dependencies failed." \
        "Most often this is no internet connection. If the error above names a" \
        "package that failed to build, check the Python version is 3.11 to 3.14."
fi

# An interrupted install leaves the directory behind but no interpreter in it,
# which the directory check above would happily accept.
[ -x "backend/.venv/bin/python" ] || fail \
    "backend/.venv exists but has no interpreter - the install was interrupted." \
    "Remove it and run this script again:  rm -rf backend/.venv"

# 2. Setup Frontend Node Modules
if [ ! -d "frontend/node_modules" ]; then
    echo "[SETUP] Installing frontend dependencies..."
    # `ci`, not `install`: it installs exactly what package-lock.json pins and
    # refuses if the lock disagrees with package.json, where `install` would
    # quietly rewrite the lock and give this machine a different toolchain.
    (cd frontend && npm ci) || fail \
        "Installing the frontend dependencies failed (npm ci)." \
        "Check the internet connection. If npm reports the lock file is out of" \
        "sync with package.json, the checkout is inconsistent - restore" \
        "package-lock.json rather than running \`npm install\`."
fi

# 3. Start Services
echo "[1/2] Starting backend on http://localhost:8000 ..."
(cd backend && ./.venv/bin/python run.py) &
BACKEND_PID=$!

echo "[2/2] Starting frontend on http://localhost:5173 ..."
(cd frontend && npm run dev -- --host) &
FRONTEND_PID=$!

# Keep script running and handle shutdown gracefully
trap "echo 'Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
echo "Platform started! Press CTRL+C to stop both servers."
wait
