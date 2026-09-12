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

import {
  BACKEND_ORIGIN,
  BACKEND_PORT,
  EMPTY_BACKEND_ORIGIN,
  EMPTY_BACKEND_PORT,
  PREVIEW_ORIGIN,
  PREVIEW_PORT,
} from "./e2e/harness/ports";

const HERE = path.dirname(fileURLToPath(import.meta.url));

/** Wiped and re-seeded on every run, so the suite starts from known rows.
 *  Nothing in either is real and nothing in either is kept; both are gitignored.
 *  `empty` is never seeded: a first run is a state the app cannot be returned to
 *  once a search exists, so the onboarding journey gets its own database rather
 *  than a stubbed answer. */
const DATA_DIR = path.join(HERE, ".e2e-data", "seeded");
const EMPTY_DATA_DIR = path.join(HERE, ".e2e-data", "empty");

export default defineConfig({
  testDir: "./e2e",
  // One worker, one backend, one database. Journeys that favourite, hide or
  // delete would otherwise race each other through shared rows, and a suite
  // that fails only when the machine is fast is worse than no suite.
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  // Well above what a journey needs: the per-screen invariants re-measure and
  // re-scan the page at three widths (e2e/harness/invariants.ts), and an axe
  // pass over a full grid is seconds rather than milliseconds. The default 30s
  // would fail a slow machine as if the app were broken.
  timeout: 180_000,
  reporter: [["list"], ["html", { open: "never" }]],
  // The action recorder appends to a directory the coverage gate reads back;
  // last run's files would credit this one with what it never fired.
  globalSetup: "./e2e/harness/global-setup.ts",

  use: {
    baseURL: PREVIEW_ORIGIN,
    // Pinned, and deliberately *not* the language the suite reads. The
    // dashboard no longer asks the browser what it prefers — it opens in
    // Italian unless a choice was stored (src/i18n/index.tsx) — so every
    // assertion below being in Italian on an en-US browser is the proof of
    // that, on the machine the default exists for: one shipped in English,
    // whose owner has never opened the language menu.
    locale: "en-US",
    timezoneId: "Europe/Rome",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },

  // A pixel diff is never bit-for-bit even on the same machine twice — font
  // hinting and anti-aliasing shift by a handful of pixels along a glyph's
  // edge run to run. Loose enough to absorb that, tight enough that a shifted
  // card or a missing icon still fails: the two have never landed in the same
  // range on this app.
  expect: {
    toHaveScreenshot: { maxDiffPixelRatio: 0.01 },
  },

  // Chromium only. A second engine doubles the run and the flakes to cover
  // rendering differences this app has never had; the browser bugs worth
  // catching here are ours.
  //
  // `channel: "chromium"` on the two functional projects, and it is not a
  // preference: without it `headless` runs the separate chrome-headless-shell
  // binary, which intermittently fails to exit when the worker closes it
  // (microsoft/playwright#39753). The worker then blocks in its own teardown,
  // the runner force-kills it after five minutes and reports a fatal
  // `processError` (microsoft/playwright#40637) — which is what a full green
  // run of the journeys looked like on 2026-09-12: 51 passed, the coverage
  // project never started, the gate red on a docs-only commit. The channel
  // runs the real Chromium build in its new headless mode instead, so the
  // binary the hang is reported against is not in the suite's path at all.
  //
  // Two projects rather than one, and the split is load-bearing: A.5's second
  // gate fails on any inventoried control the run never fired, so it has to be
  // the last thing that happens. `dependencies` is what says so — the journeys
  // run first, the coverage spec runs after them, and it reads what all of them
  // recorded rather than only its own.
  projects: [
    {
      name: "journeys",
      testIgnore: [/coverage\.spec\.ts/, /visual\.spec\.ts/],
      use: { ...devices["Desktop Chrome"], channel: "chromium" },
    },
    {
      name: "coverage",
      testMatch: /coverage\.spec\.ts/,
      dependencies: ["journeys"],
      use: { ...devices["Desktop Chrome"], channel: "chromium" },
    },
    // Pixel diffs are not a functional gate: they belong to their own run so a
    // font-rendering shift never blocks the coverage gate above from finishing,
    // and so a run of the suite that only wants behaviour never pays for them.
    // Picked up only by `npm run e2e:visual`, never by `npm run e2e`.
    //
    // Left on the default headless shell on purpose: the baselines in
    // e2e/visual.spec.ts-snapshots were rendered by it, and a browser swap
    // under a pixel comparison invalidates every one of them. The hang above
    // costs this project a red run at worst — it gates nothing after itself.
    {
      name: "visual",
      testMatch: /visual\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
  ],

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
      // The same script with the seeding step switched off. It answers on its
      // own port and its own data directory, so the seeded corpus is never at
      // risk from the journey that asserts there is nothing to show.
      command: "node e2e/harness/serve-backend.mjs",
      url: `${EMPTY_BACKEND_ORIGIN}/api/scrapers/status`,
      env: {
        E2E_BACKEND_PORT: String(EMPTY_BACKEND_PORT),
        E2E_DATA_DIR: EMPTY_DATA_DIR,
        E2E_SEED: "0",
      },
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
