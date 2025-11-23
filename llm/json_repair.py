"""Fallback helpers that use the Responses API to repair profile JSON payloads."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from config import ModelTask, get_model_for, is_llm_enabled
from llm.openai_responses import build_json_schema_format, call_responses_safe
from llm.profile_normalization import normalize_interview_stages_field
from pydantic import AnyUrl, HttpUrl

logger = logging.getLogger(__name__)

_SCHEMA_NAME = "need_analysis_profile"
_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema" / "need_analysis.schema.json"


def _coerce_json_serializable(value: Any) -> Any:
    """Return ``value`` converted into a JSON-serializable structure."""

    if isinstance(value, (HttpUrl, AnyUrl)):
        return str(value)
    if isinstance(value, Mapping):
        return {key: _coerce_json_serializable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_coerce_json_serializable(item) for item in value]

    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


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

    serializable_payload = _coerce_json_serializable(payload)

    try:
        payload_text = json.dumps(serializable_payload, ensure_ascii=False, indent=2, sort_keys=True)
    except TypeError:
        fallback_payload = _coerce_json_serializable(dict(payload))
        try:
            payload_text = json.dumps(fallback_payload, ensure_ascii=False, indent=2, sort_keys=True)
        except TypeError:
            payload_text = json.dumps(
                fallback_payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=str,
            )

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
        response = call_responses_safe(
            messages,
            model=model,
            response_format=response_format,
            temperature=0.0,
            max_completion_tokens=1600,
            task=ModelTask.JSON_REPAIR,
            logger_instance=logger,
            context="json repair",
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("JSON repair call failed: %s", exc)
        return None

    if response is None:
        logger.warning("JSON repair call returned no content after fallback attempts")
        return None

    if response.used_chat_fallback:
        logger.info("JSON repair succeeded via classic chat fallback")

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

    result = dict(repaired)
    normalize_interview_stages_field(result)
    return result


__all__ = ["repair_profile_payload"]
