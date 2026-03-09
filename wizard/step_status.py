"""Helpers for computing wizard step completion status."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from wizard.metadata import field_belongs_to_page
from wizard.field_metadata import get_field_metadata
from wizard.missing_fields import get_path_value, missing_fields
from wizard.services.gaps import load_critical_fields
from wizard_pages.base import WizardPage


logger = logging.getLogger(__name__)

HIGH_CONFIDENCE_THRESHOLD = 0.75
MEDIUM_CONFIDENCE_THRESHOLD = 0.45


@dataclass(frozen=True)
class FieldScore:
    """Confidence scoring metadata for a single field path."""

    path: str
    score: float
    tier: str
    ui_behavior: str
    reasons: tuple[str, ...]


__all__ = [
    "FieldScore",
    "StepMissing",
    "compute_field_score",
    "compute_step_field_scores",
    "compute_step_missing",
    "is_step_complete",
    "iter_step_missing_fields",
]


def _critical_fields_for_step(step_meta: WizardPage) -> tuple[str, ...]:
    return tuple(field for field in load_critical_fields() if field_belongs_to_page(field, step_meta.key))


@dataclass(frozen=True)
class StepMissing:
    """Missing required and critical field lists for a wizard step."""

    required: list[str]
    critical: list[str]
    low_confidence: list[str]
    blocked_by_confidence: list[str]


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _score_tier(score: float) -> str:
    if score >= HIGH_CONFIDENCE_THRESHOLD:
        return "high"
    if score >= MEDIUM_CONFIDENCE_THRESHOLD:
        return "medium"
    return "low"


def _ui_behavior_for_tier(tier: str, *, is_critical: bool) -> str:
    if tier == "high":
        return "hint"
    if tier == "medium":
        return "followup_required"
    return "block_next" if is_critical else "followup_required"


def compute_field_score(
    profile: Mapping[str, Any],
    field_path: str,
    *,
    is_critical: bool = False,
) -> FieldScore:
    """Compute a confidence score and reason codes for one field."""

    value = get_path_value(profile, field_path)
    reasons: list[str] = []
    score = 1.0

    if value in (None, "", [], {}):
        if isinstance(value, list):
            reasons.append("REQ_LIST_MISSING")
        else:
            reasons.append("REQ_VALUE_MISSING")
        score -= 0.9

    metadata = get_field_metadata(field_path, profile=profile) or {}
    source = str(metadata.get("source") or "").strip().lower()
    if source == "heuristic":
        reasons.append("HEURISTIC_ONLY")
        score -= 0.25
    elif source == "rule":
        score += 0.05
    elif source == "user":
        score += 0.1

    if metadata.get("evidence_snippet") in (None, ""):
        reasons.append("CUE_SPARSE")
        score -= 0.1

    legacy_meta = _as_mapping(profile.get("meta"))
    llm_recovery = _as_mapping(legacy_meta.get("llm_recovery"))
    low_conf_fields = llm_recovery.get("low_confidence_fields")
    if llm_recovery.get("invalid_json") and (not isinstance(low_conf_fields, list) or field_path in low_conf_fields):
        reasons.append("JSON_REPAIRED")
        score -= 0.25

    if field_path == "compensation.salary_max":
        salary_min = get_path_value(profile, "compensation.salary_min")
        if isinstance(value, (int, float)) and isinstance(salary_min, (int, float)) and value < salary_min:
            reasons.append("CONSISTENCY_SALARY_RANGE")
            score -= 0.4

    confidence_meta = _as_mapping(_as_mapping(legacy_meta.get("field_confidence")).get(field_path))
    legacy_score = confidence_meta.get("score")
    if isinstance(legacy_score, (float, int)):
        score = (score + max(0.0, min(1.0, float(legacy_score)))) / 2

    normalized_score = max(0.0, min(1.0, score))
    tier = _score_tier(normalized_score)
    behavior = _ui_behavior_for_tier(tier, is_critical=is_critical)
    field_score = FieldScore(
        path=field_path,
        score=normalized_score,
        tier=tier,
        ui_behavior=behavior,
        reasons=tuple(dict.fromkeys(reasons)),
    )
    logger.info(
        "field_confidence path=%s score=%.2f tier=%s ui=%s reasons=%s",
        field_score.path,
        field_score.score,
        field_score.tier,
        field_score.ui_behavior,
        ",".join(field_score.reasons) or "NONE",
    )
    return field_score


def compute_step_field_scores(profile: Mapping[str, Any], step_meta: WizardPage) -> dict[str, FieldScore]:
    """Return field confidence scores for required + critical step fields."""

    required_fields = tuple(step_meta.required_fields or ())
    critical_fields = _critical_fields_for_step(step_meta)
    candidates = tuple(dict.fromkeys([*required_fields, *critical_fields]))
    critical_lookup = set(critical_fields)
    return {
        field_path: compute_field_score(profile, field_path, is_critical=field_path in critical_lookup)
        for field_path in candidates
    }


def compute_step_missing(profile: object, step_meta: WizardPage) -> StepMissing:
    """Compute missing required and critical fields for ``step_meta``."""  # GREP:STEP_STATUS_V1

    profile_data = get_path_value(profile, "")
    required_fields = tuple(step_meta.required_fields or ())
    missing_required = missing_fields(profile_data, required_fields) if required_fields else []
    critical_fields = _critical_fields_for_step(step_meta)
    missing_critical = missing_fields(profile_data, critical_fields) if critical_fields else []
    score_map = compute_step_field_scores(profile_data if isinstance(profile_data, Mapping) else {}, step_meta)
    low_confidence = [field for field, score in score_map.items() if score.tier == "low"]
    blocked_by_confidence = [
        field
        for field, score in score_map.items()
        if score.ui_behavior == "block_next" and field not in missing_required and field not in missing_critical
    ]
    return StepMissing(
        required=missing_required,
        critical=missing_critical,
        low_confidence=low_confidence,
        blocked_by_confidence=blocked_by_confidence,
    )


def is_step_complete(profile: object, step_meta: WizardPage) -> bool:
    """Return ``True`` when ``step_meta`` has no missing required/critical fields."""

    missing = compute_step_missing(profile, step_meta)
    return not missing.required and not missing.critical and not missing.blocked_by_confidence


def iter_step_missing_fields(missing: StepMissing) -> Iterable[str]:
    """Return an ordered iterable of all missing fields."""

    return tuple(dict.fromkeys([*missing.required, *missing.critical, *missing.blocked_by_confidence]))
