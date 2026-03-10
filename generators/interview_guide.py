"""Structured interview guide generation."""

from __future__ import annotations

from typing import Any, Mapping

from config import get_active_verbosity
from config.models import ModelTask, get_model_for
from exports.transform import build_v2_export_payload
from openai_utils import call_chat_api
from prompts import prompt_registry
from schemas import INTERVIEW_GUIDE_SCHEMA

__all__ = ["generate_interview_guide"]


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


def _prepare_interview_payload(vacancy_json: Mapping[str, Any]) -> dict[str, Any]:
    """Apply V2 export decision filtering before prompting the model."""

    prepared = build_v2_export_payload(vacancy_json, artifact_key="interview_guide")
    return _inject_esco_references(prepared)


def generate_interview_guide(vacancy_json: Mapping[str, Any], lang: str) -> Any:
    """Generate an interview guide JSON payload for a vacancy."""

    locale = str(lang or "de")
    export_payload = _prepare_interview_payload(vacancy_json)
    system = {
        "role": "system",
        "content": prompt_registry.get(
            "generators.interview_guide.system",
            locale=locale,
            default=prompt_registry.get("generators.interview_guide.system", locale="en"),
        ),
    }
    user = {
        "role": "user",
        "content": f"Sprache: {lang}\nProfil:\n{export_payload}",
    }
    return call_chat_api(
        messages=[system, user],
        model=get_model_for(ModelTask.INTERVIEW_GUIDE),
        temperature=0.3,
        json_schema={"name": "InterviewGuide", "schema": INTERVIEW_GUIDE_SCHEMA},
        task=ModelTask.INTERVIEW_GUIDE,
        verbosity=get_active_verbosity(),
    )
