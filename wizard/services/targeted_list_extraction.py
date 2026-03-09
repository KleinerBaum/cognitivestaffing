"""Targeted second-pass extraction helpers for list-heavy fields."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from typing import Any

from nlp.cue_detection import TARGETED_FIELDS, detect_targeted_cues

MIN_LIST_ENTRY_CHARS = 3
MAX_LIST_ENTRY_CHARS = 120


def build_targeted_list_schema(fields: Sequence[str]) -> dict[str, Any]:
    """Build a minimal schema for targeted list extraction fields."""

    properties: dict[str, Any] = {}
    required: list[str] = []

    def _ensure_group(name: str) -> dict[str, Any]:
        group = properties.get(name)
        if isinstance(group, dict):
            return group
        group = {"type": "object", "properties": {}}
        properties[name] = group
        return group

    for field in fields:
        if field not in TARGETED_FIELDS:
            continue
        top, leaf = field.split(".", 1)
        block = _ensure_group(top)
        nested = block.setdefault("properties", {})
        if isinstance(nested, dict):
            nested[leaf] = {"type": "array", "items": {"type": "string"}}
        if top not in required:
            required.append(top)

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def normalize_list_entries(values: Sequence[str]) -> list[str]:
    """Normalize list-like outputs into concise, deduplicated items."""

    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = re.sub(r"^[\-•\d\)\.(\s]+", "", str(raw or "")).strip()
        item = re.sub(r"\s+", " ", item)
        if len(item) < MIN_LIST_ENTRY_CHARS or len(item) > MAX_LIST_ENTRY_CHARS:
            continue
        if item.count(" ") > 18:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return normalized


def merge_list_entries(existing: Sequence[str], incoming: Sequence[str]) -> list[str]:
    """Keep existing high-quality items and append only missing deduplicated ones."""

    base = normalize_list_entries(existing)
    additions = normalize_list_entries(incoming)
    seen = {entry.casefold() for entry in base}
    merged = list(base)
    for item in additions:
        if item.casefold() not in seen:
            merged.append(item)
            seen.add(item.casefold())
    return merged


def merge_targeted_lists(base: Mapping[str, Any] | None, patch: Mapping[str, Any]) -> dict[str, Any]:
    """Merge targeted list fields without replacing existing quality entries."""

    merged: dict[str, Any] = deepcopy(dict(base)) if isinstance(base, Mapping) else {}
    for path in TARGETED_FIELDS:
        top, leaf = path.split(".", 1)
        patch_values = patch.get(top, {}) if isinstance(patch, Mapping) else {}
        if not isinstance(patch_values, Mapping) or not isinstance(patch_values.get(leaf), Sequence):
            continue
        target = merged.setdefault(top, {})
        if not isinstance(target, dict):
            target = {}
            merged[top] = target
        existing = target.get(leaf)
        existing_values = existing if isinstance(existing, Sequence) and not isinstance(existing, str) else []
        target[leaf] = merge_list_entries(existing_values, patch_values.get(leaf, []))
    return merged


def build_targeted_cue_context(text: str, fields: Iterable[str]) -> str:
    """Build cue-focused context block used by the second extraction pass."""

    cues = detect_targeted_cues(text, fields)
    blocks: list[str] = []
    for field in TARGETED_FIELDS:
        snippets = cues.get(field)
        if not snippets:
            continue
        rendered = "\n".join(f"- {snippet}" for snippet in snippets[:12])
        blocks.append(f"{field}:\n{rendered}")
    return "\n\n".join(blocks)
