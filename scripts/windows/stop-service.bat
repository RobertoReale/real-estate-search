@echo off
rem Stop the "Real Estate Search" Windows service without removing it.
rem Use this before start.bat/serve.bat when you need to solve a CAPTCHA by
rem hand during the availability check: the service runs in Session 0 (no
rem desktop), so it can never show a browser window, no matter the Settings.
setlocal
cd /d "%~dp0"
title Stop Real Estate Search service

net session >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Please right-click this file and choose "Run as administrator".
    pause
    exit /b 1
)

set "NSSM=nssm.exe"
where nssm.exe >nul 2>nul
if errorlevel 1 if exist "%~dp0nssm.exe" set "NSSM=%~dp0nssm.exe"

"%NSSM%" stop RealEstateSearch

echo.
echo ============================================================================
echo  Service stopped. Run start.bat or serve.bat now to use the app normally.
echo.
echo  Don't forget to bring the service back afterwards:
echo    nssm start RealEstateSearch
echo  (or double-click restart-services.bat)
echo ============================================================================
pause
