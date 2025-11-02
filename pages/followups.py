from __future__ import annotations

from pages.base import WizardPage


PAGE = WizardPage(
    key="followups",
    label=("Q&A", "Q&A"),
    panel_header=("🔍 Zusatzinfos benötigt", "🔍 Additional info needed"),
    panel_subheader=("Antworten für einen vollständigen Datensatz", "Provide answers to complete the dataset"),
    panel_intro_variants=(
        (
            "Beantworte gezielte Anschlussfragen, um fehlende Angaben zu vervollständigen.",
            "Answer the targeted follow-up questions to complete missing details.",
        ),
        (
            "Die Antworten fließen direkt in die Struktur des Rollenprofils.",
            "Responses feed straight into the structured vacancy profile.",
        ),
    ),
    required_fields=(),
    summary_fields=(),
    allow_skip=False,
)
