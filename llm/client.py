"""Abstraction over the OpenAI client for JSON extraction."""

from __future__ import annotations

import json
import re
import logging
from pathlib import Path
from collections.abc import MutableMapping
from typing import Any, Mapping, Optional

from jsonschema import Draft7Validator
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pydantic import ValidationError
import streamlit as st

from openai_utils import call_chat_api
from prompts import prompt_registry
from .context import build_extract_messages
from .prompts import FIELDS_ORDER
from core.errors import ExtractionError
from config import (
    REASONING_EFFORT,
    USE_RESPONSES_API,
    ModelTask,
    get_active_verbosity,
    get_model_for,
)
from models.need_analysis import NeedAnalysisProfile
from .openai_responses import build_json_schema_format, call_responses

logger = logging.getLogger("cognitive_needs.llm")
tracer = trace.get_tracer(__name__)


_STRUCTURED_EXTRACTION_CHAIN: Any | None = None
_STRUCTURED_RESPONSE_RETRIES = 2


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


SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "need_analysis.schema.json"
with open(SCHEMA_PATH, "r", encoding="utf-8") as _f:
    raw = _f.read()
    cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
    NEED_ANALYSIS_SCHEMA = json.loads(cleaned)
NEED_ANALYSIS_SCHEMA.pop("$schema", None)
NEED_ANALYSIS_SCHEMA.pop("title", None)
_assert_closed_schema(NEED_ANALYSIS_SCHEMA)


def _structured_extraction(payload: dict[str, Any]) -> str:
    """Call the chat API and validate the structured extraction output."""

    chain = _STRUCTURED_EXTRACTION_CHAIN
    if chain is not None:
        return chain.invoke(payload)

    content: str | None = None
    if USE_RESPONSES_API:
        response_format = build_json_schema_format(
            name="need_analysis_profile",
            schema=NEED_ANALYSIS_SCHEMA,
        )
        try:
            result = call_responses(
                payload["messages"],
                model=payload["model"],
                response_format=response_format,
                temperature=0,
                reasoning_effort=payload.get("reasoning_effort"),
                max_tokens=payload.get("max_tokens"),
                retries=payload.get("retries", _STRUCTURED_RESPONSE_RETRIES),
                task=ModelTask.EXTRACTION,
            )
        except Exception as exc:  # pragma: no cover - network/SDK issues
            logger.warning("Responses API call failed; falling back to chat completions: %s", exc)
        else:
            content = (result.content or "").strip()

    if content is None:
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
        )
        content = (call_result.content or "").strip()
    if not content:
        raise ValueError("LLM returned empty response")

    try:
        data = json.loads(content)
    except json.JSONDecodeError as err:
        raise ValueError("Structured extraction did not return valid JSON") from err

    try:
        profile = NeedAnalysisProfile.model_validate(data)
    except ValidationError as err:
        report = _generate_error_report(data)
        if report:
            logger.debug("Schema validation errors:\n%s", report)
            if hasattr(err, "add_note"):
                err.add_note(report)
        raise

    return json.dumps(profile.model_dump(mode="json"), ensure_ascii=False)


def _minimal_messages(text: str) -> list[dict[str, str]]:
    """Build a minimal prompt asking for raw JSON output."""

    keys = ", ".join(FIELDS_ORDER)
    system_content = prompt_registry.format("llm.client.minimal_system", keys=keys)
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": text},
    ]


def extract_json(
    text: str,
    title: Optional[str] = None,
    company: Optional[str] = None,
    url: Optional[str] = None,
    locked_fields: Optional[Mapping[str, str]] = None,
    *,
    minimal: bool = False,
) -> str:
    """Extract schema fields via JSON mode with optional plain fallback.

    Args:
        text: Input job posting.
        title: Optional job title for context.
        company: Optional company name for context.
        url: Optional source URL.

    Returns:
        Raw JSON string as returned by the model.
    """

    with tracer.start_as_current_span("llm.extract_json") as span:
        messages = (
            _minimal_messages(text)
            if minimal
            else build_extract_messages(
                text,
                title=title,
                company=company,
                url=url,
                locked_fields=locked_fields,
            )
        )
        effort = st.session_state.get("reasoning_effort", REASONING_EFFORT)
        model = get_model_for(ModelTask.EXTRACTION)
        span.set_attribute("llm.model", model)
        span.set_attribute("llm.extract.minimal", minimal)
        try:
            output = _structured_extraction(
                {
                    "messages": messages,
                    "model": model,
                    "reasoning_effort": effort,
                    "verbosity": get_active_verbosity(),
                    "retries": _STRUCTURED_RESPONSE_RETRIES,
                }
            )
            if locked_fields:
                data = json.loads(output)
                _merge_locked_fields(data, locked_fields)
                output = json.dumps(data, ensure_ascii=False)
        except ValidationError as err:
            notes = "\n".join(getattr(err, "__notes__", ()))
            detail = notes or str(err)
            logger.warning(
                "Structured extraction output failed validation; falling back to plain text.\n%s",
                detail,
            )
            span.record_exception(err)
            span.add_event("structured_validation_failed")
        except Exception as exc:  # pragma: no cover - network/SDK issues
            logger.warning("Structured extraction failed, falling back to plain text: %s", exc)
            span.record_exception(exc)
            span.add_event("structured_call_failed")
        else:
            span.set_attribute("llm.extract.fallback", False)
            return output

        span.set_attribute("llm.extract.fallback", True)
        try:
            result = call_chat_api(
                messages,
                model=model,
                temperature=0,
                reasoning_effort=effort,
                verbosity=get_active_verbosity(),
                task=ModelTask.EXTRACTION,
            )
        except Exception as exc2:  # pragma: no cover - network/SDK issues
            span.record_exception(exc2)
            span.set_status(Status(StatusCode.ERROR, "fallback_call_failed"))
            raise ExtractionError("LLM call failed") from exc2
        content = (result.content or "").strip()
        if content:
            return content
        span.set_status(Status(StatusCode.ERROR, "empty_response"))
        raise ExtractionError("LLM returned empty response")
