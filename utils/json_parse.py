"""Robust JSON parsing helpers for LLM outputs."""

from __future__ import annotations

import json
import re
from typing import Optional

from core.schema import VacalyserJD, coerce_and_fill
from core.errors import JsonInvalid, ModelResponseEmpty


def extract_first_json_block(s: str) -> Optional[str]:
    """Extract the first balanced JSON object from a string.

    Args:
        s: Raw string possibly containing JSON.

    Returns:
        The substring covering the first balanced JSON object, or ``None`` if
        no such block exists.
    """

    start = None
    depth = 0
    for i, ch in enumerate(s):
        if ch == "{":
            if start is None:
                start = i
            depth += 1
        elif ch == "}" and start is not None:
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    return None


def _strip_code_fences(text: str) -> str:
    """Remove Markdown code fences from text."""

    fence_re = re.compile(r"```(?:json)?\n?|```", re.IGNORECASE)
    return fence_re.sub("", text)


def parse_extraction(s: str) -> VacalyserJD:
    """Parse and validate a model extraction output.

    The function attempts to load JSON directly. If that fails, common artefacts
    like Markdown code fences or surrounding text are stripped and the first
    JSON object is extracted and parsed.

    Args:
        s: Model output potentially containing JSON.

    Returns:
        A normalised :class:`VacalyserJD` instance.

    Raises:
        ModelResponseEmpty: If the input string is empty.
        JsonInvalid: If no valid JSON object could be parsed.
    """

    if not s or not s.strip():
        raise ModelResponseEmpty("model response was empty")

    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        cleaned = _strip_code_fences(s)
        block = extract_first_json_block(cleaned)
        if not block:
            raise JsonInvalid("no JSON object found")
        try:
            data = json.loads(block)
        except json.JSONDecodeError as exc:
            raise JsonInvalid("could not parse JSON") from exc

    if not isinstance(data, dict):
        raise JsonInvalid("top-level JSON must be an object")

    return coerce_and_fill(data)
