"""Structured interview guide generation."""

from __future__ import annotations

from typing import Any

from config import ModelTask, get_model_for
from openai_utils import call_chat_api
from schemas import INTERVIEW_GUIDE_SCHEMA

__all__ = ["generate_interview_guide"]


def generate_interview_guide(vacancy_json: dict, lang: str) -> Any:
    """Generate an interview guide JSON payload for a vacancy."""

    system = {
        "role": "system",
        "content": "Erzeuge strukturierten Interviewleitfaden mit Scoringrubrik.",
    }
    user = {
        "role": "user",
        "content": f"Sprache: {lang}\nProfil:\n{vacancy_json}",
    }
    return call_chat_api(
        messages=[system, user],
        model=get_model_for(ModelTask.INTERVIEW_GUIDE),
        temperature=0.3,
        json_schema={"name": "InterviewGuide", "schema": INTERVIEW_GUIDE_SCHEMA},
        task=ModelTask.INTERVIEW_GUIDE,
    )
