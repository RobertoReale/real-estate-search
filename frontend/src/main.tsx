import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import AuthGate from "./components/AuthGate";
import ErrorBoundary from "./components/ErrorBoundary";
import { I18nProvider } from "./i18n";
import { createQueryClient } from "./queries/client";
import "./index.css";

// One client for the process. Built here rather than at module scope in
// `client.ts` so a test can hand its own to a component tree without inheriting
// this one's cache.
const queryClient = createQueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {/* Outermost so even the error boundary and the auth prompt speak the
        user's language — they render before the app itself exists. */}
    <I18nProvider>
      {/* Above the boundary and the gate: the prompt proves a token by asking
          the backend, and it does that through the same client as everything
          else so the answer is not fetched twice. */}
      <QueryClientProvider client={queryClient}>
        <ErrorBoundary>
          <AuthGate>
            <App />
          </AuthGate>
        </ErrorBoundary>
      </QueryClientProvider>
    </I18nProvider>
  </React.StrictMode>
);
