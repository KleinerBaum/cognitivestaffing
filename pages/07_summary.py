from __future__ import annotations

from .base import WizardPage


PAGE = WizardPage(
    key="summary",
    label=("Zusammenfassung", "Summary"),
    panel_header=("Bereit zum Export", "Ready to export"),
    panel_subheader=("Prüfe Ergebnisse", "Review the results"),
    panel_intro_variants=(
        (
            "Überprüfe Datenpunkte, generiere Anzeige oder Interviewleitfaden.",
            "Review the data points and generate the job ad or interview guide.",
        ),
        (
            "Von hier aus kannst du JSON, Markdown oder Analysen exportieren.",
            "From here you can export JSON, Markdown, or analysis outputs.",
        ),
    ),
    required_fields=(),
    summary_fields=(),
    allow_skip=False,
)
