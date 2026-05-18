"use client";

import { useEffect, useState } from "react";
import { ListingsMap } from "@/components/Map";
import { QueryPanel } from "@/components/QueryPanel";
import type {
  AmenityCategory,
  Listing,
  NearbyResponse,
  RecommendationResponse,
} from "@/lib/types";

export default function Home() {
  const [listings, setListings] = useState<Listing[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  // What the user asked for in the most recent query — drives which amenity
  // categories we overlay on the map when a listing is selected.
  const [searchedAmenities, setSearchedAmenities] = useState<AmenityCategory[]>([]);
  const [nearbyPois, setNearbyPois] = useState<NearbyResponse["pois"]>([]);

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

  return (
    <main className="relative h-screen w-screen overflow-hidden">
      {/* Sidebar: fixed width, full height */}
      <div className="absolute left-0 top-0 bottom-0 w-[500px]">
        <QueryPanel
          onResult={onResult}
          selectedId={selectedId}
          hoveredId={hoveredId}
          onHover={setHoveredId}
          onSelect={(id) => setSelectedId((prev) => (prev === id ? null : id))}
        />
      </div>
      {/* Map: explicit absolute positioning so its container has a definite size
          when MapLibre measures it. */}
      <div className="absolute left-[500px] right-0 top-0 bottom-0">
        <ListingsMap
          listings={listings}
          selectedId={selectedId}
          hoveredId={hoveredId}
          onSelect={(id) => setSelectedId((prev) => (prev === id ? null : id))}
          nearbyPois={nearbyPois}
        />
      </div>
    </main>
  );
}
