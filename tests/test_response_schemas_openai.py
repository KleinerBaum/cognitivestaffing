from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import pytest

from llm.response_schemas import (
    FOLLOW_UP_QUESTIONS_SCHEMA_NAME,
    NEED_ANALYSIS_PROFILE_SCHEMA_NAME,
    PRE_EXTRACTION_ANALYSIS_SCHEMA_NAME,
    get_response_schema,
)


def _iter_object_nodes(schema: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    if not isinstance(schema, Mapping):
        return []

    if schema.get("type") == "object" and isinstance(schema.get("properties"), Mapping):
        yield schema
        for child in schema["properties"].values():
            if isinstance(child, Mapping):
                yield from _iter_object_nodes(child)

    if isinstance(schema.get("items"), Mapping):
        yield from _iter_object_nodes(schema["items"])

    for composite_key in ("anyOf", "oneOf", "allOf"):
        options = schema.get(composite_key)
        if isinstance(options, list):
            for option in options:
                if isinstance(option, Mapping):
                    yield from _iter_object_nodes(option)


@pytest.mark.parametrize(
    "schema_name",
    [
        NEED_ANALYSIS_PROFILE_SCHEMA_NAME,
        PRE_EXTRACTION_ANALYSIS_SCHEMA_NAME,
        FOLLOW_UP_QUESTIONS_SCHEMA_NAME,
    ],
)
def test_responses_schema_required_matches_properties(schema_name: str) -> None:
    schema = get_response_schema(schema_name)

    for node in _iter_object_nodes(schema):
        properties = node.get("properties")
        if not isinstance(properties, Mapping):
            continue
        required = node.get("required")
        if required is not None:
            assert set(required) == set(properties)


def test_pre_extraction_analysis_schema_includes_missing_fields() -> None:
    schema = get_response_schema(PRE_EXTRACTION_ANALYSIS_SCHEMA_NAME)
    properties = schema.get("properties")

    assert isinstance(properties, Mapping)
    assert "missing_fields" in properties
    required = schema.get("required")
    assert isinstance(required, list)
    assert set(required) == set(properties)
