"""Fallback helpers that use the Responses API to repair profile JSON payloads."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from config import ModelTask, get_model_for, is_llm_enabled
from llm.openai_responses import build_json_schema_format, call_responses

logger = logging.getLogger(__name__)

_SCHEMA_NAME = "need_analysis_profile"
_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema" / "need_analysis.schema.json"


@lru_cache(maxsize=1)
def _load_schema() -> Mapping[str, Any] | None:
    """Return the cached NeedAnalysisProfile JSON schema."""

    try:
        with _SCHEMA_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        logger.error("Need analysis schema file missing: %s", _SCHEMA_PATH)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        logger.error("Failed to parse need analysis schema: %s", exc)
    return None


def _format_error_summary(errors: Sequence[Mapping[str, Any]] | None) -> str:
    """Return a bullet list describing validation issues."""

    if not errors:
        return "- (no validation details available)"
    lines: list[str] = []
    for entry in errors:
        loc = entry.get("loc")
        if isinstance(loc, (list, tuple)):
            path = ".".join(str(part) for part in loc if part is not None)
        else:
            path = str(loc or "<root>")
        message = str(entry.get("msg") or entry.get("type") or "invalid value")
        lines.append(f"- {path or '<root>'}: {message}")
    return "\n".join(lines)


def repair_profile_payload(
    payload: Mapping[str, Any], *, errors: Sequence[Mapping[str, Any]] | None = None
) -> Mapping[str, Any] | None:
    """Return a repaired NeedAnalysisProfile payload using an LLM fallback."""

    if not is_llm_enabled():
        logger.debug("Skipping JSON repair because no OpenAI API key is configured.")
        return None

    schema = _load_schema()
    if not schema:
        return None

    model = get_model_for(ModelTask.JSON_REPAIR)
    response_format = build_json_schema_format(name=_SCHEMA_NAME, schema=schema, strict=True)

    try:
        payload_text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    except TypeError:
        payload_text = json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True)

    error_summary = _format_error_summary(errors)
    system_prompt = (
        "You fix JSON objects for the hiring NeedAnalysisProfile schema. "
        "Return a single JSON object that conforms to the schema, preserves valid "
        "data, and leaves uncertain fields null. Do not include explanations."
    )
    user_prompt = (
        "Source JSON (may be invalid):\n"
        f"{payload_text}\n\n"
        "Validation issues:\n"
        f"{error_summary}\n\n"
        "Respond with corrected JSON only."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = call_responses(
            messages,
            model=model,
            response_format=response_format,
            temperature=0.0,
            max_tokens=1600,
            task=ModelTask.JSON_REPAIR,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("JSON repair call failed: %s", exc)
        return None

    if not response.content:
        logger.debug("JSON repair returned empty content.")
        return None

    try:
        repaired = json.loads(response.content)
    except json.JSONDecodeError as exc:
        logger.debug("JSON repair response was not valid JSON: %s", exc)
        return None

    if not isinstance(repaired, Mapping):
        logger.debug("JSON repair response was not an object: %s", type(repaired))
        return None

    return dict(repaired)


__all__ = ["repair_profile_payload"]
