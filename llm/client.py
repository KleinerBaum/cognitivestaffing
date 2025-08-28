"""Abstraction over the OpenAI client for JSON extraction."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from jsonschema import Draft7Validator
from openai import OpenAI

from .context import build_extract_messages
from .prompts import FIELDS_ORDER
from models.need_analysis import NeedAnalysisProfile
from core.errors import ExtractionError, JsonInvalid
from utils.json_parse import parse_extraction
from utils.retry import retry

logger = logging.getLogger("vacalyser.llm")


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


def _log_schema_errors(raw: str) -> None:
    """Validate raw JSON and log any schema inconsistencies."""

    try:
        instance = json.loads(raw)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to decode JSON for validation: %s", exc)
        return
    report = _generate_error_report(instance)
    if report:
        logger.error("Schema validation errors:\n%s", report)


SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "schema" / "need_analysis.schema.json"
)
with open(SCHEMA_PATH, "r", encoding="utf-8") as _f:
    NEED_ANALYSIS_SCHEMA = json.load(_f)
NEED_ANALYSIS_SCHEMA.pop("$schema", None)
NEED_ANALYSIS_SCHEMA.pop("title", None)
_assert_closed_schema(NEED_ANALYSIS_SCHEMA)

MODE = os.getenv("LLM_MODE", "plain").lower()
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-nano")
OPENAI_CLIENT = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))


def build_extraction_function() -> dict[str, Any]:
    """Return an OpenAI function schema for the vacancy profile."""

    return {
        "name": "return_extraction",
        "description": "Return extracted fields",
        "parameters": NEED_ANALYSIS_SCHEMA,
    }


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
    """Extract schema fields via the configured LLM mode.

    Structured output modes (JSON or function calls) are attempted first to
    reduce downstream parsing errors.

    Args:
        text: Input job description.
        title: Optional job title for context.
        url: Optional source URL.

    Returns:
        Raw JSON string as returned by the model.
    """

    messages = (
        _minimal_messages(text) if minimal else build_extract_messages(text, title, url)
    )
    common: dict[str, Any] = {"model": MODEL, "messages": messages, "temperature": 0}
    # Some SDKs support deterministic seeds
    common["seed"] = 42

    modes: list[str]
    if MODE == "plain":
        modes = ["json", "function", "plain"]
    else:
        modes = [MODE, "plain"] if MODE != "plain" else ["plain"]

    last_exc: Exception | None = None
    for mode in modes:
        try:
            if mode == "json":
                response = OPENAI_CLIENT.chat.completions.create(
                    **common, response_format={"type": "json_object"}
                )
                return response.choices[0].message.content.strip()
            if mode == "function":
                response = OPENAI_CLIENT.chat.completions.create(  # type: ignore[call-overload]
                    **common,
                    functions=[build_extraction_function()],
                    function_call={"name": "return_extraction"},
                )
                call = response.choices[0].message.function_call
                if call and getattr(call, "arguments", None):
                    return call.arguments
                continue
            response = OPENAI_CLIENT.chat.completions.create(**common)
            return response.choices[0].message.content.strip()
        except Exception as exc:  # pragma: no cover - network/SDK issues
            last_exc = exc
            continue

    raise ExtractionError("LLM call failed") from last_exc


def extract_and_parse(
    text: str, title: Optional[str] = None, url: Optional[str] = None
) -> NeedAnalysisProfile:
    """Extract fields and return a parsed :class:`NeedAnalysisProfile`.

    The function performs a second minimal-prompt attempt if the first
    response cannot be parsed as JSON.
    """

    raw = extract_json(text, title, url)
    _log_schema_errors(raw)
    try:
        return parse_extraction(raw)
    except JsonInvalid:

        def second_call() -> str:
            return extract_json(text, title, url, minimal=True)

        raw_retry = retry(second_call)
        _log_schema_errors(raw_retry)
        try:
            return parse_extraction(raw_retry)
        except JsonInvalid as exc:  # pragma: no cover - defensive
            raise ExtractionError("Failed to parse AI response as JSON") from exc
