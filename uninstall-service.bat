@echo off
rem Remove the "Real Estate Search" Windows service. Run as administrator.
rem Your data (backend\case.db, settings.json, backups) is left untouched.
setlocal
cd /d "%~dp0"
title Uninstall Real Estate Search service

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
"%NSSM%" remove RealEstateSearch confirm
echo.
echo Service removed. Your database and settings were not touched.
pause
