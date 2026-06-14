"""Unit tests for the network-free LLM helpers."""

import pytest

from app.services.llm import _strip_code_fence


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('{"a": 1}', '{"a": 1}'),
        ('  {"a": 1}  ', '{"a": 1}'),
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ('```\n{"a": 1}\n```', '{"a": 1}'),
        ('```JSON\n{"a": 1}```', '{"a": 1}'),
    ],
)
def test_strip_code_fence(raw, expected):
    assert _strip_code_fence(raw) == expected
