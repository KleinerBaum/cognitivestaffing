"""Builders for LLM prompt/message context."""

from __future__ import annotations

from typing import Mapping, Optional

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
    locked_fields: Optional[Mapping[str, str]] = None,
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
    locked_mapping: Mapping[str, str] | None = locked_fields
    if locked_mapping:
        filtered_fields = [field for field in FIELDS_ORDER if not locked_mapping.get(field)]
        if not filtered_fields:
            filtered_fields = FIELDS_ORDER
    else:
        filtered_fields = FIELDS_ORDER

    user_prompt = USER_JSON_EXTRACT_TEMPLATE(
        filtered_fields,
        truncated,
        extras,
        locked_fields=locked_fields,
    )

    system_content = SYSTEM_JSON_EXTRACTOR
    if locked_fields:
        system_content = (
            f"{SYSTEM_JSON_EXTRACTOR} Keep locked fields unchanged in the JSON output; "
            "the application will supply their stored values."
        )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_prompt},
    ]
