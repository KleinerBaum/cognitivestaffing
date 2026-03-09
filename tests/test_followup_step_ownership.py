from __future__ import annotations

from wizard.validation import missing_inline_followups
from wizard_pages.base import WizardPage


def _page(key: str) -> WizardPage:
    return WizardPage(
        key=key,
        label=(key, key),
        panel_header=(key, key),
        panel_subheader=(key, key),
        panel_intro_variants=tuple(),
    )


def test_missing_inline_followups_routes_requirements_to_skills() -> None:
    followups = [
        {"field": "requirements.hard_skills_required", "priority": "critical"},
        {"field": "responsibilities.items", "priority": "critical"},
    ]

    role_tasks_missing = missing_inline_followups(
        _page("role_tasks"),
        profile={},
        followups=followups,
        session_state={},
    )
    skills_missing = missing_inline_followups(
        _page("skills"),
        profile={},
        followups=followups,
        session_state={},
    )

    assert role_tasks_missing == ["responsibilities.items"]
    assert skills_missing == ["requirements.hard_skills_required"]


def test_missing_inline_followups_uses_profile_values_as_fallback() -> None:
    followups = [{"field": "requirements.soft_skills_required", "priority": "critical"}]

    missing = missing_inline_followups(
        _page("skills"),
        profile={"requirements": {"soft_skills_required": ["Kommunikation"]}},
        followups=followups,
        session_state={},
    )

    assert missing == []
