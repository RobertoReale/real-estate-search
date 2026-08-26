@echo off
title Real Estate Search - Phone access
cd /d "%~dp0..\.."

echo ============================================
echo   Real Estate Search - Serving to the phone
echo ============================================

rem Setup steps are checked exactly as in start.bat, and for the same reason:
rem this script already refused to serve a frontend that failed to build, but a
rem failed `pip install` upstream of that used to sail straight past.

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
    rem `ci` installs exactly what package-lock.json pins; `install` would
    rem rewrite it (see start.bat).
    call npm ci
    if errorlevel 1 (
        popd
        goto :npm_failed
    )
    popd
)

rem An interrupted install leaves the directory behind but no interpreter in it.
if not exist "backend\.venv\Scripts\python.exe" goto :venv_failed

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
rem Same pre-flight as start.bat: backend\pyproject.toml declares
rem requires-python = ">=3.11,<3.15", and an unsupported interpreter must say so
rem before the venv is built rather than fail inside the dependency install.
rem The caller checks `if errorlevel 1` rather than using `|| exit /b 1`, which
rem stops the script but leaves the process reporting success.
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
