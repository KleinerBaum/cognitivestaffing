"""Default payloads and helper factories for the RecruitingWizard schema."""

from __future__ import annotations

from typing import Any, Mapping

from .schema import RecruitingWizard, WIZARD_KEYS_CANONICAL

_REQUIRED_FIELD_REASONS: Mapping[str, str] = {
    "company.name": "Company name is required to personalise outputs.",
    "role.title": "Role title is required to scope the vacancy.",
    "summary.headline": "Headline is required to generate summaries and job ads.",
}


_DEFAULT_WIZARD_DATA: Mapping[str, Any] = {
    "company": {},
    "department": {},
    "team": {},
    "role": {},
    "tasks": {},
    "skills": {},
    "benefits": {},
    "interview_process": {},
    "summary": {},
    "sources": {},
    "missing_fields": {
        field: {"required": True, "reason": reason} for field, reason in _REQUIRED_FIELD_REASONS.items()
    },
}


def default_recruiting_wizard() -> RecruitingWizard:
    """Return the default wizard payload used for smoke tests and roundtrips."""

    payload = RecruitingWizard.model_validate(_DEFAULT_WIZARD_DATA)
    if WIZARD_KEYS_CANONICAL:  # defensive: ensure the schema stayed aligned.
        missing = sorted(
            key
            for key in payload.sources.root
            if key not in WIZARD_KEYS_CANONICAL  # type: ignore[attr-defined]
        )
        if missing:
            raise ValueError(f"Source map not aligned with canonical keys: {missing}")
    return payload


__all__ = ["default_recruiting_wizard"]
