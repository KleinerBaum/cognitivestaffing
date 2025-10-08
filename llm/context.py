"""Builders for LLM prompt/message context."""

from __future__ import annotations

from typing import Optional

from .prompts import (
    FIELDS_ORDER,
    SYSTEM_JSON_EXTRACTOR,
    USER_JSON_EXTRACT_TEMPLATE,
)
from nlp.prepare_text import truncate_smart

# Maximum character budget for user supplied text in prompts
MAX_CHAR_BUDGET = 12000


def build_extract_messages(
    text: str,
    title: Optional[str] = None,
    company: Optional[str] = None,
    url: Optional[str] = None,
) -> list[dict[str, str]]:
    """Construct messages for field extraction.

    Args:
        text: Job description text.
        title: Optional job title hint.
        company: Optional company name hint.
        url: Optional source URL.

    Returns:
        A list of messages formatted for the OpenAI Responses API.
    """

    extras: dict[str, str] = {}
    if title:
        extras["title"] = title
    if company:
        extras["company"] = company
    if url:
        extras["url"] = url

    truncated = truncate_smart(text or "", MAX_CHAR_BUDGET)
    user_prompt = USER_JSON_EXTRACT_TEMPLATE(FIELDS_ORDER, truncated, extras)

    return [
        {"role": "system", "content": SYSTEM_JSON_EXTRACTOR},
        {"role": "user", "content": user_prompt},
    ]
