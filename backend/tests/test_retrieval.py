"""Unit tests for the SQL builder — the security-critical, network-free core."""

import pytest

from app.models import ParsedQuery
from app.services.retrieval import TOP_K, _as_dict, _build_candidate_sql


def build(parsed, embed=None, commute=None):
    return _build_candidate_sql(parsed, embed, commute)


def test_empty_query_has_only_base_clauses():
    sql, args = build(ParsedQuery())
    assert "l.status = 'active'" in sql
    assert "l.desc_embed IS NOT NULL" in sql
    assert args == []
    # No lifestyle embed → score is the constant 0.0, not a vector distance.
    assert "0.0" in sql
    assert "<=>" not in sql
    assert f"LIMIT {TOP_K}" in sql


@pytest.mark.parametrize(
    "parsed, expected_arg, fragment",
    [
        (ParsedQuery(city="Toronto"), "Toronto", "l.city ILIKE"),
        (ParsedQuery(max_rent=2500), 2500, "l.monthly_rent <= $1"),
        (ParsedQuery(min_rent=1000), 1000, "l.monthly_rent >= $1"),
        (ParsedQuery(min_bedrooms=2), 2, "l.bedrooms >= $1"),
        (ParsedQuery(max_bedrooms=3), 3, "l.bedrooms <= $1"),
        (ParsedQuery(min_bathrooms=1.5), 1.5, "l.bathrooms >= $1"),
        (ParsedQuery(furnished=True), True, "l.furnished = $1"),
        (ParsedQuery(pet_friendly=True), True, "l.pet_friendly = $1"),
        (ParsedQuery(property_types=["condo"]), ["condo"], "l.property_type = ANY($1)"),
        (
            ParsedQuery(utilities_required=["heat"]),
            ["heat"],
            "l.utilities_included @> $1",
        ),
    ],
)
def test_single_filter_maps_to_clause_and_arg(parsed, expected_arg, fragment):
    sql, args = build(parsed)
    assert fragment in sql
    assert expected_arg in args


def test_province_is_uppercased():
    _, args = build(ParsedQuery(province="on"))
    assert "ON" in args


def test_placeholders_are_numbered_in_order():
    sql, args = build(ParsedQuery(city="Toronto", max_rent=2500, min_bedrooms=1))
    assert args == ["Toronto", 2500, 1]
    assert "$1" in sql and "$2" in sql and "$3" in sql


@pytest.mark.parametrize(
    "requested, clamped",
    # 0 is falsy → treated as "unspecified" and falls back to the 800m default.
    [(10, 50), (800, 800), (99999, 5000), (0, 800)],
)
def test_amenity_radius_is_clamped(requested, clamped):
    sql, _ = build(ParsedQuery(near_amenities=["subway"], amenity_max_m=requested))
    assert f"<= {clamped}" in sql


def test_injected_amenity_is_dropped_not_interpolated():
    # Defense-in-depth: bypass pydantic validation to smuggle a non-whitelisted
    # amenity straight into the builder. It must be silently skipped, never
    # interpolated into the SQL string.
    evil = "subway'; DROP TABLE listings;--"
    parsed = ParsedQuery.model_construct(near_amenities=["subway", evil], amenity_max_m=800)
    sql, _ = build(parsed)
    assert "DROP TABLE" not in sql
    assert "amenity_distances_m ? 'subway'" in sql


def test_lifestyle_embed_uses_vector_distance():
    embed = [0.1, 0.2, 0.3]
    sql, args = build(ParsedQuery(lifestyle_query="quiet leafy street"), embed=embed)
    assert "<=>" in sql
    # The embedding is passed as a bind arg formatted as a pgvector literal.
    assert args[-1] == "[0.100000,0.200000,0.300000]"


def test_commute_filter_adds_radius_clause():
    parsed = ParsedQuery(commute_target="UBC", commute_max_km=2)
    sql, args = build(parsed, commute="POINT(-123 49)")
    assert "ST_DWithin" in sql
    assert "POINT(-123 49)" in args
    assert 2000.0 in args  # km → metres


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, {}),
        ({"subway": 320}, {"subway": 320}),
        ('{"subway": 320}', {"subway": 320}),
    ],
)
def test_as_dict_normalises_jsonb(value, expected):
    assert _as_dict(value) == expected
