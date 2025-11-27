"""High-level LLM pipelines for vacancy processing."""

from __future__ import annotations

__all__ = [
    "extract_vacancy_structured",
    "ExtractionResult",
    "extract_need_analysis_profile",
    "generate_followups",
    "summarize_candidate",
    "match_candidates",
    "generate_team_advice",
    "Task",
    "TaskStatus",
    "WorkflowRunner",
    "SkipTask",
]

from .extraction import extract_vacancy_structured
from .need_analysis import ExtractionResult, extract_need_analysis_profile
from .followups import generate_followups
from .team_advice import generate_team_advice
from .profile_summary import summarize_candidate
from .matching import match_candidates
from .workflow import SkipTask, Task, TaskStatus, WorkflowRunner
