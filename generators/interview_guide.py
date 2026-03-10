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


def _prepare_interview_payload(vacancy_json: Mapping[str, Any]) -> dict[str, Any]:
    """Apply V2 export decision filtering before prompting the model."""

    return build_v2_export_payload(vacancy_json, artifact_key="interview_guide")


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
