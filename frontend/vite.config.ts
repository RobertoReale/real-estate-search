/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  // `vite preview` serves the production build, which — unlike the packaged app
  // — is not served by the backend, so it needs the same proxy the dev server
  // has. The browser suite starts it against its own backend and says which
  // port that is (playwright.config.ts); a human running `npm run preview` gets
  // the usual 8000.
  preview: {
    proxy: {
      "/api": `http://127.0.0.1:${process.env.E2E_BACKEND_PORT ?? 8000}`,
    },
  },
  test: {
    // jsdom so component tests (@testing-library/react) can render; pure-logic
    // tests like propertyParams don't need it but pay nothing for it.
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    // The 5000 ms default is not enough on a loaded machine: the suite went red
    // on a docs-only commit, failing a different number of tests each run, and
    // passed unchanged once the clock was raised. A test that is genuinely
    // broken fails on its assertion, not on the timer, so a generous budget
    // costs nothing and removes a whole class of false reds — here and on any
    // CI runner sharing its cores.
    testTimeout: 20000,
  },
});
