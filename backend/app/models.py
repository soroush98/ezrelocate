from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

# Canonical amenity categories. Keep in sync with etl/load_osm_pois.CATEGORIES
# and the frontend lib/types.ts. Used to validate Claude's `near_amenities`.
AmenityCategory = Literal[
    "subway", "lrt", "train", "bus_stop",
    "grocery", "cafe", "pharmacy",
    "park", "school", "university", "library", "gym", "hospital",
]


class ParsedQuery(BaseModel):
    """Structured filters extracted from a user's natural-language rental prompt."""

    # Scope guard — the parser sets these to true when the user's prompt is
    # not a Canadian rental search (off-topic, prompt-injection, abuse, etc.).
    # The route short-circuits and returns rejection_reason without running
    # retrieval or generation.
    out_of_scope: bool = False
    rejection_reason: str = ""

    # Location
    city: str | None = None
    province: str | None = None

    # Rent / size
    max_rent: int | None = None
    min_rent: int | None = None
    min_bedrooms: float | None = None
    max_bedrooms: float | None = None
    min_bathrooms: float | None = None

    # Rental specifics
    property_types: list[str] = Field(default_factory=list)
    furnished: bool | None = None
    pet_friendly: bool | None = None
    utilities_required: list[str] = Field(default_factory=list)
    lease_length_months_max: int | None = None
    available_by: date | None = None

    # Amenity proximity (OSM-backed)
    near_amenities: list[AmenityCategory] = Field(default_factory=list)
    amenity_max_m: int = 800  # default "walkable" radius

    # Soft / fuzzy
    lifestyle_query: str = ""
    commute_target: str | None = None
    commute_max_km: float | None = None


class ListingOut(BaseModel):
    id: int
    source: str
    url: str
    title: str | None
    address: str | None
    city: str
    province: str
    neighborhood: str | None
    lat: float | None
    lng: float | None

    monthly_rent: int | None
    bedrooms: float | None
    bathrooms: float | None
    sqft: int | None
    property_type: str | None
    furnished: bool | None
    pet_friendly: bool | None
    utilities_included: list[str]
    lease_length_months: int | None
    available_from: date | None

    # Map of amenity category -> distance in metres to the nearest one.
    # Missing keys mean nothing of that type within 5km of the listing.
    amenity_distances_m: dict[str, int] = Field(default_factory=dict)

    description: str | None
    score: float


class RecommendationResponse(BaseModel):
    query: str
    parsed: ParsedQuery
    listings: list[ListingOut]
    reasoning: str


class NearbyPOI(BaseModel):
    id: int
    poi_type: AmenityCategory
    name: str | None
    lat: float
    lng: float
    distance_m: int


class NearbyResponse(BaseModel):
    listing_id: int
    pois: list[NearbyPOI]
