"""Abstraction over the OpenAI client for JSON extraction."""

from __future__ import annotations

import json
import re
import logging
from pathlib import Path
from typing import Any, Optional

from jsonschema import Draft7Validator
from openai import OpenAI
import streamlit as st

from openai_utils import model_supports_reasoning, model_supports_temperature
from .context import build_extract_messages
from .prompts import FIELDS_ORDER
from core.errors import ExtractionError
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, REASONING_EFFORT

logger = logging.getLogger("cognitive_needs.llm")


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

OPENAI_CLIENT = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL or None)


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

    messages = (
        _minimal_messages(text) if minimal else build_extract_messages(text, title, url)
    )
    effort = st.session_state.get("reasoning_effort", REASONING_EFFORT)
    model = st.session_state.get("model", OPENAI_MODEL)
    try:
        request: dict[str, Any] = {
            "model": model,
            "input": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": NEED_ANALYSIS_SCHEMA,
            },
        }
        if model_supports_reasoning(model):
            request["reasoning"] = {"effort": effort}
        if model_supports_temperature(model):
            request["temperature"] = 0
        response = OPENAI_CLIENT.responses.create(**request)
        return response.output_text.strip()
    except Exception as exc:  # pragma: no cover - network/SDK issues
        logger.warning(
            "Structured extraction failed, falling back to plain text: %s", exc
        )
        try:
            request = {
                "model": model,
                "input": messages,
            }
            if model_supports_reasoning(model):
                request["reasoning"] = {"effort": effort}
            if model_supports_temperature(model):
                request["temperature"] = 0
            response = OPENAI_CLIENT.responses.create(**request)
            return response.output_text.strip()
        except Exception as exc2:  # pragma: no cover - network/SDK issues
            raise ExtractionError("LLM call failed") from exc2
