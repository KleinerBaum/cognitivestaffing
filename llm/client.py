"""Abstraction over the OpenAI client for JSON extraction."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from copy import deepcopy
from collections.abc import MutableMapping, Sequence
from typing import Any, Callable, Mapping, Optional, Final

from jsonschema import Draft7Validator
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pydantic import ValidationError
import streamlit as st

from openai import BadRequestError
from openai_utils import call_chat_api
from openai_utils.api import is_unrecoverable_schema_error
from constants.keys import StateKeys
from prompts import prompt_registry
from .context import build_extract_messages, build_preanalysis_messages
import config as app_config
from config import (
    REASONING_EFFORT,
    ModelTask,
    get_active_verbosity,
    get_model_for,
    mark_model_unavailable,
    select_model,
)
from .openai_responses import (
    ResponsesCallResult,
    build_json_schema_format,
    call_responses_safe,
)
from .output_parsers import (
    NeedAnalysisParserError,
    get_need_analysis_output_parser,
)
from .prompts import FIELDS_ORDER, PreExtractionInsights
from core.errors import ExtractionError
from core.schema import NeedAnalysisProfile, canonicalize_profile_payload, coerce_and_fill
from core.schema_registry import load_need_analysis_schema
from llm.json_repair import parse_profile_json
from utils.json_parse import parse_extraction

logger = logging.getLogger("cognitive_needs.llm")
tracer = trace.get_tracer(__name__)


@dataclass(frozen=True)
class StructuredExtractionOutcome:
    """Result envelope for structured extraction attempts."""

    content: str
    source: str
    low_confidence: bool = False


_STRUCTURED_EXTRACTION_CHAIN: Any | None = None
_STRUCTURED_RESPONSE_RETRIES = 3
_EXTRACTION_MAX_COMPLETION_TOKENS: Final[int] = 500


def _build_missing_section_schema(missing_sections: Sequence[str]) -> Mapping[str, Any]:
    """Return a JSON schema covering the missing ``missing_sections`` only."""

    properties: dict[str, Any] = {}
    required: list[str] = []

    if "responsibilities.items" in missing_sections:
        properties["responsibilities"] = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            },
        }
        required.append("responsibilities")

    if "company.culture" in missing_sections:
        properties["company"] = {
            "type": "object",
            "properties": {
                "culture": {
                    "type": ["string", "null"],
                }
            },
        }
        required.append("company")

    if "process.overview" in missing_sections:
        properties["process"] = {
            "type": "object",
            "properties": {
                "recruitment_timeline": {"type": ["string", "null"]},
                "hiring_process": {
                    "type": ["array", "null"],
                    "items": {"type": "string"},
                },
                "process_notes": {"type": ["string", "null"]},
                "application_instructions": {"type": ["string", "null"]},
            },
        }
        required.append("process")

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def _collect_missing_paths(errors: Sequence[Mapping[str, Any]] | None) -> list[str]:
    """Return dot-paths for missing sections collected from ``errors``."""

    if not errors:
        return []
    paths: list[str] = []
    for entry in errors:
        if entry.get("msg") != "missing":
            continue
        location = entry.get("loc")
        if not isinstance(location, (list, tuple)):
            continue
        label = ".".join(str(part) for part in location if str(part))
        if label:
            paths.append(label)
    return paths


def _merge_missing_section_payload(base: Mapping[str, Any] | None, patch: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep merge of ``base`` with ``patch`` limited to missing sections."""

    merged: dict[str, Any] = deepcopy(dict(base)) if isinstance(base, Mapping) else {}

    for key, value in patch.items():
        if isinstance(value, Mapping):
            existing = merged.get(key)
            if isinstance(existing, Mapping):
                merged[key] = _merge_missing_section_payload(existing, value)
            else:
                merged[key] = deepcopy(value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _retry_missing_sections(
    text: str,
    missing_sections: Sequence[str],
    *,
    model: str,
    retries: int,
) -> Mapping[str, Any] | None:
    """Request a focused retry for ``missing_sections`` from ``text``."""

    if not missing_sections or not text.strip():
        return None

    section_list = ", ".join(missing_sections)
    logger.info("Retrying missing sections with dedicated prompt: %s", section_list)
    messages = [
        {
            "role": "system",
            "content": prompt_registry.get("llm.extraction.missing_sections.system"),
        },
        {
            "role": "user",
            "content": prompt_registry.format(
                "llm.extraction.missing_sections.user",
                sections=section_list,
                text=text,
            ),
        },
    ]

    response_format = build_json_schema_format(
        name="need_analysis_missing_sections",
        schema=_build_missing_section_schema(missing_sections),
    )

    effort = _resolve_extraction_effort()
    verbosity = get_active_verbosity()

    result = call_responses_safe(
        messages,
        model=model,
        response_format=response_format,
        temperature=0,
        max_completion_tokens=800,
        retries=retries,
        reasoning_effort=effort,
        verbosity=verbosity,
        task=ModelTask.EXTRACTION,
        logger_instance=logger,
        context="missing_section_retry",
    )
    if result is None:
        return None

    payload = (result.content or "").strip()
    if not payload:
        return None

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, Mapping):
        return None

    return canonicalize_profile_payload(parsed)


def _responses_api_enabled() -> bool:
    """Return whether the structured extraction should use the Responses API."""

    return _strict_extraction_enabled() and app_config.USE_RESPONSES_API


def _strict_extraction_enabled() -> bool:
    """Return whether structured parsing should enforce strict JSON mode."""

    return True


def _resolve_extraction_effort() -> str:
    """Return the reasoning effort for extraction honoring precise mode."""

    try:
        effort_raw = st.session_state.get(StateKeys.REASONING_EFFORT, REASONING_EFFORT)
    except Exception:
        effort_raw = REASONING_EFFORT
    effort_value = str(effort_raw or "").strip().lower() or REASONING_EFFORT
    if app_config.get_reasoning_mode() == "precise" and effort_value in {"none", "minimal", "low", "medium"}:
        return "high"
    return effort_value


_PRE_ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "relevant_fields": {
            "type": "array",
            "description": "Schema field keys that likely have evidence in the text.",
            "items": {"type": "string"},
            "minItems": 0,
        },
        "missing_fields": {
            "type": "array",
            "description": "Schema fields that appear absent or weak in the text.",
            "items": {"type": "string"},
            "minItems": 0,
        },
        "summary": {
            "type": "string",
            "description": "Short notes about the available information in the document.",
        },
    },
    "required": ["relevant_fields", "missing_fields", "summary"],
    "additionalProperties": False,
}


def _summarise_prompt(messages: Sequence[Mapping[str, Any]] | None) -> str:
    """Return a short digest for ``messages`` without leaking sensitive data."""

    if not messages:
        return "messages=0"

    total = len(messages)
    latest: Mapping[str, Any] | None = None
    for message in reversed(messages):
        if not isinstance(message, Mapping):
            continue
        role = str(message.get("role", "")).strip().lower()
        if role == "user":
            latest = message
            break
        if latest is None:
            latest = message

    if latest is None:
        return f"messages={total}, latest_user_chars=0"

    content = str(latest.get("content") or "")
    length = len(content)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:8] if content else "0" * 8
    return f"messages={total}, latest_user_chars={length}, latest_user_hash={digest}"


def _summarise_missing_sections(fields: Sequence[str] | None) -> str:
    """Return a concise summary of missing schema sections for logging."""

    if not fields:
        return "none reported"
    sections = sorted({field.split(".")[0] for field in fields if isinstance(field, str) and field})
    return ", ".join(sections) if sections else "none reported"


def _set_nested_value(target: MutableMapping[str, Any], path: str, value: Any) -> None:
    """Assign ``value`` to ``path`` within ``target`` using dot-notation."""

    parts = path.split(".")
    cursor: MutableMapping[str, Any] = target
    for part in parts[:-1]:
        child = cursor.get(part)
        if not isinstance(child, MutableMapping):
            child = {}
            cursor[part] = child
        cursor = child
    cursor[parts[-1]] = value


def _merge_locked_fields(payload: MutableMapping[str, Any], locked_fields: Mapping[str, Any] | None) -> None:
    """Apply locked field values to the extracted payload in-place."""

    if not locked_fields:
        return

    for field, value in locked_fields.items():
        if value is None:
            continue
        final_value = value
        if isinstance(value, str):
            sanitized = value.strip().replace("\n", " ")
            if not sanitized:
                continue
            final_value = sanitized
        _set_nested_value(payload, field, final_value)


def _assert_closed_schema(schema: dict[str, Any]) -> None:
    """Ensure the JSON schema is self-contained.

    Args:
        schema: Schema to inspect.

    Raises:
        ValueError: If forbidden ``$ref`` keys are present.
    """

    refs: list[str] = []

    def _walk(obj: Any, path: str = "") -> None:
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref = obj["$ref"]
                loc = path or "$"
                refs.append(f"{loc} -> {ref}")
            for key, value in obj.items():
                _walk(value, f"{path}/{key}" if path else key)
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                _walk(item, f"{path}[{idx}]")

    _walk(schema)
    if refs:
        report = "\n".join(refs)
        raise ValueError("Foreign key references are not allowed in function-calling schema:\n" + report)


def _filter_known_fields(fields: Sequence[Any] | None) -> list[str]:
    """Return unique schema fields from ``fields`` preserving order."""

    if not fields:
        return []

    seen: set[str] = set()
    ordered: list[str] = []
    for item in fields:
        candidate = str(item).strip()
        if not candidate or candidate not in FIELDS_ORDER:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered


def _coerce_pre_analysis(payload: Mapping[str, Any]) -> PreExtractionInsights | None:
    """Convert a model payload into :class:`PreExtractionInsights`."""

    relevant = _filter_known_fields(payload.get("relevant_fields"))
    missing = _filter_known_fields(payload.get("missing_fields"))
    summary_raw = payload.get("summary")
    summary = str(summary_raw).strip() if isinstance(summary_raw, str) else ""

    insights = PreExtractionInsights(
        summary=summary,
        relevant_fields=relevant or None,
        missing_fields=missing or None,
    )
    return insights if insights.has_data() else None


def _generate_error_report(instance: dict[str, Any]) -> str:
    """Return detailed validation errors for ``instance``.

    Args:
        instance: Data to validate against ``NEED_ANALYSIS_SCHEMA``.

    Returns:
        Multiline error report or an empty string if validation passes.
    """

    validator = Draft7Validator(NEED_ANALYSIS_SCHEMA)
    lines = []
    for err in validator.iter_errors(instance):
        path = "/".join(str(p) for p in err.path) or "$"
        lines.append(f"{path}: {err.message}")
    return "\n".join(lines)


NEED_ANALYSIS_SCHEMA = load_need_analysis_schema()
NEED_ANALYSIS_SCHEMA.pop("$schema", None)
NEED_ANALYSIS_SCHEMA.pop("title", None)
_assert_closed_schema(NEED_ANALYSIS_SCHEMA)

_required_company_fields = NEED_ANALYSIS_SCHEMA.get("properties", {}).get("company", {}).get("required", [])
logger.debug(
    "Using schema (strict=%s) with required fields: %s",
    app_config.STRICT_JSON,
    _required_company_fields,
)


def _run_pre_extraction_analysis(
    text: str,
    *,
    title: str | None = None,
    company: str | None = None,
    url: str | None = None,
) -> PreExtractionInsights | None:
    """Call the model to obtain pre-analysis hints for extraction."""

    if not (text or "").strip():
        return None

    messages = build_preanalysis_messages(
        text,
        title=title,
        company=company,
        url=url,
    )

    effort = _resolve_extraction_effort()
    model = select_model(ModelTask.EXTRACTION)

    try:
        result = call_chat_api(
            messages,
            model=model,
            temperature=0,
            reasoning_effort=effort,
            verbosity=get_active_verbosity(),
            json_schema={"name": "pre_extraction_analysis", "schema": _PRE_ANALYSIS_SCHEMA},
            task=ModelTask.EXTRACTION,
        )
    except Exception as exc:  # pragma: no cover - network/SDK issues
        logger.debug("Pre-analysis call failed; continuing without hints: %s", exc)
        return None

    content = (result.content or "").strip()
    if not content:
        return None

    try:
        payload = json.loads(content)
    except json.JSONDecodeError:  # pragma: no cover - defensive guard
        logger.debug("Pre-analysis returned invalid JSON: %s", content)
        return None

    if not isinstance(payload, Mapping):
        return None

    insights = _coerce_pre_analysis(payload)
    if insights:
        logger.debug(
            "Pre-analysis identified %d relevant fields and %d potential gaps.",
            len(insights.relevant_fields or ()),
            len(insights.missing_fields or ()),
        )
    return insights


def _structured_extraction(payload: dict[str, Any]) -> StructuredExtractionOutcome:
    """Call the chat API and validate the structured extraction output."""

    chain = _STRUCTURED_EXTRACTION_CHAIN
    if chain is not None:
        return chain.invoke(payload)

    prompt_digest = _summarise_prompt(payload.get("messages"))
    strict_format = _strict_extraction_enabled()
    low_confidence = False
    source = "responses"

    def _build_chat_call() -> Callable[[], StructuredExtractionOutcome]:
        def _invoke() -> StructuredExtractionOutcome:
            chat_kwargs: dict[str, Any] = {
                "messages": payload["messages"],
                "model": payload["model"],
                "temperature": 0,
                "max_completion_tokens": payload.get("max_completion_tokens"),
                "reasoning_effort": payload.get("reasoning_effort"),
                "verbosity": payload.get("verbosity"),
                "task": ModelTask.EXTRACTION,
            }
            if strict_format:
                chat_kwargs["json_schema"] = {
                    "name": "need_analysis_profile",
                    "schema": NEED_ANALYSIS_SCHEMA,
                }
            call_result = call_chat_api(**chat_kwargs)
            content_value = (call_result.content or "").strip()
            return StructuredExtractionOutcome(content=content_value, source="chat", low_confidence=low_confidence)

        return _invoke

    attempts: list[tuple[str, Callable[[], StructuredExtractionOutcome]]] = []

    if strict_format and _responses_api_enabled():
        response_format = build_json_schema_format(
            name="need_analysis_profile",
            schema=NEED_ANALYSIS_SCHEMA,
        )

        def _call_responses() -> StructuredExtractionOutcome:
            def _attempt(model_name: str) -> ResponsesCallResult | None:
                return call_responses_safe(
                    payload["messages"],
                    model=model_name,
                    response_format=response_format,
                    temperature=0,
                    reasoning_effort=payload.get("reasoning_effort"),
                    max_completion_tokens=payload.get("max_completion_tokens"),
                    retries=payload.get("retries", _STRUCTURED_RESPONSE_RETRIES),
                    task=ModelTask.EXTRACTION,
                    logger_instance=logger,
                    context="structured extraction",
                )

            active_model = payload["model"]

            try:
                result = _attempt(active_model)
            except BadRequestError as err:
                if is_unrecoverable_schema_error(err):
                    logger.warning(
                        "Responses schema invalid for %s; switching to chat fallback without retrying.",
                        prompt_digest,
                    )
                    return StructuredExtractionOutcome(content="", source="responses", low_confidence=True)
                raise

            if result is None:
                logger.info(
                    "Structured extraction returned empty content for %s; attempting alternate model.",
                    prompt_digest,
                )
                mark_model_unavailable(active_model)
                alternate_model = get_model_for(ModelTask.EXTRACTION)
                if alternate_model != active_model:
                    logger.warning(
                        "Retrying structured extraction with alternate model: %s",
                        alternate_model,
                    )
                    active_model = alternate_model
                    result = _attempt(active_model)
                if result is None:
                    logger.error(
                        "All API attempts failed for structured extraction via Responses for %s.",
                        prompt_digest,
                    )
                    return StructuredExtractionOutcome(content="", source="responses", low_confidence=True)
            outcome_source = "responses"
            if result.used_chat_fallback:
                outcome_source = "chat"
                low_confidence_result = True
                logger.info(
                    "Structured extraction fell back to chat completions for %s",
                    prompt_digest,
                )
            else:
                low_confidence_result = low_confidence
            content_value = (result.content or "").strip()
            return StructuredExtractionOutcome(
                content=content_value,
                source=outcome_source,
                low_confidence=low_confidence_result,
            )

        attempts.append(("responses", _call_responses))

    attempts.append(("chat", _build_chat_call()))

    content: StructuredExtractionOutcome | None = None
    last_error: Exception | None = None

    for label, attempt in attempts:
        try:
            candidate = attempt()
            if candidate.content:
                content = candidate
                low_confidence = low_confidence or candidate.low_confidence
                source = candidate.source
                break
            low_confidence = low_confidence or candidate.low_confidence
            source = candidate.source
        except Exception as err:  # pragma: no cover - network/SDK issues
            last_error = err
            logger.warning(
                "Structured extraction %s attempt failed for %s: %s",
                label,
                prompt_digest,
                err,
            )

    if content is None or not content.content.strip():
        logger.warning(
            "Structured extraction streaming returned empty content; retrying via chat completions for %s.",
            prompt_digest,
        )
        call_result = call_chat_api(
            payload["messages"],
            model=payload["model"],
            temperature=0,
            reasoning_effort=payload.get("reasoning_effort"),
            verbosity=payload.get("verbosity"),
            json_schema={
                "name": "need_analysis_profile",
                "schema": NEED_ANALYSIS_SCHEMA,
            },
            task=ModelTask.EXTRACTION,
            api_mode="chat",
        )
        fallback_content = (call_result.content or "").strip()
        content = StructuredExtractionOutcome(content=fallback_content, source="chat", low_confidence=True)
        low_confidence = True
        source = "chat"

    if not content.content:
        logger.warning(
            "Structured extraction returned empty response for %s; defaulting to an empty profile.",
            prompt_digest,
        )
        empty_payload = NeedAnalysisProfile().model_dump_json()
        return StructuredExtractionOutcome(content=empty_payload, source=source, low_confidence=True)

    parser = get_need_analysis_output_parser()

    def _attempt_schema_repair(err: NeedAnalysisParserError) -> StructuredExtractionOutcome | None:
        if not err.raw_text:
            return None
        repair_result = parse_profile_json(err.raw_text, errors=err.errors)
        if repair_result.payload is None:
            return None
        canonical_payload = canonicalize_profile_payload(repair_result.payload)
        try:
            repaired_model = NeedAnalysisProfile.model_validate(canonical_payload)
        except ValidationError as repair_error:
            logger.warning(
                "Structured extraction repair retry failed for %s: %s",
                prompt_digest,
                repair_error,
            )
            return None
        logger.info("Structured extraction repaired invalid JSON for %s.", prompt_digest)
        return StructuredExtractionOutcome(
            content=repaired_model.model_dump_json(),
            source="chat" if low_confidence else source,
            low_confidence=True,
        )

    try:
        profile, raw_data = parser.parse(content.content)
    except NeedAnalysisParserError as err:
        missing_sections = _collect_missing_paths(err.errors)
        if missing_sections and isinstance(payload.get("source_text"), str):
            retry_payload = _retry_missing_sections(
                payload["source_text"],
                missing_sections,
                model=payload["model"],
                retries=payload.get("retries", _STRUCTURED_RESPONSE_RETRIES),
            )
            if retry_payload:
                merged_payload = _merge_missing_section_payload(err.data, retry_payload)
                canonical_payload = canonicalize_profile_payload(merged_payload)
                try:
                    validated = NeedAnalysisProfile.model_validate(canonical_payload)
                except ValidationError as merge_error:
                    logger.debug(
                        "Validation failed after missing-section retry: %s",
                        merge_error,
                    )
                else:
                    logger.info(
                        "Structured extraction recovered missing sections: %s",
                        ", ".join(missing_sections),
                    )
                    return StructuredExtractionOutcome(
                        content=validated.model_dump_json(),
                        source="chat" if low_confidence else source,
                        low_confidence=True,
                    )
        repaired_outcome = _attempt_schema_repair(err)
        if repaired_outcome is not None:
            return repaired_outcome
        if err.data:
            report = _generate_error_report(err.data)
            if report:
                logger.debug("Schema validation errors:\n%s", report)
                logger.warning(
                    "Schema validation error encountered (Schema fix needed) for %s: %s",
                    prompt_digest,
                    report,
                )
                if err.original and hasattr(err.original, "add_note"):
                    err.original.add_note(report)
        logger.warning("Structured extraction parsing failed for %s: %s", prompt_digest, err.message)
        raise ValueError(err.message) from err.original or err
    except ValidationError as err:
        logger.warning(
            "Structured extraction validation raised unexpected error for %s: %s",
            prompt_digest,
            err,
        )
        raise
    else:
        if raw_data is not None and not raw_data:
            logger.warning(
                "Structured extraction pruned all fields for %s; triggering fallback.",
                prompt_digest,
            )
            raise ValueError("structured_extraction_empty_payload")
        validated_payload = (
            json.dumps(raw_data, ensure_ascii=False) if raw_data is not None else profile.model_dump_json()
        )
        return StructuredExtractionOutcome(
            content=validated_payload,
            source=source,
            low_confidence=low_confidence,
        )

    if last_error is not None:
        raise ValueError("Structured extraction failed") from last_error
    raise ValueError("Structured extraction returned empty response")


def _minimal_messages(text: str) -> list[dict[str, str]]:
    """Build a minimal prompt asking for raw JSON output."""

    keys = ", ".join(FIELDS_ORDER)
    parser = get_need_analysis_output_parser()
    system_content = prompt_registry.format("llm.client.minimal_system", keys=keys)
    system_content = f"{system_content}\n\n{parser.format_instructions}".strip()
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": text},
    ]


def _extract_json_outcome(
    text: str,
    title: Optional[str] = None,
    company: Optional[str] = None,
    url: Optional[str] = None,
    locked_fields: Optional[Mapping[str, str]] = None,
    *,
    minimal: bool = False,
) -> StructuredExtractionOutcome:
    """Extract schema fields via JSON mode with optional plain fallback.

    Args:
        text: Input job posting.
        title: Optional job title for context.
        company: Optional company name for context.
        url: Optional source URL.

    Returns:
        StructuredExtractionOutcome describing the extracted payload.
    """

    with tracer.start_as_current_span("llm.extract_json") as span:
        insights: PreExtractionInsights | None = None
        if not minimal:
            insights = _run_pre_extraction_analysis(
                text,
                title=title,
                company=company,
                url=url,
            )
            span.set_attribute("llm.extract.preanalysis", bool(insights and insights.has_data()))
            if insights and insights.summary:
                span.set_attribute(
                    "llm.extract.preanalysis.summary",
                    insights.summary[:120],
                )
        messages = (
            _minimal_messages(text)
            if minimal
            else build_extract_messages(
                text,
                title=title,
                company=company,
                url=url,
                locked_fields=locked_fields,
                insights=insights,
            )
        )
        prompt_digest = _summarise_prompt(messages)
        missing_sections = _summarise_missing_sections(getattr(insights, "missing_fields", None))
        effort = _resolve_extraction_effort()
        model = select_model(ModelTask.EXTRACTION)
        span.set_attribute("llm.model", model)
        span.set_attribute("llm.extract.minimal", minimal)
        try:
            outcome = _structured_extraction(
                {
                    "messages": messages,
                    "model": model,
                    "reasoning_effort": effort,
                    "verbosity": get_active_verbosity(),
                    "retries": _STRUCTURED_RESPONSE_RETRIES,
                    "source_text": text,
                    "max_completion_tokens": _EXTRACTION_MAX_COMPLETION_TOKENS,
                }
            )
            span.set_attribute("llm.extract.source", outcome.source)
            span.set_attribute("llm.extract.low_confidence", bool(outcome.low_confidence))
            output = outcome.content
            if locked_fields:
                data = json.loads(output)
                _merge_locked_fields(data, locked_fields)
                output = json.dumps(data, ensure_ascii=False)
        except ValidationError as err:
            notes = "\n".join(getattr(err, "__notes__", ()))
            detail = notes or str(err)
            logger.warning(
                (
                    "Structured extraction output failed validation for %s (missing sections: %s); "
                    "falling back to plain text.\n%s"
                ),
                prompt_digest,
                missing_sections,
                detail,
            )
            span.record_exception(err)
            span.set_status(Status(StatusCode.ERROR, "structured_validation_failed"))
            span.add_event(
                "structured_validation_failed",
                {"error.detail": detail[:512]},
            )
        except Exception as exc:  # pragma: no cover - network/SDK issues
            logger.warning(
                "Structured extraction failed for %s (missing sections: %s); falling back to plain text: %s",
                prompt_digest,
                missing_sections,
                exc,
            )
            span.record_exception(exc)
            span.add_event("structured_call_failed")
        else:
            span.set_attribute("llm.extract.fallback", False)
            return StructuredExtractionOutcome(
                content=output,
                source=outcome.source,
                low_confidence=outcome.low_confidence,
            )

        span.set_attribute("llm.extract.fallback", True)
        try:
            result = call_chat_api(
                messages,
                model=model,
                temperature=0,
                max_completion_tokens=_EXTRACTION_MAX_COMPLETION_TOKENS,
                reasoning_effort=effort,
                verbosity=get_active_verbosity(),
                json_schema={
                    "name": "need_analysis_profile",
                    "schema": NEED_ANALYSIS_SCHEMA,
                },
                task=ModelTask.EXTRACTION,
            )
        except Exception as exc2:  # pragma: no cover - network/SDK issues
            span.record_exception(exc2)
            span.set_status(Status(StatusCode.ERROR, "fallback_call_failed"))
            raise ExtractionError("LLM call failed") from exc2
        content = (result.content or "").strip()
        if content:
            profile: NeedAnalysisProfile | None = None
            try:
                profile = parse_extraction(content)
            except Exception as err3:  # pragma: no cover - defensive
                span.record_exception(err3)
                span.add_event(
                    "fallback_parse_failed",
                    {"error.type": err3.__class__.__name__},
                )
                repair_result = parse_profile_json(content)
                if repair_result.payload is not None:
                    try:
                        profile = coerce_and_fill(repair_result.payload)
                        span.add_event(
                            "fallback_repair_succeeded",
                            {"repair.issues": len(repair_result.issues)},
                        )
                    except Exception as err4:  # pragma: no cover - defensive
                        span.record_exception(err4)
                        span.add_event(
                            "fallback_repair_validation_failed",
                            {"error.type": err4.__class__.__name__},
                        )
                else:
                    logger.warning(
                        "Plain-text fallback returned unparseable content; repair could not recover JSON.",
                        exc_info=err3,
                    )
            if profile is not None:
                profile.meta.extraction_fallback_active = True
                return StructuredExtractionOutcome(
                    content=profile.model_dump_json(),
                    source="chat",
                    low_confidence=True,
                )
            span.set_status(Status(StatusCode.ERROR, "fallback_parse_failed"))
            logger.warning(
                "Plain-text fallback returned unparseable content; defaulting to an empty profile.",
            )
        span.set_status(Status(StatusCode.ERROR, "empty_response"))
        logger.info(
            "Plain-text fallback returned no content; defaulting to an empty profile.",
        )
        empty_profile = NeedAnalysisProfile()
        empty_profile.meta.extraction_fallback_active = True
        return StructuredExtractionOutcome(
            content=empty_profile.model_dump_json(),
            source="chat",
            low_confidence=True,
        )


def extract_json(
    text: str,
    title: Optional[str] = None,
    company: Optional[str] = None,
    url: Optional[str] = None,
    locked_fields: Optional[Mapping[str, str]] = None,
    *,
    minimal: bool = False,
) -> str:
    """Compatibility wrapper returning only the extracted JSON string."""

    outcome = _extract_json_outcome(
        text,
        title=title,
        company=company,
        url=url,
        locked_fields=locked_fields,
        minimal=minimal,
    )
    return outcome.content
