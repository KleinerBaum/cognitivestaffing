from __future__ import annotations

from .base import WizardPage


PAGE = WizardPage(
    key="interview",
    label=("Interviewprozess", "Interview process"),
    panel_header=("Hiring Journey", "Hiring journey"),
    panel_subheader=("Phasen & Beteiligte", "Stages & stakeholders"),
    panel_intro_variants=(
        (
            "Skizziere Schritte, Dauer und Stakeholder für einen klaren Prozess.",
            "Outline steps, timing, and stakeholders for a clear process.",
        ),
        (
            "Diese Infos landen im Interviewleitfaden und der Zusammenfassung.",
            "These details power the interview guide and summary.",
        ),
    ),
    required_fields=(),
    summary_fields=(
        "process.stages",
        "process.stakeholders",
        "process.onboarding_process",
    ),
    allow_skip=True,
)
