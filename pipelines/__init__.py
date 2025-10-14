"""High-level LLM pipelines for vacancy processing."""

from __future__ import annotations

__all__ = [
    "extract_vacancy_structured",
    "generate_followups",
    "summarize_candidate",
    "match_candidates",
]

from .extraction import extract_vacancy_structured
from .followups import generate_followups
from .profile_summary import summarize_candidate
from .matching import match_candidates
