"""Abstraction over the OpenAI client for JSON extraction."""

from __future__ import annotations

import json
import re
import logging
from pathlib import Path
from typing import Any, Optional

from jsonschema import Draft7Validator
from langchain_core.runnables import RunnableLambda, RunnableSerializable
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pydantic import ValidationError
import streamlit as st

from openai_utils import call_chat_api
from .context import build_extract_messages
from .prompts import FIELDS_ORDER
from core.errors import ExtractionError
from config import REASONING_EFFORT, ModelTask, get_model_for
from models.need_analysis import NeedAnalysisProfile

logger = logging.getLogger("cognitive_needs.llm")
tracer = trace.get_tracer(__name__)


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
        raise ValueError(
            "Foreign key references are not allowed in function-calling schema:\n"
            + report
        )


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


SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "schema" / "need_analysis.schema.json"
)
with open(SCHEMA_PATH, "r", encoding="utf-8") as _f:
    raw = _f.read()
    cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
    NEED_ANALYSIS_SCHEMA = json.loads(cleaned)
NEED_ANALYSIS_SCHEMA.pop("$schema", None)
NEED_ANALYSIS_SCHEMA.pop("title", None)
_assert_closed_schema(NEED_ANALYSIS_SCHEMA)


def _build_structured_extraction_chain() -> RunnableSerializable[dict[str, Any], str]:
    """Create a LangChain runnable that validates model output against the schema."""

    def _call_model(payload: dict[str, Any]) -> dict[str, Any]:
        result = call_chat_api(
            payload["messages"],
            model=payload["model"],
            temperature=0,
            reasoning_effort=payload.get("reasoning_effort"),
            json_schema={
                "name": "need_analysis_profile",
                "schema": NEED_ANALYSIS_SCHEMA,
            },
        )
        content = (result.content or "").strip()
        if not content:
            raise ValueError("LLM returned empty response")
        return {"content": content}

    def _parse_json(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            data = json.loads(payload["content"])
        except json.JSONDecodeError as err:
            raise ValueError("Structured extraction did not return valid JSON") from err
        return {"content": payload["content"], "data": data}

    def _validate(payload: dict[str, Any]) -> dict[str, Any]:
        data = payload["data"]
        try:
            profile = NeedAnalysisProfile.model_validate(data)
        except ValidationError as err:
            report = _generate_error_report(data)
            if report:
                logger.debug("Schema validation errors:\n%s", report)
                if hasattr(err, "add_note"):
                    err.add_note(report)
            raise
        return {"validated": profile.model_dump(mode="json")}

    def _serialise(payload: dict[str, Any]) -> str:
        return json.dumps(payload["validated"], ensure_ascii=False)

    return (
        RunnableLambda(_call_model)
        | RunnableLambda(_parse_json)
        | RunnableLambda(_validate)
        | RunnableLambda(_serialise)
    )


_STRUCTURED_EXTRACTION_CHAIN = _build_structured_extraction_chain()


def _minimal_messages(text: str) -> list[dict[str, str]]:
    """Build a minimal prompt asking for raw JSON output."""

    keys = ", ".join(FIELDS_ORDER)
    return [
        {"role": "system", "content": f"Return JSON only with these keys: {keys}"},
        {"role": "user", "content": text},
    ]


def extract_json(
    text: str,
    title: Optional[str] = None,
    url: Optional[str] = None,
    *,
    minimal: bool = False,
) -> str:
    """Extract schema fields via JSON mode with optional plain fallback.

    Args:
        text: Input job posting.
        title: Optional job title for context.
        url: Optional source URL.

    Returns:
        Raw JSON string as returned by the model.
    """

    with tracer.start_as_current_span("llm.extract_json") as span:
        messages = (
            _minimal_messages(text)
            if minimal
            else build_extract_messages(text, title, url)
        )
        effort = st.session_state.get("reasoning_effort", REASONING_EFFORT)
        model = get_model_for(ModelTask.EXTRACTION)
        span.set_attribute("llm.model", model)
        span.set_attribute("llm.extract.minimal", minimal)
        try:
            output = _STRUCTURED_EXTRACTION_CHAIN.invoke(
                {
                    "messages": messages,
                    "model": model,
                    "reasoning_effort": effort,
                }
            )
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
            logger.warning(
                "Structured extraction failed, falling back to plain text: %s", exc
            )
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
