from __future__ import annotations

from constants.keys import ProfilePaths

from .base import WizardPage


PAGE = WizardPage(
    key="jobad",
    label=("Stellenvorbereitung", "Job ad intake"),
    panel_header=("Erfasste Eingaben", "Captured inputs"),
    panel_subheader=("Aus der Anzeigenbasis", "From the source material"),
    panel_intro_variants=(
        (
            "Nutze Upload, URL oder Textfeld, um die Stelle zu initialisieren.",
            "Use upload, URL, or manual text to seed the wizard.",
        ),
        (
            "Alle Inhalte lassen sich anschließend verfeinern.",
            "You can refine all extracted details afterwards.",
        ),
    ),
    required_fields=(),
    summary_fields=(
        ProfilePaths.META_TARGET_START_DATE,
        ProfilePaths.META_APPLICATION_DEADLINE,
        ProfilePaths.META_FOLLOWUPS_ANSWERED,
    ),
    allow_skip=False,
)
