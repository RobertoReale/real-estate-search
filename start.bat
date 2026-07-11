@echo off
title Real Estate Search - Startup
cd /d "%~dp0"

echo ============================================
echo   Real Estate Search - Starting Platform
echo ============================================

if not exist "backend\.venv\Scripts\python.exe" (
    echo [SETUP] Creating Python virtual environment...
    python -m venv backend\.venv
    backend\.venv\Scripts\pip install -r backend\requirements.txt
)

if not exist "frontend\node_modules" (
    echo [SETUP] Installing frontend dependencies...
    pushd frontend
    call npm install
    popd
)

echo [1/2] Starting backend on http://localhost:8000 ...
start "Backend - FastAPI" cmd /k "cd /d %~dp0backend && set APP_RELOAD=1&& .venv\Scripts\python run.py"

echo [2/2] Starting frontend on http://localhost:5173 ...
start "Frontend - Vite" cmd /k "cd /d %~dp0frontend && npm run dev"

timeout /t 4 /nobreak >nul
start http://localhost:5173

echo.
echo Platform started! Close the two windows "Backend" and "Frontend" to stop it.
