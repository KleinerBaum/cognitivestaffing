"""Abstraction over the OpenAI client for JSON extraction."""

from __future__ import annotations

import os
from typing import Any, Optional

import openai

from .context import build_extract_messages
from .prompts import FIELDS_ORDER
from core.schema import LIST_FIELDS, VacalyserJD
from core.errors import ExtractionError, JsonInvalid
from utils.json_parse import parse_extraction
from utils.retry import retry

MODE = os.getenv("LLM_MODE", "plain").lower()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _function_schema() -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for field in FIELDS_ORDER:
        if field in LIST_FIELDS:
            properties[field] = {
                "type": "array",
                "items": {"type": "string"},
                "description": field.replace("_", " "),
            }
        else:
            properties[field] = {
                "type": "string",
                "description": field.replace("_", " "),
            }
    return {
        "name": "return_extraction",
        "description": "Return extracted fields",
        "parameters": {"type": "object", "properties": properties},
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
                response = openai.ChatCompletion.create(  # type: ignore[attr-defined]
                    **common, response_format={"type": "json_object"}
                )
                return response["choices"][0]["message"]["content"].strip()
            if mode == "function":
                response = openai.ChatCompletion.create(  # type: ignore[attr-defined]
                    **common,
                    functions=[_function_schema()],
                    function_call={"name": "return_extraction"},
                )
                call = response["choices"][0]["message"].get("function_call", {})
                if call.get("arguments"):
                    return call["arguments"]
                continue
            response = openai.ChatCompletion.create(**common)  # type: ignore[attr-defined]
            return response["choices"][0]["message"]["content"].strip()
        except Exception as exc:  # pragma: no cover - network/SDK issues
            last_exc = exc
            continue

    raise ExtractionError("LLM call failed") from last_exc


def extract_and_parse(
    text: str, title: Optional[str] = None, url: Optional[str] = None
) -> VacalyserJD:
    """Extract fields and return a parsed :class:`VacalyserJD`.

    The function performs a second minimal-prompt attempt if the first
    response cannot be parsed as JSON.
    """

    raw = extract_json(text, title, url)
    try:
        return parse_extraction(raw)
    except JsonInvalid:

        def second_call() -> str:
            return extract_json(text, title, url, minimal=True)

        raw_retry = retry(second_call)
        try:
            return parse_extraction(raw_retry)
        except JsonInvalid as exc:  # pragma: no cover - defensive
            raise ExtractionError("Failed to parse AI response as JSON") from exc
