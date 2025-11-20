"""Utilities for handling structured extraction payloads."""

from __future__ import annotations

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from core.confidence import DEFAULT_AI_TIER
from core.schema import canonicalize_profile_payload, coerce_and_fill
from llm.json_repair import repair_profile_payload
from models.need_analysis import NeedAnalysisProfile

logger = logging.getLogger("cognitive_needs.core.extraction")


def _load_required_paths() -> set[str]:
    """Return critical schema paths that must exist after validation."""

    required: set[str] = set(NeedAnalysisProfile.model_fields)
    critical_file = Path(__file__).resolve().parent.parent / "critical_fields.json"
    try:
        with critical_file.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:  # pragma: no cover - defensive fallback
        return required

    critical = payload.get("critical")
    if isinstance(critical, list):
        required.update({str(entry).strip() for entry in critical if str(entry).strip()})
    return required


_REQUIRED_PATHS: set[str] = _load_required_paths()


class InvalidExtractionPayload(ValueError):
    """Raised when a model result cannot be coerced into JSON."""


def _format_error_path(loc: Sequence[Any] | None) -> str:
    """Return a dotted path representation for ``loc``."""

    if not loc:
        return "<root>"
    parts: list[str] = []
    for entry in loc:
        if isinstance(entry, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{entry}]"
            else:
                parts.append(f"[{entry}]")
            continue
        label = str(entry).strip() if entry is not None else ""
        if label == "__root__" or not label:
            label = "<root>"
        parts.append(label)
    return ".".join(parts) or "<root>"


def _collect_validation_issues(errors: Sequence[Mapping[str, Any]] | None) -> list[str]:
    """Return formatted validation messages for ``errors``."""

    issues: list[str] = []
    if not errors:
        return issues
    for error in errors:
        loc = error.get("loc")
        if not isinstance(loc, Sequence):
            continue
        path = _format_error_path(loc)
        message = str(error.get("msg") or error.get("type") or "invalid value")
        issues.append(f"{path}: {message}")
    return issues


def _remove_error_path(target: Any, loc: Sequence[Any]) -> bool:
    """Remove the value at ``loc`` within ``target`` if it exists."""

    if not loc:
        return False
    cursor: Any = target
    for entry in loc[:-1]:
        if isinstance(entry, int):
            if isinstance(cursor, list) and 0 <= entry < len(cursor):
                cursor = cursor[entry]
                continue
            return False
        if isinstance(cursor, MutableMapping) and isinstance(entry, str) and entry in cursor:
            cursor = cursor[entry]
            continue
        return False
    tail = loc[-1]
    if isinstance(tail, int) and isinstance(cursor, list) and 0 <= tail < len(cursor):
        cursor.pop(tail)
        return True
    if isinstance(tail, str) and isinstance(cursor, MutableMapping) and tail in cursor:
        del cursor[tail]
        return True
    return False


def _prune_error_paths(payload: MutableMapping[str, Any], errors: Sequence[Mapping[str, Any]] | None) -> list[str]:
    """Remove invalid fields referenced by ``errors`` and return their paths."""

    removed: list[str] = []
    if not errors:
        return removed
    for error in errors:
        loc = error.get("loc")
        if not isinstance(loc, Sequence):
            continue
        if _remove_error_path(payload, loc):
            removed.append(_format_error_path(loc))
    return removed


def _deduplicate_issues(issues: Iterable[str]) -> list[str]:
    """Return ``issues`` without duplicates while preserving order."""

    ordered: list[str] = []
    seen: set[str] = set()
    for issue in issues:
        candidate = issue.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered


def _collect_present_paths(data: Mapping[str, Any], prefix: str = "") -> set[str]:
    """Return dotted paths for mapping keys present in ``data``."""

    paths: set[str] = set()
    for key, value in data.items():
        if not isinstance(key, str):
            continue
        path = f"{prefix}.{key}" if prefix else key
        paths.add(path)
        if isinstance(value, Mapping):
            paths.update(_collect_present_paths(value, path))
    return paths


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


def _has_meaningful_value(value: Any) -> bool:
    """Return ``True`` if ``value`` contains data worth preserving."""

    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _clean_validated_payload(
    validated: Mapping[str, Any],
    original: Mapping[str, Any],
    *,
    issues: list[str],
    prefix: str = "",
) -> dict[str, Any]:
    """Return ``validated`` data limited to keys provided in ``original``."""

    cleaned: dict[str, Any] = {}
    for key, original_value in original.items():
        if not isinstance(key, str):
            continue
        path = f"{prefix}.{key}" if prefix else key
        validated_value = validated.get(key)
        if isinstance(original_value, Mapping) and isinstance(validated_value, Mapping):
            child = _clean_validated_payload(
                validated_value,
                original_value,
                issues=issues,
                prefix=path,
            )
            if child:
                cleaned[key] = child
            elif _has_meaningful_value(original_value):
                issues.append(f"{path}: removed invalid value")
            continue
        if isinstance(original_value, list):
            if isinstance(validated_value, list) and validated_value:
                cleaned[key] = validated_value
                if validated_value != original_value:
                    issues.append(f"{path}: coerced value")
            elif _has_meaningful_value(original_value):
                issues.append(f"{path}: removed invalid value")
            continue
        if not _has_meaningful_value(validated_value):
            if _has_meaningful_value(original_value):
                issues.append(f"{path}: removed invalid value")
            continue
        cleaned[key] = validated_value
        if validated_value != original_value:
            issues.append(f"{path}: coerced value")
    return cleaned


def parse_structured_payload(raw: str) -> tuple[dict[str, Any], bool, list[str]]:
    """Parse ``raw`` into a dictionary, tolerating surrounding noise."""

    issues: list[str] = []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise InvalidExtractionPayload("Model returned invalid JSON") from exc
        fragment = raw[start : end + 1]
        parsed = json.loads(fragment)
        recovered = True
        issues.append(f"JSON parsing error at line {exc.lineno}, column {exc.colno}: {exc.msg}")
    else:
        recovered = False

    if not isinstance(parsed, dict):
        raise InvalidExtractionPayload("Model returned JSON that is not an object.")

    canonical_payload: dict[str, Any] = canonicalize_profile_payload(parsed)
    validated_model: NeedAnalysisProfile | None = None
    try:
        validated_model = NeedAnalysisProfile.model_validate(canonical_payload)
    except ValidationError as exc:
        errors = exc.errors()
        issues.extend(_collect_validation_issues(errors))
        repaired = repair_profile_payload(canonical_payload, errors=errors)
        if repaired:
            canonical_payload = canonicalize_profile_payload(repaired)
        else:
            removed_paths = _prune_error_paths(canonical_payload, errors)
            if removed_paths:
                logger.warning(
                    "Structured extraction pruned invalid fields: %s",
                    ", ".join(removed_paths),
                )
            for path in removed_paths:
                issues.append(f"{path}: removed invalid value")
        try:
            validated_model = NeedAnalysisProfile.model_validate(canonical_payload)
        except ValidationError as final_error:
            raise InvalidExtractionPayload("Model returned JSON that could not be validated.") from final_error

    if validated_model is None:  # pragma: no cover - defensive guard
        validated_model = NeedAnalysisProfile.model_validate(canonical_payload)

    validated_dump = validated_model.model_dump(mode="python")
    canonical_payload = _clean_validated_payload(
        validated_dump,
        canonical_payload,
        issues=issues,
    )

    try:
        filled_profile = coerce_and_fill(canonical_payload)
    except ValidationError as exc:  # pragma: no cover - defensive
        raise InvalidExtractionPayload("Model returned JSON that could not be normalised.") from exc

    filled_payload = filled_profile.model_dump(mode="python")
    added_paths = _collect_present_paths(filled_payload) - _collect_present_paths(canonical_payload)
    for path in sorted(added_paths):
        if path in _REQUIRED_PATHS:
            issues.append(f"{path}: added missing default")

    return filled_payload, recovered, _deduplicate_issues(issues)


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
