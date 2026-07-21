import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useMemo, useRef, useState } from "react";
import { formatNumber, translateCurrent, useT, type TranslationKey } from "../i18n";
import { formatPrice } from "../services/api";
import type { GeoFilter, Property } from "../types";

interface Props {
  properties: Property[];
  onSelect: (property: Property) => void;
  /** When set, center the map on this property and open its tooltip instead of
   *  fitting the whole set — the target of a card's "View on map" jump. */
  focusId?: number | null;
  /** Current geographic-zone filter (radius or polygon), owned by App's filter
   *  state; the drawing tools produce changes to it via `onGeoChange`. */
  geo?: GeoFilter;
  onGeoChange?: (next: GeoFilter) => void;
  /** Kick off the batch geocoder ("Find coordinates") so more properties get a
   *  pin — the mitigation for the NULL-coordinate exclusion the banner warns
   *  about. Optional so the component still renders without it. */
  onFindCoordinates?: () => void;
  /** True while a geocode batch is running, to disable the banner button. */
  geocoding?: boolean;
}

type PinKind = "drop" | "favorite" | "filtered" | "gone" | "sold" | "active";

const EMPTY_GEO: GeoFilter = {
  geo_mode: "", center_lat: "", center_lng: "", radius_m: "", poly: "",
};

/** Pin colors follow the same semantics as the card badges, so the map never
 *  says something different from the grid it replaces. Order matters: a
 *  favorited price drop reads as a price drop, the rarer and more actionable
 *  signal. */
const PIN_STYLE: Record<PinKind, { color: string; label: TranslationKey }> = {
  drop: { color: "#059669", label: "map.pinDrop" },
  favorite: { color: "#d97706", label: "map.pinFavorite" },
  filtered: { color: "#e11d48", label: "map.pinFiltered" },
  gone: { color: "#64748b", label: "map.pinGone" },
  sold: { color: "#ca8a04", label: "map.pinSold" },
  active: { color: "#2563eb", label: "map.pinActive" },
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

/** A small draggable square: the radius handle, visually distinct from a
 *  listing pin so it can't be mistaken for one. */
const HANDLE_ICON = L.divIcon({
  className: "",
  iconSize: [16, 16],
  iconAnchor: [8, 8],
  html: `<span style="
    display:block;width:14px;height:14px;
    background:#0ea5e9;border:2px solid #fff;border-radius:3px;
    box-shadow:0 1px 6px rgba(0,0,0,.5);cursor:grab;"></span>`,
});

type DrawMode = "" | "radius" | "polygon";

export default function MapView({
  properties, onSelect, focusId, geo, onGeoChange, onFindCoordinates, geocoding,
}: Props) {
  const t = useT();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  // the committed zone (circle or polygon), rendered from the `geo` prop
  const zoneLayerRef = useRef<L.LayerGroup | null>(null);
  // scratch layer for the shape being drawn, before it is committed
  const drawLayerRef = useRef<L.LayerGroup | null>(null);
  // markers call back into React; keeping the handler in a ref means the
  // marker layer does not need rebuilding whenever the parent re-renders
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const onGeoRef = useRef(onGeoChange);
  onGeoRef.current = onGeoChange;

  const [drawMode, setDrawMode] = useState<DrawMode>("");
  // the map click handler is registered once; it reads the live draw mode and
  // the in-progress vertices through refs so it never goes stale
  const drawModeRef = useRef<DrawMode>("");
  drawModeRef.current = drawMode;
  const polyVertsRef = useRef<L.LatLng[]>([]);
  const radiusCenterRef = useRef<L.LatLng | null>(null);

  const activeGeo = geo ?? EMPTY_GEO;
  const hasZone = activeGeo.geo_mode === "radius" || activeGeo.geo_mode === "polygon";

  const geolocated = useMemo(
    () => properties.filter((p) => p.latitude !== null && p.longitude !== null),
    [properties],
  );
  const missing = properties.length - geolocated.length;

  const commit = (next: GeoFilter) => onGeoRef.current?.(next);

  // --- map instance: created once, destroyed on unmount --------------------
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, { scrollWheelZoom: true, doubleClickZoom: false })
      .setView([41.9, 12.5], 5); // Italy, before any listing is placed
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
    zoneLayerRef.current = L.layerGroup().addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    drawLayerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    const onClick = (e: L.LeafletMouseEvent) => {
      const mode = drawModeRef.current;
      if (mode === "radius") handleRadiusClick(e.latlng);
      else if (mode === "polygon") handlePolyClick(e.latlng);
    };
    const onDblClick = () => {
      if (drawModeRef.current === "polygon") finishPolygon();
    };
    map.on("click", onClick);
    map.on("dblclick", onDblClick);
    return () => {
      map.off("click", onClick);
      map.off("dblclick", onDblClick);
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
      zoneLayerRef.current = null;
      drawLayerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- radius drawing ------------------------------------------------------
  function handleRadiusClick(center: L.LatLng) {
    const map = mapRef.current;
    const draw = drawLayerRef.current;
    if (!map || !draw) return;
    draw.clearLayers();
    radiusCenterRef.current = center;
    // start with a handle offset ~1/4 of the visible span to the east, so it is
    // immediately grabbable without overlapping the centre
    const span = map.getBounds().getEast() - map.getBounds().getWest();
    const handleStart = L.latLng(center.lat, center.lng + Math.max(span / 4, 0.002));
    const circle = L.circle(center, {
      radius: map.distance(center, handleStart),
      color: "#0ea5e9", weight: 2, fillColor: "#0ea5e9", fillOpacity: 0.12,
    }).addTo(draw);
    const handle = L.marker(handleStart, { icon: HANDLE_ICON, draggable: true }).addTo(draw);
    handle.on("drag", () => {
      circle.setRadius(map.distance(center, handle.getLatLng()));
    });
    handle.on("dragend", () => {
      const radius = Math.round(map.distance(center, handle.getLatLng()));
      commit({
        geo_mode: "radius",
        center_lat: center.lat.toFixed(6),
        center_lng: center.lng.toFixed(6),
        radius_m: String(Math.max(radius, 1)),
        poly: "",
      });
      draw.clearLayers();
      setDrawMode("");
    });
  }

  // --- polygon drawing -----------------------------------------------------
  function redrawPolyScratch() {
    const draw = drawLayerRef.current;
    if (!draw) return;
    draw.clearLayers();
    const verts = polyVertsRef.current;
    for (const v of verts) {
      L.circleMarker(v, { radius: 4, color: "#0ea5e9", fillColor: "#0ea5e9", fillOpacity: 1 })
        .addTo(draw);
    }
    if (verts.length >= 2) {
      L.polyline(verts, { color: "#0ea5e9", weight: 2, dashArray: "5,5" }).addTo(draw);
    }
  }

  function handlePolyClick(latlng: L.LatLng) {
    polyVertsRef.current = [...polyVertsRef.current, latlng];
    redrawPolyScratch();
  }

  function finishPolygon() {
    const verts = polyVertsRef.current;
    if (verts.length < 3) return; // a polygon needs at least three vertices
    const poly = verts.map((v) => `${v.lat.toFixed(6)},${v.lng.toFixed(6)}`).join(";");
    commit({ geo_mode: "polygon", center_lat: "", center_lng: "", radius_m: "", poly });
    polyVertsRef.current = [];
    drawLayerRef.current?.clearLayers();
    setDrawMode("");
  }

  function startRadius() {
    cancelDrawing();
    setDrawMode("radius");
  }
  function startPolygon() {
    cancelDrawing();
    setDrawMode("polygon");
  }
  function cancelDrawing() {
    polyVertsRef.current = [];
    radiusCenterRef.current = null;
    drawLayerRef.current?.clearLayers();
    setDrawMode("");
  }
  function clearZone() {
    cancelDrawing();
    commit(EMPTY_GEO);
  }

  // --- render the committed zone from the geo prop -------------------------
  useEffect(() => {
    const zone = zoneLayerRef.current;
    if (!zone) return;
    zone.clearLayers();
    if (activeGeo.geo_mode === "radius") {
      const lat = Number(activeGeo.center_lat);
      const lng = Number(activeGeo.center_lng);
      const r = Number(activeGeo.radius_m);
      if (Number.isFinite(lat) && Number.isFinite(lng) && r > 0) {
        L.circle([lat, lng], {
          radius: r, color: "#0ea5e9", weight: 2, fillColor: "#0ea5e9", fillOpacity: 0.1,
          interactive: false,
        }).addTo(zone);
      }
    } else if (activeGeo.geo_mode === "polygon" && activeGeo.poly) {
      const verts = activeGeo.poly
        .split(";")
        .map((c) => c.split(",").map(Number))
        .filter((p) => p.length === 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]))
        .map(([la, ln]) => [la, ln] as [number, number]);
      if (verts.length >= 3) {
        L.polygon(verts, {
          color: "#0ea5e9", weight: 2, fillColor: "#0ea5e9", fillOpacity: 0.1,
          interactive: false,
        }).addTo(zone);
      }
    }
  }, [activeGeo.geo_mode, activeGeo.center_lat, activeGeo.center_lng, activeGeo.radius_m, activeGeo.poly]);

  // --- markers: rebuilt whenever the filtered set changes ------------------
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();

    let focusMarker: L.Marker | null = null;
    let focusLatLng: L.LatLngExpression | null = null;
    for (const p of geolocated) {
      const marker = L.marker([p.latitude!, p.longitude!], {
        icon: makeIcon(pinKind(p)),
        title: p.title || translateCurrent("card.untitled"),
      });
      const sqmPrice =
        p.current_min_price && p.sqm
          ? translateCurrent("common.sqmPrice", {
              value: formatNumber(Math.round(p.current_min_price / p.sqm)),
            })
          : "";
      marker.bindTooltip(
        `<strong>${formatPrice(p.current_min_price, p.contract)}</strong>` +
          (sqmPrice ? ` · ${sqmPrice}` : "") +
          `<br/>${escapeHtml(p.title || translateCurrent("card.untitled"))}` +
          `<br/><em>${escapeHtml(
            [p.zone, p.city].filter(Boolean).join(", ") ||
              translateCurrent("card.locationUnknown"),
          )}</em>`,
        { direction: "top", offset: [0, -8] },
      );
      marker.on("click", () => onSelectRef.current(p));
      layer.addLayer(marker);
      if (focusId != null && p.id === focusId) {
        focusMarker = marker;
        focusLatLng = [p.latitude!, p.longitude!];
      }
    }

    if (focusMarker && focusLatLng) {
      // "View on map" jump: land on the requested property, close enough to
      // read the street, and flag which pin it is.
      map.setView(focusLatLng, 16);
      focusMarker.openTooltip();
    } else if (hasZone) {
      // A zone is active: keep the user's current view. Re-fitting on every
      // refetch after drawing would yank the zoom away from what they drew.
    } else if (geolocated.length) {
      map.fitBounds(
        L.latLngBounds(geolocated.map((p) => [p.latitude!, p.longitude!])),
        // a single pin would otherwise zoom to street level, which hides
        // the context that makes the map useful in the first place
        { padding: [40, 40], maxZoom: 15 },
      );
    }
    // hasZone intentionally excluded: it must not trigger a marker rebuild, it
    // only gates the fitBounds branch above on the runs the set already drives
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geolocated, focusId]);

  // keep the map's cursor/interaction hint in sync with the draw mode
  useEffect(() => {
    const el = containerRef.current;
    if (el) el.style.cursor = drawMode ? "crosshair" : "";
  }, [drawMode]);

  const legend = (Object.keys(PIN_STYLE) as PinKind[]).filter((kind) =>
    geolocated.some((p) => pinKind(p) === kind),
  );

  return (
    <section className="glass rounded-2xl p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm t-muted">
          {t("map.onMap", { shown: geolocated.length, total: properties.length })}
          {missing > 0 && (
            <span
              className="ml-2 text-xs chip-amber px-2 py-0.5 rounded-lg"
              title={t("map.missingTitle")}>
              {t("map.missing", { count: missing })}
            </span>
          )}
        </p>
        <div className="flex flex-wrap gap-3 text-xs t-muted">
          {legend.map((kind) => (
            <span key={kind} className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full border border-white/70"
                style={{ background: PIN_STYLE[kind].color }} />
              {t(PIN_STYLE[kind].label)}
            </span>
          ))}
        </div>
      </div>

      {/* Drawing toolbar: produces a radius or polygon filter that flows into
          the grid/export like any other filter. */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={drawMode === "radius" ? cancelDrawing : startRadius}
          className={`btn-ghost min-h-11 sm:min-h-0 text-sm ${drawMode === "radius" ? "ring-2 ring-sky-400" : ""}`}
          title={t("map.drawRadiusTitle")}>
          {t(drawMode === "radius" ? "map.drawingRadius" : "map.drawRadius")}
        </button>
        <button
          type="button"
          onClick={drawMode === "polygon" ? finishPolygon : startPolygon}
          className={`btn-ghost min-h-11 sm:min-h-0 text-sm ${drawMode === "polygon" ? "ring-2 ring-sky-400" : ""}`}
          title={t("map.drawAreaTitle")}>
          {t(drawMode === "polygon" ? "map.finishArea" : "map.drawArea")}
        </button>
        {drawMode === "polygon" && (
          <span className="text-xs t-dim">
            {t("map.polyHint", { count: polyVertsRef.current.length })}
          </span>
        )}
        {(hasZone || drawMode) && (
          <button
            type="button"
            onClick={clearZone}
            className="btn-ghost min-h-11 sm:min-h-0 text-sm">
            {t("map.clearZone")}
          </button>
        )}
        {hasZone && (
          <span className="text-xs chip-sky px-2 py-0.5 rounded-lg">
            {activeGeo.geo_mode === "radius"
              ? t("map.radiusActive", {
                  km: (Number(activeGeo.radius_m) / 1000).toFixed(2),
                })
              : t("map.areaActive")}
          </span>
        )}
      </div>

      {/* The mandatory caveat: a geographic filter silently drops every property
          without coordinates. Keep it loud whenever a zone is active. */}
      {hasZone && missing > 0 && (
        <div className="text-xs rounded-lg chip-amber px-3 py-2 flex flex-wrap items-center gap-2">
          <span>
            {t(missing === 1 ? "map.zoneWarningOne" : "map.zoneWarning", { count: missing })}
          </span>
          {onFindCoordinates && (
            <button
              type="button"
              onClick={onFindCoordinates}
              disabled={geocoding}
              className="btn-ghost min-h-8 sm:min-h-0 text-xs underline disabled:opacity-60">
              {t(geocoding ? "map.findingCoordinates" : "map.findCoordinates")}
            </button>
          )}
        </div>
      )}

      {/* dvh keeps the map from resizing (and Leaflet from re-fitting) every
          time a mobile browser collapses or restores its address bar */}
      <div ref={containerRef}
        className="h-[60dvh] min-h-[320px] sm:h-[70dvh] sm:min-h-[420px] rounded-xl overflow-hidden z-0" />

      {geolocated.length === 0 && (
        <p className="text-sm t-muted text-center py-2">{t("map.noneGeolocated")}</p>
      )}
      <p className="text-xs t-dim">{t("map.attribution")}</p>
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
