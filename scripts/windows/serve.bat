@echo off
title Real Estate Search - Accesso dal telefono
cd /d "%~dp0..\.."

echo ============================================
echo   Real Estate Search - Servito al telefono
echo ============================================

rem Setup steps are checked exactly as in start.bat, and for the same reason:
rem this script already refused to serve a frontend that failed to build, but a
rem failed `pip install` upstream of that used to sail straight past.

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

if not exist "frontend\node_modules" (
    echo [SETUP] Installazione delle dipendenze del frontend...
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

echo [1/3] Compilazione della dashboard - e' quello che carica il telefono...
pushd frontend
call npm run build
if errorlevel 1 (
    popd
    echo.
    echo [ERRORE] Compilazione della dashboard non riuscita - niente avviato.
    pause
    exit /b 1
)
popd

echo [2/3] Ricerca dell'indirizzo su cui mettersi in ascolto...
if not "%APP_HOST%"=="" goto :have_host

if /i "%~1"=="lan" (
    set "APP_HOST=0.0.0.0"
    echo [ATTENZIONE] In ascolto su 0.0.0.0: ogni dispositivo di questa rete
    echo              raggiunge la dashboard, e l'API non ha password.
    echo              Tailscale e' piu' sicuro.
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
    echo [ERRORE] Nessun indirizzo Tailscale trovato - Tailscale e' installato
    echo          e hai fatto l'accesso?
    echo          Installalo su questo PC e sul telefono ^(https://tailscale.com^),
    echo          poi riesegui questo script.
    echo          In alternativa: `serve.bat lan` per esporla sul Wi-Fi di casa,
    echo          oppure imposta tu APP_HOST per scegliere un'interfaccia.
    pause
    exit /b 1
)

:have_host
echo.
echo [3/3] Dashboard + API su http://%APP_HOST%:8000
echo       Apri quell'indirizzo sul telefono, poi "Aggiungi alla schermata Home".
echo       Premi Ctrl+C per fermare.
echo.
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

:npm_failed
echo.
echo [ERRORE] Installazione delle dipendenze del frontend non riuscita ^(npm ci^).
echo          Controlla la connessione a internet. Se npm dice che il lock file
echo          non e' allineato con package.json, la copia del progetto non e'
echo          coerente: ripristina package-lock.json invece di lanciare
echo          `npm install`.
goto :setup_failed

:setup_failed
echo.
echo Installazione interrotta - non e' stato avviato niente.
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
