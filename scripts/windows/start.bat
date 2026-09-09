@echo off
title Real Estate Search
cd /d "%~dp0..\.."

echo ============================================
echo   Real Estate Search
echo ============================================

rem One window, one port. The backend serves the built React app at "/" (the
rem StaticFiles mount in main.py), so there is no second process and no second
rem port to explain - closing this window stops the application.
rem
rem The two-process Vite flow this script used to be is still here as dev.bat:
rem it is the right tool for editing code, and the wrong one for using the app.
rem
rem Every setup step is checked. Unchecked, a failed `pip install` still reached
rem the startup line below and the user met an import traceback three steps away
rem from the actual cause.
rem
rem `if errorlevel 1` and not `%errorlevel%`: inside a parenthesised block the
rem percent form is expanded when the block is *parsed*, so it holds the value
rem from before the command ran. The keyword form is evaluated at run time.

if not exist "backend\.venv\Scripts\python.exe" (
    call :require_python
    if errorlevel 1 goto :setup_failed
    echo [SETUP] Creazione dell'ambiente virtuale Python...
    python -m venv backend\.venv
    if errorlevel 1 goto :venv_failed
    echo [SETUP] Installazione delle dipendenze del backend...
    backend\.venv\Scripts\pip install -r backend\requirements.txt
    if errorlevel 1 goto :pip_failed
)

rem Catches a venv that exists but is incomplete - an install interrupted
rem halfway leaves the directory behind, and the check above would accept it.
if not exist "backend\.venv\Scripts\python.exe" goto :venv_failed

rem Builds only when frontend\dist is missing or older than the sources, and
rem only then needs Node at all - a release ships dist prebuilt, so this is a
rem no-op there. See scripts\build_frontend.py.
backend\.venv\Scripts\python scripts\build_frontend.py
if errorlevel 1 goto :frontend_failed

echo.
echo Dashboard: http://localhost:8000
echo Premi Ctrl+C in questa finestra per fermare l'applicazione.
echo.

rem Opens the browser once the port actually answers. It has to run alongside
rem the server, because the server below owns this window until it exits.
start "" /b backend\.venv\Scripts\python scripts\open_dashboard.py

pushd backend
.venv\Scripts\python run.py
popd
exit /b 0

:venv_failed
echo.
echo [ERRORE] Impossibile creare l'ambiente virtuale in backend\.venv.
echo          Su Windows la causa solita e' il modulo "venv" mancante oppure
echo          l'assenza dei permessi di scrittura in questa cartella. Cancella
echo          backend\.venv se esiste e riesegui questo script.
goto :setup_failed

:pip_failed
echo.
echo [ERRORE] Installazione delle dipendenze del backend non riuscita.
echo          Nella maggior parte dei casi manca la connessione a internet:
echo          controllala e riesegui questo script. Se l'errore qui sopra nomina
echo          un pacchetto che non si e' compilato, la versione di Python e'
echo          probabilmente fuori intervallo: questo progetto richiede dalla
echo          3.11 alla 3.14.
goto :setup_failed

:frontend_failed
echo.
echo [ERRORE] Impossibile compilare la dashboard - vedi il messaggio qui sopra.
echo          Per compilarla serve Node.js 18+ nel PATH. Una release scaricata
echo          arriva con la dashboard gia' compilata e non richiede Node.
goto :setup_failed

:setup_failed
echo.
echo Installazione interrotta - non e' stato avviato niente.
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
    echo [ERRORE] Questo progetto richiede Python dalla 3.11 alla 3.14 ^(la 3.12
    echo          e' quella su cui gira la verifica^).
    echo          Trovato:
    python --version 2>nul
    echo          Se qui sopra non c'e' niente, Python non e' nel PATH.
    echo          Installalo da https://www.python.org/downloads/ spuntando
    echo          "Add python.exe to PATH", poi riesegui questo script.
    exit /b 1
)
exit /b 0
