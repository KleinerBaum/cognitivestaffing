"""Candidate profile summarisation pipeline."""

from __future__ import annotations

from typing import Any

from config import ModelTask
from openai_utils import call_chat_api
from schemas import PROFILE_SUMMARY_SCHEMA

__all__ = ["summarize_candidate"]


def summarize_candidate(cv_text: str, lang: str, candidate_id: str) -> Any:
    """Create a structured profile summary for a candidate CV."""

    system = {
        "role": "system",
        "content": "Erzeuge eine knappe, strukturierte Kandidatenzusammenfassung.",
    }
    user = {
        "role": "user",
        "content": (f"Sprache: {lang}\nCandidateID: {candidate_id}\nCV:\n{cv_text}"),
    }
    return call_chat_api(
        messages=[system, user],
        model="gpt-5-nano",
        temperature=0.2,
        json_schema={
            "name": "CandidateProfileSummary",
            "schema": PROFILE_SUMMARY_SCHEMA,
        },
        task=ModelTask.PROFILE_SUMMARY,
    )
