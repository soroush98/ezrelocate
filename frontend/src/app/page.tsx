"use client";

import { useEffect, useState } from "react";
import { AccountBar } from "@/components/AccountBar";
import { ListingsMap } from "@/components/Map";
import { QueryPanel } from "@/components/QueryPanel";
import type {
  AmenityCategory,
  Listing,
  NearbyResponse,
  RecommendationResponse,
} from "@/lib/types";

type MobileView = "list" | "map";

export default function Home() {
  const [listings, setListings] = useState<Listing[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  // What the user asked for in the most recent query — drives which amenity
  // categories we overlay on the map when a listing is selected.
  const [searchedAmenities, setSearchedAmenities] = useState<AmenityCategory[]>([]);
  const [nearbyPois, setNearbyPois] = useState<NearbyResponse["pois"]>([]);
  // Mobile-only: which pane is currently shown. Both panes stay mounted so the
  // map keeps its WebGL context and the list keeps its scroll position.
  const [mobileView, setMobileView] = useState<MobileView>("list");

  // Fetch the actual nearby POIs whenever a listing is selected.
  useEffect(() => {
    if (selectedId == null || searchedAmenities.length === 0) {
      setNearbyPois([]);
      return;
    }
    const ctl = new AbortController();
    const types = searchedAmenities.join(",");
    fetch(`/api/listings/${selectedId}/nearby?types=${types}&radius_m=1200&per_type=4`, {
      signal: ctl.signal,
    })
      .then((r) => (r.ok ? (r.json() as Promise<NearbyResponse>) : Promise.reject(r.status)))
      .then((data) => setNearbyPois(data.pois))
      .catch((e) => {
        if (e?.name !== "AbortError") setNearbyPois([]);
      });
    return () => ctl.abort();
  }, [selectedId, searchedAmenities]);

  function onResult(result: RecommendationResponse | null) {
    if (result == null) {
      setListings([]);
      setSearchedAmenities([]);
    } else {
      setListings(result.listings);
      setSearchedAmenities(result.parsed.near_amenities);
    }
    setSelectedId(null);
    setHoveredId(null);
    setNearbyPois([]);
  }

  // On mobile, tapping a listing card should jump to the map so the user can
  // see where it is. On desktop both panes are visible so we just update state.
  function handleSelect(id: number) {
    setSelectedId((prev) => (prev === id ? null : id));
    if (typeof window !== "undefined" && window.matchMedia("(max-width: 767px)").matches) {
      setMobileView("map");
    }
  }

  return (
    <main className="relative h-dvh w-screen overflow-hidden">
      {/* Sidebar / query panel. Full-width on mobile, fixed 500px on md+. */}
      <div
        className={
          "absolute left-0 top-0 bottom-0 z-10 w-full md:w-[500px] " +
          (mobileView === "list" ? "block" : "hidden md:block")
        }
      >
        <QueryPanel
          onResult={onResult}
          selectedId={selectedId}
          hoveredId={hoveredId}
          onHover={setHoveredId}
          onSelect={handleSelect}
        />
      </div>

      {/* Floating account controls in the top-right corner */}
      <div className="pointer-events-none absolute right-3 top-3 z-40 flex items-center gap-2 sm:right-4 sm:top-4">
        <div className="pointer-events-auto rounded-full bg-white/95 px-2 py-1.5 shadow-md backdrop-blur">
          <AccountBar />
        </div>
      </div>

      {/* Map: fills the right side on md+, fills the screen behind the toggle on mobile. */}
      <div
        className={
          "absolute right-0 top-0 bottom-0 left-0 md:left-[500px] " +
          (mobileView === "map" ? "block" : "hidden md:block")
        }
      >
        <ListingsMap
          listings={listings}
          selectedId={selectedId}
          hoveredId={hoveredId}
          onSelect={(id) => setSelectedId((prev) => (prev === id ? null : id))}
          nearbyPois={nearbyPois}
        />
      </div>

      {/* Mobile-only segmented control to switch between list and map. */}
      <div className="pointer-events-none absolute inset-x-0 bottom-4 z-30 flex justify-center md:hidden">
        <div className="pointer-events-auto flex rounded-full bg-white/95 p-1 shadow-(--shadow-pop) backdrop-blur">
          <ViewToggle
            label="List"
            active={mobileView === "list"}
            onClick={() => setMobileView("list")}
          />
          <ViewToggle
            label={`Map${listings.length > 0 ? ` · ${listings.length}` : ""}`}
            active={mobileView === "map"}
            onClick={() => setMobileView("map")}
          />
        </div>
      </div>
    </main>
  );
}

function ViewToggle({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={
        "rounded-full px-4 py-1.5 text-xs font-medium transition-colors " +
        (active
          ? "bg-ink text-white shadow-sm"
          : "text-ink-2 hover:text-ink")
      }
    >
      {label}
    </button>
  );
}
