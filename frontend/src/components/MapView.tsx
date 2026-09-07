import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useMemo, useRef, useState } from "react";
import { formatNumber, translateCurrent, useT, type TranslationKey } from "../i18n";
import { formatPrice } from "../services/api";
import type { GeoFilter, Property } from "../types";
import { Button, Card, Chip } from "../ui";
import { Close, DrawnArea } from "../ui/icons";
import { clusterByGrid } from "../utils/cluster";

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
  /** The property under the pointer in the list beside the map: its pin grows
   *  and opens its tooltip, so pointing at a card says where it is. */
  hoverId?: number | null;
  /** The other direction: a pin under the pointer reports itself, and `null`
   *  when the pointer leaves it, so the list can mark the matching card. */
  onHover?: (id: number | null) => void;
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

/** True when the backend placed this property in the middle of its district
 *  because nobody could resolve its actual address. Which sources count as
 *  approximate is the backend's list (`geocoder.APPROXIMATE_SOURCES`); this only
 *  reads the answer it sent. */
function isApproximate(p: Property): boolean {
  return p.coordinate_source === "zone";
}

/** Leaflet's default marker is a PNG resolved relative to the CSS file, which
 *  bundlers rewrite into a 404. A divIcon sidesteps the asset pipeline
 *  entirely and lets the pin carry its own color.
 *
 *  An approximate pin is drawn hollow and dashed, at the same size and colour:
 *  it still reads as that property's status, and it no longer claims to be
 *  standing on its doorstep. Presenting an area as an address is the one error
 *  the user has no way of catching, so the difference is in the shape and not
 *  only in the tooltip. */
function makeIcon(kind: PinKind, approximate: boolean): L.DivIcon {
  const { color } = PIN_STYLE[kind];
  const fill = approximate
    ? `background:transparent;border:2px dashed ${color};`
    : `background:${color};border:2px solid rgba(255,255,255,.9);`;
  return L.divIcon({
    className: "", // Leaflet's default class draws a white box behind the pin
    iconSize: [18, 18],
    iconAnchor: [9, 9],
    html: `<span style="
      display:block;width:18px;height:18px;border-radius:9999px;
      ${fill}
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

/** Above this many pins the map stops drawing them one by one and groups the
 *  ones that overlap. Below it every listing keeps its own pin, which is what a
 *  normal search looks like — the grouping is for the saved search that matches
 *  a whole city, where a thousand 18-pixel dots are a single blue shape. */
const CLUSTER_FROM = 300;
/** How close is "on top of each other", in screen pixels at the current zoom.
 *  Three pin-widths: close enough that separate dots were already touching. */
const CLUSTER_CELL_PX = 54;

/** A group of pins, drawn as one circle carrying how many it stands for. It
 *  grows with the count so a big group reads before its number does, and it is
 *  deliberately not any of the six pin colours: a group has no single status. */
function makeClusterIcon(count: number): L.DivIcon {
  const size = count < 10 ? 34 : count < 100 ? 42 : 50;
  return L.divIcon({
    className: "",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    html: `<span style="
      display:flex;align-items:center;justify-content:center;
      width:${size}px;height:${size}px;border-radius:9999px;
      background:rgba(15,23,42,.86);border:2px solid rgba(255,255,255,.9);
      color:#fff;font:600 ${count < 100 ? 13 : 12}px/1 system-ui,sans-serif;
      box-shadow:0 1px 8px rgba(0,0,0,.45);cursor:pointer;"
      >${formatNumber(count)}</span>`,
  });
}

type DrawMode = "" | "radius" | "polygon";

export default function MapView({
  properties, onSelect, focusId, geo, onGeoChange, onFindCoordinates, geocoding,
  hoverId, onHover,
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
  const onHoverRef = useRef(onHover);
  onHoverRef.current = onHover;
  // the pin for each placed property, by id, so the hover coming from the list
  // can find one without walking the layer. Rebuilt with the markers; a
  // property swallowed by a group is simply absent from it.
  const markersRef = useRef(new Map<number, L.Marker>());
  // which pin currently wears the highlight, so it can be taken off again
  const hotRef = useRef<number | null>(null);

  const [drawMode, setDrawMode] = useState<DrawMode>("");
  // the map click handler is registered once; it reads the live draw mode and
  // the in-progress vertices through refs so it never goes stale
  const drawModeRef = useRef<DrawMode>("");
  drawModeRef.current = drawMode;
  const polyVertsRef = useRef<L.LatLng[]>([]);
  // The vertex count is mirrored in state, not read off the ref during render:
  // a click only mutates the ref and repaints Leaflet's scratch layer, so
  // nothing re-rendered React and the "N points added" hint sat at 0 for the
  // whole drawing — the one feedback saying the clicks were registering.
  const [polyCount, setPolyCount] = useState(0);
  const radiusCenterRef = useRef<L.LatLng | null>(null);

  const activeGeo = geo ?? EMPTY_GEO;
  const hasZone = activeGeo.geo_mode === "radius" || activeGeo.geo_mode === "polygon";

  const geolocated = useMemo(
    () => properties.filter((p) => p.latitude !== null && p.longitude !== null),
    [properties],
  );
  const missing = properties.length - geolocated.length;
  // Grouping is a property of the set, not a setting: it turns itself on when
  // there are more pins than the eye can separate, and off again when a filter
  // brings the number back down.
  const clustering = geolocated.length > CLUSTER_FROM;
  // The zoom the pins were last laid out at. Only read while grouping, because
  // only then does the layout depend on it — see the markers effect.
  const [zoom, setZoom] = useState(5);

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
    // Grouping is measured in screen pixels, so it is only correct for the zoom
    // it was computed at: a new zoom is a new layout, and this is what asks for
    // one. `zoomend` and not `zoom`, or the groups would re-form sixty times
    // during a single wheel gesture.
    const onZoomEnd = () => setZoom(map.getZoom());
    map.on("click", onClick);
    map.on("dblclick", onDblClick);
    map.on("zoomend", onZoomEnd);
    return () => {
      map.off("click", onClick);
      map.off("dblclick", onDblClick);
      map.off("zoomend", onZoomEnd);
      map.remove();
      markersRef.current.clear();
      hotRef.current = null;
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
    setPolyCount(polyVertsRef.current.length);
    redrawPolyScratch();
  }

  function finishPolygon() {
    const verts = polyVertsRef.current;
    if (verts.length < 3) return; // a polygon needs at least three vertices
    const poly = verts.map((v) => `${v.lat.toFixed(6)},${v.lng.toFixed(6)}`).join(";");
    commit({ geo_mode: "polygon", center_lat: "", center_lng: "", radius_m: "", poly });
    polyVertsRef.current = [];
    setPolyCount(0);
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
    setPolyCount(0);
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
    markersRef.current.clear();

    // One list, two shapes: grouped into cells of the current zoom's pixel
    // plane above the threshold, and one single-member group per listing below
    // it, so the loop that follows does not care which of the two it got.
    const placed = geolocated.map((p) => ({ lat: p.latitude!, lng: p.longitude!, p }));
    const groups = clustering
      ? clusterByGrid(placed, (lat, lng) => map.project([lat, lng], map.getZoom()), CLUSTER_CELL_PX)
      : placed.map((it) => ({ lat: it.lat, lng: it.lng, items: [it] }));

    for (const group of groups) {
      if (group.items.length > 1) {
        addCluster(map, layer, group);
        continue;
      }
      const { p } = group.items[0];
      const approximate = isApproximate(p);
      const marker = L.marker([p.latitude!, p.longitude!], {
        icon: makeIcon(pinKind(p), approximate),
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
          )}</em>` +
          // said in words as well as in the shape: someone reading a single
          // tooltip has no other pin to compare the dashes against
          (approximate
            ? `<br/><small data-limit="map.zoneCentroid">${escapeHtml(
                translateCurrent("map.approximateZone"),
              )}</small>`
            : ""),
        { direction: "top", offset: [0, -8] },
      );
      marker.on("click", () => onSelectRef.current(p));
      // The map half of the two-way hover. Leaflet opens the tooltip by itself;
      // what this adds is telling the list which card to mark.
      marker.on("mouseover", () => onHoverRef.current?.(p.id));
      marker.on("mouseout", () => onHoverRef.current?.(null));
      layer.addLayer(marker);
      markersRef.current.set(p.id, marker);
    }

    const focused = focusId != null ? geolocated.find((p) => p.id === focusId) : undefined;
    if (focused) {
      // "View on map" jump: land on the requested property, close enough to
      // read the street, and flag which pin it is. Zoom 16 is also past any
      // grouping, so by the time this runs again the pin exists on its own.
      map.setView([focused.latitude!, focused.longitude!], 16);
      markersRef.current.get(focused.id)?.openTooltip();
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
    // only gates the fitBounds branch above on the runs the set already drives.
    // The zoom is a dependency only while grouping, because only then does the
    // layout depend on it — otherwise every wheel click would rebuild every pin
    // to produce exactly the same map.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geolocated, focusId, clustering, clustering ? zoom : 0]);

  /** Draws one group of overlapping pins as a single numbered circle, and makes
   *  clicking it the way back to the individual listings: fit the group and the
   *  next layout splits it. Pins stacked on the exact same coordinate have no
   *  extent to fit, so those step the zoom in instead — otherwise `fitBounds`
   *  on a point jumps straight to the maximum and the group never opens. */
  function addCluster(
    map: L.Map,
    layer: L.LayerGroup,
    group: { lat: number; lng: number; items: { lat: number; lng: number }[] },
  ) {
    const count = group.items.length;
    const label = translateCurrent("map.cluster", { count: formatNumber(count) });
    const marker = L.marker([group.lat, group.lng], {
      icon: makeClusterIcon(count),
      title: label,
    });
    marker.bindTooltip(escapeHtml(label), { direction: "top", offset: [0, -12] });
    marker.on("click", () => {
      const bounds = L.latLngBounds(
        group.items.map((it) => [it.lat, it.lng] as [number, number]),
      );
      if (bounds.getNorthEast().equals(bounds.getSouthWest())) {
        map.setView(bounds.getCenter(), Math.min(map.getZoom() + 2, 19));
      } else {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 18 });
      }
    });
    layer.addLayer(marker);
  }

  // --- the pin the list is pointing at -------------------------------------
  // A class and a stacking offset, never a new icon: `setIcon` replaces the
  // marker's element, and replacing the element under the pointer is read as
  // the pointer leaving it — which fired `mouseout`, cleared the hover, put the
  // icon back, and started again, sixty times a second.
  useEffect(() => {
    const markers = markersRef.current;
    const previous = hotRef.current;
    if (previous != null && previous !== hoverId) {
      const was = markers.get(previous);
      was?.getElement()?.classList.remove("is-hovered");
      was?.setZIndexOffset(0);
      // the "View on map" pin keeps its tooltip: it was opened to answer a
      // question the user asked, not by the pointer passing over it
      if (previous !== focusId) was?.closeTooltip();
    }
    hotRef.current = hoverId ?? null;
    if (hoverId == null) return;
    const marker = markers.get(hoverId);
    if (!marker) return; // inside a group, or without coordinates at all
    marker.getElement()?.classList.add("is-hovered");
    marker.setZIndexOffset(1000);
    marker.openTooltip();
    // geolocated/zoom/clustering: the markers effect above runs first on those
    // and hands this one a fresh set of pins to re-apply the highlight to
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hoverId, focusId, geolocated, clustering, clustering ? zoom : 0]);

  // keep the map's cursor/interaction hint in sync with the draw mode
  useEffect(() => {
    const el = containerRef.current;
    if (el) el.style.cursor = drawMode ? "crosshair" : "";
  }, [drawMode]);

  const legend = (Object.keys(PIN_STYLE) as PinKind[]).filter((kind) =>
    geolocated.some((p) => pinKind(p) === kind),
  );
  // The dashed pin needs a stated meaning, and only while one is on screen: a
  // legend entry for a shape nobody can see is noise.
  const approximateCount = geolocated.filter(isApproximate).length;

  return (
    <Card asChild padding="md">
      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm t-muted">
            {t("map.onMap", { shown: geolocated.length, total: properties.length })}
            {missing > 0 && (
              <span title={t("map.missingTitle")}>
                <Chip tone="caution" className="ml-2">
                  {t("map.missing", { count: missing })}
                </Chip>
              </span>
            )}
            {clustering && (
              <span title={t("map.clusteredTitle")}>
                <Chip tone="info" className="ml-2">{t("map.clustered")}</Chip>
              </span>
            )}
          </p>
          <div className="flex flex-wrap gap-3 text-xs t-muted">
            {legend.map((kind) => (
              <span key={kind} className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full border border-hairline"
                  style={{ background: PIN_STYLE[kind].color }} />
                {t(PIN_STYLE[kind].label)}
              </span>
            ))}
            {approximateCount > 0 && (
              <span className="flex items-center gap-1.5" data-limit="map.zoneCentroid"
                title={t("map.pinApproximateTitle")}>
                <span className="w-3 h-3 rounded-full border border-dashed border-current" />
                {t("map.pinApproximate", { count: approximateCount })}
              </span>
            )}
          </div>
        </div>

        {/* Drawing toolbar: produces a radius or polygon filter that flows into
            the grid/export like any other filter. */}
        <div className="flex flex-wrap items-center gap-2">
          <Button data-action="map.drawRadius"
            onClick={drawMode === "radius" ? cancelDrawing : startRadius}
            className={drawMode === "radius" ? "ring-2 ring-info-marker" : undefined}
            title={t("map.drawRadiusTitle")}>
            {t(drawMode === "radius" ? "map.drawingRadius" : "map.drawRadius")}
          </Button>
          <Button data-action="map.drawArea"
            onClick={drawMode === "polygon" ? finishPolygon : startPolygon}
            className={drawMode === "polygon" ? "ring-2 ring-info-marker" : undefined}
            title={t("map.drawAreaTitle")}>
            <DrawnArea /> {t(drawMode === "polygon" ? "map.finishArea" : "map.drawArea")}
          </Button>
          {/* At rest the two buttons are labels without a job description. This
              is the one line that says what drawing is for, and it steps aside
              the moment there is a zone or a shape in progress to talk about. */}
          {!drawMode && !hasZone && (
            <span className="text-xs t-dim">{t("map.drawHint")}</span>
          )}
          {(hasZone || drawMode) && (
            <Button data-action="map.clearZone" onClick={clearZone}>
              <Close /> {t("map.clearZone")}
            </Button>
          )}
          {hasZone && (
            <Chip tone="info">
              {activeGeo.geo_mode === "radius"
                ? t("map.radiusActive", {
                    km: (Number(activeGeo.radius_m) / 1000).toFixed(2),
                  })
                : t("map.areaActive")}
            </Chip>
          )}
        </div>

        {/* Drawing is two or three steps and none of them is a button press, so
            the steps are written down while they are being taken. Above the map
            and never over it: an overlay would sit on the tiles the next click
            has to land on, and cover Leaflet's own zoom control and attribution
            with it. */}
        {drawMode && (
          <div role="status"
            className="text-xs rounded-lg chip-info px-3 py-2 space-y-1">
            <p className="font-semibold">
              {t(drawMode === "radius" ? "map.guideRadiusTitle" : "map.guideAreaTitle")}
            </p>
            <ol className="list-decimal ms-4 space-y-0.5">
              <li>{t(drawMode === "radius" ? "map.guideRadiusStep1" : "map.guideAreaStep1")}</li>
              <li>{t(drawMode === "radius" ? "map.guideRadiusStep2" : "map.guideAreaStep2")}</li>
            </ol>
            {drawMode === "polygon" && (
              <p className="font-semibold">{t("map.polyHint", { count: polyCount })}</p>
            )}
          </div>
        )}

        {/* The mandatory caveat: a geographic filter silently drops every property
            without coordinates. Keep it loud whenever a zone is active. */}
        {hasZone && missing > 0 && (
          <div className="text-xs rounded-lg chip-caution px-3 py-2 flex flex-wrap items-center gap-2">
            <span>
              {t(missing === 1 ? "map.zoneWarningOne" : "map.zoneWarning", { count: missing })}
            </span>
            {onFindCoordinates && (
              <Button data-action="map.findCoordinates"
                size="sm"
                onClick={onFindCoordinates}
                disabled={geocoding}
                className="underline">
                {t(geocoding ? "map.findingCoordinates" : "map.findCoordinates")}
              </Button>
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
    </Card>
  );
}

/** Tooltips take an HTML string, and listing titles come straight from the
 *  portals: escape before interpolating. */
function escapeHtml(text: string): string {
  const el = document.createElement("div");
  el.textContent = text;
  return el.innerHTML;
}
