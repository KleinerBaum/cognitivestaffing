from __future__ import annotations

from constants.keys import ProfilePaths
from core.schema import is_wizard_schema_enabled

from .base import WizardPage


if is_wizard_schema_enabled():
    _REQUIRED_FIELDS = ("role.purpose", "tasks.core")
    _SUMMARY_FIELDS = (
        "role.title",
        "role.purpose",
        "role.outcomes",
        "role.reports_to",
        "role.work_location",
        "role.work_model",
        "role.on_call",
        "tasks.core",
        "tasks.secondary",
        "tasks.success_metrics",
    )
else:
    _REQUIRED_FIELDS = tuple(
        field.value
        for field in (
            ProfilePaths.POSITION_ROLE_SUMMARY,
            ProfilePaths.RESPONSIBILITIES_ITEMS,
        )
    )
    _SUMMARY_FIELDS = tuple(
        field.value
        for field in (
            ProfilePaths.POSITION_ROLE_SUMMARY,
            ProfilePaths.RESPONSIBILITIES_ITEMS,
            ProfilePaths.POSITION_KEY_PROJECTS,
            ProfilePaths.POSITION_PERFORMANCE_INDICATORS,
            ProfilePaths.POSITION_DECISION_AUTHORITY,
        )
    )


PAGE = WizardPage(
    key="role_tasks",
    label=("Aufgaben", "Role tasks"),
    panel_header=("Kernaufgaben", "Core responsibilities"),
    panel_subheader=("Deliverables & Wirkung", "Deliverables & impact"),
    panel_intro_variants=(
        (
            "Fasse zusammen, welche Ergebnisse die Rolle kurzfristig liefern muss.",
            "Summarise the outcomes this role needs to deliver in the near term.",
        ),
        (
            "Konkret benannte Deliverables helfen bei Automatisierung von Anzeigen, Scorecards und Onboarding.",
            "Explicit deliverables feed automation for job ads, scorecards, and onboarding.",
        ),
        (
            "Schreibe locker runter, woran die Person in den ersten Monaten wirklich arbeitet.",
            "Jot down what this person will actually be tackling in the first months.",
        ),
    ),
    required_fields=_REQUIRED_FIELDS,
    summary_fields=_SUMMARY_FIELDS,
    allow_skip=False,
)
