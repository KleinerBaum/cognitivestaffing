from __future__ import annotations

from .base import WizardPage


_REQUIRED_FIELDS: tuple[str, ...] = ()
_SUMMARY_FIELDS: tuple[str, ...] = (
    "compensation.salary_min",
    "compensation.salary_max",
    "compensation.currency",
    "compensation.period",
    "compensation.variable_pay",
    "compensation.bonus_percentage",
    "compensation.commission_structure",
    "compensation.equity_offered",
    "compensation.benefits",
    "employment.relocation_support",
    "employment.travel_required",
    "employment.visa_sponsorship",
)


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
    required_fields=_REQUIRED_FIELDS,
    summary_fields=_SUMMARY_FIELDS,
    allow_skip=True,
)
