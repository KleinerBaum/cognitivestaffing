from __future__ import annotations

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
        "meta.input_method",
        "meta.source_url",
        "meta.upload_filename",
    ),
    allow_skip=False,
)
