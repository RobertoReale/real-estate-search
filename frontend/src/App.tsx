import { useCallback, useEffect, useRef, useState } from "react";
import EmailImport from "./components/EmailImport";
import FiltersBar from "./components/FiltersBar";
import MapView from "./components/MapView";
import MarketVelocityPanel from "./components/MarketVelocity";
import Navbar from "./components/Navbar";
import PropertyCard from "./components/PropertyCard";
import PropertyModal from "./components/PropertyModal";
import SearchProfiles from "./components/SearchProfiles";
import SettingsModal from "./components/SettingsModal";
import { api } from "./services/api";
import type {
  Property, PropertyFilters, ScanStatus, SearchProfile, Settings, ViewMode,
} from "./types";

const DEFAULT_FILTERS: PropertyFilters = {
  status: "active", contract: "sale", city: "", min_price: "", max_price: "",
  min_sqm: "", rooms: "", only_price_drops: false, only_favorites: false,
  sort: "newest",
};

export default function App() {
  const [properties, setProperties] = useState<Property[]>([]);
  const [profiles, setProfiles] = useState<SearchProfile[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null);
  const [filters, setFilters] = useState<PropertyFilters>(DEFAULT_FILTERS);
  const [view, setView] = useState<ViewMode>("grid");
  const [selected, setSelected] = useState<Property | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  // monotonic id per refresh: typing in a filter fires overlapping requests,
  // and without this guard a slow older response would land after the newer
  // one and overwrite the grid with stale results
  const refreshSeq = useRef(0);

  const refresh = useCallback(async () => {
    const seq = ++refreshSeq.current;
    try {
      const [props, profs, status, sett] = await Promise.all([
        api.getProperties(filters),
        api.getProfiles(),
        api.getScanStatus(),
        api.getSettings(),
      ]);
      if (seq !== refreshSeq.current) return; // a newer refresh superseded this one
      setProperties(props);
      setProfiles(profs);
      setScanStatus(status);
      setSettings(sett);
      setLoadError("");
      // keep the open modal in sync with fresh data (e.g. after saving
      // notes or toggling favorite); if the property left the current
      // filter set, keep showing the stale copy until the user closes it
      setSelected((prev) =>
        prev ? props.find((p) => p.id === prev.id) ?? prev : prev
      );
    } catch (e) {
      if (seq !== refreshSeq.current) return;
      setLoadError(
        "Backend unreachable on http://localhost:8000 — start it with start.bat"
      );
    }
  }, [filters]);

  // small debounce: `refresh` changes on every keystroke in the City/price
  // filters, and firing four API calls per letter typed is pure waste
  useEffect(() => {
    const t = window.setTimeout(refresh, 250);
    return () => window.clearTimeout(t);
  }, [refresh]);

  // polling: frequent during scan, slow otherwise
  useEffect(() => {
    const ms = scanStatus?.running ? 4000 : 30000;
    const t = window.setInterval(refresh, ms);
    return () => window.clearInterval(t);
  }, [refresh, scanStatus?.running]);

  // a failed click must say so: without this wrapper the rejection is
  // unhandled and the button silently does nothing, which reads as "broken"
  async function runAction(fn: () => Promise<void>) {
    try {
      setActionError("");
      await fn();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Action failed");
    }
  }

  function scanNow() {
    return runAction(async () => {
      await api.triggerScan();
      setScanStatus((s) => (s ? { ...s, running: true } : s));
      setTimeout(refresh, 1500);
    });
  }

  function quickHide(p: Property) {
    // same confirm() used by the modal's "Hide property" action: hiding is
    // irreversible on its own (only a manual "Restore" brings it back), so
    // both entry points must ask the same way
    if (!confirm("Hide this property? It will never appear in lists or notifications again.")) {
      return;
    }
    return runAction(async () => {
      await api.deleteProperty(p.id);
      setProperties((list) => list.filter((x) => x.id !== p.id));
      if (selected?.id === p.id) setSelected(null);
    });
  }

  function toggleFavorite(p: Property) {
    return runAction(async () => {
      const updated = await api.updateProperty(p.id, { is_favorite: !p.is_favorite });
      setProperties((list) => list.map((x) => (x.id === p.id ? updated : x)));
      setSelected((prev) => (prev?.id === p.id ? updated : prev));
    });
  }

  const hasProfiles = profiles.length > 0;

  return (
    <div className="min-h-screen">
      <Navbar
        scanStatus={scanStatus}
        onScanNow={scanNow}
        onOpenSettings={() => setShowSettings(true)}
      />

      <main className="max-w-7xl mx-auto p-3 sm:p-6 space-y-4 sm:space-y-6">
        {loadError && (
          <div className="glass rounded-2xl p-4 border-rose-500/50 text-rose-600 dark:text-rose-300 text-sm">
            ⚠️ {loadError}
          </div>
        )}
        {actionError && (
          <div className="glass rounded-2xl p-4 border-rose-500/50 text-rose-600 dark:text-rose-300 text-sm flex items-center justify-between gap-3">
            <span>⚠️ {actionError}</span>
            <button className="btn-ghost shrink-0" aria-label="Dismiss error"
              onClick={() => setActionError("")}>✕</button>
          </div>
        )}

        <SearchProfiles profiles={profiles} settings={settings} onChanged={refresh} />

        <EmailImport profiles={profiles} settings={settings} onChanged={refresh} />

        {hasProfiles && (
          <MarketVelocityPanel contract={filters.contract} city={filters.city} />
        )}

        <FiltersBar filters={filters} onChange={setFilters} count={properties.length}
          view={view} onViewChange={setView} />

        {properties.length === 0 && !loadError && (
          <div className="glass rounded-2xl p-6 sm:p-10 text-center t-muted">
            <p className="text-4xl mb-3">🏘️</p>
            <p className="font-medium t-strong">
              {hasProfiles
                ? "No properties match the current filters."
                : "Welcome! Three steps to get started:"}
            </p>
            {!hasProfiles && (
              <ol className="mt-4 text-sm text-left max-w-md mx-auto space-y-2">
                <li className="flex gap-3">
                  <span className="shrink-0 w-6 h-6 rounded-full chip-blue text-xs flex items-center justify-center font-bold">1</span>
                  <span>
                    Add a search above — describe it in words with "💬 Just
                    describe it", build one with "🧭 Build a search", or paste a
                    results URL from Immobiliare.it / Idealista.{" "}
                    <strong>Tip:</strong> to use every portal filter (bathrooms,
                    floor, elevator, energy class, exclude auctions…), set them
                    on the portal and use "🔗 Paste a URL" — the app monitors
                    exactly that search.
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="shrink-0 w-6 h-6 rounded-full chip-blue text-xs flex items-center justify-center font-bold">2</span>
                  Press "▶ Start Scan Now" — the first scan builds your
                  baseline (no notification flood).
                </li>
                <li className="flex gap-3">
                  <span className="shrink-0 w-6 h-6 rounded-full chip-blue text-xs flex items-center justify-center font-bold">3</span>
                  Optional: open ⚙️ Settings to enable Telegram or Email
                  alerts for new listings and price drops.
                </li>
              </ol>
            )}
            {hasProfiles && (
              <p className="text-sm mt-1">
                Try switching the Buy/Rent toggle or relaxing the filters.
              </p>
            )}
          </div>
        )}

        {view === "map" ? (
          properties.length > 0 && (
            <MapView properties={properties} onSelect={setSelected} />
          )
        ) : (
          <div className="grid gap-4 sm:gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {properties.map((p) => (
              <PropertyCard
                key={p.id}
                property={p}
                onClick={() => setSelected(p)}
                onQuickHide={() => quickHide(p)}
                onToggleFavorite={() => toggleFavorite(p)}
              />
            ))}
          </div>
        )}
      </main>

      {selected && (
        <PropertyModal
          property={selected}
          onClose={() => setSelected(null)}
          onDeleted={() => {
            setSelected(null);
            refresh();
          }}
          onToggleFavorite={() => toggleFavorite(selected)}
          onNotesSaved={(updated) => {
            setProperties((list) =>
              list.map((x) => (x.id === updated.id ? updated : x))
            );
            setSelected(updated);
          }}
        />
      )}
      {showSettings && (
        <SettingsModal
          onClose={() => {
            setShowSettings(false);
            refresh(); // channel warnings depend on the freshly saved settings
          }}
        />
      )}
    </div>
  );
}
