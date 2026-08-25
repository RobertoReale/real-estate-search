@echo off
title Real Estate Search - Startup
cd /d "%~dp0..\.."

echo ============================================
echo   Real Estate Search - Starting Platform
echo ============================================

if not exist "backend\.venv\Scripts\python.exe" (
    call :require_python
    if errorlevel 1 goto :setup_failed
    echo [SETUP] Creating Python virtual environment...
    python -m venv backend\.venv
    backend\.venv\Scripts\pip install -r backend\requirements.txt
)

if not exist "frontend\node_modules" (
    echo [SETUP] Installing frontend dependencies...
    pushd frontend
    rem `ci`, not `install`: it installs exactly what package-lock.json pins and
    rem refuses if the lock disagrees with package.json, where `install` would
    rem quietly rewrite the lock and give this machine a different toolchain.
    call npm ci
    popd
)

echo [1/2] Starting backend on http://localhost:8000 ...
start "Backend - FastAPI" cmd /k "cd /d %~dp0..\..\backend && set APP_RELOAD=1&& .venv\Scripts\python run.py"

echo [2/2] Starting frontend on http://localhost:5173 ...
start "Frontend - Vite" cmd /k "cd /d %~dp0..\..\frontend && npm run dev"

timeout /t 4 /nobreak >nul
start http://localhost:5173

echo.
echo Platform started! Close the two windows "Backend" and "Frontend" to stop it.
exit /b 0

:setup_failed
echo.
echo Setup stopped - nothing was started.
pause
exit /b 1

rem ---------------------------------------------------------------------------
:require_python
rem backend\pyproject.toml declares requires-python = ">=3.11,<3.15". Checking it
rem here, before the venv exists, is the difference between "install a different
rem Python" and a traceback about a wheel that failed to build, printed halfway
rem through the dependency install.
rem
rem The caller uses `if errorlevel 1 goto`, not `call ... || exit /b 1`: the
rem second form does stop the script, but cmd loses the code on the way out and
rem the process still reports success.
python -c "import sys; raise SystemExit(0 if (3,11) <= sys.version_info < (3,15) else 1)" 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] This project needs Python 3.11 to 3.14 ^(3.12 is the tested pick^).
    echo         Found:
    python --version 2>nul
    echo         Nothing printed above means Python is not on PATH at all.
    echo         Install it from https://www.python.org/downloads/ with
    echo         "Add python.exe to PATH" ticked, then run this script again.
    exit /b 1
)
exit /b 0
