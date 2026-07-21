import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import AuthGate from "./components/AuthGate";
import ErrorBoundary from "./components/ErrorBoundary";
import { I18nProvider } from "./i18n";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {/* Outermost so even the error boundary and the auth prompt speak the
        user's language — they render before the app itself exists. */}
    <I18nProvider>
      <ErrorBoundary>
        <AuthGate>
          <App />
        </AuthGate>
      </ErrorBoundary>
    </I18nProvider>
  </React.StrictMode>
);
