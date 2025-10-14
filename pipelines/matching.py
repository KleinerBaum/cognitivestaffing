"""Candidate matching pipeline."""

from __future__ import annotations

from typing import Any

from config import ModelTask
from openai_utils import call_chat_api
from schemas import CANDIDATE_MATCHES_SCHEMA

__all__ = ["match_candidates"]


def match_candidates(vacancy_json: dict, candidate_summaries: list[dict]) -> Any:
    """Return structured match scores for candidates against a vacancy."""

    system = {
        "role": "system",
        "content": "Berechne Match-Scores 0..100, erkläre Gründe, markiere Gaps.",
    }
    user = {
        "role": "user",
        "content": f"Vacancy:\n{vacancy_json}\n\nCandidates:\n{candidate_summaries}",
    }
    return call_chat_api(
        messages=[system, user],
        model="gpt-5-mini",
        temperature=0.1,
        json_schema={"name": "CandidateMatches", "schema": CANDIDATE_MATCHES_SCHEMA},
        task=ModelTask.CANDIDATE_MATCHING,
    )
