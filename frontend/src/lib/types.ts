export type AmenityCategory =
  | "subway" | "lrt" | "train" | "bus_stop"
  | "grocery" | "cafe" | "pharmacy"
  | "park" | "school" | "university" | "library" | "gym" | "hospital";

export type ParsedQuery = {
  city: string | null;
  province: string | null;
  max_rent: number | null;
  min_rent: number | null;
  min_bedrooms: number | null;
  max_bedrooms: number | null;
  min_bathrooms: number | null;
  property_types: string[];
  furnished: boolean | null;
  pet_friendly: boolean | null;
  utilities_required: string[];
  lease_length_months_max: number | null;
  available_by: string | null;
  near_amenities: AmenityCategory[];
  amenity_max_m: number;
  lifestyle_query: string;
  commute_target: string | null;
  commute_max_km: number | null;
};

export type Listing = {
  id: number;
  source: string;
  url: string;
  title: string | null;
  address: string | null;
  city: string;
  province: string;
  neighborhood: string | null;
  lat: number | null;
  lng: number | null;
  monthly_rent: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  sqft: number | null;
  property_type: string | null;
  furnished: boolean | null;
  pet_friendly: boolean | null;
  utilities_included: string[];
  lease_length_months: number | null;
  available_from: string | null;
  amenity_distances_m: Partial<Record<AmenityCategory, number>>;
  description: string | null;
  score: number;
};

export type RecommendationResponse = {
  query: string;
  parsed: ParsedQuery;
  listings: Listing[];
  reasoning: string;
};

export type NearbyPOI = {
  id: number;
  poi_type: AmenityCategory;
  name: string | null;
  lat: number;
  lng: number;
  distance_m: number;
};

export type NearbyResponse = {
  listing_id: number;
  pois: NearbyPOI[];
};
