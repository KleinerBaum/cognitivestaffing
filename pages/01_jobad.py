from __future__ import annotations

from .base import WizardPage


_SUMMARY_FIELDS: tuple[str, ...] = ()


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
    summary_fields=_SUMMARY_FIELDS,
    allow_skip=False,
)
