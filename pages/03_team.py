from __future__ import annotations

from .base import WizardPage


PAGE = WizardPage(
    key="team",
    label=("Team & Kontext", "Team & context"),
    panel_header=("Rahmen der Rolle", "Role context"),
    panel_subheader=("Berichtslinien & Timing", "Reporting & timing"),
    panel_intro_variants=(
        (
            "Definiere Titel, Seniorität und Ansprechpartner für die Rolle.",
            "Define title, seniority, and reporting lines for the role.",
        ),
        (
            "Diese Angaben steuern Follow-ups und Teamdarstellung.",
            "These inputs shape follow-ups and how the team is presented.",
        ),
    ),
    required_fields=("position.job_title",),
    summary_fields=(
        "position.job_title",
        "position.seniority_level",
        "position.reporting_line",
        "position.reporting_manager_name",
    ),
    allow_skip=False,
)
