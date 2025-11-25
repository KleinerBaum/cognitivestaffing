from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping, Sequence

from config import STRICT_JSON


def _assert_responses_schema_valid(schema: Mapping[str, Any], *, path: str = "$") -> None:
    if not isinstance(schema, Mapping):
        return

    if schema.get("type") == "object":
        properties = schema.get("properties")
        if isinstance(properties, Mapping):
            required = schema.get("required")
            if required is not None and set(required) != set(properties):
                missing = sorted(set(properties) - set(required or []))
                extra = sorted(set(required or []) - set(properties))
                raise ValueError(
                    "Responses JSON schema requires 'required' to include all properties at %s (missing=%s, extra=%s)"
                    % (path, ",".join(missing), ",".join(extra))
                )
            for key, value in properties.items():
                if isinstance(value, Mapping):
                    _assert_responses_schema_valid(value, path=f"{path}.{key}")

    items = schema.get("items")
    if isinstance(items, Mapping):
        _assert_responses_schema_valid(items, path=f"{path}[*]")

    for composite_key in ("anyOf", "oneOf", "allOf"):
        options = schema.get(composite_key)
        if isinstance(options, list):
            for index, option in enumerate(options):
                if isinstance(option, Mapping):
                    _assert_responses_schema_valid(option, path=f"{path}.{composite_key}[{index}]")


def sanitize_json_schema_for_responses(schema: Mapping[str, Any]) -> dict[str, Any]:
    from core.schema import ensure_responses_json_schema

    sanitized = ensure_responses_json_schema(schema)
    _assert_responses_schema_valid(sanitized)
    return sanitized


@dataclass(frozen=True)
class SchemaFormatBundle:
    name: str
    schema: dict[str, Any]
    strict: bool | None
    chat_response_format: dict[str, Any]
    responses_format: dict[str, Any]


def build_schema_format_bundle(json_schema_payload: Mapping[str, Any]) -> SchemaFormatBundle:
    if not isinstance(json_schema_payload, Mapping):
        raise TypeError("json_schema payload must be a mapping")

    schema_name_candidate = json_schema_payload.get("name")
    schema_name = str(schema_name_candidate or "").strip()
    if not schema_name:
        raise ValueError("json_schema payload requires a non-empty 'name'.")

    schema_body = json_schema_payload.get("schema")
    if not isinstance(schema_body, Mapping):
        raise ValueError("json_schema payload requires a mapping 'schema'.")

    strict_override = json_schema_payload.get("strict") if "strict" in json_schema_payload else None
    strict_value = STRICT_JSON if strict_override is None else bool(strict_override)

    sanitized_schema = deepcopy(sanitize_json_schema_for_responses(schema_body))

    chat_format: dict[str, Any] = {
        "type": "json_schema",
        "json_schema": {
            "name": schema_name,
            "schema": deepcopy(sanitized_schema),
        },
    }

    responses_format: dict[str, Any] = {
        "type": "json_schema",
        "name": schema_name,
        "schema": deepcopy(sanitized_schema),
        "json_schema": {
            "name": schema_name,
            "schema": deepcopy(sanitized_schema),
        },
    }

    if strict_value:
        responses_format["json_schema"]["strict"] = strict_value
        responses_format["strict"] = strict_value

    return SchemaFormatBundle(
        name=schema_name,
        schema=sanitized_schema,
        strict=strict_value if strict_value else None,
        chat_response_format=chat_format,
        responses_format=responses_format,
    )


@lru_cache(maxsize=None)
def need_analysis_schema(sections: tuple[str, ...] | None = None) -> dict[str, Any]:
    from core.schema import build_need_analysis_responses_schema

    return build_need_analysis_responses_schema(sections=sections)


def build_need_analysis_json_schema_payload(*, sections: Sequence[str] | None = None) -> dict[str, Any]:
    section_tuple = tuple(sections) if sections else None
    return {
        "name": "need_analysis_profile",
        "schema": deepcopy(need_analysis_schema(section_tuple)),
    }


def sanitize_response_format_payload(response_format: Mapping[str, Any]) -> dict[str, Any]:
    cleaned = dict(response_format)
    format_type = str(cleaned.get("type") or "").lower()
    if format_type != "json_schema":
        return cleaned

    json_schema_block = cleaned.get("json_schema") if isinstance(cleaned.get("json_schema"), Mapping) else None
    schema_payload = None
    if isinstance(json_schema_block, Mapping):
        schema_payload = json_schema_block.get("schema") if isinstance(json_schema_block.get("schema"), Mapping) else None
    if schema_payload is None:
        schema_payload = cleaned.get("schema") if isinstance(cleaned.get("schema"), Mapping) else None

    if schema_payload is not None:
        sanitized_schema = sanitize_json_schema_for_responses(schema_payload)
        if json_schema_block is not None:
            json_schema_block = dict(json_schema_block)
            json_schema_block["schema"] = sanitized_schema
            cleaned["json_schema"] = json_schema_block
        cleaned["schema"] = sanitized_schema

    return cleaned


__all__ = [
    "SchemaFormatBundle",
    "build_need_analysis_json_schema_payload",
    "build_schema_format_bundle",
    "need_analysis_schema",
    "sanitize_json_schema_for_responses",
    "sanitize_response_format_payload",
]
