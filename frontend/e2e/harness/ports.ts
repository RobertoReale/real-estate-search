/** The two ports the browser suite runs on, and nothing else in this project does.
 *
 *  Deliberately not 8000 and 5173. Those belong to the developer flow
 *  (`scripts/windows/start.bat`, `dev.bat`), and a suite that seized either
 *  would at best fail against a running instance and at worst drive the real
 *  `backend/case.db` — the one file in this repository that cannot be
 *  regenerated. The harness gets its own addresses so the two can never be the
 *  same thing by accident.
 */
export const BACKEND_PORT = 8137;
export const PREVIEW_PORT = 4137;

/** A second backend on an empty data directory, for the one journey that cannot
 *  be told from the seeded one: a first run, before any search exists. The
 *  onboarding screen is what a new user meets, so it is asserted against a
 *  database that is genuinely empty rather than against a stubbed response —
 *  `emptyBackend()` in e2e/harness/empty.ts is how a spec reaches it. */
export const EMPTY_BACKEND_PORT = 8138;

export const BACKEND_ORIGIN = `http://127.0.0.1:${BACKEND_PORT}`;
export const PREVIEW_ORIGIN = `http://127.0.0.1:${PREVIEW_PORT}`;
export const EMPTY_BACKEND_ORIGIN = `http://127.0.0.1:${EMPTY_BACKEND_PORT}`;
