from __future__ import annotations

from .base import WizardPage


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
