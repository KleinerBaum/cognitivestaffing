from __future__ import annotations

from constants.keys import ProfilePaths

from .base import WizardPage


PAGE = WizardPage(
    key="team",
    label=("Team & Kontext", "Team & context"),
    panel_header=("Rahmen der Rolle", "Role context"),
    panel_subheader=("Berichtslinien & Timing", "Reporting & timing"),
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
    required_fields=(ProfilePaths.POSITION_JOB_TITLE,),
    summary_fields=(
        ProfilePaths.POSITION_JOB_TITLE,
        ProfilePaths.POSITION_SENIORITY,
        ProfilePaths.POSITION_DEPARTMENT,
        ProfilePaths.POSITION_TEAM_STRUCTURE,
        ProfilePaths.POSITION_TEAM_SIZE,
        ProfilePaths.POSITION_SUPERVISES,
        ProfilePaths.POSITION_REPORTING_LINE,
        ProfilePaths.POSITION_REPORTING_MANAGER_NAME,
        ProfilePaths.POSITION_OCCUPATION_LABEL,
        ProfilePaths.POSITION_OCCUPATION_URI,
        ProfilePaths.POSITION_OCCUPATION_GROUP,
    ),
    allow_skip=False,
)
