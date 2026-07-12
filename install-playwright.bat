@echo off
rem ============================================================================
rem  Install Playwright & Chromium into backend\.venv for Automatic Cookie Grab
rem
rem  This script sets up Playwright in the backend virtual environment (`.venv`)
rem  and downloads Chromium so the Windows Service (NSSM) or local platform
rem  can find and run it automatically at startup without any manual path setup.
rem ============================================================================
setlocal
cd /d "%~dp0"
title Install Playwright & Chromium

echo ============================================================================
echo   Installing Playwright & Chromium into backend virtual environment
echo ============================================================================

set "PY=%~dp0backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo [SETUP] Creating Python virtual environment...
    python -m venv backend\.venv
)

echo [1/3] Installing playwright package into backend\.venv ...
"%~dp0backend\.venv\Scripts\pip.exe" install playwright
if errorlevel 1 (
    echo [ERROR] Failed to install playwright. Check internet connection.
    pause
    exit /b 1
)

echo [2/3] Downloading Chromium browser binary ...
rem If not already set, default download path to user profile ms-playwright
if not defined PLAYWRIGHT_BROWSERS_PATH (
    if exist "%USERPROFILE%\AppData\Local\ms-playwright" (
        set "PLAYWRIGHT_BROWSERS_PATH=%USERPROFILE%\AppData\Local\ms-playwright"
    ) else (
        set "PLAYWRIGHT_BROWSERS_PATH=%~dp0backend\browser_binaries"
    )
)
"%~dp0backend\.venv\Scripts\playwright.exe" install chromium
if errorlevel 1 (
    echo [ERROR] Failed to download Chromium binary.
    pause
    exit /b 1
)

echo [3/3] Checking if RealEstateSearch Windows Service is active...
where nssm.exe >nul 2>nul
if not errorlevel 1 (
    nssm set RealEstateSearch AppEnvironmentExtra "PLAYWRIGHT_BROWSERS_PATH=%PLAYWRIGHT_BROWSERS_PATH%" >nul 2>nul
    nssm restart RealEstateSearch >nul 2>nul
    if not errorlevel 1 echo [INFO] Restarted RealEstateSearch service to pick up the new Chromium browser!
)

echo.
echo ============================================================================
echo   Done! Playwright & Chromium are ready.
echo   You can now open Settings (http://localhost:8000) and use automatic grab.
echo ============================================================================
pause
