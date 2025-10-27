from __future__ import annotations

from constants.keys import ProfilePaths

from .base import WizardPage


PAGE = WizardPage(
    key="interview",
    label=("Interviewprozess", "Interview process"),
    panel_header=("Hiring Journey", "Hiring journey"),
    panel_subheader=("Phasen & Beteiligte", "Stages & stakeholders"),
    panel_intro_variants=(
        (
            "Skizziere Recruiting-Phasen, Dauer und beteiligte Personen für einen verlässlichen Ablauf.",
            "Map out the interview stages, timing, and stakeholders for a reliable journey.",
        ),
        (
            "Standardisierte Prozessdaten sichern Erwartungsmanagement, Candidate Experience und Auswertbarkeit.",
            "Standardised process data supports expectation management, candidate experience, and reporting.",
        ),
        (
            "Erzähl locker, wie Bewerber:innen durch euren Prozess gehen und wer sie dabei trifft.",
            "Give a quick rundown of how candidates move through your process and who they meet.",
        ),
    ),
    required_fields=(),
    summary_fields=(
        ProfilePaths.PROCESS_INTERVIEW_STAGES,
        ProfilePaths.PROCESS_PHASES,
        ProfilePaths.PROCESS_STAKEHOLDERS,
        ProfilePaths.PROCESS_RECRUITMENT_TIMELINE,
        ProfilePaths.PROCESS_PROCESS_NOTES,
        ProfilePaths.PROCESS_APPLICATION_INSTRUCTIONS,
        ProfilePaths.PROCESS_ONBOARDING_PROCESS,
        ProfilePaths.PROCESS_HIRING_MANAGER_NAME,
        ProfilePaths.PROCESS_HIRING_MANAGER_ROLE,
    ),
    allow_skip=True,
)
