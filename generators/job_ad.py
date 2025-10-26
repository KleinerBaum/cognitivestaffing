"""Structured job ad generation."""

from __future__ import annotations

from typing import Any

from config import ModelTask, get_active_verbosity, get_model_for
from openai_utils import call_chat_api
from prompts import prompt_registry
from schemas import JOB_AD_SCHEMA

__all__ = ["generate_job_ad"]


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
    return call_chat_api(
        messages=[system, user],
        model=get_model_for(ModelTask.JOB_AD),
        temperature=0.4,
        json_schema={"name": "JobAd", "schema": JOB_AD_SCHEMA},
        task=ModelTask.JOB_AD,
        verbosity=get_active_verbosity(),
    )
