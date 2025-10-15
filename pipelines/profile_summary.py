"""Candidate profile summarisation pipeline."""

from __future__ import annotations

from typing import Any

from config import ModelTask, get_active_verbosity, get_model_for
from openai_utils import call_chat_api
from schemas import PROFILE_SUMMARY_SCHEMA

__all__ = ["summarize_candidate"]


def summarize_candidate(cv_text: str, lang: str, candidate_id: str) -> Any:
    """Create a structured profile summary for a candidate CV."""

    system = {
        "role": "system",
        "content": (
            "Du bist eine strukturierte Talent-Analystin nach den GPT-5-Prompting-Guidelines. Plane kurz im Kopf, wie du vorge"
            "hst (Plan nicht ausgeben) und arbeite ihn konsequent ab. Folge diesen Schritten: 1) Lebenslauf vollständig lesen, "
            "2) Stärken, Erfahrungen und Risiken je Schemafeld sammeln, 3) Zusammenfassung validieren und auf Lücken prüfen. "
            "Beende deine Arbeit erst, wenn die Anfrage vollständig erfüllt ist, und liefere ausschließlich JSON nach Schema."
        ),
    }
    user = {
        "role": "user",
        "content": (f"Sprache: {lang}\nCandidateID: {candidate_id}\nCV:\n{cv_text}"),
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
