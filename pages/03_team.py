from __future__ import annotations

from .base import WizardPage


PAGE = WizardPage(
    key="team",
    label=("Team & Struktur", "Team & Structure"),
    panel_header=("Rahmen & Berichtslinien", "Context & reporting"),
    panel_subheader=("Struktur, Größe & Ansprechpartner", "Structure, size & stakeholders"),
    panel_intro_variants=(
        (
            "Skizziere Abteilung, Teamaufbau und Berichtslinien.",
            "Outline department, team setup, and reporting lines.",
        ),
        (
            "Diese Angaben helfen bei Follow-ups und der Teamdarstellung.",
            "These inputs guide follow-ups and how the team is presented.",
        ),
    ),
    required_fields=(),
    summary_fields=(
        "position.department",
        "position.team_structure",
        "position.team_size",
        "position.reporting_line",
        "position.reporting_manager_name",
    ),
    allow_skip=False,
)
