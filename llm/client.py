"""Abstraction over the OpenAI client for JSON extraction."""

from __future__ import annotations

import os
from typing import Any, Optional

import openai

from .context import build_extract_messages
from .prompts import FIELDS_ORDER
from core.schema import LIST_FIELDS

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


def extract_json(text: str, title: Optional[str] = None, url: Optional[str] = None) -> str:
    """Extract schema fields via the configured LLM mode.

    Args:
        text: Input job description.
        title: Optional job title for context.
        url: Optional source URL.

    Returns:
        Raw JSON string as returned by the model.
    """

    messages = build_extract_messages(text, title, url)
    common: dict[str, Any] = {"model": MODEL, "messages": messages, "temperature": 0}
    # Some SDKs support deterministic seeds
    common["seed"] = 42

    if MODE == "json":
        response = openai.ChatCompletion.create(
            **common, response_format={"type": "json_object"}
        )
        return response["choices"][0]["message"]["content"].strip()

    if MODE == "function":
        response = openai.ChatCompletion.create(
            **common,
            functions=[_function_schema()],
            function_call={"name": "return_extraction"},
        )
        call = response["choices"][0]["message"].get("function_call", {})
        return call.get("arguments", "")

    # Plain text fallback
    response = openai.ChatCompletion.create(**common)
    return response["choices"][0]["message"]["content"].strip()
