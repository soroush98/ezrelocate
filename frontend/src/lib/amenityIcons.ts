// Shared amenity icon definitions used by the map and listing cards.
// Each path is a 24×24 viewBox SVG body, currentColor stroke, stroke-width 2.
import type { AmenityCategory } from "./types";

export const AMENITY_COLOR: Record<AmenityCategory, string> = {
  subway:     "#dc2626",
  lrt:        "#ea580c",
  train:      "#991b1b",
  bus_stop:   "#ca8a04",
  grocery:    "#16a34a",
  cafe:       "#92400e",
  pharmacy:   "#0891b2",
  park:       "#65a30d",
  school:     "#2563eb",
  university: "#1e40af",
  library:    "#7c3aed",
  gym:        "#db2777",
  hospital:   "#be185d",
};

export const AMENITY_ICON_PATHS: Record<AmenityCategory, string> = {
  subway:
    '<rect x="5" y="3" width="14" height="14" rx="2"/>' +
    '<path d="M5 13h14"/>' +
    '<circle cx="9" cy="15.5" r="0.8" fill="currentColor" stroke="none"/>' +
    '<circle cx="15" cy="15.5" r="0.8" fill="currentColor" stroke="none"/>' +
    '<path d="M9 17l-2 4M15 17l2 4"/>',
  lrt:
    '<rect x="4" y="5" width="16" height="12" rx="2"/>' +
    '<path d="M4 12h16"/><path d="M8 5V3M16 5V3"/>' +
    '<circle cx="8" cy="15" r="0.8" fill="currentColor" stroke="none"/>' +
    '<circle cx="16" cy="15" r="0.8" fill="currentColor" stroke="none"/>' +
    '<path d="M7 17l-2 4M17 17l2 4"/>',
  train:
    '<path d="M6 4h12a2 2 0 0 1 2 2v10a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V6a2 2 0 0 1 2-2z"/>' +
    '<path d="M4 11h16"/>' +
    '<circle cx="8" cy="15" r="0.8" fill="currentColor" stroke="none"/>' +
    '<circle cx="16" cy="15" r="0.8" fill="currentColor" stroke="none"/>' +
    '<path d="M7 19l-2 3M17 19l2 3"/>',
  bus_stop:
    '<path d="M5 17V6a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v11"/>' +
    '<rect x="5" y="17" width="14" height="3" rx="1"/>' +
    '<path d="M5 11h14"/>' +
    '<circle cx="8" cy="19" r="0.8" fill="currentColor" stroke="none"/>' +
    '<circle cx="16" cy="19" r="0.8" fill="currentColor" stroke="none"/>',
  grocery:
    '<circle cx="9" cy="20" r="1.4"/><circle cx="17" cy="20" r="1.4"/>' +
    '<path d="M3 4h2.5l2.4 11.2a2 2 0 0 0 2 1.6h7.6a2 2 0 0 0 2-1.5L21 8H7"/>',
  cafe:
    '<path d="M4 9h12v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V9z"/>' +
    '<path d="M16 10h2a3 3 0 0 1 0 6h-2"/>' +
    '<path d="M7 3v3M10 3v3M13 3v3"/>',
  pharmacy:
    '<rect x="3" y="3" width="18" height="18" rx="3"/>' +
    '<path d="M12 8v8M8 12h8"/>',
  park:
    '<path d="M12 3 6 12h3.5l-3 5h11l-3-5H18z"/>' +
    '<path d="M12 17v5"/>',
  school:
    '<path d="M2 9l10-5 10 5-10 5L2 9z"/>' +
    '<path d="M6 11v4.5c0 1.5 2.7 3 6 3s6-1.5 6-3V11"/>' +
    '<path d="M20 9v5"/>',
  university:
    '<path d="M3 21h18"/>' +
    '<path d="M5 21V8l7-4 7 4v13"/>' +
    '<path d="M10 21v-6h4v6"/>' +
    '<path d="M9 11h.01M15 11h.01"/>',
  library:
    '<path d="M2 5h7a3 3 0 0 1 3 3v13H5a3 3 0 0 1-3-3V5z"/>' +
    '<path d="M22 5h-7a3 3 0 0 0-3 3v13h7a3 3 0 0 0 3-3V5z"/>',
  gym:
    '<rect x="2" y="9" width="3" height="6" rx="1"/>' +
    '<rect x="19" y="9" width="3" height="6" rx="1"/>' +
    '<rect x="5" y="7" width="3" height="10" rx="1"/>' +
    '<rect x="16" y="7" width="3" height="10" rx="1"/>' +
    '<path d="M8 12h8"/>',
  hospital:
    '<rect x="3" y="5" width="18" height="16" rx="2"/>' +
    '<path d="M12 9v8M8 13h8"/>' +
    '<path d="M9 5V3h6v2"/>',
};

export function amenitySvgString(cat: AmenityCategory, size = 14): string {
  return (
    `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" ` +
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
    'stroke-linejoin="round" aria-hidden="true">' +
    AMENITY_ICON_PATHS[cat] +
    "</svg>"
  );
}
