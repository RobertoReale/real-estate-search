import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import AuthGate from "./components/AuthGate";
import ErrorBoundary from "./components/ErrorBoundary";
import { ToastProvider } from "./components/Toast";
import { I18nProvider } from "./i18n";
import { createQueryClient } from "./queries/client";
import AppRoutes from "./routes/router";
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
          {/* Inside the boundary, so a rendering crash takes the messages down
              with the screen they were about, and above everything that reports
              a failure — which after this task is everything that writes. */}
          <ToastProvider>
            {/* Inside the gate: until a token is proved there is no dashboard to
                address, and the prompt is the same page whatever URL was asked
                for — which is also what lets a link survive being opened by
                someone who has to sign in first. */}
            <AuthGate>
              <AppRoutes />
            </AuthGate>
          </ToastProvider>
        </ErrorBoundary>
      </QueryClientProvider>
    </I18nProvider>
  </React.StrictMode>
);
