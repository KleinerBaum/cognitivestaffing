from __future__ import annotations

from .base import WizardPage


PAGE = WizardPage(
    key="role_tasks",
    label=("Rolle & Aufgaben", "Role & Tasks"),
    panel_header=("Kernaufgaben", "Core responsibilities"),
    panel_subheader=("Deliverables & Wirkung", "Deliverables & impact"),
    panel_intro_variants=(
        (
            "Beschreibe, was die Rolle wöchentlich leisten soll.",
            "Capture what the role delivers week-to-week.",
        ),
        (
            "Die Liste fließt in Anzeigen- und Interviewleitfäden ein.",
            "This list powers job ads and interview guides.",
        ),
    ),
    required_fields=(
        "position.role_summary",
        "responsibilities.items",
    ),
    summary_fields=(
        "position.role_summary",
        "responsibilities.items",
    ),
    allow_skip=False,
)
