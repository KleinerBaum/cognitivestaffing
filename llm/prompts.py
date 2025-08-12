"""Prompt templates for LLM interactions."""

from __future__ import annotations

from core.schema import ALL_FIELDS

# ----------------------------------------------------------------------------
# Field enumeration
# ----------------------------------------------------------------------------

# Export schema order for prompt rendering
FIELDS_ORDER: list[str] = ALL_FIELDS


def render_field_bullets() -> str:
    """Return fields as a bullet list in schema order."""
    return "\n".join(f"- {field}" for field in FIELDS_ORDER)


# ----------------------------------------------------------------------------
# Extraction templates
# ----------------------------------------------------------------------------

SYSTEM_JSON_EXTRACTOR: str = (
    "You are an extractor. Return ONLY a JSON object with the exact keys provided. "
    "Use empty strings for missing values and empty lists for missing arrays. No prose."
)


def USER_JSON_EXTRACT_TEMPLATE(
    fields_list: list[str], job_text: str, extras: dict | None = None
) -> str:
    """Render a user prompt for JSON field extraction.

    Args:
        fields_list: Fields to extract.
        job_text: Source text containing the information.
        extras: Optional additional context (e.g., title, url).

    Returns:
        A formatted prompt for the LLM user message.
    """

    extras = extras or {}
    extras_lines = [f"{k.capitalize()}: {v}" for k, v in extras.items() if v]
    extras_block = "\n".join(extras_lines)

    field_lines = "\n".join(f"- {f}" for f in fields_list)

    instructions = (
        "Extract the following fields and respond with a JSON object containing these keys. "
        "If data for a key is missing, use an empty string or empty list.\n"
        f"Fields:\n{field_lines}"
    )

    if extras_block:
        prompt = f"{extras_block}\n\n{instructions}\n\nText:\n{job_text}"
    else:
        prompt = f"{instructions}\n\nText:\n{job_text}"
    return prompt
