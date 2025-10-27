from __future__ import annotations

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
        "process.stages",
        "process.stakeholders",
        "process.onboarding_process",
    ),
    allow_skip=True,
)
