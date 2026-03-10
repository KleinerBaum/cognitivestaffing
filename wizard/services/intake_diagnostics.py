"""Intake diagnostics for V2 fast-path decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class IntakeDiagnosticsResult:
    coverage: float
    ambiguities: list[str]
    contradictions: list[str]
    recommendation: str
    focus_fields: tuple[str, ...]


def evaluate_intake_diagnostics(profile: Mapping[str, object]) -> IntakeDiagnosticsResult:
    """Assess intake quality and return a fast-path recommendation."""

    coverage_fields = (
        "intake.raw_input",
        "role.title",
        "role.summary",
        "work.responsibilities",
        "requirements.hard_skills_required",
        "constraints.timeline",
        "selection.process_steps",
    )
    filled = sum(1 for field in coverage_fields if _has_value(profile, field))
    coverage = filled / len(coverage_fields)

    ambiguities = _detect_ambiguities(profile)
    contradictions = _detect_contradictions(profile)

    if coverage >= 0.8 and not contradictions and len(ambiguities) <= 1:
        recommendation = "review"
        focus_fields: tuple[str, ...] = ()
    elif coverage >= 0.45:
        recommendation = "decision_board"
        focus_fields = _focus_fields_for_decisions(profile)
    else:
        recommendation = "guided_steps"
        focus_fields = (
            "role.summary",
            "work.responsibilities",
            "requirements.hard_skills_required",
        )

    return IntakeDiagnosticsResult(
        coverage=round(coverage, 3),
        ambiguities=ambiguities,
        contradictions=contradictions,
        recommendation=recommendation,
        focus_fields=focus_fields,
    )


def _has_value(profile: Mapping[str, object], path: str) -> bool:
    value: object | None = profile
    for part in path.split("."):
        if isinstance(value, Mapping):
            value = value.get(part)
        else:
            value = None
            break
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return value is not None


def _detect_ambiguities(profile: Mapping[str, object]) -> list[str]:
    ambiguities: list[str] = []
    role = profile.get("role")
    if isinstance(role, Mapping):
        summary = str(role.get("summary") or "").strip().lower()
        if summary in {"", "tbd", "to be defined", "n/a", "unknown"}:
            ambiguities.append("role.summary")

    requirements = profile.get("requirements")
    if isinstance(requirements, Mapping):
        hard_required = requirements.get("hard_skills_required")
        if isinstance(hard_required, list) and any(
            str(item).strip().lower() in {"tbd", "optional"} for item in hard_required
        ):
            ambiguities.append("requirements.hard_skills_required")
    return ambiguities


def _detect_contradictions(profile: Mapping[str, object]) -> list[str]:
    contradictions: list[str] = []
    constraints = profile.get("constraints")
    if isinstance(constraints, Mapping):
        salary_min = constraints.get("salary_min")
        salary_max = constraints.get("salary_max")
        if isinstance(salary_min, (int, float)) and isinstance(salary_max, (int, float)) and salary_min > salary_max:
            contradictions.append("constraints.salary_range")

    work = profile.get("work")
    if isinstance(work, Mapping):
        work_policy = str(work.get("work_policy") or "").strip().lower()
        location = str(work.get("location") or "").strip().lower()
        if work_policy == "remote" and location in {"onsite", "on-site", "office only"}:
            contradictions.append("work.location_policy")
    return contradictions


def _focus_fields_for_decisions(profile: Mapping[str, object]) -> tuple[str, ...]:
    ordered = (
        "requirements.hard_skills_required",
        "constraints.timeline",
        "selection.process_steps",
        "role.summary",
    )
    return tuple(field for field in ordered if not _has_value(profile, field))
