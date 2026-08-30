/** The browser suite's configuration: what it runs against, and what it may touch.
 *
 *  Thirteen unit test files can tell you a component renders. None of them can
 *  tell you the page scrolls sideways on a phone, that a filter reaches the
 *  backend, or that a button does what its label says. That is what this is
 *  for, and the whole value of it rests on the run being reproducible — so the
 *  suite brings its own backend, its own database and its own data, and is
 *  allowed to reach nothing beyond them.
 *
 *  Two servers are started for it, in order (see e2e/harness/serve-backend.mjs
 *  for the first, and `preview` in vite.config.ts for how the second finds it):
 *
 *    1. the backend, on a throwaway data directory holding the demo corpus;
 *    2. `vite preview` over the production build, proxying /api to that backend.
 *
 *  The build is what makes this worth running: the dev server is not the
 *  artefact users get, and the differences between them — asset paths, minified
 *  identifiers, the absence of the dev overlay — are exactly where a bug hides
 *  from `npm run dev`. `npm run e2e` builds first for that reason.
 */
import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { BACKEND_ORIGIN, BACKEND_PORT, PREVIEW_ORIGIN, PREVIEW_PORT } from "./e2e/harness/ports";

const HERE = path.dirname(fileURLToPath(import.meta.url));

/** Wiped and re-seeded on every run, so the suite starts from known rows.
 *  Nothing in it is real and nothing in it is kept; it is gitignored. */
const DATA_DIR = path.join(HERE, ".e2e-data");

export default defineConfig({
  testDir: "./e2e",
  // One worker, one backend, one database. Journeys that favourite, hide or
  // delete would otherwise race each other through shared rows, and a suite
  // that fails only when the machine is fast is worse than no suite.
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],

  use: {
    baseURL: PREVIEW_ORIGIN,
    // Pinned, not inherited: the dashboard picks its language from the browser
    // (src/i18n/index.tsx), so an unset locale would make the assertions depend
    // on the machine running them.
    locale: "en-US",
    timezoneId: "Europe/Rome",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },

  // Chromium only. A second engine doubles the run and the flakes to cover
  // rendering differences this app has never had; the browser bugs worth
  // catching here are ours.
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],

  webServer: [
    {
      command: "node e2e/harness/serve-backend.mjs",
      // A real route rather than the docs page: it answers only once the app's
      // lifespan has run, so the first test cannot start against a half-open
      // database.
      url: `${BACKEND_ORIGIN}/api/scrapers/status`,
      env: { E2E_BACKEND_PORT: String(BACKEND_PORT), E2E_DATA_DIR: DATA_DIR },
      // Never reuse: a server already on this port is not one this file
      // configured, and adopting it would put the suite against an unknown
      // database.
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      // `--host 127.0.0.1` explicitly: left to itself vite preview binds the
      // name "localhost", which on Windows resolves to ::1 first, and the suite
      // then waits two minutes for an address nothing is listening on.
      command: `npx vite preview --host 127.0.0.1 --port ${PREVIEW_PORT} --strictPort`,
      url: PREVIEW_ORIGIN,
      env: { E2E_BACKEND_PORT: String(BACKEND_PORT) },
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: "pipe",
      stderr: "pipe",
    },
  ],
});
