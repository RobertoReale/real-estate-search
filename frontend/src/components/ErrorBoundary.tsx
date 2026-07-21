import { Component, type ErrorInfo, type ReactNode } from "react";
import { translateCurrent } from "../i18n";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/** Last-resort catch for rendering errors: without it React unmounts the
 * whole tree and the user faces a blank page with no hint that reloading
 * would help — indistinguishable from "the app is broken forever". */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled rendering error", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center p-4">
          <div className="glass rounded-2xl p-6 sm:p-10 max-w-lg text-center space-y-4">
            <p className="text-4xl">💥</p>
            {/* a class component has no hooks, so it reads the active
                language through the module-level helper */}
            <p className="font-semibold t-strong">{translateCurrent("error.title")}</p>
            <p className="text-sm t-muted break-words">{this.state.error.message}</p>
            <p className="text-sm t-muted">{translateCurrent("error.dataSafe")}</p>
            <button className="btn-primary" onClick={() => window.location.reload()}>
              {translateCurrent("error.reload")}
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
