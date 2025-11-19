"""Candidate profile summarisation pipeline."""

from __future__ import annotations

import json
from typing import Any, Mapping

from config import ModelTask, get_active_verbosity, get_model_for
from openai_utils import call_chat_api
from prompts import prompt_registry
from schemas import PROFILE_SUMMARY_SCHEMA

__all__ = ["summarize_candidate"]


def summarize_candidate(
    cv_text: str,
    lang: str,
    candidate_id: str,
    job_requirements: str | Mapping[str, Any] | None = None,
) -> Any:
    """Create a structured profile summary for a candidate CV and vacancy fit."""

    system = {
        "role": "system",
        "content": prompt_registry.get("pipelines.profile_summary.system"),
    }
    user = {
        "role": "user",
        "content": (
            "Sprache: {lang}\n".format(lang=lang)
            + f"CandidateID: {candidate_id}\n"
            + "Zielrolle / Target role requirements:\n"
            + _serialize_job_requirements(job_requirements)
            + "\n\nCV:\n"
            + cv_text
        ),
    }
    return call_chat_api(
        messages=[system, user],
        model=get_model_for(ModelTask.PROFILE_SUMMARY),
        temperature=0.2,
        json_schema={
            "name": "CandidateProfileSummary",
            "schema": PROFILE_SUMMARY_SCHEMA,
        },
        task=ModelTask.PROFILE_SUMMARY,
        verbosity=get_active_verbosity(),
    )


def _serialize_job_requirements(job_requirements: str | Mapping[str, Any] | None) -> str:
    if job_requirements is None:
        return "Keine Angaben / No requirements provided."

    if isinstance(job_requirements, str):
        cleaned = job_requirements.strip()
        return cleaned or "Keine Angaben / No requirements provided."

    try:
        return json.dumps(job_requirements, ensure_ascii=False, indent=2)
    except TypeError:
        return str(job_requirements)
