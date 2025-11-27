"""Structured job ad generation."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from config import get_active_verbosity
from config.models import ModelTask, get_model_for
from openai_utils import call_chat_api
from openai_utils.api import ChatCallResult
from prompts import prompt_registry
from schemas import JOB_AD_SCHEMA

__all__ = ["generate_job_ad"]


def _normalized_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _sequence_has_content(values: Any) -> bool:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return False
    return any(_normalized_text(item) for item in values)


def _validate_job_ad_sections(payload: Mapping[str, Any]) -> None:
    metadata = payload.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("Job ad generation returned no metadata block.")

    tone_value = _normalized_text(metadata.get("tone"))
    if not tone_value:
        raise ValueError("Job ad generation returned an empty tone value.")

    audience_value = _normalized_text(metadata.get("target_audience"))
    if not audience_value:
        raise ValueError("Job ad generation returned an empty target audience.")

    ad_block = payload.get("ad")
    if not isinstance(ad_block, Mapping):
        raise ValueError("Job ad generation returned no ad block.")

    sections = ad_block.get("sections")
    if not isinstance(sections, Mapping):
        raise ValueError("Job ad generation returned no sections block.")

    overview_text = _normalized_text(sections.get("overview"))
    if not overview_text:
        raise ValueError("Job ad generation returned an empty overview section.")

    if not _sequence_has_content(sections.get("responsibilities")):
        raise ValueError("Job ad generation returned empty responsibilities.")

    if not _sequence_has_content(sections.get("requirements")):
        raise ValueError("Job ad generation returned empty requirements.")

    how_to_apply = _normalized_text(sections.get("how_to_apply"))
    if not how_to_apply:
        raise ValueError("Job ad generation returned an empty how-to-apply section.")

    eos_text = _normalized_text(sections.get("equal_opportunity_statement"))
    if not eos_text:
        raise ValueError("Job ad generation returned an empty equal-opportunity section.")


def _validate_job_ad_response(result: ChatCallResult) -> None:
    raw_content = (result.content or "").strip()
    if not raw_content:
        raise ValueError("Job ad generation returned no content.")
    try:
        payload = json.loads(raw_content)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError("Job ad generation returned invalid JSON.") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("Job ad generation returned a non-object payload.")
    _validate_job_ad_sections(payload)


def generate_job_ad(vacancy_json: dict, lang: str, tone: str = "professional") -> Any:
    """Generate a structured job ad JSON payload."""

    locale = str(lang or "de")
    system = {
        "role": "system",
        "content": prompt_registry.get("generators.job_ad.system", locale=locale),
    }
    user = {
        "role": "user",
        "content": f"Sprache: {lang}\nTon: {tone}\nProfil:\n{vacancy_json}",
    }
    result = call_chat_api(
        messages=[system, user],
        model=get_model_for(ModelTask.JOB_AD),
        temperature=0.4,
        json_schema={"name": "JobAd", "schema": JOB_AD_SCHEMA},
        task=ModelTask.JOB_AD,
        verbosity=get_active_verbosity(),
    )
    _validate_job_ad_response(result)
    return result
