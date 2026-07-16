import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useMemo, useRef } from "react";
import { formatPrice } from "../services/api";
import type { Property } from "../types";

interface Props {
  properties: Property[];
  onSelect: (property: Property) => void;
}

type PinKind = "drop" | "favorite" | "filtered" | "gone" | "sold" | "active";

/** Pin colors follow the same semantics as the card badges, so the map never
 *  says something different from the grid it replaces. Order matters: a
 *  favorited price drop reads as a price drop, the rarer and more actionable
 *  signal. */
const PIN_STYLE: Record<PinKind, { color: string; label: string }> = {
  drop: { color: "#059669", label: "📉 Price drop" },
  favorite: { color: "#d97706", label: "★ Favorite" },
  filtered: { color: "#e11d48", label: "🚫 Filtered" },
  gone: { color: "#64748b", label: "💨 No longer available" },
  sold: { color: "#ca8a04", label: "🔑 Sold / rented out" },
  active: { color: "#2563eb", label: "Active listing" },
};

function pinKind(p: Property): PinKind {
  const dropped =
    p.first_price && p.current_min_price && p.current_min_price < p.first_price;
  if (dropped) return "drop";
  if (p.is_favorite) return "favorite";
  if (p.status === "filtered") return "filtered";
  if (p.status === "gone") return "gone";
  if (p.status === "sold") return "sold";
  return "active";
}

/** Leaflet's default marker is a PNG resolved relative to the CSS file, which
 *  bundlers rewrite into a 404. A divIcon sidesteps the asset pipeline
 *  entirely and lets the pin carry its own color. */
function makeIcon(kind: PinKind): L.DivIcon {
  const { color } = PIN_STYLE[kind];
  return L.divIcon({
    className: "", // Leaflet's default class draws a white box behind the pin
    iconSize: [18, 18],
    iconAnchor: [9, 9],
    html: `<span style="
      display:block;width:18px;height:18px;border-radius:9999px;
      background:${color};border:2px solid rgba(255,255,255,.9);
      box-shadow:0 1px 6px rgba(0,0,0,.4);"></span>`,
  });
}

export default function MapView({ properties, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  // markers call back into React; keeping the handler in a ref means the
  // marker layer does not need rebuilding whenever the parent re-renders
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  const geolocated = useMemo(
    () => properties.filter((p) => p.latitude !== null && p.longitude !== null),
    [properties],
  );
  const missing = properties.length - geolocated.length;

  // map instance: created once, destroyed on unmount. The cleanup is what
  // makes React 18 StrictMode's double-mount survivable — without it the
  // second mount hits "Map container is already initialized".
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, { scrollWheelZoom: true })
      .setView([41.9, 12.5], 5); // Italy, before any listing is placed
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, []);

  // markers: rebuilt whenever the filtered set changes
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();

    for (const p of geolocated) {
      const marker = L.marker([p.latitude!, p.longitude!], {
        icon: makeIcon(pinKind(p)),
        title: p.title || "Untitled",
      });
      const sqmPrice =
        p.current_min_price && p.sqm
          ? `${Math.round(p.current_min_price / p.sqm).toLocaleString("en-IE")} €/sqm`
          : "";
      marker.bindTooltip(
        `<strong>${formatPrice(p.current_min_price, p.contract)}</strong>` +
          (sqmPrice ? ` · ${sqmPrice}` : "") +
          `<br/>${escapeHtml(p.title || "Untitled")}` +
          `<br/><em>${escapeHtml(
            [p.zone, p.city].filter(Boolean).join(", ") || "Location N/A",
          )}</em>`,
        { direction: "top", offset: [0, -8] },
      );
      marker.on("click", () => onSelectRef.current(p));
      layer.addLayer(marker);
    }

    if (geolocated.length) {
      map.fitBounds(
        L.latLngBounds(geolocated.map((p) => [p.latitude!, p.longitude!])),
        // a single pin would otherwise zoom to street level, which hides
        // the context that makes the map useful in the first place
        { padding: [40, 40], maxZoom: 15 },
      );
    }
  }, [geolocated]);

  const legend = (Object.keys(PIN_STYLE) as PinKind[]).filter((kind) =>
    geolocated.some((p) => pinKind(p) === kind),
  );

  return (
    <section className="glass rounded-2xl p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm t-muted">
          {geolocated.length} of {properties.length} properties on the map
          {missing > 0 && (
            <span
              className="ml-2 text-xs chip-amber px-2 py-0.5 rounded-lg"
              title="Portals do not publish coordinates for every listing; those properties are still in the grid view.">
              {missing} without coordinates
            </span>
          )}
        </p>
        <div className="flex flex-wrap gap-3 text-xs t-muted">
          {legend.map((kind) => (
            <span key={kind} className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full border border-white/70"
                style={{ background: PIN_STYLE[kind].color }} />
              {PIN_STYLE[kind].label}
            </span>
          ))}
        </div>
      </div>

      {/* dvh keeps the map from resizing (and Leaflet from re-fitting) every
          time a mobile browser collapses or restores its address bar */}
      <div ref={containerRef}
        className="h-[60dvh] min-h-[320px] sm:h-[70dvh] sm:min-h-[420px] rounded-xl overflow-hidden z-0" />

      {geolocated.length === 0 && (
        <p className="text-sm t-muted text-center py-2">
          None of the current properties has coordinates yet — run a scan, or
          switch back to the grid view.
        </p>
      )}
      <p className="text-xs t-dim">
        Click a pin to open the property. Map data © OpenStreetMap
        contributors (tiles are fetched online).
      </p>
    </section>
  );
}

/** Tooltips take an HTML string, and listing titles come straight from the
 *  portals: escape before interpolating. */
function escapeHtml(text: string): string {
  const el = document.createElement("div");
  el.textContent = text;
  return el.innerHTML;
}
