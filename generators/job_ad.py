"""Structured job ad generation."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from config import get_active_verbosity
from config.models import ModelTask, get_model_for
from exports.transform import build_v2_export_payload
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


def _inject_esco_references(payload: dict[str, Any]) -> dict[str, Any]:
    """Attach optional machine-readable ESCO references for downstream tooling."""

    position_raw = payload.get("position")
    requirements_raw = payload.get("requirements")
    position: Mapping[str, Any] = position_raw if isinstance(position_raw, Mapping) else {}
    requirements: Mapping[str, Any] = requirements_raw if isinstance(requirements_raw, Mapping) else {}
    refs = {
        "occupation": {
            "label": position.get("occupation_label"),
            "uri": position.get("occupation_uri"),
            "group": position.get("occupation_group"),
        },
        "skill_mappings": requirements.get("skill_mappings"),
    }
    meta_raw = payload.get("meta")
    meta: dict[str, Any] = dict(meta_raw) if isinstance(meta_raw, Mapping) else {}
    meta["esco_references"] = refs
    payload["meta"] = meta
    return payload


def _prepare_job_ad_payload(vacancy_json: Mapping[str, Any]) -> dict[str, Any]:
    """Apply V2 export decision filtering before prompting the model."""

    prepared = build_v2_export_payload(vacancy_json, artifact_key="job_ad_markdown")
    return _inject_esco_references(prepared)


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


def generate_job_ad(vacancy_json: Mapping[str, Any], lang: str, tone: str = "professional") -> Any:
    """Generate a structured job ad JSON payload."""

    locale = str(lang or "de")
    export_payload = _prepare_job_ad_payload(vacancy_json)
    system = {
        "role": "system",
        "content": prompt_registry.get("generators.job_ad.system", locale=locale),
    }
    user = {
        "role": "user",
        "content": f"Sprache: {lang}\nTon: {tone}\nProfil:\n{export_payload}",
    }
    result = call_chat_api(
        messages=[system, user],
        model=get_model_for(ModelTask.JOB_AD),
        temperature=0.4,
        json_schema={"name": "JobAd", "schema": JOB_AD_SCHEMA},
        task=ModelTask.JOB_AD,
        reasoning_effort="medium",
        verbosity=get_active_verbosity(),
    )
    _validate_job_ad_response(result)
    return result
