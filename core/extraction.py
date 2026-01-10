"""Utilities for handling structured extraction payloads."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from core.confidence import DEFAULT_AI_TIER
from core.schema import canonicalize_profile_payload, coerce_and_fill, merge_profile_with_defaults
from llm.json_repair import parse_profile_json, repair_profile_payload
from models.need_analysis import NeedAnalysisProfile
from utils.json_repair import JsonRepairStatus
from ingest.heuristics import extract_responsibilities, refine_requirements

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
_OMISSION_LOG_KEYS: set[str] = set()

_RESPONSIBILITY_PATTERNS: tuple[str, ...] = (
    r"\bresponsibil",
    r"\baufgaben",
    r"\bhauptaufgaben",
    r"\bverantwortung",
    r"what you will do",
    r"was du machst",
    r"your tasks",
)

_REQUIREMENT_PATTERNS: tuple[str, ...] = (
    r"\brequirement",
    r"\bqualifications?",
    r"\banforderungsprofil",
    r"\bvoraussetzungen",
    r"\bprofil",
    r"was du mitbringst",
    r"what you bring",
    r"skills?",
)


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


def _validate_with_repair(
    payload: Mapping[str, Any],
    *,
    issues: list[str],
) -> tuple[dict[str, Any], NeedAnalysisProfile, bool]:
    """Validate ``payload`` and repair it if the schema check fails."""

    used_repair = False
    canonical_payload = canonicalize_profile_payload(payload)
    try:
        validated_model = NeedAnalysisProfile.model_validate(canonical_payload)
    except ValidationError as exc:
        errors = exc.errors()
        issues.extend(_collect_validation_issues(errors))
        repaired = repair_profile_payload(canonical_payload, errors=errors)
        if repaired:
            canonical_payload = canonicalize_profile_payload(repaired)
            used_repair = True
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

    validated_dump = validated_model.model_dump(mode="python")
    cleaned_payload = _clean_validated_payload(
        validated_dump,
        canonical_payload,
        issues=issues,
    )

    return cleaned_payload, validated_model, used_repair


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


def _log_once(key: str, message: str) -> None:
    """Emit ``message`` at warning level only once per process."""

    if key in _OMISSION_LOG_KEYS:
        return
    _OMISSION_LOG_KEYS.add(key)
    logger.warning(message)


def _text_contains_bullets(text: str, *, min_count: int = 3) -> bool:
    """Return ``True`` if ``text`` contains at least ``min_count`` bullet lines."""

    if not text:
        return False
    bullet_count = 0
    for line in text.splitlines():
        if re.match(r"^\s*[-*•·]", line.strip()):
            bullet_count += 1
            if bullet_count >= min_count:
                return True
    return False


def _contains_keywords(text: str, patterns: Sequence[str]) -> bool:
    """Return ``True`` when any regex in ``patterns`` matches ``text``."""

    if not text:
        return False
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _log_schema_omissions(profile: Mapping[str, Any], *, source_text: str | None = None) -> None:
    """Log schema omissions that hint at prompt or model gaps.

    The logging is deduplicated per interpreter session to avoid noisy output
    while still surfacing repeated omission patterns in monitoring.
    """

    company_name = ""
    company = profile.get("company") if isinstance(profile, Mapping) else None
    if isinstance(company, Mapping):
        company_name = str(company.get("name") or "").strip()
        other_company_values = any(key != "name" and _has_meaningful_value(value) for key, value in company.items())
        if not company_name and other_company_values:
            _log_once(
                "company.name_missing",
                "LLM output missing company.name; other company fields present.",
            )

    if not source_text or not source_text.strip():
        return

    source_text_normalized = source_text.strip()
    has_list_signals = _text_contains_bullets(source_text_normalized)

    if isinstance(company, Mapping) and has_list_signals and not company_name:
        # Additional context logged above; no extra message needed.
        pass

    responsibilities = profile.get("responsibilities") if isinstance(profile, Mapping) else None
    if isinstance(responsibilities, Mapping):
        items = responsibilities.get("items")
        if (not isinstance(items, list) or not items) and (
            has_list_signals or _contains_keywords(source_text_normalized, _RESPONSIBILITY_PATTERNS)
        ):
            _log_once(
                "responsibilities.items_empty",
                "LLM output returned empty responsibilities list despite source content.",
            )

    requirements = profile.get("requirements") if isinstance(profile, Mapping) else None
    if isinstance(requirements, Mapping):
        requirement_lists = [
            requirements.get("hard_skills_required"),
            requirements.get("hard_skills_optional"),
            requirements.get("soft_skills_required"),
            requirements.get("soft_skills_optional"),
            requirements.get("tools_and_technologies"),
            requirements.get("languages_required"),
            requirements.get("languages_optional"),
            requirements.get("certificates"),
        ]
        has_requirements = any(isinstance(entry, list) and entry for entry in requirement_lists)
        if (not has_requirements) and (
            has_list_signals or _contains_keywords(source_text_normalized, _REQUIREMENT_PATTERNS)
        ):
            _log_once(
                "requirements.empty",
                "LLM output missing requirement lists while source text shows requirement cues.",
            )


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


def _get_path_value(data: Mapping[str, Any], path: str) -> Any:
    """Return the value located at ``path`` within ``data`` if present."""

    target: Any = data
    for part in path.split("."):
        if not isinstance(target, Mapping):
            return None
        target = target.get(part)
    return target


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


def _apply_heuristic_fallbacks(
    profile: NeedAnalysisProfile,
    *,
    source_text: str | None,
    issues: list[str],
) -> tuple[NeedAnalysisProfile, bool]:
    """Fill missing lists using heuristics when the model output is empty."""

    if not source_text or not source_text.strip():
        return profile, False

    updated = False
    normalized_text = source_text.strip()

    if not (profile.responsibilities.items or []):
        responsibilities = [item.strip() for item in extract_responsibilities(normalized_text) if item.strip()]
        if responsibilities:
            profile.responsibilities.items = responsibilities
            issues.append("responsibilities.items: filled via heuristics")
            updated = True

    requirement_fields = (
        "hard_skills_required",
        "hard_skills_optional",
        "soft_skills_required",
        "soft_skills_optional",
        "tools_and_technologies",
        "languages_required",
        "languages_optional",
        "certificates",
        "certifications",
    )
    has_requirements = any(getattr(profile.requirements, field) for field in requirement_fields)
    if not has_requirements:
        refined_profile = refine_requirements(profile, normalized_text)
        if refined_profile != profile:
            profile = refined_profile
            issues.append("requirements: filled via heuristics")
            updated = True

    return profile, updated


def parse_structured_payload(raw: str, *, source_text: str | None = None) -> tuple[dict[str, Any], bool, list[str]]:
    """Parse ``raw`` into a dictionary, tolerating surrounding noise.

    Args:
        raw: Model response payload to parse.
        source_text: Optional source text used during extraction for omission logging.
    """

    issues: list[str] = []
    repair_result = parse_profile_json(raw)
    issues.extend(repair_result.issues)

    if repair_result.status is JsonRepairStatus.FAILED or repair_result.payload is None:
        raise InvalidExtractionPayload("Model returned invalid JSON")

    parsed = dict(repair_result.payload)
    recovered = repair_result.status is JsonRepairStatus.REPAIRED
    used_repair = recovered

    cleaned_payload, _validated_model, repaired_in_validation = _validate_with_repair(parsed, issues=issues)
    used_repair = used_repair or repaired_in_validation

    try:
        filled_profile = coerce_and_fill(cleaned_payload)
    except ValidationError as exc:  # pragma: no cover - defensive
        raise InvalidExtractionPayload("Model returned JSON that could not be normalised.") from exc

    merged_payload = merge_profile_with_defaults(filled_profile.model_dump(mode="python"))

    heuristic_profile = NeedAnalysisProfile.model_validate(merged_payload)
    heuristic_profile, heuristics_used = _apply_heuristic_fallbacks(
        heuristic_profile,
        source_text=source_text,
        issues=issues,
    )
    if heuristics_used:
        merged_payload = merge_profile_with_defaults(heuristic_profile.model_dump(mode="python"))

    for_missing = [
        path for path in sorted(_REQUIRED_PATHS) if not _has_meaningful_value(_get_path_value(merged_payload, path))
    ]
    if for_missing:
        for path in for_missing:
            issues.append(f"{path}: missing value")
        repaired_missing = repair_profile_payload(
            merged_payload,
            errors=[{"loc": tuple(path.split(".")), "msg": "missing required value"} for path in for_missing],
        )
        if repaired_missing:
            used_repair = True
            try:
                cleaned_payload, _validated_model, repaired_in_validation = _validate_with_repair(
                    repaired_missing, issues=issues
                )
                used_repair = used_repair or repaired_in_validation
                filled_profile = coerce_and_fill(cleaned_payload)
                merged_payload = merge_profile_with_defaults(filled_profile.model_dump(mode="python"))
            except InvalidExtractionPayload as exc:  # pragma: no cover - defensive
                logger.warning("Repaired payload could not be validated: %s", exc)

    added_paths = _collect_present_paths(merged_payload) - _collect_present_paths(cleaned_payload)
    for path in sorted(added_paths):
        if path in _REQUIRED_PATHS:
            issues.append(f"{path}: added missing default")

    _log_schema_omissions(merged_payload, source_text=source_text)

    return merged_payload, recovered or used_repair, _deduplicate_issues(issues)


def mark_low_confidence(
    metadata: MutableMapping[str, Any],
    data: Mapping[str, Any],
    *,
    confidence: float = 0.2,
    issues: Sequence[str] | None = None,
    repaired: bool = True,
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
    recovery_payload = metadata["llm_recovery"] if isinstance(metadata["llm_recovery"], MutableMapping) else {}
    recovery_payload["invalid_json"] = True
    recovery_payload["confidence"] = confidence
    recovery_payload["repaired"] = repaired
    if issues:
        recovery_payload["errors"] = _deduplicate_issues(list(issues))
    metadata["llm_recovery"] = recovery_payload

    logger.warning("Structured extraction returned invalid JSON; coerced result with low confidence.")


__all__ = ["InvalidExtractionPayload", "mark_low_confidence", "parse_structured_payload"]
