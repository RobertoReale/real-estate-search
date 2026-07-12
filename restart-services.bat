@echo off
:: Verifica se ha i permessi di amministratore, altrimenti si auto-esegue come admin
net session >nul 2>nul
if %errorLevel% neq 0 (
    echo Richiesta permessi di amministratore...
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
echo Riavvio del servizio Real Estate Search in corso...
.\nssm.exe restart RealEstateSearch
echo.
echo Riavviato con successo!
timeout /t 3
