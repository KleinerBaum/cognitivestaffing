from __future__ import annotations

from .base import WizardPage


PAGE = WizardPage(
    key="benefits",
    label=("Vergütung & Benefits", "Compensation & benefits"),
    panel_header=("Vergütung", "Compensation"),
    panel_subheader=("Gehalt & Zusatzleistungen", "Salary & perks"),
    panel_intro_variants=(
        (
            "Definiere Rahmen, Bonus und Benefits – wichtig für Marktplatz & Ad.",
            "Define ranges, bonuses, and perks – vital for marketplace & ads.",
        ),
        (
            "Nutze Benchmarks, um Erwartungen realistisch zu halten.",
            "Use benchmarks to keep expectations realistic.",
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
