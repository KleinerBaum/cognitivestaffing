from __future__ import annotations

from .base import WizardPage


PAGE = WizardPage(
    key="summary",
    label=("Zusammenfassung", "Summary"),
    panel_header=("Bereit zum Export", "Ready to export"),
    panel_subheader=("Prüfe Ergebnisse", "Review the results"),
    panel_intro_variants=(
        (
            "Prüfe die wichtigsten Angaben und starte anschließend Export oder KI-Outputs.",
            "Double-check the key inputs before triggering exports or AI outputs.",
        ),
        (
            "Saubere Validierung hier stellt konsistente Daten für Anzeigen, Reports und Integrationen sicher.",
            "Thorough validation here ensures consistent data for ads, reports, and integrations.",
        ),
        (
            "Gönn dir einen letzten Blick, dann kannst du mit einem Klick exportieren oder teilen.",
            "Take one last look and then share or export everything with a single click.",
        ),
    ),
    required_fields=(),
    summary_fields=(),
    allow_skip=False,
)
