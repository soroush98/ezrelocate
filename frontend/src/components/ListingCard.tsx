"use client";

import type { AmenityCategory, Listing } from "@/lib/types";
import { AMENITY_COLOR, amenitySvgString } from "@/lib/amenityIcons";
import {
  BathIcon,
  BedIcon,
  ExternalIcon,
  PawIcon,
  PinIcon,
  RulerIcon,
} from "./Icon";
import { Pill } from "./Pill";

const fmtRent = (n: number | null) =>
  n == null ? "—" : "$" + n.toLocaleString();

const fmtDistance = (m: number) =>
  m < 1000 ? `${m}m` : `${(m / 1000).toFixed(1)}km`;

const AMENITY_LABEL: Record<AmenityCategory, string> = {
  subway: "subway",
  lrt: "LRT",
  train: "train",
  bus_stop: "bus",
  grocery: "grocery",
  cafe: "café",
  pharmacy: "pharmacy",
  park: "park",
  school: "school",
  university: "uni",
  library: "library",
  gym: "gym",
  hospital: "hospital",
};

// Show these 4 categories on the card when present, ranked by distance.
// Other categories are still in the data but kept out of the card for tidiness.
const AMENITY_SHOWLIST: AmenityCategory[] = [
  "subway", "lrt", "train", "bus_stop",
  "grocery", "cafe", "pharmacy",
  "park", "school", "university", "library", "gym", "hospital",
];

function nearestAmenities(
  m: Partial<Record<AmenityCategory, number>>,
  n: number,
): [AmenityCategory, number][] {
  return (AMENITY_SHOWLIST
    .map((c) => [c, m[c]] as const)
    .filter((p): p is [AmenityCategory, number] => p[1] != null)
    .sort((a, b) => a[1] - b[1])
    .slice(0, n)) as [AmenityCategory, number][];
}

type Props = {
  listing: Listing;
  rank: number;
  selected: boolean;
  onHover: (id: number | null) => void;
  onSelect: (id: number) => void;
};

export function ListingCard({ listing, rank, selected, onHover, onSelect }: Props) {
  const isPriceSane = listing.monthly_rent != null && listing.monthly_rent < 20000;

  return (
    <li
      onMouseEnter={() => onHover(listing.id)}
      onMouseLeave={() => onHover(null)}
      onClick={() => onSelect(listing.id)}
      className={
        "group cursor-pointer rounded-xl border bg-card p-3.5 shadow-(--shadow-card) " +
        "transition-all duration-200 hover:-translate-y-0.5 hover:shadow-(--shadow-pop) " +
        (selected
          ? "border-brand-500 ring-2 ring-brand-100"
          : "border-line hover:border-slate-300")
      }
    >
      <div className="flex items-start gap-3">
        <span
          className={
            "mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full font-mono text-[11px] font-semibold " +
            (selected
              ? "bg-ink text-white"
              : "bg-slate-100 text-slate-600 group-hover:bg-brand-100 group-hover:text-brand-700")
          }
        >
          {rank}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="truncate text-[13px] font-semibold text-ink">
                {listing.neighborhood ?? listing.city}
                <span className="font-normal text-ink-muted">
                  {" · "}
                  {listing.city}, {listing.province}
                </span>
              </div>
              <div className="mt-0.5 truncate text-xs text-ink-muted">
                {listing.title ?? listing.address ?? "—"}
              </div>
            </div>
            <div className="text-right shrink-0">
              <div className={
                "font-semibold tracking-tight " +
                (isPriceSane ? "text-ink text-[15px]" : "text-amber-600 text-sm")
              }>
                {fmtRent(listing.monthly_rent)}
              </div>
              <div className="text-[10px] uppercase tracking-wider text-ink-muted">
                /mo
              </div>
            </div>
          </div>

          <div className="mt-2 flex items-center gap-3 text-[11px] text-ink-2">
            <span className="inline-flex items-center gap-1">
              <BedIcon size={13} className="text-ink-muted" />
              {listing.bedrooms == null
                ? "—"
                : listing.bedrooms === 0.5
                  ? "Studio"
                  : `${listing.bedrooms} bd`}
            </span>
            <span className="inline-flex items-center gap-1">
              <BathIcon size={13} className="text-ink-muted" />
              {listing.bathrooms == null ? "—" : `${listing.bathrooms} ba`}
            </span>
            <span className="inline-flex items-center gap-1">
              <RulerIcon size={13} className="text-ink-muted" />
              {listing.sqft == null || listing.sqft === 0 ? "—" : `${listing.sqft} ft²`}
            </span>
            {listing.property_type && (
              <span className="text-ink-muted">· {listing.property_type}</span>
            )}
          </div>

          {(listing.furnished || listing.pet_friendly || listing.utilities_included.length > 0) && (
            <div className="mt-2 flex flex-wrap gap-1">
              {listing.furnished && <Pill variant="warm">Furnished</Pill>}
              {listing.pet_friendly && (
                <Pill variant="brand" icon={<PawIcon size={12} />}>Pets ok</Pill>
              )}
              {listing.utilities_included.length > 0 && (
                <Pill variant="info">incl. {listing.utilities_included.join(" + ")}</Pill>
              )}
            </div>
          )}

          {Object.keys(listing.amenity_distances_m).length > 0 && (
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-ink-2">
              {nearestAmenities(listing.amenity_distances_m, 4).map(([c, m]) => (
                <span key={c} className="inline-flex items-center gap-1">
                  <span
                    style={{ color: AMENITY_COLOR[c] }}
                    dangerouslySetInnerHTML={{ __html: amenitySvgString(c, 12) }}
                  />
                  <span className="text-ink-muted">{AMENITY_LABEL[c]}</span>
                  <span className="font-mono text-ink-2">{fmtDistance(m)}</span>
                </span>
              ))}
            </div>
          )}

          {listing.description && (
            <p className="mt-2.5 line-clamp-2 text-xs leading-relaxed text-ink-2">
              {listing.description}
            </p>
          )}

          <div className="mt-2 flex items-center justify-between text-[10px] text-ink-muted">
            <a
              href={listing.url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1 text-brand-700 hover:text-brand-900 hover:underline"
            >
              View on {listing.source}
              <ExternalIcon size={11} />
            </a>
            <span className="inline-flex items-center gap-1.5">
              <PinIcon size={11} className="text-ink-muted/70" />
              {listing.lat != null ? "Mapped" : "No coords"}
              <span className="text-ink-muted/50">·</span>
              <span className="font-mono">{listing.score.toFixed(3)}</span>
            </span>
          </div>
        </div>
      </div>
    </li>
  );
}
