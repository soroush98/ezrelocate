"use client";

import maplibregl, { type StyleSpecification } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import type { AmenityCategory, Listing, NearbyPOI } from "@/lib/types";
import { AMENITY_COLOR, amenitySvgString } from "@/lib/amenityIcons";

const AMENITY_LABEL: Record<AmenityCategory, string> = {
  subway: "Subway", lrt: "LRT", train: "Train", bus_stop: "Bus",
  grocery: "Grocery", cafe: "Café", pharmacy: "Pharmacy",
  park: "Park", school: "School", university: "University",
  library: "Library", gym: "Gym", hospital: "Hospital",
};

const fmtMeters = (m: number) =>
  m < 1000 ? `${m}m` : `${(m / 1000).toFixed(1)}km`;

// POI names come from scraped OSM data, so escape them before they go into the
// popup's setHTML — a name containing markup must never become live HTML.
const HTML_ESCAPES: Record<string, string> = {
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
};
const escapeHtml = (s: string) =>
  s.replace(/[&<>"']/g, (c) => HTML_ESCAPES[c] ?? c);

const CANADA_CENTER: [number, number] = [-93.0, 49.2];

// Carto Voyager is light + colourful enough to make pins pop, no API key.
const STYLE: StyleSpecification = {
  version: 8,
  sources: {
    carto: {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png",
        "https://b.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png",
        "https://c.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png",
        "https://d.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png",
      ],
      tileSize: 256,
      attribution:
        '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, © <a href="https://carto.com/attributions">CARTO</a>',
    },
  },
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#f1f5f9" } },
    { id: "carto", type: "raster", source: "carto" },
  ],
};

type Props = {
  listings: Listing[];
  selectedId: number | null;
  hoveredId: number | null;
  onSelect: (id: number) => void;
  nearbyPois: NearbyPOI[];
};

export function ListingsMap({
  listings,
  selectedId,
  hoveredId,
  onSelect,
  nearbyPois = [],
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<Map<number, { marker: maplibregl.Marker; el: HTMLElement }>>(
    new Map(),
  );
  const amenityMarkersRef = useRef<maplibregl.Marker[]>([]);
  const [initError, setInitError] = useState<string | null>(null);

  // Map init
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const el = containerRef.current;
    if (!hasWebGL()) {
      setInitError("WEBGL_UNAVAILABLE");
      return;
    }
    try {
      const m = new maplibregl.Map({
        container: el,
        style: STYLE,
        center: CANADA_CENTER,
        zoom: 3.5,
      });
      m.on("error", (e) => console.error("[Map] runtime:", e?.error ?? e));
      m.on("load", () => {
        m.resize();
        requestAnimationFrame(() => m.resize());
      });
      m.addControl(
        new maplibregl.NavigationControl({ showCompass: false }),
        "top-right",
      );
      mapRef.current = m;

      // Keep the canvas in sync with the container after layout settles.
      const ro = new ResizeObserver(() => mapRef.current?.resize());
      ro.observe(el);

      return () => {
        ro.disconnect();
        mapRef.current?.remove();
        mapRef.current = null;
      };
    } catch (e) {
      console.error("[Map] init threw:", e);
      setInitError(e instanceof Error ? `${e.name}: ${e.message}` : String(e));
    }
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  function hasWebGL(): boolean {
    if (typeof window === "undefined") return false;
    try {
      const c = document.createElement("canvas");
      return !!(c.getContext("webgl2") || c.getContext("webgl"));
    } catch {
      return false;
    }
  }

  // Rebuild markers whenever the listing set changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Clear old
    markersRef.current.forEach(({ marker }) => marker.remove());
    markersRef.current.clear();

    const geolocated = listings.filter(
      (l): l is Listing & { lat: number; lng: number } =>
        l.lat != null && l.lng != null,
    );
    if (geolocated.length === 0) {
      map.flyTo({ center: CANADA_CENTER, zoom: 3.5, duration: 600 });
      return;
    }

    const bounds = new maplibregl.LngLatBounds();
    geolocated.forEach((l, i) => {
      const el = document.createElement("div");
      el.className = "rl-pin";
      el.textContent = String(i + 1);
      el.setAttribute("data-listing-id", String(l.id));
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        onSelect(l.id);
      });
      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([l.lng, l.lat])
        .addTo(map);
      markersRef.current.set(l.id, { marker, el });
      bounds.extend([l.lng, l.lat]);
    });

    map.fitBounds(bounds, { padding: 90, maxZoom: 13, duration: 700 });
  }, [listings, onSelect]);

  // Render / update amenity overlay pins
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    amenityMarkersRef.current.forEach((m) => m.remove());
    amenityMarkersRef.current = [];

    for (const p of nearbyPois) {
      const el = document.createElement("div");
      el.className = "rl-amenity-pin";
      el.style.setProperty("--amenity-color", AMENITY_COLOR[p.poi_type]);
      el.title = `${AMENITY_LABEL[p.poi_type]} · ${fmtMeters(p.distance_m)}`;
      el.innerHTML = amenitySvgString(p.poi_type);
      const marker = new maplibregl.Marker({ element: el, anchor: "center" })
        .setLngLat([p.lng, p.lat])
        .setPopup(
          new maplibregl.Popup({ offset: 12, closeButton: false }).setHTML(
            `<div class="text-xs"><strong>${
              p.name ? escapeHtml(p.name) : AMENITY_LABEL[p.poi_type]
            }</strong><br/>` +
              `<span style="color:${AMENITY_COLOR[p.poi_type]}">${
                AMENITY_LABEL[p.poi_type]
              }</span> · ${fmtMeters(p.distance_m)}</div>`,
          ),
        )
        .addTo(map);
      amenityMarkersRef.current.push(marker);
    }
  }, [nearbyPois]);

  // Reflect selected/hovered state on existing pins
  useEffect(() => {
    markersRef.current.forEach(({ el }, id) => {
      el.classList.toggle("is-active", id === selectedId);
      el.classList.toggle("is-hover", id === hoveredId && id !== selectedId);
    });
    if (selectedId != null) {
      const found = listings.find((l) => l.id === selectedId);
      if (found && found.lat != null && found.lng != null) {
        mapRef.current?.flyTo({
          center: [found.lng, found.lat],
          zoom: Math.max(mapRef.current.getZoom(), 12),
          duration: 600,
          essential: true,
        });
      }
    }
  }, [selectedId, hoveredId, listings]);

  // Legend: which amenity categories are currently shown on the map
  const legendCats = Array.from(new Set(nearbyPois.map((p) => p.poi_type)));

  return (
    <div
      className="bg-slate-200"
      style={{ position: "absolute", inset: 0 }}
    >
      <div
        ref={containerRef}
        style={{ position: "absolute", inset: 0 }}
      />
      {initError === "WEBGL_UNAVAILABLE" && (
        <div className="absolute inset-4 grid place-items-center">
          <div className="max-w-md rounded-xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-900 shadow-(--shadow-card)">
            <div className="mb-1 font-semibold">Map needs WebGL</div>
            <p className="text-xs leading-relaxed text-amber-800">
              Your browser has WebGL disabled, so the map can&apos;t render.
              In Chrome: <span className="font-mono">chrome://settings/system</span>
              → enable <em>Use hardware acceleration</em> → fully quit and
              reopen Chrome. Or use Safari, which has WebGL on by default.
            </p>
          </div>
        </div>
      )}
      {initError && initError !== "WEBGL_UNAVAILABLE" && (
        <div className="absolute inset-x-0 top-4 mx-auto w-max max-w-[90%] rounded-md bg-rose-50 px-3 py-2 text-xs text-rose-800 shadow-(--shadow-card)">
          Map failed to initialise: <span className="font-mono">{initError}</span>
        </div>
      )}
      {listings.length === 0 && !initError && (
        <div className="pointer-events-none absolute inset-x-0 top-20 mx-auto w-max max-w-[80%] rounded-full bg-white/85 px-3 py-1 text-center text-xs text-ink-muted shadow-(--shadow-card) backdrop-blur md:top-6">
          Search to see rentals on the map
        </div>
      )}
      {legendCats.length > 0 && (
        <div className="absolute bottom-20 left-3 right-3 rounded-lg bg-white/95 px-3 py-2 text-[11px] shadow-(--shadow-pop) backdrop-blur md:bottom-4 md:left-4 md:right-auto">
          <div className="mb-1 font-medium text-ink-muted">Nearby (around #{
            (() => {
              const idx = listings.findIndex((l) => l.id === selectedId);
              return idx >= 0 ? idx + 1 : "selected";
            })()
          })</div>
          <div className="flex flex-wrap gap-x-3 gap-y-1.5">
            {legendCats.map((c) => (
              <span key={c} className="inline-flex items-center gap-1.5 text-ink-2">
                <span
                  className="grid h-5 w-5 place-items-center rounded-full bg-white"
                  style={{
                    color: AMENITY_COLOR[c],
                    boxShadow: `inset 0 0 0 1.5px ${AMENITY_COLOR[c]}`,
                  }}
                  dangerouslySetInnerHTML={{ __html: amenitySvgString(c, 11) }}
                />
                {AMENITY_LABEL[c]}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
