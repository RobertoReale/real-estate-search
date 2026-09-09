#!/bin/bash
# Startup script for Linux / Raspberry Pi
#
# `set -e` is deliberately NOT used: it would abort with no explanation at all,
# and the whole point here is that a failed setup step says what to do about it.
# Every step is checked explicitly instead, the same way the .bat scripts do it.

# Repository root, not the script's own directory: every path below is relative
# to the root, and `cd $(dirname $0)` used to leave us in scripts/linux, where
# "backend/" does not exist. The venv was then built under scripts/linux and the
# dependency install failed on a requirements.txt that was not there - silently,
# because nothing checked its exit code.
cd "$(dirname "$0")/../.." || exit 1

echo "============================================"
echo "  Real Estate Search - Avvio su Linux            "
echo "============================================"

fail() {
    echo
    echo "[ERRORE] $1"
    shift
    for line in "$@"; do
        echo "         $line"
    done
    echo
    echo "Installazione interrotta - non è stato avviato niente."
    exit 1
}

# Ensure node and python3 are available
if ! command -v node &> /dev/null; then
    fail "Serve Node.js, ma non è installato."
fi

if ! command -v python3 &> /dev/null; then
    fail "Serve Python 3, ma non è installato."
fi

# 1. Setup Backend Virtual Environment
if [ ! -x "backend/.venv/bin/python" ]; then
    # backend/pyproject.toml declares requires-python = ">=3.11,<3.15". Check it
    # before building the venv: an unsupported interpreter otherwise surfaces as
    # a wheel that will not build, midway through installing dependencies.
    if ! python3 -c 'import sys; raise SystemExit(0 if (3,11) <= sys.version_info < (3,15) else 1)'; then
        fail "Questo progetto richiede Python dalla 3.11 alla 3.14 - la 3.12 è quella verificata." \
             "Trovato: $(python3 --version 2>&1)" \
             "Installa una versione supportata, poi riesegui questo script."
    fi
    echo "[SETUP] Creazione dell'ambiente virtuale Python..."
    python3 -m venv backend/.venv || fail \
        "Impossibile creare l'ambiente virtuale in backend/.venv." \
        "Su Debian e Raspberry Pi OS il modulo venv si installa a parte:" \
        "  sudo apt install python3-venv"
    echo "[SETUP] Installazione delle dipendenze Python..."
    backend/.venv/bin/pip install --upgrade pip || fail \
        "Impossibile aggiornare pip nell'ambiente virtuale." \
        "Quasi sempre manca la connessione a internet."
    backend/.venv/bin/pip install -r backend/requirements.txt || fail \
        "Installazione delle dipendenze del backend non riuscita." \
        "Nella maggior parte dei casi manca la connessione a internet. Se l'errore" \
        "qui sopra nomina un pacchetto che non si è compilato, controlla che la" \
        "versione di Python sia dalla 3.11 alla 3.14."
fi

# An interrupted install leaves the directory behind but no interpreter in it,
# which the directory check above would happily accept.
[ -x "backend/.venv/bin/python" ] || fail \
    "backend/.venv esiste ma non contiene un interprete: l'installazione si è interrotta." \
    "Cancellalo e riesegui questo script:  rm -rf backend/.venv"

# 2. Setup Frontend Node Modules
if [ ! -d "frontend/node_modules" ]; then
    echo "[SETUP] Installazione delle dipendenze del frontend..."
    # `ci`, not `install`: it installs exactly what package-lock.json pins and
    # refuses if the lock disagrees with package.json, where `install` would
    # quietly rewrite the lock and give this machine a different toolchain.
    (cd frontend && npm ci) || fail \
        "Installazione delle dipendenze del frontend non riuscita (npm ci)." \
        "Controlla la connessione a internet. Se npm dice che il lock file non è" \
        "allineato con package.json, la copia del progetto non è coerente:" \
        "ripristina package-lock.json invece di lanciare \`npm install\`."
fi

# 3. Start Services
echo "[1/2] Avvio del backend su http://localhost:8000 ..."
(cd backend && ./.venv/bin/python run.py) &
BACKEND_PID=$!

echo "[2/2] Avvio della dashboard su http://localhost:5173 ..."
(cd frontend && npm run dev -- --host) &
FRONTEND_PID=$!

# Keep script running and handle shutdown gracefully
trap "echo 'Arresto dei servizi...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
echo "Tutto avviato. Premi CTRL+C per fermare entrambi i servizi."
wait
