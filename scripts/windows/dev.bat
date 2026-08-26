@echo off
title Real Estate Search - Development
cd /d "%~dp0..\.."

echo ============================================
echo   Real Estate Search - Development Mode
echo ============================================
echo.
echo   Backend  :8000  (auto-reload on save)
echo   Frontend :5173  (Vite hot module reload)
echo.
echo   For normal use run start.bat instead: one window, one port.
echo.

rem This is the two-process flow: uvicorn with its file watcher, and Vite serving
rem the React app with HMR and proxying /api to :8000. It is what start.bat used
rem to be, and it is the right shape for editing code - a saved .tsx is on screen
rem before the editor loses focus, which no rebuild-and-serve loop can match.
rem
rem Every setup step is checked. Unchecked, a failed `pip install` still reached
rem the `start` lines below and the user met an import traceback in a window that
rem closes itself, three steps away from the actual cause.
rem
rem `if errorlevel 1` and not `%errorlevel%`: inside a parenthesised block the
rem percent form is expanded when the block is *parsed*, so it holds the value
rem from before the command ran. The keyword form is evaluated at run time.

if not exist "backend\.venv\Scripts\python.exe" (
    call :require_python
    if errorlevel 1 goto :setup_failed
    echo [SETUP] Creating Python virtual environment...
    python -m venv backend\.venv
    if errorlevel 1 goto :venv_failed
    echo [SETUP] Installing backend dependencies...
    backend\.venv\Scripts\pip install -r backend\requirements.txt
    if errorlevel 1 goto :pip_failed
)

if not exist "frontend\node_modules" (
    echo [SETUP] Installing frontend dependencies...
    pushd frontend
    rem `ci`, not `install`: it installs exactly what package-lock.json pins and
    rem refuses if the lock disagrees with package.json, where `install` would
    rem quietly rewrite the lock and give this machine a different toolchain.
    call npm ci
    if errorlevel 1 (
        popd
        goto :npm_failed
    )
    popd
)

rem Catches a venv that exists but is incomplete — an install interrupted
rem halfway leaves the directory behind, and the check above would accept it.
if not exist "backend\.venv\Scripts\python.exe" goto :venv_failed

echo [1/2] Starting backend on http://localhost:8000 ...
start "Backend - FastAPI" cmd /k "cd /d %~dp0..\..\backend && set APP_RELOAD=1&& .venv\Scripts\python run.py"

echo [2/2] Starting frontend on http://localhost:5173 ...
start "Frontend - Vite" cmd /k "cd /d %~dp0..\..\frontend && npm run dev"

timeout /t 4 /nobreak >nul
start http://localhost:5173

echo.
echo Dev servers started! Close the two windows "Backend" and "Frontend" to stop them.
exit /b 0

:venv_failed
echo.
echo [ERROR] Could not create the virtual environment in backend\.venv.
echo         On Windows the usual cause is a missing "venv" module or no write
echo         permission in this folder. Delete backend\.venv if it is there and
echo         run this script again.
goto :setup_failed

:pip_failed
echo.
echo [ERROR] Installing the backend dependencies failed.
echo         Most often this is no internet connection - check it and run this
echo         script again. If the error above names a package that failed to
echo         build, the Python version is probably out of range: this project
echo         needs 3.11 to 3.14.
goto :setup_failed

:npm_failed
echo.
echo [ERROR] Installing the frontend dependencies failed ^(npm ci^).
echo         Check the internet connection. If npm complains that the lock file
echo         is out of sync with package.json, the checkout is inconsistent -
echo         restore package-lock.json rather than running `npm install`.
goto :setup_failed

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
