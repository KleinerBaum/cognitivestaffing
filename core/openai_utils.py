"""OpenAI helper functions used across the project."""

from __future__ import annotations

import json
from typing import Any, Dict, List

try:  # pragma: no cover - optional dependency
    from openai import OpenAI  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

_client = OpenAI() if OpenAI else None


def call_chat_api(
    messages: List[Dict[str, str]],
    model: str | None = None,
    max_tokens: int = 500,
    temperature: float = 0.5,
) -> str:
    """Call the Chat Completions API and return the message content."""

    if _client is None:  # pragma: no cover - network not available
        return ""
    chat = _client.chat.completions.create(
        model=model or "gpt-4o-mini",
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    content = chat.choices[0].message.content or ""
    return content.strip()


def responses_json(**kwargs: Any) -> Dict[str, Any]:
    """Return parsed JSON from a Responses API call.

    Args:
        **kwargs: Parameters forwarded to ``client.responses.create``.

    Returns:
        Parsed JSON dictionary from the first ``output_text`` chunk.

    Raises:
        ValueError: If no JSON text could be extracted or parsing failed.
    """

    if _client is None:  # pragma: no cover - network not available
        raise ValueError("OpenAI client not available")

    resp = _client.responses.create(**kwargs)
    output = getattr(resp, "output", None)
    if output is None and isinstance(resp, dict):
        output = resp.get("output")
    for item in output or []:
        content = getattr(item, "content", None)
        if content is None and isinstance(item, dict):
            content = item.get("content")
        for part in content or []:
            part_type = getattr(part, "type", None)
            text = getattr(part, "text", None)
            if part_type is None and isinstance(part, dict):
                part_type = part.get("type")
                text = part.get("text")
            if part_type == "output_text":
                try:
                    return json.loads(text or "")
                except json.JSONDecodeError as exc:  # pragma: no cover - invalid caller
                    raise ValueError("Invalid JSON in response") from exc
    raise ValueError("No output_text in response")


__all__ = ["call_chat_api", "responses_json"]
