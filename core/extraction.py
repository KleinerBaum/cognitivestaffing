"""Utilities for handling structured extraction payloads."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping, MutableMapping
from typing import Any

from core.confidence import DEFAULT_AI_TIER

logger = logging.getLogger("cognitive_needs.core.extraction")


class InvalidExtractionPayload(ValueError):
    """Raised when a model result cannot be coerced into JSON."""


def _iter_paths(data: Mapping[str, Any], prefix: str = "") -> Iterable[str]:
    """Yield dotted field paths for truthy values in ``data``."""

    for key, value in data.items():
        if not isinstance(key, str):
            continue
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping):
            yield from _iter_paths(value, path)
            continue
        if isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, Mapping):
                    yield from _iter_paths(item, f"{path}[{index}]")
            continue
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        yield path


def parse_structured_payload(raw: str) -> tuple[dict[str, Any], bool]:
    """Parse ``raw`` into a dictionary, tolerating surrounding noise."""

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise InvalidExtractionPayload("Model returned invalid JSON")
        fragment = raw[start : end + 1]
        parsed = json.loads(fragment)
        recovered = True
    else:
        recovered = False

    if not isinstance(parsed, dict):
        raise InvalidExtractionPayload("Model returned JSON that is not an object.")

    return parsed, recovered


def mark_low_confidence(
    metadata: MutableMapping[str, Any],
    data: Mapping[str, Any],
    *,
    confidence: float = 0.2,
) -> None:
    """Annotate ``metadata`` to indicate low confidence extraction fields."""

    field_confidence = metadata.setdefault("field_confidence", {})
    if not isinstance(field_confidence, MutableMapping):
        field_confidence = {}
        metadata["field_confidence"] = field_confidence

    for path in _iter_paths(data):
        entry = field_confidence.setdefault(
            path,
            {
                "tier": DEFAULT_AI_TIER.value,
                "source": "llm",
                "score": None,
            },
        )
        entry["confidence"] = confidence
        entry["note"] = "invalid_json_recovery"

    metadata.setdefault("llm_recovery", {})
    if isinstance(metadata["llm_recovery"], MutableMapping):
        metadata["llm_recovery"]["invalid_json"] = True
    else:
        metadata["llm_recovery"] = {"invalid_json": True}

    logger.warning("Structured extraction returned invalid JSON; coerced result with low confidence.")


__all__ = ["InvalidExtractionPayload", "mark_low_confidence", "parse_structured_payload"]
