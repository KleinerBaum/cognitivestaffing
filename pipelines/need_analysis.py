"""Need analysis extraction pipeline logic decoupled from Streamlit UI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.extraction import parse_structured_payload
from llm.client import _extract_json_outcome

__all__ = ["ExtractionResult", "extract_need_analysis_profile"]


@dataclass
class ExtractionResult:
    """Container for structured extraction outputs."""

    raw_json: str
    data: dict[str, Any]
    recovered: bool
    issues: list[str]
    low_confidence: bool = False


def extract_need_analysis_profile(
    text: str,
    *,
    title_hint: str | None = None,
    company_hint: str | None = None,
    url_hint: str | None = None,
    locked_fields: Mapping[str, str] | None = None,
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
    return ExtractionResult(
        raw_json=outcome.content,
        data=data,
        recovered=recovered,
        issues=issues,
        low_confidence=outcome.low_confidence,
    )
