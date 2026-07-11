@echo off
title Real Estate Search - Phone access
cd /d "%~dp0"

echo ============================================
echo   Real Estate Search - Serving to the phone
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

echo [1/3] Building the frontend (this is what the phone loads)...
pushd frontend
call npm run build
if errorlevel 1 (
    popd
    echo.
    echo [ERROR] Frontend build failed - server not started.
    pause
    exit /b 1
)
popd

echo [2/3] Resolving the address to bind...
if not "%APP_HOST%"=="" goto :have_host

if /i "%~1"=="lan" (
    set "APP_HOST=0.0.0.0"
    echo [WARNING] Binding 0.0.0.0: every device on this network reaches the
    echo           dashboard, and the API has no password. Tailscale is safer.
    goto :have_host
)

rem Prefer the Tailscale address: reachable from the phone anywhere, and from
rem nothing else. `tailscale` is often off PATH, so try the install path too.
for /f "delims=" %%i in ('tailscale ip -4 2^>nul') do if not defined APP_HOST set "APP_HOST=%%i"
if not defined APP_HOST (
    for /f "delims=" %%i in ('"%ProgramFiles%\Tailscale\tailscale.exe" ip -4 2^>nul') do if not defined APP_HOST set "APP_HOST=%%i"
)

if not defined APP_HOST (
    echo.
    echo [ERROR] No Tailscale address found - is Tailscale installed and logged in?
    echo         Install it on this PC and on the phone ^(https://tailscale.com^),
    echo         then run this script again.
    echo         Alternatives: `serve.bat lan` to expose it on the local Wi-Fi,
    echo         or set APP_HOST yourself to pick an interface.
    pause
    exit /b 1
)

:have_host
echo.
echo [3/3] Dashboard + API on http://%APP_HOST%:8000
echo       Open that URL on the phone, then "Add to home screen".
echo       Press Ctrl+C to stop.
echo.
pushd backend
.venv\Scripts\python run.py
popd
