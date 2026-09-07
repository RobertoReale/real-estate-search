/**
 * Puts the shipped dashboard in front of Lighthouse, and nothing else on this
 * machine.
 *
 * This is the browser suite's server, reused rather than rewritten: the same
 * script (../e2e/harness/serve-backend.mjs), the same throwaway data directory
 * under frontend/.e2e-data/, the same deterministic demo corpus, the same
 * settings with scanning, notifications and the cookie harvester off. What
 * differs is only which port it answers on and that nothing seeds a second one.
 *
 * The backend serves the built frontend itself (the StaticFiles mount at the
 * bottom of backend/app/main.py — invariant 13), so what Lighthouse measures is
 * one origin serving exactly the artefact a user runs: no dev server, no
 * preview proxy, no second hop that would make the numbers describe a
 * configuration nobody has.
 *
 * The port is read from the run's own config rather than written here as well —
 * Lighthouse has to be pointed at the same address this listens on, and two
 * copies of a port number are one edit away from a run that waits two minutes
 * for a server that started somewhere else. It is deliberately none of the
 * three the browser suite uses (see ../e2e/harness/ports.ts) and none of the
 * developer flow's: a harness that seized 8000 would drive the real case.db.
 *
 * Started and stopped by @lhci/cli, which waits for the line printed at the
 * bottom before it opens a browser. That line is printed by this script, after
 * the backend has answered a real route — not matched out of uvicorn's own
 * logging, which would be a promise about a message rather than about a server.
 */
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, "..");

const config = JSON.parse(readFileSync(path.join(HERE, "lighthouserc.json"), "utf-8"));
const origin = new URL(config.ci.collect.url[0]);

/** Wiped and re-seeded here on every run, exactly as the browser suite's is.
 *  Beside it, under the one path .gitignore already covers. */
const DATA_DIR = path.join(FRONTEND, ".e2e-data", "lighthouse");

const backend = spawn(
  process.execPath,
  [path.join(FRONTEND, "e2e", "harness", "serve-backend.mjs")],
  {
    env: { ...process.env, E2E_BACKEND_PORT: origin.port, E2E_DATA_DIR: DATA_DIR },
    stdio: "inherit",
  },
);

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => backend.kill(signal));
}
backend.on("exit", (code, signal) => process.exit(signal ? 1 : (code ?? 0)));

/** Answers only once the app's lifespan has run, so the first navigation cannot
 *  land on a half-open database. The same route the browser suite waits on. */
const HEALTH = new URL("/api/scrapers/status", origin);

for (let attempt = 0; attempt < 120; attempt += 1) {
  try {
    const answer = await fetch(HEALTH);
    if (answer.ok) {
      // The pattern @lhci/cli is watching for. Anything it prints before this
      // is the seeding, which it is welcome to but must not act on.
      console.log("LIGHTHOUSE_SERVER_READY");
      break;
    }
  } catch {
    // not up yet; the loop is the wait
  }
  await new Promise((resume) => setTimeout(resume, 1000));
}
