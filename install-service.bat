@echo off
rem ============================================================================
rem  Install "Real Estate Search" as a Windows service via NSSM.
rem
rem  Runs the backend (which also runs the scheduler: scans, price snapshots,
rem  backups) on http://localhost:8000, starting at boot and auto-restarting if
rem  it crashes -- no console window to keep open. Everything stays on loopback
rem  (127.0.0.1): the API has no password, so it must not be exposed.
rem
rem  One-time prep:
rem    1. Download NSSM from https://nssm.cc/download (nssm 2.24).
rem    2. From the zip, copy win64\nssm.exe next to THIS script (or put it on PATH).
rem    3. Right-click this file -> "Run as administrator".
rem ============================================================================
setlocal
cd /d "%~dp0"
title Install Real Estate Search service

rem --- must be elevated: creating a service needs admin -----------------------
net session >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Please right-click this file and choose "Run as administrator".
    pause
    exit /b 1
)

rem --- locate nssm.exe: PATH first, then this folder --------------------------
set "NSSM=nssm.exe"
where nssm.exe >nul 2>nul
if errorlevel 1 (
    if exist "%~dp0nssm.exe" (
        set "NSSM=%~dp0nssm.exe"
    ) else (
        echo [ERROR] nssm.exe not found. Download it from https://nssm.cc/download,
        echo         then copy win64\nssm.exe next to this script and re-run.
        pause
        exit /b 1
    )
)

set "PY=%~dp0backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo [ERROR] Backend virtual environment missing: %PY%
    echo         Run start.bat once first so it creates backend\.venv.
    pause
    exit /b 1
)

rem --- build the dashboard so the backend serves it on the single port 8000 ---
if not exist "%~dp0frontend\dist\index.html" (
    echo [1/2] Building the frontend once...
    pushd frontend
    call npm run build
    if errorlevel 1 (
        popd
        echo [ERROR] Frontend build failed. Fix it, then re-run this script.
        pause
        exit /b 1
    )
    popd
)

set "SVC=RealEstateSearch"
echo [2/2] Registering the "%SVC%" service...

"%NSSM%" install %SVC% "%PY%" run.py
"%NSSM%" set %SVC% AppDirectory "%~dp0backend"
"%NSSM%" set %SVC% DisplayName "Real Estate Search"
"%NSSM%" set %SVC% Description "Local real estate monitor (Immobiliare.it + Idealista) + scheduler"
"%NSSM%" set %SVC% Start SERVICE_AUTO_START
rem NSSM restarts the process automatically if it exits; log to a rotating file
"%NSSM%" set %SVC% AppStdout "%~dp0backend\service.log"
"%NSSM%" set %SVC% AppStderr "%~dp0backend\service.log"
"%NSSM%" set %SVC% AppRotateFiles 1
"%NSSM%" set %SVC% AppRotateBytes 5000000

rem Point NSSM service (LocalSystem) to the Chromium browser cache if already installed
if exist "%~dp0backend\browser_binaries" (
    "%NSSM%" set %SVC% AppEnvironmentExtra "PLAYWRIGHT_BROWSERS_PATH=%~dp0backend\browser_binaries"
) else if exist "%USERPROFILE%\AppData\Local\ms-playwright" (
    "%NSSM%" set %SVC% AppEnvironmentExtra "PLAYWRIGHT_BROWSERS_PATH=%USERPROFILE%\AppData\Local\ms-playwright"
)

"%NSSM%" start %SVC%

echo.
echo ============================================================================
echo  Done. The dashboard is at:  http://localhost:8000
echo  (bookmark it, or make a desktop shortcut to that address)
echo.
echo  Manage it later:
echo    nssm restart RealEstateSearch     ^(after updating the code^)
echo    nssm stop    RealEstateSearch
echo    nssm edit    RealEstateSearch     ^(GUI: change account, env vars...^)
echo  Logs: backend\service.log
echo ============================================================================
pause
