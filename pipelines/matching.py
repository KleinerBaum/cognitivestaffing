"""Candidate matching pipeline."""

from __future__ import annotations

from typing import Any

from config import ModelTask, get_active_verbosity, get_model_for
from openai_utils import call_chat_api
from prompts import prompt_registry
from schemas import CANDIDATE_MATCHES_SCHEMA

__all__ = ["match_candidates"]


def match_candidates(vacancy_json: dict, candidate_summaries: list[dict]) -> Any:
    """Return structured match scores for candidates against a vacancy."""

    system = {
        "role": "system",
        "content": prompt_registry.get("pipelines.matching.system"),
    }
    user = {
        "role": "user",
        "content": f"Vacancy:\n{vacancy_json}\n\nCandidates:\n{candidate_summaries}",
    }
    return call_chat_api(
        messages=[system, user],
        model=get_model_for(ModelTask.CANDIDATE_MATCHING),
        temperature=0.1,
        json_schema={"name": "CandidateMatches", "schema": CANDIDATE_MATCHES_SCHEMA},
        task=ModelTask.CANDIDATE_MATCHING,
        verbosity=get_active_verbosity(),
    )
