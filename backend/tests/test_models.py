"""Unit tests for boundary validation on the parsed-query model."""

import pytest
from pydantic import ValidationError

from app.models import ParsedQuery


def test_valid_amenity_accepted():
    assert ParsedQuery(near_amenities=["subway", "grocery"]).near_amenities == [
        "subway",
        "grocery",
    ]


def test_unknown_amenity_rejected():
    with pytest.raises(ValidationError):
        ParsedQuery(near_amenities=["teleporter"])


def test_defaults_are_safe():
    q = ParsedQuery()
    assert q.out_of_scope is False
    assert q.near_amenities == []
    assert q.amenity_max_m == 800
    # Mutable defaults must not be shared between instances.
    q.near_amenities.append("subway")
    assert ParsedQuery().near_amenities == []
