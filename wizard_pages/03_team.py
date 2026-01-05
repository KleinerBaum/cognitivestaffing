from __future__ import annotations

from .base import WizardPage


_REQUIRED_FIELDS: tuple[str, ...] = (
    "department.name",
    "team.reporting_line",
    "position.reporting_manager_name",
    "position.job_title",
)
_SUMMARY_FIELDS: tuple[str, ...] = (
    "department.name",
    "department.function",
    "department.leader_name",
    "department.leader_title",
    "department.strategic_goals",
    "team.name",
    "team.mission",
    "team.reporting_line",
    "team.headcount_current",
    "team.headcount_target",
    "team.collaboration_tools",
    "team.locations",
    "position.customer_contact_required",
    "position.customer_contact_details",
)


PAGE = WizardPage(
    key="team",
    label=("Team & Struktur", "Team & Structure"),
    panel_header=("Team & Struktur", "Team & Structure"),
    panel_subheader=("Berichtslinien & Teamaufbau", "Reporting & team setup"),
    panel_intro_variants=(
        (
            "Skizziere Struktur, Berichtslinien und Startzeitpunkt der Rolle.",
            "Outline the team structure, reporting line, and start timing for the role.",
        ),
        (
            "Präzise Angaben zu Seniorität, Reporting und Standort steuern Folgefragen und Automatisierung.",
            "Precise details on seniority, reporting, and location inform follow-up prompts and automation.",
        ),
        (
            "Erzähl kurz, wer die neue Person an die Hand nimmt und ab wann es losgeht.",
            "Let us know who the new hire reports to and when they’ll get started.",
        ),
    ),
    required_fields=_REQUIRED_FIELDS,
    summary_fields=_SUMMARY_FIELDS,
    allow_skip=False,
)
