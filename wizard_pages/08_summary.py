from __future__ import annotations

from .base import WizardPage


_SUMMARY_FIELDS: tuple[str, ...] = (
    "summary.headline",
    "summary.value_proposition",
    "summary.culture_highlights",
    "summary.next_steps",
)


PAGE = WizardPage(
    key="summary",
    label=("Zusammenfassung", "Summary"),
    panel_header=("Letzter Check & Export", "Final check & export"),
    panel_subheader=("Fehlende Pflichtfelder erkennen und schließen", "Spot and close any missing critical fields"),
    panel_intro_variants=(
        (
            "Prüfe die wichtigsten Angaben, wir zeigen offene Pflichtfelder direkt an.",
            "Review the key inputs; we highlight any remaining critical fields for you.",
        ),
        (
            "Eine letzte Validierung stellt konsistente Daten für Anzeigen, Reports und Integrationen sicher.",
            "A final validation keeps ads, reports, and integrations consistent.",
        ),
        (
            "Letzter Blick und offene Antworten schließen – danach kannst du exportieren oder teilen.",
            "Take a last look, close any gaps, and then export or share.",
        ),
    ),
    required_fields=(),
    summary_fields=_SUMMARY_FIELDS,
    allow_skip=False,
)
