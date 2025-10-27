from __future__ import annotations

from .base import WizardPage


PAGE = WizardPage(
    key="benefits",
    label=("Vergütung & Benefits", "Compensation & benefits"),
    panel_header=("Vergütung", "Compensation"),
    panel_subheader=("Gehalt & Zusatzleistungen", "Salary & perks"),
    panel_intro_variants=(
        (
            "Lege Gehaltsrahmen, Bonusmodell und Benefits transparent fest.",
            "Set a clear salary range, bonus model, and benefit package.",
        ),
        (
            "Strukturierte Vergütungsdaten verbessern Marktplatz-Matching, Benchmarks und Angebotsunterlagen.",
            "Structured compensation data improves marketplace matching, benchmarking, and offer collateral.",
        ),
        (
            "Sag offen, was ihr zahlt und womit ihr Kandidat:innen begeistert.",
            "Be upfront about pay and the perks that make candidates excited.",
        ),
    ),
    required_fields=(),
    summary_fields=(
        "compensation.salary_min",
        "compensation.salary_max",
        "compensation.currency",
        "compensation.benefits",
    ),
    allow_skip=True,
)
