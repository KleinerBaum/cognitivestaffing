"""Need analysis extraction pipeline logic decoupled from Streamlit UI."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Mapping

from core.critical_fields import load_critical_fields

from core.extraction import parse_structured_payload
from llm.client import _extract_json_outcome

__all__ = ["ExtractionResult", "extract_need_analysis_profile"]

logger = logging.getLogger("cognitive_needs.pipeline.extraction")
_CRITICAL_FIELDS: tuple[str, ...] = tuple(sorted({field.strip() for field in load_critical_fields() if field.strip()}))


def _has_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return any(_has_value(item) for item in value.values())
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_has_value(item) for item in value)
    return bool(value)


def _get_path(data: Mapping[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _count_missing_critical_fields(payload: Mapping[str, Any]) -> int:
    return sum(1 for path in _CRITICAL_FIELDS if not _has_value(_get_path(payload, path)))


def _count_heuristic_critical_fields(metadata: Mapping[str, Any] | None) -> int:
    if not isinstance(metadata, Mapping):
        return 0
    sources = metadata.get("field_sources")
    if not isinstance(sources, Mapping):
        return 0
    count = 0
    for field in _CRITICAL_FIELDS:
        source_entry = sources.get(field)
        if isinstance(source_entry, Mapping) and str(source_entry.get("source") or "").lower() == "heuristic":
            count += 1
    return count


@dataclass
class ExtractionResult:
    """Container for structured extraction outputs."""

    raw_json: str
    data: dict[str, Any]
    recovered: bool
    issues: list[str]
    low_confidence: bool = False
    repair_applied: bool = False
    repair_confidence: float | None = None
    repair_count: int = 0
    missing_required_count: int = 0
    heuristic_critical_count: int = 0
    degraded: bool = False
    degraded_reasons: list[str] | None = None


def extract_need_analysis_profile(
    text: str,
    *,
    title_hint: str | None = None,
    company_hint: str | None = None,
    url_hint: str | None = None,
    locked_fields: Mapping[str, str] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ExtractionResult:
    """Run LLM-based extraction and return structured results.

    This helper isolates the orchestration of the extraction call and subsequent
    JSON parsing from any UI concerns. Callers can handle caching, retries, and
    UI updates separately while reusing the same business logic.

    Args:
        text: Source text to analyse.
        title_hint: Optional job title hint for the prompt.
        company_hint: Optional company name hint for the prompt.
        url_hint: Optional source URL for context.
        locked_fields: Optional mapping of fields that should stay fixed.

    Returns:
        An :class:`ExtractionResult` containing the raw JSON payload, the parsed
        data, and parsing diagnostics.

    Raises:
        ExtractionError: When the model call fails.
        InvalidExtractionPayload: When the payload cannot be parsed.
    """

    outcome = _extract_json_outcome(
        text,
        title=title_hint,
        company=company_hint,
        url=url_hint,
        locked_fields=locked_fields or None,
    )
    data, recovered, issues = parse_structured_payload(outcome.content, source_text=text)
    if outcome.low_confidence:
        issues.append("extraction_fallback_active")

    missing_required_count = _count_missing_critical_fields(data)
    heuristic_critical_count = _count_heuristic_critical_fields(metadata)
    degraded_reasons: list[str] = []
    if outcome.repair_count > 1:
        degraded_reasons.append("multiple_json_repairs")
    if missing_required_count > 0:
        degraded_reasons.append("missing_required_fields_after_retry")
    degraded = bool(degraded_reasons)
    if degraded:
        logger.warning(
            "Extraction degraded state detected reasons=%s",
            ",".join(degraded_reasons),
        )

    return ExtractionResult(
        raw_json=outcome.content,
        data=data,
        recovered=recovered,
        issues=issues,
        low_confidence=outcome.low_confidence,
        repair_applied=outcome.repair_applied,
        repair_confidence=outcome.repair_confidence,
        repair_count=outcome.repair_count,
        missing_required_count=missing_required_count,
        heuristic_critical_count=heuristic_critical_count,
        degraded=degraded,
        degraded_reasons=degraded_reasons or None,
    )
