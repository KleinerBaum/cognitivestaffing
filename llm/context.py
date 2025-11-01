"""Builders for LLM prompt/message context."""

from __future__ import annotations

from typing import Mapping

from prompts import prompt_registry
from .prompts import (
    FIELDS_ORDER,
    SYSTEM_JSON_EXTRACTOR,
    build_user_json_extract_prompt,
    render_field_bullets,
    PreExtractionInsights,
)
from .output_parsers import get_need_analysis_output_parser
from nlp.prepare_text import truncate_smart

# Maximum character budget for user supplied text in prompts
MAX_CHAR_BUDGET = 12000


def build_extract_messages(
    text: str,
    title: str | None = None,
    company: str | None = None,
    url: str | None = None,
    locked_fields: Mapping[str, str] | None = None,
    insights: PreExtractionInsights | None = None,
) -> list[dict[str, str]]:
    """Construct messages for field extraction.

    Args:
        text: Job description text.
        title: Optional job title hint.
        company: Optional company name hint.
        url: Optional source URL.
        locked_fields: Fields with values that must stay untouched.
        insights: Optional hints from the pre-analysis chain.

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

    user_prompt = build_user_json_extract_prompt(
        filtered_fields,
        truncated,
        extras,
        locked_fields=locked_fields,
        insights=insights,
    )

    parser = get_need_analysis_output_parser()
    format_instructions = parser.format_instructions

    system_content = f"{SYSTEM_JSON_EXTRACTOR}\n\n{format_instructions}".strip()
    if locked_fields:
        system_content = f"{SYSTEM_JSON_EXTRACTOR} {LOCKED_SYSTEM_HINT}\n\n{format_instructions}".strip()

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_prompt},
    ]


LOCKED_SYSTEM_HINT = prompt_registry.get("llm.json_extractor.locked_system_hint")
PRE_ANALYSIS_SYSTEM = prompt_registry.get("llm.json_extractor.pre_analysis.system")
PRE_ANALYSIS_USER_TEMPLATE = prompt_registry.get("llm.json_extractor.pre_analysis.user")


def build_preanalysis_messages(
    text: str,
    *,
    title: str | None = None,
    company: str | None = None,
    url: str | None = None,
) -> list[dict[str, str]]:
    """Construct messages for the preliminary extraction analysis."""

    extras: dict[str, str] = {}
    if title:
        extras["title"] = title
    if company:
        extras["company"] = company
    if url:
        extras["url"] = url

    extras_lines = [f"{key.capitalize()}: {value}" for key, value in extras.items() if value]
    extras_block = "\n".join(extras_lines)
    truncated = truncate_smart(text or "", MAX_CHAR_BUDGET)

    user_content = PRE_ANALYSIS_USER_TEMPLATE.format(
        extras_block=f"{extras_block}\n\n" if extras_block else "",
        field_reference=render_field_bullets(),
        text=truncated,
    )

    return [
        {"role": "system", "content": PRE_ANALYSIS_SYSTEM},
        {"role": "user", "content": user_content},
    ]
