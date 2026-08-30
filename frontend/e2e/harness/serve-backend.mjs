/**
 * Starts the backend the browser suite runs against — and touches nothing else
 * on this machine.
 *
 * Playwright's `webServer` runs this before the first test (see
 * ../../playwright.config.ts). It is a script rather than a command line
 * because four things have to happen in a fixed order, and the order is the
 * safety:
 *
 *   1. a throwaway data directory, wiped first, so every run starts from the
 *      same rows and a failed run leaves nothing behind to poison the next one;
 *   2. a settings.json in it, with automatic scanning paused;
 *   3. the demo corpus seeded into it (scripts/seed_demo.py, deterministic),
 *      unless E2E_SEED=0 — the onboarding journey needs a database that has
 *      never held anything, and there is no way back to that state once seeded;
 *   4. the backend, with APP_DATA_DIR pointing at that directory and a port
 *      that is not 8000.
 *
 * Steps 1-3 belong here and not in a test fixture because APP_DATA_DIR is read
 * once, at import time (backend/app/config.py), so the directory has to be
 * finished before the process starts. That is also what puts the developer's
 * own backend/case.db permanently out of reach: the suite never opens it, never
 * migrates it and cannot restore over it.
 */
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..", "..");
const BACKEND_DIR = path.join(ROOT, "backend");

const port = process.env.E2E_BACKEND_PORT;
const dataDir = process.env.E2E_DATA_DIR;
if (!port || !dataDir) {
  console.error("E2E_BACKEND_PORT and E2E_DATA_DIR must be set; playwright.config.ts sets both.");
  process.exit(1);
}

/**
 * Everything the harness needs to be off. The rest of the defaults already are
 * (backend/app/config.py), but these four are the ones whose cost is a request
 * leaving the machine, so they are stated rather than assumed.
 */
const SETTINGS = {
  // The scheduler starts with the app. Paused, its scans return before they
  // reach a portal — a test run must never spend the residential IP that the
  // real scans, and the DataDome reputation attached to it, depend on.
  scanning_paused: true,
  // Notifications are off by default, but the Telegram poller is started
  // unconditionally (backend/app/main.py) and would hold a standing connection
  // to api.telegram.org the moment a token appeared in this directory.
  telegram_enabled: false,
  telegram_actions_enabled: false,
  email_enabled: false,
  // Nothing may launch a second browser behind Playwright's back.
  datadome_auto_refresh: false,
  // Invariant 14: the harness binds loopback, so the bind address is the access
  // control here exactly as it is in the product. No token, because the product
  // does not ask for one on loopback and the suite must exercise what ships.
  api_auth_token: "",
};

/** The backend's own interpreter when there is one, so the harness runs the
 *  same dependencies the gates do rather than whatever `python` resolves to. */
function pythonExecutable() {
  const venv =
    process.platform === "win32"
      ? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe")
      : path.join(BACKEND_DIR, ".venv", "bin", "python");
  if (existsSync(venv)) return venv;
  return process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
}

const python = pythonExecutable();

rmSync(dataDir, { recursive: true, force: true });
mkdirSync(dataDir, { recursive: true });
writeFileSync(path.join(dataDir, "settings.json"), `${JSON.stringify(SETTINGS, null, 2)}\n`, "utf-8");

if (process.env.E2E_SEED !== "0") {
  const seeded = spawnSync(python, [path.join("scripts", "seed_demo.py"), "--data-dir", dataDir], {
    cwd: ROOT,
    stdio: "inherit",
  });
  if (seeded.status !== 0) {
    console.error(
      `seeding the demo corpus failed (${python} exited ${seeded.status}). ` +
        "The backend is not started: a suite against an empty database would report " +
        "an empty product as a passing one.",
    );
    process.exit(seeded.status ?? 1);
  }
}

const backend = spawn(python, ["run.py"], {
  cwd: BACKEND_DIR,
  env: {
    ...process.env,
    APP_DATA_DIR: dataDir,
    APP_HOST: "127.0.0.1",
    APP_PORT: port,
    APP_RELOAD: "0",
  },
  stdio: "inherit",
});

// Playwright kills this script when the run ends; on POSIX that signal has to
// reach the interpreter underneath or the port stays held and the next run
// fails to bind.
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => backend.kill(signal));
}
backend.on("exit", (code, signal) => process.exit(signal ? 1 : (code ?? 0)));
